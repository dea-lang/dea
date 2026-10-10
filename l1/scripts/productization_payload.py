# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Curate a private canonical L1 payload from explicit bootstrap inputs."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

from build_l1c import build_compiler
from dea_tooling.bootstrap import wrapper_command
from productization_inventory import MANIFEST_PATH, inventory_payload, verify_payload
from productization_launchers import env_cmd_script, env_script, native_cmd_wrapper, native_wrapper
from productization_provenance import collect_provenance


def _read(root: Path, relative: str) -> bytes:
    """Read an ordinary selected file, rejecting substituted parents and links."""
    path = root
    for part in Path(relative).parts:
        path /= part
        mode = path.lstat().st_mode
        if not (stat.S_ISREG(mode) if path == root / relative else stat.S_ISDIR(mode)):
            raise ValueError(f"package input must be an ordinary file/directory: {path}")
    return path.read_bytes()


def _select(root: Path, directory: str, suffix: str) -> dict[str, bytes]:
    """Select one source family without following directory aliases."""
    selected = {}
    base = root / directory
    if not base.is_dir() or base.is_symlink():
        raise ValueError(f"missing ordinary package input directory: {base}")
    for current, directories, files in os.walk(base, followlinks=False):
        for name in directories:
            if (Path(current) / name).is_symlink():
                raise ValueError(f"linked package input directory: {Path(current) / name}")
        for name in sorted(files):
            if name.endswith(suffix):
                path = (Path(current) / name).relative_to(root).as_posix()
                selected[path] = _read(root, path)
    if not selected:
        raise ValueError(f"empty package input family: {base}")
    return selected


def snapshot_support(root: Path, layout: Path) -> dict[str, bytes]:
    """Capture only semantic interfaces and compiler-owned preparation inputs.

    Args:
        root: L1 checkout containing canonical shared sources.
        layout: Explicit bootstrap layout containing verified interfaces and headers.

    Returns:
        Prefix-relative file names and exact bytes, independent of later source edits.

    Raises:
        ValueError: Inputs are substituted, incomplete, or inconsistent with bootstrap.
        OSError: Required inputs cannot be read.
    """
    compiler = root / "compiler"
    selected = _select(compiler, "shared/l1/stdlib", ".l1")
    modules = {path.removeprefix("shared/l1/stdlib/").removesuffix(".l1") for path in selected}
    if any(not path.startswith(("std/", "sys/")) for path in modules):
        raise ValueError("package sources must belong to std or sys")
    interfaces = _select(layout, "interfaces", ".l1m")
    if {path.removeprefix("interfaces/").removesuffix(".l1m") for path in interfaces} != modules:
        raise ValueError("bootstrap interface set does not match bundled source modules")
    selected.update(interfaces)
    selected.update(_select(compiler, "shared/runtime/src", ".c"))
    selected.update(_select(compiler, "shared/runtime/internal", ".h"))
    for name in ("dea_rt.h", "l1_real.h"):
        source = _read(compiler, f"shared/runtime/include/{name}")
        if _read(layout, f"include/{name}") != source:
            raise ValueError(f"bootstrap public header differs from shipped source: {name}")
        selected[f"shared/runtime/include/{name}"] = source
        selected[f"include/{name}"] = source
    for name in ("dea_rt.symbols", "dea_rt_traced.symbols"):
        path = f"shared/runtime/{name}"
        selected[path] = _read(compiler, path)
    return dict(sorted(selected.items()))


def _write(root: Path, relative: str, data: bytes, mode: int = 0o644) -> None:
    """Write one selected payload file with portable permissions."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)


@contextmanager
def build_payload(root: Path, layout: Path, seed: Path, env: dict[str, str], *,
                  upstream: Path, compiler_options: list[str]):
    """Build and yield a private curated payload and its provenance snapshot.

    The caller must first build a private canonical compiler with the explicit upstream L0 toolchain.
    The payload has no install manifest; publish it through ``install_payload``.
    All scratch and the yielded payload are removed when the context exits.

    Args:
        root: L1 checkout matching the compiler builder's source root.
        layout: Completed bootstrap layout; never modified by this helper.
        seed: Private repository-mode canonical compiler for semantic verification.
        env: Native build and package-version selection.
        upstream: Upstream L0 compiler used for canonical construction.
        compiler_options: Arguments used for the private canonical construction.

    Yields:
        Pair of private payload directory and immutable package provenance.

    Raises:
        ValueError: Required input families or package metadata are inconsistent.
        OSError: A selected input cannot be read or private output cannot be written.
        subprocess.CalledProcessError: Semantic verification or compiler construction fails.
    """
    root, layout, seed = root.resolve(), layout.resolve(), seed.absolute()
    support = snapshot_support(root, layout)
    extra = {name: _read(root.parent, name) for name in
             ("LICENSE-MIT", "LICENSE-APACHE", "THIRD_PARTY_NOTICES")}
    for source, target in (("README.md", "README.md"), ("README-WINDOWS.md", "README-WINDOWS.md"),
                           ("toolchain.md", "share/doc/dea/l1/toolchain.md")):
        extra[target] = _read(root, "docs/user/" + source)
    extra["share/dea/l1/smoke/hello.l1"] = _read(root, "scripts/package/hello.l1")
    provenance, build_env = collect_provenance(
        root, env, upstream=upstream, compiler=seed,
        compiler_options=compiler_options,
        preparation_inputs={name: hashlib.sha256(data).hexdigest() for name, data in support.items()})
    with tempfile.TemporaryDirectory(prefix="l1-package-") as temporary:
        scratch = Path(temporary)
        payload = scratch / "payload"
        for name, data in {**support, **extra}.items():
            _write(payload, name, data)
        # Validate the exact captured interface graph using its matching captured sources.
        modules = [path.removeprefix("interfaces/").removesuffix(".l1m").replace("/", ".")
                   for path in support if path.startswith("interfaces/")]
        umbrella = scratch / "_dea_package_inputs.l1"
        umbrella.write_text("module _dea_package_inputs;\n" +
                            "".join(f"import {module};\n" for module in modules), encoding="utf-8")
        subprocess.run([*wrapper_command(seed), "--gen", "--no-managed-stdlib",
                        "--sys-root", str(payload / "shared/l1/stdlib"),
                        "-I", str(payload / "interfaces"), str(umbrella), "-o", str(scratch / "verify.c")],
                       cwd=root, env=build_env, check=True)
        overlay = scratch / "build_info.l0"
        overlay.write_text(provenance.build_info_module(installed=True), encoding="utf-8")
        command = build_compiler(upstream, payload / "bin/l1c.native", build_env, build_info_overlay=overlay)
        provenance = provenance.with_installed_compiler_command(command)
        _write(payload, "bin/l1c", native_wrapper().encode(), 0o755)
        if provenance.metadata()["os"] == "windows":
            _write(payload, "bin/l1c.cmd", native_cmd_wrapper().encode(), 0o755)
        _write(payload, "bin/l1-env.sh", env_script().encode(), 0o755)
        if provenance.metadata()["os"] == "windows":
            _write(payload, "bin/l1-env.cmd", env_cmd_script().encode(), 0o755)
        _write(payload, "VERSION", provenance.version_text().encode())
        # The marked native compiler must consume the captured graph through its
        # installed roots before any requested destination can be modified.
        # Its startup guard needs a complete private inventory. The publisher
        # later records the final tree after optional documentation is added.
        record = inventory_payload(payload, provenance.metadata())
        _write(payload, MANIFEST_PATH, (json.dumps(record, sort_keys=True, indent=2) + "\n").encode())
        installed_env = {name: value for name, value in build_env.items()
                         if name not in {"L1_HOME", "L1_BUILD_DIR", "L1_SYSTEM", "L1_RUNTIME_INCLUDE",
                                         "L1_RUNTIME_LIB", "L1_STDLIB_CACHE"}}
        try:
            subprocess.run([str(payload / "bin/l1c.native"), "--gen", "--no-managed-stdlib",
                            "-I", str(payload / "interfaces"), str(umbrella),
                            "-o", str(scratch / "verify-installed.c")],
                           cwd=scratch, env=installed_env, check=True)
            verify_payload(payload, record)
        finally:
            (payload / MANIFEST_PATH).unlink()
        yield payload, provenance
