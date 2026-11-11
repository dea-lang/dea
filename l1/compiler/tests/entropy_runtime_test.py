#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Public entropy, bounded native transfers, and failure ownership regressions."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from entropy_native_simulation import require_simulated_adapters
from file_runtime_test import check_trace
from os_runtime_test import (
    L1_ROOT, RUNTIME_ROOT, RUNTIME_SOURCES, compiler_path,
    require_success, runtime_c_compiler,
)
from support.driver_inputs import native_driver_args


FIXTURES = L1_ROOT / "compiler/tests/fixtures/entropy_runtime"
STDLIB = L1_ROOT / "compiler/shared/l1/stdlib"
ALLOCATION_EVENTS = frozenset({
    "alloc", "calloc", "realloc", "new_alloc", "alloc_string", "realloc_string",
})
RANGE_FAILURES = (
    "negative_start", "negative_count", "past_end", "empty_past_end",
    "range_overflow", "capacity_only",
)


def build(
    work: Path, module: str, cc: str, flags: tuple[str, ...] = (), *,
    library: Path | None = None, project_root: Path = FIXTURES,
) -> Path:
    """Build an actual public L1 consumer against selected runtime inputs.

    Args:
        work: Owned destination directory.
        module: Fixture module to build.
        cc: Explicit native compiler.
        flags: Runtime mode and trace arguments.
        library: Optional directory containing an injected runtime archive.
        project_root: Directory containing the selected consumer module.

    Returns:
        Path to the built native executable.

    Raises:
        AssertionError: Compilation fails.
    """
    compiler = compiler_path()
    executable = work / (module + (".exe" if os.name == "nt" else ""))
    native = native_driver_args(compiler, cc)
    if library is not None:
        native = [
            "--runtime-lib", str(library), "--no-auto-prepare", "--no-managed-stdlib",
            "--sys-root", str(L1_ROOT / "compiler/shared/l1/stdlib"),
            "--runtime-include", str(RUNTIME_ROOT / "include"),
        ]
    require_success([
        str(compiler), "--project-root", str(project_root), "--c-compiler", cc,
        *native, *flags, "--build", module, "-o", str(executable),
    ], timeout=240)
    return executable


def require_generated(work: Path, cc: str) -> None:
    """Exercise real host bytes, public bounds, and successful result cleanup.

    Args:
        work: Owned build directory.
        cc: Explicit native compiler.

    Raises:
        AssertionError: Public behavior or unconditional bounds checks fail.
    """
    for mode, flags in (
        ("checked", ()), ("basic", ("--check-basic",)), ("unchecked", ("--unchecked",)),
        ("traced", ("--trace-arc", "--trace-memory")),
    ):
        output = work / mode
        output.mkdir()
        executable = build(output, "entropy_main", cc, flags)
        result = require_success([str(executable)], timeout=60)
        assert result.stdout == "entropy_main: PASS\n", result.stdout
        if mode == "traced":
            check_trace(output, "public", result.stderr)
            continue
        assert result.stderr == "", result.stderr
        for scenario in (*RANGE_FAILURES, "negative_random"):
            failed = subprocess.run(
                [str(executable), scenario], cwd=L1_ROOT, capture_output=True,
                text=True, timeout=60, check=False,
            )
            message = "std.entropy: negative count" if scenario == "negative_random" else "std.bytes: range out of bounds"
            assert failed.returncode not in (0, 99), (mode, scenario, failed)
            assert message in failed.stderr, (mode, scenario, failed.stderr)
        if mode == "checked":
            failed = subprocess.run(
                [str(executable), "expired_alias"], cwd=L1_ROOT, capture_output=True,
                text=True, timeout=60, check=False,
            )
            assert failed.returncode not in (0, 99) and "use after drop/free" in failed.stderr, failed
        print(f"entropy_runtime_test: public {mode} PASS")


def injected_runtime(work: Path, cc: str) -> Path:
    """Build a traced runtime with deterministic entropy host-call injection.

    Args:
        work: Owned build directory.
        cc: Explicit native compiler.

    Returns:
        Directory containing the injected traced runtime archive.

    Raises:
        AssertionError: Compilation fails or no archiver is available.
    """
    library = work / "injected-runtime"
    library.mkdir()
    objects = []
    for name in (*RUNTIME_SOURCES, "dea_rt_trace.c", "entropy_faults.c"):
        source = FIXTURES / name if name == "entropy_faults.c" else RUNTIME_ROOT / "src" / name
        obj = library / (name + ".o")
        hooks = ["-include", str(FIXTURES / "entropy_faults.h")] if name == "dea_rt_entropy.c" else []
        require_success([
            cc, "-std=c99", "-DDEA_TRACE_ARC", "-DDEA_TRACE_MEMORY", *hooks,
            f"-I{RUNTIME_ROOT / 'include'}", f"-I{RUNTIME_ROOT / 'internal'}",
            "-c", str(source), "-o", str(obj),
        ], timeout=120)
        objects.append(str(obj))
    archiver = shutil.which("ar")
    assert archiver, "injected entropy runtime requires an archiver"
    require_success([archiver, "rcs", str(library / "libdea_rt_traced.a"), *objects], timeout=60)
    return library


def require_injected(work: Path, cc: str) -> None:
    """Verify deterministic partial failures and cleanup through public L1 APIs.

    Args:
        work: Owned build directory.
        cc: Explicit native compiler.

    Raises:
        AssertionError: Error transport, prefix preservation, or cleanup fails.
    """
    library = injected_runtime(work, cc)
    native = work / ("entropy-native.exe" if os.name == "nt" else "entropy-native")
    require_success([
        cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
        f"-I{RUNTIME_ROOT / 'include'}", f"-I{RUNTIME_ROOT / 'internal'}",
        f"-I{RUNTIME_ROOT / 'src'}", str(FIXTURES / "native_probe.c"),
        str(library / "libdea_rt_traced.a"), "-lm", "-o", str(native),
    ], timeout=120)
    result = require_success([str(native)], timeout=60)
    assert "PASS" in result.stdout, result.stdout
    require_simulated_adapters(work, cc, library / "libdea_rt_traced.a")
    executable = build(work, "entropy_failure_main", cc, ("--trace-arc", "--trace-memory"), library=library)
    result = require_success([str(executable)], timeout=60)
    assert result.stdout == "entropy_failure_main: PASS\n", result.stdout
    check_trace(work, "failures", result.stderr)
    require_allocations(work, cc, library)


def require_allocations(work: Path, cc: str, library: Path) -> None:
    """Observe first and repeated fill success/failure without transport allocations.

    Args:
        work: Owned build directory.
        cc: Explicit native compiler.
        library: Traced runtime archive with deterministic native injection.

    Raises:
        AssertionError: A fill allocates, tracing is absent, or cleanup leaks.
    """
    executable = build(
        work, "entropy_allocations", cc, ("--trace-arc", "--trace-memory"), library=library,
    )
    result = require_success([str(executable)], timeout=60)
    assert result.stdout == "entropy_allocations: PASS\n", result.stdout
    lines = result.stderr.splitlines()
    first = lines.index("ENTROPY_SUCCESS_ALLOC_BEGIN")
    assert any("op=alloc_string " in line for line in lines[:first]), "missing allocation positive control"
    for family in ("SUCCESS", "FAILURE"):
        begin, end = f"ENTROPY_{family}_ALLOC_BEGIN", f"ENTROPY_{family}_ALLOC_END"
        assert lines.count(begin) == 1 and lines.count(end) == 1, result.stderr
        start, stop = lines.index(begin), lines.index(end)
        assert start < stop, result.stderr
        window = "\n".join(lines[start + 1:stop])
        found = set(re.findall(r"\bop=(\w+)", window)) & ALLOCATION_EVENTS
        assert not found, (family, found, window)
    check_trace(work, "allocations", result.stderr)
    print("entropy_runtime_test: allocation-free fill success/partial failure PASS")


def require_interfaces(work: Path, cc: str) -> None:
    """Run the public API with entropy and buffer providers available only as artifacts.

    Args:
        work: Owned compile artifacts and source-copy directory.
        cc: Explicit native compiler executable.

    Raises:
        AssertionError: Public interfaces, opaque storage, or native linking differs.
    """
    compiler = compiler_path()
    artifacts = work / "interfaces with spaces"
    (artifacts / "std").mkdir(parents=True)
    bundled = compiler.parent.parent / "interfaces"
    for module in ("bytes", "entropy"):
        require_success([
            str(compiler), "--no-managed-stdlib", "--sys-root", str(STDLIB),
            "--project-root", str(FIXTURES), "--c-compiler", cc,
            "-I", str(artifacts), "-I", str(bundled), "-c", f"std.{module}",
            "-o", str(artifacts / f"std/{module}.o"),
        ], timeout=120)
    interface = (artifacts / "std/entropy.l1m").read_text(encoding="utf-8")
    for declaration in (
        "enum EntropyResult", "enum RandomBytesResult", "func fill(",
        "func random_bytes(", "func free_random_bytes_result(",
    ):
        assert declaration in interface, declaration
    assert "_fill_action" not in interface and "_decode_entropy_result" not in interface, interface
    isolated = work / "isolated source root"
    shutil.copytree(STDLIB, isolated)
    for module in ("bytes", "entropy"):
        (isolated / f"std/{module}.l1").unlink()
    consumer = work / "interface consumer"
    consumer.mkdir()
    shutil.copyfile(FIXTURES / "entropy_main.l1", consumer / "entropy_main.l1")
    executable = work / ("entropy-interfaces.exe" if os.name == "nt" else "entropy-interfaces")
    native = native_driver_args(compiler, cc, source=False)
    require_success([
        str(compiler), *native, "--no-managed-stdlib", "--sys-root", str(isolated),
        "--runtime-include", str(compiler.parent.parent / "include"),
        "--c-compiler", cc, "--project-root", str(consumer), "-I", str(artifacts),
        "--build", "entropy_main", "-o", str(executable),
    ], timeout=240)
    result = require_success([str(executable)], timeout=60)
    assert result.stdout == "entropy_main: PASS\n" and not result.stderr, result
    print("entropy_runtime_test: separate interfaces PASS")


def range_conversion_source() -> str:
    """Append a private entropy conversion probe without adding a production test API.

    Returns:
        Production provider with callback-entry observation and schema assertions.
    """
    source = (STDLIB / "std/entropy.l1").read_text(encoding="utf-8")
    source = source.replace("module std.entropy;", "module entropy_range_probe;")
    source = source.replace("import sys.os;", "import sys.os;\nimport std.system as system;\nimport std.io;")
    source = source.replace("free_random_bytes_result;", "free_random_bytes_result, main;")
    entry = "unsafe func _fill_action(data: byte*, count: int, context: RangeContext) -> RangeResult {"
    assert source.count(entry) == 1, "entropy callback entry cannot be instrumented"
    source = source.replace(entry, entry + '\n    err_printl_s("ENTROPY_CALLBACK_ENTERED");')
    return source + (FIXTURES / "entropy_range_checks.l1.inc").read_text(encoding="utf-8")


def require_range_conversions(work: Path, cc: str) -> None:
    """Check entropy-specific payload validation and dispatch in all runtime modes.

    Args:
        work: Owned source and executable directory.
        cc: Explicit native compiler.

    Raises:
        AssertionError: Conversion loses progress or errors, or accepts malformed data.
    """
    source = work / "range conversion source"
    source.mkdir()
    (source / "entropy_range_probe.l1").write_text(range_conversion_source(), encoding="utf-8")
    invalid = {
        "native_negative": "invalid native entropy result",
        "native_stopped": "invalid native entropy result",
        "native_timeout": "invalid native entropy result",
        "native_unknown": "invalid native entropy result",
        "requested_negative": "invalid range action result",
        "applied_negative": "invalid range action result",
        "applied_short": "invalid range action result",
        "applied_large": "invalid range action result",
        "applied_value": "invalid range action result",
        "stopped": "invalid range action result",
        "failed_negative": "invalid range action result",
        "failed_large": "invalid range action result",
        "failed_tag": "invalid range action result",
        "failed_domain": "invalid range action error",
        "runtime_code": "invalid range action error",
    }
    for mode, flags in (("checked", ()), ("basic", ("--check-basic",)), ("unchecked", ("--unchecked",))):
        output = work / f"range-conversion-{mode}"
        output.mkdir()
        executable = build(output, "entropy_range_probe", cc, flags, project_root=source)
        result = require_success([str(executable), "normal"], timeout=60)
        assert result.stdout == "entropy range conversions: PASS\n" and not result.stderr, result
        empty = require_success([str(executable), "empty"], timeout=60)
        assert empty.stderr.splitlines() == ["ENTROPY_CALLBACK_ENTERED"], empty
        for case, message in {**invalid, "bad_range": "std.bytes: range out of bounds"}.items():
            failed = subprocess.run(
                [str(executable), case], cwd=L1_ROOT, capture_output=True,
                text=True, timeout=60, check=False,
            )
            assert failed.returncode != 0, (mode, case, failed)
            expected = message if case == "bad_range" else f"std.entropy: {message}"
            assert expected in failed.stderr, (mode, case, failed.stderr)
            assert "ENTROPY_CALLBACK_ENTERED" not in failed.stderr, (mode, case, failed.stderr)
        print(f"entropy_runtime_test: range conversion {mode} PASS")


def main() -> int:
    """Run public entropy and native fault-injection regression scenarios.

    Returns:
        Zero after all applicable scenarios pass.

    Raises:
        AssertionError: A public or native contract is violated.
    """
    cc = runtime_c_compiler()
    version = require_success([cc, "--version"]).stdout.splitlines()[0]
    print(f"Entropy runtime compiler: {cc}: {version}")
    with tempfile.TemporaryDirectory(prefix="l1-entropy-") as temporary:
        work = Path(temporary)
        require_generated(work, cc)
        require_range_conversions(work, cc)
        require_interfaces(work, cc)
        require_injected(work, cc)
    print("entropy_runtime_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
