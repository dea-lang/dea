# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Curate a private Stage 2 payload from explicit bootstrap inputs."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import tempfile

from build_stage2_l1c import build_compiler
from dea_tooling.bootstrap import wrapper_command
from productization_inventory import inventory_payload
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
                  upstream: Path, stage1_options: list[str]):
    """Self-build and yield a private curated payload and its provenance snapshot.

    The caller must first build the explicit upstream/Stage 1/Stage 2 seed chain.
    The payload has no install manifest; publish it through ``install_payload``.
    All scratch and the yielded payload are removed when the context exits.

    Args:
        root: L1 checkout matching the compiler builder's source root.
        layout: Completed bootstrap layout; never modified by this helper.
        seed: Explicit repository-mode Stage 2 compiler, independent of the alias.
        env: Native build and package-version selection.
        upstream: Upstream L0 compiler used to construct Stage 1.
        stage1_options: Arguments used for that Stage 1 construction.

    Yields:
        Pair of private payload directory and immutable package provenance.

    Raises:
        ValueError: Required input families or package metadata are inconsistent.
        OSError: A selected input cannot be read or private output cannot be written.
        subprocess.CalledProcessError: Semantic verification or self-build fails.
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
        root, env, upstream=upstream, stage1=layout / "bin/l1c-stage1", stage2=seed,
        stage1_options=stage1_options,
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
        overlay = scratch / "build_info.l1"
        overlay.write_text(provenance.build_info_module(installed=True), encoding="utf-8")
        build_compiler(seed, payload / "bin/l1c-stage2.native", build_env, build_info_overlay=overlay)
        for name in ("l1c", "l1c-stage2"):
            _write(payload, "bin/" + name, native_wrapper().encode(), 0o755)
            if provenance.metadata()["os"] == "windows":
                _write(payload, "bin/" + name + ".cmd", native_cmd_wrapper().encode(), 0o755)
        _write(payload, "bin/l1-env.sh", env_script().encode(), 0o755)
        if provenance.metadata()["os"] == "windows":
            _write(payload, "bin/l1-env.cmd", env_cmd_script().encode(), 0o755)
        _write(payload, "VERSION", provenance.version_text().encode())
        inventory_payload(payload, provenance.metadata())
        yield payload, provenance
