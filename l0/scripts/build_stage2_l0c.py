#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Build the repo-local Stage 2 compiler artifact."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import subprocess
import sys

from dist_tools_lib import (
    DeaBuildLayout,
    normalize_dea_build_dir,
    source_tree_stage1_command,
    stage2_build_info_overlay,
    write_stage2_wrapper,
)

DEFAULT_COMPILER_RT_CHECK_BASIC = "1"
DEFAULT_COMPILER_RT_QUARANTINE_MAX_COUNT = "256"
COMPILER_RT_CHECK_BASIC_ENV = "L0_COMPILER_RT_CHECK_BASIC"
COMPILER_RT_QUARANTINE_MAX_COUNT_ENV = "L0_COMPILER_RT_QUARANTINE_MAX_COUNT"
USER_RT_CHECK_BASIC_ENV = "L0_RT_CHECK_BASIC"
USER_RT_UNCHECKED_ENV = "L0_RT_UNCHECKED"
USER_RT_QUARANTINE_MAX_BYTES_ENV = "L0_RT_QUARANTINE_MAX_BYTES"
USER_RT_QUARANTINE_MAX_COUNT_ENV = "L0_RT_QUARANTINE_MAX_COUNT"
RT_CHECK_BASIC_DEFINE = "L0_RT_CHECK_BASIC"
RT_UNCHECKED_DEFINE = "L0_RT_UNCHECKED"
RT_QUARANTINE_MAX_BYTES_DEFINE = "_RT_QUARANTINE_MAX_BYTES"
RT_QUARANTINE_MAX_COUNT_DEFINE = "_RT_QUARANTINE_MAX_COUNT"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Build the repo-local Stage 2 compiler artifact.")
    return parser.parse_args()


def _append_cflag(cflags: str, flag: str) -> str:
    """Append one C flag to an existing flag string."""

    return f"{cflags} {flag}".strip()


def _has_c_define(cflags: str, name: str) -> bool:
    """Return whether a raw C flag string defines ``name``."""

    prefix = f"-D{name}"
    words = cflags.split()
    for index, word in enumerate(words):
        if word == prefix or word.startswith(f"{prefix}="):
            return True
        if word == "-D" and index + 1 < len(words):
            value = words[index + 1]
            if value == name or value.startswith(f"{name}="):
                return True
    return False


def compiler_runtime_build_env(source_env: Mapping[str, str]) -> dict[str, str]:
    """Return an env for building compiler binaries with checked-runtime defaults."""

    build_env = dict(source_env)
    cflags = build_env.get("L0_CFLAGS", "")

    raw_mode = _has_c_define(cflags, RT_CHECK_BASIC_DEFINE) or _has_c_define(cflags, RT_UNCHECKED_DEFINE)
    if not raw_mode:
        explicit_mode = False
        if build_env.get(USER_RT_UNCHECKED_ENV, "").strip():
            cflags = _append_cflag(cflags, f"-D{RT_UNCHECKED_DEFINE}")
            explicit_mode = True
        if build_env.get(USER_RT_CHECK_BASIC_ENV, "").strip():
            cflags = _append_cflag(cflags, f"-D{RT_CHECK_BASIC_DEFINE}")
            explicit_mode = True
        if not explicit_mode and build_env.get(
            COMPILER_RT_CHECK_BASIC_ENV,
            DEFAULT_COMPILER_RT_CHECK_BASIC,
        ).strip():
            cflags = _append_cflag(cflags, f"-D{RT_CHECK_BASIC_DEFINE}")

    if not _has_c_define(cflags, RT_QUARANTINE_MAX_BYTES_DEFINE):
        user_bytes = build_env.get(USER_RT_QUARANTINE_MAX_BYTES_ENV, "").strip()
        if user_bytes:
            cflags = _append_cflag(cflags, f"-D{RT_QUARANTINE_MAX_BYTES_DEFINE}={user_bytes}")

    if not _has_c_define(cflags, RT_QUARANTINE_MAX_COUNT_DEFINE):
        user_count = build_env.get(USER_RT_QUARANTINE_MAX_COUNT_ENV, "").strip()
        compiler_count = build_env.get(
            COMPILER_RT_QUARANTINE_MAX_COUNT_ENV,
            DEFAULT_COMPILER_RT_QUARANTINE_MAX_COUNT,
        ).strip()
        selected_count = user_count or compiler_count
        if selected_count:
            cflags = _append_cflag(cflags, f"-D{RT_QUARANTINE_MAX_COUNT_DEFINE}={selected_count}")

    if cflags != build_env.get("L0_CFLAGS", ""):
        build_env["L0_CFLAGS"] = cflags
    return build_env


def build_stage2_artifact(
        layout: DeaBuildLayout,
        *,
        keep_c: bool,
        extra_project_roots: Sequence[str] | None = None,
        extra_env: Mapping[str, str] | None = None,
) -> tuple[Path, Path, Path]:
    """Build the repo-local Stage 2 compiler artifact for one validated layout."""

    layout.bin_dir.mkdir(parents=True, exist_ok=True)

    native_bin = layout.bin_dir / "l0c-stage2.native"
    c_output = layout.bin_dir / "l0c-stage2.c"

    build_args = [*source_tree_stage1_command(layout.repo_root), "--build"]
    if keep_c:
        build_args.append("--keep-c")
    else:
        c_output.unlink(missing_ok=True)
    for root in extra_project_roots or ():
        build_args.extend(["-P", root])
    build_args.extend(["-P", "compiler/stage2_l0/src", "-o", str(native_bin), "l0c"])

    build_env = os.environ.copy()
    if extra_env is not None:
        build_env.update(extra_env)
    build_env = compiler_runtime_build_env(build_env)
    build_env["L0_HOME"] = str(layout.repo_root / "compiler")
    build_env.pop("L0_SYSTEM", None)
    build_env.pop("L0_RUNTIME_INCLUDE", None)
    build_env.pop("L0_RUNTIME_LIB", None)

    subprocess.run(build_args, cwd=layout.repo_root, env=build_env, check=True)

    if not keep_c:
        c_output.unlink(missing_ok=True)

    wrapper_bin = write_stage2_wrapper(layout)
    native_bin.chmod(native_bin.stat().st_mode | 0o111)
    return wrapper_bin, native_bin, c_output


def main() -> int:
    """Program entrypoint."""

    parse_args()

    dea_build_dir_text = os.environ.get("DEA_BUILD_DIR", "build/dea")
    keep_c = os.environ.get("KEEP_C", "0") == "1"

    try:
        layout = normalize_dea_build_dir(dea_build_dir_text)
    except ValueError as exc:
        print(f"build-stage2-l0c: {exc}", file=sys.stderr)
        return 1

    build_root = layout.repo_root / "build"
    build_root.mkdir(parents=True, exist_ok=True)
    try:
        with stage2_build_info_overlay(layout.repo_root, os.environ.copy(), temp_parent=build_root) as overlay:
            build_env = compiler_runtime_build_env(overlay.build_env)
            wrapper_bin, native_bin, c_output = build_stage2_artifact(
                layout,
                keep_c=keep_c,
                extra_project_roots=[str(overlay.overlay_root)],
                extra_env=build_env,
            )
    except ValueError as exc:
        print(f"build-stage2-l0c: {exc}", file=sys.stderr)
        return 1

    print(f"build-stage2-l0c: wrote {wrapper_bin}")
    print(f"build-stage2-l0c: wrote {native_bin}")
    if keep_c:
        print(f"build-stage2-l0c: wrote {c_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
