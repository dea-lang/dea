#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

"""
ARC trace runtime verification tests.

Each test compiles an L0 program with trace_arc=True, runs it, parses the
structured ``[l0][arc]`` lines from stderr, and asserts on refcount
transitions, action outcomes, and leak-freedom invariants.

Trace line format (from l0_runtime.h):
    [l0][arc] op=<retain|release> kind=<static|heap> ptr=<hex>
              rc_before=<int> rc_after=<int> action=<noop|retain|keep|free|...>
"""

import re
from collections import defaultdict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ARC_LINE_RE = re.compile(r"^\[l0\]\[arc\] (.+)$")
_KV_RE = re.compile(r"(\w+)=(\S+)")


def parse_arc_lines(stderr: str) -> list[dict[str, str]]:
    """Extract ``[l0][arc]`` lines and split key=value tokens into dicts."""
    results: list[dict[str, str]] = []
    for line in stderr.splitlines():
        m = _ARC_LINE_RE.match(line)
        if m:
            fields = dict(_KV_RE.findall(m.group(1)))
            results.append(fields)
    return results


def _heap_rc_values(arc_lines: list[dict[str, str]]) -> list[int]:
    """Collect integer rc_before/rc_after values from heap ARC events."""
    values: list[int] = []
    for ev in arc_lines:
        if ev.get("kind") != "heap":
            continue
        for key in ("rc_before", "rc_after"):
            raw = ev.get(key)
            if raw is None:
                continue
            if re.fullmatch(r"-?\d+", raw):
                values.append(int(raw))
    return values


def _compile_with_trace_arc(analyze_single, compile_and_run, tmp_path, src):
    """Shared pipeline: analyze → set trace_arc → codegen → compile → run → parse."""
    result = analyze_single("main", src)
    assert not result.has_errors(), result.diagnostics
    result.context.trace_arc = True

    from l0_backend import Backend

    c_code = Backend(result).generate()
    ok, stdout, stderr = compile_and_run(c_code, tmp_path)
    arc_lines = parse_arc_lines(stderr)
    return ok, stdout, stderr, arc_lines


# ---------------------------------------------------------------------------
# A – Static string noop
# ---------------------------------------------------------------------------


def test_trace_arc_static_string_noop(analyze_single, compile_and_run, tmp_path):
    """Static strings should produce only noop actions (no heap ops)."""
    ok, _stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        func main() -> int {
            let a: string = "hello";
            let b: string = a;
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert len(arc) > 0, "expected ARC trace events for static strings"
    for ev in arc:
        assert ev["kind"] == "static", f"unexpected heap event: {ev}"
        assert ev["action"] == "noop", f"expected noop for static: {ev}"


# ---------------------------------------------------------------------------
# B – Heap string lifecycle (concat → release → free)
# ---------------------------------------------------------------------------


def test_trace_arc_heap_string_lifecycle(analyze_single, compile_and_run, tmp_path):
    """A single heap string (from concat_s) must be freed with rc 1→0."""
    ok, _stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        func main() -> int {
            let h: string = concat_s("a", "b");
            return 0;
        }
        """,
    )
    assert ok, _stderr

    heap_releases = [e for e in arc if e["kind"] == "heap" and e["op"] == "release"]
    frees = [e for e in heap_releases if e["action"] == "free"]
    assert len(frees) >= 1, f"expected at least one heap free, got: {heap_releases}"

    for f in frees:
        assert f["rc_before"] == "1"
        assert f["rc_after"] == "0"


# ---------------------------------------------------------------------------
# C – Copy-retain then release
# ---------------------------------------------------------------------------


def test_trace_arc_string_copy_retain_and_release(
    analyze_single, compile_and_run, tmp_path
):
    """Copying a heap string must retain (1→2), then release both (keep 2→1, free 1→0)."""
    ok, _stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        func main() -> int {
            let a: string = concat_s("x", "y");
            let b: string = a;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    heap = [e for e in arc if e["kind"] == "heap"]
    retains = [e for e in heap if e["op"] == "retain" and e["action"] == "retain"]
    assert any(
        e["rc_before"] == "1" and e["rc_after"] == "2" for e in retains
    ), f"expected retain 1→2: {retains}"

    releases = [e for e in heap if e["op"] == "release"]
    keeps = [e for e in releases if e["action"] == "keep"]
    frees = [e for e in releases if e["action"] == "free"]
    assert any(
        e["rc_before"] == "2" and e["rc_after"] == "1" for e in keeps
    ), f"expected keep 2→1: {keeps}"
    assert any(
        e["rc_before"] == "1" and e["rc_after"] == "0" for e in frees
    ), f"expected free 1→0: {frees}"


# ---------------------------------------------------------------------------
# D – Fanout: three references
# ---------------------------------------------------------------------------


def test_trace_arc_fanout_three_references(
    analyze_single, compile_and_run, tmp_path
):
    """Three aliases to one heap string: retain 1→2→3, then release 3→2→1→0."""
    ok, _stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        func main() -> int {
            let a: string = concat_s("f", "o");
            let b: string = a;
            let c: string = a;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    heap = [e for e in arc if e["kind"] == "heap"]
    retains = [e for e in heap if e["op"] == "retain" and e["action"] == "retain"]

    rc_afters = sorted(int(e["rc_after"]) for e in retains)
    assert 2 in rc_afters, f"expected retain to rc=2: {retains}"
    assert 3 in rc_afters, f"expected retain to rc=3: {retains}"

    releases = [e for e in heap if e["op"] == "release"]
    frees = [e for e in releases if e["action"] == "free"]
    assert any(
        e["rc_before"] == "1" and e["rc_after"] == "0" for e in frees
    ), f"expected final free 1→0: {frees}"


# ---------------------------------------------------------------------------
# E – Discarded concat freed immediately
# ---------------------------------------------------------------------------


def test_trace_arc_discarded_concat_freed(
    analyze_single, compile_and_run, tmp_path
):
    """A discarded call result (no binding) must still be freed."""
    ok, _stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        func main() -> int {
            concat_s("a", "b");
            return 0;
        }
        """,
    )
    assert ok, _stderr

    heap = [e for e in arc if e["kind"] == "heap"]
    frees = [e for e in heap if e["op"] == "release" and e["action"] == "free"]
    assert len(frees) >= 1, f"expected discarded temp to be freed: {heap}"
    assert frees[0]["rc_before"] == "1"
    assert frees[0]["rc_after"] == "0"

    # No heap retains expected for a discarded temp.
    heap_retains = [
        e for e in heap if e["op"] == "retain" and e["action"] == "retain"
    ]
    assert len(heap_retains) == 0, f"unexpected heap retain: {heap_retains}"


# ---------------------------------------------------------------------------
# F – Unwrap-cast scrutinee copies retain correctly
# ---------------------------------------------------------------------------


def test_trace_arc_case_scrutinee_unwrap_retains(
    analyze_single, compile_and_run, tmp_path
):
    """`case (opt as string)` must retain `_scrutinee` before later cleanup."""
    ok, _stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        func main() -> int {
            let opt: string? = concat_s("o", "k") as string?;
            case (opt as string) {
                "ok" => { return 0; }
                else { return 1; }
            }
        }
        """,
    )
    assert ok, _stderr

    heap = [e for e in arc if e["kind"] == "heap"]
    assert [(e["op"], e["action"], e["rc_before"], e["rc_after"]) for e in heap] == [
        ("retain", "retain", "1", "2"),
        ("release", "keep", "2", "1"),
        ("release", "free", "1", "0"),
    ], f"unexpected case scrutinee ARC sequence: {heap!r}"


def test_trace_arc_match_scrutinee_enum_unwrap_retains(
    analyze_single, compile_and_run, tmp_path
):
    """`match (value? as Value)` must retain the string-bearing scrutinee copy."""
    ok, _stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        enum Value {
            String(s: string);
            OptString(s: string?);
        }

        func get_opt_value(v: Value) -> Value? {
            match (v) {
                OptString(x) => {
                    if (x == null) {
                        return null;
                    }
                    return String(x as string);
                }
                _ => { return v; }
            }
        }

        func main() -> int {
            let unwrapped = get_opt_value(OptString(concat_s("o", "k") as string?));
            if (unwrapped == null) {
                return 1;
            }
            match (unwrapped as Value) {
                String(s) => { return 0; }
                _ => { return 2; }
            }
        }
        """,
    )
    assert ok, _stderr

    heap = [e for e in arc if e["kind"] == "heap"]
    assert [(e["op"], e["action"], e["rc_before"], e["rc_after"]) for e in heap] == [
        ("retain", "retain", "1", "2"),
        ("retain", "retain", "2", "3"),
        ("release", "keep", "3", "2"),
        ("release", "keep", "2", "1"),
        ("release", "free", "1", "0"),
    ], f"unexpected enum scrutinee ARC sequence: {heap!r}"


# ---------------------------------------------------------------------------
# G – Struct with static string field drop
# ---------------------------------------------------------------------------


def test_trace_arc_struct_string_field_drop(
    analyze_single, compile_and_run, tmp_path
):
    """Dropping a struct with a static string field fires a static release noop."""
    ok, _stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        struct Box {
            s: string;
        }

        func main() -> int {
            let b: Box* = new Box("hello");
            drop b;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    static_releases = [
        e for e in arc if e["kind"] == "static" and e["op"] == "release"
    ]
    assert any(
        e["action"] == "noop" for e in static_releases
    ), f"expected static release noop on struct drop: {arc}"


# ---------------------------------------------------------------------------
# F2 – Struct with heap string field drop
# ---------------------------------------------------------------------------


def test_trace_arc_struct_heap_string_field_drop(
    analyze_single, compile_and_run, tmp_path
):
    """Dropping a struct with a heap string field must free the string."""
    ok, _stdout, _stderr, arc = _compile_with_trace_arc(
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

    heap_frees = [
        e for e in arc
        if e["kind"] == "heap" and e["op"] == "release" and e["action"] == "free"
    ]
    assert len(heap_frees) >= 1, f"expected heap free on struct drop: {arc}"
    assert heap_frees[-1]["rc_after"] == "0"


# ---------------------------------------------------------------------------
# G – Enum string variant cleanup
# ---------------------------------------------------------------------------


def test_trace_arc_enum_string_variant_cleanup(
    analyze_single, compile_and_run, tmp_path
):
    """A heap string inside an enum variant must be freed at scope exit."""
    ok, _stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        enum E {
            Val(value: string);
            Empty;
        }

        func main() -> int {
            let e: E = Val(concat_s("v", "al"));
            return 0;
        }
        """,
    )
    assert ok, _stderr

    heap_frees = [
        e for e in arc
        if e["kind"] == "heap" and e["op"] == "release" and e["action"] == "free"
    ]
    assert len(heap_frees) >= 1, f"expected heap free for enum variant: {arc}"


# ---------------------------------------------------------------------------
# H – Optional string cleanup
# ---------------------------------------------------------------------------


def test_trace_arc_optional_string_cleanup(
    analyze_single, compile_and_run, tmp_path
):
    """A heap string wrapped in string? must be freed at scope exit."""
    ok, _stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        func main() -> int {
            let v: string? = concat_s("o", "pt") as string?;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    heap_frees = [
        e for e in arc
        if e["kind"] == "heap" and e["op"] == "release" and e["action"] == "free"
    ]
    assert len(heap_frees) >= 1, f"expected heap free for optional string: {arc}"


# ---------------------------------------------------------------------------
# H2 – Null optional: no heap releases
# ---------------------------------------------------------------------------


def test_trace_arc_null_optional_no_heap_release(
    analyze_single, compile_and_run, tmp_path
):
    """A null optional string must not produce any heap release events."""
    ok, _stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        func main() -> int {
            let v: string? = null;
            return 0;
        }
        """,
    )
    assert ok, _stderr

    heap_releases = [
        e for e in arc if e["kind"] == "heap" and e["op"] == "release"
    ]
    assert len(heap_releases) == 0, f"unexpected heap release for null optional: {heap_releases}"


# ---------------------------------------------------------------------------
# I – Optional unwrap ownership boundaries
# ---------------------------------------------------------------------------


def test_trace_arc_optional_unwrap_return_stabilized(
    analyze_single, compile_and_run, tmp_path
):
    """`return opt as string` from a local optional must retain before cleanup."""
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;
        import std.io;

        func make() -> string {
            let opt: string? = concat_s("p", "q") as string?;
            return opt as string;
        }

        func main() -> int {
            let x: string = make();
            printl_s(x);
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout == "pq\n", f"unexpected output for optional unwrap return: {stdout!r}"

    heap_retains = [e for e in arc if e["kind"] == "heap" and e["op"] == "retain"]
    assert any(
        e["action"] == "retain" and e["rc_before"] == "1" and e["rc_after"] == "2"
        for e in heap_retains
    ), f"expected retain 1→2 before optional cleanup: {heap_retains}"

    panic_actions = [e for e in arc if e.get("action", "").startswith("panic")]
    assert len(panic_actions) == 0, f"unexpected ARC panic action(s): {panic_actions}"

    rc_values = _heap_rc_values(arc)
    assert all(0 <= rc <= 8 for rc in rc_values), f"suspicious heap refcounts: {rc_values}"


def test_trace_arc_optional_unwrap_into_vector_stabilized(
    analyze_single, compile_and_run, tmp_path
):
    """`vs_push(v, opt as string)` must not leave vector entries dangling."""
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;
        import std.vector;
        import std.io;

        func build() -> VectorString* {
            let v = vs_create(0);
            let opt: string? = concat_s("c", "d") as string?;
            vs_push(v, opt as string);
            return v;
        }

        func main() -> int {
            let v = build();
            let s = vs_get(v, 0);
            printl_s(s);
            vs_free(v);
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout == "cd\n", f"unexpected output for vector unwrap push: {stdout!r}"

    panic_actions = [e for e in arc if e.get("action", "").startswith("panic")]
    assert len(panic_actions) == 0, f"unexpected ARC panic action(s): {panic_actions}"

    rc_values = _heap_rc_values(arc)
    assert all(0 <= rc <= 8 for rc in rc_values), f"suspicious heap refcounts: {rc_values}"

    frees = [
        e for e in arc
        if e["kind"] == "heap" and e["op"] == "release" and e["action"] == "free"
    ]
    assert len(frees) >= 1, f"expected at least one heap free: {arc}"


# ---------------------------------------------------------------------------
# J – Nested concat: intermediary freed
# ---------------------------------------------------------------------------


def test_trace_arc_nested_concat_intermediary_freed(
    analyze_single, compile_and_run, tmp_path
):
    """Nested concat_s must free both the intermediary and the outer result."""
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.io;
        import std.string;

        func main() -> int {
            let x: string = concat_s("a", concat_s("b", "c"));
            printl_s(x);
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout.strip() == "abc"

    heap_frees = [
        e for e in arc
        if e["kind"] == "heap" and e["op"] == "release" and e["action"] == "free"
    ]
    # At least 2 heap frees: the intermediary concat_s("b","c") and the outer result.
    assert len(heap_frees) >= 2, (
        f"expected >=2 heap frees (intermediary + final), got {len(heap_frees)}: {heap_frees}"
    )
    # All should be simple rc 1→0 frees (no shared references).
    for f in heap_frees:
        assert f["rc_before"] == "1" and f["rc_after"] == "0", (
            f"expected rc 1→0 free: {f}"
        )


def test_trace_arc_concat3_nested_argument_freed(
    analyze_single, compile_and_run, tmp_path
):
    """concat3_s-style nested argument temps must be freed on each call."""
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.io;
        import std.string;

        func concat3_s(a: string, b: string, c: string) -> string {
            return concat_s(concat_s(a, b), c);
        }

        func main() -> int {
            let x: string = concat3_s("a", "b", "c");
            let y: string = concat3_s("", "middle", "");
            printl_s(x);
            printl_s(y);
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout.strip().splitlines() == ["abc", "middle"]

    heap_frees = [
        e for e in arc
        if e["kind"] == "heap" and e["op"] == "release" and e["action"] == "free"
    ]
    # Two concat3_s calls => each has one intermediary + one final heap string.
    assert len(heap_frees) >= 4, (
        f"expected >=4 heap frees (2 calls x intermediary+final), got {len(heap_frees)}: {heap_frees}"
    )
    for f in heap_frees:
        assert f["rc_before"] == "1" and f["rc_after"] == "0", (
            f"expected rc 1→0 free: {f}"
        )


def test_trace_arc_loop_continue_skips_uninitialized_arc_cleanup(
    analyze_single, compile_and_run, tmp_path
):
    """A continue path before ARC local initialization must not trigger invalid cleanup."""
    ok, stdout, stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.io;
        import std.string;

        func mk_name(n: int) -> string {
            if (n == 0) {
                return concat_s("a", "0");
            }
            return concat_s("b", "1");
        }

        func main() -> int {
            let total: int = 0;
            for (let i = 0; i < 3; i = i + 1) {
                if (i == 0) {
                    continue;
                }

                let name = mk_name(i);
                printl_s(name);
                total = total + len_s(name);
            }
            return 0;
        }
        """,
    )
    assert ok, stderr
    assert stdout.strip().splitlines() == ["b1", "b1"]

    heap_rcs = _heap_rc_values(arc)
    assert heap_rcs, f"expected heap ARC events, stderr={stderr}"
    assert all(0 <= rc < 1000 for rc in heap_rcs), (
        f"unexpected heap refcount values: {heap_rcs}"
    )


def test_trace_arc_loop_continue_cleans_only_acquired_arc_locals(
    analyze_single, compile_and_run, tmp_path
):
    """Each continue path should release exactly the ARC locals acquired on that path."""
    ok, stdout, stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        func mk_a(n: int) -> string {
            return concat_s("a", "1");
        }

        func mk_b(n: int) -> string {
            return concat_s("b", "2");
        }

        func main() -> int {
            for (let i = 0; i < 3; i = i + 1) {
                if (i == 0) {
                    continue;
                }

                let a = mk_a(i);
                if (i == 1) {
                    continue;
                }

                let b = mk_b(i);
                if (len_s(b) > 0) {
                    continue;
                }
            }
            return 0;
        }
        """,
    )
    assert ok, stderr
    assert stdout == ""

    heap_rcs = _heap_rc_values(arc)
    assert heap_rcs, f"expected heap ARC events, stderr={stderr}"
    assert all(0 <= rc < 1000 for rc in heap_rcs), (
        f"unexpected heap refcount values: {heap_rcs}"
    )

    heap_frees = [
        e for e in arc
        if e["kind"] == "heap" and e["op"] == "release" and e["action"] == "free"
    ]
    assert len(heap_frees) >= 3, (
        f"expected frees for two `a` values and one `b` value, got: {heap_frees}"
    )
    for f in heap_frees:
        assert f["rc_before"] == "1" and f["rc_after"] == "0", (
            f"expected rc 1→0 free: {f}"
        )


def test_trace_arc_loop_break_after_single_arc_local_cleans_that_local(
    analyze_single, compile_and_run, tmp_path
):
    """A break after one ARC acquisition must free that value before leaving the loop."""
    ok, stdout, stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        func mk_a(n: int) -> string {
            return concat_s("a", "1");
        }

        func main() -> int {
            for (let i = 0; i < 2; i = i + 1) {
                let a = mk_a(i);
                break;
            }
            return 0;
        }
        """,
    )
    assert ok, stderr
    assert stdout == ""

    heap_frees = [
        e for e in arc
        if e["kind"] == "heap" and e["op"] == "release" and e["action"] == "free"
    ]
    assert len(heap_frees) >= 1, f"expected a heap free for `a`, got: {heap_frees}"
    for f in heap_frees:
        assert f["rc_before"] == "1" and f["rc_after"] == "0", (
            f"expected rc 1→0 free: {f}"
        )


def test_trace_arc_loop_return_after_single_arc_local_cleans_that_local(
    analyze_single, compile_and_run, tmp_path
):
    """A return after one ARC acquisition in a loop must free that value before returning."""
    ok, stdout, stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        func mk_a(n: int) -> string {
            return concat_s("a", "1");
        }

        func main() -> int {
            for (let i = 0; i < 2; i = i + 1) {
                let a = mk_a(i);
                return 0;
            }
            return 0;
        }
        """,
    )
    assert ok, stderr
    assert stdout == ""

    heap_frees = [
        e for e in arc
        if e["kind"] == "heap" and e["op"] == "release" and e["action"] == "free"
    ]
    assert len(heap_frees) >= 1, f"expected a heap free for `a`, got: {heap_frees}"
    for f in heap_frees:
        assert f["rc_before"] == "1" and f["rc_after"] == "0", (
            f"expected rc 1→0 free: {f}"
        )


# ---------------------------------------------------------------------------
# J – Return borrowed param retains
# ---------------------------------------------------------------------------


def test_trace_arc_return_borrowed_param_retains(
    analyze_single, compile_and_run, tmp_path
):
    """Returning a borrowed string param must retain it (1→2) for the caller."""
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.io;
        import std.string;

        func id_s(s: string) -> string {
            return s;
        }

        func main() -> int {
            let a: string = concat_s("i", "d");
            let b: string = id_s(a);
            printl_s(b);
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout.strip() == "id"

    heap = [e for e in arc if e["kind"] == "heap"]
    retains = [e for e in heap if e["op"] == "retain" and e["action"] == "retain"]
    assert any(
        e["rc_before"] == "1" and e["rc_after"] == "2" for e in retains
    ), f"expected retain 1→2 for borrowed return: {retains}"

    releases = [e for e in heap if e["op"] == "release"]
    keeps = [e for e in releases if e["action"] == "keep"]
    frees = [e for e in releases if e["action"] == "free"]
    assert len(keeps) >= 1, f"expected at least one keep release: {releases}"
    assert len(frees) >= 1, f"expected at least one free release: {releases}"


# ---------------------------------------------------------------------------
# K – Condition temps in control-flow headers
# ---------------------------------------------------------------------------


def test_trace_arc_control_flow_condition_temp_cleanup(
    analyze_single, compile_and_run, tmp_path
):
    """Dynamic-string condition temps in `if`/`while` headers must stay leak-free."""
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        extern func rt_print_int(x: int) -> void;
        extern func rt_println() -> void;

        func tick(flag: bool) -> string {
            if (flag) {
                return concat_s("x", "");
            }
            return concat_s("", "");
        }

        func main() -> int {
            if (false && len_s(tick(true)) > 0) {
                rt_print_int(9);
                rt_println();
            }

            let i: int = 0;
            while (i < 3 && len_s(tick(i == 0)) > 0) {
                i = i + 1;
            }

            rt_print_int(i);
            rt_println();
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout.strip() == "1"

    heap = [e for e in arc if e["kind"] == "heap"]
    frees = [e for e in heap if e["op"] == "release" and e["action"] == "free"]
    assert len(frees) >= 1, f"expected condition heap values to be freed: {heap}"

    rc_values = _heap_rc_values(arc)
    assert rc_values, "expected heap ARC events for dynamic-string condition temps"
    assert min(rc_values) >= 0, f"unexpected negative heap refcount values: {heap}"
    assert max(rc_values) <= 2, f"unexpected heap refcount growth in condition temps: {heap}"


# ---------------------------------------------------------------------------
# L – Logical-expression short-circuit temps
# ---------------------------------------------------------------------------


def test_trace_arc_logical_expression_temp_cleanup(
    analyze_single, compile_and_run, tmp_path
):
    """Value-context logical expressions must short-circuit and free only taken RHS temps."""
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.string;

        extern func rt_print_int(x: int) -> void;
        extern func rt_println() -> void;

        func tick(flag: bool) -> string {
            if (flag) {
                return concat_s("x", "");
            }
            return concat_s("", "");
        }

        func main() -> int {
            let a: bool = false && len_s(tick(true)) > 0;
            let b: bool = true || len_s(tick(true)) > 0;
            let c: bool = false || len_s(tick(true)) > 0;
            let d: bool = true && len_s(tick(true)) > 0;

            let total: int = 0;
            if (a) { total = total + 1; }
            if (b) { total = total + 1; }
            if (c) { total = total + 1; }
            if (d) { total = total + 1; }

            rt_print_int(total);
            rt_println();
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout.strip() == "3"

    heap = [e for e in arc if e["kind"] == "heap"]
    frees = [e for e in heap if e["op"] == "release" and e["action"] == "free"]
    assert len(frees) == 2, f"expected frees only for taken RHS logical branches: {heap}"

    rc_values = _heap_rc_values(arc)
    assert rc_values, "expected heap ARC events for logical-expression temps"
    assert min(rc_values) >= 0, f"unexpected negative heap refcount values: {heap}"
    assert max(rc_values) <= 2, f"unexpected heap refcount growth in logical-expression temps: {heap}"


# ---------------------------------------------------------------------------
# M – Leak-freedom balance (comprehensive)
# ---------------------------------------------------------------------------


def test_trace_arc_leak_freedom_balance(
    analyze_single, compile_and_run, tmp_path
):
    """
    Complex program exercising concat, copy, id_s, discard, and print.

    Every unique heap pointer must have ``action=free`` as its last event,
    and the number of free events must equal the number of unique heap pointers.
    """
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.io;
        import std.string;

        func id_s(s: string) -> string {
            return s;
        }

        func main() -> int {
            let a: string = concat_s("he", "llo");
            let b: string = a;
            let c: string = id_s(b);
            concat_s("dis", "card");
            printl_s(c);
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout.strip() == "hello"

    # Group heap events by ptr.
    heap = [e for e in arc if e["kind"] == "heap"]
    by_ptr: dict[str, list[dict[str, str]]] = defaultdict(list)
    for ev in heap:
        by_ptr[ev["ptr"]].append(ev)

    assert len(by_ptr) > 0, "expected at least one heap pointer"

    # Every unique heap pointer must end with a free.
    for ptr, events in by_ptr.items():
        last = events[-1]
        assert last["action"] == "free", (
            f"ptr {ptr}: last action is {last['action']}, not free. events={events}"
        )

    # The total number of frees must equal the number of unique heap pointers.
    total_frees = sum(
        1 for ev in heap if ev["op"] == "release" and ev["action"] == "free"
    )
    assert total_frees == len(by_ptr), (
        f"free count ({total_frees}) != unique heap ptrs ({len(by_ptr)})"
    )


# ---------------------------------------------------------------------------
# M – Borrowed ARC parameter reassignment
# ---------------------------------------------------------------------------


def _assert_no_double_free(arc: list[dict[str, str]]) -> None:
    """No heap event may release an already-freed object or produce a negative refcount.

    This catches the borrowed-param reassignment bug directly: the pre-fix
    lowering releases the caller's value while it is still referenced, so a
    later release by the caller would see ``rc_before=0`` (or ``rc_after<0``
    under non-reuse heaps) or fail outright under UCRT.
    """
    heap = [e for e in arc if e["kind"] == "heap"]
    assert heap, "expected heap ARC events"
    for ev in heap:
        rc_before = int(ev["rc_before"])
        rc_after = int(ev["rc_after"])
        assert rc_before >= 1, f"release of already-freed object: {ev}"
        assert rc_after >= 0, f"negative refcount: {ev}"
        if ev["op"] == "release":
            assert rc_after == rc_before - 1, f"malformed release: {ev}"
        else:
            assert rc_after == rc_before + 1, f"malformed retain: {ev}"


def _assert_last_event_is_free(arc: list[dict[str, str]]) -> None:
    """Every heap pointer's final event must be a free (reuse-safe; covers no-reuse leaks)."""
    heap = [e for e in arc if e["kind"] == "heap"]
    by_ptr: dict[str, list[dict[str, str]]] = defaultdict(list)
    for ev in heap:
        by_ptr[ev["ptr"]].append(ev)
    assert by_ptr, "expected at least one heap pointer in trace"
    for ptr, events in by_ptr.items():
        last = events[-1]
        assert last["action"] == "free", (
            f"ptr {ptr}: last action is {last['action']}, not free. events={events}"
        )


def test_trace_arc_param_unconditional_reassign(
    analyze_single, compile_and_run, tmp_path
):
    """Unconditional reassignment of a borrowed string param must balance and not double-free."""
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.io;
        import std.string;

        func f(s: string) {
            s = concat_s("one", "1");
            s = concat_s("two", "2");
            printl_s(s);
        }

        func main() -> int {
            let input: string = concat_s("o", "ld");
            f(input);
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout.strip() == "two2"
    _assert_no_double_free(arc)
    _assert_last_event_is_free(arc)


def test_trace_arc_param_conditional_reassign(
    analyze_single, compile_and_run, tmp_path
):
    """Reassignment in only one branch must not double-free the caller's value on the other branch."""
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.io;
        import std.string;

        func f(flag: bool, s: string) {
            if (flag) {
                s = concat_s("new", "-value");
            }
            printl_s(s);
        }

        func main() -> int {
            let input: string = concat_s("o", "ld");
            f(false, input);
            f(true, input);
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout.splitlines() == ["old", "new-value"]
    _assert_no_double_free(arc)
    _assert_last_event_is_free(arc)


def test_trace_arc_param_loop_carried_reassign(
    analyze_single, compile_and_run, tmp_path
):
    """Reassignment inside a loop body must balance across iterations and at exit."""
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.io;
        import std.string;

        func f(s: string) {
            let i: int = 0;
            while (i < 3) {
                s = concat_s("x", "y");
                i = i + 1;
            }
            printl_s(s);
        }

        func main() -> int {
            let input: string = concat_s("o", "ld");
            f(input);
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout.strip() == "xy"
    _assert_no_double_free(arc)
    _assert_last_event_is_free(arc)


def test_trace_arc_param_for_update_reassign(
    analyze_single, compile_and_run, tmp_path
):
    """Reassignment in a `for` update clause must be discovered and balanced."""
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.io;
        import std.string;

        func f(s: string) {
            let i: int = 0;
            for (; i < 2; s = concat_s("up", "date")) {
                i = i + 1;
            }
            printl_s(s);
        }

        func main() -> int {
            let input: string = concat_s("o", "ld");
            f(input);
            printl_s(input);
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout.splitlines() == ["update", "old"]
    _assert_no_double_free(arc)
    _assert_last_event_is_free(arc)


def test_trace_arc_param_with_header_and_cleanup_reassign(
    analyze_single, compile_and_run, tmp_path
):
    """Reassignment in `with` header init/cleanup must be discovered and balanced."""
    ok, stdout, _stderr, arc = _compile_with_trace_arc(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import std.io;
        import std.string;

        func f(s: string) {
            with (s = concat_s("head", "er") => s = concat_s("clean", "up")) {
                printl_s(s);
            }
            printl_s(s);
        }

        func main() -> int {
            let input: string = concat_s("o", "ld");
            f(input);
            printl_s(input);
            return 0;
        }
        """,
    )
    assert ok, _stderr
    assert stdout.splitlines() == ["header", "cleanup", "old"]
    _assert_no_double_free(arc)
    _assert_last_event_is_free(arc)
