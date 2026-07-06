#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Generate repo-local Dea build and install-prefix tooling artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

from build_stage2_l0c import build_stage2_artifact, compiler_runtime_build_env
from dist_tools_lib import (
    create_stage2_distribution,
    distribution_archive_basename,
    distribution_root_dir_name,
    install_prefix_stage2,
    list_installed_files,
    normalize_dea_build_dir,
    normalize_prefix_dir,
    remove_dea_build_tree,
    set_alias,
    stage2_wrapper_command,
    stage2_build_info_overlay,
    write_env_script,
    write_stage1_wrapper,
    write_stage2_wrapper,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_build_time_utc(build_time_text: str) -> datetime:
    """Parse one recorded UTC build-time string back into a datetime."""

    return datetime.strptime(build_time_text, "%Y-%m-%d %H:%M:%S+00:00").replace(tzinfo=timezone.utc)


def render_display_path(path: Path) -> str:
    """Render one path relative to the repo root when possible."""

    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def print_progress(message: str) -> None:
    """Emit one install-progress line immediately."""

    print(f"gen-dea-build-tools: {message}", flush=True)


def print_toolchain_env(env: dict[str, str] | None = None) -> None:
    """Emit the current host toolchain-related environment."""

    source_env = os.environ if env is None else env
    for name in ("L0_CC", "L0_CFLAGS"):
        value = source_env.get(name)
        if value is None:
            rendered = "<unset>"
        elif value == "":
            rendered = "''"
        else:
            rendered = shlex.quote(value)
        print_progress(f"{name}={rendered}")


def add_dea_build_dir_arg(parser: argparse.ArgumentParser) -> None:
    """Attach the shared repo-local Dea build dir option to one parser."""

    parser.add_argument(
        "--dea-build-dir",
        required=True,
        help="Repo-local Dea build directory to generate into.",
    )


def add_prefix_arg(parser: argparse.ArgumentParser) -> None:
    """Attach the shared prefix option to one parser."""

    parser.add_argument("--prefix", required=True, help="Install prefix to generate into.")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Generate repo-local Dea build and install-prefix artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    write_stage1 = subparsers.add_parser("write-stage1-wrapper", help="Write `bin/l0c-stage1`.")
    add_dea_build_dir_arg(write_stage1)

    write_stage2 = subparsers.add_parser("write-stage2-wrapper", help="Write `bin/l0c-stage2`.")
    add_dea_build_dir_arg(write_stage2)

    write_env = subparsers.add_parser("write-env-script", help="Write `bin/l0-env.sh`.")
    add_dea_build_dir_arg(write_env)

    alias_parser = subparsers.add_parser("set-alias", help="Point `bin/l0c` at one stage wrapper.")
    add_dea_build_dir_arg(alias_parser)
    alias_parser.add_argument("--stage", choices=("stage1", "stage2"), required=True)

    clean_parser = subparsers.add_parser(
        "clean-dea-build",
        help="Delete one validated repo-local Dea build tree.",
    )
    add_dea_build_dir_arg(clean_parser)

    install_prefix = subparsers.add_parser(
        "install-prefix",
        help="Build compiler 2 (self-hosted Stage 2) and install it into one prefix.",
    )
    add_prefix_arg(install_prefix)

    subparsers.add_parser(
        "make-dist",
        help="Build compiler 2 (self-hosted Stage 2) into one temporary `dist/` tree and archive it.",
    )

    list_installed = subparsers.add_parser(
        "list-installed",
        help="List files installed by `make install` under one prefix.",
    )
    add_prefix_arg(list_installed)

    return parser.parse_args()


def main() -> int:
    """Program entrypoint."""

    args = parse_args()
    try:
        if args.command == "install-prefix":
            prefix_layout = normalize_prefix_dir(args.prefix)
            build_root = prefix_layout.repo_root / "build"
            build_root.mkdir(parents=True, exist_ok=True)
            temp_dist = Path(tempfile.mkdtemp(prefix="install_stage2_prefix.", dir=build_root))
            try:
                temp_layout = normalize_dea_build_dir(str(temp_dist))
                with stage2_build_info_overlay(prefix_layout.repo_root, os.environ.copy(), temp_parent=build_root) as overlay:
                    compiler_build_env = compiler_runtime_build_env(overlay.build_env)
                    print_toolchain_env(compiler_build_env)
                    print_progress(f"stage 1/3: building bootstrap Stage 2 compiler under {temp_layout.dea_build_dir}")
                    stage2_wrapper, _, _ = build_stage2_artifact(
                        temp_layout,
                        keep_c=False,
                        extra_project_roots=[str(overlay.overlay_root)],
                        extra_env=compiler_build_env,
                    )
                    self_hosted_native = temp_dist / "l0c-stage2-selfhosted.native"
                    self_build_env = compiler_runtime_build_env(overlay.build_env)
                    self_build_env["L0_HOME"] = str(prefix_layout.repo_root / "compiler")
                    self_build_env.pop("L0_SYSTEM", None)
                    self_build_env.pop("L0_RUNTIME_INCLUDE", None)
                    self_build_env.pop("L0_RUNTIME_LIB", None)
                    print_progress(f"stage 2/3: self-hosting Stage 2 compiler into {self_hosted_native}")
                    subprocess.run(
                        [
                            *stage2_wrapper_command(stage2_wrapper),
                            "--build",
                            "-P",
                            str(overlay.overlay_root),
                            "-P",
                            "compiler/stage2_l0/src",
                            "-o",
                            str(self_hosted_native),
                            "l0c",
                        ],
                        cwd=prefix_layout.repo_root,
                        env=self_build_env,
                        check=True,
                    )
                    print_progress(f"stage 3/3: installing self-hosted Stage 2 compiler into {prefix_layout.prefix_dir}")
                    installed_native = install_prefix_stage2(prefix_layout, self_hosted_native)
                    print_progress(f"installed self-hosted Stage 2 compiler at {installed_native}")
                    print_progress(f"installed prefix layout at {prefix_layout.prefix_dir}")
                    return 0
            finally:
                shutil.rmtree(temp_dist, ignore_errors=True)

        if args.command == "list-installed":
            prefix_layout = normalize_prefix_dir(args.prefix)
            for path in list_installed_files(prefix_layout):
                print(path)
            return 0

        if args.command == "make-dist":
            build_root = REPO_ROOT / "build"
            build_root.mkdir(parents=True, exist_ok=True)
            temp_root = Path(tempfile.mkdtemp(prefix="stage2_dist.", dir=build_root))
            try:
                bootstrap_layout = normalize_dea_build_dir(str(temp_root / "bootstrap"))
                with stage2_build_info_overlay(REPO_ROOT, os.environ.copy(), temp_parent=build_root) as overlay:
                    compiler_build_env = compiler_runtime_build_env(overlay.build_env)
                    dist_layout = normalize_prefix_dir(str(temp_root / distribution_root_dir_name()))
                    print_toolchain_env(compiler_build_env)
                    print_progress(
                        f"stage 1/4: building bootstrap Stage 2 compiler under {render_display_path(bootstrap_layout.dea_build_dir)}"
                    )
                    stage2_wrapper, _, _ = build_stage2_artifact(
                        bootstrap_layout,
                        keep_c=False,
                        extra_project_roots=[str(overlay.overlay_root)],
                        extra_env=compiler_build_env,
                    )
                    self_hosted_native = temp_root / "l0c-stage2-selfhosted.native"
                    self_build_env = compiler_runtime_build_env(overlay.build_env)
                    self_build_env["L0_HOME"] = str(REPO_ROOT / "compiler")
                    self_build_env.pop("L0_SYSTEM", None)
                    self_build_env.pop("L0_RUNTIME_INCLUDE", None)
                    self_build_env.pop("L0_RUNTIME_LIB", None)
                    print_progress(f"stage 2/4: self-hosting Stage 2 compiler into {render_display_path(self_hosted_native)}")
                    subprocess.run(
                        [
                            *stage2_wrapper_command(stage2_wrapper),
                            "--build",
                            "-P",
                            str(overlay.overlay_root),
                            "-P",
                            "compiler/stage2_l0/src",
                            "-o",
                            str(self_hosted_native),
                            "l0c",
                        ],
                        cwd=REPO_ROOT,
                        env=self_build_env,
                        check=True,
                    )
                    print_progress(
                        f"stage 3/4: assembling relocatable distribution under {render_display_path(dist_layout.prefix_dir)}"
                    )
                    distribution = create_stage2_distribution(
                        dist_layout,
                        self_hosted_native,
                        distribution_archive_basename(
                            parse_build_time_utc(overlay.provenance.build_time),
                            overlay.provenance.host,
                        ),
                        overlay.provenance,
                    )
                    print_progress(f"stage 4/4: wrote distribution archive at {render_display_path(distribution.archive_path)}")
                    print_progress(f"created distribution directory at {render_display_path(distribution.dist_dir)}")
                    print("-------------------------------------------------------------------------------")
                    print(f"created distribution archive at {render_display_path(distribution.archive_path)}")
                    print("-------------------------------------------------------------------------------")
                    return 0
            except ValueError as exc:
                print(f"gen-dea-build-tools: {exc}", file=sys.stderr)
                return 1

        layout = normalize_dea_build_dir(args.dea_build_dir)
        if args.command == "write-stage1-wrapper":
            path = write_stage1_wrapper(layout)
            print(f"gen-dea-build-tools: wrote {path}")
            return 0
        if args.command == "write-stage2-wrapper":
            path = write_stage2_wrapper(layout)
            print(f"gen-dea-build-tools: wrote {path}")
            return 0
        if args.command == "write-env-script":
            path = write_env_script(layout)
            print(f"gen-dea-build-tools: wrote {path}")
            return 0
        if args.command == "set-alias":
            path = set_alias(layout, args.stage)
            if path.is_symlink():
                print(f"gen-dea-build-tools: linked {path} -> {path.readlink()}")
            else:
                print(f"gen-dea-build-tools: selected {args.stage} alias at {path}")
            return 0
        if args.command == "clean-dea-build":
            remove_dea_build_tree(layout)
            print(f"gen-dea-build-tools: removed {layout.dea_build_dir}")
            return 0
        raise AssertionError(f"unhandled command: {args.command}")
    except ValueError as exc:
        print(f"gen-dea-build-tools: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
