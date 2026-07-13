#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression checks for content-sensitive L1 runtime build configuration."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"


def require_runtime_build(build_dir: Path, quarantine_count: int | None = None) -> str:
    """Build runtime archives in an isolated directory and return make output."""

    compiler = next(
        (candidate for name in ("clang", "gcc", "cc") if (candidate := shutil.which(name))),
        None,
    )
    if compiler is None:
        raise AssertionError("runtime build-config test requires a C compiler")

    command = [
        "make",
        "runtime",
        f"L1_BUILD_DIR={build_dir}",
        f"L1_RUNTIME_CC={compiler}",
        "L1_TCC_OBJ_CC=",
    ]
    if quarantine_count is not None:
        command.append(f"L1_RT_QUARANTINE_MAX_COUNT={quarantine_count}")

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


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        build_dir = Path(tmp) / "dea"

        first = require_runtime_build(build_dir)
        if "runtime/default/dea_rt_alloc.o" not in first:
            raise AssertionError(f"initial runtime build did not compile default objects:\n{first}")

        default_stamp = build_dir / "runtime" / "default" / ".build-config"
        unchecked_stamp = build_dir / "runtime" / "unchecked" / ".build-config"
        default_before = default_stamp.read_text(encoding="utf-8")
        unchecked_before = unchecked_stamp.read_text(encoding="utf-8")

        identical = require_runtime_build(build_dir)
        assert_no_object_rebuild(identical, "identical runtime configuration")
        if default_stamp.read_text(encoding="utf-8") != default_before:
            raise AssertionError("identical build rewrote the default config stamp")

        changed = require_runtime_build(build_dir, quarantine_count=17)
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

        repeated_changed = require_runtime_build(build_dir, quarantine_count=17)
        assert_no_object_rebuild(repeated_changed, "repeated changed runtime configuration")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
