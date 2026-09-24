#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Bootstrap semantic ownership, provider precedence, and CLI scope regressions."""

from __future__ import annotations

import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

from l1c_stage1_compile_only_test import stage1_compiler, resolve_deterministic_host_c_compiler

L1_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(L1_ROOT / "scripts"))
from build_stage1_l1c import L1BuildLayout, build_semantic_interfaces, provide_public_headers


def run(compiler: Path, root: Path, env: dict[str, str], *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    """Run a compiler case and preserve actionable output on failure.

    Args:
        compiler: Selected L1 executable.
        root: Invocation directory.
        env: Isolated command environment.
        *args: Compiler operands.
        expected: Required exit status.

    Returns:
        Captured compiler result.
    """
    result = subprocess.run([str(compiler), *args], cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == expected, (args, result.returncode, result.stdout, result.stderr)
    return result


def providers(result: subprocess.CompletedProcess[str]) -> dict[str, dict]:
    """Read selected provider events from a debug invocation.

    Args:
        result: Captured compiler output.

    Returns:
        Provider records keyed by canonical module name.
    """
    records = [json.loads(line.removeprefix("Preparation observation: "))
               for line in result.stderr.splitlines() if line.startswith("Preparation observation: ")]
    return {record["module"]: record for record in records if record["event"] == "provider"}


def main() -> int:
    """Verify semantic bootstrap with no native stdlib or runtime preparation."""
    compiler = stage1_compiler()
    native = compiler.parent / "l1c-stage1.native"
    cc = resolve_deterministic_host_c_compiler()
    assert native.is_file() and cc, "build Stage 1 and provide a host C compiler first"
    with tempfile.TemporaryDirectory(prefix="l1-semantic-test-") as temporary:
        root = Path(temporary).resolve()
        build = root / "build"
        build.mkdir()
        layout = L1BuildLayout(L1_ROOT, build, build / "bin", "unused", "unused")
        poison = root / "project"
        (poison / "std").mkdir(parents=True)
        (poison / "std/io.l1").write_text("module std.io; this is invalid source", encoding="utf-8")
        bad_cache = root / "not-a-cache"
        bad_cache.write_text("caller-owned file", encoding="utf-8")
        ambient = {**os.environ, "L1_SYSTEM": str(poison), "L1_STDLIB_CACHE": str(bad_cache),
                   "L1_CC": str(root / "missing-compiler"), "L1_RUNTIME_INCLUDE": str(poison)}
        with patch.dict(os.environ, ambient, clear=True):
            provide_public_headers(layout)
            build_semantic_interfaces(layout, native)
        expected_modules = {p.relative_to(L1_ROOT / "compiler/shared/l1/stdlib").with_suffix(".l1m")
                            for p in (L1_ROOT / "compiler/shared/l1/stdlib").rglob("*.l1")}
        assert {p.relative_to(build / "interfaces") for p in (build / "interfaces").rglob("*.l1m")} == expected_modules
        assert (build / "include/dea_rt.h").is_file() and (build / "include/l1_real.h").is_file()
        assert not (build / "lib").exists() and not (build / "runtime").exists() and not (build / "cache").exists()
        assert not list(build.rglob("*.o")) and not list(build.rglob("*.a"))
        source = root / "main.l1"
        source.write_text('module main; import std.io; func main() { printl_s("semantic-only"); }\n', encoding="utf-8")
        env = {**os.environ, "L1_HOME": str(L1_ROOT / "compiler"), "L1_BUILD_DIR": str(build),
               "L1_STDLIB_CACHE": str(bad_cache), "L1_CC": str(root / "missing-compiler")}
        for name in ("L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_CFLAGS"):
            env.pop(name, None)
        for mode in ("--check", "--emit-interface", "--gen"):
            result = run(native, root, env, mode, "--project-root", str(poison), str(source))
            assert "Preparing " not in result.stderr
        run(native, root, env, "--compile", "--c-compiler", cc, "main", "-o", str(root / "main.o"))
        assert not (build / "cache").exists()
        for mode in ("--tok", "--ast", "--sym", "--type"):
            inspected = run(native, root, env, mode, "--all-modules", "main")
            # Token dumps include source paths; match the default root spelling.
            source_inspected = run(native, root, env, mode, "--all-modules", "--sys-root",
                                   env["L1_HOME"] + "/shared/l1/stdlib", "main")
            assert inspected.stdout == source_inspected.stdout, mode
        # Equivalent system positions select the same managed interfaces, including aliases.
        bundled = L1_ROOT / "compiler/shared/l1/stdlib"
        baseline = providers(run(native, root, env, "--gen", "-vvv", "main"))
        assert baseline and all(item["managed"] and item["origin"] == "interface" for item in baseline.values())
        spellings = [str(bundled), os.path.relpath(bundled, root), str(bundled / ".." / "stdlib")]
        alias = root / "bundled-alias"
        try:
            alias.symlink_to(bundled, target_is_directory=True)
        except OSError as exc:
            print(f"bundled directory symlink unavailable: {exc}")
        else:
            spellings.append(str(alias))
        if os.name == "nt":
            junction = root / "bundled-junction"
            made = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(bundled)], capture_output=True)
            if made.returncode == 0:
                spellings.append(str(junction))
            else:
                print(f"bundled directory junction unavailable: {made.stderr!r}")
        for spelling in spellings:
            selected = run(native, root, env, "--gen", "-vvv", "--sys-root", spelling, "main")
            assert providers(selected) == baseline
            assert "explicit-system-root" not in selected.stderr
        assert providers(run(native, root, {**env, "L1_SYSTEM": str(bundled)}, "--gen", "-vvv", "main")) == baseline
        run(native, root, env, "--compile", "--sys-root", str(bundled), "--c-compiler", cc,
            "main", "-o", str(root / "explicit.o"))
        # The explicit opt-out also works without an explicit root and without any semantic bootstrap.
        unbuilt_env = {**env, "L1_BUILD_DIR": str(root / "unbuilt")}
        for roots in ([], ["--sys-root", str(bundled)]):
            selected = run(native, root, unbuilt_env, "--gen", "-vvv", "--no-managed-stdlib", *roots, "main")
            assert providers(selected) and all(not item["managed"] and item["origin"] == "source"
                                               for item in providers(selected).values())
            assert '"reason":"no-managed-stdlib"' in selected.stderr
        run(native, root, env, "--compile", "--no-managed-stdlib", "--c-compiler", cc,
            "main", "-o", str(root / "source.o"), expected=1)
        # Copies remain ordinary sources, even when their contents match exactly.
        copied = root / "copied-stdlib"
        shutil.copytree(bundled, copied)
        selected = run(native, root, unbuilt_env, "--gen", "-vvv", "--sys-root", str(copied), "main")
        assert providers(selected) and all(not item["managed"] for item in providers(selected).values())
        # A prior custom provider wins; a later custom provider cannot shadow the bundled position.
        run(native, root, env, "--gen", "--sys-root", str(poison), "--sys-root", str(bundled), "main", expected=1)
        assert providers(run(native, root, env, "--gen", "-vvv", "--sys-root", str(bundled),
                             "--sys-root", str(poison), "main")) == baseline
        empty = root / "empty-system"
        empty.mkdir()
        assert providers(run(native, root, env, "--gen", "-vvv", "--sys-root", str(empty),
                             "--sys-root", str(bundled), "main")) == baseline
        # An explicitly requested bundled module remains a source target.
        target = run(native, root, env, "--gen", "-vvv", "--sys-root", str(bundled), "std.io")
        assert providers(target)["std.io"]["origin"] == "source"
        assert not providers(target)["std.io"]["managed"]
        # Caller-selected system roots suppress the managed bundled position.
        for altered_env, extra in ((env, ["--sys-root", str(poison)]), ({**env, "L1_SYSTEM": str(poison)}, [])):
            run(native, root, altered_env, "--gen", *extra, "main", expected=1)
        # Bundled sources selected through a project root retain source-backed semantics.
        caller_system = root / "caller-system"
        caller_system.mkdir()
        project_env = {**env, "L1_SYSTEM": str(caller_system), "L1_BUILD_DIR": str(root / "unbuilt")}
        run(native, root, project_env, "--gen", "--project-root", str(L1_ROOT / "compiler/shared/l1/stdlib"), str(source))
        run(native, root, project_env, "--compile", "--c-compiler", cc, "--project-root",
            str(L1_ROOT / "compiler/shared/l1/stdlib"), str(source), expected=1)
        missing = build / "interfaces/std/io.l1m"
        saved = missing.read_bytes()
        missing.unlink()
        absent = run(native, root, env, "--gen", "main", expected=1)
        assert "L1C-2158" in absent.stderr and "build-stage1" in absent.stderr
        explicit_absent = run(native, root, env, "--gen", "--sys-root", str(bundled), "main", expected=1)
        assert "L1C-2158" in explicit_absent.stderr
        run(native, root, env, "--gen", "--no-managed-stdlib", "main")
        missing.write_bytes(b"invalid bundled interface")
        corrupt = run(native, root, env, "--gen", "main", expected=1)
        assert "L1C-2158" in corrupt.stderr and "build-stage1" in corrupt.stderr
        explicit_corrupt = run(native, root, env, "--gen", "--sys-root", str(bundled), "main", expected=1)
        assert "L1C-2158" in explicit_corrupt.stderr
        missing.write_bytes(saved)
        # A selected explicit interface remains authoritative even if malformed.
        explicit = root / "explicit/std"
        explicit.mkdir(parents=True)
        (explicit / "io.l1m").write_text("invalid interface", encoding="utf-8")
        for extra in ([], ["--sys-root", str(bundled)], ["--no-managed-stdlib"]):
            invalid = run(native, root, env, "--gen", *extra, "-I", str(explicit.parent), "main", expected=1)
            assert "L1C-2158" not in invalid.stderr
        # A valid explicit interface still wins when automatic managed discovery is disabled.
        explicit_selected = providers(run(native, root, env, "--gen", "-vvv", "--no-managed-stdlib",
                                         "-I", str(build / "interfaces"), "main"))
        assert explicit_selected and all(item["origin"] == "interface" and not item["managed"]
                                         for item in explicit_selected.values())
        run(native, root, env, "--link", str(root / "main.o"), "-I", str(explicit.parent), "-o", str(root / "app"), expected=1)
        for mode in ("--compile", "--gen", "--check", "--emit-interface", "--tok", "--ast", "--sym", "--type"):
            for control in ("--stdlib-cache=cache", "--no-auto-prepare", "--force"):
                run(native, root, env, mode, control, "main", expected=2)
        for args in (("--prepare-stdlib", "main"), ("--prepare-stdlib", "--no-auto-prepare"),
                     ("--build", "--force", "main"), ("--prepare-stdlib", "-I", str(root)),
                     ("--prepare-stdlib", "--sys-root", str(root)),
                     ("--prepare-stdlib", "--project-root", str(root)),
                     ("--prepare-stdlib", "--runtime-lib", str(root)),
                     ("--prepare-stdlib", "--foreign-object", str(root / "main.o")),
                     ("--prepare-stdlib", "-l", "unused"), ("--prepare-stdlib", "-o", "unused"),
                     ("--prepare-stdlib", "--keep-c"), ("--prepare-stdlib", "--", "unused"),
                     ("--prepare-stdlib", "--stdlib-cache="), ("--prepare-stdlib", "--force", "--run", "main")):
            run(native, root, env, *args, expected=2)
        for mode, operands in (("--link", [str(root / "main.o"), "-o", str(root / "app")]),
                               ("--prepare-stdlib", [])):
            rejected = run(native, root, env, mode, "--no-managed-stdlib", *operands, expected=2)
            assert "L1C-2157" in rejected.stderr
        for removed in ("--no-stdlib-cache", "--system-stdlib-cache", "--cache-scope", "--clean-cache", "--scrub"):
            run(native, root, env, removed, "main", expected=2)
    print("bootstrap semantic interfaces, provider precedence, and preparation CLI scope: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
