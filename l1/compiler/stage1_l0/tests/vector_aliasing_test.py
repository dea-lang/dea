#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Bulk byte-vector aliasing regressions across L1 runtime modes."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
RUNTIME_ROOT = L1_ROOT / "compiler" / "shared" / "runtime"
RUNTIME_SOURCES = (
    "dea_rt_panic.c",
    "dea_rt_sys.c",
    "dea_rt_math.c",
    "dea_rt_rand.c",
    "dea_rt_string.c",
    "dea_rt_alloc.c",
    "dea_rt_io.c",
    "dea_rt_hash.c",
    "dea_rt_time.c",
)
RANGE_FAILURE = "Source range out of bounds in vec_push_bytes"
OVERLAP_FAILURE = "Source range overlaps backing storage in vec_push_bytes"


def resolve_tool(base: Path) -> Path:
    """Return a host-compatible launcher path for one tool base path."""

    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
        return base.with_suffix(".cmd")
    return base


def compiler_path() -> Path:
    """Return the repo-local L1 Stage 1 compiler launcher."""

    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def valid_source(module_name: str) -> str:
    """Return semantic coverage for aliased, external, and no-op pushes."""

    return f"""
        module {module_name};

        import std.assert;
        import std.vector;
        import sys.memory;

        unsafe func exercise() -> int {{
            let base_growth = vec_create(sizeof(byte), 2);
            vec_push_byte(base_growth, 'A');
            vec_push_byte(base_growth, 'B');
            let base_source = base_growth.arr.data as byte*;
            vec_push_bytes(base_growth, base_source, 2);
            assert(vec_size(base_growth) == 4, "base growth length mismatch");
            assert(*(vec_get(base_growth, 2) as byte*) == 'A', "base growth byte 0 mismatch");
            assert(*(vec_get(base_growth, 3) as byte*) == 'B', "base growth byte 1 mismatch");
            vec_free(base_growth);

            let interior_growth = vec_create(sizeof(byte), 4);
            vec_push_byte(interior_growth, 'A');
            vec_push_byte(interior_growth, 'B');
            vec_push_byte(interior_growth, 'C');
            vec_push_byte(interior_growth, 'D');
            let interior_source = vec_get(interior_growth, 1) as byte*;
            vec_push_bytes(interior_growth, interior_source, 2);
            assert(vec_size(interior_growth) == 6, "interior growth length mismatch");
            assert(*(vec_get(interior_growth, 4) as byte*) == 'B', "interior growth byte 0 mismatch");
            assert(*(vec_get(interior_growth, 5) as byte*) == 'C', "interior growth byte 1 mismatch");
            vec_free(interior_growth);

            let base_no_growth = vec_create(sizeof(byte), 8);
            vec_push_byte(base_no_growth, 'M');
            vec_push_byte(base_no_growth, 'N');
            let base_no_growth_source = base_no_growth.arr.data as byte*;
            vec_push_bytes(base_no_growth, base_no_growth_source, 2);
            assert(vec_size(base_no_growth) == 4, "base no-growth length mismatch");
            assert(*(vec_get(base_no_growth, 2) as byte*) == 'M', "base no-growth byte 0 mismatch");
            assert(*(vec_get(base_no_growth, 3) as byte*) == 'N', "base no-growth byte 1 mismatch");
            vec_free(base_no_growth);

            let interior_no_growth = vec_create(sizeof(byte), 8);
            vec_push_byte(interior_no_growth, 'W');
            vec_push_byte(interior_no_growth, 'X');
            vec_push_byte(interior_no_growth, 'Y');
            vec_push_byte(interior_no_growth, 'Z');
            let interior_no_growth_source = vec_get(interior_no_growth, 1) as byte*;
            vec_push_bytes(interior_no_growth, interior_no_growth_source, 2);
            assert(vec_size(interior_no_growth) == 6, "interior no-growth length mismatch");
            assert(*(vec_get(interior_no_growth, 4) as byte*) == 'X', "interior no-growth byte 0 mismatch");
            assert(*(vec_get(interior_no_growth, 5) as byte*) == 'Y', "interior no-growth byte 1 mismatch");
            vec_free(interior_no_growth);

            let external = vec_create(sizeof(byte), 3);
            vec_push_byte(external, 'Q');
            vec_push_byte(external, 'R');
            vec_push_byte(external, 'S');
            let destination = vec_create(sizeof(byte), 1);
            vec_push_bytes(destination, external.arr.data as byte*, 3);
            assert(vec_size(destination) == 3, "external length mismatch");
            assert(*(vec_get(destination, 0) as byte*) == 'Q', "external byte 0 mismatch");
            assert(*(vec_get(destination, 1) as byte*) == 'R', "external byte 1 mismatch");
            assert(*(vec_get(destination, 2) as byte*) == 'S', "external byte 2 mismatch");
            vec_free(destination);
            vec_free(external);

            let noop = vec_create(sizeof(byte), 0);
            let stale: void* = rt_alloc(1) as void*;
            rt_free(stale);
            vec_push_bytes(noop, stale as byte*, 0);
            assert(vec_size(noop) == 0, "zero-count push changed length");
            vec_free(noop);
            return 0;
        }}

        func main() -> int {{
            return exercise();
        }}
    """


def invalid_source(module_name: str, *, empty: bool) -> str:
    """Return one backing-derived non-logical source-range fixture."""

    if empty:
        setup = """
            let vec = vec_create(sizeof(byte), 0);
            let source = vec.arr.data as byte*;
            vec_push_bytes(vec, source, 1);
        """
    else:
        setup = """
            let vec = vec_create(sizeof(byte), 4);
            vec_push_byte(vec, 'A');
            vec_push_byte(vec, 'B');
            let source = vec_get(vec, 1) as byte*;
            vec_push_bytes(vec, source, 2);
        """
    return f"""
        module {module_name};

        import std.vector;

        unsafe func exercise() -> int {{
            {setup}
            return 0;
        }}

        func main() -> int {{
            return exercise();
        }}
    """


def left_overlap_source(module_name: str) -> str:
    """Return a source range that starts below and overlaps vector backing."""

    return f"""
        module {module_name};

        import std.array;
        import std.vector;
        import sys.memory;

        unsafe func exercise() -> int {{
            let storage = rt_alloc(9) as void*;
            let backing = rt_array_element(storage, 1, 4);
            let arr = new ArrayBase(4, sizeof(byte), backing);
            let vec = new VectorBase(arr, 2);
            let source = rt_array_element(storage, 1, 3) as byte*;
            vec_push_bytes(vec, source, 2);
            return 0;
        }}

        func main() -> int {{
            return exercise();
        }}
    """


def run_source(
    module_name: str,
    source: str,
    mode_flags: list[str],
) -> subprocess.CompletedProcess[str]:
    """Compile and run one temporary L1 source module."""

    with tempfile.TemporaryDirectory(prefix="l1_vector_aliasing.") as tmp:
        project_root = Path(tmp)
        (project_root / f"{module_name}.l1").write_text(
            textwrap.dedent(source), encoding="utf-8"
        )
        return subprocess.run(
            [
                str(compiler_path()),
                "--project-root",
                str(project_root),
                "--run",
                *mode_flags,
                module_name,
            ],
            cwd=L1_ROOT,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )


def require_success(module_name: str, source: str, mode_flags: list[str]) -> None:
    """Require one vector fixture to run successfully."""

    completed = run_source(module_name, source, mode_flags)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise AssertionError(f"{module_name} exited with {completed.returncode}")


def require_range_failure(module_name: str, source: str, mode_flags: list[str]) -> None:
    """Require one vector fixture to reject a non-logical self-range."""

    completed = run_source(module_name, source, mode_flags)
    output = completed.stdout + completed.stderr
    if completed.returncode == 0 or RANGE_FAILURE not in output:
        sys.stderr.write(output)
        raise AssertionError(f"{module_name} did not report {RANGE_FAILURE!r}")


def require_overlap_failure(module_name: str, source: str, mode_flags: list[str]) -> None:
    """Require rejection when an external-looking source crosses into backing."""

    completed = run_source(module_name, source, mode_flags)
    output = completed.stdout + completed.stderr
    if completed.returncode == 0 or OVERLAP_FAILURE not in output:
        sys.stderr.write(output)
        raise AssertionError(f"{module_name} did not report {OVERLAP_FAILURE!r}")


def asan_compilers() -> list[str]:
    """Return distinct GNU-compatible compiler candidates for ASan probes."""

    candidates = [
        os.environ.get("L1_ASAN_CC", "").strip(),
        os.environ.get("L1_RUNTIME_CC", "").strip(),
        os.environ.get("L1_CC", "").strip(),
        "clang",
        "gcc",
        "cc",
    ]
    resolved: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        path = shutil.which(candidate)
        if path is None:
            continue
        name = Path(path).name.lower().removesuffix(".exe")
        if "gcc" not in name and "clang" not in name and name != "cc":
            continue
        key = str(Path(path).resolve())
        if key not in seen:
            seen.add(key)
            resolved.append(path)
    return resolved


def find_asan_compiler(work_dir: Path) -> str | None:
    """Return the first compiler whose ASan runtime compiles and runs."""

    source = work_dir / "asan_support.c"
    executable = work_dir / ("asan_support.exe" if os.name == "nt" else "asan_support")
    source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    unsupported: list[str] = []
    for compiler in asan_compilers():
        compiled = subprocess.run(
            [compiler, "-fsanitize=address", str(source), "-o", str(executable)],
            capture_output=True,
            text=True,
            check=False,
        )
        if compiled.returncode != 0:
            unsupported.append(f"{compiler}: {compiled.stderr.strip()}")
            continue
        env = os.environ.copy()
        env["ASAN_OPTIONS"] = "detect_leaks=0"
        try:
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, env=env, check=False
            )
        except OSError as error:
            unsupported.append(f"{compiler}: ASan runtime did not launch: {error}")
            continue
        if executed.returncode == 0:
            return compiler
        detail = executed.stderr.strip() or executed.stdout.strip()
        unsupported.append(
            f"{compiler}: ASan runtime exited {executed.returncode}: {detail}"
        )
    detail = " | ".join(unsupported) if unsupported else "no compatible compiler found"
    print(f"vector_aliasing_test: SKIP ASan: {detail}")
    return None


def require_asan_success(mode_name: str, mode_flags: list[str]) -> None:
    """Build and run the growth fixture plus runtime with AddressSanitizer."""

    with tempfile.TemporaryDirectory(prefix=f"l1_vector_aliasing_asan_{mode_name}.") as tmp:
        work_dir = Path(tmp)
        compiler = find_asan_compiler(work_dir)
        if compiler is None:
            return
        archiver = shutil.which(os.environ.get("AR", "ar"))
        if archiver is None:
            raise AssertionError("ASan-capable compiler found but no archiver is available")
        module_name = f"vector_aliasing_asan_{mode_name}"
        (work_dir / f"{module_name}.l1").write_text(
            textwrap.dedent(valid_source(module_name)), encoding="utf-8"
        )
        executable = work_dir / (
            f"{module_name}.exe" if os.name == "nt" else module_name
        )
        runtime_lib_dir = work_dir / "lib"
        runtime_lib_dir.mkdir()
        runtime_objects: list[Path] = []
        runtime_flags = [
            "-std=c99",
            "-O0",
            "-g",
            "-fsanitize=address",
            "-fno-omit-frame-pointer",
        ]
        if mode_name == "unchecked":
            runtime_flags.append("-DDEA_RT_UNCHECKED=1")
        for source_name in RUNTIME_SOURCES:
            source_path = RUNTIME_ROOT / "src" / source_name
            object_path = work_dir / f"{Path(source_name).stem}.o"
            compiled_runtime = subprocess.run(
                [
                    compiler,
                    *runtime_flags,
                    f"-I{RUNTIME_ROOT / 'include'}",
                    f"-I{RUNTIME_ROOT / 'internal'}",
                    "-c",
                    str(source_path),
                    "-o",
                    str(object_path),
                ],
                cwd=L1_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if compiled_runtime.returncode != 0:
                sys.stderr.write(compiled_runtime.stdout)
                sys.stderr.write(compiled_runtime.stderr)
                raise AssertionError(f"{source_name} ASan compilation failed")
            runtime_objects.append(object_path)

        archive_name = (
            "libdea_rt_unchecked.a" if mode_name == "unchecked" else "libdea_rt.a"
        )
        archive = runtime_lib_dir / archive_name
        archived = subprocess.run(
            [archiver, "rcs", str(archive), *(str(path) for path in runtime_objects)],
            cwd=L1_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if archived.returncode != 0:
            sys.stderr.write(archived.stdout)
            sys.stderr.write(archived.stderr)
            raise AssertionError(f"{module_name} ASan runtime archive failed")

        build_env = os.environ.copy()
        build_env["L1_CFLAGS"] = " ".join(runtime_flags)
        built = subprocess.run(
            [
                str(compiler_path()),
                "--build",
                *mode_flags,
                "--c-compiler",
                compiler,
                "--link-arg=-fsanitize=address",
                "--runtime-include",
                str(RUNTIME_ROOT / "include"),
                "--runtime-lib",
                str(runtime_lib_dir),
                "--project-root",
                str(work_dir),
                "--output",
                str(executable),
                module_name,
            ],
            cwd=L1_ROOT,
            capture_output=True,
            text=True,
            env=build_env,
            check=False,
        )
        if built.returncode != 0:
            sys.stderr.write(built.stdout)
            sys.stderr.write(built.stderr)
            raise AssertionError(f"{module_name} ASan build failed")

        env = os.environ.copy()
        env["ASAN_OPTIONS"] = "abort_on_error=1:detect_leaks=0:halt_on_error=1"
        if mode_name == "checked":
            env["DEA_RT_QUARANTINE_MAX_COUNT"] = "4096"
        executed = subprocess.run(
            [str(executable)],
            cwd=L1_ROOT,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if executed.returncode != 0:
            sys.stderr.write(executed.stdout)
            sys.stderr.write(executed.stderr)
            raise AssertionError(f"{module_name} ASan execution failed")


def main() -> int:
    """Run semantic, contract-failure, and sanitizer regressions."""

    for mode_name, mode_flags in (("checked", []), ("unchecked", ["--unchecked"])):
        module_name = f"vector_aliasing_{mode_name}"
        require_success(module_name, valid_source(module_name), mode_flags)
        for case_name, empty in (("logical_tail", False), ("empty_backing", True)):
            failure_name = f"vector_aliasing_{case_name}_{mode_name}"
            require_range_failure(
                failure_name,
                invalid_source(failure_name, empty=empty),
                mode_flags,
            )
        overlap_name = f"vector_aliasing_left_overlap_{mode_name}"
        require_overlap_failure(
            overlap_name,
            left_overlap_source(overlap_name),
            mode_flags,
        )
        require_asan_success(mode_name, mode_flags)
    print("vector_aliasing_test: all tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
