#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Install the canonical L1 toolchain or list its recorded payload."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from build_l1c import REPO_ROOT, normalize_l1_build_dir, compiler_build_options
from build_l1c import compiler_build_env
from dea_tooling.bootstrap import resolve_bootstrap_compiler, wrapper_command
from docs_artifacts import source_identity, unpack_bundle
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


def install(prefix_text: str, env: dict[str, str], *, make: str = "make") -> Path:
    """Build an isolated bootstrap chain and publish its curated canonical L1 payload.

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
                   ("l0", "l2", "scripts", "tools", ".git", ".venv", "LICENSE-MIT", "LICENSE-APACHE", "THIRD_PARTY_NOTICES")))
    prefix = resolve_prefix(prefix_text, working_dir=REPO_ROOT, protected_paths=protected)
    resolve_prefix(build_root, working_dir=REPO_ROOT, protected_paths=protected[1:])
    version = package_version(env)
    host_target(platform.system(), platform.machine(), env)
    docs_text = env.get("DOCS_ARTIFACT", "").strip()
    if docs_text:
        bundle = Path(docs_text)
        if not bundle.is_absolute() or not bundle.is_file():
            raise ValueError("DOCS_ARTIFACT must be an existing absolute bundle path; generate it with "
                             "make docs-artifacts DEA_DIST_VERSION=<version>")
        protected = (*protected, bundle.resolve())
        prefix = resolve_prefix(prefix, working_dir=REPO_ROOT, protected_paths=protected)
    # Verify and retain a private docs snapshot before spending time on bootstrap.
    # Publication consumes this tree, never reopens a possibly replaced input archive.
    with ExitStack() as resources:
        docs = None
        if docs_text:
            build_root.mkdir(parents=True, exist_ok=True)
            extracted = Path(resources.enter_context(tempfile.TemporaryDirectory(prefix="install-docs-", dir=build_root)))
            docs_source = source_identity(REPO_ROOT)
            unpack_bundle(bundle, extracted, version=version, source=docs_source)
            docs = extracted / "dea-l1-autodocs"
        # Bootstrap uses only checkout inputs and private caches, never an activated
        # installation's source roots, runtime overrides, or native preparation state.
        build_env = dict(env)
        # The installed compiler is an optimized product by default. L1_CFLAGS
        # configures programs it compiles; L0_CFLAGS constructs this .l0 compiler.
        build_env.setdefault("L0_CFLAGS", "-O2")
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
            # Pin the effective upstream native compiler and construction controls.
            build_env, _ = compiler_build_env(build_env)
            print("install: building private canonical L1 compiler", flush=True)
            subprocess.run([sys.executable, str(REPO_ROOT / "scripts/build_l1c.py")],
                           cwd=REPO_ROOT, env=build_env, check=True)
            print("install: building the installed canonical L1 payload", flush=True)
            with build_payload(REPO_ROOT, layout.build_dir, layout.bin_dir / "l1c", build_env,
                               upstream=upstream, compiler_options=compiler_build_options(layout)) as (payload, provenance):
                if docs is not None:
                    if source_identity(REPO_ROOT) != docs_source:
                        raise ValueError("documentation source identity changed during bootstrap; regenerate DOCS_ARTIFACT")
                    shutil.copytree(docs, payload / "share/doc/dea/l1/autodocs")
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
            print(f"Installed Dea/L1 at {prefix}")
            print(f"Run {prefix / 'bin/l1c'} --help or activate {prefix / 'bin/l1-env.sh'}")
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"{args.command}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
