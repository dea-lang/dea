# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""L0 and L1 signature fidelity and Doxygen syntax regressions."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compiler.docgen.l1_docgen_l0_filter import transform_l0_for_doxygen
from compiler.docgen.l1_docgen_l0_helpers import extract_l0_member_declaration


def test_wide_slice_function_pointer_and_unsafe_signatures(tmp_path):
    source = '''module interface example;
fingerprint "sip13:0123456789abcdef";
/** Apply a callback. */
unsafe extern func apply(
    callback: func(uint, ulong) -> long,
    values: int[], count: uint) -> ulong;
struct Box { value: long; }
struct Options {
    callback: (func(int, int) -> bool)?; /* callback */
    bytes: byte[];
}
'''
    rendered = transform_l0_for_doxygen(source)
    assert 'extern ulong apply(void* callback, int* values, uint count);' in rendered
    assert 'long value;' in rendered
    assert 'void* callback;' in rendered
    assert 'byte* bytes;' in rendered
    assert len(rendered.splitlines()) == len(source.splitlines())
    file = tmp_path / 'example.l1'
    file.write_text(source)
    member = ET.fromstring(f'<memberdef kind="function"><name>apply</name><location file="{file}" line="4"/></memberdef>')
    declaration = extract_l0_member_declaration(member)
    assert 'unsafe extern func apply' in declaration
    assert 'func(uint, ulong) -> long' in declaration
    assert 'int[]' in declaration


def test_comments_and_inline_structs_are_preserved():
    rendered = transform_l0_for_doxygen('struct Pair { x: int; y: long; }\nstruct A {\n value: int; /* value */\n}\n')
    assert 'int x;long y;' in rendered.replace(' ', '') or 'int x; long y;' in rendered
    assert 'int value; /* value */' in rendered


def test_real_doxygen_keeps_interface_declarations(tmp_path):
    import shutil
    import subprocess
    import pytest
    if not shutil.which('doxygen'):
        pytest.skip('Doxygen is required for the XML integration fixture')
    source = '''module interface fixture;
fingerprint "sip13:0123456789abcdef";
/** Callback alias. */
type Callback = func(uint, ulong) -> long;
/** Record. */
struct Result { value: ulong; }
/** Apply a callback. */
unsafe extern func apply(callback: func(uint, ulong) -> long, values: int[]) -> ulong;
/** Return a callback. */
func factory() -> func(uint, ulong) -> long;
'''
    fixture = tmp_path / 'fixture.l1'
    fixture.write_text(transform_l0_for_doxygen(source))
    config = tmp_path / 'Doxyfile'
    config.write_text(f'INPUT = "{fixture}"\nOUTPUT_DIRECTORY = "{tmp_path}"\nEXTENSION_MAPPING = l1=C\nGENERATE_XML = YES\nGENERATE_HTML = NO\nGENERATE_LATEX = NO\nEXTRACT_ALL = YES\nQUIET = YES\n')
    subprocess.run(['doxygen',str(config)],check=True,capture_output=True,text=True)
    names = {node.text for xml in (tmp_path / 'xml').glob('*.xml') for node in ET.parse(xml).findall('.//memberdef/name')}
    assert {'Callback','value','apply','factory'} <= names
    assert not any(name.startswith('__pad') for name in names)


def test_inline_function_body_and_callback_return():
    source = 'func factory() -> func(int, int) -> bool { return callback; }\n'
    assert transform_l0_for_doxygen(source) == 'void* factory() { return callback; }\n'
