#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Capture ARC and memory traces for one Stage 2 `.l0` test."""

from __future__ import annotations

import argparse
from pathlib import Path
import datetime as dt
import subprocess
import sys

from test_runner_common import (
    REPO_ROOT,
    SCRIPT_DIR,
    STAGE2_COMPILER_SUPPORT_SOURCE,
    TESTS_DIR,
    discover_l0_tests,
    require_repo_stage2_test_env,
    run_captured_binary_output,
    source_tree_l0c_command,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Capture Stage 2 trace logs for one `.l0` test.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--out",
        dest="trace_stderr_path",
        help="Path to write trace stderr output.",
    )
    parser.add_argument(
        "--stdout",
        dest="trace_stdout_path",
        help="Path to write program stdout output.",
    )
    parser.add_argument(
        "test_name",
        nargs="?",
        help="Test name in compiler/stage2_l0/tests, with or without .l0.",
    )

    args = parser.parse_args()
    if args.test_name is None:
        parser.print_usage(sys.stderr)
        print("run_test_trace.py: error: test_name is required", file=sys.stderr)
        print("", file=sys.stderr)
        print("Available tests in compiler/stage2_l0/tests:", file=sys.stderr)
        cases = discover_l0_tests()
        if not cases:
            print("  (none found)", file=sys.stderr)
        else:
            for case in cases:
                print(f"  - {case.name}", file=sys.stderr)
        raise SystemExit(2)

    return args


def resolve_test_path(test_name: str) -> Path:
    """Return the existing `.l0` test file for `test_name`."""

    file_name = test_name if test_name.endswith(".l0") else f"{test_name}.l0"
    path = TESTS_DIR / file_name
    if not path.is_file():
        print(f"Error: Test file not found: compiler/stage2_l0/tests/{file_name}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Available tests in compiler/stage2_l0/tests:", file=sys.stderr)
        for case in discover_l0_tests():
            print(f"  - {case.name}", file=sys.stderr)
        raise SystemExit(2)
    return path


def default_trace_paths() -> tuple[Path, Path]:
    """Return default stdout/stderr output paths."""

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path("/tmp") / f"l0_stage2_test_trace_{timestamp}"
    return base.with_suffix(".stderr.log"), base.with_suffix(".stdout.log")


def main() -> int:
    """Program entrypoint."""

    args = parse_args()
    test_path = resolve_test_path(args.test_name)
    try:
        python_path, _, _, repo_env = require_repo_stage2_test_env("run_test_trace.py")
    except RuntimeError as exc:
        print(f"run_test_trace.py: {exc}", file=sys.stderr)
        return 2

    default_stderr, default_stdout = default_trace_paths()
    stderr_path = Path(args.trace_stderr_path) if args.trace_stderr_path else default_stderr
    stdout_path = Path(args.trace_stdout_path) if args.trace_stdout_path else default_stdout

    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)

    trace_env = repo_env.copy()
    trace_env.setdefault("DEA_TRACE_FLUSH", "block")
    result = run_captured_binary_output(
        [
            *source_tree_l0c_command(),
            "--c-source",
            STAGE2_COMPILER_SUPPORT_SOURCE,
            "--project-root",
            "compiler/stage2_l0/src",
            "--run",
            "--trace-arc",
            "--trace-memory",
            str(test_path.relative_to(REPO_ROOT)),
        ],
        cwd=REPO_ROOT,
        env=trace_env,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    print(f"trace_stderr={stderr_path}")
    print(f"trace_stdout={stdout_path}")
    print(f"exit_code={result.returncode}")
    print("")
    print("triage with:")
    print("")
    print(f"\"{python_path}\" \"{SCRIPT_DIR / 'check_trace_log.py'}\" \"{stderr_path}\" --triage")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
