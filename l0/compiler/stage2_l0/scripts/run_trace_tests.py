#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Run Stage 2 trace checks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from test_runner_common import (
    REPO_ROOT,
    SCRIPT_DIR,
    STAGE2_COMPILER_SUPPORT_SOURCE,
    TRACE_EXCLUDED_L0_TESTS,
    discover_trace_l0_tests,
    first_lines,
    require_repo_stage2_test_env,
    resolve_trace_job_count,
    run_captured_binary_output,
    source_tree_l0c_command,
)
from run_tests import select_cases

TRACE_CHECKER = SCRIPT_DIR / "check_trace_log.py"


@dataclass(frozen=True)
class TraceResult:
    """One completed trace test result."""

    case_index: int
    case_name: str
    status: str
    report_text: str
    failure_excerpt: str
    summary: str
    trace_path: Path
    run_seconds: float
    analyzer_seconds: float
    trace_bytes: int
    event_count: int | None


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Run Stage 2 ARC/memory trace checks.",
        epilog="Parallelism defaults to a bounded auto-detected worker count. Override with L0_TEST_JOBS=<n>.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show analyzer details for each test.")
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep trace/stdout/report files under the temp directory.",
    )
    parser.add_argument(
        "--max-details",
        type=int,
        default=5,
        help="Pass through to check_trace_log.py detail limit (default: 5).",
    )
    parser.add_argument(
        "tests",
        nargs="*",
        metavar="TEST",
        help="Optional Stage 2 trace test name(s) to run. Match `tests/` file names exactly or omit the extension.",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    """Read one text file with replacement for invalid bytes."""

    return path.read_text(encoding="utf-8", errors="replace")


def read_text_excerpt(path: Path, max_bytes: int = 64 * 1024) -> str:
    """Read a bounded leading excerpt from one artifact."""

    with path.open("rb") as artifact_file:
        data = artifact_file.read(max_bytes + 1)
    truncated = len(data) > max_bytes
    text = data[:max_bytes].decode("utf-8", errors="replace")
    if truncated:
        text += f"\n... trace excerpt truncated after {max_bytes} bytes ...\n"
    return text


def leak_summary(report_text: str) -> str:
    """Return the leak summary fields from one trace report."""

    fields: list[str] = []
    for line in report_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("leaked_object_ptrs=") or stripped.startswith("leaked_string_ptrs="):
            fields.append(stripped)
    if not fields:
        return ""
    return " ".join(fields)


def parsed_event_count(report_text: str) -> int | None:
    """Return the analyzer's total parsed event count, when present."""

    for line in report_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("total_events="):
            try:
                return int(stripped.partition("=")[2])
            except ValueError:
                return None
    return None


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

    trace_env = repo_env.copy()
    trace_env.setdefault("DEA_TRACE_FLUSH", "block")
    run_started = time.perf_counter()
    run_result = run_captured_binary_output(
        [
            *source_tree_l0c_command(),
            "--trace-memory",
            "--trace-arc",
            "--c-source",
            STAGE2_COMPILER_SUPPORT_SOURCE,
            "--project-root",
            "compiler/stage2_l0/src",
            "--run",
            str(case_path),
        ],
        cwd=REPO_ROOT,
        env=trace_env,
        stdout_path=out_path,
        stderr_path=trace_path,
    )
    run_seconds = time.perf_counter() - run_started
    if run_result.returncode != 0:
        return TraceResult(
            case_index=case_index,
            case_name=case_name,
            status="RUN_FAIL",
            report_text="",
            failure_excerpt=read_text_excerpt(trace_path),
            summary="",
            trace_path=trace_path,
            run_seconds=run_seconds,
            analyzer_seconds=0.0,
            trace_bytes=run_result.stderr_bytes,
            event_count=None,
        )

    analyzer_started = time.perf_counter()
    with report_path.open("w", encoding="utf-8") as report_file:
        analyzer_result = subprocess.run(
            [
                str(python_path),
                str(TRACE_CHECKER),
                str(trace_path),
                "--triage",
                "--max-details",
                str(max_details),
            ],
            cwd=REPO_ROOT,
            env=trace_env,
            stdout=report_file,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    analyzer_seconds = time.perf_counter() - analyzer_started

    report_text = read_text(report_path)
    event_count = parsed_event_count(report_text)
    if analyzer_result.returncode == 0:
        return TraceResult(
            case_index=case_index,
            case_name=case_name,
            status="TRACE_OK",
            report_text=report_text,
            failure_excerpt="",
            summary=leak_summary(report_text),
            trace_path=trace_path,
            run_seconds=run_seconds,
            analyzer_seconds=analyzer_seconds,
            trace_bytes=run_result.stderr_bytes,
            event_count=event_count,
        )

    return TraceResult(
        case_index=case_index,
        case_name=case_name,
        status="TRACE_FAIL",
        report_text=report_text,
        failure_excerpt="",
        summary="",
        trace_path=trace_path,
        run_seconds=run_seconds,
        analyzer_seconds=analyzer_seconds,
        trace_bytes=run_result.stderr_bytes,
        event_count=event_count,
    )


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
        python_path, _, _, repo_env = require_repo_stage2_test_env("run_trace_tests.py")
    except RuntimeError as exc:
        print(f"run_trace_tests.py: {exc}", file=sys.stderr, flush=True)
        return 2

    try:
        cases = select_cases(discover_trace_l0_tests(), args.tests)
    except ValueError as exc:
        print(f"run_trace_tests.py: {exc}", file=sys.stderr, flush=True)
        return 2
    if not cases:
        print("No tests found in compiler/stage2_l0/tests", flush=True)
        return 0

    artifact_dir = Path(tempfile.mkdtemp(prefix="l0_stage2_trace_tests."))
    keep_artifacts = args.keep_artifacts
    failed_results: list[TraceResult] = []
    passed = 0

    try:
        print("Running stage2_l0 trace checks...", flush=True)
        print(f"artifacts={artifact_dir}", flush=True)
        print(f"Parallel jobs: {jobs}", flush=True)
        if TRACE_EXCLUDED_L0_TESTS:
            skipped = " ".join(sorted(TRACE_EXCLUDED_L0_TESTS))
            print(f"Skipping trace-incompatible tests: {skipped}", flush=True)
        print("======================================", flush=True)

        def emit(result: TraceResult) -> None:
            nonlocal passed

            events = str(result.event_count) if result.event_count is not None else "n/a"
            summary = f" {result.summary}" if result.summary else ""
            metrics = (
                f" run_s={result.run_seconds:.3f} analyzer_s={result.analyzer_seconds:.3f}"
                f" trace_bytes={result.trace_bytes} events={events}"
            )
            print(f"{result.case_name}: {result.status}{summary}{metrics}", flush=True)

            if result.status == "TRACE_OK":
                passed += 1
                if args.verbose:
                    sys.stdout.write(first_lines(result.report_text, 80))
                    if result.report_text and not result.report_text.endswith("\n"):
                        sys.stdout.write("\n")
                    sys.stdout.flush()
                return

            failed_results.append(result)
            print(f"trace_artifact={result.trace_path} trace_bytes={result.trace_bytes}", flush=True)
            detail_text = result.failure_excerpt if result.status == "RUN_FAIL" else result.report_text
            if detail_text:
                sys.stdout.write(first_lines(detail_text, 120))
                if detail_text and not detail_text.endswith("\n"):
                    sys.stdout.write("\n")
                sys.stdout.flush()

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
                emit(future.result())

        print("======================================", flush=True)
        print(f"Passed: {passed}", flush=True)
        print(f"Failed: {len(failed_results)}", flush=True)

        if failed_results:
            failed_names = [result.case_name for result in sorted(failed_results, key=lambda result: result.case_index)]
            print(f"Failed tests: {' '.join(failed_names)}", flush=True)
            print(f"Trace artifacts kept at: {artifact_dir}", flush=True)
            keep_artifacts = True
            return 1

        print("All trace checks passed!", flush=True)
        if keep_artifacts:
            print(f"Trace artifacts kept at: {artifact_dir}", flush=True)
        return 0
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
