#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Install the self-built Stage 2 toolchain or list its recorded payload."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

from build_stage1_l1c import REPO_ROOT, normalize_l1_build_dir, stage1_build_options
from build_stage2_l1c import build_compiler, compiler_build_env, write_stage2_wrapper
from dea_tooling.bootstrap import resolve_bootstrap_compiler, wrapper_command
from productization_inventory import install_payload, list_installed, resolve_prefix
from productization_payload import build_payload
from productization_provenance import host_target, package_version


def bootstrap_upstream(env: dict[str, str], make: str) -> Path:
    """Resolve the explicit L0 compiler, preparing only an absent default.

    Args:
        env: Bootstrap environment, with inherited installation roots removed.
        make: GNU Make executable used to prepare the repo-local default.

    Returns:
        Explicit upstream compiler path; ambient compiler aliases are never used.

    Raises:
        RuntimeError: An explicit override or prepared default is missing.
        subprocess.CalledProcessError: Default bootstrap preparation fails.
    """
    override = env.get("L1_BOOTSTRAP_L0C")
    default = REPO_ROOT.parent / "l0/build/dea/bin/l0c-stage2"
    if not override and not Path(wrapper_command(default)[0]).is_file():
        for target in ("venv", "install-dev-stage2"):
            subprocess.run([make, "-C", str(REPO_ROOT.parent / "l0"), target,
                            "DEA_BUILD_DIR=build/dea"], env=env, check=True)
    upstream, _ = resolve_bootstrap_compiler(
        override_text=override, default_path=default, env_var_name="L1_BOOTSTRAP_L0C",
        setup_hint="run `make -C ../l0 use-dev-stage2`")
    return upstream


def verify_seed_interfaces(layout: Path, seed: Path, env: dict[str, str]) -> None:
    """Require the Stage 2 seed to reproduce every canonical Stage 1 interface.

    Args:
        layout: Private bootstrap layout with Stage 1's verified semantic set.
        seed: Explicit repository-mode Stage 2 launcher.
        env: Isolated bootstrap environment.

    Raises:
        ValueError: The two stages produce different semantic interface bytes.
        subprocess.CalledProcessError: Stage 2 interface generation fails.
    """
    with tempfile.TemporaryDirectory(prefix="verify-stage2-", dir=layout) as temporary:
        scratch = Path(temporary)
        for source in sorted((REPO_ROOT / "compiler/shared/l1/stdlib").rglob("*.l1")):
            relative = source.relative_to(REPO_ROOT / "compiler/shared/l1/stdlib")
            module = relative.with_suffix("").as_posix().replace("/", ".")
            output = scratch / "module.l1m"
            subprocess.run([*wrapper_command(seed), "--emit-interface", "--no-managed-stdlib",
                            "--sys-root", str(REPO_ROOT / "compiler/shared/l1/stdlib"),
                            "--project-root", str(scratch), module, "-o", str(output)],
                           cwd=REPO_ROOT, env=env, check=True)
            if output.read_bytes() != (layout / "interfaces" / relative.with_suffix(".l1m")).read_bytes():
                raise ValueError(f"Stage 2 interface differs from Stage 1: {module}")


def install(prefix_text: str, env: dict[str, str], *, make: str = "make") -> Path:
    """Build an isolated bootstrap chain and publish its curated Stage 2 payload.

    Args:
        prefix_text: Required destination, relative to the L1 working directory.
        env: Explicit build controls and package version selection.
        make: GNU Make executable for missing upstream preparation.

    Returns:
        Absolute successfully installed prefix.

    Raises:
        ValueError: Prefix, package inputs, or metadata are invalid.
        RuntimeError: A required bootstrap compiler is unavailable.
        OSError: Inputs cannot be read or outputs cannot be written.
        subprocess.CalledProcessError: Bootstrap or package construction fails.
    """
    build_root = normalize_l1_build_dir(env.get("L1_BUILD_DIR", "build/dea")).build_dir
    protected = (build_root, *(REPO_ROOT / name for name in ("compiler", "scripts", "docs", "tests", "work")),
                 *(REPO_ROOT.parent / name for name in
                   ("l0", "scripts", "tools", ".git", ".venv", "LICENSE-MIT", "LICENSE-APACHE", "THIRD_PARTY_NOTICES")))
    prefix = resolve_prefix(prefix_text, working_dir=REPO_ROOT, protected_paths=protected)
    resolve_prefix(build_root, working_dir=REPO_ROOT, protected_paths=protected[1:])
    package_version(env)
    host_target(platform.system(), platform.machine(), env)
    if env.get("DOCS_ARTIFACT", "").strip():
        raise ValueError("DOCS_ARTIFACT integration is not implemented yet; omit it for a compiler-only install")
    # Bootstrap uses only checkout inputs and private caches, never an activated
    # installation's source roots, runtime overrides, or native preparation state.
    build_env = dict(env)
    for name in ("L0_HOME", "L0_SYSTEM", "L0_RUNTIME_INCLUDE", "L0_RUNTIME_LIB",
                 "L1_HOME", "L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_STDLIB_CACHE"):
        build_env.pop(name, None)
    upstream = bootstrap_upstream(build_env, make)
    protected = (*protected, upstream, Path(wrapper_command(upstream)[0]))
    prefix = resolve_prefix(prefix, working_dir=REPO_ROOT, protected_paths=protected)
    # The existing layout validator stays repo-local. Only disposable bootstrap
    # artifacts go beneath the selected build root; its bin/ and alias are untouched.
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="install-bootstrap-", dir=build_root) as temporary:
        layout = normalize_l1_build_dir(temporary)
        build_env.update(L1_BUILD_DIR=str(layout.build_dir), L1_BOOTSTRAP_L0C=str(upstream), KEEP_C="0",
                         L1_STDLIB_CACHE=str(layout.build_dir / "cache"))
        # Pin the effective Stage 2 host compiler and controls for seed and self-build.
        build_env, _ = compiler_build_env(build_env)
        print("install: building private L1 Stage 1", flush=True)
        subprocess.run([sys.executable, str(REPO_ROOT / "scripts/build_stage1_l1c.py")],
                       cwd=REPO_ROOT, env=build_env, check=True)
        print("install: building repository-mode L1 Stage 2 seed", flush=True)
        build_compiler(layout.bin_dir / "l1c-stage1", layout.bin_dir / "l1c-stage2.native", build_env)
        seed = write_stage2_wrapper(layout)
        print("install: verifying Stage 1/Stage 2 semantic interface agreement", flush=True)
        verify_seed_interfaces(layout.build_dir, seed, build_env)
        print("install: self-building the curated L1 Stage 2 payload", flush=True)
        with build_payload(REPO_ROOT, layout.build_dir, seed, build_env, upstream=upstream,
                           stage1_options=stage1_build_options(layout)) as (payload, provenance):
            install_payload(payload, prefix, provenance.metadata(), protected_paths=protected)
    return prefix


def main(argv: list[str] | None = None) -> int:
    """Run the public install/list interface with actionable tooling failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "list-installed"))
    parser.add_argument("--make", default=os.environ.get("L1_INSTALL_MAKE", "make"),
                        help="GNU Make executable for upstream bootstrap.")
    args = parser.parse_args(argv)
    try:
        if args.command == "list-installed":
            prefix = resolve_prefix(os.environ.get("PREFIX", ""))
            for path in list_installed(prefix):
                print(path)
        else:
            prefix = install(os.environ.get("PREFIX", ""), dict(os.environ), make=args.make)
            print(f"Installed Dea/L1 Stage 2 at {prefix}")
            print(f"Run {prefix / 'bin/l1c'} --help or activate {prefix / 'bin/l1-env.sh'}")
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"{args.command}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
