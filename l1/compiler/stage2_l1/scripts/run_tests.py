#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Run L1 Stage 2 tests under `compiler/stage2_l1/tests/`."""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import sys
from time import perf_counter

from test_runner_common import (
    CI_ONLY_NORMAL_STAGE2_TESTS,
    TestCase,
    build_normal_test_command,
    discover_stage2_l1_tests,
    print_output_block,
    require_repo_stage2_test_env,
    resolve_job_count,
    run_combined_output,
    summarize_failures,
)


@dataclass(frozen=True)
class TestResult:
    """One completed L1 Stage 2 test result."""

    case: TestCase
    returncode: int
    output: str
    elapsed_seconds: float


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Run L1 Stage 2 tests.",
        epilog="Parallelism defaults to a bounded auto-detected worker count. Override with L1_TEST_JOBS=<n>.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show output for every test.")
    parser.add_argument(
        "--include-ci-only",
        action="store_true",
        help="Include CI-only cases in aggregate discovery; explicit test selectors still limit the run.",
    )
    parser.add_argument(
        "tests",
        nargs="*",
        metavar="TEST",
        help="Optional L1 Stage 2 test name(s) to run. Match `tests/` file names exactly or omit the extension.",
    )
    parser.add_argument("--compiler", type=Path, help="Explicit Stage 2 subject, including a self-built native artifact.")
    return parser.parse_args(argv)


def run_one(case: TestCase, build_dir: Path, repo_env: dict[str, str]) -> TestResult:
    """Run one L1 Stage 2 test case."""

    started_at = perf_counter()
    completed = run_combined_output(build_normal_test_command(case, build_dir), env=repo_env)
    return TestResult(
        case=case,
        returncode=completed.returncode,
        output=completed.output,
        elapsed_seconds=perf_counter() - started_at,
    )


def format_elapsed_seconds(seconds: float) -> str:
    """Return one human-readable wall-clock duration."""

    return f"{seconds:.3f}s"


def result_status_line(result: TestResult) -> str:
    """Return the one-line PASS/FAIL status for one completed test."""

    status = "PASS" if result.returncode == 0 else "FAIL"
    return f"Running {result.case.name}... {status} ({format_elapsed_seconds(result.elapsed_seconds)})"


def select_cases(
    cases: list[TestCase],
    requested: list[str],
    *,
    include_ci_only: bool = False,
) -> list[TestCase]:
    """Return the selected L1 Stage 2 cases for optional CLI test-name filters."""

    if not requested:
        selected = [
            case
            for case in cases
            if include_ci_only or case.name not in CI_ONLY_NORMAL_STAGE2_TESTS
        ]
        return [
            TestCase(index=index, name=case.name, path=case.path, kind=case.kind)
            for index, case in enumerate(selected)
        ]

    by_path_name = {case.path.name: case for case in cases}
    by_stem: dict[str, list[TestCase]] = {}
    for case in cases:
        by_stem.setdefault(case.path.stem, []).append(case)

    selected_indexes: set[int] = set()
    missing: list[str] = []
    ambiguous: list[str] = []

    for raw_name in requested:
        selector = Path(raw_name).name
        exact = by_path_name.get(selector)
        if exact is not None:
            selected_indexes.add(exact.index)
            continue

        if Path(selector).suffix:
            missing.append(selector)
            continue

        matches = by_stem.get(selector, [])
        if not matches:
            missing.append(selector)
            continue
        if len(matches) > 1:
            ambiguous.append(f"{selector}: {', '.join(case.path.name for case in matches)}")
            continue
        selected_indexes.add(matches[0].index)

    if missing or ambiguous:
        parts: list[str] = []
        if missing:
            parts.append(f"unknown L1 Stage 2 test name(s): {' '.join(missing)}")
        if ambiguous:
            parts.append(f"ambiguous L1 Stage 2 test name(s): {'; '.join(ambiguous)}")
        raise ValueError("; ".join(parts))

    selected = [case for case in cases if case.index in selected_indexes]
    return [TestCase(index=index, name=case.name, path=case.path, kind=case.kind) for index, case in enumerate(selected)]


def main() -> int:
    """Program entrypoint."""

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    args = parse_args()
    if args.compiler:
        os.environ["L1_TEST_COMPILER"] = str(args.compiler.resolve())

    try:
        jobs = resolve_job_count()
    except ValueError as exc:
        print(f"run_tests.py: {exc}", file=sys.stderr, flush=True)
        return 2
    try:
        _, _, build_dir, repo_env = require_repo_stage2_test_env("run_tests.py")
    except RuntimeError as exc:
        print(f"run_tests.py: {exc}", file=sys.stderr, flush=True)
        return 2

    try:
        discovered_cases = discover_stage2_l1_tests()
        cases = select_cases(discovered_cases, args.tests, include_ci_only=args.include_ci_only)
    except ValueError as exc:
        print(f"run_tests.py: {exc}", file=sys.stderr, flush=True)
        return 2
    classified_cases = [case.name for case in discovered_cases if case.name in CI_ONLY_NORMAL_STAGE2_TESTS]
    selected_classified_cases = [case.name for case in cases if case.name in CI_ONLY_NORMAL_STAGE2_TESTS]
    if args.tests:
        selected_text = ", ".join(selected_classified_cases) if selected_classified_cases else "none"
        print(
            "CI-only classification bypassed by explicit test selection; "
            f"selected CI-only cases: {selected_text}.",
            flush=True,
        )
    elif args.include_ci_only:
        print(f"CI-only cases included: {', '.join(classified_cases) or 'none discovered'}.", flush=True)
    else:
        print(f"CI-only cases excluded: {', '.join(classified_cases) or 'none discovered'}.", flush=True)
    if not cases:
        print("No tests found in compiler/stage2_l1/tests", flush=True)
        return 0

    print("Running stage2_l1 tests...", flush=True)
    print(f"Parallel jobs: {jobs}", flush=True)
    print("======================================", flush=True)

    passed = 0
    failures: list[TestResult] = []

    def emit(result: TestResult) -> None:
        nonlocal passed

        if args.verbose:
            print(f"Running {result.case.name}...", flush=True)
            print_output_block(result.output)
            sys.stdout.flush()
            print(
                f"{'PASS' if result.returncode == 0 else 'FAIL'} ({format_elapsed_seconds(result.elapsed_seconds)})",
                flush=True,
            )
        else:
            print(result_status_line(result), flush=True)

        if result.returncode == 0:
            passed += 1
        else:
            failures.append(result)

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        future_map = {
            executor.submit(run_one, case, build_dir, repo_env): case.index
            for case in cases
        }
        for future in as_completed(future_map):
            emit(future.result())

    if not args.verbose and failures:
        print("======================================", flush=True)
        print("Failed test outputs:", flush=True)
        for result in failures:
            print(f"Output for {result.case.name} ({format_elapsed_seconds(result.elapsed_seconds)}):", flush=True)
            print_output_block(result.output)
            sys.stdout.flush()
            print("--------------------------------------", flush=True)

    print("======================================", flush=True)
    print(f"Passed: {passed}", flush=True)
    print(f"Failed: {len(failures)}", flush=True)

    if failures:
        print(f"Failed tests: {summarize_failures(result.case for result in failures)}", flush=True)
        return 1

    print("All tests passed!", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
