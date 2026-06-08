#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for installed-prefix env leakage isolation."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from tool_test_common import (
    BUILD_TESTS_ROOT,
    MONOREPO_ROOT,
    REPO_ROOT,
    ToolTestFailure,
    assert_contains,
    assert_not_contains,
    native_path,
    repo_relative,
    run,
)


def fail(message: str) -> int:
    """Print one failure and return the shell-style exit code."""

    print(f"l0c_stage2_test_env_isolation_test: FAIL: {message}")
    return 1


def repo_python() -> Path:
    """Return the repo-local venv Python executable."""

    for candidate in (
            MONOREPO_ROOT / ".venv" / "bin" / "python",
            MONOREPO_ROOT / ".venv" / "bin" / "python.exe",
            MONOREPO_ROOT / ".venv" / "Scripts" / "python.exe",
    ):
        if candidate.is_file():
            return candidate
    raise ToolTestFailure("missing repo virtualenv python")


def run_trace_after_activation(prefix_dir: Path, dist_dir_rel: str, trace_log: Path) -> None:
    """Run trace helper after activating the installed environment."""

    if os.name == "nt":
        cmd_script = prefix_dir / "env-trace-probe.cmd"
        cmd_script.write_text(
            "@echo off\r\n"
            f"call \"{prefix_dir / 'bin' / 'l0-env.cmd'}\"\r\n"
            f"set DEA_BUILD_DIR={dist_dir_rel}\r\n"
            f"\"{repo_python()}\" \"{REPO_ROOT / 'compiler' / 'stage2_l0' / 'scripts' / 'run_test_trace.py'}\" parser_test\r\n",
            encoding="utf-8",
        )
        command = ["cmd.exe", "/d", "/s", "/c", str(cmd_script)]
    else:
        shell = shutil.which("bash") or shutil.which("sh")
        if shell is None:
            raise ToolTestFailure("bash or sh is required to validate l0-env.sh activation")
        command = [
            shell,
            "-lc",
            (
                f'. "{prefix_dir / "bin" / "l0-env.sh"}" && '
                f'DEA_BUILD_DIR="{dist_dir_rel}" '
                f'"{repo_python()}" ./compiler/stage2_l0/scripts/run_test_trace.py parser_test'
            ),
        ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    trace_log.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise ToolTestFailure(f"run_test_trace.py failed after sourcing the installed prefix env\n{completed.stdout}")


def main() -> int:
    """Program entrypoint."""

    prefix_dir = Path(tempfile.mkdtemp(prefix="scratch."))
    dist_dir_path: Path | None = None
    trace_log = Path(tempfile.gettempdir()) / f"l0_stage2_test_env_isolation_{os.getpid()}.log"
    try:
        BUILD_TESTS_ROOT.mkdir(parents=True, exist_ok=True)
        dist_dir_path = Path(tempfile.mkdtemp(prefix="l0_stage2_envdist.", dir=BUILD_TESTS_ROOT))
        dist_dir_rel = repo_relative(dist_dir_path)
        run(["make", f"DEA_BUILD_DIR={dist_dir_rel}", "install-dev-stage2"])
        run(["make", f"PREFIX={native_path(prefix_dir)}", "install"])
        run_trace_after_activation(prefix_dir, dist_dir_rel, trace_log)
        assert_contains(trace_log, "exit_code=0")
        assert_not_contains(trace_log, f"{prefix_dir}/stage1_py/l0c.py")
    except ToolTestFailure as exc:
        return fail(str(exc))
    finally:
        shutil.rmtree(prefix_dir, ignore_errors=True)
        if dist_dir_path is not None:
            shutil.rmtree(dist_dir_path, ignore_errors=True)
        trace_log.unlink(missing_ok=True)

    print("l0c_stage2_test_env_isolation_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
