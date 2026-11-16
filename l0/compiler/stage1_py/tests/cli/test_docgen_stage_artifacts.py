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


@pytest.mark.parametrize("stage", ["stage1", "stage2"])
def test_stage_front_pages_share_tagline(stage: str) -> None:
    templates = ROOT / "scripts/docs/templates"
    tagline = (templates / "tagline.txt.j2").read_text(encoding="utf-8").strip()
    env = Environment(loader=FileSystemLoader(templates))
    for name in ("mainpage_html.md.j2", "mainpage_latex.md.j2", "markdown_index.md.j2"):
        text = env.get_template(name).render(stage=stage, stage1=[], stage2=[], shared=[])
        assert f"Dea/L0 Stage {stage[-1]}" in text
        assert f"*{tagline}*" in text


def test_l0_readmes_match_shared_tagline() -> None:
    tagline = (ROOT / "scripts/docs/templates/tagline.txt.j2").read_text(encoding="utf-8").strip()
    for name in ("README.md", "docs/user/README.md", "docs/user/README-WINDOWS.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        quote = next(block for block in text.split("\n\n") if block.startswith("> "))
        quote = " ".join(line.removeprefix("> ").strip() for line in quote.splitlines())
        assert quote == f"_{tagline}_"


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


def pages_fixture(source: Path) -> None:
    """Build isolated HTML, search, and PDF inputs with nested source pages."""
    for stage in ("stage1", "stage2"):
        docs_fixture(source, stage)
        tree = source / stage / "html"
        (tree / "index.html").write_text(
            f'<html><title>Dea/L0 Stage {stage[-1]}</title><body><header></header>'
            '<a href="search.js">Search</a></body></html>')
        (tree / "search.js").write_text(f"search data for {stage}")
        (tree / "searchdata.bin").write_bytes(stage.encode())
        (tree / f"{stage}.html").write_text('<html><body>Stage hub</body></html>')
        nested = tree / f"api/compiler/{'stage1_py' if stage == 'stage1' else 'stage2_l0'}/source.html"
        nested.parent.mkdir(parents=True)
        nested.write_text('<html><body class="m-doc">Source</body></html>')
    (source / "stage1/html/python_classl0__ast_1_1_node.html").write_text('<html><body>Node</body></html>')


@pytest.mark.parametrize("with_pdf", [True, False])
def test_pages_workflow_input_layout(tmp_path: Path, with_pdf: bool) -> None:
    import os
    import shutil
    import yaml

    if os.name == "nt":
        pytest.skip("Pages assembly runs on Ubuntu")
    source = tmp_path / "build/docs"
    pages_fixture(source)
    workflow = yaml.safe_load((ROOT.parent / ".github/workflows/l0-docs-build.yml").read_text())
    steps = workflow["jobs"]["build-docs"]["steps"]
    prepare = next(step["run"] for step in steps if step.get("name") == "Prepare Pages inputs")
    for stage in ("stage1", "stage2"):
        (source / stage / "private-build.log").write_text("not part of Pages")
        if not with_pdf:
            shutil.rmtree(source / stage / "pdf")
        subprocess.run(["bash", "-e", "-c", prepare], cwd=tmp_path,
                       env={**os.environ, "DOC_STAGE": stage}, check=True)
        tree = source / "pages-input" / stage
        assert (tree / "html/index.html").is_file()
        assert (tree / "pdf").is_dir() == with_pdf
        assert not (tree / "private-build.log").exists()
    stage_pages(source / "pages-input", tmp_path / "pages")


def test_pages_isolates_references_and_preserves_inputs(tmp_path: Path) -> None:
    from html.parser import HTMLParser
    from urllib.parse import urljoin

    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.links.append(dict(attrs)["href"])

    source, destination = tmp_path / "docs", tmp_path / "pages"
    pages_fixture(source)
    before = {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}
    stage_pages(source, destination)
    for stage, prefix in (("stage1", "stage1/"), ("stage2", "")):
        tree = destination / prefix
        assert (tree / "searchdata.bin").read_bytes() == stage.encode()
        assert (tree / "search.js").read_bytes() == (source / stage / "html/search.js").read_bytes()
        assert (tree / f"pdf/dea_l0_{stage}_api_reference.pdf").read_bytes() == (source / stage / f"pdf/dea_l0_{stage}_api_reference.pdf").read_bytes()
        for original in (source / stage / "html").rglob("*.html"):
            rel = original.relative_to(source / stage / "html")
            page = tree / rel
            text = page.read_text()
            assert text.count('aria-label="Reference stage"') == 1
            assert text.count('aria-current="true"') == 1
            links = Links()
            links.feed(text)
            targets = [urljoin('/dea/' + page.relative_to(destination).as_posix(), link) for link in links.links]
            assert '/dea/index.html' in targets
            assert '/dea/stage1/index.html' in targets
            assert all((destination / target.removeprefix('/dea/')).is_file() for target in targets)
    assert (destination / "pdf/dea_l0_api_reference.pdf").read_bytes() == (destination / "pdf/dea_l0_stage2_api_reference.pdf").read_bytes()
    assert 'href="stage1/stage1.html"' in (destination / "stage1.html").read_text()
    assert 'href="stage1/python_classl0__ast_1_1_node.html"' in (destination / "classl0__ast_1_1_node.html").read_text()
    assert 'href="../../../stage1/index.html"' in (destination / "api/compiler/stage1_py/l0_ast.html").read_text()
    assert (destination / ".nojekyll").is_file()
    assert before == {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}
    # Restaging replaces stale output without stacking selectors or reusing either search index.
    (destination / "stale.html").touch()
    stage_pages(source, destination)
    assert not (destination / "stale.html").exists()
    assert (destination / "index.html").read_text().count('aria-label="Reference stage"') == 1


@pytest.mark.parametrize("base_path", ["/dea/", "/DEA/", "/"])
def test_pages_404_links_work_from_nested_urls(tmp_path: Path, base_path: str) -> None:
    source, destination = tmp_path / "docs", tmp_path / "pages"
    pages_fixture(source)
    stage_pages(source, destination, base_path=base_path)
    text = (destination / "404.html").read_text()
    assert f'href="{base_path}stage1/index.html"' in text
    assert f'href="{base_path}index.html"' in text


@pytest.mark.parametrize("stage", ["stage1", "stage2"])
@pytest.mark.parametrize("failure", ["missing", "wrong-title", "malformed"])
def test_pages_rejects_incomplete_inputs_without_replacing_site(tmp_path: Path, stage: str, failure: str) -> None:
    source, destination = tmp_path / "docs", tmp_path / "pages"
    pages_fixture(source)
    destination.mkdir()
    (destination / "index.html").write_text("previous publication")
    index = source / stage / "html/index.html"
    if failure == "missing":
        index.unlink()
    elif failure == "wrong-title":
        index.write_text("Wrong stage")
    else:
        index.write_text(f"Dea/L0 Stage {stage[-1]} without a body")
    with pytest.raises(ValueError, match="Pages"):
        stage_pages(source, destination)
    assert (destination / "index.html").read_text() == "previous publication"


def test_pages_preserves_stage2_on_legacy_name_collision(tmp_path: Path) -> None:
    source, destination = tmp_path / "docs", tmp_path / "pages"
    pages_fixture(source)
    (source / "stage2/html/classl0__ast_1_1_node.html").write_text('<html><body>Stage 2 symbol</body></html>')
    stage_pages(source, destination)
    assert "Stage 2 symbol" in (destination / "classl0__ast_1_1_node.html").read_text()
    assert "Node" in (destination / "stage1/python_classl0__ast_1_1_node.html").read_text()


def test_pages_supports_html_only_without_inventing_pdfs(tmp_path: Path) -> None:
    import shutil
    source, destination = tmp_path / "docs", tmp_path / "pages"
    pages_fixture(source)
    for stage in ("stage1", "stage2"):
        shutil.rmtree(source / stage / "pdf")
    stage_pages(source, destination)
    assert not (destination / "pdf").exists()
    assert not (destination / "stage1/pdf").exists()


def test_pages_rejects_overlapping_inputs(tmp_path: Path) -> None:
    source = tmp_path / "docs"
    pages_fixture(source)
    for destination in (source, source / "stage1/html/pages"):
        with pytest.raises(ValueError, match="overlap"):
            stage_pages(source, destination)


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
