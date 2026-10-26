# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Short progress and logging checks without running documentation tools."""

import io
import os
from pathlib import Path
import sys
import threading

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import docgen_progress as progress


def test_phase_reports_heartbeat_and_stops_on_success(monkeypatch):
    messages = []
    observed = threading.Event()

    def report(message):
        messages.append(message)
        if message.startswith("RUNNING"):
            observed.set()

    monkeypatch.setattr(progress, "_report", report)
    with progress.phase("tiny phase", heartbeat_seconds=0.001):
        assert messages[0] == "START tiny phase"
        assert observed.wait(2)
    assert messages[-1].startswith("DONE tiny phase (")
    assert "s elapsed)" in next(message for message in messages if message.startswith("RUNNING"))
    assert not any(thread.name == "docgen-progress" for thread in threading.enumerate())


@pytest.mark.parametrize("error", [ValueError("failed"), SystemExit(1)])
def test_phase_reports_failure_without_swallowing_it(capsys, error):
    with pytest.raises(type(error)):
        with progress.phase("failed phase"):
            raise error
    output = capsys.readouterr().out
    assert "[docgen] START failed phase" in output
    assert "[docgen] FAILED failed phase (" in output
    assert "[docgen] DONE" not in output
    assert not any(thread.name == "docgen-progress" for thread in threading.enumerate())


def test_invalid_heartbeat_is_rejected():
    with pytest.raises(ValueError, match="positive"):
        with progress.phase("invalid", heartbeat_seconds=0):
            pytest.fail("invalid phase entered")


@pytest.mark.parametrize("verbose", [False, True])
def test_log_and_child_progress_are_live_before_process_exit(tmp_path, monkeypatch, verbose):
    log = tmp_path / "output with spaces.log"
    release = tmp_path / "release"
    code = '''
import os, pathlib, sys, time
print("ordinary output")
print("[docgen] child ready")
deadline = time.monotonic() + 3
while not pathlib.Path(sys.argv[1]).exists():
    if time.monotonic() > deadline:
        sys.exit(2)
    time.sleep(0.005)
print(os.environ["DOCGEN_PROBE"], os.environ["PYTHONUNBUFFERED"])
os.write(1, b"last line with invalid UTF-8: \\xff\\n")
'''

    class LiveOutput(io.StringIO):
        def write(self, text):
            if text == "[docgen] child ready\n":
                # A buffered implementation cannot release this still-running child.
                assert log.read_text(encoding="utf-8") == "ordinary output\n[docgen] child ready\n"
                release.touch()
            return super().write(text)

    output = LiveOutput()
    monkeypatch.setattr(sys, "stdout", output)
    progress.run_logged([sys.executable, "-c", code, str(release)], log, verbose=verbose, cwd=tmp_path,
                        env={**os.environ, "DOCGEN_PROBE": "environment preserved", "PYTHONUNBUFFERED": "0"}, phase_name="Probe")
    assert release.is_file()
    assert "environment preserved 1\n" in log.read_text(encoding="utf-8")
    assert "invalid UTF-8: \ufffd\n" in log.read_text(encoding="utf-8")
    assert "[docgen] child ready" in output.getvalue()
    assert ("ordinary output" in output.getvalue()) == verbose
    assert "[docgen] DONE Probe (" in output.getvalue()


def test_failure_preserves_complete_log_and_exit_status(tmp_path, capsys):
    log = tmp_path / "failure.log"
    command = [sys.executable, "-c", "import sys; print('first'); print('last', file=sys.stderr); sys.exit(7)"]
    with pytest.raises(SystemExit) as error:
        progress.run_logged(command, log, verbose=False, cwd=tmp_path, phase_name="Failure")
    assert error.value.code == 1
    assert log.read_text(encoding="utf-8") == "first\nlast\n"
    output = capsys.readouterr()
    assert "command failed (7)" in output.err
    assert "first\nlast\n" in output.err
    assert "[docgen] FAILED Failure (" in output.out


def test_launch_error_is_timed_without_masking_the_error(tmp_path, monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise OSError("cannot launch")

    monkeypatch.setattr(progress.subprocess, "Popen", fail)
    with pytest.raises(OSError, match="cannot launch"):
        progress.run_logged(["missing"], tmp_path / "failure.log", verbose=False, cwd=tmp_path)
    assert "[docgen] FAILED Documentation command (" in capsys.readouterr().out


def test_pdf_passes_and_indexing_are_visible_in_quiet_mode(tmp_path, capsys):
    lines = ["This is pdfTeX, first pass", "hidden TeX output", "This is makeindex, version 2.17",
             "This is pdfTeX, second pass"]
    code = "\n".join(f"print({line!r})" for line in lines)
    log = tmp_path / "latex.log"
    progress.run_logged([sys.executable, "-c", code], log, verbose=False, cwd=tmp_path, phase_name="Full PDF")
    output = capsys.readouterr().out
    assert "Full PDF: pdfLaTeX pass 1 started (" in output
    assert "Full PDF: pdfLaTeX pass 2 started (" in output
    assert "Full PDF: makeindex started (" in output
    assert "hidden TeX output" not in output
    assert log.read_text(encoding="utf-8").splitlines() == lines
