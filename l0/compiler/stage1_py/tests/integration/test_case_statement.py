#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

"""
Tests for the `case` statement: scalar and string dispatch.

Covers:
- Lexer: `case` keyword
- Parser: valid forms, error diagnostics, and recovery
- Type checker: scrutinee type (TYP-0106), arm type mismatch (TYP-0107),
  duplicate literals (TYP-0108), Unicode escape validation (TYP-0109)
- Codegen: int switch, string if/else chain, byte, bool, default arm,
  compile-and-run round-trips
"""

import pytest

from l0_ast import (
    Module, FuncDecl, CaseStmt, CaseElse,
    IntLiteral, ByteLiteral, StringLiteral, BoolLiteral, Block, )
from l0_lexer import Lexer, TokenKind
from l0_parser import Parser


# ============================================================================
# Helpers
# ============================================================================

def parse_module(src: str) -> Module:
    parser = Parser.from_source(src)
    return parser.parse_module()

def parse_module_with_parser(src: str):
    parser = Parser.from_source(src)
    mod = parser.parse_module()
    return mod, parser


def get_func_body_stmt(src: str, func_name: str = "main", stmt_index: int = 0):
    mod = parse_module(src)
    for decl in mod.decls:
        if isinstance(decl, FuncDecl) and decl.name == func_name:
            return decl.body.stmts[stmt_index]
    raise ValueError(f"Function '{func_name}' not found")


# ============================================================================
# Lexer tests
# ============================================================================


def test_case_keyword_lexed():
    tokens = Lexer.from_source("case").tokenize()
    assert tokens[0].kind == TokenKind.CASE
    assert tokens[0].text == "case"


# ============================================================================
# Parser tests: valid forms
# ============================================================================


def test_parse_case_single_int_arm():
    src = """
    module test;
    func main() {
        case (42) {
            1 => { return; }
        }
    }
    """
    stmt = get_func_body_stmt(src)
    assert isinstance(stmt, CaseStmt)
    assert len(stmt.arms) == 1
    assert isinstance(stmt.arms[0].literal, IntLiteral)
    assert stmt.arms[0].literal.value == 1
    assert stmt.else_arm is None


def test_parse_case_multiple_int_arms():
    src = """
    module test;
    func main() {
        case (42) {
            1 => { return; }
            2 => { return; }
            3 => { return; }
        }
    }
    """
    stmt = get_func_body_stmt(src)
    assert isinstance(stmt, CaseStmt)
    assert len(stmt.arms) == 3
    assert stmt.arms[0].literal.value == 1
    assert stmt.arms[1].literal.value == 2
    assert stmt.arms[2].literal.value == 3


def test_parse_case_string_literal():
    src = """
    module test;
    func main() {
        let s: string = "hello";
        case (s) {
            "hello" => { return; }
            "world" => { return; }
        }
    }
    """
    stmt = get_func_body_stmt(src, stmt_index=1)
    assert isinstance(stmt, CaseStmt)
    assert len(stmt.arms) == 2
    assert isinstance(stmt.arms[0].literal, StringLiteral)
    assert stmt.arms[0].literal.value == "hello"


def test_parse_case_byte_literal():
    src = """
    module test;
    func main() {
        let b: byte = 'a';
        case (b) {
            'a' => { return; }
            'b' => { return; }
        }
    }
    """
    stmt = get_func_body_stmt(src, stmt_index=1)
    assert isinstance(stmt, CaseStmt)
    assert len(stmt.arms) == 2
    assert isinstance(stmt.arms[0].literal, ByteLiteral)


def test_parse_case_bool_literal():
    src = """
    module test;
    func main() {
        case (true) {
            true => { return; }
            false => { return; }
        }
    }
    """
    stmt = get_func_body_stmt(src)
    assert isinstance(stmt, CaseStmt)
    assert len(stmt.arms) == 2
    assert isinstance(stmt.arms[0].literal, BoolLiteral)
    assert stmt.arms[0].literal.value is True
    assert isinstance(stmt.arms[1].literal, BoolLiteral)
    assert stmt.arms[1].literal.value is False


def test_parse_case_negative_int():
    src = """
    module test;
    func main() {
        case (0) {
            -1 => { return; }
            0 => { return; }
            1 => { return; }
        }
    }
    """
    stmt = get_func_body_stmt(src)
    assert isinstance(stmt, CaseStmt)
    literal1 = stmt.arms[0].literal
    literal2 = stmt.arms[1].literal
    literal3 = stmt.arms[2].literal
    assert isinstance(literal1, IntLiteral) and literal1.value == -1
    assert isinstance(literal2, IntLiteral) and literal2.value == 0
    assert isinstance(literal3, IntLiteral) and literal3.value == 1


def test_parse_case_arm_body_is_single_stmt():
    """Arms can have a block or a single statement as body."""
    src = """
    module test;
    func main() -> int {
        case (42) {
            1 => return 1;
            _ => return 0;
        }
    }
    """
    stmt = get_func_body_stmt(src)
    assert isinstance(stmt, CaseStmt)
    assert len(stmt.arms) == 1
    # Body is not a Block — it's a ReturnStmt directly
    assert not isinstance(stmt.arms[0].body, Block)
    assert not isinstance(stmt.else_arm.body, Block)


def test_parse_case_with_wildcard_default():
    """`_ =>` parses as the sole default-arm spelling."""
    src = """
    module test;
    func main() {
        case (42) {
            1 => { return; }
            _ => { return; }
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    stmt = mod.decls[0].body.stmts[0]
    assert isinstance(stmt, CaseStmt)
    assert len(stmt.arms) == 1
    assert stmt.else_arm is not None
    assert isinstance(stmt.else_arm, CaseElse)
    assert not parser.diagnostics


def test_parse_case_only_wildcard_default():
    src = """
        module test;
        func main() {
            case (42) {
                _ => { return; }
            }
        }
    """
    stmt = get_func_body_stmt(src)
    assert isinstance(stmt, CaseStmt)
    assert len(stmt.arms) == 0
    assert stmt.else_arm is not None


def test_parse_case_wildcard_single_stmt():
    src = """
    module test;
    func main() -> int {
        case (42) {
            1 => return 1;
            _ => return 0;
        }
    }
    """
    stmt = get_func_body_stmt(src)
    assert isinstance(stmt, CaseStmt)
    assert not isinstance(stmt.else_arm.body, Block)


def test_parse_case_stray_else_arm_error():
    """Stray `else` arm spellings are PAR-0123 without a generic cascade."""
    for arm in ("else { return; }", "else => { return; }"):
        src = f"""
        module test;
        func main() {{
            case (42) {{
                {arm}
            }}
        }}
        """
        _, parser = parse_module_with_parser(src)
        codes = [d.message for d in parser.diagnostics]
        assert sum("PAR-0123" in message for message in codes) == 1
        assert not any("PAR-0235" in message for message in codes)
        assert not any("PAR-0225" in message for message in codes)
        assert not any("PAR-0020" in message for message in codes)


def test_parse_case_value_arm_if_else_body_accepted():
    """An unbraced value-arm `if` eagerly consumes its matching `else`."""
    src = """
    module test;
    func main() -> int {
        case (42) {
            1 => if (true) return 1; else return 0;
            _ => return 0;
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert not parser.diagnostics


def test_parse_case_default_arm_if_else_body_accepted():
    """A default-arm body may be an unbraced if-else."""
    wildcard = """
    module test;
    func main() -> int {
        case (42) {
            1 => { return 1; }
            _ => if (true) return 2; else return 3;
        }
    }
    """
    mod, parser = parse_module_with_parser(wildcard)
    assert not parser.diagnostics


# ============================================================================
# Parser tests: error cases
# ============================================================================


def test_parse_case_missing_lparen():
    src = """
    module test;
    func main() {
        case 42 {
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert any("PAR-0231" in d.message for d in parser.diagnostics)


def test_parse_case_missing_rparen():
    src = """
    module test;
    func main() {
        case (42 {
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert any("PAR-0232" in d.message for d in parser.diagnostics)


def test_parse_case_missing_lbrace():
    src = """
    module test;
    func main() {
        case (42) 1 => { return; }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert any("PAR-0233" in d.message for d in parser.diagnostics)


def test_parse_case_missing_arrow_in_arm():
    src = """
    module test;
    func main() {
        case (42) {
            1 { return; }
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert any("PAR-0235" in d.message for d in parser.diagnostics)


def test_parse_case_unexpected_token():
    src = """
    module test;
    func main() {
        case (42) {
            42;
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert any("PAR-0235" in d.message for d in parser.diagnostics)


def test_parse_case_missing_rbrace():
    src = """
    module test;
    func main() {
        case (42) {
            1 => { return; }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert any(d.kind == "error" for d in parser.diagnostics)


def test_parse_case_empty_body():
    src = """
    module test;
    func main() {
        case (42) {
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert any("PAR-0240" in d.message for d in parser.diagnostics)


def test_parse_case_invalid_literal():
    src = """
    module test;
    func main() {
        case (42) {
            x => { return; }
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert any("PAR-0241" in d.message for d in parser.diagnostics)


def test_parse_case_wildcard_missing_arrow():
    src = """
    module test;
    func main() {
        case (42) {
            _ { return; }
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert any("PAR-0235" in d.message for d in parser.diagnostics)


def test_parse_case_duplicate_wildcard_default():
    """A second `_` default is PAR-0236."""
    src = """
    module test;
    func main() {
        case (42) {
            _ => { return; }
            _ => { return; }
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert any("PAR-0236" in d.message for d in parser.diagnostics)


def test_parse_case_value_arm_after_wildcard():
    src = """
    module test;
    func main() {
        case (42) {
            _ => { return; }
            1 => { return; }
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert any("PAR-0234" in d.message for d in parser.diagnostics)


# ============================================================================
# Type checker tests
# ============================================================================


def test_typecheck_case_int_passes(analyze_single):
    result = analyze_single("main", """
        module main;
        func main() -> int {
            let x: int = 1;
            case (x) {
                1 => { return 1; }
                2 => { return 2; }
                _ => { return 0; }
            }
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert len(errors) == 0, [d.message for d in errors]


def test_typecheck_case_string_passes(analyze_single):
    result = analyze_single("main", """
        module main;
        func main() -> int {
            let s: string = "hi";
            case (s) {
                "hi" => { return 1; }
                "bye" => { return 2; }
                _ => { return 0; }
            }
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert len(errors) == 0, [d.message for d in errors]


def test_typecheck_case_byte_passes(analyze_single):
    result = analyze_single("main", """
        module main;
        func main() -> int {
            let b: byte = 'a';
            case (b) {
                'a' => { return 1; }
                'b' => { return 2; }
                _ => { return 0; }
            }
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert len(errors) == 0, [d.message for d in errors]


def test_typecheck_case_bool_passes(analyze_single):
    result = analyze_single("main", """
        module main;
        func main() -> int {
            let b: bool = true;
            case (b) {
                true => { return 1; }
                false => { return 0; }
                _ => { return 0; }
            }
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert len(errors) == 0, [d.message for d in errors]


def test_typecheck_case_invalid_scrutinee_type(analyze_single):
    """TYP-0106: scrutinee must be int, byte, bool, or string."""
    result = analyze_single("main", """
        module main;
        struct Point { x: int; y: int; }
        func main() -> int {
            let p: Point = Point(1, 2);
            case (p) {
                _ => { return 0; }
            }
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert any("TYP-0106" in d.message for d in errors)


def test_typecheck_case_arm_type_mismatch(analyze_single):
    """TYP-0107: arm literal type must match scrutinee type."""
    result = analyze_single("main", """
        module main;
        func main() -> int {
            let x: int = 1;
            case (x) {
                "hello" => { return 1; }
                _ => { return 0; }
            }
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert any("TYP-0107" in d.message for d in errors)


def test_typecheck_case_duplicate_literal(analyze_single):
    """TYP-0108: duplicate literal value in case statement."""
    result = analyze_single("main", """
        module main;
        func main() -> int {
            let x: int = 1;
            case (x) {
                1 => { return 1; }
                1 => { return 2; }
                _ => { return 0; }
            }
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert any("TYP-0108" in d.message for d in errors)


def test_typecheck_case_duplicate_string_literal(analyze_single):
    """TYP-0108: duplicate string literal value."""
    result = analyze_single("main", """
        module main;
        func main() -> int {
            let s: string = "hi";
            case (s) {
                "hi" => { return 1; }
                "hi" => { return 2; }
                _ => { return 0; }
            }
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert any("TYP-0108" in d.message for d in errors)


def test_typecheck_case_duplicate_byte_literal(analyze_single):
    """TYP-0108: duplicate byte literal value."""
    result = analyze_single("main", """
        module main;
        func main() -> int {
            let b: byte = 'a';
            case (b) {
                'a' => { return 1; }
                'a' => { return 2; }
            }
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert any("TYP-0108" in d.message for d in errors)


def test_typecheck_case_return_path_with_else(analyze_single):
    """Case with else arm where all arms return should satisfy return path."""
    result = analyze_single("main", """
        module main;
        func helper(x: int) -> int {
            case (x) {
                1 => { return 1; }
                2 => { return 2; }
                _ => { return 0; }
            }
        }
        func main() -> int {
            return helper(1);
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert len(errors) == 0, [d.message for d in errors]


# ============================================================================
# Codegen tests
# ============================================================================


def test_codegen_case_int_switch(codegen_single):
    """Int case should generate a C switch statement."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let x: int = 1;
            case (x) {
                1 => { return 0; }
                2 => { return 1; }
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    assert "switch" in c_code
    assert "case" in c_code


def test_codegen_case_string_if_chain(codegen_single):
    """String case should generate an if/else chain with rt_string_equals."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let s: string = "hi";
            case (s) {
                "hi" => { return 0; }
                "bye" => { return 1; }
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    assert "rt_string_equals" in c_code
    assert "switch" not in c_code or c_code.index("rt_string_equals") < c_code.index("switch") if "switch" in c_code else True


def test_codegen_case_byte_switch(codegen_single):
    """Byte case should generate a C switch statement."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let b: byte = 'x';
            case (b) {
                'a' => { return 1; }
                'x' => { return 0; }
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    assert "switch" in c_code


def test_codegen_case_bool_switch(codegen_single):
    """Bool case should generate a C switch statement."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let b: bool = true;
            case (b) {
                true => { return 0; }
                false => { return 1; }
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    assert "switch" in c_code


def test_codegen_case_with_else(codegen_single):
    """Case with else arm should generate default case."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let x: int = 42;
            case (x) {
                1 => { return 1; }
                _ => { return 0; }
            }
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    assert "default:" in c_code


def test_codegen_case_string_with_else(codegen_single):
    """String case with else arm should generate else branch."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let s: string = "other";
            case (s) {
                "hi" => { return 1; }
                _ => { return 0; }
            }
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    assert "rt_string_equals" in c_code
    assert "else" in c_code


# ============================================================================
# Codegen tests: compile-and-run round-trips
# ============================================================================


def test_codegen_case_int_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Int case dispatches correctly at runtime."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let x: int = 2;
            case (x) {
                1 => { return 1; }
                2 => { return 0; }
                3 => { return 1; }
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (matched is 2): stderr={stderr}"


def test_codegen_case_int_else_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Int case falls through to else arm at runtime."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let x: int = 99;
            case (x) {
                1 => { return 1; }
                2 => { return 1; }
                _ => { return 0; }
            }
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (matched else): stderr={stderr}"


def test_codegen_case_string_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """String case dispatches correctly at runtime."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let s: string = "bye";
            case (s) {
                "hi" => { return 1; }
                "bye" => { return 0; }
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (matched 'bye'): stderr={stderr}"


def test_codegen_case_string_else_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """String case falls through to else arm at runtime."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let s: string = "other";
            case (s) {
                "hi" => { return 1; }
                "bye" => { return 1; }
                _ => { return 0; }
            }
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (matched else): stderr={stderr}"


def test_codegen_case_byte_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Byte case dispatches correctly at runtime."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let b: byte = 'b';
            case (b) {
                'a' => { return 1; }
                'b' => { return 0; }
                'c' => { return 1; }
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (matched 'b'): stderr={stderr}"


def test_codegen_case_bool_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Bool case dispatches correctly at runtime."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let b: bool = false;
            case (b) {
                true => { return 1; }
                false => { return 0; }
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (matched false): stderr={stderr}"


def test_codegen_case_negative_int_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Negative int literals work in case arms."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let x: int = -1;
            case (x) {
                -1 => { return 0; }
                0 => { return 1; }
                1 => { return 1; }
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (matched -1): stderr={stderr}"


def test_codegen_case_no_match_falls_through(codegen_single, compile_and_run, tmp_path):
    """Case with no else and no matching arm falls through."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let x: int = 99;
            case (x) {
                1 => { return 1; }
                2 => { return 1; }
            }
            return 0;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (no match, falls through): stderr={stderr}"


def test_codegen_case_only_else_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Case with only an else arm dispatches correctly."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let x: int = 42;
            case (x) {
                _ => { return 0; }
            }
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (only else): stderr={stderr}"


# ============================================================================
# Regression tests: unreachability tracking
# ============================================================================


def test_codegen_case_no_else_falls_through_to_with_cleanup(codegen_single, compile_and_run, tmp_path):
    """Case without else inside with — cleanup must run on fall-through (Bug regression)."""
    c_code, diags = codegen_single("main", """
        module main;
        func open_res() -> int { return 42; }
        func close_res(r: int) -> int { return r; }
        func main() -> int {
            let result: int = 0;
            with (let r = open_res() => close_res(r)) {
                case (r) {
                    99 => { return 1; }
                }
                result = 0;
            }
            return result;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (case falls through, with cleanup runs): stderr={stderr}"


# ============================================================================
# Regression tests: break/continue inside match/case switch
# ============================================================================


def test_codegen_case_break_inside_while(codegen_single, compile_and_run, tmp_path):
    """Break inside case arm inside while loop exits the loop (Bug regression)."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let i: int = 0;
            while (i < 10) {
                case (i) {
                    5 => { break; }
                }
                i = i + 1;
            }
            case (i) {
                5 => { return 0; }
                _ => { return 1; }
            }
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (break at i=5): stderr={stderr}"


def test_codegen_case_continue_inside_while(codegen_single, compile_and_run, tmp_path):
    """Continue inside case arm inside while loop continues the loop (Bug regression)."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let i: int = 0;
            let sum: int = 0;
            while (i < 6) {
                i = i + 1;
                case (i) {
                    3 => { continue; }
                }
                sum = sum + i;
            }
            case (sum) {
                18 => { return 0; }
                _ => { return 1; }
            }
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (sum=1+2+4+5+6=18, skipped 3): stderr={stderr}"


def test_codegen_match_break_inside_while(codegen_single, compile_and_run, tmp_path):
    """Break inside match arm inside while loop exits the loop (Bug regression)."""
    c_code, diags = codegen_single("main", """
        module main;
        enum Cmd { Go(); Stop(); }
        func get_cmd(i: int) -> Cmd {
            case (i) {
                3 => { return Stop(); }
                _ => { return Go(); }
            }
        }
        func main() -> int {
            let i: int = 0;
            while (i < 10) {
                let cmd: Cmd = get_cmd(i);
                match (cmd) {
                    Stop() => { break; }
                    Go() => {}
                }
                i = i + 1;
            }
            case (i) {
                3 => { return 0; }
                _ => { return 1; }
            }
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (break at i=3): stderr={stderr}"


def test_codegen_case_break_inside_for(codegen_single, compile_and_run, tmp_path):
    """Break inside case arm inside for loop exits the loop (Bug regression)."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let result: int = 0;
            for (let i: int = 0; i < 10; i = i + 1) {
                case (i) {
                    7 => { result = i; break; }
                }
            }
            case (result) {
                7 => return 0;
                _ => return 1;
            }
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (break at i=7): stderr={stderr}"


# ============================================================================
# Regression tests: scrutinee ARC scope tracking
# ============================================================================


def test_codegen_case_string_rvalue_scrutinee(codegen_single, compile_and_run, tmp_path):
    """Case on function call returning string — no leak (Bug regression)."""
    c_code, diags = codegen_single("main", """
        module main;
        func get_name() -> string { return "hello"; }
        func main() -> int {
            case (get_name()) {
                "hello" => { return 0; }
                "world" => { return 1; }
                _ => { return 2; }
            }
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Expected exit 0 (matched 'hello'): stderr={stderr}"
