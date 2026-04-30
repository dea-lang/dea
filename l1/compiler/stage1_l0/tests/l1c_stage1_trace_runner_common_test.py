#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for L1 Stage 1 trace-runner helper behavior."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile

SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER_DIR = SCRIPT_DIR.parent / "scripts"
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))

import test_runner_common as common
import run_trace_tests


def fail(message: str) -> int:
    """Print one failure and return the shell-style exit code."""

    print(f"l1c_stage1_trace_runner_common_test: FAIL: {message}")
    return 1


def test_resolve_trace_job_count_matches_normal_default_policy() -> str | None:
    """Return one failure message, or `None` when trace jobs match the normal default."""

    old_trace_jobs = os.environ.get("L1_TRACE_TEST_JOBS")
    old_jobs = os.environ.get("L1_TEST_JOBS")
    old_cpu_count = os.cpu_count
    try:
        os.environ.pop("L1_TRACE_TEST_JOBS", None)
        os.environ.pop("L1_TEST_JOBS", None)
        os.cpu_count = lambda: 64
        jobs = common.resolve_trace_job_count()
        normal_jobs = common.resolve_job_count()
        if jobs != normal_jobs:
            return (
                "expected trace runner default jobs to match normal jobs, "
                f"got trace={jobs} normal={normal_jobs}"
            )
    finally:
        os.cpu_count = old_cpu_count
        if old_trace_jobs is None:
            os.environ.pop("L1_TRACE_TEST_JOBS", None)
        else:
            os.environ["L1_TRACE_TEST_JOBS"] = old_trace_jobs
        if old_jobs is None:
            os.environ.pop("L1_TEST_JOBS", None)
        else:
            os.environ["L1_TEST_JOBS"] = old_jobs
    return None


def test_resolve_trace_job_count_honors_trace_override_first() -> str | None:
    """Return one failure message, or `None` when the trace override wins."""

    old_trace_jobs = os.environ.get("L1_TRACE_TEST_JOBS")
    old_jobs = os.environ.get("L1_TEST_JOBS")
    try:
        os.environ["L1_TRACE_TEST_JOBS"] = "3"
        os.environ["L1_TEST_JOBS"] = "9"
        jobs = common.resolve_trace_job_count()
        if jobs != 3:
            return f"expected L1_TRACE_TEST_JOBS to win, got {jobs}"
    finally:
        if old_trace_jobs is None:
            os.environ.pop("L1_TRACE_TEST_JOBS", None)
        else:
            os.environ["L1_TRACE_TEST_JOBS"] = old_trace_jobs
        if old_jobs is None:
            os.environ.pop("L1_TEST_JOBS", None)
        else:
            os.environ["L1_TEST_JOBS"] = old_jobs
    return None


def test_resolve_trace_job_count_falls_back_to_normal_override() -> str | None:
    """Return one failure message, or `None` when the normal override still applies."""

    old_trace_jobs = os.environ.get("L1_TRACE_TEST_JOBS")
    old_jobs = os.environ.get("L1_TEST_JOBS")
    try:
        os.environ.pop("L1_TRACE_TEST_JOBS", None)
        os.environ["L1_TEST_JOBS"] = "5"
        jobs = common.resolve_trace_job_count()
        if jobs != 5:
            return f"expected L1_TEST_JOBS fallback to win, got {jobs}"
    finally:
        if old_trace_jobs is None:
            os.environ.pop("L1_TRACE_TEST_JOBS", None)
        else:
            os.environ["L1_TRACE_TEST_JOBS"] = old_trace_jobs
        if old_jobs is None:
            os.environ.pop("L1_TEST_JOBS", None)
        else:
            os.environ["L1_TEST_JOBS"] = old_jobs
    return None


def test_resolve_artifact_dir_prefers_cli_and_keeps_explicit_dirs() -> str | None:
    """Return one failure message, or `None` when explicit artifact dirs are preserved."""

    old_artifact_dir = os.environ.get(run_trace_tests.TRACE_ARTIFACT_DIR_ENV)
    base_dir = Path(tempfile.mkdtemp(prefix="l1_trace_runner_common_test."))
    try:
        env_dir = base_dir / "env-artifacts"
        cli_dir = base_dir / "cli-artifacts"
        os.environ[run_trace_tests.TRACE_ARTIFACT_DIR_ENV] = str(env_dir)
        args = run_trace_tests.parse_args(["--artifact-dir", str(cli_dir)])
        artifact_dir, cleanup = run_trace_tests.resolve_artifact_dir(args)
        if artifact_dir != cli_dir.resolve(strict=False):
            return f"expected CLI artifact dir to win, got {artifact_dir}"
        if cleanup:
            return "expected explicit artifact dir to disable cleanup"
        if not cli_dir.is_dir():
            return f"expected CLI artifact dir to be created: {cli_dir}"
    finally:
        if old_artifact_dir is None:
            os.environ.pop(run_trace_tests.TRACE_ARTIFACT_DIR_ENV, None)
        else:
            os.environ[run_trace_tests.TRACE_ARTIFACT_DIR_ENV] = old_artifact_dir
        shutil.rmtree(base_dir, ignore_errors=True)
    return None


def main() -> int:
    """Program entrypoint."""

    checks = [
        test_resolve_trace_job_count_matches_normal_default_policy,
        test_resolve_trace_job_count_honors_trace_override_first,
        test_resolve_trace_job_count_falls_back_to_normal_override,
        test_resolve_artifact_dir_prefers_cli_and_keeps_explicit_dirs,
    ]
    for check in checks:
        message = check()
        if message is not None:
            return fail(message)

    print("l1c_stage1_trace_runner_common_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
