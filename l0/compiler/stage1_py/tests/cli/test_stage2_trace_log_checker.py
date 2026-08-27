#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tracemalloc
from pathlib import Path
from textwrap import dedent

import pytest


def _checker_path() -> Path:
    workspace_root = Path(__file__).resolve().parents[4]
    return workspace_root / "compiler" / "stage2_l0" / "scripts" / "check_trace_log.py"


def _l1_checker_path() -> Path:
    monorepo_root = Path(__file__).resolve().parents[5]
    return monorepo_root / "l1" / "compiler" / "stage1_l0" / "scripts" / "check_trace_log.py"


def _run_checker(tmp_path, log_text: str, extra_args: list[str] | None = None):
    log_path = tmp_path / "trace.stderr.log"
    log_path.write_text(dedent(log_text), encoding="utf-8")

    args = [sys.executable, str(_checker_path()), str(log_path)]
    if extra_args:
        args.extend(extra_args)

    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
    )
    return proc


def test_trace_checker_balanced_log_returns_zero(tmp_path):
    proc = _run_checker(
        tmp_path,
        """
        [l0][mem] op=new_alloc bytes=16 ptr=0x1 action=ok
        [l0][mem] op=drop ptr=0x1 action=free
        [l0][mem] op=alloc_string len=2 ptr=0x2
        [l0][mem] op=free_string ptr=0x2 action=decrement-only
        [l0][mem] op=free_string ptr=0x2 action=free
        [l0][arc] op=release kind=heap ptr=0x2 rc_before=1 rc_after=0 action=free
        """,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "errors=0" in proc.stdout


def test_trace_checker_detects_object_leak(tmp_path):
    proc = _run_checker(
        tmp_path,
        """
        [l0][mem] op=new_alloc bytes=32 ptr=0xAA action=ok
        """,
    )

    assert proc.returncode == 1
    assert "ERROR: object leak balance for ptr=0xAA" in proc.stdout


def test_trace_checker_detects_string_leak(tmp_path):
    proc = _run_checker(
        tmp_path,
        """
        [l0][mem] op=alloc_string len=4 ptr=0xBB
        [l0][mem] op=free_string ptr=0xBB action=decrement-only
        """,
    )

    assert proc.returncode == 1
    assert "ERROR: string leak balance for ptr=0xBB" in proc.stdout


def test_trace_checker_detects_negative_balance(tmp_path):
    proc = _run_checker(
        tmp_path,
        """
        [l0][mem] op=drop ptr=0x10 action=free
        [l0][mem] op=free_string ptr=0x20 action=free
        """,
    )

    assert proc.returncode == 1
    assert "without matching new_alloc" in proc.stdout
    assert "without matching alloc_string" in proc.stdout


def test_trace_checker_detects_arc_panic_and_bad_terminal_rc(tmp_path):
    proc = _run_checker(
        tmp_path,
        """
        [l0][arc] op=retain kind=heap ptr=0x1 rc_before=0 rc_after=1 action=panic-overflow
        [l0][arc] op=release kind=heap ptr=0x1 rc_before=2 rc_after=1 action=free
        """,
    )

    assert proc.returncode == 1
    assert "ERROR: line 2: arc panic action detected" in proc.stdout
    assert "ERROR: line 3: arc heap free release must end at rc_after=0" in proc.stdout


def test_trace_checker_detects_missing_ptr_for_critical_events(tmp_path):
    proc = _run_checker(
        tmp_path,
        """
        [l0][mem] op=new_alloc bytes=64 action=ok
        [l0][mem] op=alloc_string len=3
        [l0][arc] op=release kind=heap rc_before=1 rc_after=0 action=free
        """,
    )

    assert proc.returncode == 1
    assert "ERROR: line 2: mem op=new_alloc is missing ptr" in proc.stdout
    assert "ERROR: line 3: mem op=alloc_string is missing ptr" in proc.stdout
    assert "ERROR: line 4: arc heap free release is missing ptr" in proc.stdout


def test_trace_checker_warns_when_new_alloc_is_finalized_by_free_call(tmp_path):
    proc = _run_checker(
        tmp_path,
        """
        [l0][mem] op=new_alloc bytes=16 ptr=0x99 action=ok
        [l0][mem] op=free ptr=0x99 action=call
        """,
    )

    assert proc.returncode == 0
    assert "errors=0" in proc.stdout
    assert "WARN: line 3: new_alloc ptr=0x99 released via mem op=free action=call" in proc.stdout


def test_trace_checker_honors_max_details(tmp_path):
    lines = "\n".join(
        f"[l0][mem] op=new_alloc bytes=16 ptr=0x{i:x} action=ok" for i in range(1, 8)
    )
    proc = _run_checker(tmp_path, lines, extra_args=["--max-details", "3"])

    assert proc.returncode == 1
    assert proc.stdout.count("ERROR: object leak balance") == 3
    assert "ERROR: ... 4 more" in proc.stdout


def test_trace_checker_bounds_operation_and_leak_size_sections(tmp_path):
    lines = []
    for index in range(1, 8):
        lines.append(f"[l0][mem] op=custom_{index} ptr=0x0")
        lines.append(f"[l0][mem] op=new_alloc bytes={index} ptr=0x{index:x} action=ok")
    proc = _run_checker(
        tmp_path,
        "\n".join(lines),
        extra_args=["--triage", "--max-details", "3"],
    )

    assert proc.returncode == 1
    assert "... 5 more operation kinds" in proc.stdout
    assert "... 4 more byte sizes" in proc.stdout


def test_trace_checker_triage_output(tmp_path):
    proc = _run_checker(
        tmp_path,
        """
        [l0][mem] op=new_alloc bytes=16 ptr=0xA action=ok
        [l0][mem] op=new_alloc bytes=64 ptr=0xB action=ok
        [l0][mem] op=alloc_string len=5 ptr=0xC
        """,
        extra_args=["--triage"],
    )

    assert proc.returncode == 1
    assert "triage:" in proc.stdout
    assert "leaked_object_ptrs=2" in proc.stdout
    assert "leaked_string_ptrs=1" in proc.stdout
    assert "bytes=16 count=1" in proc.stdout
    assert "bytes=64 count=1" in proc.stdout


@pytest.mark.parametrize(
    "log_text",
    [
        """
        unrelated diagnostic
        [l0][mem] payload-without-op ptr=0x1
        [l0][mem] op=new_alloc bytes=16 ptr=0x1 action=ok loc="main.l0":4
        [l0][mem] op=drop ptr=0x1 action=free loc="main.l0":5
        """,
        """
        [l0][mem] op=drop ptr=0x2 action=free
        [l0][arc] op=release kind=heap ptr=0x3 rc_before=x rc_after=y action=free
        """,
        """
        [l0][mem] op=new_alloc bytes=8 ptr=0x4 action=ok
        [l0][mem] op=drop ptr=0x4 action=free
        [l0][mem] op=new_alloc bytes=32 ptr=0x4 action=ok
        [l0][mem] op=drop ptr=0x4 action=free
        [l0][mem] op=alloc_string len=2 ptr=0x5 loc="reuse.l0":7
        [l0][mem] op=free_string ptr=0x5 action=free loc="reuse.l0":8
        """,
    ],
)
def test_l0_and_l1_trace_checkers_report_identical_results(tmp_path, log_text):
    log_path = tmp_path / "shared-trace.stderr.log"
    log_path.write_text(dedent(log_text), encoding="utf-8")
    args = [str(log_path), "--triage", "--max-details", "3"]

    l0_proc = subprocess.run(
        [sys.executable, str(_checker_path()), *args],
        capture_output=True,
        text=True,
    )
    l1_proc = subprocess.run(
        [sys.executable, str(_l1_checker_path()), *args],
        capture_output=True,
        text=True,
    )

    assert l0_proc.returncode == l1_proc.returncode
    assert l0_proc.stdout == l1_proc.stdout
    assert l0_proc.stderr == l1_proc.stderr


def test_trace_checker_releases_balanced_pointer_state_while_streaming():
    spec = importlib.util.spec_from_file_location("stage2_trace_checker", _checker_path())
    assert spec is not None and spec.loader is not None
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    def events():
        for index in range(50_000):
            ptr = f"0x{index:x}"
            yield {
                "family": "mem",
                "line_no": str(index * 2 + 1),
                "op": "new_alloc",
                "action": "ok",
                "ptr": ptr,
                "bytes": "16",
            }
            yield {
                "family": "mem",
                "line_no": str(index * 2 + 2),
                "op": "drop",
                "action": "free",
                "ptr": ptr,
            }

    tracemalloc.start()
    errors, warnings, _op_counts, triage = checker._validate_events(events())
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert errors.total == 0
    assert warnings.total == 0
    assert not triage["leaked_objects"]
    assert peak < 5 * 1024 * 1024
