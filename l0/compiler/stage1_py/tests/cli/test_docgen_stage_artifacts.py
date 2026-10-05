# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Regression coverage for independent stage output and offline distribution integrity."""

from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
import io
import json
import subprocess
import sys
import tarfile

import pytest
from jinja2 import Environment, FileSystemLoader

from compiler.docgen import l0_docgen

ROOT = l0_docgen.repo_root()
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from docs_artifacts import package_version, source_identity, unpack_bundle, verify_tree
from docs_fixture import docs_fixture
from stage_docs_pages import stage_pages
import gen_docs


def test_bundle_consumers_work_without_rendering_dependencies(tmp_path: Path) -> None:
    """Exercise CI's system-Python path with third-party imports disabled."""
    bundles = {stage: docs_fixture(tmp_path / stage, stage) for stage in ("stage1", "stage2")}
    script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from docs_artifacts import package_version, source_identity, unpack_bundle
import gen_docs
import gen_dist_tools
import dist_tools_lib
root = Path(sys.argv[2])
for stage, bundle in zip(("stage1", "stage2"), sys.argv[3:]):
    bundle = Path(bundle)
    unpack_bundle(bundle, bundle.parent / "extracted", stage=stage,
                  version=package_version(root), source=source_identity(root, stage))
assert "jinja2" not in sys.modules
assert "compiler.docgen.l0_docgen" not in sys.modules
"""
    subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, str(ROOT / "scripts"), str(ROOT),
         *(str(bundle) for bundle in bundles.values())],
        check=True, capture_output=True, text=True,
    )


@pytest.mark.parametrize("path_type", [PurePosixPath, PureWindowsPath])
def test_stage_source_boundaries(path_type: type[PurePath]) -> None:
    one = {path_type(p.as_posix()) for p in l0_docgen.build_source_manifest(ROOT, "stage1").files}
    two = {path_type(p.as_posix()) for p in l0_docgen.build_source_manifest(ROOT, "stage2").files}
    assert not any(p.as_posix().startswith("compiler/stage2_l0") for p in one)
    assert not any(p.as_posix().startswith("compiler/stage1_py") for p in two)
    assert {p.as_posix() for p in one & two if p.suffix == ".h"} == {
        "compiler/shared/runtime/dea_rt.h", "compiler/shared/runtime/dea_siphash.h", "compiler/shared/runtime/l0_runtime.h"}
    assert any(p.as_posix().startswith("compiler/shared/l0/stdlib") for p in one & two)


@pytest.mark.parametrize("stage", ["stage1", "stage2"])
def test_stage_templates_have_isolated_navigation(stage: str) -> None:
    env = Environment(loader=FileSystemLoader(str(ROOT / "scripts/docs/templates")))
    other = "stage2" if stage == "stage1" else "stage1"
    for name in ("mainpage_html.md.j2", "mcss_conf.py.in", "html_api_page.j2", "html_api_group.j2"):
        text = env.get_template(name).render(stage=stage, root_prefix=".")
        assert f"Dea/L0 Stage {stage[-1]}" in text
        assert f"{other}.html" not in text
        assert f"dea_l0_{stage}_api_reference.pdf" in text
        assert "fonts.googleapis" not in text


def test_all_runs_independent_pipelines_and_preserves_other_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def generate(args):
        manifest = l0_docgen.build_source_manifest(ROOT, args.stage)
        args.output_dir.mkdir()
        (args.output_dir / "inventory").write_text("\n".join(p.as_posix() for p in manifest.files))
        return 0
    monkeypatch.setattr(l0_docgen, "_generate_stage", generate)
    l0_docgen.main(["--output-dir", str(tmp_path)])
    one = (tmp_path / "stage1/inventory").read_bytes()
    two = (tmp_path / "stage2/inventory").read_bytes()
    assert b"stage2_l0" not in one and b"stage1_py" not in two
    l0_docgen.main(["--stage", "stage2", "--output-dir", str(tmp_path)])
    assert (tmp_path / "stage1/inventory").read_bytes() == one
    def fail(args):
        raise SystemExit("strict warnings")
    monkeypatch.setattr(l0_docgen, "_generate_stage", fail)
    artifact = tmp_path / "artifacts/dea_l0_stage2_autodocs.tar.gz"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_bytes(b"prior success")
    with pytest.raises(SystemExit):
        l0_docgen.main(["--stage", "stage2", "--output-dir", str(tmp_path)])
    assert (tmp_path / "stage2/inventory").read_bytes() == two
    assert not artifact.exists()
    assert (tmp_path / "stage2-failure").is_dir()


def test_wrapper_failure_invalidates_bundle_but_preserves_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "docs"
    for stage in ("stage1", "stage2"):
        (output / stage / "pdf").mkdir(parents=True)
        (output / stage / "pdf/old.pdf").write_bytes(b"old")
    artifact = output / "artifacts/dea_l0_stage2_autodocs.tar.gz"
    artifact.parent.mkdir()
    artifact.write_bytes(b"old success")
    monkeypatch.setattr(gen_docs, "require_command", lambda *a: None)
    monkeypatch.setattr(gen_docs, "run_logged", lambda *a, **kw: (_ for _ in ()).throw(SystemExit(1)))
    assert gen_docs.main(["--stage", "stage2", "--strict", "--pdf", "--artifacts", "--output-dir", str(output)]) == 1
    assert not artifact.exists()
    assert (output / "stage1/pdf/old.pdf").read_bytes() == b"old"
    assert (output / "stage2/pdf/old.pdf").read_bytes() == b"old"
    assert (output / "stage2-failure").is_dir()


def test_fast_pdf_cannot_claim_distribution_success() -> None:
    assert gen_docs.main(["--pdf-fast", "--artifacts", "--strict"]) == 1


def test_bundle_roundtrip_and_digest_verification(tmp_path: Path) -> None:
    bundle = docs_fixture(tmp_path / "fixture")
    identity = source_identity(ROOT, "stage2")
    unpack_bundle(bundle, tmp_path / "unpack", stage="stage2", version=package_version(ROOT), source=identity)
    tree = tmp_path / "unpack/dea-l0-stage2-autodocs"
    (tree / "html/index.html").write_text("corrupt")
    with pytest.raises(ValueError, match="digests"):
        verify_tree(tree, stage="stage2", version=package_version(ROOT), source=identity)


@pytest.mark.parametrize("field,value", [("strict", 1), ("schema_version", True), ("stage", "stage1"), ("package_version", "other"), ("strict", False), ("full_pdf", False), ("schema_version", 2), ("source", {})])
def test_bundle_rejects_wrong_or_partial_identity(tmp_path: Path, field: str, value) -> None:
    bundle = docs_fixture(tmp_path / "fixture")
    tree = tmp_path / "tree"
    with tarfile.open(bundle) as archive:
        archive.extractall(tree, filter="data")
    root = tree / "dea-l0-stage2-autodocs"
    manifest = json.loads((root / "manifest.json").read_text())
    manifest[field] = value
    (root / "manifest.json").write_text(json.dumps(manifest))
    with tarfile.open(bundle, "w:gz") as archive:
        archive.add(root, arcname=root.name)
    with pytest.raises(ValueError, match="identity"):
        unpack_bundle(bundle, tmp_path / "out", stage="stage2", version=package_version(ROOT), source=source_identity(ROOT, "stage2"))


@pytest.mark.parametrize("name,link", [("../outside", False), ("/absolute", False), ("dea-l0-stage2-autodocs/html/link", True), ("dea-l0-stage2-autodocs/html/../../outside", False), ("dea-l0-stage2-autodocs/html/C:evil", False)])
def test_bundle_rejects_unsafe_members(tmp_path: Path, name: str, link: bool) -> None:
    bundle = tmp_path / "unsafe.tar.gz"
    with tarfile.open(bundle, "w:gz") as archive:
        member = tarfile.TarInfo(name)
        if link:
            member.type = tarfile.SYMTYPE
            member.linkname = "../../outside"
            archive.addfile(member)
        else:
            member.size = 4
            archive.addfile(member, io.BytesIO(b"evil"))
    with pytest.raises(ValueError, match="unsafe"):
        unpack_bundle(bundle, tmp_path / "out", stage="stage2", version=package_version(ROOT), source=source_identity(ROOT, "stage2"))
    assert not (tmp_path / "outside").exists()


def test_pages_preserves_pdf_alias_and_notices(tmp_path: Path) -> None:
    docs_fixture(tmp_path / "fixture")
    source = tmp_path / "fixture/stage2"
    destination = tmp_path / "pages"
    stage_pages(source, destination)
    assert (destination / "pdf/dea_l0_api_reference.pdf").read_bytes() == (source / "pdf/dea_l0_stage2_api_reference.pdf").read_bytes()
    assert "Stage 1 reference moved" in (destination / "stage1.html").read_text()
    assert "Historical release downloads" in (destination / "404.html").read_text()
    assert "Stage 1 reference moved" in (destination / "api/compiler/stage1_py/l0_ast.html").read_text()
    assert "Stage 1 reference moved" in (destination / "classl0__ast_1_1_node.html").read_text()
    assert not (source / "html/stage1.html").exists()


@pytest.mark.parametrize("host", ["Linux 6 x86_64", "Darwin 24 x86_64", "Darwin 24 arm64", "Windows 10 x86_64"])
def test_distribution_embeds_verified_docs_on_all_archive_hosts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, host: str) -> None:
    from dataclasses import replace
    import os
    import dist_tools_lib as dist

    bundle = docs_fixture(tmp_path / "fixture")
    native = tmp_path / "l0c.native"
    native.write_bytes(b"native compiler fixture")
    layout = dist.normalize_prefix_dir(str(tmp_path / "dea-l0"))
    provenance, _ = dist.collect_stage2_build_provenance(ROOT, os.environ.copy())
    provenance = replace(provenance, host=host)
    monkeypatch.setattr(dist, "is_windows_host", lambda: host.startswith("Windows"))
    result = dist.create_stage2_distribution(layout, native, "archive", provenance, docs_artifact=bundle)
    unpack = tmp_path / "unpacked"
    if result.archive_path.suffix == ".zip":
        import zipfile
        with zipfile.ZipFile(result.archive_path) as archive:
            archive.extractall(unpack)
    else:
        with tarfile.open(result.archive_path) as archive:
            archive.extractall(unpack, filter="data")
    tree = unpack / "dea-l0/share/doc/dea/l0/autodocs/stage2"
    manifest = verify_tree(tree, stage="stage2", version=package_version(ROOT), source=source_identity(ROOT, "stage2"))
    assert manifest["files"]["html/index.html"]
    assert not (unpack / "dea-l0/share/doc/dea/l0/autodocs/stage1").exists()


def test_missing_docs_blocks_compiler_packaging_before_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    import gen_dist_tools
    monkeypatch.delenv("DOCS_ARTIFACT", raising=False)
    monkeypatch.setattr(gen_dist_tools, "parse_args", lambda: SimpleNamespace(command="make-dist"))
    monkeypatch.setattr(gen_dist_tools, "build_stage2_artifact", lambda *a, **kw: pytest.fail("compiler build started without docs"))
    assert gen_dist_tools.main() == 1
