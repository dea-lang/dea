#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for Stage 2 trace-runner helper behavior."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap

SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER_DIR = SCRIPT_DIR.parent / "scripts"
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))

import test_runner_common as common


def fail(message: str) -> int:
    """Print one failure and return the shell-style exit code."""

    print(f"l0c_stage2_trace_runner_common_test: FAIL: {message}")
    return 1


def test_resolve_trace_job_count_matches_normal_jobs_on_windows_env() -> str | None:
    """Return one failure message, or `None` when trace jobs follow the normal job policy."""

    old_os = os.environ.get("OS")
    old_msystem = os.environ.get("MSYSTEM")
    old_jobs = os.environ.get("L0_TEST_JOBS")
    try:
        os.environ["OS"] = "Windows_NT"
        os.environ.pop("MSYSTEM", None)
        os.environ.pop("L0_TEST_JOBS", None)
        jobs = common.resolve_trace_job_count()
        normal_jobs = common.resolve_job_count()
        if jobs != normal_jobs:
            return f"expected Windows-like trace runner jobs to match normal jobs, got trace={jobs} normal={normal_jobs}"
    finally:
        if old_os is None:
            os.environ.pop("OS", None)
        else:
            os.environ["OS"] = old_os
        if old_msystem is None:
            os.environ.pop("MSYSTEM", None)
        else:
            os.environ["MSYSTEM"] = old_msystem
        if old_jobs is None:
            os.environ.pop("L0_TEST_JOBS", None)
        else:
            os.environ["L0_TEST_JOBS"] = old_jobs
    return None


def test_resolve_trace_job_count_honors_override() -> str | None:
    """Return one failure message, or `None` when explicit job overrides win."""

    old_os = os.environ.get("OS")
    old_jobs = os.environ.get("L0_TEST_JOBS")
    try:
        os.environ["OS"] = "Windows_NT"
        os.environ["L0_TEST_JOBS"] = "3"
        jobs = common.resolve_trace_job_count()
        if jobs != 3:
            return f"expected explicit trace job override to win, got {jobs}"
    finally:
        if old_os is None:
            os.environ.pop("OS", None)
        else:
            os.environ["OS"] = old_os
        if old_jobs is None:
            os.environ.pop("L0_TEST_JOBS", None)
        else:
            os.environ["L0_TEST_JOBS"] = old_jobs
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


def test_run_captured_binary_output_writes_complete_files() -> str | None:
    """Return one failure message, or `None` when captured output is written after completion."""

    with tempfile.TemporaryDirectory(prefix="l0_trace_runner_common.") as tmp_dir:
        stdout_path = Path(tmp_dir) / "stdout.log"
        stderr_path = Path(tmp_dir) / "stderr.log"
        completed = common.run_captured_binary_output(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'out\\n'); sys.stderr.buffer.write(b'err\\n')"],
            cwd=Path.cwd(),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        if completed.returncode != 0:
            return f"expected binary capture helper to succeed, got rc={completed.returncode}"
        if stdout_path.read_bytes() != b"out\n":
            return f"unexpected stdout artifact bytes: {stdout_path.read_bytes()!r}"
        if stderr_path.read_bytes() != b"err\n":
            return f"unexpected stderr artifact bytes: {stderr_path.read_bytes()!r}"
    return None


def test_run_captured_binary_output_waits_for_inherited_grandchild_writers() -> str | None:
    """Return one failure message, or `None` when late inherited writes are captured fully."""

    with tempfile.TemporaryDirectory(prefix="l0_trace_runner_common.") as tmp_dir:
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

    with tempfile.TemporaryDirectory(prefix="l0_trace_runner_common.") as tmp_dir:
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

    with tempfile.TemporaryDirectory(prefix="l0_trace_runner_common.") as tmp_dir:
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
        test_resolve_trace_job_count_matches_normal_jobs_on_windows_env,
        test_resolve_trace_job_count_honors_override,
        test_run_captured_binary_output_writes_complete_files,
        test_run_captured_binary_output_waits_for_inherited_grandchild_writers,
        test_run_captured_binary_output_supports_parallel_calls,
        test_run_captured_binary_output_streams_large_artifacts_without_result_copies,
    ]
    for check in checks:
        message = check()
        if message is not None:
            return fail(message)

    print("l0c_stage2_trace_runner_common_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
