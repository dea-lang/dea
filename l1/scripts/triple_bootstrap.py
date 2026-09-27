#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Establish the strict L1 Stage 2 fixed point and test the final compiler."""

from __future__ import annotations

import difflib
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from build_stage1_l1c import REPO_ROOT, normalize_l1_build_dir
from build_stage2_l1c import host_compiler
from bootstrap_identity import (
    assert_stable_native_toolchain, deterministic_c_flags, merge_cflags,
    normalized_native_artifact, uses_tcc,
)


def retained_inventory(root: Path) -> dict[str, bytes]:
    """Read the complete retained tree without transforming its contents.

    Args:
        root: Native output's retained-C directory.

    Returns:
        Relative file names mapped to their exact bytes.

    Raises:
        AssertionError: The tree is absent, incomplete, or contains unexpected files.
    """
    if root.is_symlink() or not root.is_dir():
        raise AssertionError(f"missing retained C tree: {root}")
    inventory = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise AssertionError(f"unexpected retained symlink: {path}")
        if path.is_file():
            if path.suffix != ".c":
                raise AssertionError(f"unexpected retained file: {path}")
            inventory[path.relative_to(root).as_posix()] = path.read_bytes()
    if "__dea_wrapper.c" not in inventory or len(inventory) < 2:
        raise AssertionError(f"incomplete retained C tree: {root}")
    return inventory


def compare_trees(left: Path, right: Path, expected_inventory: set[str] | None = None) -> None:
    """Require exact file inventory and bytes, without normalizing generated C.

    Args:
        left: Generation B's retained tree.
        right: Generation C's retained tree.
        expected_inventory: Optional complete inventory emitted by the Stage 1 oracle.

    Raises:
        AssertionError: An inventory or byte comparison fails.
    """
    a, b = retained_inventory(left), retained_inventory(right)
    if expected_inventory is not None and a.keys() != expected_inventory:
        raise AssertionError(f"retained inventory differs from Stage 1-built A: missing={sorted(expected_inventory-a.keys())}; extra={sorted(a.keys()-expected_inventory)}")
    if a.keys() != b.keys():
        raise AssertionError(f"retained inventory differs: missing={sorted(a.keys()-b.keys())}; extra={sorted(b.keys()-a.keys())}")
    for name in a:
        if a[name] != b[name]:
            diff = list(difflib.unified_diff(
                a[name].decode(errors="replace").splitlines(), b[name].decode(errors="replace").splitlines(),
                fromfile=f"B/{name}", tofile=f"C/{name}",
            ))[:80]
            raise AssertionError(f"retained C differs: {name}\n" + "\n".join(diff))


def run_logged(name: str, command: list[str], env: dict[str, str], artifacts: Path) -> None:
    """Run a bootstrap step and preserve its complete output on failure.

    Args:
        name: Stable step label used for its log.
        command: Explicit subprocess argument vector.
        env: Construction or test environment for this step.
        artifacts: Bootstrap-owned evidence directory.

    Raises:
        RuntimeError: The step exits unsuccessfully.
    """
    started = time.monotonic()
    log = artifacts / f"{name}.log"
    print(f"triple-bootstrap: {name}", flush=True)
    with log.open("wb") as stream:
        result = subprocess.run(command, cwd=REPO_ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    elapsed = time.monotonic() - started
    with (artifacts / "steps.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"step": name, "command": command, "seconds": elapsed,
                                 "exit_status": result.returncode}) + "\n")
    print(f"triple-bootstrap: {name}: {elapsed:.2f}s; log={log}", flush=True)
    if result.returncode:
        raise RuntimeError(f"{name} exited {result.returncode}\n{log.read_text(errors='replace')[-10000:]}")


def input_manifest(build_dir: Path) -> dict[str, str]:
    """Hash the source, interface, native support, and runtime inputs of all generations.

    Args:
        build_dir: Validated repo-local runtime and interface build directory.

    Returns:
        Repo-relative input names mapped to SHA-256 digests.
    """
    roots = [REPO_ROOT / path for path in (
        "compiler/stage2_l1/src", "compiler/stage1_l0/support", "compiler/shared",
    )]
    roots.extend(build_dir / name for name in ("interfaces", "include", "lib", "runtime/tcc"))
    return {str(path.relative_to(REPO_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for root in roots for path in sorted(root.rglob("*")) if path.is_file()}


def main() -> int:
    """Build A through Stage 1, B through A, C through B, then verify and test C."""
    layout = normalize_l1_build_dir(os.environ.get("L1_BUILD_DIR", "build/dea"))
    layout.build_dir.mkdir(parents=True, exist_ok=True)
    artifacts = Path(tempfile.mkdtemp(prefix="triple-bootstrap-", dir=layout.build_dir))
    keep = os.environ.get("KEEP_ARTIFACTS", "0") == "1"
    try:
        env = dict(os.environ)
        compiler = host_compiler(env)
        env.update(L1_CC=compiler, L1_RUNTIME_CC=compiler, L1_BUILD_DIR=str(layout.build_dir))
        env["L1_CFLAGS"] = merge_cflags(env.get("L1_CFLAGS", ""), deterministic_c_flags(compiler))
        # Keep preparation state local and identical across the three generations.
        env["L1_STDLIB_CACHE"] = str(artifacts / "stdlib-cache")
        env["L1_HOME"] = str(REPO_ROOT / "compiler")
        for key in ("L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_TEST_COMPILER"):
            env.pop(key, None)
        run_logged("native-toolchain", [compiler, "--version"], env, artifacts)
        assert_stable_native_toolchain(compiler, env["L1_CFLAGS"], artifacts)
        pinned = input_manifest(layout.build_dir)
        (artifacts / "inputs.json").write_text(json.dumps(pinned, indent=2) + "\n")
        controls = {key: value for key, value in env.items()
                    if key.startswith("L1_COMPILER_RT_") or key in ("L1_CC", "L1_RUNTIME_CC", "L1_CFLAGS")}
        (artifacts / "native-controls.json").write_text(json.dumps(controls, indent=2) + "\n")
        previous = layout.bin_dir / "l1c-stage1"
        outputs = []
        # Separate processes also isolate native support construction from test imports.
        for generation in ("A", "B", "C"):
            output = artifacts / generation / "bin" / "l1c-stage2.native"
            command = [sys.executable, "-c",
                       "import os,sys; from pathlib import Path; sys.path.insert(0,'scripts'); "
                       "from build_stage2_l1c import build_compiler; "
                       "build_compiler(Path(sys.argv[1]),Path(sys.argv[2]),dict(os.environ),keep_c=True)",
                       str(previous), str(output)]
            run_logged(f"build-{generation}", command, env, artifacts)
            if input_manifest(layout.build_dir) != pinned:
                raise AssertionError(f"bootstrap inputs changed while building {generation}")
            run_logged(f"version-{generation}", [str(output), "--version"], env, artifacts)
            if "Dea language / L1 compiler (Stage 2)" not in (artifacts / f"version-{generation}.log").read_text():
                raise AssertionError(f"wrong stage identity: {generation}")
            generated = retained_inventory(Path(str(output) + ".dea-c"))
            generated["<native>"] = output.read_bytes()
            report = [f"{name}\t{len(data)}\t{hashlib.sha256(data).hexdigest()}" for name, data in generated.items()]
            (artifacts / f"{generation}.sha256").write_text("\n".join(report) + "\n")
            outputs.append(output)
            previous = output
        b, c = outputs[1:]
        expected_inventory = set(retained_inventory(Path(str(outputs[0]) + ".dea-c")))
        compare_trees(Path(str(b) + ".dea-c"), Path(str(c) + ".dea-c"), expected_inventory)
        if uses_tcc(compiler) or os.name == "nt":
            print("triple-bootstrap: native identity skipped for TinyCC/Windows; exact C identity passed", flush=True)
        else:
            # Normalization names must remain distinct although native basenames match.
            normalized = []
            for label, output in (("B", b), ("C", c)):
                target = artifacts / f"{label}.native"
                shutil.copy2(output, target)
                normalized.append(normalized_native_artifact(target, artifacts))
            data = [path.read_bytes() for path in normalized]
            report = {label: {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
                      for label, value in zip(("B", "C"), data)}
            (artifacts / "normalized-native.json").write_text(json.dumps(report, indent=2) + "\n")
            if data[0] != data[1]:
                offsets = list(itertools.islice((index for index, pair in enumerate(zip(*data))
                                                 if pair[0] != pair[1]), 16))
                raise AssertionError(f"normalized native artifacts differ: {report}; first differing offsets={offsets}")
        inventory = retained_inventory(Path(str(c) + ".dea-c"))
        for name in ("interfaces", "include", "lib"):
            shutil.copytree(layout.build_dir / name, c.parent.parent / name)
        tcc_objects = layout.build_dir / "runtime/tcc"
        if tcc_objects.is_dir():
            shutil.copytree(tcc_objects, c.parent.parent / "runtime/tcc")
        test_env = {**env, "L1_TEST_COMPILER": str(c),
                    "L1_TEST_ORACLE": str(layout.bin_dir / "l1c-stage1"),
                    "L1_BUILD_DIR": str(c.parent.parent)}
        run_logged("final-suite", [sys.executable, "compiler/stage2_l1/scripts/run_tests.py", "--compiler", str(c)], test_env, artifacts)
        run_logged("final-examples", [sys.executable, "../scripts/check_examples.py", "--compiler", str(c),
                                     "--examples-dir", "examples", "--extension", ".l1", "--label", "L1 self-built Stage 2"], test_env, artifacts)
        run_logged("final-smoke", [str(c), "--run", "--project-root", "examples", "hello"], test_env, artifacts)
        print(f"triple-bootstrap: PASS ({len(inventory)} identical C translation units)", flush=True)
        return 0
    except Exception as exc:
        keep = True
        (artifacts / "failure.txt").write_text(str(exc) + "\n", encoding="utf-8")
        print(f"triple-bootstrap: FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        if keep:
            print(f"triple-bootstrap: artifacts={artifacts}", flush=True)
        else:
            shutil.rmtree(artifacts)


if __name__ == "__main__":
    raise SystemExit(main())
