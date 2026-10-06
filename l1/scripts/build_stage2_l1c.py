#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Build the repo-local self-hosted L1 compiler through an explicit compiler."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

from build_stage1_l1c import (
    REPO_ROOT, L1BuildLayout, normalize_l1_build_dir, provide_public_headers,
    write_env_script, write_executable,
    _has_c_define,
)
from dea_tooling.bootstrap import wrapper_command
from dea_tooling.launchers import render_repo_native_wrapper, render_repo_native_cmd_wrapper


SUPPORT_ROOT = REPO_ROOT / "compiler/stage1_l0/support"
STAGE2_SUPPORT_SOURCES = tuple(SUPPORT_ROOT / name for name in (
    "compiler_support.c", "preparation_support.c",
))


def host_compiler(env: dict[str, str]) -> str:
    """Resolve the exact native compiler used for support and generated sources.

    Args:
        env: Calling environment, with the driver's compiler-selection overrides.

    Returns:
        Resolved executable path, preserving spaces and native path separators.

    Raises:
        RuntimeError: No requested or supported fallback executable is available.
    """
    configured = env.get("L1_CC")
    candidates = [configured] if configured else ["tcc", "gcc", "clang", "cc", env.get("CC", "")]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError(f"native compiler not found: {configured or 'tcc/gcc/clang/cc'}")


def compiler_build_env(source: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Select compiler-only runtime mode and quarantine controls.

    Args:
        source: Calling environment; generated-program defaults remain untouched.

    Returns:
        Independent build environment and explicit runtime-mode CLI arguments.
    """
    env = dict(source)
    env["L1_HOME"] = str(REPO_ROOT / "compiler")
    for name in ("L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB"):
        env.pop(name, None)
    env["L1_CC"] = host_compiler(env)
    mode = []
    flags = env.get("L1_CFLAGS", "")
    if _has_c_define(flags, "DEA_RT_UNCHECKED"):
        mode = ["--unchecked"]
    elif _has_c_define(flags, "DEA_RT_CHECK_BASIC"):
        mode = ["--check-basic"]
    elif env.get("L1_COMPILER_RT_UNCHECKED", "").strip():
        mode = ["--unchecked"]
    elif env.get("L1_COMPILER_RT_CHECK_BASIC", "1").strip():
        mode = ["--check-basic"]
    for suffix, default in (("MAX_BYTES", ""), ("MAX_COUNT", "256")):
        value = env.get(f"L1_COMPILER_RT_QUARANTINE_{suffix}", default).strip()
        if value:
            define = f"_RT_QUARANTINE_{suffix}"
            if not _has_c_define(flags, define):
                flags = f"{flags} -D{define}={value}".strip()
    env["L1_CFLAGS"] = flags
    return env, mode


def build_support_objects(directory: Path, env: dict[str, str], *, preparation: bool = True) -> list[str]:
    """Build private support objects with one owner per bridge symbol.

    Args:
        directory: Command-owned output directory.
        env: Environment containing the selected compiler and C flags.
        preparation: Whether the consumer imports native preparation.

    Returns:
        Ordered foreign-object arguments for the L1 compiler.
    """
    directory.mkdir(parents=True, exist_ok=True)
    compiler = host_compiler(env)
    args = []
    cflags = [flag for flag in shlex.split(env.get("L1_CFLAGS", "")) if not flag.startswith("-Wl,")]
    for source in STAGE2_SUPPORT_SOURCES:
        if not preparation and source.name == "preparation_support.c":
            continue
        obj = directory / f"{source.stem}.o"
        subprocess.run([compiler, "-std=c99", *cflags,
                        "-c", str(source), "-o", str(obj)], env=env, check=True)
        args.extend(["--foreign-object", str(obj)])
    return args


def write_stage2_wrapper(layout: L1BuildLayout) -> Path:
    """Write relocatable POSIX and Windows launchers without selecting an alias.

    Args:
        layout: Validated repo-local output layout.

    Returns:
        Path to the POSIX launcher; Windows also receives its companion `.cmd` file.
    """
    path = layout.bin_dir / "l1c-stage2"
    text = render_repo_native_wrapper(
        repo_relative_from_bin=layout.repo_relative_from_bin,
        home_var_name="L1_HOME", native_name="l1c-stage2.native",
    ).replace('export L1_HOME="${repo_root}/compiler"\n',
              'export L1_HOME="${repo_root}/compiler"\n'
              f'export L1_BUILD_DIR="${{repo_root}}/{layout.build_relative_from_repo}"\n')
    write_executable(path, text)
    if os.name == "nt":
        text = render_repo_native_cmd_wrapper(
            repo_relative_from_bin=layout.repo_relative_from_bin,
            home_var_name="L1_HOME", native_name="l1c-stage2.native",
        )
        build_relative = layout.build_relative_from_repo.replace("/", "\\")
        text = text.replace('set "L1_HOME=%REPO_ROOT%\\compiler"\n',
                            'set "L1_HOME=%REPO_ROOT%\\compiler"\n'
                            f'set "L1_BUILD_DIR=%REPO_ROOT%\\{build_relative}"\n')
        path.with_suffix(".cmd").write_text(text, encoding="utf-8")
    return path


def build_compiler(
    compiler: Path, output: Path, env: dict[str, str], *, keep_c: bool = False,
    build_info_overlay: Path | None = None,
) -> None:
    """Build one Stage 2 generation using the supplied compiler and native inputs.

    Args:
        compiler: Explicit Stage 1 or self-built Stage 2 artifact.
        output: Native output path; retained C is its `.dea-c` sibling directory.
        env: Compiler construction environment.
        keep_c: Preserve the exact generated translation-unit tree.
        build_info_overlay: Optional generated build-info module. Only this file
            enters a private project root ahead of the checked-in sources; its
            siblings cannot shadow compiler modules. Ordinary builds use the
            checked-in fallback. The caller owns provenance and installed-mode
            policy and must select a separate package output.

    Raises:
        OSError: The supplied overlay cannot be read or build scratch cannot be written.
        subprocess.CalledProcessError: Native support or compiler construction fails.
    """
    # Read before starting construction so a missing overlay cannot silently fall
    # back to repository metadata or launch an expensive partial build.
    overlay_bytes = build_info_overlay.read_bytes() if build_info_overlay is not None else None
    output.parent.mkdir(parents=True, exist_ok=True)
    build_env, mode = compiler_build_env(env)
    with tempfile.TemporaryDirectory(prefix="stage2-support-", dir=output.parent) as temporary:
        scratch = Path(temporary)
        project_roots = []
        if overlay_bytes is not None:
            overlay_root = scratch / "build-info"
            overlay_root.mkdir()
            (overlay_root / "build_info.l1").write_bytes(overlay_bytes)
            project_roots = ["--project-root", str(overlay_root)]
        support = build_support_objects(scratch, build_env)
        command = [*wrapper_command(compiler), "--build", *mode, *support,
                   *project_roots,
                   "--project-root", str(REPO_ROOT / "compiler/stage2_l1/src"),
                   "-o", str(output), "l1c"]
        if keep_c:
            command.append("--keep-c")
        subprocess.run(command, cwd=REPO_ROOT, env=build_env, check=True)
    output.chmod(output.stat().st_mode | 0o111)


def main() -> int:
    """Build the selected repo-local Stage 2 artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, help="Explicit bootstrap compiler (defaults to repo Stage 1).")
    args = parser.parse_args()
    layout = normalize_l1_build_dir(os.environ.get("L1_BUILD_DIR", "build/dea"))
    provide_public_headers(layout)
    compiler = (args.compiler or layout.bin_dir / "l1c-stage1").resolve()
    output = layout.bin_dir / "l1c-stage2.native"
    retained = Path(str(output) + ".dea-c")
    # This is the builder-owned retained tree, never an arbitrary user output.
    if retained.exists():
        shutil.rmtree(retained)
    env = {**os.environ, "L1_BUILD_DIR": str(layout.build_dir)}
    build_compiler(compiler, output, env, keep_c=os.environ.get("KEEP_C", "0") == "1")
    write_stage2_wrapper(layout)
    write_env_script(layout)
    print(f"build-stage2-l1c: wrote {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
