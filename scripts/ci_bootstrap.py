#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Run native CI delegates with explicit, same-run predecessor handoffs."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys

from dea_tooling.bootstrap import (resolve_bootstrap_compiler, resolve_l1_toolchain,
                                  wrapper_command, l1_bootstrap_environment)

ROOT = Path(__file__).resolve().parents[1]


def validate_l0(path_text: str, env: dict[str, str]) -> Path:
    """Check an explicitly supplied L0 Stage 2 compiler without building it.

    Args:
        path_text: Selected predecessor compiler path.
        env: Native toolchain environment.

    Returns:
        Absolute host-compatible predecessor path.

    Raises:
        RuntimeError: The supplied compiler is missing or has the wrong identity.
        subprocess.CalledProcessError: Compiler startup fails.
    """
    _, command = resolve_bootstrap_compiler(
        override_text=path_text, default_path=Path(path_text), env_var_name="CI_BOOTSTRAP_L0C",
        setup_hint="supply the L0 CI delegate output")
    result = subprocess.run([*command, "--version"], env=env, capture_output=True, text=True, check=True)
    banner = result.stdout.splitlines()[0] if result.stdout else ""
    if not banner.startswith("Dea language / L0 compiler") or "Stage 1" in banner:
        raise RuntimeError(f"incompatible L0 bootstrap identity: {banner!r}")
    return Path(command[0]).resolve()


def make_target(root: Path, level: str, target: str, env: dict[str, str]) -> None:
    """Execute one selected level-local Make target without shell interpolation.

    Args:
        root: Current checkout.
        level: Level containing the target.
        target: Make target and optional arguments.
        env: Selected native toolchain and bootstrap environment.

    Raises:
        ValueError: The selection is empty or malformed.
        subprocess.CalledProcessError: Make validation fails.
    """
    arguments = shlex.split(target)
    if not arguments:
        raise ValueError("CI_MAKE_TARGET must not be empty")
    subprocess.run(["make", "-C", str(root / level), *arguments], env=env, check=True)


def publish_compiler(root: Path, level: str, env: dict[str, str]) -> None:
    """Publish a compiler handoff only after successful validation produced it.

    Args:
        root: Current checkout.
        level: Validated predecessor level.
        env: Environment containing the GitHub output file.

    Raises:
        RuntimeError: A produced compiler is incomplete or incompatible.
        OSError: The output file cannot be written.
        subprocess.CalledProcessError: Compiler startup fails.
    """
    name = "l0c-stage2" if level == "l0" else "l1c"
    compiler = root / level / "build/dea/bin" / name
    command = Path(wrapper_command(compiler)[0])
    value = ""
    if command.is_file():
        selected = (validate_l0(str(compiler), env) if level == "l0" else
                    resolve_l1_toolchain(str(compiler), mode="development", env=env))
        value = str(selected)
    output = env.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"bootstrap_{level}c={value}\n")
    print(f"ci-bootstrap: {level} handoff: {value or '<not produced>'}", flush=True)


def run_delegate(level: str, source: dict[str, str], *, root: Path = ROOT) -> None:
    """Validate a level using handed-off or deliberately prepared predecessors.

    Args:
        level: Native CI delegate level.
        source: CI selection and native toolchain environment.
        root: Current checkout; overridden only by focused orchestration tests.

    Raises:
        ValueError: A required target or temporary directory is missing.
        RuntimeError: An explicit handoff or bootstrap mode is invalid.
        OSError: A compiler cannot be started.
        subprocess.CalledProcessError: Construction or validation fails.
    """
    env = dict(source)
    upstream = env.pop("CI_BOOTSTRAP_L0C", "").strip()
    if upstream:
        env["L1_BOOTSTRAP_L0C"] = str(validate_l0(upstream, env))
    if level == "l2":
        mode = env.pop("CI_BOOTSTRAP_MODE", "installed").strip()
        if mode not in {"installed", "development"}:
            raise RuntimeError("L2_BOOTSTRAP_MODE must be installed or development")
        compiler = env.pop("CI_BOOTSTRAP_L1C", "").strip()
        if not compiler:
            if mode == "development":
                make_target(root, "l1", "build", env)
                compiler = str(root / "l1/build/dea/bin/l1c")
            else:
                temporary = env.get("RUNNER_TEMP", "")
                if not temporary:
                    raise ValueError("RUNNER_TEMP is required to construct an installed L1 bootstrap")
                prefix = Path(temporary) / "l2-bootstrap-l1"
                subprocess.run(["make", "-C", str(root / "l1"), "install", f"PREFIX={prefix}"],
                               env=env, check=True)
                compiler = str(prefix / "bin/l1c")
        # The same sanitized environment is used by construction and every L2
        # implementation harness. An invalid explicit handoff never falls back.
        env["L2_BOOTSTRAP_MODE"] = mode
        build_dir = Path(env.get("L2_BUILD_DIR", "build/dea"))
        if not build_dir.is_absolute():
            build_dir = root / "l2" / build_dir
        env["L2_BOOTSTRAP_L1C"] = str(resolve_l1_toolchain(
            compiler, mode=mode, env=l1_bootstrap_environment(env, build_dir / "bootstrap-cache")))
        print(f"ci-bootstrap: reusing {mode} L1 compiler {env['L2_BOOTSTRAP_L1C']}", flush=True)
    make_target(root, level, env.get("CI_MAKE_TARGET", ""), env)
    if level == "l0" and env.get("RUNNER_OS") == "Windows":
        # Focused manual targets still get both full interpreter passes. Normal
        # aggregate targets already contain Stage 1 and must not repeat it.
        targets = shlex.split(env.get("CI_MAKE_TARGET", ""))
        if not {"test", "test-extended", "test-stage1"}.intersection(targets):
            make_target(root, "l0", "test-stage1", env)
    if level in {"l0", "l1"}:
        publish_compiler(root, level, env)


def main() -> int:
    """Run the selected native delegate and report bootstrap failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("level", choices=("l0", "l1", "l2"))
    args = parser.parse_args()
    try:
        run_delegate(args.level, dict(os.environ))
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ci-bootstrap: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
