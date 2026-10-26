# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Live documentation phase timings and continuously flushed subprocess logs."""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

PREFIX = "[docgen] "
_OUTPUT_LOCK = threading.Lock()


def _report(message: str) -> None:
    """Print one complete progress message immediately.

    Args:
        message: Progress text without the shared prefix.
    """
    with _OUTPUT_LOCK:
        print(f"{PREFIX}{message}", flush=True)


@contextmanager
def phase(label: str, *, heartbeat_seconds: float = 30.0) -> Iterator[None]:
    """Report phase start, periodic elapsed time, and success or failure.

    Args:
        label: Human-readable phase name.
        heartbeat_seconds: Interval between elapsed-time reports.

    Yields:
        Control to the timed phase.

    Raises:
        ValueError: The heartbeat interval is not positive.
    """
    if heartbeat_seconds <= 0:
        raise ValueError("heartbeat interval must be positive")
    started = time.monotonic()
    stopped = threading.Event()

    def heartbeat() -> None:
        """Report elapsed time until the phase exits."""
        while not stopped.wait(heartbeat_seconds):
            _report(f"RUNNING {label} ({time.monotonic() - started:.1f}s elapsed)")

    _report(f"START {label}")
    ticker = threading.Thread(target=heartbeat, name="docgen-progress", daemon=True)
    ticker.start()
    failed = True
    try:
        yield
        failed = False
    finally:
        stopped.set()
        ticker.join()
        _report(f"{'FAILED' if failed else 'DONE'} {label} ({time.monotonic() - started:.1f}s)")


def run_logged(
        command: list[str],
        log_file: Path,
        *,
        verbose: bool,
        cwd: Path,
        env: dict[str, str] | None = None,
        phase_name: str = "Documentation command",
) -> None:
    """Stream a command into its log while showing live phase progress.

    Args:
        command: Subprocess argument vector.
        log_file: Complete output log, flushed as each line arrives.
        verbose: Whether to show all subprocess output immediately.
        cwd: Subprocess working directory.
        env: Optional replacement environment, with Python buffering disabled.
        phase_name: Label for timings and PDF pass markers.

    Raises:
        OSError: The log or subprocess cannot be opened.
        SystemExit: The subprocess fails; its complete log is printed to stderr.
    """
    child_env = dict(os.environ if env is None else env)
    child_env["PYTHONUNBUFFERED"] = "1"
    started = time.monotonic()
    pdf_pass = 0
    with phase(phase_name), log_file.open("w", encoding="utf-8") as log:
        with subprocess.Popen(command, cwd=cwd, env=child_env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                              errors="replace", bufsize=1) as process:
            for line in process.stdout:
                log.write(line)
                log.flush()
                if verbose or line.startswith(PREFIX):
                    with _OUTPUT_LOCK:
                        print(line, end="", flush=True)
                if line.startswith("This is pdfTeX,"):
                    pdf_pass += 1
                    _report(f"{phase_name}: pdfLaTeX pass {pdf_pass} started "
                            f"({time.monotonic() - started:.1f}s elapsed)")
                elif line.startswith("This is makeindex,"):
                    _report(f"{phase_name}: makeindex started ({time.monotonic() - started:.1f}s elapsed)")
            result = process.wait()
        if result:
            print(f"Error: command failed ({result}): {' '.join(command)}", file=sys.stderr)
            print(f"Log saved to: {log_file}", file=sys.stderr)
            with log_file.open(encoding="utf-8") as saved:
                shutil.copyfileobj(saved, sys.stderr)
            raise SystemExit(1)
