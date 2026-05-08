#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from conftest import has_error_code
from l0_ast import StructDecl, TypeAliasDecl, FuncDecl
from l0_parser import Parser


def parse_module(src: str):
    parser = Parser.from_source(src)
    return parser.parse_module()


def test_parser_types_valid_pointer_and_nullable():
    src = """
    module main;

    type Buffer = byte*;

    struct Slice {
        data: byte*?;
        len: int;
    }

    func take(buf: Buffer, maybe: Slice*?) -> void {
        return;
    }
    """
    mod = parse_module(src)

    alias, slice_struct, take_func = mod.decls
    assert isinstance(alias, TypeAliasDecl)
    assert alias.target.name == "byte"
    assert alias.target.pointer_depth == 1

    assert isinstance(slice_struct, StructDecl)
    data_field = slice_struct.fields[0]
    assert data_field.type.name == "byte"
    assert data_field.type.pointer_depth == 1
    assert data_field.type.is_nullable

    assert isinstance(take_func, FuncDecl)
    assert take_func.return_type.name == "void"
    assert take_func.params[1].type.pointer_depth == 1
    assert take_func.params[1].type.is_nullable


def test_parser_type_missing_name(analyze_single):
    src = """
    module main;

    type Alias = ;
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "PAR-0400")


def test_parser_type_array_syntax_rejected(analyze_single):
    src = """
    module main;

    func main() -> int {
        let x: int[] = 0;
        return x;
    }
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "PAR-9401")
    assert any(d.message == "[PAR-9401] array types not yet supported" for d in result.diagnostics)
