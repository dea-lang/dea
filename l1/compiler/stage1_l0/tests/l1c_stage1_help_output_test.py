#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end coverage for the L1 Stage 1 CLI help surface."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"


def resolve_tool(base: Path) -> Path:
    """Return a host-compatible launcher path.

    Args:
        base: Extensionless tool path.

    Returns:
        Existing launcher path for the host platform, or the expected path when missing.
    """

    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
        return base.with_suffix(".cmd")
    return base


def stage1_compiler() -> Path:
    """Return the repo-local L1 Stage 1 compiler path."""

    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def main() -> int:
    """Assert the canonical aliases and operational compile-only wording in `--help`."""

    compiler = stage1_compiler()
    if not compiler.is_file():
        raise AssertionError(f"missing repo-local Stage 1 compiler: {compiler}")

    completed = subprocess.run(
        [str(compiler), "--help"],
        cwd=L1_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, f"--help exited with {completed.returncode}: {completed.stderr}"
    assert completed.stderr == "", f"--help wrote stderr: {completed.stderr!r}"

    help_text = completed.stdout
    expected_fragments = (
        "usage: l1c [-h] [-V] [-v] [-Vl] [-Rp PROJECT_ROOT] [-Rs SYS_ROOT]",
        "           [-Cf C_OBJECT] [-l LIBRARY] [-L LIBRARY_PATH]",
        "           [-Rr RPATH] [-Cl LINK_ARG] [-e MODULE]",
        "       l1c -k DEA_OBJECT... [-Cf C_OBJECT]... [-l LIBRARY]... [-L LIBRARY_PATH]...",
        "           [-Rr RPATH]... [-Cl LINK_ARG]... [-e MODULE] -o OUTPUT",
        "  -V, --version         show compiler version and exit",
        "  -Vl, --log            Enable rich log formatting",
        "  -Rp, --project-root PROJECT_ROOT",
        "  -Rs, --sys-root SYS_ROOT",
        "  -c, --compile         Compile one module to sibling .o and .l1m artifacts",
        "  -k, --link            Link Dea .o files through verified sibling .l1m files",
        "  -Gi, --emit-interface Emit the module interface",
        "  --gen, -Gc, --codegen Generate C code",
        "  --c-compiler, -Cc C_COMPILER",
        "  --c-options, -Co C_OPTIONS",
        "  -I, --interface-path INTERFACE_PATH",
        "'--build', '--compile', '--gen', '--run'; searched in",
        "declaration order)",
        "  --runtime-include, -Ri RUNTIME_INCLUDE",
        "  --runtime-lib, -Rl RUNTIME_LIB",
        "  -Cf, --foreign-object C_OBJECT",
        "  -l LIBRARY            Link an external library in encounter order",
        "attached -lLIBRARY is also accepted; valid in:",
        "  -L LIBRARY_PATH       Add an external-library search path in encounter order",
        "attached -LLIBRARY_PATH is also accepted;",
        "  -Rr, --rpath RPATH    Add a runtime dynamic-library search path in encounter",
        "  -Cl, --link-arg LINK_ARG",
        "Pass one intact host compiler-driver argument in",
        "  -e, --entry MODULE    Select one canonical dotted Dea entry module",
        "  -Gk, --keep-c         Keep generated C (valid in: '--build', '--compile',",
        "  -Sb, --check-basic",
        "  -Su, --unchecked",
        "  -Va, --trace-arc",
        "  -Vm, --trace-memory",
        "'--run'; build/run retain a mirrored .dea-c tree;",
        "compile mode adds the sibling .c artifact)",
        "  -g                    Reserved debug-information option (not supported yet)",
        "  -S                    Reserved assembly-output option (not supported yet)",
    )
    for fragment in expected_fragments:
        assert fragment in help_text, f"missing help fragment: {fragment!r}"

    retired_fragments = (
        "  -l, --log",
        "  -P, --project-root",
        "  -S, --sys-root",
        "  --gen, -g, --codegen",
        "  --c-compiler, -c C_COMPILER",
        "  --c-options, -C C_OPTIONS",
        "  --runtime-include, -I RUNTIME_INCLUDE",
        "  --runtime-lib, -L RUNTIME_LIB",
        "Reserved library search path (not supported yet)",
        "Reserved library link option (not supported yet)",
    )
    for fragment in retired_fragments:
        assert fragment not in help_text, f"retired help fragment remains: {fragment!r}"

    long_version = subprocess.run(
        [str(compiler), "--version"],
        cwd=L1_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    short_version = subprocess.run(
        [str(compiler), "-V"],
        cwd=L1_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert long_version.returncode == 0, f"--version exited with {long_version.returncode}: {long_version.stderr}"
    assert short_version.returncode == 0, f"-V exited with {short_version.returncode}: {short_version.stderr}"
    assert short_version.stdout == long_version.stdout, "-V and --version output differ"
    assert short_version.stderr == long_version.stderr == "", "version aliases wrote stderr"

    print("l1c_stage1_help_output_test: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
