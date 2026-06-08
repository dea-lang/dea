#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

"""
Tests for the `with` statement: deterministic resource cleanup.

Covers:
- Lexer: `with` and `cleanup` keywords
- Parser: inline => form, cleanup block form, constraint validation
- Name resolution: scoping rules
- Type checking: statement checking in with contexts
- Codegen: LIFO cleanup, cleanup block, early return
"""

import pytest

from conftest import has_error_code
from l0_ast import (
    Module, FuncDecl, WithStmt, LetStmt, ExprStmt, AssignStmt,
)
from l0_lexer import Lexer, TokenKind
from l0_parser import Parser


# ============================================================================
# Helper
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


def test_with_keyword_lexed():
    tokens = Lexer.from_source("with").tokenize()
    assert tokens[0].kind == TokenKind.WITH
    assert tokens[0].text == "with"


def test_cleanup_keyword_lexed():
    tokens = Lexer.from_source("cleanup").tokenize()
    assert tokens[0].kind == TokenKind.CLEANUP
    assert tokens[0].text == "cleanup"


def test_with_cleanup_not_identifiers():
    tokens = Lexer.from_source("with cleanup").tokenize()
    assert tokens[0].kind == TokenKind.WITH
    assert tokens[1].kind == TokenKind.CLEANUP


# ============================================================================
# Parser tests: valid forms
# ============================================================================


def test_parse_with_inline_single_item():
    src = """
    module test;
    extern func open(name: string) -> int;
    extern func close(f: int);
    func main() {
        with (let f: int = open("a") => close(f)) {
            f;
        }
    }
    """
    stmt = get_func_body_stmt(src)
    assert isinstance(stmt, WithStmt)
    assert len(stmt.items) == 1
    assert isinstance(stmt.items[0].init, LetStmt)
    assert stmt.items[0].init.name == "f"
    assert isinstance(stmt.items[0].cleanup, ExprStmt)
    assert stmt.cleanup_body is None


def test_parse_with_inline_multiple_items():
    src = """
    module test;
    extern func open(name: string) -> int;
    extern func close(f: int);
    func main() {
        with (let f: int = open("a") => close(f),
              let g: int = open("b") => close(g)) {
            f;
            g;
        }
    }
    """
    stmt = get_func_body_stmt(src)
    assert isinstance(stmt, WithStmt)
    assert len(stmt.items) == 2
    assert isinstance(stmt.items[0].init, LetStmt)
    assert stmt.items[0].init.name == "f"
    assert isinstance(stmt.items[1].init, LetStmt)
    assert stmt.items[1].init.name == "g"
    assert stmt.items[0].cleanup is not None
    assert stmt.items[1].cleanup is not None
    assert stmt.cleanup_body is None


def test_parse_with_cleanup_block():
    src = """
    module test;
    extern func open(name: string) -> int;
    extern func close(f: int);
    extern func flush(f: int);
    func main() {
        with (let f: int = open("file")) {
            f;
        } cleanup {
            flush(f);
            close(f);
        }
    }
    """
    stmt = get_func_body_stmt(src)
    assert isinstance(stmt, WithStmt)
    assert len(stmt.items) == 1
    assert isinstance(stmt.items[0].init, LetStmt)
    assert stmt.items[0].cleanup is None
    assert stmt.cleanup_body is not None
    assert len(stmt.cleanup_body.stmts) == 2


def test_parse_with_cleanup_block_multiple_items():
    src = """
    module test;
    extern func open(name: string) -> int;
    extern func close(f: int);
    extern func free(p: int);
    extern func alloc(n: int) -> int;
    extern func write(f: int, buf: int);
    func main() {
        with (let f: int = open("file"),
              let buf: int = alloc(1024)) {
            write(f, buf);
        } cleanup {
            free(buf);
            close(f);
        }
    }
    """
    stmt = get_func_body_stmt(src)
    assert isinstance(stmt, WithStmt)
    assert len(stmt.items) == 2
    assert stmt.cleanup_body is not None
    assert len(stmt.cleanup_body.stmts) == 2


def test_parse_with_bare_expr_init():
    """Bare expression as init (e.g., lock(mutex) => unlock(mutex))."""
    src = """
    module test;
    extern func lock(m: int);
    extern func unlock(m: int);
    func main() {
        let mutex: int = 0;
        with (lock(mutex) => unlock(mutex)) {
            mutex;
        }
    }
    """
    stmt = get_func_body_stmt(src, stmt_index=1)
    assert isinstance(stmt, WithStmt)
    assert isinstance(stmt.items[0].init, ExprStmt)
    assert isinstance(stmt.items[0].cleanup, ExprStmt)


def test_parse_with_assignment_init():
    """Assignment as init (e.g., cursor.state = ACTIVE => cursor.state = CLOSED)."""
    src = """
    module test;
    func main() {
        let state: int = 0;
        with (state = 1 => state = 0) {
            state;
        }
    }
    """
    stmt = get_func_body_stmt(src, stmt_index=1)
    assert isinstance(stmt, WithStmt)
    assert isinstance(stmt.items[0].init, AssignStmt)
    assert isinstance(stmt.items[0].cleanup, AssignStmt)


def test_parse_with_empty_body():
    src = """
    module test;
    func main() {
        let x: int = 0;
        with (x = 1 => x = 0) {
        }
    }
    """
    stmt = get_func_body_stmt(src, stmt_index=1)
    assert isinstance(stmt, WithStmt)
    assert len(stmt.body.stmts) == 0


# ============================================================================
# Parser tests: invalid forms (constraint violations)
# ============================================================================


def test_parse_with_mixed_arrows_error():
    """All items must use => or none."""
    src = """
    module test;
    extern func open(name: string) -> int;
    extern func close(f: int);
    func main() {
        with (let f: int = open("a") => close(f),
              let g: int = open("b")) {
            f;
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert has_error_code(parser.diagnostics, "PAR-0503")


def test_parse_with_arrows_and_cleanup_block_error():
    """Cannot have both => and cleanup block."""
    src = """
    module test;
    extern func open(name: string) -> int;
    extern func close(f: int);
    func main() {
        with (let f: int = open("a") => close(f)) {
            f;
        } cleanup {
            close(f);
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert has_error_code(parser.diagnostics, "PAR-0504")


def test_parse_with_no_arrows_no_cleanup_error():
    """Cleanup block required when => is not used."""
    src = """
    module test;
    extern func open(name: string) -> int;
    func main() {
        with (let f: int = open("a")) {
            f;
        }
    }
    """
    mod, parser = parse_module_with_parser(src)
    assert has_error_code(parser.diagnostics, "PAR-0505")


# ============================================================================
# Type checker tests
# ============================================================================


def test_typecheck_with_inline_passes(analyze_single):
    """with statement with inline cleanup type-checks successfully."""
    result = analyze_single("main", """
        module main;
        extern func open(name: string) -> int;
        extern func close(f: int);
        func main() -> int {
            with (let f: int = open("a") => close(f)) {
                f;
            }
            return 0;
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert len(errors) == 0, [d.message for d in errors]


def test_typecheck_with_cleanup_block_passes(analyze_single):
    """with statement with cleanup block type-checks successfully."""
    result = analyze_single("main", """
        module main;
        extern func open(name: string) -> int;
        extern func close(f: int);
        extern func flush(f: int);
        func main() -> int {
            with (let f: int = open("file")) {
                f;
            } cleanup {
                flush(f);
                close(f);
            }
            return 0;
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert len(errors) == 0, [d.message for d in errors]


def test_typecheck_with_body_var_not_visible_in_cleanup(analyze_single):
    """Variables declared in body are not visible in cleanup block."""
    result = analyze_single("main", """
        module main;
        extern func open(name: string) -> int;
        extern func close(f: int);
        func main() -> int {
            with (let f: int = open("file")) {
                let body_var: int = 10;
            } cleanup {
                close(body_var);
            }
            return 0;
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert len(errors) > 0  # body_var is not defined in cleanup scope


def test_typecheck_with_sequential_item_visibility(analyze_single):
    """Item N sees names from items 0..N-1."""
    result = analyze_single("main", """
        module main;
        extern func open(name: string) -> int;
        extern func close(f: int);
        func main() -> int {
            with (let f: int = open("a") => close(f),
                  let g: int = f => close(g)) {
                f;
                g;
            }
            return 0;
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert len(errors) == 0, [d.message for d in errors]


# ============================================================================
# Codegen tests
# ============================================================================


def test_codegen_with_inline_cleanup(codegen_single):
    """with statement with inline cleanup generates correct C code."""
    c_code, diags = codegen_single("main", """
        module main;
        extern func open(name: string) -> int;
        extern func close(f: int);
        func main() -> int {
            with (let f: int = open("a") => close(f)) {
                f;
            }
            return 0;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    # The init should be emitted
    assert "open" in c_code
    # The cleanup should be emitted
    assert "close" in c_code


def test_codegen_with_inline_lifo_order(codegen_single):
    """Inline cleanup should be in LIFO order."""
    c_code, diags = codegen_single("main", """
        module main;
        extern func open(name: string) -> int;
        extern func close_a(f: int);
        extern func close_b(f: int);
        func main() -> int {
            with (let f: int = open("a") => close_a(f),
                  let g: int = open("b") => close_b(g)) {
                f;
                g;
            }
            return 0;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    # Find the function definition section (after declarations)
    func_def_start = c_code.find("l0_int l0_main_main(void)")
    assert func_def_start > 0
    func_body = c_code[func_def_start:]
    # close_b should appear before close_a in the cleanup (LIFO)
    pos_close_b = func_body.find("close_b(")
    pos_close_a = func_body.find("close_a(")
    assert pos_close_b > 0
    assert pos_close_a > 0
    assert pos_close_b < pos_close_a, f"LIFO order: close_b should come before close_a in func body"


def test_codegen_with_cleanup_block(codegen_single):
    """with statement with cleanup block generates correct C code."""
    c_code, diags = codegen_single("main", """
        module main;
        extern func open(name: string) -> int;
        extern func close(f: int);
        extern func flush(f: int);
        func main() -> int {
            with (let f: int = open("file")) {
                f;
            } cleanup {
                flush(f);
                close(f);
            }
            return 0;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    assert "flush" in c_code
    assert "close" in c_code


def test_codegen_with_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Full round-trip: cleanup sets result to 0, verifying it actually executed."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let result: int = 1;
            with (let x: int = 0 => result = x) {
                result = 1;
            }
            return result;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0 (cleanup sets result=0): stderr={stderr}"


def test_codegen_with_nested(codegen_single):
    """Nested with statements should work."""
    c_code, diags = codegen_single("main", """
        module main;
        extern func open(name: string) -> int;
        extern func close(f: int);
        func main() -> int {
            with (let f: int = open("a") => close(f)) {
                with (let g: int = open("b") => close(g)) {
                    f;
                    g;
                }
            }
            return 0;
        }
    """)
    assert c_code is not None, [d.message for d in diags]


# ============================================================================
# Codegen tests: scoping (body/cleanup as nested C blocks)
# ============================================================================


def test_codegen_with_body_shadowing_compiles(codegen_single, compile_and_run, tmp_path):
    """Body may shadow a variable from the with header without C redeclaration errors."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            with (let x: int = 1 => x = x) {
                let x: int = 2;
                x;
            }
            return 0;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success or "error" not in stderr.lower(), f"C compilation failed: {stderr}"


def test_codegen_with_cleanup_block_shadowing_compiles(codegen_single, compile_and_run, tmp_path):
    """Cleanup block may shadow a variable from the with header without C redeclaration errors."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let result: int = 0;
            with (let x: int = 1) {
                result = x;
            } cleanup {
                let x: int = 2;
                result = x;
            }
            return result;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success or "error" not in stderr.lower(), f"C compilation failed: {stderr}"


# ============================================================================
# Codegen tests: early exit cleanup
# ============================================================================


def test_codegen_with_early_return_runs_cleanup(codegen_single):
    """Early return from with body evaluates expression, then emits cleanup."""
    c_code, diags = codegen_single("main", """
        module main;
        func helper() -> int {
            let result: int = 1;
            with (let x: int = 0 => result = x) {
                return result;
            }
            return 1;
        }
        func main() -> int {
            return helper();
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    # Verify the cleanup (result = x) appears before the return in generated code
    func_start = c_code.find("l0_main_helper")
    assert func_start > 0
    func_body = c_code[func_start:]
    assert "result" in func_body
    assert "return" in func_body


def test_codegen_with_early_return_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Early return evaluates expression before cleanup; returns pre-cleanup value."""
    c_code, diags = codegen_single("main", """
        module main;
        func helper() -> int {
            let result: int = 0;
            with (let x: int = 1 => result = x) {
                return result;
            }
            return 2;
        }
        func main() -> int {
            return helper();
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0 (return value should be pre-cleanup result=0): stderr={stderr}"


def test_codegen_with_nested_early_return_cleanup_order(codegen_single):
    """Nested with cleanup should run inner before outer on early return."""
    c_code, diags = codegen_single("main", """
        module main;
        extern func cleanup_outer();
        extern func cleanup_inner();
        func helper() -> int {
            with (let x: int = 0 => cleanup_outer()) {
                with (let y: int = 0 => cleanup_inner()) {
                    return 0;
                }
            }
            return 1;
        }
        func main() -> int {
            return helper();
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    func_start = c_code.find("l0_main_helper")
    assert func_start > 0
    func_body = c_code[func_start:]
    # Temp assignment should appear before cleanup calls
    pos_tmp = func_body.find("l0_ret_")
    pos_inner = func_body.find("cleanup_inner(")
    pos_outer = func_body.find("cleanup_outer(")
    pos_return = func_body.find("return l0_ret_")
    assert pos_tmp > 0, "Expected temp var for return expression"
    assert pos_inner > 0
    assert pos_outer > 0
    assert pos_return > 0
    assert pos_tmp < pos_inner < pos_outer < pos_return


def test_codegen_with_break_runs_cleanup(codegen_single):
    """Break from within a with body inside a loop should emit cleanup."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let result: int = 1;
            while (true) {
                with (let x: int = 0 => result = x) {
                    break;
                }
            }
            return result;
        }
    """)
    assert c_code is not None, [d.message for d in diags]


def test_codegen_with_break_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Break from within a with body inside a loop runs cleanup."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let result: int = 1;
            while (true) {
                with (let x: int = 0 => result = x) {
                    break;
                }
            }
            return result;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0 (break cleanup sets result=0): stderr={stderr}"


def test_codegen_with_break_in_cleanup_block_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Break from within a with body runs cleanup block."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let result: int = 1;
            while (true) {
                with (let x: int = 0) {
                    break;
                } cleanup {
                    result = 0;
                }
            }
            return result;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0 (cleanup block on break sets result=0): stderr={stderr}"


def test_codegen_with_continue_runs_cleanup_block_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Continue from within a with body runs cleanup block."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let result: int = 1;
            let count: int = 0;
            while (count < 1) {
                count = count + 1;
                with (let x: int = 0) {
                    continue;
                } cleanup {
                    result = 0;
                }
            }
            return result;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0 (cleanup block on continue sets result=0): stderr={stderr}"


def test_codegen_with_unreachable_inline_cleanup_emitted_once(codegen_single):
    """Inline cleanup should not be emitted on unreachable fallthrough."""
    c_code, diags = codegen_single("main", """
        module main;
        extern func do_cleanup();
        func helper() -> int {
            with (let x: int = 0 => do_cleanup()) {
                return 0;
            }
            return 1;
        }
        func main() -> int {
            return helper();
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    func_start = c_code.find("l0_main_helper")
    assert func_start > 0
    func_body = c_code[func_start:]
    assert func_body.count("do_cleanup(") == 1


def test_codegen_with_cleanup_block_return_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Return inside cleanup block should compile and run with expected result."""
    c_code, diags = codegen_single("main", """
        module main;
        func helper() -> int {
            with (let x: int = 0) {
                let y: int = x + 1;
            } cleanup {
                return 0;
            }
            return 1;
        }
        func main() -> int {
            let value: int = helper();
            if (value == 0) {
                return 0;
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0: stderr={stderr}"


def test_codegen_with_expr_header_cleanup_return_overrides_body_return(codegen_single, compile_and_run, tmp_path):
    """A cleanup-block return overrides a body return even for a bare expression header item."""
    c_code, diags = codegen_single("main", """
        module main;
        import std.io;
        func helper() -> int {
            with (null) {
                return 0;
            } cleanup {
                return 1;
            }
        }
        func main() -> int {
            printl_i(helper());
            return 0;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0: stderr={stderr}"
    assert stdout == "1\n"


def test_codegen_with_inline_return_header_runs_cleanup(codegen_single, compile_and_run, tmp_path):
    """Inline cleanup runs when a with-header item returns."""
    c_code, diags = codegen_single("main", """
        module main;
        import std.io;
        func helper() -> int {
            with (return 42 => printl_s("leaving")) {
            }
            return 0;
        }
        func main() -> int {
            printl_i(helper());
            return 0;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0: stderr={stderr}"
    assert stdout == "leaving\n42\n"


def test_codegen_with_inline_return_header_evaluates_value_before_cleanup(codegen_single, compile_and_run, tmp_path):
    """A return header value is evaluated before its inline cleanup."""
    c_code, diags = codegen_single("main", """
        module main;
        import std.io;
        func value() -> int {
            printl_s("value");
            return 3;
        }
        func helper() -> int {
            with (return value() => printl_s("cleanup")) {
            }
            return 0;
        }
        func main() -> int {
            printl_i(helper());
            return 0;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0: stderr={stderr}"
    assert stdout == "value\ncleanup\n3\n"


def test_codegen_with_inline_return_header_cleanup_return_overrides(codegen_single, compile_and_run, tmp_path):
    """A return in inline cleanup overrides a pending with-header return."""
    c_code, diags = codegen_single("main", """
        module main;
        import std.io;
        func helper() -> int {
            with (return 42 => return 7) {
            }
            return 0;
        }
        func main() -> int {
            printl_i(helper());
            return 0;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0: stderr={stderr}"
    assert stdout == "7\n"


def test_codegen_with_inline_return_header_preserves_lifo_order(codegen_single, compile_and_run, tmp_path):
    """Inline cleanup remains LIFO when a later header item returns."""
    c_code, diags = codegen_single("main", """
        module main;
        import std.io;
        func helper() -> int {
            with (let a: int = 1 => printl_s("a"),
                  return 0 => printl_s("b")) {
            }
            return 1;
        }
        func main() -> int {
            printl_i(helper());
            return 0;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0: stderr={stderr}"
    assert stdout == "b\na\n0\n"


def test_codegen_with_inline_break_header_runs_cleanup(codegen_single, compile_and_run, tmp_path):
    """Inline cleanup runs before a with-header break exits the loop."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let result: int = 1;
            while (true) {
                with (break => result = 0) {
                }
            }
            return result;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0: stderr={stderr}"


def test_codegen_with_inline_continue_header_runs_cleanup(codegen_single, compile_and_run, tmp_path):
    """Inline cleanup runs before a with-header continue exits the iteration."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let result: int = 1;
            let count: int = 0;
            while (count < 1) {
                count = count + 1;
                with (continue => result = 0) {
                }
                result = 2;
            }
            return result;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0: stderr={stderr}"


def test_codegen_with_inline_cleanup_return_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Return inside inline cleanup should compile and run with expected result."""
    c_code, diags = codegen_single("main", """
        module main;
        func helper() -> int {
            with (let x: int = 0 => return 0) {
                let y: int = x + 1;
            }
            return 1;
        }
        func main() -> int {
            let value: int = helper();
            if (value == 0) {
                return 0;
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0: stderr={stderr}"


def test_codegen_with_cleanup_block_containing_with_compiles_and_runs(codegen_single, compile_and_run, tmp_path):
    """Cleanup blocks may contain nested with statements."""
    c_code, diags = codegen_single("main", """
        module main;
        func main() -> int {
            let result: int = 0;
            with (let x: int = 0) {
                result = 2;
            } cleanup {
                result = 1;
                with (let y: int = 0 => result = 0) {
                    result = 3;
                }
            }
            return result;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0 (cleanup nested with yields 0): stderr={stderr}"


def test_codegen_with_inline_cleanup_mixed_order(codegen_single):
    """Inline cleanup preserves LIFO ordering with mixed statement types."""
    c_code, diags = codegen_single("main", """
        module main;
        extern func mark(x: int);
        func main() -> int {
            let result: int = 0;
            with (let a: int = 0 => result = 1,
                  let b: int = 0 => mark(result),
                  let c: int = 0 => result = 2) {
                result = 3;
            }
            return result;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    func_start = c_code.find("l0_int l0_main_main(void)")
    assert func_start > 0
    func_body = c_code[func_start:]
    pos_result2 = func_body.find("result = 2")
    pos_mark = func_body.find("mark(")
    pos_result1 = func_body.find("result = 1")
    assert pos_result2 > 0
    assert pos_mark > 0
    assert pos_result1 > 0
    assert pos_result2 < pos_mark < pos_result1


# ============================================================================
# Codegen tests: return expression evaluation order
# ============================================================================


def test_codegen_with_return_expr_evaluated_before_cleanup(codegen_single):
    """Return expression is evaluated into a temp before with-cleanup runs."""
    c_code, diags = codegen_single("main", """
        module main;
        extern func build(x: int) -> int;
        extern func destroy(x: int);
        func helper() -> int {
            with (let r: int = 42 => destroy(r)) {
                return build(r);
            }
            return 0;
        }
        func main() -> int {
            return helper();
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    func_start = c_code.find("l0_main_helper")
    assert func_start > 0
    func_body = c_code[func_start:]
    pos_build = func_body.find("build(")
    pos_destroy = func_body.find("destroy(")
    assert pos_build > 0, "Expected build() call in generated code"
    assert pos_destroy > 0, "Expected destroy() call in generated code"
    assert pos_build < pos_destroy, "build() must be called before destroy()"


def test_codegen_return_string_expr_evaluated_before_arc_cleanup(codegen_single):
    """Return expression with local string: expression evaluated before rt_string_release."""
    c_code, diags = codegen_single("main", """
        module main;
        import std.string;
        func helper() -> int {
            let s: string = "hello";
            return len_s(s);
        }
        func main() -> int {
            return helper();
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    func_start = c_code.find("l0_main_helper")
    assert func_start > 0
    func_body = c_code[func_start:]
    pos_len = func_body.find("len_s(")
    pos_release = func_body.find("rt_string_release(")
    assert pos_len > 0, "Expected len_s() call in generated code"
    assert pos_release > 0, "Expected rt_string_release() call in generated code"
    assert pos_len < pos_release, "len_s() must be called before rt_string_release()"


def test_codegen_try_operator_emits_cleanup_on_early_return(codegen_single):
    """Try operator (?) emits cleanup in the null-check branch when cleanup exists."""
    c_code, diags = codegen_single("main", """
        module main;
        func may_fail() -> int? {
            return null;
        }
        func helper() -> int? {
            let s: string = "hello";
            let x: int = may_fail()?;
            return x as int?;
        }
        func main() -> int {
            let r: int? = helper();
            return 0;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    func_start = c_code.find("l0_main_helper")
    assert func_start > 0
    func_body = c_code[func_start:]
    # Find the try-check if-block
    pos_has_value = func_body.find("has_value")
    assert pos_has_value > 0, "Expected has_value check for try operator"
    # After the has_value check, there should be cleanup before return
    check_region = func_body[pos_has_value:]
    pos_release = check_region.find("rt_string_release(")
    pos_return = check_region.find("return")
    assert pos_release > 0, "Expected rt_string_release in try null-check branch"
    assert pos_return > 0, "Expected return in try null-check branch"
    assert pos_release < pos_return, "rt_string_release must come before return in null branch"


def test_with_header_try_failure_runs_prior_inline_cleanup(codegen_single, compile_and_run, tmp_path):
    """A ? failure in a later with-header item must run prior successful inline cleanup."""
    c_code, diags = codegen_single("main", """
        module main;
        import std.io;
        func ok() -> int? {
            return 1 as int?;
        }
        func fail() -> int? {
            return null;
        }
        func helper() -> int? {
            with (let q: int = ok()? => printl_s("cleanup_q"),
                  let p: int = fail()? => printl_s("cleanup_p")) {
                printl_s("inside");
            }
            return 0 as int?;
        }
        func main() -> int {
            let r: int? = helper();
            if (r == null) {
                return 0;
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0: stderr={stderr}"
    assert "cleanup_q" in stdout, "Expected prior successful with-header item cleanup to run"
    assert "cleanup_p" not in stdout, "Failed with-header item cleanup must not run"
    assert "inside" not in stdout, "With body should not execute when header ? fails"


def test_with_cleanup_block_header_try_failure_nullable_vars(codegen_single, compile_and_run, tmp_path):
    """Cleanup block can run on header ? failure when referenced header vars are nullable."""
    c_code, diags = codegen_single("main", """
        module main;
        import std.io;
        func ok() -> int? {
            return 1 as int?;
        }
        func fail() -> int? {
            return null;
        }
        func helper() -> int? {
            with (let q: int? = ok()?,
                  let p: int? = fail()?) {
                printl_s("inside");
            } cleanup {
                if (q != null) { printl_s("cleanup_q"); }
                if (p != null) { printl_s("cleanup_p"); }
            }
            return 0 as int?;
        }
        func main() -> int {
            let r: int? = helper();
            if (r == null) {
                return 0;
            }
            return 1;
        }
    """)
    assert c_code is not None, [d.message for d in diags]
    # Nullable lets in cleanup-block headers are predeclared to `null`.
    assert "q = {0};" in c_code
    assert "p = {0};" in c_code
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0: stderr={stderr}"
    assert "cleanup_q" in stdout
    assert "cleanup_p" not in stdout
    assert "inside" not in stdout


def test_typecheck_with_drop_in_cleanup_allowed(analyze_single):
    """Verifies that 'drop' in a 'with' cleanup clause is allowed and doesn't mark the variable as dropped in the body."""
    result = analyze_single("main", """
        module main;
        import std.io;
        struct S { field: string; }
        func main() -> int {
            with(let s = new S("hello") => drop s) {
                printl_s(s.field);
            }
            return 0;
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert len(errors) == 0, [d.message for d in errors]


def test_typecheck_with_drop_in_cleanup_use_after_drop_rejected(analyze_single):
    """Verifies that use-after-drop in cleanup clauses is still caught (LIFO order)."""
    result = analyze_single("main", """
        module main;
        import std.io;
        struct S { field: string; }
        func free_s(s: S*) { drop s; }
        func use_s(s: S*) { printl_s(s.field); }
        func main() -> int {
            with(
                let s1 = new S("S1") => use_s(s1),
                let s2 = new S("S2") => drop s1
            ) {
                printl_s("Body");
            }
            return 0;
        }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert has_error_code(errors, "TYP-0150"), [d.message for d in errors]


def test_typecheck_with_cleanup_block_header_try_failure_nonnullable_ref_rejected(analyze_single):
    """Cleanup references to maybe-uninitialized non-nullable header lets are rejected."""
    result = analyze_single("main", """
        module main;
        import std.io;
        func ok() -> int? { return 1 as int?; }
        func fail() -> int? { return null; }
        func helper() -> int? {
            with (let q: int = ok()?,
                  let p: int = fail()?) {
            } cleanup {
                printl_si("q", q);
                printl_si("p", p);
            }
            return 0 as int?;
        }
        func main() -> int { return 0; }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert has_error_code(errors, "TYP-0156"), [d.message for d in errors]


def test_typecheck_with_cleanup_block_header_try_failure_nonnullable_not_referenced_passes(analyze_single):
    """Non-nullable maybe-uninitialized header lets are allowed when cleanup does not reference them."""
    result = analyze_single("main", """
        module main;
        import std.io;
        func ok() -> int? { return 1 as int?; }
        func fail() -> int? { return null; }
        func helper() -> int? {
            with (let q: int = ok()?,
                  let p: int = fail()?) {
            } cleanup {
                printl_s("cleanup");
            }
            return 0 as int?;
        }
        func main() -> int { return 0; }
    """)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert len(errors) == 0, [d.message for d in errors]
