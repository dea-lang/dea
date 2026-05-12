#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Runtime coverage for L1 std.io numeric helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"


def resolve_tool(base: Path) -> Path:
    """Return a host-compatible launcher path for one tool base path."""

    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
        return base.with_suffix(".cmd")
    return base


def compiler_path() -> Path:
    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def run_mode(mode: str, stdin_text: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(compiler_path()),
            "-P",
            "compiler/stage1_l0/tests/fixtures/io_runtime",
            "--run",
            "io_numeric_main",
            "--",
            mode,
        ],
        cwd=L1_ROOT,
        input=stdin_text,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def require_run(mode: str, stdin_text: str, stdout: str, stderr: str = "") -> None:
    completed = run_mode(mode, stdin_text)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise AssertionError(f"{mode} exited with {completed.returncode}")
    assert completed.stdout == stdout, f"{mode} stdout mismatch: {completed.stdout!r}"
    assert completed.stderr == stderr, f"{mode} stderr mismatch: {completed.stderr!r}"


def main() -> int:
    require_run("delim", ",alpha beta;gamma", "\nalpha\nbeta\ngamma\n")
    require_run(
        "reads",
        "  -42 4294967295\n-9223372036854775808 18446744073709551615 bad",
        "-42\n4294967295\n-9223372036854775808\n18446744073709551615\ninvalid\n",
    )
    require_run("prints", "", "1 -2 3 1.5 0.25\n", "4 -5 6 2.5 0.125\n")
    require_run(
        "text",
        "",
        (
            "4294967295\n"
            "ffffffff\n"
            "-9223372036854775808\n"
            "-8000000000000000\n"
            "18446744073709551615\n"
            "ffffffffffffffff\n"
            "4294967295\n"
            "-9223372036854775808\n"
            "18446744073709551615\n"
            "invalids\n"
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
