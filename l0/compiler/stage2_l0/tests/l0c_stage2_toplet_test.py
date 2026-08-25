#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Native Stage 2 regressions for top-level let behavior."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap

from tool_test_common import resolve_tool


REPO_ROOT = Path(__file__).resolve().parents[4]
L0_ROOT = REPO_ROOT / "l0"
TRACE_CHECKER = L0_ROOT / "compiler" / "stage2_l0" / "scripts" / "check_trace_log.py"
_ARC_LINE_RE = re.compile(r"^\[l0\]\[arc\] (.+)$")
_KV_RE = re.compile(r"(\w+)=(\S+)")


class TopletFailure(RuntimeError):
    """Raised when one Stage 2 toplet regression fails."""


def read_text(path: Path) -> str:
    """Read one text file with replacement for invalid bytes."""

    return path.read_text(encoding="utf-8", errors="replace")


def stage2_compiler() -> Path:
    """Return the repo-local native Stage 2 compiler path."""

    build_dir = Path(os.environ.get("DEA_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L0_ROOT / build_dir
    return resolve_tool(build_dir / "bin", "l0c-stage2")


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
    """Write one temporary L0 source file for one regression case."""

    case_dir = artifact_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    source_path = case_dir / "main.l0"
    source_path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return source_path


def run_compiler(
    case_name: str,
    source: str,
    artifact_dir: Path,
    *args: str,
) -> tuple[int, str, str]:
    """Run the native Stage 2 compiler for one temporary case."""

    compiler = stage2_compiler()
    assert_true(compiler.is_file(), f"missing repo-local Stage 2 compiler: {compiler}", artifact_dir)

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
    compiler = stage2_compiler()

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


def test_toplet_bare_variant_static_initializer(artifact_dir: Path) -> None:
    """Bare zero-argument enum variants infer top-level let type and lower statically."""

    source = """
        module main;

        enum Color {
            Red;
            Green(value: int);
        }

        let favorite = Red;

        func main() -> int {
            return ord(favorite);
        }
    """

    c_code = run_gen("toplet_bare_variant_gen", source, artifact_dir)
    assert_true(
        "static struct l0_main_Color l0_main_favorite = { .tag = l0_main_Color_Red };" in c_code,
        "missing bare variant static initializer",
        artifact_dir,
    )
    run_ok("toplet_bare_variant_run", 0, source, artifact_dir)


def test_toplet_bare_payload_variant_diagnostic(artifact_dir: Path) -> None:
    """Bare payload variants still require constructor arguments."""

    run_check_error(
        "toplet_bare_payload_variant_diagnostic",
        "[SIG-0030]",
        """
        module main;

        enum Color {
            Red;
            Green(value: int);
        }

        let favorite = Green;

        func main() -> int {
            return 0;
        }
        """,
        artifact_dir,
    )


def test_toplet_initializer_type_mismatch(artifact_dir: Path) -> None:
    """Annotated top-level initializers must be checked before lowering."""

    actual_rc, _stdout, stderr = run_compiler(
        "toplet_initializer_type_mismatch",
        """
        module main;

        let bad: int = "text";

        func main() -> int {
            return 0;
        }
        """,
        artifact_dir,
        "--check",
    )
    assert_true(actual_rc != 0, "top-level initializer mismatch should fail checking", artifact_dir)
    assert_true(stderr.count("[TYP-0310]") == 1, "expected exactly one TYP-0310 diagnostic", artifact_dir)


def test_toplet_static_intrinsics(artifact_dir: Path) -> None:
    """Static intrinsic initializers must type-check, compile, and execute."""

    source = """
        module main;

        enum Choice {
            None;
            Some(value: int);
        }

        struct Holder {
            value: byte?;
        }

        let byte_size: int = sizeof(byte);
        let none_tag: int = ord(None);
        let some_tag: int = ord(Some(99));
        let top_value: byte? = 1;

        func read(value: byte?) -> int {
            return (value as byte) as int;
        }

        func main() -> int {
            let local_value: byte? = 2;
            let holder = Holder(3);
            return byte_size + none_tag + some_tag + read(top_value) +
                read(local_value) + read(holder.value) + read(4) - 12;
        }
    """

    c_code = run_gen("toplet_static_intrinsics_gen", source, artifact_dir)
    assert_true(
        "static l0_int l0_main_none_tag = ((l0_int)(l0_main_Choice_None));" in c_code,
        "bare variant ord should use its direct tag constant",
        artifact_dir,
    )
    assert_true(
        "static l0_int l0_main_some_tag = ((l0_int)(l0_main_Choice_Some));" in c_code,
        "payload variant ord should use its direct tag constant",
        artifact_dir,
    )
    run_ok("toplet_static_intrinsics", 0, source, artifact_dir)


def test_toplet_nonconstant_ord_rejected(artifact_dir: Path) -> None:
    """An `ord` of a top-level variable must not become an invalid C initializer."""

    actual_rc, stdout, stderr = run_compiler(
        "toplet_nonconstant_ord_rejected",
        """
        module main;

        enum Choice {
            None;
        }

        let choice: Choice = None;
        let tag: int = ord(choice);

        func main() -> int {
            return tag;
        }
        """,
        artifact_dir,
        "--build",
    )
    output = stdout + stderr
    assert_true(actual_rc != 0, "non-constant top-level ord should fail lowering", artifact_dir)
    assert_true("[ICE-1181]" in output, "expected the static-initializer restriction", artifact_dir)
    assert_true("initializer element is not constant" not in output,
        "invalid C should not reach the host compiler", artifact_dir)


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
    assert_true("static l0_string l0_main_greeting" in c_code, "missing top-level string declaration", artifact_dir)
    assert_true(
        c_code.count("rt_string_release(l0_main_greeting);") >= 2,
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

    artifact_dir = Path(tempfile.mkdtemp(prefix="l0_stage2_toplet_test."))
    keep_artifacts = os.environ.get("KEEP_ARTIFACTS", "0") == "1"

    checks = [
        test_execute_toplet_primitives,
        test_execute_toplet_mutation,
        test_execute_toplet_struct,
        test_execute_toplet_nested_struct,
        test_toplet_bare_variant_static_initializer,
        test_toplet_bare_payload_variant_diagnostic,
        test_toplet_initializer_type_mismatch,
        test_toplet_static_intrinsics,
        test_toplet_nonconstant_ord_rejected,
        test_toplet_string_reassignment_arc,
        test_drop_toplet_pointer_diagnostic,
    ]

    try:
        for check in checks:
            check(artifact_dir)
        print("l0c_stage2_toplet_test: PASS")
        return 0
    except TopletFailure as exc:
        keep_artifacts = True
        lines = str(exc).splitlines()
        if lines:
            print(f"l0c_stage2_toplet_test: FAIL: {lines[0]}")
        for line in lines[1:]:
            print(f"l0c_stage2_toplet_test: {line}")
        return 1
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
