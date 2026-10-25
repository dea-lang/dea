# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""L0 and L1 signature fidelity and Doxygen syntax regressions."""
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

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


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
@pytest.mark.parametrize('manifest', [
    'export *;\n',
    'export first, current_dir;\n',
    'export first,\n    current_dir;\n',
    'export opaque {\n    Handle, State\n}, current_dir;\n',
    'export first, /* ; export ignored; */\n    // ; export ignored;\n    current_dir;\n',
])
def test_export_manifests_are_removed_without_shifting_declarations(manifest, newline):
    declaration = '\n/**\n * Current directory.\n */\nfunc current_dir() -> int;'
    source = ('module fixture;\n' + manifest + declaration).replace('\n', newline)
    rendered = transform_l0_for_doxygen(source)
    lines = rendered.splitlines()
    assert len(lines) == len(source.splitlines())
    assert all(not line.strip() for line in lines[:1 + len(manifest.splitlines())])
    assert lines[-5:] == ['', '/**', ' * Current directory.', ' */', 'int current_dir();']


def test_export_text_in_comments_and_literals_is_preserved():
    source = r'''/*
export documented;
*/
let message = "export quoted; }";
let quote = '\'';
func keep() -> void {
    // export body_comment;
    let body = "export nested; {\"";
}
/* export hidden; */
export current_dir;
func current_dir() -> int;
'''
    rendered = transform_l0_for_doxygen(source)
    for line in source.splitlines():
        if 'export' in line and line != 'export current_dir;':
            assert line in rendered.splitlines()
    assert 'void keep() {' in rendered
    assert 'int current_dir();' in rendered
    assert 'export current_dir;' not in rendered
    assert len(rendered.splitlines()) == len(source.splitlines())


@pytest.mark.parametrize('suffix', [
    ' func current_dir() -> int;',
    ' /** Current directory. */\nfunc current_dir() -> int;',
])
def test_export_removal_preserves_same_line_suffix(suffix):
    source = 'export current_dir;' + suffix
    rendered = transform_l0_for_doxygen(source)
    assert 'export' not in rendered
    assert rendered.splitlines()[-1].strip() == 'int current_dir();'
    assert len(rendered.splitlines()) == len(source.splitlines())
    if '/**' in suffix:
        assert '/** Current directory. */' in rendered


def _doxygen_members(tmp_path, source):
    """Generate member records from one isolated Dea source fixture.

    Args:
        tmp_path: Temporary fixture and output directory.
        source: Original Dea source to filter.

    Returns:
        Member definitions from the generated XML files.

    Raises:
        subprocess.CalledProcessError: Doxygen fails to generate XML.
    """
    if not shutil.which('doxygen'):
        pytest.skip('Doxygen is required for the XML integration fixture')
    fixture = tmp_path / 'fixture.l1'
    fixture.write_text(transform_l0_for_doxygen(source), newline='')
    config = tmp_path / 'Doxyfile'
    config.write_text(f'INPUT = "{fixture}"\nOUTPUT_DIRECTORY = "{tmp_path}"\nEXTENSION_MAPPING = l1=C\nGENERATE_XML = YES\nGENERATE_HTML = NO\nGENERATE_LATEX = NO\nEXTRACT_ALL = YES\nQUIET = YES\n')
    subprocess.run(['doxygen',str(config)],check=True,capture_output=True,text=True)
    return [member for xml in (tmp_path / 'xml').glob('*.xml') for member in ET.parse(xml).findall('.//memberdef')]


def test_real_doxygen_keeps_interface_declarations(tmp_path):
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
    names = {member.findtext('name') for member in _doxygen_members(tmp_path, source)}
    assert {'Callback','value','apply','factory'} <= names
    assert not any(name.startswith('__pad') for name in names)


def test_real_doxygen_classifies_exported_zero_argument_function(tmp_path):
    source = '''module fixture;
export first,
    current_dir;

/**
 * Current directory.
 */
func current_dir() -> int;
'''
    members = [member for member in _doxygen_members(tmp_path, source) if member.findtext('name') == 'current_dir']
    assert [member.get('kind') for member in members] == ['function']
    location = members[0].find('location')
    assert location is not None
    declaration_line = source.splitlines().index('func current_dir() -> int;') + 1
    assert int(location.get('line')) == declaration_line


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
@pytest.mark.parametrize('layout', ['inline', 'multiline'])
def test_real_doxygen_payload_enums_preserve_following_function_metadata(tmp_path, layout, newline):
    enums = {
        'OpenDirResult': ['OpenedDir(dir: Dir*)', 'OpenDirFailed(error: OsError)'],
        'NextResult': ['Entry(entry: DirEntry)', 'End', 'NextFailed(error: OsError)'],
        'EntriesResult': ['Entries(entries: DirEntries*)', 'EntriesFailed(error: OsError)'],
        'PathResult': ['Path(path: string)', 'PathFailed(error: OsError)'],
        'CallbackResult': [
            'Handler(callback: func(int, byte[]) -> bool)',
            'Optional(callback: (func(int, int) -> bool)?)',
            'Values(values: byte[]?)',
            'Missing',
        ],
        'PlainState': ['Initial', 'Ready = (1 << 3)'],
    }
    declarations = []
    for name, variants in enums.items():
        documentation = f'\n/**\n * {name} alternatives.\n */\n'
        if layout == 'inline':
            declaration = f'enum {name} {{ ' + '; '.join(variants) + '; }\n'
        else:
            variant_lines = []
            for variant in variants:
                if variant.startswith('Handler('):
                    variant = 'Handler(\n        callback: func(int, byte[]) -> bool /* ; } */\n    )'
                variant_lines.append(f'    {variant};\n')
            declaration = f'enum {name} {{\n' + ''.join(variant_lines) + '}\n'
        declarations.append(documentation + declaration)
    source = '''module fixture;
export OpenDirResult, NextResult, EntriesResult, PathResult, CallbackResult,
    open, read_all, absolute;
struct Dir { handle: int; }
struct DirEntry { name: string; }
struct DirEntries { size: int; }
struct OsError { code: int; }
''' + ''.join(declarations) + '''
/**
 * Open a directory.
 *
 * @param path Directory path.
 * @return Cursor or captured failure.
 */
func open(path: string) -> OpenDirResult {
    return OpenDirFailed(error);
}

/**
 * Read directory entries.
 *
 * @param path Directory path.
 * @return Entries or captured failure.
 */
func read_all(path: string) -> EntriesResult {
    return EntriesFailed(error);
}

/**
 * Resolve an absolute path.
 *
 * @param path Input path.
 * @return Owned path or captured failure.
 */
func absolute(path: string) -> PathResult;
'''
    source = source.replace('\n', newline)
    assert len(transform_l0_for_doxygen(source).splitlines()) == len(source.splitlines())
    members = _doxygen_members(tmp_path, source)
    functions = [member for member in members if member.get('kind') == 'function']
    assert {member.findtext('name') for member in functions} == {'open', 'read_all', 'absolute'}
    assert len(functions) == 3
    expected_returns = {'open': 'OpenDirResult', 'read_all': 'EntriesResult', 'absolute': 'PathResult'}
    source_lines = source.splitlines()
    for function in functions:
        name = function.findtext('name')
        assert ''.join(function.find('type').itertext()) == expected_returns[name]
        assert [(''.join(param.find('type').itertext()), param.findtext('declname'))
                for param in function.findall('param')] == [('string', 'path')]
        declaration = f'func {name}(path: string) -> {expected_returns[name]}'
        line = next(index + 1 for index, text in enumerate(source_lines) if text.startswith(declaration))
        location = function.find('location')
        assert Path(location.get('file')).samefile(tmp_path / 'fixture.l1')
        assert int(location.get('line')) == line
        if name != 'absolute':
            assert Path(location.get('bodyfile')).samefile(tmp_path / 'fixture.l1')
            assert int(location.get('bodystart')) == line
            assert int(location.get('bodyend')) == line + 2
    enum_members = {member.findtext('name'): member for member in members if member.get('kind') == 'enum'}
    assert set(enum_members) == set(enums)
    for name, variants in enums.items():
        enum = enum_members[name]
        assert [value.findtext('name') for value in enum.findall('enumvalue')] == [
            variant.split('(', 1)[0].split('=', 1)[0].strip() for variant in variants
        ]
        line = next(index + 1 for index, text in enumerate(source_lines) if text.startswith(f'enum {name} {{'))
        location = enum.find('location')
        assert Path(location.get('file')).samefile(tmp_path / 'fixture.l1')
        assert int(location.get('line')) == line
        assert int(location.get('bodystart')) == line
        end_line = line
        if layout == 'multiline':
            end_line = next(index + 1 for index in range(line, len(source_lines)) if source_lines[index] == '}')
        assert int(location.get('bodyend')) == end_line
    ready = enum_members['PlainState'].findall('enumvalue')[1]
    assert ''.join(ready.find('initializer').itertext()).replace(' ', '') == '=(1<<3)'


def test_enum_filter_preserves_enum_text_inside_comments_and_literals():
    source = '''/*
enum Commented { Variant(payload: int); }
*/
let example = "enum Quoted { Variant(payload: int); }";
enum Actual { Empty; Payload(value: string /* ; } */); }
'''
    rendered = transform_l0_for_doxygen(source)
    assert source.split('enum Actual', 1)[0] == rendered.split('enum Actual', 1)[0]
    assert len(rendered.splitlines()) == len(source.splitlines())
    assert 'Payload(value:' not in rendered


def test_inline_function_body_and_callback_return():
    source = 'func factory() -> func(int, int) -> bool { return callback; }\n'
    assert transform_l0_for_doxygen(source) == 'void* factory() { return callback; }\n'


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_real_doxygen_std_unit_preserves_signatures_and_locations(tmp_path: Path, newline: str) -> None:
    source_path = Path(__file__).resolve().parents[1] / "compiler/shared/l1/stdlib/std/unit.l1"
    source = source_path.read_text(encoding="utf-8").replace("\n", newline)
    members = _doxygen_members(tmp_path, source)
    assert sum(member.get("kind") == "function" for member in members) == 2
    functions = {member.findtext("name"): member for member in members if member.get("kind") == "function"}
    assert set(functions) == {"unit", "present"}
    expected_lines = {"unit": (30, 32), "present": (39, 41)}
    for name, function in functions.items():
        assert "".join(function.find("type").itertext()) == "Unit"
        assert function.findtext("definition") == f"Unit {name}"
        assert function.findtext("argsstring") == "()"
        assert function.findall("param") == []
        location = function.find("location")
        assert location is not None
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l1")
        assert Path(location.get("bodyfile")).samefile(tmp_path / "fixture.l1")
        start_line, end_line = expected_lines[name]
        assert int(location.get("line")) == start_line
        assert int(location.get("bodystart")) == start_line
        assert int(location.get("bodyend")) == end_line
    assert len(transform_l0_for_doxygen(source).splitlines()) == len(source.splitlines())


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("layout", ["inline", "multiline", "split_header"])
@pytest.mark.parametrize("empty", [False, True], ids=["populated", "empty"])
def test_real_doxygen_structs_preserve_following_signatures_and_locations(
    tmp_path: Path, empty: bool, layout: str, newline: str
) -> None:
    fields = [] if empty else [
        "count: int;",
        "next: Record*?;",
        "text: string?;",
        "flag: bool;",
    ]
    if layout == "inline":
        declaration = "struct Record { /* } ; : */ " + " ".join(fields) + " }\n"
    else:
        header = "struct Record {\n" if layout == "multiline" else "struct\n/* } ; : */\nRecord\n{\n"
        declaration = header + "".join(f"    {field}\n" for field in fields) + "} // } ; :\n"
    source = """/**
 * Record type.
 */
""" + declaration + """
/**
 * Return the optional original record.
 *
 * @param value Optional record.
 * @param count Number of records.
 * @return Optional original record.
 */
func identity(value: Record*?, count: int) -> Record*? {
    return value;
}

/**
 * Obtain a record through a native binding.
 *
 * @param flag Select the record.
 * @return Optional record.
 */
extern func obtain(flag: bool) -> Record*?;
"""
    source = source.replace("\n", newline)
    members = _doxygen_members(tmp_path, source)
    assert sum(member.get("kind") == "function" for member in members) == 2
    functions = {member.findtext("name"): member for member in members if member.get("kind") == "function"}
    assert set(functions) == {"identity", "obtain"}
    expected_params = {"identity": [("Record*", "value"), ("int", "count")], "obtain": [("bool", "flag")]}
    expected_args = {"identity": "(Record*value,intcount)", "obtain": "(boolflag)"}
    for name, function in functions.items():
        assert "".join(function.find("type").itertext()).replace(" ", "") == "Record*"
        assert function.findtext("definition").replace(" ", "") == f"Record*{name}"
        assert "".join(function.findtext("argsstring").split()) == expected_args[name]
        assert [
            ("".join(param.find("type").itertext()).replace(" ", ""), param.findtext("declname"))
            for param in function.findall("param")
        ] == expected_params[name]
        declaration_line = next(
            index + 1
            for index, line in enumerate(source.splitlines())
            if line.startswith((f"func {name}(", f"extern func {name}("))
        )
        location = function.find("location")
        assert location is not None
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l1")
        assert int(location.get("line")) == declaration_line
        if name == "identity":
            assert Path(location.get("bodyfile")).samefile(tmp_path / "fixture.l1")
            assert int(location.get("bodystart")) == declaration_line
            assert int(location.get("bodyend")) == declaration_line + 2
    variables = {member.findtext("name"): member for member in members if member.get("kind") == "variable"}
    assert set(variables) == ({"count", "next", "text", "flag"} if not empty else set())
    expected_types = {"count": "int", "next": "Record*", "text": "string", "flag": "bool"}
    for name, variable in variables.items():
        assert "".join(variable.find("type").itertext()).replace(" ", "") == expected_types[name]
        location = variable.find("location")
        assert location is not None
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l1")
        declaration_line = next(index + 1 for index, line in enumerate(source.splitlines()) if f"{name}:" in line)
        assert int(location.get("line")) == declaration_line
    assert len(transform_l0_for_doxygen(source).splitlines()) == len(source.splitlines())


def test_struct_filter_preserves_comments_and_literals() -> None:
    source = r'''/*
struct Commented {
    value: int;
}
*/
func example() -> void {
    let text = "struct Quoted { value: int; }";
    let brace = '}';
    let quote = '\'';
    // struct Hidden { value: int; }
}
struct Actual { value: int; }
'''
    rendered = transform_l0_for_doxygen(source)
    assert source.split("func example", 1)[0] == rendered.split("void example", 1)[0]
    for line in source.splitlines():
        if "struct" in line and not line.startswith("struct Actual"):
            assert line in rendered.splitlines()
    assert "struct Actual { int value; };" in rendered
    assert len(rendered.splitlines()) == len(source.splitlines())


def test_real_doxygen_struct_field_comments_survive_rewriting(tmp_path: Path) -> None:
    source = """/**
 * A documented record.
 */
struct Record {

    /**
     * Original count, with punctuation } ; : preserved.
     */
    count /* } ; : */ : int;

    /**
     * Optional following record.
     */
    next: Record /* } ; : */ *?;
}
"""
    members = _doxygen_members(tmp_path, source)
    fields = {member.findtext("name"): member for member in members if member.get("kind") == "variable"}
    assert set(fields) == {"count", "next"}
    for name, expected_type, expected_description, line in [
        ("count", "int", "Original count, with punctuation } ; : preserved.", 9),
        ("next", "Record*", "Optional following record.", 14),
    ]:
        field = fields[name]
        assert "".join(field.find("type").itertext()).replace(" ", "") == expected_type
        description = " ".join(" ".join(field.find(tag).itertext()) for tag in ["briefdescription", "detaileddescription"])
        assert expected_description in " ".join(description.split())
        location = field.find("location")
        assert location is not None
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l1")
        assert int(location.get("line")) == line


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_struct_filter_preserves_function_shaped_text_in_block_comments(newline: str) -> None:
    comment = """/*
func sample(value: int) -> void;
extern func native_sample(value: int) -> void;
*/"""
    source = ("struct Record {\n" + comment + "\n    value: int;\n}\n").replace("\n", newline)
    rendered = transform_l0_for_doxygen(source)
    assert comment.replace("\n", newline) in rendered
    assert "int value;" in rendered
    assert len(rendered.splitlines()) == len(source.splitlines())


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_real_doxygen_split_qualified_struct_fields_preserve_locations(tmp_path: Path, newline: str) -> None:
    source = """/**
 * A record with a qualified field type.
 */
struct Record {

    /**
     * Optional target node.
     */
    target:
        model /* } ; : */
        ::
        Node
        *
        ?;

    /**
     * Number of targets.
     */
    count:
        int;
}

/**
 * Extract the target.
 *
 * @param value Original record.
 * @return Optional target node.
 */
func target_of(value: Record*) -> model::Node*? {
    return value.target;
}
""".replace("\n", newline)
    rendered = transform_l0_for_doxygen(source)
    assert "/* nullable */" not in rendered
    assert "/* } ; : */" in rendered
    assert len(rendered.splitlines()) == len(source.splitlines())
    members = _doxygen_members(tmp_path, source)
    fields = {member.findtext("name"): member for member in members if member.get("kind") == "variable"}
    assert set(fields) == {"target", "count"}
    for name, expected_type, expected_description, line in [
        ("target", "model::Node*", "Optional target node.", 9),
        ("count", "int", "Number of targets.", 19),
    ]:
        field = fields[name]
        assert "".join(field.find("type").itertext()).replace(" ", "") == expected_type
        description = " ".join(" ".join(field.find(tag).itertext()) for tag in ["briefdescription", "detaileddescription"])
        assert expected_description in " ".join(description.split())
        location = field.find("location")
        assert location is not None
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l1")
        assert int(location.get("line")) == line
    functions = [member for member in members if member.get("kind") == "function"]
    assert len(functions) == 1
    function = functions[0]
    assert function.findtext("name") == "target_of"
    assert "".join(function.find("type").itertext()).replace(" ", "") == "model::Node*"
    assert function.findtext("definition").replace(" ", "") == "model::Node*target_of"
    assert "".join(function.findtext("argsstring").split()) == "(Record*value)"
    location = function.find("location")
    assert location is not None
    assert Path(location.get("file")).samefile(tmp_path / "fixture.l1")
    assert Path(location.get("bodyfile")).samefile(tmp_path / "fixture.l1")
    assert int(location.get("line")) == 29
    assert int(location.get("bodystart")) == 29
    assert int(location.get("bodyend")) == 31


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_real_doxygen_nullable_struct_fields_keep_distinct_trailing_docs(tmp_path: Path, newline: str) -> None:
    source = """struct Record {
    optional: Record*?; ///< Optional following record.
    count: int; ///< Number of records.
}
""".replace("\n", newline)
    members = _doxygen_members(tmp_path, source)
    fields = {member.findtext("name"): member for member in members if member.get("kind") == "variable"}
    assert set(fields) == {"optional", "count"}
    for name, expected_type, expected_description, line in [
        ("optional", "Record*", "Optional following record.", 2),
        ("count", "int", "Number of records.", 3),
    ]:
        field = fields[name]
        assert "".join(field.find("type").itertext()).replace(" ", "") == expected_type
        description = " ".join(" ".join(field.find(tag).itertext()) for tag in ["briefdescription", "detaileddescription"])
        assert " ".join(description.split()) == expected_description
        location = field.find("location")
        assert location is not None
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l1")
        assert int(location.get("line")) == line


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("layout", ["inline", "multiline", "split_header"])
def test_real_doxygen_structs_preserve_l1_types_and_export_filtering(
    tmp_path: Path, layout: str, newline: str
) -> None:
    fields = {
        "callback": ("func(int, byte[]) -> bool", "void*"),
        "unsafe_callback": ("unsafe func(uint, ulong) -> long", "void*"),
        "optional_callback": ("(unsafe func(int, int) -> bool)?", "void*"),
        "bytes": ("byte[]", "byte*"),
        "array": ("int[4]", "int*"),
        "matrix": ("int[2][3]", "int**"),
        "optional_values": ("int?[]", "int*"),
        "next": ("Record?*?", "Record*"),
    }
    declarations = [f"{name}: {type_text};" for name, (type_text, _) in fields.items()]
    if layout == "inline":
        record = "struct Record { " + " ".join(declarations) + " } // } ; :\n"
    else:
        header = "struct Record {\n" if layout == "multiline" else "struct\n/* } ; : */\nRecord\n{\n"
        record = header + "".join(f"    {field}\n" for field in declarations) + "} // } ; :\n"
    source = """module interface fixture;
fingerprint "sip13:0123456789abcdef";
export opaque {
    Record
}, apply;
""" + record + """
export opaque {
    Handle
},
    factory;
struct Handle {} // Empty opaque representation.

/**
 * Apply a callback to the supplied records.
 *
 * @param record Optional original record.
 * @param callback Native callback.
 * @param values Optional integer values.
 * @return Fixed array represented as a native pointer.
 */
unsafe extern func apply(record: Record?*?, callback: unsafe func(uint, ulong) -> long, values: int?[]) -> byte[4];

/**
 * Obtain a callback.
 *
 * @return Callback or null.
 */
func factory() -> (unsafe func(int, int) -> bool)? {
    return null;
}
"""
    source = source.replace("\n", newline)
    rendered = transform_l0_for_doxygen(source)
    assert "export" not in rendered
    assert "opaque {" not in rendered
    assert "fingerprint" not in rendered
    assert "extern byte* apply(Record* record, void* callback, int* values);" in rendered
    assert "void* factory() {" in rendered
    assert len(rendered.splitlines()) == len(source.splitlines())
    members = _doxygen_members(tmp_path, source)
    variables = {member.findtext("name"): member for member in members if member.get("kind") == "variable"}
    assert set(variables) == set(fields)
    for name, variable in variables.items():
        assert "".join(variable.find("type").itertext()).replace(" ", "") == fields[name][1]
        location = variable.find("location")
        assert location is not None
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l1")
        line = next(index + 1 for index, line in enumerate(source.splitlines()) if f"{name}:" in line)
        assert int(location.get("line")) == line
    functions = [member for member in members if member.get("kind") == "function"]
    assert len(functions) == 2
    functions = {member.findtext("name"): member for member in functions}
    assert set(functions) == {"apply", "factory"}
    expected = {
        "apply": ("byte*", "byte*apply", "(Record*record,void*callback,int*values)", [
            ("Record*", "record"), ("void*", "callback"), ("int*", "values")
        ]),
        "factory": ("void*", "void*factory", "()", []),
    }
    for name, function in functions.items():
        return_type, definition, arguments, parameters = expected[name]
        assert "".join(function.find("type").itertext()).replace(" ", "") == return_type
        assert function.findtext("definition").replace(" ", "") == definition
        assert "".join(function.findtext("argsstring").split()) == arguments
        assert [
            ("".join(param.find("type").itertext()).replace(" ", ""), param.findtext("declname"))
            for param in function.findall("param")
        ] == parameters
        line = next(
            index + 1 for index, line in enumerate(source.splitlines())
            if line.startswith((f"func {name}(", f"unsafe extern func {name}("))
        )
        location = function.find("location")
        assert location is not None
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l1")
        assert int(location.get("line")) == line
        if name == "factory":
            assert Path(location.get("bodyfile")).samefile(tmp_path / "fixture.l1")
            assert int(location.get("bodystart")) == line
            assert int(location.get("bodyend")) == line + 2


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_real_doxygen_keeps_fingerprint_struct_field(tmp_path: Path, newline: str) -> None:
    source = """module interface fixture;
fingerprint "sip13:0123456789abcdef";

/**
 * Public interface metadata.
 */
struct ModuleInterface {
    module_name: string;

    /**
     * Canonical whole-module fingerprint.
     */
    fingerprint: string;
    has_entry: bool;
}
""".replace("\n", newline)
    rendered = transform_l0_for_doxygen(source)
    assert 'fingerprint "sip13:' not in rendered
    assert "string fingerprint;" in rendered
    assert len(rendered.splitlines()) == len(source.splitlines())
    members = _doxygen_members(tmp_path, source)
    fields = {member.findtext("name"): member for member in members if member.get("kind") == "variable"}
    assert set(fields) == {"module_name", "fingerprint", "has_entry"}
    for name, expected_type, line in [
        ("module_name", "string", 8),
        ("fingerprint", "string", 13),
        ("has_entry", "bool", 14),
    ]:
        field = fields[name]
        assert "".join(field.find("type").itertext()) == expected_type
        location = field.find("location")
        assert location is not None
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l1")
        assert int(location.get("line")) == line
    fingerprint = fields["fingerprint"]
    description = " ".join(
        " ".join(fingerprint.find(tag).itertext()) for tag in ["briefdescription", "detaileddescription"]
    )
    assert " ".join(description.split()) == "Canonical whole-module fingerprint."
