#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Build the repo-local L1 Stage 1 compiler artifact."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from dea_tooling.bootstrap import resolve_bootstrap_compiler
from dea_tooling.launchers import (
    render_repo_env_cmd_script,
    render_repo_env_script,
    render_repo_native_cmd_wrapper,
    render_repo_native_wrapper,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
MONOREPO_ROOT = REPO_ROOT.parent
DEFAULT_L1_BUILD_DIR = "build/dea"
L1_BUILD_DIR_ENV = "L1_BUILD_DIR"
L1_BOOTSTRAP_L0C_ENV = "L1_BOOTSTRAP_L0C"
L1_COMPILER_RT_CHECK_BASIC_ENV = "L1_COMPILER_RT_CHECK_BASIC"
L1_COMPILER_RT_UNCHECKED_ENV = "L1_COMPILER_RT_UNCHECKED"
L1_COMPILER_RT_QUARANTINE_MAX_BYTES_ENV = "L1_COMPILER_RT_QUARANTINE_MAX_BYTES"
L1_COMPILER_RT_QUARANTINE_MAX_COUNT_ENV = "L1_COMPILER_RT_QUARANTINE_MAX_COUNT"
DEFAULT_L1_COMPILER_RT_CHECK_BASIC = "1"
DEFAULT_L1_COMPILER_RT_QUARANTINE_MAX_COUNT = "256"
L0_RT_CHECK_BASIC_DEFINE = "L0_RT_CHECK_BASIC"
L0_RT_UNCHECKED_DEFINE = "L0_RT_UNCHECKED"
RT_QUARANTINE_MAX_BYTES_DEFINE = "_RT_QUARANTINE_MAX_BYTES"
RT_QUARANTINE_MAX_COUNT_DEFINE = "_RT_QUARANTINE_MAX_COUNT"


@dataclass(frozen=True)
class L1BuildLayout:
    """Resolved repo-local L1 build layout paths."""

    repo_root: Path
    build_dir: Path
    bin_dir: Path
    build_relative_from_repo: str
    repo_relative_from_bin: str


def is_windows_host() -> bool:
    """Return whether the current Python host is Windows."""

    return os.name == "nt"


def normalize_l1_build_dir(build_dir_text: str) -> L1BuildLayout:
    """Return the normalized repo-local L1 build layout."""

    if not build_dir_text.strip():
        raise ValueError("L1_BUILD_DIR must not be empty")

    raw_path = Path(build_dir_text)
    build_dir = raw_path.resolve(strict=False) if raw_path.is_absolute() else (REPO_ROOT / raw_path).resolve(strict=False)
    try:
        build_dir.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ValueError(f"L1_BUILD_DIR must resolve to a subdirectory inside the L1 repository: {build_dir}") from exc
    if build_dir == REPO_ROOT:
        raise ValueError(f"L1_BUILD_DIR must resolve to a subdirectory inside the L1 repository: {build_dir}")

    bin_dir = build_dir / "bin"
    return L1BuildLayout(
        repo_root=REPO_ROOT,
        build_dir=build_dir,
        bin_dir=bin_dir,
        build_relative_from_repo=os.path.relpath(build_dir, REPO_ROOT),
        repo_relative_from_bin=os.path.relpath(REPO_ROOT, bin_dir),
    )


def write_executable(path: Path, text: str) -> None:
    """Write one UTF-8 executable script."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def write_relative_alias(path: Path, target_name: str) -> None:
    """Create one repo-local alias, using a copy on Windows and a symlink elsewhere."""

    if path.exists() or path.is_symlink():
        path.unlink()

    if is_windows_host():
        target_path = path.parent / target_name
        shutil.copy2(target_path, path)
        cmd_path = path.with_suffix(".cmd")
        if cmd_path.exists() or cmd_path.is_symlink():
            cmd_path.unlink()
        target_cmd = path.parent / f"{target_name}.cmd"
        if target_cmd.exists():
            shutil.copy2(target_cmd, cmd_path)
    else:
        path.symlink_to(target_name)


def _append_cflag(cflags: str, flag: str) -> str:
    """Append one C flag to an existing flag string."""

    return f"{cflags} {flag}".strip()


def _has_c_define(cflags: str, name: str) -> bool:
    """Return whether raw C flags contain an exact preprocessor definition."""

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
    """Return an env for building the native L1 compiler runtime."""

    build_env = dict(source_env)
    cflags = build_env.get("L0_CFLAGS", "")

    raw_mode_selected = _has_c_define(cflags, L0_RT_CHECK_BASIC_DEFINE) or _has_c_define(
        cflags,
        L0_RT_UNCHECKED_DEFINE,
    )
    if not raw_mode_selected:
        unchecked = build_env.get(L1_COMPILER_RT_UNCHECKED_ENV, "").strip()
        basic = build_env.get(
            L1_COMPILER_RT_CHECK_BASIC_ENV,
            DEFAULT_L1_COMPILER_RT_CHECK_BASIC,
        ).strip()
        if unchecked:
            cflags = _append_cflag(cflags, f"-D{L0_RT_UNCHECKED_DEFINE}")
        elif basic:
            cflags = _append_cflag(cflags, f"-D{L0_RT_CHECK_BASIC_DEFINE}")

    tuning = (
        (
            RT_QUARANTINE_MAX_BYTES_DEFINE,
            build_env.get(L1_COMPILER_RT_QUARANTINE_MAX_BYTES_ENV, "").strip(),
        ),
        (
            RT_QUARANTINE_MAX_COUNT_DEFINE,
            build_env.get(
                L1_COMPILER_RT_QUARANTINE_MAX_COUNT_ENV,
                DEFAULT_L1_COMPILER_RT_QUARANTINE_MAX_COUNT,
            ).strip(),
        ),
    )
    for define_name, value in tuning:
        if value and not _has_c_define(cflags, define_name):
            cflags = _append_cflag(cflags, f"-D{define_name}={value}")

    if cflags != build_env.get("L0_CFLAGS", ""):
        build_env["L0_CFLAGS"] = cflags
    return build_env


def write_stage1_wrapper(layout: L1BuildLayout) -> Path:
    """Write the repo-local L1 Stage 1 wrapper pair."""

    path = layout.bin_dir / "l1c-stage1"
    runtime_build_dir = layout.build_relative_from_repo
    write_executable(
        path,
        render_repo_native_wrapper(
            repo_relative_from_bin=layout.repo_relative_from_bin,
            home_var_name="L1_HOME",
            native_name="l1c-stage1.native",
        ).replace(
            'export L1_HOME="${repo_root}/compiler"\n\nexec',
            f'export L1_HOME="${{repo_root}}/compiler"\nexport L1_BUILD_DIR="${{repo_root}}/{runtime_build_dir}"\n\nexec',
        ),
    )
    if is_windows_host():
        (layout.bin_dir / "l1c-stage1.cmd").write_text(
            render_repo_native_cmd_wrapper(
                repo_relative_from_bin=layout.repo_relative_from_bin,
                home_var_name="L1_HOME",
                native_name="l1c-stage1.native",
            ).replace(
                'set "L1_HOME=%REPO_ROOT%\\compiler"\n',
                f'set "L1_HOME=%REPO_ROOT%\\\\compiler"\nset "L1_BUILD_DIR=%REPO_ROOT%\\\\{runtime_build_dir.replace("/", "\\\\")}"\n',
            ),
            encoding="utf-8",
        )
    return path


def write_env_script(layout: L1BuildLayout) -> Path:
    """Write the repo-local L1 environment script pair."""

    path = layout.bin_dir / "l1-env.sh"
    runtime_build_dir = layout.build_relative_from_repo
    write_executable(
        path,
        render_repo_env_script(
            repo_relative_from_bin=layout.repo_relative_from_bin,
            build_relative_from_repo=layout.build_relative_from_repo,
            env_script_name="l1-env.sh",
            env_script_label="l1-env",
            home_var_name="L1_HOME",
            compiler_env_var="L1_CC",
        ).replace(
            'export L1_HOME="${REPO_ROOT}/compiler"\n',
            f'export L1_HOME="${{REPO_ROOT}}/compiler"\nexport L1_BUILD_DIR="${{REPO_ROOT}}/{runtime_build_dir}"\n',
        ),
    )
    if is_windows_host():
        (layout.bin_dir / "l1-env.cmd").write_text(
            render_repo_env_cmd_script(
                repo_relative_from_bin=layout.repo_relative_from_bin,
                env_script_label="l1-env",
                home_var_name="L1_HOME",
            ).replace(
                'set "L1_HOME=%REPO_ROOT%\\compiler"\n',
                f'set "L1_HOME=%REPO_ROOT%\\\\compiler"\nset "L1_BUILD_DIR=%REPO_ROOT%\\\\{runtime_build_dir.replace("/", "\\\\")}"\n',
            ),
            encoding="utf-8",
        )
    return path


def build_stage1_artifact(layout: L1BuildLayout, bootstrap_command: list[str], keep_c: bool) -> tuple[Path, Path, Path]:
    """Build the repo-local L1 Stage 1 compiler artifact."""

    layout.bin_dir.mkdir(parents=True, exist_ok=True)

    native_bin = layout.bin_dir / "l1c-stage1.native"
    c_output = layout.bin_dir / "l1c-stage1.c"

    build_args = [*bootstrap_command, "--build"]
    if keep_c:
        build_args.append("--keep-c")
    else:
        c_output.unlink(missing_ok=True)
    build_args.extend(["--project-root", "compiler/stage1_l0/src", "-o", str(native_bin), "l1c"])

    build_env = compiler_runtime_build_env(os.environ.copy())
    build_env["L0_HOME"] = str(MONOREPO_ROOT / "l0" / "compiler")
    build_env["L0_SYSTEM"] = str(MONOREPO_ROOT / "l0" / "compiler" / "shared" / "l0" / "stdlib")
    build_env.pop("L0_RUNTIME_INCLUDE", None)
    build_env.pop("L0_RUNTIME_LIB", None)

    subprocess.run(build_args, cwd=REPO_ROOT, env=build_env, check=True)

    if not keep_c:
        c_output.unlink(missing_ok=True)

    wrapper_bin = write_stage1_wrapper(layout)
    write_env_script(layout)
    native_bin.chmod(native_bin.stat().st_mode | 0o111)
    write_relative_alias(layout.bin_dir / "l1c", "l1c-stage1")
    return wrapper_bin, native_bin, c_output


def main() -> int:
    """Program entrypoint."""

    build_dir_text = os.environ.get(L1_BUILD_DIR_ENV, DEFAULT_L1_BUILD_DIR)
    keep_c = os.environ.get("KEEP_C", "0") == "1"

    try:
        layout = normalize_l1_build_dir(build_dir_text)
        _, bootstrap_command = resolve_bootstrap_compiler(
            override_text=os.environ.get(L1_BOOTSTRAP_L0C_ENV),
            default_path=MONOREPO_ROOT / "l0" / "build" / "dea" / "bin" / "l0c-stage2",
            env_var_name=L1_BOOTSTRAP_L0C_ENV,
            setup_hint="run `make -C l0 use-dev-stage2`",
        )
        wrapper_bin, native_bin, c_output = build_stage1_artifact(layout, bootstrap_command, keep_c)
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"build-stage1-l1c: {exc}", file=sys.stderr)
        return 1

    print(f"build-stage1-l1c: wrote {wrapper_bin}")
    print(f"build-stage1-l1c: wrote {native_bin}")
    print(f"build-stage1-l1c: wrote {layout.bin_dir / 'l1c'}")
    print(f"build-stage1-l1c: wrote {layout.bin_dir / 'l1-env.sh'}")
    if keep_c:
        print(f"build-stage1-l1c: wrote {c_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
