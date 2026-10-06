# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Stage source boundaries and native build ownership."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from compiler.docgen.l1_docgen_sources import build_source_manifest
from build_stage1_l1c import STAGE1_SUPPORT_SOURCES
from build_stage2_l1c import STAGE2_SUPPORT_SOURCES


def test_stage_scope_and_native_build_contract():
    inventories = {s: set(build_source_manifest(ROOT, s).files) for s in ('stage1', 'stage2')}
    for stage, native in [('stage1', STAGE1_SUPPORT_SOURCES), ('stage2', STAGE2_SUPPORT_SOURCES)]:
        files = inventories[stage]
        assert files and all((ROOT / p).is_file() for p in files)
        assert {p.relative_to(ROOT) for p in native} <= files
        other = 'stage2_l1' if stage == 'stage1' else 'stage1_l0'
        assert not any(p.as_posix().startswith(f'compiler/{other}/src/') for p in files)
        assert not any(set(p.parts) & {'tests', 'fixtures', 'build', 'work'} for p in files)
    assert Path('compiler/stage1_l0/support/interface_fingerprint.c') not in inventories['stage2']
    assert Path('compiler/shared/runtime/internal/dea_interface_fingerprint.h') in inventories['stage1']
    assert Path('compiler/shared/runtime/internal/dea_interface_fingerprint.h') not in inventories['stage2']
    shared = inventories['stage1'] & inventories['stage2']
    assert Path('compiler/shared/runtime/include/dea_rt.h') in shared
    assert Path('compiler/shared/l1/stdlib/std/string.l1') in shared
    assert set(build_source_manifest(ROOT).files) == inventories['stage1'] | inventories['stage2']


def test_duplicate_module_and_symbol_names_remain_stage_local(tmp_path):
    from compiler.docgen.l1_docgen import _build_shadow_tree
    for directory, suffix, result in [('stage1_l0','l0','int'),('stage2_l1','l1','ulong')]:
        path = tmp_path / f'compiler/{directory}/src/repeated.{suffix}'
        path.parent.mkdir(parents=True)
        path.write_text(f'module repeated;\nfunc repeated() -> {result};\n')
    for stage, directory, suffix, result in [('stage1','stage1_l0','l0','int'),('stage2','stage2_l1','l1','ulong')]:
        manifest = build_source_manifest(tmp_path, stage)
        for relative in manifest.files:
            path = tmp_path / relative
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('')
        shadow = tmp_path / f'shadow-{stage}'
        _build_shadow_tree(tmp_path, manifest, shadow)
        declarations = list(shadow.rglob('repeated.*'))
        assert declarations == [shadow / f'compiler/{directory}/src/repeated.{suffix}']
        assert f'{result} repeated();' in declarations[0].read_text()
