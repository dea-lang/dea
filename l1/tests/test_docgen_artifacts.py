# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Offline bundle integrity, identity, and extraction boundaries."""
import io
import json
from pathlib import Path
import sys
import tarfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from docs_artifacts import create_bundle, unpack_bundle, verify_tree, package_version, source_identity

SOURCE = {'revision': 'fixture', 'tree_state': 'dirty', 'input_digest': 'a' * 64}
TOOLS = dict(doxygen='test', pdflatex='test', python='test', mcss='test')


def fixture(tmp_path):
    tree = tmp_path / 'source'
    (tree / 'html').mkdir(parents=True)
    (tree / 'pdf').mkdir()
    (tree / 'html/index.html').write_text('<a href="../pdf/dea_l1_stage2_api_reference.pdf">PDF</a>')
    (tree / 'pdf/dea_l1_stage2_api_reference.pdf').write_bytes(b'%PDF-1.7\nfixture\n%%EOF\n')
    bundle = tmp_path / 'bundle.tar.gz'
    create_bundle(tree, bundle, stage='stage2', version='dev', source=SOURCE, tools=TOOLS)
    unpack_bundle(bundle, tmp_path / 'out', stage='stage2', version='dev', source=SOURCE)
    return tmp_path / 'out/dea-l1-stage2-autodocs', bundle


def test_roundtrip_and_corruption(tmp_path):
    tree, bundle = fixture(tmp_path)
    manifest = verify_tree(tree, stage='stage2', version='dev', source=SOURCE)
    assert manifest['stage'] == 2
    assert set(manifest['files']) == {'html/index.html', 'pdf/dea_l1_stage2_api_reference.pdf'}
    (tree / 'html/index.html').write_text('corrupt')
    with pytest.raises(ValueError, match='digests'):
        verify_tree(tree, stage='stage2', version='dev', source=SOURCE)


@pytest.mark.parametrize('field,value', [('level','l0'),('stage',1),('stage','stage2'),('schema_version',True),('strict',1),('strict',False),('full_pdf',False),('package_version','wrong'),('source',{})])
def test_identity_mismatch(tmp_path, field, value):
    tree, _ = fixture(tmp_path)
    manifest = json.loads((tree / 'manifest.json').read_text())
    manifest[field] = value
    (tree / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='identity'):
        verify_tree(tree, stage='stage2', version='dev', source=SOURCE)


@pytest.mark.parametrize('link', ['../../stage1/html/index.html','file:///etc/passwd','/absolute','missing.html','%2e%2e/%2e%2e/outside'])
def test_links_cannot_escape_or_be_missing(tmp_path, link):
    tree, _ = fixture(tmp_path)
    (tree / 'html/index.html').write_text(f'<a href="{link}">bad</a>')
    with pytest.raises(ValueError, match='link|resource'):
        create_bundle(tree, tmp_path / 'bad.tar.gz', stage='stage2', version='dev', source=SOURCE, tools=TOOLS)


def test_external_prose_links_allowed_but_assets_rejected(tmp_path):
    tree, _ = fixture(tmp_path)
    (tree / 'html/index.html').write_text('<a href="https://github.com/dea-lang/dea">Repository</a>')
    create_bundle(tree, tmp_path / 'valid.tar.gz', stage='stage2', version='dev', source=SOURCE, tools=TOOLS)
    (tree / 'html/index.html').write_text('<script src="https://example.org/app.js"></script>')
    with pytest.raises(ValueError, match='resource'):
        create_bundle(tree, tmp_path / 'bad.tar.gz', stage='stage2', version='dev', source=SOURCE, tools=TOOLS)


@pytest.mark.parametrize('name,kind', [('../outside', 'file'),('/absolute','file'),('dea-l1-stage2-autodocs/html/../../outside','file'),('dea-l1-stage2-autodocs/html/link','link'),('dea-l1-stage2-autodocs/html/C:evil','file'),('dea-l1-stage2-autodocs/html/x','duplicate')])
def test_unsafe_archive_members(tmp_path, name, kind):
    bundle = tmp_path / 'bad.tar.gz'
    with tarfile.open(bundle,'w:gz') as archive:
        member = tarfile.TarInfo(name)
        if kind == 'link':
            member.type = tarfile.SYMTYPE
            member.linkname = '/etc/passwd'
            archive.addfile(member)
        else:
            member.size = 1
            archive.addfile(member, io.BytesIO(b'x'))
            if kind == 'duplicate':
                archive.addfile(member, io.BytesIO(b'x'))
    with pytest.raises(ValueError, match='unsafe'):
        unpack_bundle(bundle, tmp_path / 'out', stage='stage2', version='dev', source=SOURCE)


def test_duplicate_manifest_entries(tmp_path):
    tree, _ = fixture(tmp_path)
    path = tree / 'manifest.json'
    path.write_text(path.read_text().replace('"level": "l1",','"level": "l0", "level": "l1",'))
    with pytest.raises(ValueError, match='duplicate'):
        verify_tree(tree, stage='stage2', version='dev', source=SOURCE)


def test_version_and_source_contract(monkeypatch):
    monkeypatch.delenv('DEA_DIST_VERSION', raising=False)
    monkeypatch.delenv('L1_DOCS_RELEASE_TAG', raising=False)
    assert package_version(ROOT) == 'dev'
    monkeypatch.setenv('L1_DOCS_RELEASE_TAG', 'v1.2.3')
    with pytest.raises(ValueError, match='agree'):
        package_version(ROOT)
    monkeypatch.setenv('DEA_DIST_VERSION','1.2.3')
    assert package_version(ROOT) == '1.2.3'
    assert source_identity(ROOT, 'stage1')['input_digest'] != source_identity(ROOT, 'stage2')['input_digest']


@pytest.mark.parametrize('tag,version', [('l1-v1.2.3','1.2.3'),('l1-snapshot-20261006','snapshot-20261006')])
def test_hosted_l1_tag_mapping(monkeypatch, tag, version):
    monkeypatch.setenv('L1_DOCS_RELEASE_TAG', tag)
    monkeypatch.setenv('DEA_DIST_VERSION', version)
    assert package_version(ROOT) == version
