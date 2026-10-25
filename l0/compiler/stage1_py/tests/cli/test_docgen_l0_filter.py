# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Tests for L0 source normalization."""

from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

from compiler.docgen.l0_docgen_l0_filter import transform_l0_for_doxygen


def test_transform_l0_for_doxygen_rewrites_struct_fields() -> None:
    source = """
struct Span {
    start_line: int;
    name_qualifier: StringVector*?;
    fields: VectorBase*; // FieldDecl*
}
"""

    transformed = transform_l0_for_doxygen(source)

    assert "int start_line;" in transformed
    assert "StringVector* /* nullable */ name_qualifier;" in transformed
    assert "VectorBase* fields; // FieldDecl*" in transformed
    assert "};" in transformed
    assert "start_line: int;" not in transformed
    assert "name_qualifier: StringVector*?;" not in transformed


def test_transform_l0_for_doxygen_rewrites_enum_members() -> None:
    source = """
enum PatternKind {
    PT_WILDCARD;
    PT_VARIANT; // keeps comment
}
"""

    transformed = transform_l0_for_doxygen(source)

    assert "PT_WILDCARD," in transformed
    assert "PT_VARIANT, // keeps comment" in transformed
    assert "};" in transformed
    assert "PT_WILDCARD;" not in transformed


def test_transform_l0_for_doxygen_rewrites_single_line_function_signatures() -> None:
    source = """
/**
 * @param opt Optional string to unwrap.
 * @param fallback Default string to return.
 */
func unwrap_or_s(opt: string?, fallback: string) -> string {
    return fallback;
}
"""

    transformed = transform_l0_for_doxygen(source)

    assert "string unwrap_or_s(string /* nullable */ opt, string fallback) {" in transformed
    assert "func unwrap_or_s(" not in transformed


def test_transform_l0_for_doxygen_rewrites_multiline_function_signatures() -> None:
    source = """
/**
 * @param module_path Optional module path qualifier.
 * @param name Symbol name.
 * @return Optional symbol pointer.
 */
func lookup(module_path: StringVector*?,
            name: string) -> Symbol*? {
    return null;
}
"""

    transformed = transform_l0_for_doxygen(source)

    assert "Symbol* /* nullable */ lookup(StringVector* /* nullable */ module_path, string name) {" in transformed
    assert "func lookup(" not in transformed


def test_transform_l0_for_doxygen_rewrites_extern_function_declarations() -> None:
    source = """
/**
 * @param bytes Number of bytes to allocate.
 * @return Optional allocated pointer.
 */
extern func rt_alloc(bytes: int) -> void*?;
"""

    transformed = transform_l0_for_doxygen(source)

    assert "extern void* /* nullable */ rt_alloc(int bytes);" in transformed
    assert "extern func rt_alloc(" not in transformed


def _doxygen_members(tmp_path: Path, source: str) -> list[ET.Element]:
    """Generate XML member records from a filtered L0 source fixture.

    Args:
        tmp_path: Temporary directory for the fixture and Doxygen output.
        source: Original L0 source to normalize.

    Returns:
        Member definitions from every generated XML compound.

    Raises:
        subprocess.CalledProcessError: Doxygen fails to generate XML.
    """
    if shutil.which("doxygen") is None:
        pytest.skip("Doxygen is required for the XML integration fixture")
    fixture = tmp_path / "fixture.l0"
    fixture.write_text(transform_l0_for_doxygen(source), encoding="utf-8", newline="")
    config = tmp_path / "Doxyfile"
    config.write_text(
        f'INPUT = "{fixture}"\n'
        f'OUTPUT_DIRECTORY = "{tmp_path}"\n'
        "EXTENSION_MAPPING = l0=C\n"
        "GENERATE_XML = YES\n"
        "GENERATE_HTML = NO\n"
        "GENERATE_LATEX = NO\n"
        "EXTRACT_ALL = YES\n"
        "QUIET = YES\n",
        encoding="utf-8",
    )
    subprocess.run(["doxygen", str(config)], check=True, capture_output=True, text=True)
    return [
        member
        for xml in (tmp_path / "xml").glob("*.xml")
        for member in ET.parse(xml).findall(".//memberdef")
    ]


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("layout", ["inline", "multiline"])
def test_real_doxygen_payload_enums_preserve_following_signatures_and_locations(
    tmp_path: Path, layout: str, newline: str
) -> None:
    enums = {
        "TokenRecovery": [
            "TR_NONE",
            "TR_INT(text: string, value: int)",
            "TR_BYTE(text: string, value: byte)",
            "TR_STRING(text: string, value: string)",
        ],
        "TokenType": [
            "TT_EOF",
            "TT_IDENT(text: string)",
            "TT_LEXER_ERROR(code: string, message: string, line_end: int, "
            "column_end: int, recovery: TokenRecovery)",
        ],
    }
    declarations = []
    for name, variants in enums.items():
        documentation = f"\n/**\n * {name} alternatives.\n */\n"
        if layout == "inline":
            declaration = f"enum {name} {{ " + "; ".join(variants) + "; }\n"
        else:
            variant_lines = []
            for variant in variants:
                if variant.startswith("TT_LEXER_ERROR("):
                    variant = (
                        "TT_LEXER_ERROR(\n"
                        "        code: string, message: string,\n"
                        "        line_end: int, column_end: int,\n"
                        "        recovery: TokenRecovery /* ; } */\n"
                        "    )"
                    )
                variant_lines.append(f"    {variant};\n")
            declaration = f"enum {name} {{\n" + "".join(variant_lines) + "}\n"
        declarations.append(documentation + declaration)
    source = """/**
 * Token record.
 */
struct Token {
    value: int;
}

/**
 * Earlier declaration with a multiline signature.
 *
 * @param token Optional token to retain.
 * @param text Token spelling.
 * @return Optional original token.
 */
extern func initial(
    token: Token*?,
    text: string
) -> Token*?;
""" + "".join(declarations) + """
/**
 * Recover a token payload.
 *
 * @param token Optional token.
 * @param text Token spelling.
 * @return Recovery alternative.
 */
func recover(token: Token*?, text: string) -> TokenRecovery {
    return TR_NONE;
}

/**
 * Classify a token.
 *
 * @param token Token to classify.
 * @return Token alternative.
 */
func classify(token: Token*) -> TokenType {
    return TT_EOF;
}

/**
 * Parse a token through a native binding.
 *
 * @param text Token spelling.
 * @param count Spelling length.
 * @return Optional parsed token.
 */
extern func parse(text: string, count: int) -> Token*?;
"""
    source = source.replace("\n", newline)
    members = _doxygen_members(tmp_path, source)
    functions = [member for member in members if member.get("kind") == "function"]
    assert {member.findtext("name") for member in functions} == {"initial", "recover", "classify", "parse"}
    assert len(functions) == 4
    expected_types = {
        "initial": ("Token*", [("Token*", "token"), ("string", "text")]),
        "recover": ("TokenRecovery", [("Token*", "token"), ("string", "text")]),
        "classify": ("TokenType", [("Token*", "token")]),
        "parse": ("Token*", [("string", "text"), ("int", "count")]),
    }
    source_lines = source.splitlines()
    fixture = tmp_path / "fixture.l0"
    for function in functions:
        name = function.findtext("name")
        expected_return, expected_params = expected_types[name]
        assert "".join(function.find("type").itertext()).replace(" ", "") == expected_return
        assert [
            ("".join(param.find("type").itertext()).replace(" ", ""), param.findtext("declname"))
            for param in function.findall("param")
        ] == expected_params
        declaration_line = next(
            index + 1
            for index, line in enumerate(source_lines)
            if line.startswith((f"func {name}(", f"extern func {name}("))
        )
        location = function.find("location")
        assert location is not None
        assert Path(location.get("file")).samefile(fixture)
        assert int(location.get("line")) == declaration_line
        if name in {"recover", "classify"}:
            assert Path(location.get("bodyfile")).samefile(fixture)
            assert int(location.get("bodystart")) == declaration_line
            assert int(location.get("bodyend")) == declaration_line + 2
    enum_members = {member.findtext("name"): member for member in members if member.get("kind") == "enum"}
    assert set(enum_members) == set(enums)
    for name, variants in enums.items():
        enum = enum_members[name]
        assert [value.findtext("name") for value in enum.findall("enumvalue")] == [
            variant.split("(", 1)[0] for variant in variants
        ]
        declaration_line = next(
            index + 1 for index, line in enumerate(source_lines) if line.startswith(f"enum {name} {{")
        )
        location = enum.find("location")
        assert location is not None
        assert Path(location.get("file")).samefile(fixture)
        assert int(location.get("line")) == declaration_line
        assert int(location.get("bodystart")) == declaration_line
        end_line = declaration_line
        if layout == "multiline":
            end_line = next(
                index + 1 for index in range(declaration_line, len(source_lines)) if source_lines[index] == "}"
            )
        assert int(location.get("bodyend")) == end_line
    assert len(transform_l0_for_doxygen(source).splitlines()) == len(source_lines)


def test_enum_filter_preserves_enum_text_inside_comments_and_literals() -> None:
    source = r'''/*
enum Commented {
    Variant(payload: int);
}
*/
func example() -> void {
    let text = "enum Quoted { Variant(payload: int); }";
    let brace = '}';
    let quote = '\'';
    // enum Hidden { Empty; }
}
enum Actual { Empty; Payload(value: string /* ; } */); }
'''
    rendered = transform_l0_for_doxygen(source)
    assert source.split("func example", 1)[0] == rendered.split("void example", 1)[0]
    for line in source.splitlines():
        if "enum" in line and not line.startswith("enum Actual"):
            assert line in rendered.splitlines()
    assert "Payload(value:" not in rendered
    assert len(rendered.splitlines()) == len(source.splitlines())


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_real_doxygen_multiline_enum_header_preserves_locations(tmp_path: Path, newline: str) -> None:
    source = """/**
 * Multiline enum header.
 */
enum
/* Header comment. */
Recovery
{
    None;
    Integer(
        value: int /* ; } */
    );
}

/**
 * Return a recovery value.
 *
 * @return Recovery alternative.
 */
func recover() -> Recovery {
    return None;
}
""".replace("\n", newline)
    members = _doxygen_members(tmp_path, source)
    enums = [member for member in members if member.get("kind") == "enum"]
    assert len(enums) == 1
    assert enums[0].findtext("name") == "Recovery"
    assert [value.findtext("name") for value in enums[0].findall("enumvalue")] == ["None", "Integer"]
    enum_location = enums[0].find("location")
    assert enum_location is not None
    assert Path(enum_location.get("file")).samefile(tmp_path / "fixture.l0")
    assert int(enum_location.get("line")) == 4
    assert int(enum_location.get("bodystart")) == 7
    assert int(enum_location.get("bodyend")) == 12
    functions = [member for member in members if member.get("kind") == "function"]
    assert [member.findtext("name") for member in functions] == ["recover"]
    assert "".join(functions[0].find("type").itertext()) == "Recovery"
    location = functions[0].find("location")
    assert location is not None
    assert Path(location.get("file")).samefile(tmp_path / "fixture.l0")
    assert Path(location.get("bodyfile")).samefile(tmp_path / "fixture.l0")
    assert int(location.get("line")) == 19
    assert int(location.get("bodystart")) == 19
    assert int(location.get("bodyend")) == 21
    assert len(transform_l0_for_doxygen(source).splitlines()) == len(source.splitlines())


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_real_doxygen_std_unit_preserves_signatures_and_locations(tmp_path: Path, newline: str) -> None:
    source_path = Path(__file__).resolve().parents[3] / "shared/l0/stdlib/std/unit.l0"
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
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l0")
        assert Path(location.get("bodyfile")).samefile(tmp_path / "fixture.l0")
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
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l0")
        assert int(location.get("line")) == declaration_line
        if name == "identity":
            assert Path(location.get("bodyfile")).samefile(tmp_path / "fixture.l0")
            assert int(location.get("bodystart")) == declaration_line
            assert int(location.get("bodyend")) == declaration_line + 2
    variables = {member.findtext("name"): member for member in members if member.get("kind") == "variable"}
    assert set(variables) == ({"count", "next", "text", "flag"} if not empty else set())
    expected_types = {"count": "int", "next": "Record*", "text": "string", "flag": "bool"}
    for name, variable in variables.items():
        assert "".join(variable.find("type").itertext()).replace(" ", "") == expected_types[name]
        location = variable.find("location")
        assert location is not None
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l0")
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
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l0")
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
    assert rendered.count("/* nullable */") == 2
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
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l0")
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
    assert Path(location.get("file")).samefile(tmp_path / "fixture.l0")
    assert Path(location.get("bodyfile")).samefile(tmp_path / "fixture.l0")
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
        assert Path(location.get("file")).samefile(tmp_path / "fixture.l0")
        assert int(location.get("line")) == line
