#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Run one L1 Stage 1 test with trace collection."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile

from test_runner_common import (
    REPO_ROOT,
    discover_trace_l0_tests,
    repo_stage1_command,
    require_repo_stage1_test_env,
    stage1_support_args,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Run one L1 Stage 1 test with trace output.")
    parser.add_argument("test", help="Test name in compiler/stage1_l0/tests, with or without .l0.")
    return parser.parse_args()


def resolve_test_path(name: str) -> Path | None:
    """Resolve one trace-test name to its file path."""

    selector = Path(name).name
    for case in discover_trace_l0_tests():
        if selector == case.path.name or selector == case.path.stem:
            return case.path
    return None


def main() -> int:
    """Program entrypoint."""

    args = parse_args()
    test_path = resolve_test_path(args.test)
    if test_path is None:
        print(f"Error: Test file not found: compiler/stage1_l0/tests/{Path(args.test).name}", file=sys.stderr)
        print("Available tests in compiler/stage1_l0/tests:", file=sys.stderr)
        for case in discover_trace_l0_tests():
            print(f"  - {case.path.name}", file=sys.stderr)
        return 2

    try:
        _, _, _, repo_env = require_repo_stage1_test_env("run_test_trace.py")
    except RuntimeError as exc:
        print(f"run_test_trace.py: {exc}", file=sys.stderr)
        return 2

    artifact_dir = Path(tempfile.mkdtemp(prefix=f"{test_path.stem}."))
    stdout_path = artifact_dir / f"{test_path.stem}.stdout.log"
    stderr_path = artifact_dir / f"{test_path.stem}.stderr.log"

    print(f"stdout={stdout_path}")
    print(f"stderr={stderr_path}")

    import subprocess

    completed = subprocess.run(
        [
            *repo_stage1_command(),
            *stage1_support_args(),
            "--trace-memory",
            "--trace-arc",
            "--project-root",
            "compiler/stage1_l0/src",
            "--run",
            str(test_path),
        ],
        cwd=REPO_ROOT,
        env=repo_env,
        stdin=subprocess.DEVNULL,
        stdout=stdout_path.open("wb"),
        stderr=stderr_path.open("wb"),
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
