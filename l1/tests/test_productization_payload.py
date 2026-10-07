# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Curated package selection and private assembly regressions."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import productization_payload as payload
from productization_provenance import PackageProvenance
from productization_inventory import install_payload, verify_payload


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path / "repo/l1"
    layout = root / "build/dea"
    files = {"shared/l1/stdlib/std/io.l1": b"module std.io;",
             "shared/l1/stdlib/sys/rt.l1": b"module sys.rt;",
             "shared/runtime/src/dea_rt.c": b"runtime",
             "shared/runtime/internal/internal.h": b"internal",
             "shared/runtime/include/dea_rt.h": b"public",
             "shared/runtime/include/l1_real.h": b"real",
             "shared/runtime/dea_rt.symbols": b"symbols",
             "shared/runtime/dea_rt_traced.symbols": b"traced symbols"}
    for path, data in files.items():
        payload._write(root / "compiler", path, data)
    for name in ("dea_rt.h", "l1_real.h"):
        payload._write(layout, "include/" + name, files["shared/runtime/include/" + name])
    for name in ("std/io", "sys/rt"):
        payload._write(layout, "interfaces/" + name + ".l1m", name.encode())
    for name in ("LICENSE-MIT", "LICENSE-APACHE", "THIRD_PARTY_NOTICES"):
        payload._write(root.parent, name, b"notice")
    shutil.copytree(ROOT / "scripts/package", root / "scripts/package")
    shutil.copytree(ROOT / "docs/user", root / "docs/user")
    return root, layout


def test_selection_is_exact_and_snapshot_is_independent(inputs):
    root, layout = inputs
    payload._write(root / "compiler", "shared/runtime/src/retained.o", b"exclude")
    payload._write(layout, "lib/cache.a", b"exclude")
    payload._write(layout, "interfaces/retained.c", b"exclude")
    selected = payload.snapshot_support(root, layout)
    assert len(selected) == 12
    assert not any(name.endswith((".o", ".a", "retained.c")) for name in selected)
    (layout / "interfaces/std/io.l1m").write_bytes(b"changed")
    assert selected["interfaces/std/io.l1m"] == b"std/io"


@pytest.mark.parametrize("change", ["missing", "extra", "header", "link", "parent-link"])
def test_inconsistent_inputs_rejected(inputs, change):
    root, layout = inputs
    if change == "missing":
        (layout / "interfaces/std/io.l1m").unlink()
    elif change == "extra":
        payload._write(layout, "interfaces/std/extra.l1m", b"extra")
    elif change == "header":
        (layout / "include/dea_rt.h").write_bytes(b"stale")
    else:
        path = layout / ("interfaces/std/io.l1m" if change == "link" else "interfaces/std")
        target = path.with_name("moved")
        path.rename(target)
        try:
            path.symlink_to(target, target_is_directory=change == "parent-link")
        except OSError:
            pytest.skip("symlink creation unavailable")
    with pytest.raises(ValueError):
        payload.snapshot_support(root, layout)


@pytest.mark.parametrize("windows", [False, True])
def test_assembly_uses_snapshot_marker_and_private_output(inputs, monkeypatch, tmp_path, windows):
    root, layout = inputs
    expected = payload.snapshot_support(root, layout)
    calls = []

    def collect(source, env, **kwargs):
        assert kwargs["preparation_inputs"] == {name: hashlib.sha256(data).hexdigest()
                                               for name, data in expected.items()}
        metadata = {"package_version": "dev", "maturity": "development",
                    "os": "windows" if windows else "linux", "arch": "x86_64",
                    "provenance": {"source": {"revision": "fixture", "tree_state": "clean"},
                                   "build_id": "fixture", "build_time": "2026-10-07T00:00:00Z",
                                   "native_compiler": {"version": "fixture"}}}
        return PackageProvenance(json.dumps(metadata)), env

    def build(seed, output, env, **kwargs):
        assert "func build_info_is_installed() -> bool {\n    return true;" in kwargs["build_info_overlay"].read_text()
        assert not output.is_relative_to(root)
        payload._write(output.parent, output.name, b"native fixture", 0o755)
        calls.append(output)

    monkeypatch.setattr(payload, "collect_provenance", collect)
    monkeypatch.setattr(payload, "build_compiler", build)
    monkeypatch.setattr(payload.subprocess, "run", lambda *a, **kw: None)
    with payload.build_payload(root, layout, layout / "bin/l1c-stage2", {}, upstream=tmp_path / "l0",
                               stage1_options=[]) as (tree, provenance):
        for name, data in expected.items():
            assert (tree / name).read_bytes() == data
        assert (tree / "bin/l1c.cmd").exists() == windows
        assert (tree / "bin/l1-env.cmd").exists() == windows
        assert (tree / "bin/l1c").exists()
        assert not (tree / "bin/l1c-stage1").exists()
        assert "share/doc/dea/l1/toolchain.md" in (tree / "README.md").read_text()
        for document in (tree / "README.md", tree / "README-WINDOWS.md",
                         tree / "share/doc/dea/l1/toolchain.md"):
            text = document.read_text()
            targets = re.findall(r"\]\(([^)]+)\)", text)
            targets += re.findall(r"^\[[^]]+\]: (\S+)", text, re.MULTILINE)
            for target in targets:
                if not target.startswith("https://"):
                    assert (document.parent / target).is_file(), target
        assert not list(tree.rglob("build_info.l1"))
        prefix = tmp_path / "installed"
        record = install_payload(tree, prefix, provenance.metadata())
        verify_payload(prefix, record)
    assert calls and not tree.exists()


@pytest.mark.parametrize("failure", ["verification", "construction"])
def test_failed_build_removes_private_scratch(inputs, monkeypatch, tmp_path, failure):
    root, layout = inputs
    scratch = []

    class Metadata:
        def build_info_module(self, **kwargs):
            return "overlay"

    monkeypatch.setattr(payload, "collect_provenance", lambda *a, **kw: (Metadata(), {}))

    def verify(args, **kwargs):
        scratch.append(Path(args[-1]).parent)
        if failure == "verification":
            raise RuntimeError("verification failed")

    def build(*args, **kwargs):
        raise RuntimeError("construction failed")

    monkeypatch.setattr(payload.subprocess, "run", verify)
    monkeypatch.setattr(payload, "build_compiler", build)
    with pytest.raises(RuntimeError, match=failure + " failed"):
        with payload.build_payload(root, layout, layout / "bin/seed", {}, upstream=tmp_path / "l0", stage1_options=[]):
            pytest.fail("must not expose failed payload")
    assert scratch and not scratch[0].exists()
    assert not (layout / "bin").exists()
