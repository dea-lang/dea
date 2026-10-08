# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Public install orchestration and inventory-only Make entrypoints."""

from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import install_toolchain as installer
import build_stage1_l1c as stage1
from docs_artifacts import create_bundle, unpack_bundle, verify_tree
from productization_inventory import MANIFEST_PATH, install_payload, list_installed, read_inventory
from productization_provenance import PackageProvenance


def metadata():
    """Return portable inventory metadata for compiler-independent fixtures."""
    return {"package_version": "dev", "maturity": "development", "os": "linux", "arch": "x86_64",
            "provenance": {"fixture": True}}


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    root = tmp_path / "checkout/l1"
    root.mkdir(parents=True)
    monkeypatch.setattr(installer, "REPO_ROOT", root)
    monkeypatch.setattr(stage1, "REPO_ROOT", root)
    monkeypatch.setattr(installer, "host_target", lambda *args: ("linux", "x86_64"))
    return root


DOCS_SOURCE = {"revision": "fixture", "tree_state": "clean", "input_digest": "a" * 64}
DOCS_RELATIVE = Path("share/doc/dea/l1/autodocs/stage2")


def docs_bundle(tmp_path):
    """Create a small offline HTML/PDF bundle using the production writer."""
    tree = tmp_path / "docs source"
    (tree / "html").mkdir(parents=True)
    (tree / "pdf").mkdir()
    (tree / "html/index.html").write_text('<a href="../pdf/dea_l1_stage2_api_reference.pdf">PDF</a>')
    (tree / "pdf/dea_l1_stage2_api_reference.pdf").write_bytes(b"%PDF-1.7\nfixture\n%%EOF\n")
    bundle = tmp_path / "offline docs.tar.gz"
    create_bundle(tree, bundle, stage="stage2", version="dev", source=DOCS_SOURCE,
                  tools={name: "fixture" for name in ("doxygen", "pdflatex", "python", "mcss")})
    return bundle


@pytest.mark.parametrize("with_docs", [False, True])
@pytest.mark.parametrize("failure", [None, "stage1", "seed", "interfaces", "payload"])
def test_private_chain_preserves_development_artifacts(checkout, tmp_path, monkeypatch, failure, with_docs):
    root = checkout
    build = root / "build/custom layout"
    (build / "bin").mkdir(parents=True)
    for name in ("l1c", "l1c-stage1.native", "l1c-stage2.native"):
        (build / "bin" / name).write_bytes(b"preserved development artifact")
    upstream = tmp_path / "explicit l0"
    upstream.write_bytes(b"upstream")
    prefix = tmp_path / "installed prefix"
    calls = []
    private = []

    def step(name):
        calls.append(name)
        if name == failure:
            raise RuntimeError(name + " failed")

    def bootstrap(env, make):
        assert make == "selected-make"
        assert not any(key in env for key in ("L0_HOME", "L1_HOME", "L1_STDLIB_CACHE", "L1_SYSTEM"))
        return upstream

    def run(command, *, cwd, env, check):
        step("stage1")
        assert command == [sys.executable, str(root / "scripts/build_stage1_l1c.py")]
        layout = Path(env["L1_BUILD_DIR"])
        private.append(layout)
        assert layout.parent == build and layout != build
        assert env["L1_BOOTSTRAP_L0C"] == str(upstream)
        assert env["L1_STDLIB_CACHE"] == str(layout / "cache")
        assert env["KEEP_C"] == "0"
        assert env["L1_CFLAGS"] == "-Dcustom=1"
        assert cwd == root and check

    def build_seed(compiler, output, env):
        step("seed")
        assert compiler == private[-1] / "bin/l1c-stage1"
        assert output == private[-1] / "bin/l1c-stage2.native"
        output.parent.mkdir()
        output.write_bytes(b"seed")

    def verify(layout, seed, env):
        step("interfaces")
        assert layout == private[-1] and seed == layout / "bin/l1c-stage2"

    @contextmanager
    def payload(root, layout, seed, env, **kwargs):
        step("payload")
        assert seed == private[-1] / "bin/l1c-stage2"
        assert kwargs["upstream"] == upstream
        assert kwargs["stage1_options"] == stage1.stage1_build_options(stage1.normalize_l1_build_dir(str(layout)))
        tree = layout / "payload"
        tree.mkdir()
        (tree / "VERSION").write_text("fixture")
        yield tree, PackageProvenance(json.dumps(metadata()))

    monkeypatch.setattr(installer, "bootstrap_upstream", bootstrap)
    monkeypatch.setattr(installer, "compiler_build_env", lambda env: (env, []))
    monkeypatch.setattr(installer.subprocess, "run", run)
    monkeypatch.setattr(installer, "build_compiler", build_seed)
    monkeypatch.setattr(installer, "verify_seed_interfaces", verify)
    monkeypatch.setattr(installer, "build_payload", payload)
    env = {"L1_BUILD_DIR": str(build), "L1_CFLAGS": "-Dcustom=1", "KEEP_C": "1",
           "L0_HOME": "stale", "L1_HOME": "stale", "L1_SYSTEM": "stale", "L1_STDLIB_CACHE": "stale"}
    if with_docs:
        env["DOCS_ARTIFACT"] = str(docs_bundle(tmp_path))
        monkeypatch.setattr(installer, "source_identity", lambda *args: dict(DOCS_SOURCE))
    if failure:
        with pytest.raises(RuntimeError, match=failure):
            installer.install(str(prefix), env, make="selected-make")
        assert not prefix.exists()
    else:
        assert installer.install(str(prefix), env, make="selected-make") == prefix
        assert read_inventory(prefix)["state"] == "complete"
        assert calls == ["stage1", "seed", "interfaces", "payload"]
        if with_docs:
            docs = prefix / DOCS_RELATIVE
            verify_tree(docs, stage="stage2", version="dev", source=DOCS_SOURCE)
            assert (DOCS_RELATIVE / "html/index.html").as_posix() in list_installed(prefix)
            # Reinstall without docs removes only owned docs, retaining unrelated files.
            (docs / "personal-note.txt").write_text("preserve")
            installer.install(str(prefix), {k: v for k, v in env.items() if k != "DOCS_ARTIFACT"}, make="selected-make")
            assert not (docs / "html/index.html").exists()
            assert (docs / "personal-note.txt").read_text() == "preserve"
            assert not any(path.startswith(DOCS_RELATIVE.as_posix()) for path in list_installed(prefix))
            installer.install(str(prefix), env, make="selected-make")
            assert (docs / "html/index.html").is_file()
            assert (docs / "personal-note.txt").read_text() == "preserve"
            # Checkout changes during construction must leave the old installation intact.
            before = {p.relative_to(prefix): p.read_bytes() for p in prefix.rglob("*") if p.is_file()}
            identities = iter([dict(DOCS_SOURCE), {**DOCS_SOURCE, "input_digest": "b" * 64}])
            monkeypatch.setattr(installer, "source_identity", lambda *args: next(identities))
            with pytest.raises(ValueError, match="source identity changed"):
                installer.install(str(prefix), env, make="selected-make")
            assert before == {p.relative_to(prefix): p.read_bytes() for p in prefix.rglob("*") if p.is_file()}
    assert list(build.iterdir()) == [build / "bin"]
    assert all(path.read_bytes() == b"preserved development artifact" for path in (build / "bin").iterdir())


@pytest.mark.parametrize("prefix", ["", ".", "compiler/nested", "scripts", "docs", "build/dea", "../l0"])
def test_invalid_destination_fails_before_bootstrap(checkout, monkeypatch, prefix):
    monkeypatch.setattr(installer, "bootstrap_upstream", lambda *args: pytest.fail("must preflight first"))
    with pytest.raises(ValueError):
        installer.install(prefix, {})


@pytest.mark.parametrize("env", [{"DEA_DIST_VERSION": "bad/version"}, {"DOCS_ARTIFACT": "bundle.zip"},
                                  {"L1_BUILD_DIR": "compiler/scratch"}])
def test_unsupported_package_inputs_fail_early(checkout, tmp_path, monkeypatch, env):
    monkeypatch.setattr(installer, "bootstrap_upstream", lambda *args: pytest.fail("must preflight first"))
    with pytest.raises(ValueError):
        installer.install(str(tmp_path / "prefix"), env)


def test_invalid_override_never_prepares_default_or_uses_path(checkout, tmp_path, monkeypatch):
    monkeypatch.setattr(installer.subprocess, "run", lambda *a, **kw: pytest.fail("must not build default"))
    with pytest.raises(RuntimeError, match="L1_BOOTSTRAP_L0C"):
        installer.bootstrap_upstream({"L1_BOOTSTRAP_L0C": str(tmp_path / "absent"), "PATH": str(tmp_path)}, "make")


def test_default_bootstrap_prepared_once_without_selecting_alias(checkout, monkeypatch):
    default = checkout.parent / "l0/build/dea/bin/l0c-stage2"
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[-2] == "install-dev-stage2":
            default.parent.mkdir(parents=True)
            default.write_bytes(b"upstream")

    monkeypatch.setattr(installer.subprocess, "run", run)
    assert installer.bootstrap_upstream({}, "chosen-make") == default
    assert [call[-2] for call in calls] == ["venv", "install-dev-stage2"]
    assert all(call[0] == "chosen-make" and call[-1] == "DEA_BUILD_DIR=build/dea" for call in calls)
    assert installer.bootstrap_upstream({}, "chosen-make") == default
    assert len(calls) == 2


@pytest.mark.parametrize("matching", [True, False])
def test_stage2_interface_agreement(checkout, tmp_path, monkeypatch, matching):
    source = checkout / "compiler/shared/l1/stdlib/std/io.l1"
    source.parent.mkdir(parents=True)
    source.write_text("module std.io;")
    layout = tmp_path / "layout"
    canonical = layout / "interfaces/std/io.l1m"
    canonical.parent.mkdir(parents=True)
    canonical.write_bytes(b"canonical")

    def run(command, **kwargs):
        assert command[-3] == "std.io"
        Path(command[-1]).write_bytes(b"canonical" if matching else b"different")

    monkeypatch.setattr(installer.subprocess, "run", run)
    if matching:
        installer.verify_seed_interfaces(layout, tmp_path / "seed", {})
    else:
        with pytest.raises(ValueError, match="Stage 2 interface differs from Stage 1: std.io"):
            installer.verify_seed_interfaces(layout, tmp_path / "seed", {})
    assert list(layout.iterdir()) == [layout / "interfaces"]


def test_public_make_listing_is_inventory_only(tmp_path):
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "VERSION").write_text("fixture")
    # Quotes and shell punctuation must stay literal, including on native Windows.
    prefix = tmp_path / "prefix with spaces ' ; &"
    record = install_payload(payload, prefix, metadata())
    (prefix / "unrelated").write_text("preserve")
    command = ["make", "--no-print-directory", "-s", "list-installed", f"PREFIX={prefix}",
               f"PYTHON={sys.executable}", "L1_BOOTSTRAP_L0C=/absent/compiler", "L1_BUILD_DIR=/invalid/build",
               "VENV_PYTHON=/absent/python"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == sorted(entry["path"] for entry in record["entries"])
    manifest = prefix / MANIFEST_PATH
    for content in (None, "{", json.dumps({**record, "state": "incomplete", "previous_entries": record["entries"]})):
        if content is None:
            manifest.unlink()
        else:
            manifest.write_text(content)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        assert result.returncode != 0 and "list-installed:" in result.stderr
        assert not result.stdout


@pytest.mark.parametrize("target", ["install", "list-installed"])
def test_public_make_requires_prefix_without_bootstrap(target):
    result = subprocess.run(["make", "--no-print-directory", "-s", target, "PREFIX=", f"PYTHON={sys.executable}"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0
    assert "PREFIX is required" in result.stderr
    assert not result.stdout


def test_make_dry_run_does_not_invoke_installer():
    result = subprocess.run(["make", "--no-print-directory", "-n", "install", "PREFIX=", "PYTHON=/absent/python"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "scripts/install_toolchain.py install" in result.stdout


def test_public_make_invalid_override_fails_without_installing(tmp_path):
    prefix = tmp_path / "prefix"
    result = subprocess.run(["make", "--no-print-directory", "-s", "install", f"PREFIX={prefix}",
                             f"PYTHON={sys.executable}", f"L1_BOOTSTRAP_L0C={tmp_path / 'missing compiler'}"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0
    assert "missing bootstrap compiler" in result.stderr
    assert "L1_BOOTSTRAP_L0C" in result.stderr
    assert not result.stdout and not prefix.exists()


@pytest.mark.parametrize("problem", ["stage", "version", "revision", "dirty", "inputs", "incomplete", "tampered", "unsafe"])
def test_invalid_docs_preserve_prefix_before_bootstrap(checkout, tmp_path, monkeypatch, problem):
    bundle = docs_bundle(tmp_path)
    extraction = tmp_path / "extracted"
    unpack_bundle(bundle, extraction, stage="stage2", version="dev", source=DOCS_SOURCE)
    tree = extraction / "dea-l1-stage2-autodocs"
    manifest_path = tree / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if problem == "stage":
        manifest["stage"] = 1
    elif problem == "version":
        manifest["package_version"] = "other"
    elif problem in {"revision", "dirty", "inputs"}:
        field = {"revision": "revision", "dirty": "tree_state", "inputs": "input_digest"}[problem]
        manifest["source"][field] = "different"
    elif problem == "incomplete":
        manifest["full_pdf"] = False
    elif problem == "tampered":
        (tree / "html/index.html").write_text("tampered")
    manifest_path.write_text(json.dumps(manifest))
    with tarfile.open(bundle, "w:gz") as archive:
        archive.add(tree, arcname=tree.name)
        if problem == "unsafe":
            archive.add(manifest_path, arcname="../escape")
    prefix = tmp_path / "existing install"
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "VERSION").write_text("previous")
    install_payload(payload, prefix, metadata())
    before = {p.relative_to(prefix): p.read_bytes() for p in prefix.rglob("*") if p.is_file()}
    monkeypatch.setattr(installer, "source_identity", lambda *args: dict(DOCS_SOURCE))
    monkeypatch.setattr(installer, "bootstrap_upstream", lambda *args: pytest.fail("must validate docs first"))
    with pytest.raises(ValueError):
        installer.install(str(prefix), {"DOCS_ARTIFACT": str(bundle)})
    assert before == {p.relative_to(prefix): p.read_bytes() for p in prefix.rglob("*") if p.is_file()}
    assert not list((checkout / "build/dea").iterdir())


def test_docs_input_inside_destination_rejected(checkout, tmp_path, monkeypatch):
    destination = tmp_path / "destination"
    bundle = docs_bundle(destination)
    monkeypatch.setattr(installer, "bootstrap_upstream", lambda *args: pytest.fail("must preflight first"))
    before = bundle.read_bytes()
    with pytest.raises(ValueError, match="overlap"):
        installer.install(str(destination), {"DOCS_ARTIFACT": str(bundle)})
    assert bundle.read_bytes() == before
