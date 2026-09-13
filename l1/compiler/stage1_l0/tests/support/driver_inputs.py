#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Explicit native inputs for tests outside the preparation integration lane."""

from pathlib import Path

from l1c_stage1_compile_only_test import (
    L1_ROOT,
    compiler_driver_name_matches,
    resolve_host_c_compiler,
)


def native_driver_args(
    compiler: Path, c_compiler: str | None = None, *, source: bool = True,
) -> list[str]:
    """Select repo sources and the Make-built runtime for a native consumer.

    TinyCC retains automatic selection of its compatible raw runtime objects.
    Preparation integration tests deliberately do not use this helper.

    Args:
        compiler: Repo-local compiler launcher, including custom build locations.
        c_compiler: Explicit host compiler, or the driver's normal selection.
        source: Include source/header roots for build/run, rather than link mode.

    Returns:
        Native-only CLI options for the test invocation.
    """

    selected_cc = c_compiler or resolve_host_c_compiler()
    if compiler_driver_name_matches(selected_cc, "tcc"):
        return []
    build_dir = compiler.parent.parent
    args = ["--runtime-lib", str(build_dir / "lib"), "--no-auto-prepare"]
    if source:
        args.extend([
            "--sys-root", str(L1_ROOT / "compiler/shared/l1/stdlib"),
            "--runtime-include", str(build_dir / "include"),
        ])
    return args
