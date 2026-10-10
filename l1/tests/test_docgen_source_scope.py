# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Canonical source boundaries and native build ownership."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from compiler.docgen.l1_docgen_sources import build_source_manifest
from build_l1c import COMPILER_SUPPORT_SOURCES


def test_source_scope_and_native_build_contract():
    files = set(build_source_manifest(ROOT).files)
    assert files and all((ROOT / p).is_file() for p in files)
    assert {p.relative_to(ROOT) for p in COMPILER_SUPPORT_SOURCES} <= files
    assert not any('stage1_l0' in p.parts or 'stage2_l1' in p.parts for p in files)
    assert not any(set(p.parts) & {'tests', 'fixtures', 'build', 'work'} for p in files)
    assert Path('compiler/src/l1c.l0') in files
    assert Path('compiler/support/installation.h') in files
    assert Path('compiler/support/interface_fingerprint.c') in files
    assert Path('compiler/shared/runtime/internal/dea_interface_fingerprint.h') in files
    assert Path('compiler/shared/runtime/include/dea_rt.h') in files
    assert Path('compiler/shared/l1/stdlib/std/string.l1') in files


def test_canonical_inventory_excludes_transplanted_sources(tmp_path):
    from compiler.docgen.l1_docgen import _build_shadow_tree
    retained = tmp_path / 'compiler/src/repeated.l0'
    retained.parent.mkdir(parents=True)
    retained.write_text('module repeated;\nfunc repeated() -> int;\n')
    obsolete = tmp_path / 'compiler/stage2_l1/src/repeated.l1'
    obsolete.parent.mkdir(parents=True)
    obsolete.write_text('module repeated;\nfunc repeated() -> ulong;\n')
    manifest = build_source_manifest(tmp_path)
    for relative in manifest.files:
        path = tmp_path / relative
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('')
    shadow = tmp_path / 'shadow'
    _build_shadow_tree(tmp_path, manifest, shadow)
    assert list(shadow.rglob('repeated.*')) == [shadow / 'compiler/src/repeated.l0']
    assert 'int repeated();' in (shadow / 'compiler/src/repeated.l0').read_text()
