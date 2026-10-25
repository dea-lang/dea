# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Native L2 reference inventory and real header/source Doxygen contracts."""

from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from gen_c_docs import build_source_manifest, doxyfile_text, generate


def test_native_inventory_contains_all_production_c_and_no_other_levels() -> None:
    files = set(build_source_manifest(ROOT))
    expected = {path.relative_to(ROOT)
                for directory in ('compiler/shared/runtime', 'compiler/support')
                for path in (ROOT / directory).rglob('*') if path.suffix in {'.h', '.c'}}
    assert files == expected
    assert Path('compiler/shared/runtime/src/dea_rt_alloc.c') in files
    assert Path('compiler/shared/runtime/internal/dea_siphash.h') in files
    assert Path('compiler/support/preparation/build.h') in files
    assert not any(set(path.parts) & {'tests', 'fixtures', 'work', 'build', 'l0', 'l1'} for path in files)


def test_native_pipeline_copies_inputs_without_changing_documentation_lines(tmp_path: Path) -> None:
    if shutil.which('doxygen') is None:
        pytest.skip('Doxygen is unavailable')
    root = tmp_path / 'L2 checkout with spaces'
    support = root / 'compiler/support'
    support.mkdir(parents=True)
    header = '''/** @file */
enum { ANONYMOUS_FIRST, ANONYMOUS_SECOND };

/* Read the borrowed value. */
int read_value(int value);

/**
 * Return the inline value.
 * @param value Borrowed value.
 * @return The same value; failure is impossible.
 */
static inline int inline_value(int value) { return value; }
'''
    source = '''/** @file */
#include "api.h"

/**
 * Read the borrowed value.
 * @param value Borrowed input; ownership does not transfer.
 * @return The value, or minus one on failure.
 */
int read_value(int value) { return value; }
'''
    (support / 'api.h').write_text(header, encoding='utf-8')
    (support / 'api.c').write_text(source, encoding='utf-8')
    output = tmp_path / 'native output'
    generate(root, output, strict=True)
    members = [member for path in (output / 'xml').glob('*.xml')
               for member in ET.parse(path).findall('.//memberdef[@kind="function"]')]
    assert {member.findtext('name') for member in members} == {'read_value', 'inline_value'}
    for member in members:
        location = member.find('location')
        if member.findtext('name') == 'read_value':
            assert 'ownership does not transfer' in ' '.join(member.itertext())
            assert 'minus one on failure' in ' '.join(member.itertext())
            assert location.get('bodyfile') == 'compiler/support/api.c'
            assert location.get('bodystart') == '9'
            if location.get('file').endswith('.h'):
                assert location.get('declline') == '5'
    assert 'No undocumented functions found.' in (output / 'undocumented-functions.txt').read_text()
    assert (output / 'html/index.html').is_file()
    native_page = (output / 'html/api_8c.html').read_text()
    assert 'ownership does not transfer' in native_page
    assert 'minus one on failure' in native_page
    header_page = (output / 'html/api_8h.html').read_text()
    import re
    anchors = re.findall(r'href="#([^" ]+)"[^>]*>ANONYMOUS_', header_page)
    assert len(anchors) == 2
    for anchor in anchors:
        assert f'id="{anchor}"' in header_page
    assert (output / 'latex/refman.tex').is_file()
    assert (support / 'api.c').read_text() == source
    config = doxyfile_text(tmp_path / 'shadow', output, build_source_manifest(root))
    assert 'FILE_PATTERNS = *.h *.c' in config
    assert 'PREDEFINED = SIPHASH_IMPLEMENTATION DEA_TRACE_ARC DEA_TRACE_MEMORY' in config
    assert 'GENERATE_HTML = NO' in config
    assert 'compiler/support/api.c' in config


def test_native_regeneration_drops_removed_compounds_and_stale_pages(tmp_path: Path) -> None:
    if shutil.which('doxygen') is None:
        pytest.skip('Doxygen is unavailable')
    root = tmp_path / 'checkout'
    source = root / 'compiler/support/removed.c'
    source.parent.mkdir(parents=True)
    source.write_text('/** @file */\n\nint removed(void) { return 0; }\n')
    output = tmp_path / 'reference'
    generate(root, output)
    assert 'removed' in (output / 'undocumented-functions.txt').read_text()
    source.unlink()
    replacement = source.with_name('current.c')
    replacement.write_text('/** @file */\n\n/**\n * Return the current value.\n * @return One.\n */\nint current(void) { return 1; }\n')
    generate(root, output, strict=True)
    assert not list((output / 'xml').glob('*removed*'))
    assert not list((output / 'html').glob('*removed*'))
    assert 'No undocumented functions found.' in (output / 'undocumented-functions.txt').read_text()
