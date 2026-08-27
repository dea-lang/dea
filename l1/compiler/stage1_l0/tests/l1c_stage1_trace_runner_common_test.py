#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for L1 Stage 1 trace-runner helper behavior."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap

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


def _grandchild_writer_command(tag: str) -> list[str]:
    """Return one Python command that leaves a delayed grandchild writing to inherited stdio."""

    child_code = textwrap.dedent(
        f"""\
        import subprocess
        import sys
        grandchild = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys,time; time.sleep(0.1); "
                "sys.stdout.write({tag!r} + ' late stdout\\\\n'); sys.stdout.flush(); "
                "sys.stderr.write({tag!r} + ' late stderr\\\\n'); sys.stderr.flush()",
            ],
            stdout=None,
            stderr=None,
            close_fds=False,
        )
        sys.stdout.write({tag!r} + " early stdout\\n")
        sys.stdout.flush()
        sys.stderr.write({tag!r} + " early stderr\\n")
        sys.stderr.flush()
        """
    )
    return [sys.executable, "-c", child_code]


def test_run_captured_binary_output_waits_for_inherited_grandchild_writers() -> str | None:
    """Return one failure message, or `None` when late inherited writes are captured fully."""

    with tempfile.TemporaryDirectory(prefix="l1_trace_runner_common.") as tmp_dir:
        stdout_path = Path(tmp_dir) / "stdout.log"
        stderr_path = Path(tmp_dir) / "stderr.log"
        completed = common.run_captured_binary_output(
            _grandchild_writer_command("solo"),
            cwd=Path.cwd(),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        if completed.returncode != 0:
            return f"expected delayed grandchild writer command to succeed, got rc={completed.returncode}"
        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
        for expected in ("solo early stdout", "solo late stdout"):
            if expected not in stdout_text:
                return f"missing stdout line {expected!r} in {stdout_text!r}"
        for expected in ("solo early stderr", "solo late stderr"):
            if expected not in stderr_text:
                return f"missing stderr line {expected!r} in {stderr_text!r}"
    return None


def test_run_captured_binary_output_supports_parallel_calls() -> str | None:
    """Return one failure message, or `None` when multiple delayed captures complete in parallel."""

    with tempfile.TemporaryDirectory(prefix="l1_trace_runner_common.") as tmp_dir:
        root = Path(tmp_dir)

        def run_one(index: int) -> tuple[int, str, str, int]:
            tag = f"case-{index}"
            stdout_path = root / f"{tag}.stdout.log"
            stderr_path = root / f"{tag}.stderr.log"
            completed = common.run_captured_binary_output(
                _grandchild_writer_command(tag),
                cwd=Path.cwd(),
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            return (
                completed.returncode,
                stdout_path.read_text(encoding="utf-8", errors="replace"),
                stderr_path.read_text(encoding="utf-8", errors="replace"),
                index,
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = [future.result() for future in [executor.submit(run_one, index) for index in range(4)]]

        for returncode, stdout_text, stderr_text, index in results:
            if returncode != 0:
                return f"parallel capture case {index} failed with rc={returncode}"
            tag = f"case-{index}"
            for expected in (f"{tag} early stdout", f"{tag} late stdout"):
                if expected not in stdout_text:
                    return f"parallel capture case {index} missing stdout line {expected!r}"
            for expected in (f"{tag} early stderr", f"{tag} late stderr"):
                if expected not in stderr_text:
                    return f"parallel capture case {index} missing stderr line {expected!r}"
    return None


def test_run_captured_binary_output_streams_large_artifacts_without_result_copies() -> str | None:
    """Return one failure message, or `None` when large output stays file-backed."""

    with tempfile.TemporaryDirectory(prefix="l1_trace_runner_common.") as tmp_dir:
        stdout_path = Path(tmp_dir) / "stdout.log"
        stderr_path = Path(tmp_dir) / "stderr.log"
        stdout_size = common.CAPTURE_CHUNK_SIZE * 8 + 3
        stderr_size = common.CAPTURE_CHUNK_SIZE * 5 + 1
        completed = common.run_captured_binary_output(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    f"sys.stdout.buffer.write(b'x' * {stdout_size}); "
                    f"sys.stderr.buffer.write(b'y' * {stderr_size})"
                ),
            ],
            cwd=Path.cwd(),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        if completed.returncode != 0:
            return f"expected large capture to succeed, got rc={completed.returncode}"
        if hasattr(completed, "stdout") or hasattr(completed, "stderr"):
            return "capture result unexpectedly retained stdout/stderr payloads"
        if completed.stdout_bytes != stdout_size or stdout_path.stat().st_size != stdout_size:
            return f"unexpected streamed stdout size: result={completed.stdout_bytes} file={stdout_path.stat().st_size}"
        if completed.stderr_bytes != stderr_size or stderr_path.stat().st_size != stderr_size:
            return f"unexpected streamed stderr size: result={completed.stderr_bytes} file={stderr_path.stat().st_size}"
    return None


def main() -> int:
    """Program entrypoint."""

    checks = [
        test_resolve_trace_job_count_matches_normal_default_policy,
        test_resolve_trace_job_count_honors_trace_override_first,
        test_resolve_trace_job_count_falls_back_to_normal_override,
        test_resolve_artifact_dir_prefers_cli_and_keeps_explicit_dirs,
        test_run_captured_binary_output_waits_for_inherited_grandchild_writers,
        test_run_captured_binary_output_supports_parallel_calls,
        test_run_captured_binary_output_streams_large_artifacts_without_result_copies,
    ]
    for check in checks:
        message = check()
        if message is not None:
            return fail(message)

    print("l1c_stage1_trace_runner_common_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
