#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

"""
Memory trace runtime verification tests.

Each test compiles an L0 program with trace_memory=True, runs it, parses the
structured ``[l0][mem]`` lines from stderr, and asserts on heap allocation
correctness: pointer pairing, alloc/free balancing, and leak-freedom invariants.

Trace line format (from l0_runtime.h):
    [l0][mem] op=<new_alloc|drop|calloc|alloc_string|free_string|alloc|free|...>
              ptr=<hex> bytes=<int> action=<ok|free|call|...>
"""

import re

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MEM_LINE_RE = re.compile(r"^\[l0\]\[mem\] (.+)$")
_ARC_LINE_RE = re.compile(r"^\[l0\]\[arc\] (.+)$")
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


def parse_arc_lines(stderr: str) -> list[dict[str, str]]:
    """Extract ``[l0][arc]`` lines and split key=value tokens into dicts."""
    results: list[dict[str, str]] = []
    for line in stderr.splitlines():
        m = _ARC_LINE_RE.match(line)
        if m:
            fields = dict(_KV_RE.findall(m.group(1)))
            results.append(fields)
    return results


def _compile_with_trace_memory(analyze_single, compile_and_run, tmp_path, src):
    """Shared pipeline: analyze → set trace_memory → codegen → compile → run → parse."""
    result = analyze_single("main", src)
    assert not result.has_errors(), result.diagnostics
    result.context.trace_memory = True

    from l0_backend import Backend

    c_code = Backend(result).generate()
    ok, stdout, stderr = compile_and_run(c_code, tmp_path)
    mem_lines = parse_mem_lines(stderr)
    return ok, stdout, stderr, mem_lines


def _compile_with_memory_and_arc_trace(analyze_single, compile_and_run, tmp_path, src):
    """Compile and run with memory and ARC tracing enabled."""
    result = analyze_single("main", src)
    assert not result.has_errors(), result.diagnostics
    result.context.trace_memory = True
    result.context.trace_arc = True

    from l0_backend import Backend

    c_code = Backend(result).generate()
    ok, stdout, stderr = compile_and_run(c_code, tmp_path)
    return ok, stdout, stderr, parse_mem_lines(stderr), parse_arc_lines(stderr)


# ---------------------------------------------------------------------------
# A – Struct new/drop basic pairing
# ---------------------------------------------------------------------------


def test_trace_memory_struct_new_drop_basic(
    analyze_single, compile_and_run, tmp_path
):
    """new S(1,2) / drop must produce new_alloc paired with drop, same ptr."""
    ok, _stdout, _stderr, mem = _compile_with_trace_memory(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        struct S {
            x: int;
            y: int;
        }

        func main() -> int {
            let p: S* = new S(1, 2);
            drop p;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    allocs = [e for e in mem if e["op"] == "new_alloc" and e["action"] == "ok"]
    drops = [e for e in mem if e["op"] == "drop" and e["action"] == "free"]
    assert len(allocs) >= 1, f"expected at least one new_alloc: {mem}"
    assert len(drops) >= 1, f"expected at least one drop: {mem}"
    assert allocs[0]["ptr"] == drops[0]["ptr"], (
        f"new_alloc ptr {allocs[0]['ptr']} != drop ptr {drops[0]['ptr']}"
    )


def test_trace_memory_double_drop_validation_precedes_arc_cleanup(
    analyze_single, compile_and_run, tmp_path
):
    """A stale drop through an alias must panic before a second field cleanup."""
    ok, _stdout, stderr, mem, arc = _compile_with_memory_and_arc_trace(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        struct Box {
            s: string;
        }

        func zap(p: Box*) {
            drop p;
        }

        func main() -> int {
            let p: Box* = new Box(concat_s("he", "llo"));
            zap(p);
            zap(p);
            return 0;
        }
        """,
    )
    assert not ok
    assert "Software Failure:" in stderr
    assert "double drop" in stderr

    drops = [
        event
        for event in mem
        if event.get("op") == "drop" and event.get("action") == "free"
    ]
    assert len(drops) == 1, f"expected only the first drop to complete: {mem}"

    heap_release_frees = [
        event
        for event in arc
        if event.get("kind") == "heap"
        and event.get("op") == "release"
        and event.get("action") == "free"
    ]
    assert len(heap_release_frees) == 1, f"expected only the first drop to release field ARC data: {arc}"


# ---------------------------------------------------------------------------
# B – Struct default constructor (zero-init)
# ---------------------------------------------------------------------------


def test_trace_memory_struct_default_constructor(
    analyze_single, compile_and_run, tmp_path
):
    """new S() with no args must still produce new_alloc/drop pairing."""
    ok, _stdout, _stderr, mem = _compile_with_trace_memory(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        struct S {
            x: int;
            y: int;
        }

        func main() -> int {
            let p: S* = new S();
            drop p;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    allocs = [e for e in mem if e["op"] == "new_alloc" and e["action"] == "ok"]
    drops = [e for e in mem if e["op"] == "drop" and e["action"] == "free"]
    assert len(allocs) == 1, f"expected exactly one new_alloc: {allocs}"
    assert len(drops) == 1, f"expected exactly one drop: {drops}"
    assert allocs[0]["ptr"] == drops[0]["ptr"]


# ---------------------------------------------------------------------------
# C – Enum variant new/drop
# ---------------------------------------------------------------------------


def test_trace_memory_enum_new_drop(
    analyze_single, compile_and_run, tmp_path
):
    """new Variant(42) / drop must pair alloc and free for enum objects."""
    ok, _stdout, _stderr, mem = _compile_with_trace_memory(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        enum Result {
            Ok(value: int);
            Err(code: int);
        }

        func main() -> int {
            let r: Result* = new Ok(42);
            drop r;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    allocs = [e for e in mem if e["op"] == "new_alloc" and e["action"] == "ok"]
    drops = [e for e in mem if e["op"] == "drop" and e["action"] == "free"]
    assert len(allocs) >= 1, f"expected new_alloc for enum: {mem}"
    assert len(drops) >= 1, f"expected drop for enum: {mem}"
    assert allocs[0]["ptr"] == drops[0]["ptr"]


# ---------------------------------------------------------------------------
# D – Primitive new/drop
# ---------------------------------------------------------------------------


def test_trace_memory_primitive_new_drop(
    analyze_single, compile_and_run, tmp_path
):
    """new int(42) / drop must pair alloc and free for primitive heap objects."""
    ok, _stdout, _stderr, mem = _compile_with_trace_memory(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        func main() -> int {
            let p: int* = new int(42);
            drop p;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    allocs = [e for e in mem if e["op"] == "new_alloc" and e["action"] == "ok"]
    drops = [e for e in mem if e["op"] == "drop" and e["action"] == "free"]
    assert len(allocs) == 1, f"expected one new_alloc: {allocs}"
    assert len(drops) == 1, f"expected one drop: {drops}"
    assert allocs[0]["ptr"] == drops[0]["ptr"]


# ---------------------------------------------------------------------------
# E – String new/drop (heap-allocated string value)
# ---------------------------------------------------------------------------


def test_trace_memory_string_new_drop(
    analyze_single, compile_and_run, tmp_path
):
    """new string("test") / drop must produce at least new_alloc/drop pair."""
    ok, _stdout, _stderr, mem = _compile_with_trace_memory(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        func main() -> int {
            let p: string* = new string("test");
            drop p;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    allocs = [e for e in mem if e["op"] == "new_alloc" and e["action"] == "ok"]
    drops = [e for e in mem if e["op"] == "drop" and e["action"] == "free"]
    assert len(allocs) >= 1, f"expected new_alloc for string: {mem}"
    assert len(drops) >= 1, f"expected drop for string: {mem}"
    assert allocs[0]["ptr"] == drops[0]["ptr"]


# ---------------------------------------------------------------------------
# F – calloc accompanies every new_alloc
# ---------------------------------------------------------------------------


def test_trace_memory_calloc_accompanies_new_alloc(
    analyze_single, compile_and_run, tmp_path
):
    """Every new_alloc must be preceded by a calloc with count=1 and same ptr."""
    ok, _stdout, _stderr, mem = _compile_with_trace_memory(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        struct S {
            x: int;
            y: int;
        }

        func main() -> int {
            let p: S* = new S(10, 20);
            drop p;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    allocs = [e for e in mem if e["op"] == "new_alloc" and e["action"] == "ok"]
    assert len(allocs) >= 1, f"expected at least one new_alloc: {mem}"

    for alloc_ev in allocs:
        ptr = alloc_ev["ptr"]
        # Find the calloc that produced this ptr (must appear before the new_alloc)
        alloc_idx = mem.index(alloc_ev)
        preceding_callocs = [
            e for e in mem[:alloc_idx]
            if e["op"] == "calloc" and e["ptr"] == ptr and e["action"] == "ok"
        ]
        assert len(preceding_callocs) >= 1, (
            f"new_alloc ptr={ptr} has no preceding calloc with same ptr"
        )
        assert preceding_callocs[-1]["count"] == "1", (
            f"calloc for new_alloc should have count=1: {preceding_callocs[-1]}"
        )


# ---------------------------------------------------------------------------
# G – Struct with heap string field: both object and string events
# ---------------------------------------------------------------------------


def test_trace_memory_struct_with_heap_string_field(
    analyze_single, compile_and_run, tmp_path
):
    """new Box(concat_s(...)) / drop must produce both new_alloc/drop AND alloc_string/free_string."""
    ok, _stdout, _stderr, mem = _compile_with_trace_memory(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        struct Box {
            s: string;
        }

        func main() -> int {
            let b: Box* = new Box(concat_s("he", "ap"));
            drop b;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    allocs = [e for e in mem if e["op"] == "new_alloc" and e["action"] == "ok"]
    drops = [e for e in mem if e["op"] == "drop" and e["action"] == "free"]
    assert len(allocs) >= 1, f"expected new_alloc for Box: {mem}"
    assert len(drops) >= 1, f"expected drop for Box: {mem}"

    str_allocs = [e for e in mem if e["op"] == "alloc_string"]
    str_frees = [e for e in mem if e["op"] == "free_string" and e["action"] == "free"]
    assert len(str_allocs) >= 1, f"expected alloc_string from concat_s: {mem}"
    assert len(str_frees) >= 1, f"expected free_string on drop: {mem}"


# ---------------------------------------------------------------------------
# H – alloc_string from concat (no new/drop)
# ---------------------------------------------------------------------------


def test_trace_memory_alloc_string_from_concat(
    analyze_single, compile_and_run, tmp_path
):
    """concat_s produces alloc_string + free_string, but zero new_alloc/drop."""
    ok, _stdout, _stderr, mem = _compile_with_trace_memory(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        func main() -> int {
            let s: string = concat_s("a", "b");
            return 0;
        }
        """,
    )
    assert ok, _stderr

    str_allocs = [e for e in mem if e["op"] == "alloc_string"]
    str_frees = [e for e in mem if e["op"] == "free_string" and e["action"] == "free"]
    assert len(str_allocs) >= 1, f"expected alloc_string from concat_s: {mem}"
    assert len(str_frees) >= 1, f"expected free_string at scope exit: {mem}"

    new_allocs = [e for e in mem if e["op"] == "new_alloc"]
    drops = [e for e in mem if e["op"] == "drop"]
    assert len(new_allocs) == 0, f"unexpected new_alloc without new: {new_allocs}"
    assert len(drops) == 0, f"unexpected drop without new: {drops}"


# ---------------------------------------------------------------------------
# I – No trace events for stack-allocated struct
# ---------------------------------------------------------------------------


def test_trace_memory_no_trace_for_stack_struct(
    analyze_single, compile_and_run, tmp_path
):
    """A stack-allocated struct must not produce new_alloc or drop events."""
    ok, _stdout, _stderr, mem = _compile_with_trace_memory(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        struct S {
            x: int;
        }

        func main() -> int {
            let s: S = S(42);
            return 0;
        }
        """,
    )
    assert ok, _stderr

    new_allocs = [e for e in mem if e["op"] == "new_alloc"]
    drops = [e for e in mem if e["op"] == "drop"]
    assert len(new_allocs) == 0, f"unexpected new_alloc for stack struct: {new_allocs}"
    assert len(drops) == 0, f"unexpected drop for stack struct: {drops}"


# ---------------------------------------------------------------------------
# J – Multiple allocations: distinct ptrs, sets match
# ---------------------------------------------------------------------------


def test_trace_memory_multiple_allocations_paired(
    analyze_single, compile_and_run, tmp_path
):
    """3x new S / drop must yield 3 distinct ptrs; alloc ptr set == drop ptr set."""
    ok, _stdout, _stderr, mem = _compile_with_trace_memory(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        struct S {
            x: int;
            y: int;
        }

        func main() -> int {
            let a: S* = new S(1, 2);
            let b: S* = new S(3, 4);
            let c: S* = new S(5, 6);
            drop a;
            drop b;
            drop c;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    allocs = [e for e in mem if e["op"] == "new_alloc" and e["action"] == "ok"]
    drops = [e for e in mem if e["op"] == "drop" and e["action"] == "free"]
    assert len(allocs) == 3, f"expected 3 new_alloc events: {allocs}"
    assert len(drops) == 3, f"expected 3 drop events: {drops}"

    alloc_ptrs = {e["ptr"] for e in allocs}
    drop_ptrs = {e["ptr"] for e in drops}
    assert len(alloc_ptrs) == 3, f"expected 3 distinct alloc ptrs: {alloc_ptrs}"
    assert alloc_ptrs == drop_ptrs, (
        f"alloc ptrs {alloc_ptrs} != drop ptrs {drop_ptrs}"
    )


# ---------------------------------------------------------------------------
# K – Enum with string variant: both object and string events
# ---------------------------------------------------------------------------


def test_trace_memory_enum_with_string_variant(
    analyze_single, compile_and_run, tmp_path
):
    """new Str(concat_s(...)) / drop produces both object and string heap events."""
    ok, _stdout, _stderr, mem = _compile_with_trace_memory(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        enum Val {
            Str(value: string);
            Num(value: int);
        }

        func main() -> int {
            let v: Val* = new Str(concat_s("e", "num"));
            drop v;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    allocs = [e for e in mem if e["op"] == "new_alloc" and e["action"] == "ok"]
    drops = [e for e in mem if e["op"] == "drop" and e["action"] == "free"]
    assert len(allocs) >= 1, f"expected new_alloc for enum: {mem}"
    assert len(drops) >= 1, f"expected drop for enum: {mem}"

    str_allocs = [e for e in mem if e["op"] == "alloc_string"]
    str_frees = [e for e in mem if e["op"] == "free_string" and e["action"] == "free"]
    assert len(str_allocs) >= 1, f"expected alloc_string from concat_s: {mem}"
    assert len(str_frees) >= 1, f"expected free_string on enum drop: {mem}"


# ---------------------------------------------------------------------------
# L – Leak-freedom balance (comprehensive)
# ---------------------------------------------------------------------------


def test_trace_memory_leak_freedom_balance(
    analyze_single, compile_and_run, tmp_path
):
    """
    Complex program: 2x Pair + 1x Box(concat_s).

    Every new_alloc ptr must have a matching drop free.
    Every alloc_string ptr must have a matching free_string free.
    """
    ok, _stdout, _stderr, mem = _compile_with_trace_memory(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        struct Pair {
            x: int;
            y: int;
        }

        struct Box {
            s: string;
        }

        func main() -> int {
            let p1: Pair* = new Pair(1, 2);
            let p2: Pair* = new Pair(3, 4);
            let b: Box* = new Box(concat_s("hello", "world"));
            drop p1;
            drop p2;
            drop b;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    # Check new_alloc / drop pairing
    allocs = [e for e in mem if e["op"] == "new_alloc" and e["action"] == "ok"]
    drops = [e for e in mem if e["op"] == "drop" and e["action"] == "free"]

    alloc_ptrs = {e["ptr"] for e in allocs}
    drop_ptrs = {e["ptr"] for e in drops}

    assert len(alloc_ptrs) == 3, f"expected 3 unique new_alloc ptrs: {alloc_ptrs}"
    assert alloc_ptrs == drop_ptrs, (
        f"leak detected: alloc ptrs {alloc_ptrs} != drop ptrs {drop_ptrs}"
    )

    # Check alloc_string / free_string pairing
    str_allocs = [e for e in mem if e["op"] == "alloc_string"]
    str_frees = [e for e in mem if e["op"] == "free_string" and e["action"] == "free"]

    str_alloc_ptrs = {e["ptr"] for e in str_allocs}
    str_free_ptrs = {e["ptr"] for e in str_frees}

    assert len(str_alloc_ptrs) >= 1, f"expected at least one alloc_string: {mem}"
    assert str_alloc_ptrs == str_free_ptrs, (
        f"string leak: alloc_string ptrs {str_alloc_ptrs} != "
        f"free_string ptrs {str_free_ptrs}"
    )
