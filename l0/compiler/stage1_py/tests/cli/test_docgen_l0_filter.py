# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Tests for L0 source normalization."""

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
    assert "StringVector* name_qualifier; /* nullable */" in transformed
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
