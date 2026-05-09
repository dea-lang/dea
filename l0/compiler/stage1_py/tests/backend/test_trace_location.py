#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import pytest
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MEM_LINE_RE = re.compile(r"^\[l0\]\[mem\] (.+)$")
_KV_RE = re.compile(r"(\w+)=(\S+)")

def parse_mem_lines(stderr: str) -> list[dict[str, str]]:
    """Extract ``[l0][mem]`` lines and split key=value tokens into dicts."""
    results: list[dict[str, str]] = []
    for line in stderr.splitlines():
        m = _MEM_LINE_RE.match(line)
        if m:
            fields = dict(_KV_RE.findall(m.group(1)))
            results.append(fields)
    return results

def _compile_with_trace(analyze_single, compile_and_run, tmp_path, src, memory=True, arc=True):
    """Shared pipeline: analyze → set trace → codegen → compile → run → parse."""
    result = analyze_single("main", src)
    assert not result.has_errors(), result.diagnostics
    result.context.trace_memory = memory
    result.context.trace_arc = arc

    from l0_backend import Backend

    backend = Backend(result)
    c_code = backend.generate()
    ok, stdout, stderr = compile_and_run(c_code, tmp_path)
    mem_lines = parse_mem_lines(stderr)
    return ok, stdout, stderr, mem_lines

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_trace_memory_loc_reporting(analyze_single, compile_and_run, tmp_path):
    """Verify that memory trace lines include the correct loc= field."""
    ok, _stdout, _stderr, mem = _compile_with_trace(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        func main() -> int {
            let p: void*? = rt_alloc(8);
            rt_free(p);
            return 0;
        }
        """,
    )
    assert ok, _stderr

    allocs = [e for e in mem if e["op"] == "alloc" and e["action"] == "ok"]
    assert len(allocs) == 1
    # Check that loc contains main.l0
    assert "loc" in allocs[0]
    assert "main.l0" in allocs[0]["loc"]

    frees = [e for e in mem if e["op"] == "free" and e["action"] == "call"]
    assert len(frees) == 1
    assert "loc" in frees[0]
    assert "main.l0" in frees[0]["loc"]

def test_trace_arc_loc_reporting(analyze_single, compile_and_run, tmp_path):
    """Verify that ARC trace lines include the correct loc= field."""
    ok, _stdout, stderr, _mem = _compile_with_trace(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.rt;

        func main() -> int {
            let s: string = "test";
            rt_string_retain(s);
            rt_string_release(s);
            return 0;
        }
        """,
    )
    assert ok, stderr

    # Extract [l0][arc] lines
    arc_lines = []
    for line in stderr.splitlines():
        if line.startswith("[l0][arc] "):
            fields = dict(_KV_RE.findall(line[10:]))
            arc_lines.append(fields)

    retains = [e for e in arc_lines if e["op"] == "retain"]
    assert len(retains) >= 1
    assert "loc" in retains[0]
    assert "main.l0" in retains[0]["loc"]

    releases = [e for e in arc_lines if e["op"] == "release"]
    assert len(releases) >= 1
    assert "loc" in releases[0]
    assert "main.l0" in releases[0]["loc"]

def test_trace_memory_realloc_loc_reporting(analyze_single, compile_and_run, tmp_path):
    """Verify that realloc trace lines include the correct loc= field."""
    ok, _stdout, _stderr, mem = _compile_with_trace(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        func main() -> int {
            let p: void* = rt_alloc(8) as void*;
            let p2: void*? = rt_realloc(p, 16);
            rt_free(p2);
            return 0;
        }
        """,
    )
    assert ok, _stderr

    reallocs = [e for e in mem if e["op"] == "realloc" and e["action"] == "ok"]
    assert len(reallocs) == 1
    assert "loc" in reallocs[0]
    assert "main.l0" in reallocs[0]["loc"]

def test_trace_memory_calloc_loc_reporting(analyze_single, compile_and_run, tmp_path):
    """Verify that calloc trace lines include the correct loc= field."""
    ok, _stdout, _stderr, mem = _compile_with_trace(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        func main() -> int {
            let p: void*? = rt_calloc(2, 4);
            rt_free(p);
            return 0;
        }
        """,
    )
    assert ok, _stderr

    callocs = [e for e in mem if e["op"] == "calloc" and e["action"] == "ok"]
    assert len(callocs) == 1
    assert "loc" in callocs[0]
    assert "main.l0" in callocs[0]["loc"]

def test_trace_log_analyzer_surfaces_loc(analyze_single, compile_and_run, tmp_path):
    """Verify that check_trace_log.py surfaces the loc in its report."""
    ok, _stdout, stderr, _mem = _compile_with_trace(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        struct Box {
            x: int;
        }

        func main() -> int {
            let b: Box* = new Box(42);
            // Intentionally leak b
            return 0;
        }
        """,
    )
    assert ok, stderr

    # Save stderr to a file for the analyzer
    trace_file = tmp_path / "trace.stderr"
    trace_file.write_text(stderr)

    # Find check_trace_log.py relative to this test
    repo_root = Path(__file__).parent.parent.parent.parent.parent
    analyzer = repo_root / "compiler" / "stage2_l0" / "scripts" / "check_trace_log.py"
    
    cmd = [sys.executable, str(analyzer), str(trace_file), "--triage"]
    cp = subprocess.run(cmd, capture_output=True, text=True)
    
    # It should exit with 1 because of the leak
    assert cp.returncode == 1
    
    # The output should contain the triage report with the location
    assert "leaked_object_ptrs=1" in cp.stdout
    assert "loc=" in cp.stdout
    assert "main.l0" in cp.stdout
