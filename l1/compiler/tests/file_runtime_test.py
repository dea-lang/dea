#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Public L1 files, native wide offsets, and deterministic failure boundaries."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from filesystem_native_test import path_argument
from os_runtime_test import (
    L1_ROOT, RUNTIME_ROOT, RUNTIME_SOURCES, compiler_path,
    require_success, runtime_c_compiler,
)
from support.driver_inputs import native_driver_args


FIXTURES = L1_ROOT / "compiler/tests/fixtures/file_runtime"
RANGE_FAILURES = (
    "negative_start", "negative_count", "past_end", "empty_past_end",
    "range_overflow", "capacity_only", "write_all_range",
)


def build(
    work: Path, module: str, cc: str, flags: tuple[str, ...] = (), *,
    library: Path | None = None, project_root: Path | None = None,
) -> Path:
    """Build a public consumer with explicit source and native runtime inputs.

    Args:
        work: Owned destination directory.
        module: Fixture module name.
        cc: Selected native compiler.
        flags: Runtime mode or tracing flags.
        library: Optional injected runtime archive directory.
        project_root: Optional staged source tree containing shared fixture modules.

    Returns:
        Built native executable.

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
        str(compiler), "--project-root", str(project_root or FIXTURES), "--c-compiler", cc,
        *native, *flags, "--build", module, "-o", str(executable),
    ], timeout=240)
    return executable


def check_trace(work: Path, name: str, trace: str) -> None:
    """Require balanced ARC and raw-memory traces from an actual target program.

    Args:
        work: Owned trace output directory.
        name: Unique evidence filename stem.
        trace: Program stderr containing resource trace records.

    Raises:
        AssertionError: Resource ownership or required trace families fail.
    """
    path = work / f"{name}.trace"
    path.write_text(trace, encoding="utf-8")
    report = require_success([
        sys.executable, str(L1_ROOT / "compiler/scripts/check_trace_log.py"),
        str(path), "--triage", "--max-details", "5",
    ], timeout=60)
    assert "leaked_object_ptrs=0" in report.stdout and "leaked_string_ptrs=0" in report.stdout, report.stdout
    assert "[l0][mem]" in trace and "[l0][arc]" in trace, trace


def require_generated(work: Path, cc: str) -> None:
    """Exercise real public APIs and unconditional buffer-range assertions.

    Args:
        work: Owned build and fixture directory.
        cc: Selected native compiler.

    Raises:
        AssertionError: API semantics, cleanup, bounds, or lifetime checks fail.
    """
    for mode, flags in (("checked", ()), ("basic", ("--check-basic",)), ("unchecked", ("--unchecked",))):
        output = work / mode
        output.mkdir()
        executable = build(output, "file_main", cc, flags)
        result = require_success([str(executable), "normal", str(output / "public")], timeout=60)
        assert result.stdout == "file_main: PASS\n" and not result.stderr, result
        for case in RANGE_FAILURES:
            failure = subprocess.run([
                str(executable), case, str(output / case),
            ], cwd=L1_ROOT, capture_output=True, text=True, timeout=60, check=False)
            assert failure.returncode != 0, f"{mode}/{case} unexpectedly succeeded"
            assert "std.bytes: file range out of bounds" in failure.stderr, (mode, case, failure.stderr)
        if mode == "checked":
            failure = subprocess.run([
                str(executable), "expired_alias", str(output / "expired"),
            ], cwd=L1_ROOT, capture_output=True, text=True, timeout=60, check=False)
            assert failure.returncode != 0 and "use after drop/free" in failure.stderr, failure.stderr
        print(f"file_runtime_test: public {mode} PASS")
    traced = work / "traced"
    traced.mkdir()
    executable = build(traced, "file_main", cc, ("--trace-arc", "--trace-memory"))
    result = require_success([str(executable), "normal", str(traced / "public")], timeout=60)
    assert result.stdout == "file_main: PASS\n", result.stdout
    check_trace(traced, "public", result.stderr)


def require_interface(work: Path) -> None:
    """Prove file representation remains opaque through source and interface imports.

    Args:
        work: Owned source/interface output directory.

    Raises:
        AssertionError: Opaque representation or compiler diagnostics differ.
    """
    compiler = compiler_path()
    source = ["--no-managed-stdlib", "--sys-root", str(L1_ROOT / "compiler/shared/l1/stdlib")]
    interfaces = work / "interfaces"
    (interfaces / "std").mkdir(parents=True)
    interface = interfaces / "std/file.l1m"
    require_success([str(compiler), *source, "--emit-interface", "std.file", "-o", str(interface)], timeout=120)
    contents = interface.read_text(encoding="utf-8")
    assert "opaque struct File;" in contents and "struct File {" not in contents, contents
    assert "func read_exact(" in contents and "func _close_result(" not in contents, contents
    for name, operation in (
        ("field", "let hidden = file._handle;"),
        ("drop", "drop file;"),
        ("layout", "let count = sizeof(File);"),
    ):
        module = f"file_opaque_{name}"
        (work / f"{module}.l1").write_text(
            f"module {module};\nimport std.file;\n"
            "/**\n * Attempt a forbidden operation on an opaque file.\n *\n * @param file Borrowed file.\n */\n"
            f"func forbidden(file: File*) {{ {operation} }}\n"
            "/**\n * Supply a harmless entry point for generation.\n */\nfunc main() {}\n",
            encoding="utf-8",
        )
        for imports in ([], ["-I", str(interfaces)]):
            result = subprocess.run([
                str(compiler), *source, *imports, "--project-root", str(work),
                "--gen", module, "-o", str(work / f"{module}.c"),
            ], cwd=L1_ROOT, capture_output=True, text=True, timeout=120, check=False)
            assert result.returncode == 1 and "[RES-0038]" in result.stderr, result.stderr


def prepare_sparse(path: Path) -> None:
    """Create a sparse-capable empty fixture without allocating a wide real extent.

    Args:
        path: New native file path.

    Raises:
        AssertionError: Windows cannot mark the test file sparse.
    """
    path.touch()
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.DeviceIoControl.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    )
    kernel.DeviceIoControl.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), 0x40000000, 7, None, 3, 0, None)
    assert handle != wintypes.HANDLE(-1).value, ctypes.get_last_error()
    try:
        returned = wintypes.DWORD()
        assert kernel.DeviceIoControl(handle, 0x000900C4, None, 0, None, 0, ctypes.byref(returned), None), ctypes.get_last_error()
    finally:
        assert kernel.CloseHandle(handle), ctypes.get_last_error()


def require_wide_public(work: Path, cc: str) -> None:
    """Verify wide offsets through actual traced L1 file and buffer APIs.

    Args:
        work: Owned executable, sparse-file, and trace directory.
        cc: Selected native compiler.

    Raises:
        AssertionError: Wide public transfers, cursor preservation, or cleanup fails.
    """
    project = work / "wide-public-sources"
    project.mkdir()
    for name in ("file_main.l1", "file_wide_main.l1"):
        shutil.copyfile(FIXTURES / name, project / name)
    shutil.copyfile(FIXTURES.parent / "filesystem_runtime/path_arguments.l1", project / "path_arguments.l1")
    executable = build(work, "file_wide_main", cc, ("--trace-arc", "--trace-memory"), project_root=project)
    path = work / "wide public café"
    prepare_sparse(path)
    result = require_success([str(executable), path_argument(path)], timeout=60)
    assert result.stdout == "file_wide_main: PASS\n", result.stdout
    assert path.stat().st_size == 0, "public wide file must be truncated after the probe"
    check_trace(work, "wide-public", result.stderr)


def require_native(work: Path, cc: str) -> None:
    """Check native wide offsets, runtime validation, and non-seekable endpoints.

    Args:
        work: Owned native probe directory.
        cc: Selected native C compiler.

    Raises:
        AssertionError: Native compilation or a runtime boundary fails.
    """
    executable = work / ("file-native.exe" if os.name == "nt" else "file-native")
    require_success([
        cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
        *(["-DDEA_FILE_READ_FILE=file_probe_read_file"] if os.name == "nt" else []),
        f"-I{RUNTIME_ROOT / 'include'}", f"-I{RUNTIME_ROOT / 'internal'}",
        str(FIXTURES / "native_probe.c"),
        *(str(RUNTIME_ROOT / "src" / name) for name in RUNTIME_SOURCES),
        "-lm", "-o", str(executable),
    ], timeout=120)
    path = work / "wide sparse café"
    prepare_sparse(path)
    arguments = [path_argument(path)]
    if os.name != "nt":
        fifo = work / "nonseekable"
        os.mkfifo(fifo)
        arguments.append(path_argument(fifo))
    result = require_success([str(executable), *arguments], timeout=60)
    assert result.stdout == "file native: PASS\n", result.stdout
    assert path.stat().st_size == 0, "wide file must be truncated after the probe"


def require_injected(work: Path, cc: str) -> None:
    """Trace actual public L1 callers against deterministic native faults.

    Args:
        work: Owned build and archive directory.
        cc: Selected native compiler.

    Raises:
        AssertionError: Failure semantics or resource cleanup violates its contract.
    """
    library = work / "injected-runtime"
    library.mkdir()
    if os.name == "nt":
        hooks = ["CLOSE_HANDLE", "READ_FILE", "WRITE_FILE", "GET_FILE_INFORMATION", "FLUSH_FILE_BUFFERS"]
    else:
        hooks = ["CLOSE", "READ", "WRITE", "FSTAT", "FSYNC"]
        if sys.platform != "darwin":
            hooks.append("FDATASYNC")
    objects = []
    for name in (*RUNTIME_SOURCES, "dea_rt_trace.c", "file_faults.c"):
        source = FIXTURES / name if name == "file_faults.c" else RUNTIME_ROOT / "src" / name
        obj = library / (name + ".o")
        require_success([
            cc, "-std=c99", "-DDEA_TRACE_ARC", "-DDEA_TRACE_MEMORY",
            *(f"-DDEA_FILE_{hook}=file_probe_{hook.lower()}" for hook in hooks),
            f"-I{RUNTIME_ROOT / 'include'}", f"-I{RUNTIME_ROOT / 'internal'}",
            "-c", str(source), "-o", str(obj),
        ], timeout=120)
        objects.append(str(obj))
    archiver = shutil.which("ar")
    assert archiver, "injected runtime requires an archiver"
    require_success([archiver, "rcs", str(library / "libdea_rt_traced.a"), *objects], timeout=60)
    executable = build(work, "file_failure_main", cc, ("--trace-arc", "--trace-memory"), library=library)
    result = require_success([str(executable), str(work / "faulted-file")], timeout=60)
    assert result.stdout == "file_failure_main: PASS\n", result.stdout
    check_trace(work, "failures", result.stderr)


def main() -> int:
    """Run focused public, native, opacity, and failure-injection regressions.

    Returns:
        Zero after all applicable scenarios pass.

    Raises:
        AssertionError: A file API or resource-lifetime requirement fails.
    """
    cc = runtime_c_compiler()
    version = require_success([cc, "--version"]).stdout.splitlines()[0]
    print(f"File runtime compiler: {cc}: {version}")
    with tempfile.TemporaryDirectory(prefix="l1-files-") as temporary:
        work = Path(temporary)
        require_native(work, cc)
        require_generated(work, cc)
        require_wide_public(work, cc)
        require_interface(work)
        require_injected(work, cc)
    print("file_runtime_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
