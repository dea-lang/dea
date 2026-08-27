#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression checks for content-sensitive L1 runtime build configuration."""

from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"


def resolve_runtime_compiler() -> str:
    """Resolve the configured runtime compiler without changing compiler families."""

    configured = os.environ.get("L1_RUNTIME_CC", "").strip()
    if not configured:
        configured = os.environ.get("L1_CC", "").strip()
    if configured:
        compiler = shutil.which(configured)
        if compiler is None:
            raise AssertionError(f"configured runtime compiler was not found: {configured}")
        return compiler

    compiler = next(
        (candidate for name in ("clang", "gcc", "cc") if (candidate := shutil.which(name))),
        None,
    )
    if compiler is not None:
        return compiler

    configured = os.environ.get("CC", "").strip()
    if configured:
        compiler = shutil.which(configured)
        if compiler is not None:
            return compiler
    raise AssertionError("runtime build-config test requires a C compiler")


def compiler_path_for_shell_regression(compiler: str, tmp_dir: Path) -> tuple[str, Path | None]:
    """Return a compiler path that exercises native Windows shell escaping."""

    if os.name == "nt":
        return compiler, None

    alias = tmp_dir / rf"D:\a\_temp\msys64\ucrt64\bin\{Path(compiler).name}"
    invocation_marker = tmp_dir / "selected-compiler-invoked"
    alias.write_text(
        f"#!/bin/sh\n: > {shlex.quote(str(invocation_marker))}\nexec {shlex.quote(compiler)} \"$@\"\n",
        encoding="utf-8",
    )
    alias.chmod(0o755)
    return str(alias), invocation_marker


def build_dir_for_shell_regression(tmp_dir: Path) -> Path:
    """Return a build path that exercises native Windows shell escaping."""

    if os.name == "nt":
        return tmp_dir / "dea"
    return tmp_dir / r"windows\temp\dea"


def require_runtime_build(
    build_dir: Path,
    compiler: str,
    quarantine_count: int | None = None,
    compiler_runtime_overrides: dict[str, str] | None = None,
    force_newer: Path | None = None,
) -> str:
    """Build runtime archives in an isolated directory and return make output."""

    command = [
        "make",
        "runtime",
        f"L1_BUILD_DIR={build_dir}",
        f"L1_RUNTIME_CC={compiler}",
        "L1_TCC_OBJ_CC=",
    ]
    if quarantine_count is not None:
        command.append(f"L1_RT_QUARANTINE_MAX_COUNT={quarantine_count}")
    if force_newer is not None:
        force_path = force_newer
        if force_path.is_absolute() and force_path.is_relative_to(L1_ROOT):
            force_path = force_path.relative_to(L1_ROOT)
        command.extend(["-W", force_path.as_posix()])
    for name, value in sorted((compiler_runtime_overrides or {}).items()):
        command.append(f"{name}={value}")

    completed = subprocess.run(
        command,
        cwd=L1_ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        raise AssertionError(f"runtime build exited with {completed.returncode}")
    return completed.stdout


def assert_no_object_rebuild(output: str, label: str) -> None:
    """Assert make performed no object compilation or archive replacement."""

    if " -c \"compiler/shared/runtime/src/" in output or "ar rcs" in output:
        raise AssertionError(f"{label} unexpectedly rebuilt runtime artifacts:\n{output}")


def hash_file(path: Path) -> str:
    """Return the SHA-256 digest of one runtime artifact."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        build_dir = build_dir_for_shell_regression(tmp_dir)
        resolved_compiler = resolve_runtime_compiler()
        requested_compiler = os.environ.get("L1_RUNTIME_CC", "").strip()
        if requested_compiler:
            expected_compiler = shutil.which(requested_compiler)
            if expected_compiler is None:
                raise AssertionError(f"configured runtime compiler was not found: {requested_compiler}")
            if os.path.normcase(os.path.abspath(resolved_compiler)) != os.path.normcase(
                os.path.abspath(expected_compiler)
            ):
                raise AssertionError(
                    f"L1_RUNTIME_CC={requested_compiler} selected {resolved_compiler}, expected {expected_compiler}"
                )
        compiler, invocation_marker = compiler_path_for_shell_regression(resolved_compiler, tmp_dir)

        first = require_runtime_build(build_dir, compiler)
        if invocation_marker is not None and not invocation_marker.is_file():
            raise AssertionError("runtime build did not invoke the selected compiler wrapper")
        if "runtime/default/dea_rt_alloc.o" not in first:
            raise AssertionError(f"initial runtime build did not compile default objects:\n{first}")

        default_stamp = build_dir / "runtime" / "default" / ".build-config"
        unchecked_stamp = build_dir / "runtime" / "unchecked" / ".build-config"
        default_before = default_stamp.read_text(encoding="utf-8")
        unchecked_before = unchecked_stamp.read_text(encoding="utf-8")
        if f"compiler={compiler}\n" not in default_before:
            raise AssertionError("runtime config stamp did not record the selected compiler")

        identical = require_runtime_build(build_dir, compiler)
        assert_no_object_rebuild(identical, "identical runtime configuration")
        if default_stamp.read_text(encoding="utf-8") != default_before:
            raise AssertionError("identical build rewrote the default config stamp")

        changed = require_runtime_build(build_dir, compiler, quarantine_count=17)
        for variant in ("default", "traced", "check_basic"):
            expected = f"runtime/{variant}/dea_rt_alloc.o"
            if expected not in changed:
                raise AssertionError(f"changed tuning did not rebuild {variant}:\n{changed}")
        if "runtime/unchecked/dea_rt_alloc.o" in changed:
            raise AssertionError(f"checked-only tuning rebuilt unchecked objects:\n{changed}")
        if "_RT_QUARANTINE_MAX_COUNT=17" not in default_stamp.read_text(encoding="utf-8"):
            raise AssertionError("changed tuning value was not recorded in the default config stamp")
        if unchecked_stamp.read_text(encoding="utf-8") != unchecked_before:
            raise AssertionError("checked-only tuning rewrote the unchecked config stamp")

        repeated_changed = require_runtime_build(build_dir, compiler, quarantine_count=17)
        assert_no_object_rebuild(repeated_changed, "repeated changed runtime configuration")

        header_changed = require_runtime_build(
            build_dir,
            compiler,
            quarantine_count=17,
            force_newer=L1_ROOT / "compiler" / "shared" / "runtime" / "include" / "dea_rt.h",
        )
        for variant in ("default", "traced", "unchecked", "check_basic"):
            expected = f"runtime/{variant}/dea_rt_alloc.o"
            if expected not in header_changed:
                raise AssertionError(f"runtime header change did not rebuild {variant}:\n{header_changed}")

        repeated_header = require_runtime_build(build_dir, compiler, quarantine_count=17)
        assert_no_object_rebuild(repeated_header, "completed runtime header rebuild")

        runtime_artifacts = [
            build_dir / "runtime" / variant / ".build-config"
            for variant in ("default", "traced", "unchecked", "check_basic")
        ]
        runtime_artifacts.extend(
            build_dir / "lib" / name
            for name in (
                "libdea_rt.a",
                "libdea_rt_traced.a",
                "libdea_rt_unchecked.a",
                "libdea_rt_check_basic.a",
            )
        )
        artifacts_before = {path: hash_file(path) for path in runtime_artifacts}
        compiler_only = require_runtime_build(
            build_dir,
            compiler,
            quarantine_count=17,
            compiler_runtime_overrides={
                "L1_COMPILER_RT_CHECK_BASIC": "",
                "L1_COMPILER_RT_QUARANTINE_MAX_BYTES": "1024",
                "L1_COMPILER_RT_QUARANTINE_MAX_COUNT": "9",
                "L1_COMPILER_RT_UNCHECKED": "1",
            },
        )
        assert_no_object_rebuild(compiler_only, "compiler-only runtime configuration")
        artifacts_after = {path: hash_file(path) for path in runtime_artifacts}
        if artifacts_after != artifacts_before:
            raise AssertionError("compiler-only runtime variables changed L1 runtime archives or config stamps")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
