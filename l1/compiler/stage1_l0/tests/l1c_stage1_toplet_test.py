#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Stage 1 regressions for top-level let behavior."""

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


class TopletFailure(RuntimeError):
    """Raised when one Stage 1 toplet regression fails."""


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

    raise TopletFailure(f"{message}\nartifacts={artifact_dir}")


def assert_true(condition: bool, message: str, artifact_dir: Path) -> None:
    """Abort with artifacts when `condition` is false."""

    if not condition:
        fail(message, artifact_dir)


def write_case_source(artifact_dir: Path, case_name: str, source: str) -> Path:
    """Write one temporary L1 source file for one regression case."""

    case_dir = artifact_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    source_path = case_dir / "main.l1"
    source_path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return source_path


def run_compiler(
    case_name: str,
    source: str,
    artifact_dir: Path,
    *args: str,
) -> tuple[int, str, str]:
    """Run the Stage 1 compiler for one temporary case."""

    compiler = stage1_compiler()
    assert_true(compiler.is_file(), f"missing repo-local Stage 1 compiler: {compiler}", artifact_dir)

    source_path = write_case_source(artifact_dir, case_name, source)
    stdout_path = artifact_dir / f"{case_name}.stdout.log"
    stderr_path = artifact_dir / f"{case_name}.stderr.log"

    run_result = subprocess.run(
        [str(compiler), *args, str(source_path)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_path.write_bytes(run_result.stdout if run_result.stdout is not None else b"")
    stderr_path.write_bytes(run_result.stderr if run_result.stderr is not None else b"")
    return run_result.returncode, read_text(stdout_path), read_text(stderr_path)


def run_ok(case_name: str, expected_rc: int, source: str, artifact_dir: Path) -> None:
    """Run one success case and assert the program exit code."""

    actual_rc, _stdout, stderr = run_compiler(case_name, source, artifact_dir, "--run")
    if actual_rc != expected_rc:
        fail(f"{case_name} expected exit code {expected_rc}, got {actual_rc}\nstderr={stderr}", artifact_dir)


def run_check_error(case_name: str, expected_code: str, source: str, artifact_dir: Path) -> None:
    """Run one type-checking failure case and assert the diagnostic code."""

    actual_rc, _stdout, stderr = run_compiler(case_name, source, artifact_dir, "--check")
    if actual_rc == 0:
        fail(f"{case_name} expected check failure with {expected_code}", artifact_dir)
    if expected_code not in stderr:
        fail(f"{case_name} missing expected diagnostic {expected_code}\nstderr={stderr}", artifact_dir)


def run_gen(case_name: str, source: str, artifact_dir: Path) -> str:
    """Generate C for one case and return the output."""

    actual_rc, stdout, stderr = run_compiler(case_name, source, artifact_dir, "--gen")
    if actual_rc != 0:
        fail(f"{case_name} expected code generation success\nstderr={stderr}", artifact_dir)
    return stdout


def run_trace_ok(case_name: str, expected_rc: int, source: str, artifact_dir: Path) -> list[dict[str, str]]:
    """Run one traced success case and assert leak-free ARC output."""

    source_path = write_case_source(artifact_dir, case_name, source)
    stdout_path = artifact_dir / f"{case_name}.stdout.log"
    stderr_path = artifact_dir / f"{case_name}.stderr.log"
    report_path = artifact_dir / f"{case_name}.trace_report.txt"
    compiler = stage1_compiler()

    run_result = subprocess.run(
        [str(compiler), "--run", "--trace-memory", "--trace-arc", str(source_path)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_path.write_bytes(run_result.stdout if run_result.stdout is not None else b"")
    stderr_path.write_bytes(run_result.stderr if run_result.stderr is not None else b"")
    if run_result.returncode != expected_rc:
        fail(f"{case_name} expected traced exit code {expected_rc}, got {run_result.returncode}", artifact_dir)

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
    assert_true("leaked_object_ptrs=0" in report_text, f"{case_name} trace report recorded object leaks", artifact_dir)
    assert_true("leaked_string_ptrs=0" in report_text, f"{case_name} trace report recorded string leaks", artifact_dir)
    return parse_arc_lines(read_text(stderr_path))


def test_execute_toplet_case_extended(artifact_dir: Path) -> None:
    """End-to-end integration test containing valid floating-point cases, unsigned comparisons, and a warning-checked out-of-bounds arm."""
    run_ok(
        "execute_toplet_case_extended",
        3,
        """
        module main;

        func check_float(f: float) -> int {
            case (f) {
                1.0 => { return 1; }
                -2.5 => { return 2; }
                _ => { return 3; }
            }
        }

        func check_uint(u: uint) -> int {
            case (u) {
                0 => { return 0; }
                -1 => { return 1; }
                _ => { return 2; }
            }
        }

        func check_ulong(u: ulong) -> int {
            case (u) {
                -4294967296 => { return 1; }
                _ => { return 2; }
            }
        }

        func main() -> int {
            let rc1 = check_float(-2.5f); // 2
            let rc2 = check_uint(4294967295); // 2
            let rc3 = check_ulong(18446744069414584320); // 2
            return rc1 + rc2 + rc3 - 3; // 2 + 2 + 2 - 3 = 3
        }
        """,
        artifact_dir,
    )


def test_reject_toplet_case_real_integer_arm(artifact_dir: Path) -> None:
    """A real scrutinee must follow existing real equality and reject integer arm literals."""
    run_check_error(
        "reject_toplet_case_real_integer_arm",
        "TYP-0107",
        """
        module main;

        func check_double(d: double) -> int {
            case (d) {
                1 => { return 1; }
                _ => { return 2; }
            }
        }

        func main() -> int {
            return check_double(1.0);
        }
        """,
        artifact_dir,
    )


def test_generate_toplet_case_always_false_unsigned(artifact_dir: Path) -> None:
    """Always-false unsigned case arms must not lower as wrapping C labels or comparisons."""
    c_code = run_gen(
        "generate_toplet_case_always_false_unsigned",
        """
        module main;

        func check_uint(u: uint) -> int {
            case (u) {
                -1 => { return 1; }
                _ => { return 2; }
            }
        }

        func check_ulong(u: ulong) -> int {
            case (u) {
                -4294967296 => { return 3; }
                _ => { return 4; }
            }
        }

        func main() -> int {
            return check_uint(0) + check_ulong(0);
        }
        """,
        artifact_dir,
    )
    assert_true("case -1" not in c_code, "always-false uint arm must not lower as a switch label", artifact_dir)
    assert_true(
        "_scrutinee == -4294967296" not in c_code,
        "always-false ulong arm must not compare against a negative literal",
        artifact_dir,
    )
    assert_true("if (false)" in c_code, "always-false unsigned arms should lower to a safe false condition", artifact_dir)


def test_execute_toplet_primitives(artifact_dir: Path) -> None:
    """Mirror Stage 1 primitive top-level execution coverage."""

    run_ok(
        "execute_toplet_primitives",
        42,
        """
        module main;

        let result: int = 42;

        func main() -> int {
            return result;
        }
        """,
        artifact_dir,
    )


def test_execute_const_referenced_array_bound(artifact_dir: Path) -> None:
    """Scalar const references must lower before use as resolved array bounds."""

    source = """
        module main;

        const Z: ulong = 25;
        const I: int = Z as int;
        const J: int = (I + 5) / 3;
        const messages: string[I] = ["hello"];

        func classify(value: int) -> int {
            case (value) {
                I => { return 1; }
                J => { return 2; }
                _ => { return 0; }
            }
        }

        func main() -> int {
            return len(messages) - I + classify(J) - 2;
        }
    """
    run_ok(
        "execute_const_referenced_array_bound",
        0,
        source,
        artifact_dir,
    )
    c_code = run_gen("generate_const_referenced_array_bound", source, artifact_dir)
    assert_true("_rt_cast_dea_int_from_unsigned" not in c_code,
        "const cast must fold instead of using a runtime checked-cast helper", artifact_dir)
    assert_true("const dea_int __deaM4mainN1J = 10;" in c_code,
        "folded arithmetic const should lower to a static literal", artifact_dir)
    assert_true("const __deaA25_c __deaM4mainN8messages = {.data = {DEA_STRING_CONST(" in c_code,
        "const array should lower to a file-scope brace initializer", artifact_dir)


def test_execute_toplet_mutation(artifact_dir: Path) -> None:
    """Mirror Stage 1 mutable top-level execution coverage."""

    run_ok(
        "execute_toplet_mutation",
        3,
        """
        module main;

        let counter: int = 0;

        func increment() -> void {
            counter = counter + 1;
        }

        func main() -> int {
            increment();
            increment();
            increment();
            return counter;
        }
        """,
        artifact_dir,
    )


def test_execute_toplet_struct(artifact_dir: Path) -> None:
    """Mirror Stage 1 struct top-level execution coverage."""

    run_ok(
        "execute_toplet_struct",
        30,
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        let position = Point(10, 20);

        func main() -> int {
            return position.x + position.y;
        }
        """,
        artifact_dir,
    )


def test_execute_toplet_nested_struct(artifact_dir: Path) -> None:
    """Mirror Stage 1 nested-struct top-level execution coverage."""

    run_ok(
        "execute_toplet_nested_struct",
        30,
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        struct Rectangle {
            top_left: Point;
            bottom_right: Point;
        }

        let rect = Rectangle(Point(0, 0), Point(10, 20));

        func main() -> int {
            return rect.bottom_right.x + rect.bottom_right.y;
        }
        """,
        artifact_dir,
    )


def test_execute_toplet_intrinsic_initializers(artifact_dir: Path) -> None:
    """Top-level deferred initializers must carry intrinsic metadata into code generation."""

    run_ok(
        "execute_toplet_intrinsic_initializers",
        0,
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        enum Color {
            Red;
            Blue;
        }

        let arr: int[3] = [1, 2, 3];
        let chosen: Color = Red;
        let string_len: int = len("abc");
        let arr_len: int = len(arr);
        let string_size: int = sizeof("abc");
        let point_size: int = sizeof(Point);
        let red_ord: int = ord(Red);
        let chosen_is_red: bool = is(chosen, Red);

        func main() -> int {
            if (string_len != 3) { return 1; }
            if (arr_len != 3) { return 2; }
            if (string_size <= 0) { return 3; }
            if (point_size <= 0) { return 4; }
            if (red_ord != 0) { return 5; }
            if (!chosen_is_red) { return 6; }
            return 0;
        }
        """,
        artifact_dir,
    )


def test_toplet_string_reassignment_arc(artifact_dir: Path) -> None:
    """Top-level string reassignment must release old values and stay leak-free."""

    source = """
        module main;
        import std.string;

        let greeting: string = "hi";

        func main() -> int {
            greeting = concat_s("a", "b");
            greeting = concat_s(greeting, "c");
            return len_s(greeting);
        }
    """

    c_code = run_gen("toplet_string_reassignment_gen", source, artifact_dir)
    assert_true("dea_string __deaM4mainN8greeting" in c_code, "missing top-level string declaration", artifact_dir)
    assert_true(
        c_code.count("rt_string_release(__deaM4mainN8greeting);") >= 2,
        "expected top-level string reassignment releases",
        artifact_dir,
    )

    arc = run_trace_ok("toplet_string_reassignment_trace", 3, source, artifact_dir)
    assert_true(
        any(event.get("kind") == "heap" and event.get("op") == "release" for event in arc),
        "expected heap ARC release during top-level string reassignment",
        artifact_dir,
    )


def test_drop_toplet_pointer_diagnostic(artifact_dir: Path) -> None:
    """Dropping a module-level let must raise the dedicated diagnostic."""

    run_check_error(
        "drop_toplet_pointer_diagnostic",
        "[TYP-0063]",
        """
        module main;

        struct Box {
            value: int;
        }

        let gp: Box*? = null;

        func main() -> int {
            drop gp;
            return 0;
        }
        """,
        artifact_dir,
    )


def main() -> int:
    """Program entrypoint."""

    artifact_dir = Path(tempfile.mkdtemp(prefix="l1_stage1_toplet_test."))
    keep_artifacts = os.environ.get("KEEP_ARTIFACTS", "0") == "1"

    checks = [
        test_execute_toplet_case_extended,
        test_reject_toplet_case_real_integer_arm,
        test_generate_toplet_case_always_false_unsigned,
        test_execute_toplet_primitives,
        test_execute_const_referenced_array_bound,
        test_execute_toplet_mutation,
        test_execute_toplet_struct,
        test_execute_toplet_nested_struct,
        test_execute_toplet_intrinsic_initializers,
        test_toplet_string_reassignment_arc,
        test_drop_toplet_pointer_diagnostic,
    ]

    try:
        for check in checks:
            check(artifact_dir)
        print("l1c_stage1_toplet_test: PASS")
        return 0
    except TopletFailure as exc:
        keep_artifacts = True
        lines = str(exc).splitlines()
        if lines:
            print(f"l1c_stage1_toplet_test: FAIL: {lines[0]}")
        for line in lines[1:]:
            print(f"l1c_stage1_toplet_test: {line}")
        return 1
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
