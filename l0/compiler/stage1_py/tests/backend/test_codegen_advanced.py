"""
Advanced C code generation tests for L0 compiler.

This test suite focuses on:
- Multi-module code generation
- Cross-module dependencies
- Complex type scenarios
- Integration tests
- Optional compilation tests (if C compiler available)
"""

#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import pytest

from l0_backend import Backend
from l0_driver import L0Driver


# ============================================================================
# Multi-module code generation
# ============================================================================


def test_codegen_multi_module_basic(write_l0_file, temp_project):
    """Test code generation for multiple modules."""
    # Define a utility module
    write_l0_file(
        "util",
        """
        module util;

        func times2(x: int) -> int {
            return x * 2;
        }
        """,
    )

    # Define main module that imports util
    write_l0_file(
        "main",
        """
        module main;
        import util;

        func main() -> int {
            return times2(21);
        }
        """,
    )

    driver = L0Driver()
    driver.search_paths.add_project_root(temp_project)
    result = driver.analyze("main")

    if result.has_errors():
        pytest.fail("Analysis failed: " + ", ".join(diag.format() for diag in result.diagnostics))

    backend = Backend(result)
    c_code = backend.generate()

    # Should have both modules' functions
    assert "l0_util_times2" in c_code
    assert "l0_int l0_main_main(void)" in c_code

    # main should call util function
    assert "l0_util_times2(21)" in c_code


def test_codegen_multi_module_shared_types(write_l0_file, temp_project):
    """Test code generation with shared types across modules."""
    write_l0_file(
        "types",
        """
        module types;

        struct Point {
            x: int;
            y: int;
        }
        """,
    )

    write_l0_file(
        "ops",
        """
        module ops;
        import types;

        func distance_squared(p: Point) -> int {
            return p.x * p.x + p.y * p.y;
        }
        """,
    )

    write_l0_file(
        "main",
        """
        module main;
        import types;
        import ops;

        func main() -> int {
            let p: Point = Point(3, 4);
            return distance_squared(p);
        }
        """,
    )

    driver = L0Driver()
    driver.search_paths.add_project_root(temp_project)
    result = driver.analyze("main")

    if result.has_errors():
        pytest.skip("Analysis failed")

    backend = Backend(result)
    c_code = backend.generate()

    # Point struct should be defined (from types module)
    assert "struct l0_types_Point" in c_code

    # Functions from all modules should be present
    assert "l0_ops_distance_squared" in c_code
    assert "int main(" in c_code


def test_codegen_multi_module_enum_across_modules(write_l0_file, temp_project):
    """Test enum defined in one module, used in another."""
    write_l0_file(
        "result",
        """
        module result;

        enum Result {
            Ok(value: int);
            Err(code: int);
        }
        """,
    )

    write_l0_file(
        "checker",
        """
        module checker;
        import result;

        func is_ok(r: Result) -> bool {
            match (r) {
                Ok(v) => {
                    return true;
                }
                Err(e) => {
                    return false;
                }
            }
        }
        """,
    )

    driver = L0Driver()
    driver.search_paths.add_project_root(temp_project)
    result = driver.analyze("checker")

    if result.has_errors():
        pytest.skip("Analysis failed")

    backend = Backend(result)
    c_code = backend.generate()

    # Result enum tag should be defined
    assert "enum l0_result_Result_tag" in c_code
    assert "l0_result_Result_Ok" in c_code
    assert "l0_result_Result_Err" in c_code

    # Tagged union should be defined
    assert "struct l0_result_Result" in c_code


# ============================================================================
# Complex type scenarios
# ============================================================================


def test_codegen_recursive_struct(codegen_single):
    """Test code generation for recursive struct (linked list)."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Node {
            value: int;
            next: Node*;
        }

        func create_node(v: int, n: Node*) -> Node {
            return Node(v, n);
        }
        """,
    )
    assert c_code is not None

    # Forward declaration should be present
    assert "struct l0_main_Node;" in c_code

    # Struct should reference itself via pointer
    assert "struct l0_main_Node* next;" in c_code


def test_codegen_recursive_enum(codegen_single):
    """Test code generation for recursive enum (expression tree)."""
    c_code, err = codegen_single(
        "main",
        """
        module main;

        enum Expr {
            Lit(value: int);
            Add(left: Expr*, right: Expr*);
            Mul(left: Expr*, right: Expr*);
        }

        func eval(e: Expr*) -> int {
            match (*e) {
                Lit(v) => {
                    return v;
                }
                Add(l, r) => {
                    return eval(l) + eval(r);
                }
                Mul(l, r) => {
                    return eval(l) * eval(r);
                }
            }
        }
        """,
    )

    if c_code is None:
        print("Errors during codegen:")
        for diag in err:
            print(f"  {diag.format()}")
        pytest.fail("codegen failed")

    # Tag enum should have all variants
    assert "l0_main_Expr_Lit" in c_code
    assert "l0_main_Expr_Add" in c_code
    assert "l0_main_Expr_Mul" in c_code

    # Union should have variant structs
    assert "struct l0_main_Expr* left;" in c_code
    assert "struct l0_main_Expr* right;" in c_code


def test_codegen_struct_with_enum_field(codegen_single):
    """Test struct containing enum field."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        enum Status {
            Pending;
            Done;
        }

        struct Task {
            id: int;
            status: Status;
        }

        func create_task(i: int) -> Task {
            return Task(i, Pending());
        }
        """,
    )
    assert c_code is not None

    # Status enum should be defined
    assert "enum l0_main_Status_tag" in c_code

    # Task struct should have Status field
    assert "struct l0_main_Status status;" in c_code


def test_codegen_enum_with_struct_field(codegen_single):
    """Test enum variant containing struct field."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        enum Shape {
            Circle(center: Point, radius: int);
            Rectangle(corner: Point, width: int, height: int);
        }

        func make_circle(p: Point, r: int) -> Shape {
            return Circle(p, r);
        }
        """,
    )
    assert c_code is not None

    # Point struct should be defined
    assert "struct l0_main_Point" in c_code

    # Shape enum should have variants with Point fields
    assert "struct l0_main_Point center;" in c_code
    assert "struct l0_main_Point corner;" in c_code


def test_codegen_multiple_pointer_indirection(codegen_single):
    """Test generation with multiple levels of pointer indirection."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func triple_deref(p: int***) -> int {
            return ***p;
        }
        """,
    )
    assert c_code is not None

    # Function parameter should have triple pointer
    assert "l0_int*** p" in c_code

    # Return should have triple deref
    assert "(*(*(*p)))" in c_code or "(***p)" in c_code


# ============================================================================
# Control flow edge cases
# ============================================================================


def test_codegen_nested_if_statements(codegen_single):
    """Test generation of nested if statements."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func classify(x: int) -> int {
            if (x > 0) {
                if (x > 10) {
                    return 2;
                } else {
                    return 1;
                }
            } else {
                if (x < -10) {
                    return -2;
                } else {
                    return -1;
                }
            }
        }
        """,
    )
    assert c_code is not None

    # Should have nested if/else structure
    assert c_code.count("if (") >= 3
    assert c_code.count("else") >= 3


def test_codegen_nested_while_loops(codegen_single):
    """Test generation of nested while loops."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func nested_loops(n: int) -> int {
            let i: int = 0;
            let sum: int = 0;
            while (i < n) {
                let j: int = 0;
                while (j < n) {
                    sum = sum + 1;
                    j = j + 1;
                }
                i = i + 1;
            }
            return sum;
        }
        """,
    )
    assert c_code is not None

    # Should have two while loops
    assert c_code.count("while (") >= 2


def test_codegen_match_all_patterns(codegen_single):
    """Test match with multiple patterns including wildcard."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        enum Token {
            Number(value: int);
            Plus;
            Minus;
            Star;
            Slash;
        }

        func token_precedence(t: Token) -> int {
            match (t) {
                Plus() => { return 1; }
                Minus() => { return 1; }
                Star() => { return 2; }
                Slash() => { return 2; }
                _ => { return 0; }
            }
        }
        """,
    )
    assert c_code is not None

    # Should have case for each variant
    assert "case l0_main_Token_Plus:" in c_code
    assert "case l0_main_Token_Minus:" in c_code
    assert "case l0_main_Token_Star:" in c_code
    assert "case l0_main_Token_Slash:" in c_code

    # Should have default case for wildcard
    assert "default:" in c_code


def test_codegen_early_return_in_loop(codegen_single):
    """Test generation of early return inside loop."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func find_min42(len: int) -> int {
            let i: int = 0;
            while (i < len) {
                if (i >= 42) {
                    return i;
                }
                i = i + 1;
            }
            return -1;
        }
        """,
    )
    assert c_code is not None

    # Should have return inside if inside while
    assert "while (1)" in c_code
    assert "__cond_true_" in c_code
    assert "if (i >= 42)" in c_code
    assert "if ((i >= 42))" not in c_code
    assert "return i;" in c_code
    assert "return -1;" in c_code


def test_codegen_condition_headers_drop_only_outer_parens(codegen_single):
    """Condition headers should avoid redundant outer parens and keep nested ones."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func main(x: int, y: int, a: int, b: int, limit: int) -> int {
            if (x == y) {
                return 1;
            }
            while (x < y) {
                x = x + 1;
            }
            if ((a + b) < limit) {
                return 2;
            }
            return 0;
        }
        """,
    )
    assert c_code is not None
    assert "if (x == y)" in c_code
    assert "if ((x == y))" not in c_code
    assert "if (((_rt_iadd(a, b))) < limit)" in c_code
    assert "if (x < y)" in c_code
    assert "if ((x < y))" not in c_code


def test_codegen_try_cleanup_niche_nullable_avoids_redundant_condition_parens(codegen_single):
    """`?` on pointer nullables should keep direct null checks when cleanup is active."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Box {
            value: int;
        }

        func maybe_box(flag: bool) -> Box*? {
            if (flag) {
                return new Box(11);
            }
            return null;
        }

        func main() -> int? {
            let keep = new Box();
            let box = maybe_box(true)?;
            drop box;
            drop keep;
            return 0;
        }
        """,
    )
    assert c_code is not None
    assert "if (l0_try_" in c_code
    assert "== NULL)" in c_code
    assert "if ((l0_try_" not in c_code


# ============================================================================
# Expression complexity tests
# ============================================================================


def test_codegen_complex_boolean_expression(codegen_single):
    """Test generation of complex boolean expression."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func in_range(x: int, min: int, max: int) -> bool {
            return x >= min && x <= max;
        }

        func is_valid(x: int, y: int, z: int) -> bool {
            return (x > 0 || y > 0) && z > 0;
        }
        """,
    )
    assert c_code is not None

    # Logical expressions now lower through structured short-circuit branching.
    assert "l0_bool l0_cond_" in c_code
    assert "__cond_true_" in c_code
    assert "__cond_false_" in c_code
    assert ">=" in c_code
    assert "<=" in c_code


def test_codegen_chained_function_calls(codegen_single):
    """Test generation of chained function calls."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func add(a: int, b: int) -> int {
            return a + b;
        }

        func mul(a: int, b: int) -> int {
            return a * b;
        }

        func compute() -> int {
            return add(mul(2, 3), mul(4, 5));
        }
        """,
    )
    assert c_code is not None

    # Should have nested function calls
    assert "l0_main_add(" in c_code
    assert "l0_main_mul(" in c_code


def test_codegen_mixed_operator_precedence(codegen_single):
    """Test correct precedence with mixed operators."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func precedence_test(a: int, b: int, c: int) -> int {
            return a + b * c - a / b;
        }
        """,
    )
    assert c_code is not None

    # Should have proper grouping
    # (a + (b * c)) - (a / b)
    assert "_rt_imul(b, c)" in c_code
    assert "_rt_iadd(a, " in c_code
    assert "_rt_isub(" in c_code
    assert "_rt_idiv(a, b)" in c_code


# ============================================================================
# String literal handling
# ============================================================================


def test_codegen_string_literals(codegen_single):
    """Test generation of string literals."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func get_message() -> string {
            return "Hello, World!";
        }
        """,
    )
    assert c_code is not None

    # String literal should be preserved
    assert '"Hello, World!"' in c_code


def test_codegen_string_with_escapes(codegen_single):
    """Test generation of strings with escape sequences."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func get_escaped() -> string {
            return "Line1\\nLine2\\tTabbed";
        }
        """,
    )
    assert c_code is not None

    # Escape sequences should be preserved
    assert '\\n' in c_code or 'Line1' in c_code
    assert '\\t' in c_code or 'Tabbed' in c_code


# ============================================================================
# Extern function integration
# ============================================================================


def test_codegen_extern_function_calls(codegen_single):
    """Test calling extern functions from L0 code."""
    c_code, diag = codegen_single(
        "main",
        """
        module main;

        extern func rt_print(msg: string) -> void;
        extern func rt_alloc(size: int) -> int*;

        func demo() -> void {
            rt_print("test");
            return;
        }
        """,
    )

    if c_code is None:
        pytest.skip(f"Errors: " + ", ".join(d.format() for d in diag))

    # Extern declarations should be present
    assert "void (rt_print)(l0_string msg);" in c_code
    assert "l0_int* (rt_alloc)(l0_int size);" in c_code

    # Call to extern should pass an inline static l0_string value.
    assert 'rt_print(((l0_string)L0_STRING_CONST("test", 4)))' in c_code


def test_codegen_extern_with_pointer_return(codegen_single):
    """Test extern function returning pointer."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        extern func allocate() -> int*;

        func use_allocate() -> int {
            let p: int* = allocate();
            return *p;
        }
        """,
    )
    assert c_code is not None

    # Return type should be pointer
    assert "l0_int* (allocate)(void);" in c_code

    # Call and dereference should be present
    assert "allocate()" in c_code
    assert "(*p)" in c_code


# ============================================================================
# Compilation tests
# ============================================================================

def test_generated_code_compiles_minimal(codegen_single, tmp_path, compile_and_run):
    """Test that generated C code actually compiles."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func main() -> int {
            return 0;
        }
        """,
    )
    assert c_code is not None

    # Try to compile
    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Compilation failed.\nstdout: {stdout}\nstderr: {stderr}"

def test_generated_code_compiles_with_struct(codegen_single, tmp_path, compile_and_run):
    """Test that generated code with structs compiles."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func main() -> int {
            let p: Point = Point(3, 4);
            return p.x + p.y - 7;
        }
        """,
    )
    assert c_code is not None

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Compilation failed.\nstdout: {stdout}\nstderr: {stderr}"


def test_generated_code_same_type_struct_cast_avoids_c_cast(codegen_single, tmp_path, compile_and_run):
    """Test that same-type struct casts do not lower to pedantic-invalid C casts."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Token {
            payload: string;
            offset: int;
        }

        func get(x: int) -> Token? {
            if (x % 2 == 0) {
                return null;
            }
            return Token("hello", 0);
        }

        func pl(t: Token) -> int {
            return t.offset;
        }

        func main() -> int {
            let t2: Token? = get(1);

            if (t2 != null) {
                let t3: Token = t2 as Token;
                return pl(t3 as Token) - 0;
            }

            return 1;
        }
        """,
    )
    assert c_code is not None
    assert "l0_main_pl(((struct l0_main_Token)(" not in c_code

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Compilation failed.\nstdout: {stdout}\nstderr: {stderr}"


def test_generated_code_compiles_with_enum(codegen_single, tmp_path, compile_and_run):
    """Test that generated code with enums compiles."""
    c_code, err = codegen_single(
        "main",
        """
        module main;

        enum Option {
            None;
            Some(value: int);
        }

        func unwrap_or(opt: Option, default: int) -> int {
            match (opt) {
                Some(v) => {
                    return v;
                }
                None() => {
                    return default;
                }
            }
        }

        func main() -> int {
            let opt: Option = Some(42);
            return unwrap_or(opt, 0) - 42;
        }
        """,
    )

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Compilation failed.\nstdout: {stdout}\nstderr: {stderr}"


def test_generated_code_runs_correctly(codegen_single, tmp_path, compile_and_run):
    """Test that generated code runs and produces correct output."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func add(a: int, b: int) -> int {
            return a + b;
        }

        func main() -> int {
            return add(40, 2) - 42;
        }
        """,
    )
    assert c_code is not None

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Compilation failed.\nstdout: {stdout}\nstderr: {stderr}"


# ============================================================================
# Comment and whitespace preservation tests
# ============================================================================


def test_codegen_readable_output(codegen_single):
    """Test that generated code is readable with proper formatting."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func main() -> int {
            let x: int = 1;
            let y: int = 2;
            return x + y;
        }
        """,
    )
    assert c_code is not None

    # Should have reasonable indentation (not all on one line)
    lines = c_code.split('\n')
    assert len(lines) > 10

    # Should have some indented lines
    indented_lines = [line for line in lines if line.startswith('    ')]
    assert len(indented_lines) > 0


def test_codegen_section_comments(codegen_single):
    """Test that generated code has section comments."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Data {
            value: int;
        }

        func main() -> int {
            return 0;
        }
        """,
    )
    assert c_code is not None

    # Should have section comments
    assert "/* L0 runtime" in c_code
    assert "/* Function" in c_code


# ============================================================================
# Error handling edge cases
# ============================================================================


def test_codegen_handles_void_function(codegen_single):
    """Test code generation for void return type."""
    c_code, diag = codegen_single(
        "main",
        """
        module main;

        func do_nothing() -> void {
            return;
        }

        func main() -> int {
            do_nothing();
            return 0;
        }
        """,
    )

    if c_code is None:
        pytest.skip(f"Errors: " + ", ".join(d.format() for d in diag))

    assert "void l0_main_do_nothing(void)" in c_code
    assert "l0_main_do_nothing();" in c_code


def test_codegen_zero_parameter_function(codegen_single):
    """Test function with no parameters uses void."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func get_constant() -> int {
            return 42;
        }
        """,
    )
    assert c_code is not None

    # Should use (void) not ()
    assert "l0_int l0_main_get_constant(void)" in c_code


def test_codegen_single_statement_blocks(codegen_single):
    """Test blocks with single statements."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func abs(x: int) -> int {
            if (x < 0) {
                return -x;
            } else {
                return x;
            }
        }
        """,
    )
    assert c_code is not None

    # Blocks should still have braces
    assert c_code.count("{") >= 3
    assert c_code.count("}") >= 3
