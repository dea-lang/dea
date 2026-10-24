#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Public generated L1 programs and native filesystem failure boundaries."""

from __future__ import annotations

import ntpath
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile

from os_runtime_test import (
    L1_ROOT, RUNTIME_ROOT, RUNTIME_SOURCES, compiler_path,
    require_success, runtime_c_compiler,
)
from support.driver_inputs import native_driver_args

FIXTURES = L1_ROOT / "compiler/tests/fixtures/filesystem_runtime"


def path_argument(path: Path | str | bytes) -> str:
    """Encode filesystem input as ASCII, independent of Windows narrow argv.

    Args:
        path: UTF-8 Windows path or native POSIX filename bytes.

    Returns:
        Hexadecimal transport decoded inside the C or L1 test consumer.
    """
    raw = path if isinstance(path, bytes) else os.fspath(path).encode("utf-8") if os.name == "nt" else os.fsencode(path)
    return "hex:" + raw.hex()


def windows_extended(path: str) -> str:
    """Return a drive or UNC spelling with its correct Windows extended prefix.

    Args:
        path: Absolute Windows path.

    Returns:
        Extended Windows spelling, preserving an existing extended prefix.
    """
    if path.startswith("\\\\?\\"):
        return path
    return "\\\\?\\UNC\\" + path[2:] if path.startswith("\\\\") else "\\\\?\\" + path


def compile_probe(work: Path, cc: str, name: str, hooks: tuple[str, ...] = ()) -> Path:
    """Compile a direct runtime probe with optional deterministic host hooks.

    Args:
        work: Owned build directory.
        cc: Selected C compiler.
        name: Fixture source basename.
        hooks: Primitive names to replace with fixture functions.

    Returns:
        Built probe executable.
    """
    executable = work / (name + (".exe" if os.name == "nt" else ""))
    require_success([
        cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
        f"-I{RUNTIME_ROOT / 'include'}", f"-I{RUNTIME_ROOT / 'internal'}",
        *(f"-DDEA_FS_{hook.upper()}=fs_probe_{hook}" for hook in hooks),
        str(FIXTURES / f"{name}.c"),
        *(str(RUNTIME_ROOT / "src" / name) for name in RUNTIME_SOURCES),
        "-lm", "-o", str(executable),
    ])
    return executable


def require_native(work: Path, cc: str) -> None:
    """Check path bytes, links, alias-safe copying, recursive deletion and errors.

    Args:
        work: Owned temporary fixture directory.
        cc: Selected C compiler.
    """
    probe = compile_probe(work, cc, "native_probe")
    root = work / "native space caf\u00e9"
    root.mkdir()
    target = root / "target"
    different = root / "different"
    target.write_bytes(b"outside-marker")
    different.write_bytes(b"replacement")
    hard = root / "hard"
    os.link(target, hard)
    tree = root / "tree"
    (tree / "nested").mkdir(parents=True)
    (tree / "nested/marker").write_bytes(b"child")
    link, dangling = root / "link", root / "dangling"
    try:
        link.symlink_to(target)
        dangling.symlink_to(root / "absent")
        (tree / "outside").symlink_to(root, target_is_directory=True)
        (tree / "broken").symlink_to(root / "absent", target_is_directory=True)
    except OSError:
        for path in (link, dangling, tree / "outside", tree / "broken"):
            path.unlink(missing_ok=True)
        print("filesystem_native_test: native symlink creation unavailable")
        link_args = ["-", str(hard), "-"]
    else:
        link_args = [str(link), str(hard), str(dangling)]
    require_success([str(probe), *(path_argument(value) for value in (root, target, different, *link_args, tree))])
    assert target.read_bytes() == b"outside-marker", "recursive deletion escaped through link"
    assert not tree.exists()
    if os.name != "nt":
        failure = compile_probe(work, cc, "failure_probe", ("readdir", "closedir", "read", "write", "rename", "close"))
        copied, interrupted, full = work / "copied", work / "interrupted", work / "full"
        deep = work / "deep"
        current = deep
        for _ in range(259):
            current.mkdir()
            current = current / "d"
        require_success([str(failure), str(root), str(target), str(copied), str(interrupted), str(full), str(deep)])
        assert copied.read_bytes() == target.read_bytes(), "partial writes lost bytes"
        assert interrupted.read_bytes() == b"" and full.read_bytes() == target.read_bytes()


def require_permissions(work: Path, cc: str) -> None:
    """Verify inaccessible inputs return direct failure when POSIX permits the fixture.

    Args:
        work: Owned temporary fixture directory.
        cc: Selected C compiler.
    """
    if os.name == "nt":
        return
    private = work / "inaccessible"
    private.mkdir()
    target = private / "target"
    target.write_bytes(b"private")
    private.chmod(0)
    try:
        try:
            target.stat()
        except PermissionError:
            probe = compile_probe(work, cc, "permission_probe")
            require_success([str(probe), str(work), str(target)])
        else:
            print("filesystem_native_test: permission fixture bypassed by host privileges")
    finally:
        private.chmod(0o700)


def require_directory_failures(work: Path, cc: str) -> None:
    """Trace generated L1 cleanup after partial iteration and native close failures.

    Args:
        work: Owned temporary build directory.
        cc: Selected C compiler.

    Raises:
        AssertionError: Compilation, captured errors, or ownership analysis fails.
    """
    if os.name == "nt":
        return
    library = work / "injected-runtime"
    library.mkdir()
    objects = []
    for name in (*RUNTIME_SOURCES, "dea_rt_trace.c", "directory_failures.c"):
        source = FIXTURES / name if name == "directory_failures.c" else RUNTIME_ROOT / "src" / name
        obj = library / (name + ".o")
        require_success([
            cc, "-std=c99", "-DDEA_TRACE_ARC", "-DDEA_TRACE_MEMORY",
            "-DDEA_FS_READDIR=fs_dir_probe_readdir", "-DDEA_FS_CLOSEDIR=fs_dir_probe_closedir",
            f"-I{RUNTIME_ROOT / 'include'}", f"-I{RUNTIME_ROOT / 'internal'}",
            "-c", str(source), "-o", str(obj),
        ])
        objects.append(str(obj))
    archiver = shutil.which("ar")
    assert archiver, "injected runtime needs an archiver"
    require_success([archiver, "rcs", str(library / "libdea_rt_traced.a"), *objects])
    compiler = compiler_path()
    exe = work / "directory-failures"
    require_success([
        str(compiler), "--project-root", str(FIXTURES), "--c-compiler", cc,
        "--no-managed-stdlib", "--sys-root", str(L1_ROOT / "compiler/shared/l1/stdlib"),
        "--runtime-include", str(RUNTIME_ROOT / "include"), "--runtime-lib", str(library),
        "--no-auto-prepare", "--trace-arc", "--trace-memory",
        "--build", "directory_failure_main", "-o", str(exe),
    ])
    result = require_success([str(exe)])
    assert result.stdout == "directory_failure_main: PASS\n", result.stdout
    trace = work / "directory-failures.trace"
    trace.write_text(result.stderr, encoding="utf-8")
    report = require_success([
        sys.executable, str(L1_ROOT / "compiler/scripts/check_trace_log.py"),
        str(trace), "--triage", "--max-details", "5",
    ])
    assert "leaked_object_ptrs=0" in report.stdout and "leaked_string_ptrs=0" in report.stdout, report.stdout
    assert "[l0][mem]" in result.stderr and "[l0][arc]" in result.stderr


def require_generated(work: Path, cc: str) -> None:
    """Run public L1 APIs in all runtime modes and host-specific resolution cases.

    Args:
        work: Owned temporary build and fixture directory.
        cc: Selected C compiler.
    """
    compiler = compiler_path()
    for mode, flags in (
        ("checked", []), ("basic", ["--check-basic"]), ("unchecked", ["--unchecked"]),
    ):
        for module in ("filesystem_main", "directory_main"):
            exe = work / (f"{module}-{mode}" + (".exe" if os.name == "nt" else ""))
            require_success([
                str(compiler), "--project-root", str(FIXTURES), "--c-compiler", cc,
                *native_driver_args(compiler, cc), *flags, "--build", module, "-o", str(exe),
            ])
            result = require_success([str(exe)])
            assert result.stdout == f"{module}: PASS\n", result.stdout
            if module != "filesystem_main" or mode != "checked":
                continue
            fixture = work / "generated space caf\u00e9"
            fixture.mkdir()
            target, other, hard = fixture / "target", fixture / "different", fixture / "hard"
            target.write_bytes(b"target")
            other.write_bytes(b"other")
            os.link(target, hard)
            require_success([str(exe), "same", path_argument(target), path_argument(hard), "yes"])
            require_success([str(exe), "same", path_argument(target), path_argument(other), "no"])
            with (fixture / "wide").open("wb") as stream:
                stream.truncate(4294967313)
            require_success([str(exe), "wide", path_argument(fixture / "wide")])
            for spelling in (str(target), str(fixture / "." / "target")):
                result = subprocess.run([str(exe), "canonical", path_argument(spelling)], cwd=L1_ROOT, capture_output=True, check=False)
                assert result.returncode == 0, result.stderr
                # Canonical Win32 results deliberately retain the extended path prefix.
                actual = result.stdout.rstrip(b"\r\n")
                if os.name == "nt":
                    expected = windows_extended(str(target.resolve())).encode("utf-8")
                    assert actual.replace(b"\\", b"/") == expected.replace(b"\\", b"/")
                else:
                    assert actual == os.fsencode(target.resolve())
            if os.name == "nt":
                # Native GetFullPathNameW semantics: mixed separators, drive-relative,
                # rooted current-drive paths, and an unqueried UNC share.
                cwd = str(L1_ROOT)
                drive = ntpath.splitdrive(cwd)[0]
                cases = ["missing space/child", "\\missing space\\child",
                         "\\\\server\\share\\missing space", str(fixture).replace("\\", "/") + "\\missing"]
                if len(drive) == 2 and drive[1] == ":":
                    cases.append(drive + "missing")
                for spelling in cases:
                    result = subprocess.run([str(exe), "absolute", path_argument(spelling)], cwd=L1_ROOT, capture_output=True, check=False)
                    assert result.returncode == 0, result.stderr
                    actual = result.stdout.decode("utf-8").rstrip("\r\n").replace("\\", "/")
                    expected = ntpath.abspath(ntpath.join(cwd, spelling)).replace("\\", "/")
                    assert actual == expected, (actual, expected)
                    assert actual != ntpath.join(cwd, "different").replace("\\", "/")
                verbatim = windows_extended(str(fixture)) + "\\literal.\\child"
                require_success([str(exe), "create-all", path_argument(verbatim)])
                assert os.path.isdir(verbatim), "verbatim components changed during recursive creation"
                assert not (fixture / "literal").exists(), "recursive creation normalized a verbatim component"
                # Explicit extended spelling is also needed for fixture cleanup.
                os.rmdir(verbatim)
                os.rmdir(windows_extended(str(fixture)) + "\\literal.")
            else:
                # POSIX backslash and non-UTF-8 bytes remain literal filename bytes.
                for name in (b"literal\\name", b"invalid-\xff"):
                    raw = os.fsencode(fixture) + b"/" + name
                    try:
                        with open(raw, "wb") as stream:
                            stream.write(b"bytes")
                    except OSError as error:
                        created = False
                        print(f"filesystem_native_test: host rejected filename bytes {name!r}: {error.errno}")
                    else:
                        created = True
                    result = subprocess.run([str(exe), "absolute", path_argument(raw)], cwd=L1_ROOT, capture_output=True, check=False)
                    assert result.returncode == 0 and result.stdout == raw + b"\n", result.stderr
                    if not created:
                        continue
                    result = subprocess.run([str(exe), "canonical", path_argument(raw)], cwd=L1_ROOT, capture_output=True, check=False)
                    assert result.returncode == 0 and result.stdout == os.path.realpath(raw) + b"\n", result.stderr
            # Enumerate the same owned fixture through trailing separators, native
            # rooted paths, and bare drive-relative paths on actual Windows hosts.
            listing = work / ("directory-listing.exe" if os.name == "nt" else "directory-listing")
            require_success([
                str(compiler), "--project-root", str(FIXTURES), "--c-compiler", cc,
                *native_driver_args(compiler, cc), "--build", "directory_main", "-o", str(listing),
            ])
            (fixture / "caf\u00e9").touch()
            paths = [str(fixture), str(fixture) + os.sep]
            if os.name == "nt":
                paths += [windows_extended(str(fixture)), windows_extended(str(fixture)) + "\\"]
                drive, rooted = ntpath.splitdrive(str(fixture))
                if len(drive) == 2 and drive[1] == ":":
                    paths += [drive, rooted]
            expected = sorted(name.encode("utf-8") if os.name == "nt" else os.fsencode(name) for name in os.listdir(fixture))
            for spelling in paths:
                result = subprocess.run([str(listing), path_argument(spelling)], cwd=fixture, capture_output=True, check=False)
                assert result.returncode == 0, result.stderr
                assert result.stdout.splitlines() == expected, (spelling, result.stdout, expected)


def main() -> int:
    """Verify runtime interfaces and actual generated programs.

    Returns:
        Zero after all checks pass.
    """
    cc = runtime_c_compiler()
    print(require_success([cc, "--version"]).stdout.splitlines()[0])
    with tempfile.TemporaryDirectory(prefix="l1-filesystem-") as raw:
        work = Path(raw)
        require_native(work, cc)
        require_permissions(work, cc)
        require_directory_failures(work, cc)
        require_generated(work, cc)
    print("filesystem_native_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
