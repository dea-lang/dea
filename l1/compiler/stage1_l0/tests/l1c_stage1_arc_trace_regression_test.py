#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for Stage 1 ARC trace behavior."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
TRACE_CHECKER = L1_ROOT / "compiler" / "stage1_l0" / "scripts" / "check_trace_log.py"

_ARC_LINE_RE = re.compile(r"^\[l0\]\[arc\] (.+)$")
_KV_RE = re.compile(r"(\w+)=(\S+)")


class ArcTraceFailure(RuntimeError):
    """Raised when one ARC trace regression check fails."""


def resolve_tool(base: Path) -> Path:
    """Return a host-compatible launcher path for one tool base path."""

    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
        return base.with_suffix(".cmd")
    return base


def read_text(path: Path) -> str:
    """Read one text file with replacement for invalid bytes."""

    return path.read_text(encoding="utf-8", errors="replace")


def stage1_compiler() -> Path:
    """Return the repo-local Stage 1 compiler path."""

    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def parse_arc_lines(stderr: str) -> list[dict[str, str]]:
    """Extract structured ARC events from trace stderr."""

    results: list[dict[str, str]] = []
    for line in stderr.splitlines():
        match = _ARC_LINE_RE.match(line)
        if match is None:
            continue
        results.append(dict(_KV_RE.findall(match.group(1))))
    return results


def fail(message: str, artifact_dir: Path) -> None:
    """Abort the test and keep artifacts."""

    raise ArcTraceFailure(f"{message}\nartifacts={artifact_dir}")


def assert_true(condition: bool, message: str, artifact_dir: Path) -> None:
    """Raise one artifact-rich failure when `condition` is false."""

    if not condition:
        fail(message, artifact_dir)


def assert_equal(actual: object, expected: object, message: str, artifact_dir: Path) -> None:
    """Assert equality with one artifact-rich failure."""

    if actual != expected:
        fail(f"{message}: expected {expected!r}, got {actual!r}", artifact_dir)


def assert_any(
    events: list[dict[str, str]],
    predicate,
    message: str,
    artifact_dir: Path,
) -> None:
    """Assert that at least one event satisfies `predicate`."""

    if not any(predicate(event) for event in events):
        fail(f"{message}: {events!r}", artifact_dir)


def heap_events(arc_lines: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return heap ARC events only."""

    return [event for event in arc_lines if event.get("kind") == "heap"]


def heap_retains(arc_lines: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return heap retain events only."""

    return [event for event in heap_events(arc_lines) if event.get("op") == "retain"]


def heap_releases(arc_lines: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return heap release events only."""

    return [event for event in heap_events(arc_lines) if event.get("op") == "release"]


def heap_frees(arc_lines: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return heap terminal free events only."""

    return [event for event in heap_releases(arc_lines) if event.get("action") == "free"]


def heap_arc_sequence(arc_lines: list[dict[str, str]]) -> list[tuple[str | None, str | None, str | None, str | None]]:
    """Return heap ARC events as `(op, action, rc_before, rc_after)` tuples."""

    return [
        (event.get("op"), event.get("action"), event.get("rc_before"), event.get("rc_after"))
        for event in heap_events(arc_lines)
    ]


def assert_heap_transition_counts(
    arc_lines: list[dict[str, str]],
    expected_retains: int,
    expected_keeps: int,
    expected_frees: int,
    message: str,
    artifact_dir: Path,
) -> None:
    """Assert ARC transition counts and refcount deltas for heap events."""

    retains = [event for event in heap_retains(arc_lines) if event.get("action") == "retain"]
    keeps = [event for event in heap_releases(arc_lines) if event.get("action") == "keep"]
    frees = heap_frees(arc_lines)

    assert_equal(len(retains), expected_retains, f"{message}: retain count mismatch", artifact_dir)
    assert_equal(len(keeps), expected_keeps, f"{message}: keep count mismatch", artifact_dir)
    assert_equal(len(frees), expected_frees, f"{message}: free count mismatch", artifact_dir)

    for event in retains:
        assert_true(
            event.get("rc_before") == "1" and event.get("rc_after") == "2",
            f"{message}: expected retain 1->2, got {event!r}",
            artifact_dir,
        )
    for event in keeps:
        assert_true(
            event.get("rc_before") == "2" and event.get("rc_after") == "1",
            f"{message}: expected keep 2->1, got {event!r}",
            artifact_dir,
        )
    for event in frees:
        assert_true(
            event.get("rc_before") == "1" and event.get("rc_after") == "0",
            f"{message}: expected free 1->0, got {event!r}",
            artifact_dir,
        )


def static_events(arc_lines: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return static ARC events only."""

    return [event for event in arc_lines if event.get("kind") == "static"]


def write_case_source(artifact_dir: Path, case_name: str, source: str) -> Path:
    """Write one temporary L1 source file for one regression case."""

    case_dir = artifact_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    source_path = case_dir / "main.l1"
    source_path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return source_path


def run_case(case_name: str, source: str, artifact_dir: Path) -> tuple[str, str, str, list[dict[str, str]]]:
    """Compile and run one Stage 1 trace case."""

    compiler = stage1_compiler()
    assert_true(compiler.is_file(), f"missing repo-local Stage 1 compiler: {compiler}", artifact_dir)

    source_path = write_case_source(artifact_dir, case_name, source)
    stdout_path = artifact_dir / f"{case_name}.stdout.log"
    stderr_path = artifact_dir / f"{case_name}.stderr.log"
    report_path = artifact_dir / f"{case_name}.trace_report.txt"

    run_result = subprocess.run(
        [str(compiler), "--run", "--trace-memory", "--trace-arc", str(source_path)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_path.write_bytes(run_result.stdout if run_result.stdout is not None else b"")
    stderr_path.write_bytes(run_result.stderr if run_result.stderr is not None else b"")

    stdout_text = read_text(stdout_path)
    stderr_text = read_text(stderr_path)
    if run_result.returncode != 0:
        fail(f"{case_name} expected exit code 0, got {run_result.returncode}", artifact_dir)

    with report_path.open("w", encoding="utf-8") as report_file:
        analyzer_result = subprocess.run(
            [sys.executable, str(TRACE_CHECKER), "--triage", str(stderr_path)],
            cwd=REPO_ROOT,
            stdout=report_file,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    report_text = read_text(report_path)
    if analyzer_result.returncode != 0:
        fail(f"{case_name} trace triage failed (analyzer_rc={analyzer_result.returncode})", artifact_dir)

    assert_true("errors=0" in report_text, f"{case_name} trace report recorded errors", artifact_dir)
    assert_true(
        "leaked_object_ptrs=0" in report_text,
        f"{case_name} trace report recorded object leaks",
        artifact_dir,
    )
    assert_true(
        "leaked_string_ptrs=0" in report_text,
        f"{case_name} trace report recorded string leaks",
        artifact_dir,
    )
    return stdout_text, stderr_text, report_text, parse_arc_lines(stderr_text)


def test_static_string_noop(artifact_dir: Path) -> None:
    """Static strings should produce only static noop ARC events."""

    _stdout, _stderr, _report, arc = run_case(
        "static_string_noop",
        """
        module main;

        func main() -> int {
            let a: string = "hello";
            let b: string = a;
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_true(len(arc) > 0, "expected ARC trace events for static strings", artifact_dir)
    for event in static_events(arc):
        assert_true(event.get("action") == "noop", f"expected static noop ARC event {event!r}", artifact_dir)
    assert_true(
        len(heap_events(arc)) == 0,
        f"unexpected heap ARC events for static strings: {heap_events(arc)!r}",
        artifact_dir,
    )


def test_heap_string_lifecycle(artifact_dir: Path) -> None:
    """One heap string must end with a terminal free."""

    _stdout, _stderr, _report, arc = run_case(
        "heap_string_lifecycle",
        """
        module main;
        import std.string;

        func main() -> int {
            let s: string = concat_s("a", "b");
            return 0;
        }
        """,
        artifact_dir,
    )

    frees = heap_frees(arc)
    assert_true(len(frees) >= 1, f"expected at least one heap free, got {frees!r}", artifact_dir)
    for event in frees:
        assert_true(
            event.get("rc_before") == "1" and event.get("rc_after") == "0",
            f"expected rc 1->0 free, got {event!r}",
            artifact_dir,
        )


def test_string_copy_retain_and_release(artifact_dir: Path) -> None:
    """Copying a heap string must retain then release through keep/free."""

    _stdout, _stderr, _report, arc = run_case(
        "string_copy_retain_and_release",
        """
        module main;
        import std.string;

        func main() -> int {
            let a: string = concat_s("x", "y");
            let b: string = a;
            return 0;
        }
        """,
        artifact_dir,
    )

    retains = heap_retains(arc)
    assert_any(
        retains,
        lambda event: event.get("action") == "retain"
        and event.get("rc_before") == "1"
        and event.get("rc_after") == "2",
        "expected retain 1->2 after string copy",
        artifact_dir,
    )

    releases = heap_releases(arc)
    assert_any(
        releases,
        lambda event: event.get("action") == "keep"
        and event.get("rc_before") == "2"
        and event.get("rc_after") == "1",
        "expected keep 2->1 after copied string cleanup",
        artifact_dir,
    )
    assert_any(
        releases,
        lambda event: event.get("action") == "free"
        and event.get("rc_before") == "1"
        and event.get("rc_after") == "0",
        "expected free 1->0 after copied string cleanup",
        artifact_dir,
    )


def test_fanout_three_references(artifact_dir: Path) -> None:
    """Three aliases to one heap string must retain to rc 3 and free at the end."""

    _stdout, _stderr, _report, arc = run_case(
        "fanout_three_references",
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
        artifact_dir,
    )

    retains = heap_retains(arc)
    rc_afters = sorted(int(event["rc_after"]) for event in retains if "rc_after" in event)
    assert_true(2 in rc_afters, f"expected retain to rc=2, got {retains!r}", artifact_dir)
    assert_true(3 in rc_afters, f"expected retain to rc=3, got {retains!r}", artifact_dir)
    assert_any(
        heap_frees(arc),
        lambda event: event.get("rc_before") == "1" and event.get("rc_after") == "0",
        "expected final free 1->0 after fanout cleanup",
        artifact_dir,
    )


def test_discarded_concat_freed(artifact_dir: Path) -> None:
    """A discarded concat result must still be freed without any heap retain."""

    _stdout, _stderr, _report, arc = run_case(
        "discarded_concat_freed",
        """
        module main;
        import std.string;

        func main() -> int {
            concat_s("a", "b");
            return 0;
        }
        """,
        artifact_dir,
    )

    frees = heap_frees(arc)
    assert_true(len(frees) >= 1, f"expected discarded temp to be freed, got {frees!r}", artifact_dir)
    assert_true(
        len([event for event in heap_retains(arc) if event.get("action") == "retain"]) == 0,
        f"unexpected heap retain for discarded temp: {heap_retains(arc)!r}",
        artifact_dir,
    )


def test_struct_static_string_field_drop(artifact_dir: Path) -> None:
    """Dropping a struct with a static string field should emit a static noop release."""

    _stdout, _stderr, _report, arc = run_case(
        "struct_static_string_field_drop",
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
        artifact_dir,
    )

    assert_any(
        arc,
        lambda event: event.get("kind") == "static"
        and event.get("op") == "release"
        and event.get("action") == "noop",
        "expected static noop release on struct drop",
        artifact_dir,
    )


def test_struct_heap_string_field_drop(artifact_dir: Path) -> None:
    """Dropping a struct with a heap string field must free the field string."""

    _stdout, _stderr, _report, arc = run_case(
        "struct_heap_string_field_drop",
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
        artifact_dir,
    )

    frees = heap_frees(arc)
    assert_true(len(frees) >= 1, f"expected heap free on struct drop, got {frees!r}", artifact_dir)
    assert_true(frees[-1].get("rc_after") == "0", f"expected terminal heap free, got {frees[-1]!r}", artifact_dir)


def test_array_nested_arc_struct_cleanup(artifact_dir: Path) -> None:
    """An array of structs with nested heap strings must clean up every element."""

    _stdout, _stderr, _report, arc = run_case(
        "array_nested_arc_struct_cleanup",
        """
        module main;
        import std.string;

        struct NestedStruct {
            t1: string;
            t2: string;
        }

        struct MyStruct1 {
            s: string;
            n: NestedStruct;
        }

        func make_box(a: string, b: string, c: string) -> MyStruct1 {
            return MyStruct1(a, NestedStruct(b, c));
        }

        func main() -> int {
            let items: MyStruct1[2] = [
                make_box(concat_s("a", "1"), concat_s("b", "1"), concat_s("c", "1")),
                make_box(concat_s("a", "2"), concat_s("b", "2"), concat_s("c", "2")),
            ];
            return 0;
        }
        """,
        artifact_dir,
    )

    frees = heap_frees(arc)
    assert_true(len(frees) >= 6, f"expected heap frees for nested ARC struct array, got {frees!r}", artifact_dir)


def test_array_nested_arc_struct_inner_arc_arrays_cleanup(artifact_dir: Path) -> None:
    """Nested ARC arrays inside structs must be cleaned up recursively."""

    _stdout, _stderr, _report, arc = run_case(
        "array_nested_arc_struct_inner_arc_arrays_cleanup",
        """
        module main;
        import std.string;

        struct NestedStruct {
            t1: string;
            t2: string;
        }

        struct NestedStruct2 {
            v1: string;
            v2: NestedStruct[10][20];
        }

        func main() -> int {
            let seed = NestedStruct(concat_s("x", "1"), concat_s("y", "1"));
            let row = NestedStruct[20](seed);
            let items: NestedStruct2[1] = [
                NestedStruct2(concat_s("z", "1"), NestedStruct[10][20](row)),
            ];
            return 0;
        }
        """,
        artifact_dir,
    )

    frees = heap_frees(arc)
    keeps = [event for event in heap_releases(arc) if event.get("action") == "keep"]
    assert_true(len(frees) >= 3, f"expected terminal frees for recursive ARC array cleanup, got {frees!r}", artifact_dir)
    assert_true(len(keeps) >= 400, f"expected releases across NestedStruct[10][20], got {keeps!r}", artifact_dir)


def test_array_arc_slot_replacement(artifact_dir: Path) -> None:
    """`arr[i] = value` must retain the incoming string before freeing the overwritten slot."""

    _stdout, _stderr, _report, arc = run_case(
        "array_arc_slot_replacement",
        """
        module main;
        import std.string;

        func main() -> int {
            let arr: string[2] = [concat_s("a", "1"), concat_s("a", "2")];
            let replacement: string = concat_s("b", "3");
            arr[0] = replacement;
            return 0;
        }
        """,
        artifact_dir,
    )

    assert_equal(
        heap_arc_sequence(arc),
        [
            ("retain", "retain", "1", "2"),
            ("release", "free", "1", "0"),
            ("release", "keep", "2", "1"),
            ("release", "free", "1", "0"),
            ("release", "free", "1", "0"),
        ],
        "array slot replacement ARC sequence mismatch",
        artifact_dir,
    )


def test_nested_array_arc_slot_replacement(artifact_dir: Path) -> None:
    """`arr[i][j] = value` must recurse through nested arrays without leaking or double-freeing."""

    _stdout, _stderr, _report, arc = run_case(
        "nested_array_arc_slot_replacement",
        """
        module main;
        import std.string;

        func main() -> int {
            let arr: string[1][2] = [[concat_s("a", "1"), concat_s("a", "2")]];
            let replacement: string = concat_s("b", "3");
            arr[0][1] = replacement;
            return 0;
        }
        """,
        artifact_dir,
    )

    assert_equal(
        heap_arc_sequence(arc),
        [
            ("retain", "retain", "1", "2"),
            ("release", "free", "1", "0"),
            ("release", "keep", "2", "1"),
            ("release", "free", "1", "0"),
            ("release", "free", "1", "0"),
        ],
        "nested array slot replacement ARC sequence mismatch",
        artifact_dir,
    )


def test_array_self_assignment_retains_before_cleanup(artifact_dir: Path) -> None:
    """`arr = arr` must retain the source array elements before releasing the overwritten owner slots."""

    _stdout, _stderr, _report, arc = run_case(
        "array_self_assignment_retains_before_cleanup",
        """
        module main;
        import std.string;

        func main() -> int {
            let arr: string[2] = [concat_s("s", "1"), concat_s("s", "2")];
            arr = arr;
            return 0;
        }
        """,
        artifact_dir,
    )

    assert_equal(
        heap_arc_sequence(arc),
        [
            ("retain", "retain", "1", "2"),
            ("retain", "retain", "1", "2"),
            ("release", "keep", "2", "1"),
            ("release", "keep", "2", "1"),
            ("release", "free", "1", "0"),
            ("release", "free", "1", "0"),
        ],
        "array self-assignment ARC sequence mismatch",
        artifact_dir,
    )


def test_array_param_return_retains(artifact_dir: Path) -> None:
    """Passing and returning a `string[2]` by value must keep both elements alive for the caller."""

    stdout, _stderr, _report, arc = run_case(
        "array_param_return_retains",
        """
        module main;
        import std.io;
        import std.string;

        func make_pair() -> string[2] {
            let pair: string[2] = [concat_s("r", "1"), concat_s("r", "2")];
            return pair;
        }

        func bounce(pair: string[2]) -> string[2] {
            return pair;
        }

        func main() -> int {
            let pair = make_pair();
            let copy = bounce(pair);
            printl_s(copy[1]);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "r2\n", "array param/return stdout mismatch", artifact_dir)

    assert_equal(
        heap_arc_sequence(arc),
        [
            ("retain", "retain", "1", "2"),
            ("retain", "retain", "1", "2"),
            ("release", "keep", "2", "1"),
            ("release", "keep", "2", "1"),
            ("release", "free", "1", "0"),
            ("release", "free", "1", "0"),
        ],
        "array param/return ARC sequence mismatch",
        artifact_dir,
    )


def test_nested_string_array_copy_retains_recursively(artifact_dir: Path) -> None:
    """Copying a `string[2][2]` must retain every nested ARC leaf exactly once."""

    _stdout, _stderr, _report, arc = run_case(
        "nested_string_array_copy_retains_recursively",
        """
        module main;
        import std.string;

        func main() -> int {
            let src: string[2][2] = [
                [concat_s("a", "1"), concat_s("a", "2")],
                [concat_s("b", "1"), concat_s("b", "2")],
            ];
            let copy: string[2][2] = src;
            return 0;
        }
        """,
        artifact_dir,
    )

    assert_heap_transition_counts(
        arc,
        expected_retains=4,
        expected_keeps=4,
        expected_frees=4,
        message="nested string array copy ARC transitions",
        artifact_dir=artifact_dir,
    )


def test_nested_struct_array_copy_retains_recursively(artifact_dir: Path) -> None:
    """Copying a `Pair[2]` must retain ARC fields recursively through struct elements."""

    _stdout, _stderr, _report, arc = run_case(
        "nested_struct_array_copy_retains_recursively",
        """
        module main;
        import std.string;

        struct Pair {
            left: string;
            right: string;
        }

        func main() -> int {
            let src: Pair[2] = [
                Pair(concat_s("a", "1"), concat_s("a", "2")),
                Pair(concat_s("b", "1"), concat_s("b", "2")),
            ];
            let copy: Pair[2] = src;
            return 0;
        }
        """,
        artifact_dir,
    )

    assert_heap_transition_counts(
        arc,
        expected_retains=4,
        expected_keeps=4,
        expected_frees=4,
        message="nested struct array copy ARC transitions",
        artifact_dir=artifact_dir,
    )


def test_nested_struct_array_param_return_retains_recursively(artifact_dir: Path) -> None:
    """Returning an owned `Pair[1][2]` by value must retain nested ARC leaves for the caller."""

    stdout, _stderr, _report, arc = run_case(
        "nested_struct_array_param_return_retains_recursively",
        """
        module main;
        import std.io;
        import std.string;

        struct Pair {
            left: string;
            right: string;
        }

        func make_pairs() -> Pair[1][2] {
            let pairs: Pair[1][2] = [[
                Pair(concat_s("a", "1"), concat_s("a", "2")),
                Pair(concat_s("b", "1"), concat_s("b", "2")),
            ]];
            return pairs;
        }

        func bounce(pairs: Pair[1][2]) -> Pair[1][2] {
            return pairs;
        }

        func main() -> int {
            let pairs = make_pairs();
            let copy = bounce(pairs);
            printl_s(copy[0][1].right);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "b2\n", "nested struct array param/return stdout mismatch", artifact_dir)

    assert_heap_transition_counts(
        arc,
        expected_retains=4,
        expected_keeps=4,
        expected_frees=4,
        message="nested struct array param/return ARC transitions",
        artifact_dir=artifact_dir,
    )


def test_enum_string_variant_cleanup(artifact_dir: Path) -> None:
    """A heap string inside an enum variant must be freed at scope exit."""

    _stdout, _stderr, _report, arc = run_case(
        "enum_string_variant_cleanup",
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
        artifact_dir,
    )

    assert_true(len(heap_frees(arc)) >= 1, f"expected heap free for enum variant, got {arc!r}", artifact_dir)


def test_optional_string_cleanup(artifact_dir: Path) -> None:
    """A heap string stored in `string?` must be freed at scope exit."""

    _stdout, _stderr, _report, arc = run_case(
        "optional_string_cleanup",
        """
        module main;
        import std.string;

        func main() -> int {
            let v: string? = concat_s("o", "pt") as string?;
            return 0;
        }
        """,
        artifact_dir,
    )

    assert_true(len(heap_frees(arc)) >= 1, f"expected heap free for optional string, got {arc!r}", artifact_dir)


def test_case_scrutinee_unwrap_retains(artifact_dir: Path) -> None:
    """`case (opt as string)` must retain `_scrutinee` before later cleanup."""

    _stdout, _stderr, _report, arc = run_case(
        "case_scrutinee_unwrap_retains",
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
        artifact_dir,
    )

    heap = heap_events(arc)
    assert_equal(
        [(e.get("op"), e.get("action"), e.get("rc_before"), e.get("rc_after")) for e in heap],
        [
            ("retain", "retain", "1", "2"),
            ("release", "keep", "2", "1"),
            ("release", "free", "1", "0"),
        ],
        "case scrutinee ARC sequence mismatch",
        artifact_dir,
    )


def test_match_scrutinee_enum_unwrap_retains(artifact_dir: Path) -> None:
    """`match (value? as Value)` must retain the string-bearing scrutinee copy."""

    _stdout, _stderr, _report, arc = run_case(
        "match_scrutinee_enum_unwrap_retains",
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
        artifact_dir,
    )

    heap = heap_events(arc)
    assert_equal(
        [(e.get("op"), e.get("action"), e.get("rc_before"), e.get("rc_after")) for e in heap],
        [
            ("retain", "retain", "1", "2"),
            ("retain", "retain", "2", "3"),
            ("release", "keep", "3", "2"),
            ("release", "keep", "2", "1"),
            ("release", "free", "1", "0"),
        ],
        "enum scrutinee ARC sequence mismatch",
        artifact_dir,
    )


def test_null_optional_no_heap_release(artifact_dir: Path) -> None:
    """A null optional string must not emit heap release events."""

    _stdout, _stderr, _report, arc = run_case(
        "null_optional_no_heap_release",
        """
        module main;

        func main() -> int {
            let v: string? = null;
            return 0;
        }
        """,
        artifact_dir,
    )

    assert_true(
        len(heap_releases(arc)) == 0,
        f"unexpected heap release for null optional: {heap_releases(arc)!r}",
        artifact_dir,
    )


def test_borrowed_param_return_retains(artifact_dir: Path) -> None:
    """Returning a borrowed param must retain it for the caller."""

    stdout, _stderr, _report, arc = run_case(
        "borrowed_param_return_retains",
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
        artifact_dir,
    )
    assert_equal(stdout, "id\n", "borrowed return stdout mismatch", artifact_dir)

    retains = heap_retains(arc)
    assert_any(
        retains,
        lambda event: event.get("action") == "retain"
        and event.get("rc_before") == "1"
        and event.get("rc_after") == "2",
        "expected borrowed return retain 1->2",
        artifact_dir,
    )

    releases = heap_releases(arc)
    assert_any(releases, lambda event: event.get("action") == "keep", "expected one keep release", artifact_dir)
    assert_any(releases, lambda event: event.get("action") == "free", "expected one terminal free", artifact_dir)


def test_borrowed_param_return_with_cleanup_retains(artifact_dir: Path) -> None:
    """Returning a borrowed param while cleaning a local heap string must still retain correctly."""

    stdout, _stderr, _report, arc = run_case(
        "borrowed_param_return_with_cleanup_retains",
        """
        module main;
        import std.io;
        import std.string;

        func id_with_local(s: string) -> string {
            let tmp: string = concat_s("x", "y");
            return s;
        }

        func main() -> int {
            let a: string = concat_s("he", "llo");
            let x: string = id_with_local(a);
            printl_s(x);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "hello\n", "borrowed return with cleanup stdout mismatch", artifact_dir)

    retains = heap_retains(arc)
    assert_any(
        retains,
        lambda event: event.get("action") == "retain"
        and event.get("rc_before") == "1"
        and event.get("rc_after") == "2",
        "expected borrowed return retain 1->2 with local cleanup",
        artifact_dir,
    )
    assert_true(len(heap_frees(arc)) >= 2, f"expected frees for temp and returned value, got {heap_frees(arc)!r}", artifact_dir)


def test_pointer_index_arc_slot_replacement(artifact_dir: Path) -> None:
    """`ptr[i] = value` over ARC data must retain the incoming value before releasing the old slot."""

    _stdout, _stderr, _report, arc = run_case(
        "pointer_index_arc_slot_replacement",
        """
        module main;
        import std.string;

        unsafe func store(slot: string*, value: string) {
            slot[0] = value;
        }

        func main() -> int {
            let slot: string* = new string();
            let first: string = concat_s("a", "1");
            let second: string = concat_s("b", "2");
            store(slot, first);
            store(slot, second);
            drop slot;
            return 0;
        }
        """,
        artifact_dir,
    )

    heap = heap_events(arc)
    second_retain_index = -1
    overwritten_release_index = -1
    for index, event in enumerate(heap):
        if (
            second_retain_index < 0
            and event.get("op") == "retain"
            and event.get("action") == "retain"
            and event.get("rc_before") == "1"
            and event.get("rc_after") == "2"
        ):
            second_retain_index = index
            continue
        if (
            second_retain_index >= 0
            and event.get("op") == "release"
            and event.get("action") == "keep"
            and event.get("rc_before") == "2"
            and event.get("rc_after") == "1"
        ):
            overwritten_release_index = index
            break

    assert_true(second_retain_index >= 0, f"expected retain of incoming indexed value, got {heap!r}", artifact_dir)
    assert_true(
        overwritten_release_index >= 0,
        f"expected release of overwritten indexed slot, got {heap!r}",
        artifact_dir,
    )
    assert_true(
        second_retain_index < overwritten_release_index,
        f"expected incoming retain before overwritten-slot release, got {heap!r}",
        artifact_dir,
    )


def test_loop_continue_cleanup(artifact_dir: Path) -> None:
    """Continue paths should release exactly the ARC locals acquired on those paths."""

    stdout, _stderr, _report, arc = run_case(
        "loop_continue_cleanup",
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
        artifact_dir,
    )
    assert_equal(stdout, "", "loop continue case should not print", artifact_dir)

    frees = heap_frees(arc)
    assert_true(
        len(frees) >= 3,
        f"expected frees for two `a` values and one `b` value, got {frees!r}",
        artifact_dir,
    )
    for event in frees:
        assert_true(
            event.get("rc_before") == "1" and event.get("rc_after") == "0",
            f"expected rc 1->0 free, got {event!r}",
            artifact_dir,
        )


def test_loop_break_cleanup(artifact_dir: Path) -> None:
    """A break after one ARC acquisition must free that local."""

    stdout, _stderr, _report, arc = run_case(
        "loop_break_cleanup",
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
        artifact_dir,
    )
    assert_equal(stdout, "", "loop break case should not print", artifact_dir)

    frees = heap_frees(arc)
    assert_true(len(frees) >= 1, f"expected at least one heap free, got {frees!r}", artifact_dir)
    for event in frees:
        assert_true(
            event.get("rc_before") == "1" and event.get("rc_after") == "0",
            f"expected rc 1->0 free, got {event!r}",
            artifact_dir,
        )


def test_loop_return_cleanup(artifact_dir: Path) -> None:
    """A return after one ARC acquisition in a loop must free that local before returning."""

    stdout, _stderr, _report, arc = run_case(
        "loop_return_cleanup",
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
        artifact_dir,
    )
    assert_equal(stdout, "", "loop return case should not print", artifact_dir)

    frees = heap_frees(arc)
    assert_true(len(frees) >= 1, f"expected at least one heap free, got {frees!r}", artifact_dir)
    for event in frees:
        assert_true(
            event.get("rc_before") == "1" and event.get("rc_after") == "0",
            f"expected rc 1->0 free, got {event!r}",
            artifact_dir,
        )


def test_array_loop_continue_cleanup(artifact_dir: Path) -> None:
    """Continuing past an array local with ARC elements must clean both elements before the next iteration."""

    _stdout, _stderr, _report, arc = run_case(
        "array_loop_continue_cleanup",
        """
        module main;
        import std.string;

        func main() -> int {
            for (let i = 0; i < 1; i = i + 1) {
                let arr: string[2] = [concat_s("x", "1"), concat_s("y", "2")];
                continue;
            }
            return 0;
        }
        """,
        artifact_dir,
    )

    assert_equal(
        heap_arc_sequence(arc),
        [
            ("release", "free", "1", "0"),
            ("release", "free", "1", "0"),
        ],
        "array loop continue ARC sequence mismatch",
        artifact_dir,
    )


def test_array_loop_break_cleanup(artifact_dir: Path) -> None:
    """Breaking past an array local with ARC elements must clean both elements before leaving the loop."""

    _stdout, _stderr, _report, arc = run_case(
        "array_loop_break_cleanup",
        """
        module main;
        import std.string;

        func main() -> int {
            for (let i = 0; i < 1; i = i + 1) {
                let arr: string[2] = [concat_s("x", "1"), concat_s("y", "2")];
                break;
            }
            return 0;
        }
        """,
        artifact_dir,
    )

    assert_equal(
        heap_arc_sequence(arc),
        [
            ("release", "free", "1", "0"),
            ("release", "free", "1", "0"),
        ],
        "array loop break ARC sequence mismatch",
        artifact_dir,
    )


def test_array_loop_return_cleanup(artifact_dir: Path) -> None:
    """Returning past an array local with ARC elements must clean both elements before leaving the function."""

    _stdout, _stderr, _report, arc = run_case(
        "array_loop_return_cleanup",
        """
        module main;
        import std.string;

        func main() -> int {
            for (let i = 0; i < 1; i = i + 1) {
                let arr: string[2] = [concat_s("x", "1"), concat_s("y", "2")];
                return 0;
            }
            return 0;
        }
        """,
        artifact_dir,
    )

    assert_equal(
        heap_arc_sequence(arc),
        [
            ("release", "free", "1", "0"),
            ("release", "free", "1", "0"),
        ],
        "array loop return ARC sequence mismatch",
        artifact_dir,
    )


def test_optional_unwrap_return_retains(artifact_dir: Path) -> None:
    """Returning `opt as string` from a local optional must retain before cleanup."""

    stdout, _stderr, _report, arc = run_case(
        "optional_unwrap_return_retains",
        """
        module main;
        import std.io;
        import std.string;

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
        artifact_dir,
    )
    assert_equal(stdout, "pq\n", "optional unwrap return stdout mismatch", artifact_dir)

    retains = heap_retains(arc)
    assert_any(
        retains,
        lambda event: event.get("action") == "retain"
        and event.get("rc_before") == "1"
        and event.get("rc_after") == "2",
        "expected retain 1->2 before optional cleanup",
        artifact_dir,
    )


def test_optional_unwrap_into_vector_retains(artifact_dir: Path) -> None:
    """`sv_push(v, opt as string)` must retain before optional cleanup and keep the vector entry valid."""

    stdout, _stderr, _report, arc = run_case(
        "optional_unwrap_into_vector_retains",
        """
        module main;
        import std.io;
        import std.string;
        import std.vector;

        func build() -> StringVector* {
            let v = sv_create(0);
            let opt: string? = concat_s("c", "d") as string?;
            sv_push(v, opt as string);
            return v;
        }

        func main() -> int {
            let v = build();
            let s = sv_get(v, 0);
            printl_s(s);
            sv_free(v);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "cd\n", "optional unwrap into vector stdout mismatch", artifact_dir)

    assert_any(
        heap_retains(arc),
        lambda event: event.get("action") == "retain"
        and event.get("rc_before") == "1"
        and event.get("rc_after") == "2",
        "expected retain 1->2 before optional/vector owner transfer",
        artifact_dir,
    )
    assert_true(len(heap_frees(arc)) >= 1, f"expected at least one heap free, got {heap_frees(arc)!r}", artifact_dir)


def test_try_cleanup_on_early_return(artifact_dir: Path) -> None:
    """A failing `?` must clean up prior ARC locals before returning null."""

    stdout, _stderr, _report, arc = run_case(
        "try_cleanup_on_early_return",
        """
        module main;
        import std.io;
        import std.string;

        func may_fail() -> int? {
            return null;
        }

        func helper() -> int? {
            let s: string = concat_s("h", "i");
            let x: int = may_fail()?;
            printl_s("inside");
            return x as int?;
        }

        func main() -> int {
            let r: int? = helper();
            if (r == null) {
                printl_s("null");
                return 0;
            }
            return 1;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "null\n", "try cleanup stdout mismatch", artifact_dir)

    frees = heap_frees(arc)
    assert_true(len(frees) >= 1, f"expected at least one heap free, got {frees!r}", artifact_dir)
    assert_any(
        frees,
        lambda event: event.get("rc_before") == "1" and event.get("rc_after") == "0",
        "expected rc 1->0 free for prior ARC local on try failure",
        artifact_dir,
    )


def test_nested_temp_cleanup(artifact_dir: Path) -> None:
    """Nested concat temps must free both intermediaries and final values."""

    stdout, _stderr, _report, arc = run_case(
        "nested_temp_cleanup",
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
        artifact_dir,
    )
    assert_equal(stdout, "abc\nmiddle\n", "nested temp stdout mismatch", artifact_dir)

    frees = heap_frees(arc)
    assert_true(
        len(frees) >= 4,
        f"expected >=4 heap frees (2 calls x intermediary+final), got {frees!r}",
        artifact_dir,
    )
    for event in frees:
        assert_true(
            event.get("rc_before") == "1" and event.get("rc_after") == "0",
            f"expected rc 1->0 free, got {event!r}",
            artifact_dir,
        )


def test_nested_concat_intermediary_freed(artifact_dir: Path) -> None:
    """A direct nested `concat_s` call must free both the intermediary and final result."""

    stdout, _stderr, _report, arc = run_case(
        "nested_concat_intermediary_freed",
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
        artifact_dir,
    )
    assert_equal(stdout, "abc\n", "nested concat stdout mismatch", artifact_dir)

    frees = heap_frees(arc)
    assert_true(
        len(frees) >= 2,
        f"expected intermediary and final frees for nested concat, got {frees!r}",
        artifact_dir,
    )
    for event in frees:
        assert_true(
            event.get("rc_before") == "1" and event.get("rc_after") == "0",
            f"expected rc 1->0 free, got {event!r}",
            artifact_dir,
        )


def test_control_flow_condition_temp_cleanup(artifact_dir: Path) -> None:
    """Dynamic-string temps in `if` and `while` headers must stay leak-free."""

    stdout, _stderr, _report, arc = run_case(
        "control_flow_condition_temp_cleanup",
        """
        module main;
        import std.io;
        import std.string;

        func tick(flag: bool) -> string {
            if (flag) {
                return concat_s("x", "");
            }
            return concat_s("", "");
        }

        func main() -> int {
            if (false && len_s(tick(true)) > 0) {
                printl_i(9);
            }

            let i: int = 0;
            while (i < 3 && len_s(tick(i == 0)) > 0) {
                i = i + 1;
            }

            printl_i(i);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "1\n", "condition temp cleanup stdout mismatch", artifact_dir)

    frees = heap_frees(arc)
    assert_true(len(frees) >= 1, f"expected condition heap values to be freed, got {frees!r}", artifact_dir)
    rc_values = [int(event["rc_after"]) for event in heap_events(arc) if event.get("rc_after", "").isdigit()]
    assert_true(rc_values != [], "expected heap ARC events for condition temps", artifact_dir)
    assert_true(min(rc_values) >= 0, f"unexpected negative heap refcounts: {rc_values!r}", artifact_dir)
    assert_true(max(rc_values) <= 2, f"unexpected heap refcount growth: {rc_values!r}", artifact_dir)


def test_logical_expression_temp_cleanup(artifact_dir: Path) -> None:
    """Value-context logical expressions must short-circuit and free only taken RHS temps."""

    stdout, _stderr, _report, arc = run_case(
        "logical_expression_temp_cleanup",
        """
        module main;
        import std.io;
        import std.string;

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

            printl_i(total);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "3\n", "logical temp cleanup stdout mismatch", artifact_dir)

    frees = heap_frees(arc)
    assert_true(len(frees) == 2, f"expected frees only for taken RHS branches, got {frees!r}", artifact_dir)
    rc_values = [int(event["rc_after"]) for event in heap_events(arc) if event.get("rc_after", "").isdigit()]
    assert_true(rc_values != [], "expected heap ARC events for logical-expression temps", artifact_dir)
    assert_true(min(rc_values) >= 0, f"unexpected negative heap refcounts: {rc_values!r}", artifact_dir)
    assert_true(max(rc_values) <= 2, f"unexpected heap refcount growth: {rc_values!r}", artifact_dir)


def test_param_reassign_twice_no_double_free(artifact_dir: Path) -> None:
    """Repeated reassignment of a borrowed string param must stay leak-free and avoid double-free behavior."""

    stdout, _stderr, _report, arc = run_case(
        "param_reassign_twice_no_double_free",
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
            let input = concat_s("o", "ld");
            f(input);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "two2\n", "param reassignment stdout mismatch", artifact_dir)
    assert_true(len(heap_frees(arc)) >= 3, f"expected frees for input and reassigned values, got {heap_frees(arc)!r}", artifact_dir)


def test_param_reassign_conditional_branch_safe(artifact_dir: Path) -> None:
    """One-branch reassignment of a borrowed string param must not double-free the caller's value."""

    stdout, _stderr, _report, arc = run_case(
        "param_reassign_conditional_branch_safe",
        """
        module main;
        import std.io;
        import std.string;

        func f(s: string, flag: bool) {
            if (flag) {
                s = concat_s("new", "");
            }
            printl_s(s);
        }

        func main() -> int {
            let a = concat_s("keep", "");
            f(a, false);
            f(a, true);
            printl_s(a);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "keep\nnew\nkeep\n", "conditional param reassign stdout mismatch", artifact_dir)

    frees = heap_frees(arc)
    for event in frees:
        assert_true(
            event.get("rc_before") == "1" and event.get("rc_after") == "0",
            f"expected rc 1->0 free, got {event!r}",
            artifact_dir,
        )


def test_param_reassign_loop_carried_safe(artifact_dir: Path) -> None:
    """A borrowed string param reassigned inside a loop body must stay leak-free across iterations."""

    stdout, _stderr, _report, arc = run_case(
        "param_reassign_loop_carried_safe",
        """
        module main;
        import std.io;
        import std.string;

        func f(s: string) {
            for (let i = 0; i < 3; i = i + 1) {
                s = concat_s("i", "");
            }
            printl_s(s);
        }

        func main() -> int {
            let a = concat_s("start", "");
            f(a);
            printl_s(a);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "i\nstart\n", "loop-carried param reassign stdout mismatch", artifact_dir)

    frees = heap_frees(arc)
    for event in frees:
        assert_true(
            event.get("rc_before") == "1" and event.get("rc_after") == "0",
            f"expected rc 1->0 free, got {event!r}",
            artifact_dir,
        )


def test_param_reassign_for_update_safe(artifact_dir: Path) -> None:
    """A borrowed string param reassigned in a `for` update clause must stay leak-free."""

    stdout, _stderr, _report, arc = run_case(
        "param_reassign_for_update_safe",
        """
        module main;
        import std.io;
        import std.string;

        func f(s: string) {
            let i = 0;
            for (; i < 2; s = concat_s("up", "date")) {
                i = i + 1;
            }
            printl_s(s);
        }

        func main() -> int {
            let a = concat_s("old", "");
            f(a);
            printl_s(a);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "update\nold\n", "for-update param reassign stdout mismatch", artifact_dir)

    frees = heap_frees(arc)
    for event in frees:
        assert_true(
            event.get("rc_before") == "1" and event.get("rc_after") == "0",
            f"expected rc 1->0 free, got {event!r}",
            artifact_dir,
        )


def test_param_reassign_with_header_and_cleanup_safe(artifact_dir: Path) -> None:
    """A borrowed string param reassigned from `with` header init/cleanup must stay leak-free."""

    stdout, _stderr, _report, arc = run_case(
        "param_reassign_with_header_and_cleanup_safe",
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
            let a = concat_s("old", "");
            f(a);
            printl_s(a);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "header\ncleanup\nold\n", "with-header param reassign stdout mismatch", artifact_dir)

    frees = heap_frees(arc)
    for event in frees:
        assert_true(
            event.get("rc_before") == "1" and event.get("rc_after") == "0",
            f"expected rc 1->0 free, got {event!r}",
            artifact_dir,
        )


def test_leak_freedom_balance(artifact_dir: Path) -> None:
    """Every unique heap pointer in one mixed ARC program must end in one terminal free."""

    stdout, _stderr, _report, arc = run_case(
        "leak_freedom_balance",
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
        artifact_dir,
    )
    assert_equal(stdout, "hello\n", "leak balance stdout mismatch", artifact_dir)

    free_ptrs = [event.get("ptr") for event in heap_frees(arc) if event.get("ptr") is not None]
    assert_true(len(free_ptrs) >= 2, f"expected at least two freed heap pointers, got {free_ptrs!r}", artifact_dir)
    assert_equal(
        len(set(free_ptrs)),
        len(free_ptrs),
        "expected one terminal free per heap pointer",
        artifact_dir,
    )


def test_with_early_return_cleanup_order(artifact_dir: Path) -> None:
    """Nested `with` cleanup should run inner before outer on early return."""

    stdout, _stderr, _report, _arc = run_case(
        "with_early_return_cleanup_order",
        """
        module main;
        import std.io;

        func helper() -> int {
            with (let x: int = 0 => printl_s("outer")) {
                with (let y: int = 0 => printl_s("inner")) {
                    printl_s("body");
                    return 0;
                }
            }
            return 1;
        }

        func main() -> int {
            return helper();
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "body\ninner\nouter\n", "with cleanup order stdout mismatch", artifact_dir)


def test_with_inline_return_header_runs_cleanup(artifact_dir: Path) -> None:
    """A committed return from an inline with header must run that item's cleanup."""

    stdout, _stderr, _report, _arc = run_case(
        "with_inline_return_header_runs_cleanup",
        """
        module main;
        import std.io;

        func helper() -> int {
            with (return 42 => printl_s("leaving")) {
            }
            return 0;
        }

        func main() -> int {
            printl_i(helper());
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "leaving\n42\n", "inline return header cleanup stdout mismatch", artifact_dir)


def test_with_inline_return_header_evaluates_value_before_cleanup(artifact_dir: Path) -> None:
    """A return header value must be evaluated before the paired inline cleanup."""

    stdout, _stderr, _report, _arc = run_case(
        "with_inline_return_header_evaluates_value_before_cleanup",
        """
        module main;
        import std.io;

        func value() -> int {
            printl_s("value");
            return 3;
        }

        func helper() -> int {
            with (return value() => printl_s("cleanup")) {
            }
            return 0;
        }

        func main() -> int {
            printl_i(helper());
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "value\ncleanup\n3\n", "inline return header value order mismatch", artifact_dir)


def test_with_inline_return_header_cleanup_return_overrides(artifact_dir: Path) -> None:
    """A return in inline cleanup must override a pending with-header return."""

    stdout, _stderr, _report, _arc = run_case(
        "with_inline_return_header_cleanup_return_overrides",
        """
        module main;
        import std.io;

        func helper() -> int {
            with (return 42 => return 7) {
            }
            return 0;
        }

        func main() -> int {
            printl_i(helper());
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "7\n", "inline cleanup return precedence mismatch", artifact_dir)


def test_with_inline_return_header_preserves_lifo_order(artifact_dir: Path) -> None:
    """Inline cleanup must remain LIFO when a later header item returns."""

    stdout, _stderr, _report, _arc = run_case(
        "with_inline_return_header_preserves_lifo_order",
        """
        module main;
        import std.io;

        func helper() -> int {
            with (let a: int = 1 => printl_s("a"),
                  return 0 => printl_s("b")) {
            }
            return 1;
        }

        func main() -> int {
            printl_i(helper());
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "b\na\n0\n", "inline return header LIFO cleanup order mismatch", artifact_dir)


def test_with_inline_break_header_runs_cleanup(artifact_dir: Path) -> None:
    """A committed break from an inline with header must run that item's cleanup."""

    stdout, _stderr, _report, _arc = run_case(
        "with_inline_break_header_runs_cleanup",
        """
        module main;
        import std.io;

        func main() -> int {
            let result: int = 1;
            while (true) {
                with (break => result = 0) {
                }
            }
            printl_i(result);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "0\n", "inline break header cleanup stdout mismatch", artifact_dir)


def test_with_inline_continue_header_runs_cleanup(artifact_dir: Path) -> None:
    """A committed continue from an inline with header must run that item's cleanup."""

    stdout, _stderr, _report, _arc = run_case(
        "with_inline_continue_header_runs_cleanup",
        """
        module main;
        import std.io;

        func main() -> int {
            let result: int = 1;
            let count: int = 0;
            while (count < 1) {
                count = count + 1;
                with (continue => result = 0) {
                }
                result = 2;
            }
            printl_i(result);
            return 0;
        }
        """,
        artifact_dir,
    )
    assert_equal(stdout, "0\n", "inline continue header cleanup stdout mismatch", artifact_dir)


def test_with_header_try_failure_runs_prior_inline_cleanup(artifact_dir: Path) -> None:
    """A later header `?` failure must run prior successful inline cleanup and skip the body."""

    stdout, _stderr, _report, _arc = run_case(
        "with_header_try_failure_runs_prior_inline_cleanup",
        """
        module main;
        import std.io;

        func ok() -> int? {
            return 1 as int?;
        }

        func fail() -> int? {
            return null;
        }

        func helper() -> int? {
            with (let q: int = ok()? => printl_s("cleanup_q"),
                  let p: int = fail()? => printl_s("cleanup_p")) {
                printl_s("inside");
            }
            return 0 as int?;
        }

        func main() -> int {
            let r: int? = helper();
            if (r == null) {
                return 0;
            }
            return 1;
        }
        """,
        artifact_dir,
    )
    assert_true("cleanup_q\n" in stdout, "expected prior successful header cleanup to run", artifact_dir)
    assert_true("cleanup_p" not in stdout, "failed header item cleanup must not run", artifact_dir)
    assert_true("inside" not in stdout, "with body should not execute after header `?` failure", artifact_dir)


def test_with_cleanup_block_header_try_failure_nullable_vars(artifact_dir: Path) -> None:
    """Cleanup blocks may run on header `?` failure when referenced header vars are nullable."""

    stdout, _stderr, _report, _arc = run_case(
        "with_cleanup_block_header_try_failure_nullable_vars",
        """
        module main;
        import std.io;

        func ok() -> int? {
            return 1 as int?;
        }

        func fail() -> int? {
            return null;
        }

        func helper() -> int? {
            with (let q: int? = ok()?,
                  let p: int? = fail()?) {
                printl_s("inside");
            } cleanup {
                if (q != null) { printl_s("cleanup_q"); }
                if (p != null) { printl_s("cleanup_p"); }
            }
            return 0 as int?;
        }

        func main() -> int {
            let r: int? = helper();
            if (r == null) {
                return 0;
            }
            return 1;
        }
        """,
        artifact_dir,
    )
    assert_true("cleanup_q\n" in stdout, "expected nullable cleanup header value to be visible", artifact_dir)
    assert_true("cleanup_p" not in stdout, "failed nullable header value should remain null", artifact_dir)
    assert_true("inside" not in stdout, "with body should not execute after nullable header `?` failure", artifact_dir)


def main() -> int:
    """Program entrypoint."""

    artifact_dir = Path(tempfile.mkdtemp(prefix="l1_stage1_arc_trace_regression."))
    keep_artifacts = os.environ.get("KEEP_ARTIFACTS", "0") == "1"

    checks = [
        test_static_string_noop,
        test_heap_string_lifecycle,
        test_string_copy_retain_and_release,
        test_fanout_three_references,
        test_discarded_concat_freed,
        test_struct_static_string_field_drop,
        test_struct_heap_string_field_drop,
        test_array_nested_arc_struct_cleanup,
        test_array_nested_arc_struct_inner_arc_arrays_cleanup,
        test_array_arc_slot_replacement,
        test_nested_array_arc_slot_replacement,
        test_array_self_assignment_retains_before_cleanup,
        test_array_param_return_retains,
        test_nested_string_array_copy_retains_recursively,
        test_nested_struct_array_copy_retains_recursively,
        test_nested_struct_array_param_return_retains_recursively,
        test_enum_string_variant_cleanup,
        test_optional_string_cleanup,
        test_case_scrutinee_unwrap_retains,
        test_match_scrutinee_enum_unwrap_retains,
        test_null_optional_no_heap_release,
        test_borrowed_param_return_retains,
        test_borrowed_param_return_with_cleanup_retains,
        test_pointer_index_arc_slot_replacement,
        test_loop_continue_cleanup,
        test_loop_break_cleanup,
        test_loop_return_cleanup,
        test_array_loop_continue_cleanup,
        test_array_loop_break_cleanup,
        test_array_loop_return_cleanup,
        test_optional_unwrap_return_retains,
        test_optional_unwrap_into_vector_retains,
        test_try_cleanup_on_early_return,
        test_nested_temp_cleanup,
        test_nested_concat_intermediary_freed,
        test_control_flow_condition_temp_cleanup,
        test_logical_expression_temp_cleanup,
        test_param_reassign_twice_no_double_free,
        test_param_reassign_conditional_branch_safe,
        test_param_reassign_loop_carried_safe,
        test_param_reassign_for_update_safe,
        test_param_reassign_with_header_and_cleanup_safe,
        test_leak_freedom_balance,
        test_with_early_return_cleanup_order,
        test_with_inline_return_header_runs_cleanup,
        test_with_inline_return_header_evaluates_value_before_cleanup,
        test_with_inline_return_header_cleanup_return_overrides,
        test_with_inline_return_header_preserves_lifo_order,
        test_with_inline_break_header_runs_cleanup,
        test_with_inline_continue_header_runs_cleanup,
        test_with_header_try_failure_runs_prior_inline_cleanup,
        test_with_cleanup_block_header_try_failure_nullable_vars,
    ]

    try:
        for check in checks:
            check(artifact_dir)
        print("l1c_stage1_arc_trace_regression_test: PASS")
        return 0
    except ArcTraceFailure as exc:
        keep_artifacts = True
        lines = str(exc).splitlines()
        if lines:
            print(f"l1c_stage1_arc_trace_regression_test: FAIL: {lines[0]}")
        for line in lines[1:]:
            print(f"l1c_stage1_arc_trace_regression_test: {line}")
        return 1
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
