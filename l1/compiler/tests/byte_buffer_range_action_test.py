#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Range-action semantics, separate interfaces, and allocation-free transport."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from bytes_test import build
from file_runtime_test import check_trace
from filesystem_native_test import path_argument
from os_runtime_test import L1_ROOT, compiler_path, require_success, runtime_c_compiler
from support.driver_inputs import native_driver_args


FIXTURES = L1_ROOT / "compiler/tests/fixtures/bytes"
STDLIB = L1_ROOT / "compiler/shared/l1/stdlib"
RANGE_FAILURES = (
    "negative_start", "negative_count", "past_end", "capacity_only",
    "range_overflow", "start_overflow",
)
PROGRESS_FAILURES = tuple(
    f"{variant}_{bound}" for variant in ("applied", "stopped", "failed")
    for bound in ("negative", "large")
)
ALLOCATION_EVENTS = frozenset({
    "alloc", "calloc", "realloc", "new_alloc", "alloc_string", "realloc_string",
})


def require_contracts(work: Path, cc: str) -> None:
    """Check actual consumers and fatal guards in every runtime mode.

    Args:
        work: Owned executable directory.
        cc: Explicit native compiler executable.

    Raises:
        AssertionError: Result semantics, guards, or callback ordering differs.
    """
    for mode, flags in (
        ("checked", []), ("basic", ["--check-basic"]), ("unchecked", ["--unchecked"]),
    ):
        output = work / mode
        output.mkdir()
        executable = build(output, "range_action_main", cc, flags, root=FIXTURES)
        result = require_success([str(executable)], timeout=60)
        assert result.stdout == "range_action_main: PASS\n" and not result.stderr, result
        for scenario in (*RANGE_FAILURES, *PROGRESS_FAILURES):
            failed = subprocess.run(
                [str(executable), scenario], cwd=L1_ROOT, capture_output=True,
                text=True, timeout=60, check=False,
            )
            assert failed.returncode != 0, (mode, scenario, failed)
            expected = (
                "std.bytes: range out of bounds" if scenario in RANGE_FAILURES
                else "std.bytes: range action processed count out of bounds"
            )
            assert expected in failed.stderr, (mode, scenario, failed.stderr)
            entries = failed.stderr.splitlines().count("RANGE_CALLBACK_ENTERED")
            assert entries == (0 if scenario in RANGE_FAILURES else 1), (mode, scenario, failed.stderr)
        print(f"byte_buffer_range_action_test: {mode} PASS")
    traced = work / "traced"
    traced.mkdir()
    executable = build(traced, "range_action_main", cc, ["--trace-arc", "--trace-memory"], root=FIXTURES)
    result = require_success([str(executable)], timeout=60)
    assert result.stdout == "range_action_main: PASS\n", result.stdout
    check_trace(traced, "protocol", result.stderr)


def require_interfaces(work: Path, cc: str) -> None:
    """Run a consumer whose buffer and callback providers exist only as artifacts.

    Args:
        work: Owned compile artifacts and source-copy directory.
        cc: Explicit native compiler executable.

    Raises:
        AssertionError: Exports, opacity, semantic interfaces, or linking differ.
    """
    compiler = compiler_path()
    artifacts = work / "interfaces with spaces"
    (artifacts / "std").mkdir(parents=True)
    source_args = ["--no-managed-stdlib", "--sys-root", str(STDLIB)]
    bundled_interfaces = compiler.parent.parent / "interfaces"
    for module, output in (
        ("std.bytes", artifacts / "std/bytes.o"),
        ("range_action_provider", artifacts / "range_action_provider.o"),
    ):
        require_success([
            str(compiler), *source_args, "--project-root", str(FIXTURES),
            "--c-compiler", cc, "-I", str(artifacts), "-I", str(bundled_interfaces),
            "-c", module, "-o", str(output),
        ], timeout=120)
    contents = (artifacts / "std/bytes.l1m").read_text(encoding="utf-8")
    assert "opaque struct ByteBuffer;" in contents and "struct ByteBuffer {" not in contents, contents
    assert "type ByteBufferRangeAction = unsafe func(" in contents, contents
    for declaration in (
        "struct ByteBufferRangeActionContext", "struct ByteBufferRangeActionDiagnostic",
        "enum ByteBufferRangeActionResult", "unsafe func with_raw_range(",
    ):
        assert declaration in contents, declaration
    for text in (contents, (STDLIB / "std/bytes.l1").read_text(encoding="utf-8")):
        assert not re.search(r"\bimport\s+(?:module\s+)?(?:sys\.(?:fs|os)|std\.(?:file|os|io))\b", text), text
        assert not re.search(r"\b(?:_bytes_file_\w*|_bytes_entropy_\w*|rt_file_\w*|rt_entropy_\w*)\b", text), text
    isolated = work / "isolated source root"
    shutil.copytree(STDLIB, isolated)
    (isolated / "std/bytes.l1").unlink()
    consumer = work / "interface consumer"
    consumer.mkdir()
    shutil.copyfile(FIXTURES / "range_action_main.l1", consumer / "range_action_main.l1")
    executable = work / ("interface-consumer.exe" if os.name == "nt" else "interface-consumer")
    native = native_driver_args(compiler, cc, source=False)
    native.extend([
        "--no-managed-stdlib", "--sys-root", str(isolated),
        "--runtime-include", str(compiler.parent.parent / "include"),
    ])
    require_success([
        str(compiler), *native, "--c-compiler", cc, "--project-root", str(consumer),
        "-I", str(artifacts), "--build", "range_action_main", "-o", str(executable),
    ], timeout=240)
    result = require_success([str(executable)], timeout=60)
    assert result.stdout == "range_action_main: PASS\n" and not result.stderr, result
    require_bad_callbacks(work, artifacts)
    print("byte_buffer_range_action_test: separate interfaces PASS")


def require_bad_callbacks(work: Path, artifacts: Path) -> None:
    """Require exact callback signatures and unsafe markers from both provider forms.

    Args:
        work: Owned negative source directory.
        artifacts: Compiled provider interfaces to use in the second pass.

    Raises:
        AssertionError: A mismatched callback is accepted or reports an unrelated failure.
    """
    compiler = compiler_path()
    source_args = ["--no-managed-stdlib", "--sys-root", str(STDLIB)]
    for label, marker, pointer, context, returns, expression in (
        ("safe", "", "byte*", "bytes::ByteBufferRangeActionContext", "bytes::ByteBufferRangeActionResult", "bytes::RangeActionApplied(0, null)"),
        ("pointer", "unsafe ", "void*", "bytes::ByteBufferRangeActionContext", "bytes::ByteBufferRangeActionResult", "bytes::RangeActionApplied(0, null)"),
        ("context", "unsafe ", "byte*", "long", "bytes::ByteBufferRangeActionResult", "bytes::RangeActionApplied(0, null)"),
        ("result", "unsafe ", "byte*", "bytes::ByteBufferRangeActionContext", "int", "0"),
    ):
        name = f"range_bad_{label}"
        (work / f"{name}.l1").write_text(
            f"module {name};\nimport std.bytes as bytes;\n"
            "/**\n * Supply a deliberately incompatible callback.\n */\n"
            f"{marker}func candidate(data: {pointer}, count: int, context: {context}) -> {returns} {{ return {expression}; }}\n"
            "/**\n * Attempt a checked callback assignment.\n */\n"
            "func main() { let callback: bytes::ByteBufferRangeAction = candidate; }\n",
            encoding="utf-8",
        )
        for imports in ([], ["-I", str(artifacts)]):
            result = subprocess.run([
                str(compiler), *source_args, *imports, "--project-root", str(work),
                "--gen", name, "-o", str(work / f"{name}.c"),
            ], cwd=L1_ROOT, capture_output=True, text=True, timeout=120, check=False)
            assert result.returncode == 1, (label, result)
            expected = "[TYP-0780]" if label == "safe" else "[TYP-0310]"
            assert expected in result.stderr, (label, result.stderr)


def require_allocation_windows(trace: str) -> None:
    """Reject allocation events inside independently delimited transfer windows.

    Args:
        trace: Complete stderr log with runtime events and nonallocating markers.

    Raises:
        AssertionError: Tracing is absent, windows are malformed, or transport allocates.
    """
    lines = trace.splitlines()
    first = lines.index("RANGE_ALLOC_BEGIN")
    assert any("op=alloc_string " in line for line in lines[:first]), "missing allocation positive control"
    for family in ("RANGE", "FILE"):
        begin, end = f"{family}_ALLOC_BEGIN", f"{family}_ALLOC_END"
        assert lines.count(begin) == 1 and lines.count(end) == 1, trace
        start, stop = lines.index(begin), lines.index(end)
        assert start < stop, trace
        window = "\n".join(lines[start + 1:stop])
        found = set(re.findall(r"\bop=(\w+)", window)) & ALLOCATION_EVENTS
        assert not found, (family, found, window)


def require_allocations(work: Path, cc: str) -> None:
    """Check first/repeated generic and public file transfers with real trace evidence.

    Args:
        work: Owned fixture and executable directory.
        cc: Explicit native compiler executable.

    Raises:
        AssertionError: Transfers allocate, behavior fails, or cleanup is unbalanced.
    """
    project = work / "allocation sources"
    project.mkdir()
    for name in ("range_action_allocations.l1", "range_action_provider.l1"):
        shutil.copyfile(FIXTURES / name, project / name)
    shutil.copyfile(
        FIXTURES.parent / "filesystem_runtime/path_arguments.l1", project / "path_arguments.l1",
    )
    executable = build(
        work, "range_action_allocations", cc, ["--trace-arc", "--trace-memory"], root=project,
    )
    result = require_success([str(executable), path_argument(work / "allocation file café")], timeout=60)
    assert result.stdout == "range_action_allocations: PASS\n", result.stdout
    require_allocation_windows(result.stderr)
    check_trace(work, "allocations", result.stderr)
    print("byte_buffer_range_action_test: allocation-free dispatch/file transfers PASS")


def main() -> int:
    """Run the focused protocol suite without broad compiler or CI-only gates.

    Returns:
        Zero when protocol, interface, allocation, and ownership evidence passes.

    Raises:
        AssertionError: A focused contract fails.
    """
    cc = runtime_c_compiler()
    version = require_success([cc, "--version"]).stdout.splitlines()[0]
    print(f"Range-action compiler: {cc}: {version}")
    with tempfile.TemporaryDirectory(prefix="l1-range-actions-") as temporary:
        work = Path(temporary)
        require_contracts(work, cc)
        require_interfaces(work, cc)
        require_allocations(work, cc)
    print("byte_buffer_range_action_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
