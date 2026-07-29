#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Run L1 Stage 1 trace checks."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

from run_tests import select_cases
from test_runner_common import (
    REPO_ROOT,
    SCRIPT_DIR,
    TRACE_EXCLUDED_STAGE1_TESTS,
    TRACE_SLOW_STAGE1_TESTS,
    discover_trace_l0_tests,
    first_lines,
    repo_stage1_command,
    require_repo_stage1_test_env,
    resolve_trace_job_count,
    run_captured_binary_output,
    stage1_support_args,
)


TRACE_CHECKER = SCRIPT_DIR / "check_trace_log.py"
TRACE_ARTIFACT_DIR_ENV = "L1_TRACE_ARTIFACT_DIR"


@dataclass(frozen=True)
class TraceResult:
    """One completed trace test result."""

    case_index: int
    case_name: str
    status: str
    report_text: str
    trace_text: str
    summary: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Run L1 Stage 1 ARC/memory trace checks.",
        epilog=(
            "Parallelism defaults to the normal bounded auto-detected worker count. "
            "Override with L1_TRACE_TEST_JOBS=<n> or L1_TEST_JOBS=<n>."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show analyzer details for each test.")
    parser.add_argument(
        "--include-slow",
        action="store_true",
        help="Include trace tests that are intentionally skipped by the default trace suite.",
    )
    parser.add_argument("--keep-artifacts", action="store_true", help="Keep trace/stdout/report files under the temp directory.")
    parser.add_argument(
        "--artifact-dir",
        help=(
            "Write trace/stdout/report files to this directory instead of a temporary location. "
            f"Also accepts ${TRACE_ARTIFACT_DIR_ENV}."
        ),
    )
    parser.add_argument("--max-details", type=int, default=5, help="Pass through to check_trace_log.py detail limit.")
    parser.add_argument(
        "tests",
        nargs="*",
        metavar="TEST",
        help="Optional L1 Stage 1 trace test name(s) to run. Match `tests/` file names exactly or omit the extension.",
    )
    return parser.parse_args(argv)


def resolve_artifact_dir(args: argparse.Namespace) -> tuple[Path, bool]:
    """Return the effective artifact directory and whether it should be cleaned up."""

    artifact_dir_text = (args.artifact_dir or os.environ.get(TRACE_ARTIFACT_DIR_ENV, "")).strip()
    if artifact_dir_text:
        artifact_dir = Path(artifact_dir_text).expanduser()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir.resolve(strict=False), False
    return Path(tempfile.mkdtemp(prefix="l1_stage1_trace_tests.")), not args.keep_artifacts


def read_text(path: Path) -> str:
    """Read one text file with replacement for invalid bytes."""

    return path.read_text(encoding="utf-8", errors="replace")


def leak_summary(report_text: str) -> str:
    """Return the leak summary fields from one trace report."""

    fields: list[str] = []
    for line in report_text.splitlines():
        if line.startswith("leaked_object_ptrs=") or line.startswith("leaked_string_ptrs="):
            fields.append(line)
    return " ".join(fields)


def run_one(
    case_index: int,
    case_name: str,
    case_path: Path,
    artifact_dir: Path,
    max_details: int,
    python_path: Path,
    repo_env: dict[str, str],
) -> TraceResult:
    """Run one trace test and analyze its log."""

    out_path = artifact_dir / f"{case_name}.stdout.log"
    trace_path = artifact_dir / f"{case_name}.stderr.log"
    report_path = artifact_dir / f"{case_name}.trace_report.txt"

    run_result = run_captured_binary_output(
        [
            *repo_stage1_command(),
            *stage1_support_args(),
            "--trace-memory",
            "--trace-arc",
            "--project-root",
            "compiler/stage1_l0/src",
            "--run",
            str(case_path),
        ],
        cwd=REPO_ROOT,
        env=repo_env,
        stdout_path=out_path,
        stderr_path=trace_path,
    )
    trace_text = read_text(trace_path)
    if run_result.returncode != 0:
        return TraceResult(case_index, case_name, "RUN_FAIL", "", trace_text, "")

    with report_path.open("w", encoding="utf-8") as report_file:
        analyzer_result = subprocess.run(
            [str(python_path), str(TRACE_CHECKER), str(trace_path), "--triage", "--max-details", str(max_details)],
            cwd=REPO_ROOT,
            env=repo_env,
            stdout=report_file,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    report_text = read_text(report_path)
    if analyzer_result.returncode == 0:
        return TraceResult(case_index, case_name, "TRACE_OK", report_text, trace_text, leak_summary(report_text))

    return TraceResult(case_index, case_name, "TRACE_FAIL", report_text, trace_text, "")


def main() -> int:
    """Program entrypoint."""

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    args = parse_args()
    try:
        jobs = resolve_trace_job_count()
    except ValueError as exc:
        print(f"run_trace_tests.py: {exc}", file=sys.stderr, flush=True)
        return 2
    try:
        python_path, _, _, repo_env = require_repo_stage1_test_env("run_trace_tests.py")
    except RuntimeError as exc:
        print(f"run_trace_tests.py: {exc}", file=sys.stderr, flush=True)
        return 2

    try:
        include_slow = args.include_slow or bool(args.tests)
        cases = select_cases(discover_trace_l0_tests(include_slow=include_slow), args.tests)
    except ValueError as exc:
        print(f"run_trace_tests.py: {exc}", file=sys.stderr, flush=True)
        return 2
    if not cases:
        print("No tests found in compiler/stage1_l0/tests", flush=True)
        return 0

    artifact_dir, cleanup_artifacts = resolve_artifact_dir(args)
    failed_names: list[str] = []
    passed = 0

    try:
        print("Running stage1_l0 trace checks...", flush=True)
        print(f"artifacts={artifact_dir}", flush=True)
        print(f"Parallel jobs: {jobs}", flush=True)
        if TRACE_EXCLUDED_STAGE1_TESTS:
            print(f"Skipping trace-incompatible tests: {' '.join(sorted(TRACE_EXCLUDED_STAGE1_TESTS))}", flush=True)
        if TRACE_SLOW_STAGE1_TESTS and not include_slow:
            print(
                "Skipping slow trace tests by default: "
                f"{' '.join(sorted(TRACE_SLOW_STAGE1_TESTS))} "
                "(use --include-slow or pass the test name explicitly)",
                flush=True,
            )
        print("======================================", flush=True)

        ready: dict[int, TraceResult] = {}
        next_index = 0

        def emit(result: TraceResult) -> None:
            nonlocal passed

            if result.status == "TRACE_OK":
                passed += 1
                if args.verbose:
                    print(f"Running {result.case_name}... PASS", flush=True)
                    print(result.report_text, flush=True)
                else:
                    summary = f" {result.summary}" if result.summary else ""
                    print(f"Running {result.case_name}... PASS{summary}", flush=True)
                return

            failed_names.append(result.case_name)
            print(f"Running {result.case_name}... FAIL", flush=True)
            if result.status == "RUN_FAIL":
                print(first_lines(result.trace_text, 40), flush=True)
            else:
                print(result.report_text, flush=True)

        with ThreadPoolExecutor(max_workers=jobs) as executor:
            future_map = {
                executor.submit(
                    run_one,
                    case.index,
                    case.name,
                    case.path,
                    artifact_dir,
                    args.max_details,
                    python_path,
                    repo_env,
                ): case.index
                for case in cases
            }
            for future in as_completed(future_map):
                result = future.result()
                ready[result.case_index] = result
                while next_index in ready:
                    emit(ready.pop(next_index))
                    next_index += 1

        print("======================================", flush=True)
        print(f"Passed: {passed}", flush=True)
        print(f"Failed: {len(failed_names)}", flush=True)
        if failed_names:
            print(f"Failed tests: {' '.join(failed_names)}", flush=True)
            return 1
        print("All trace tests passed!", flush=True)
        return 0
    finally:
        if cleanup_artifacts:
            shutil.rmtree(artifact_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
