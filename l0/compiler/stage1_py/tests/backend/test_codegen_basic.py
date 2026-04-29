"""
Comprehensive tests for C code generation backend.

Tests that the L0 compiler generates valid, compilable C code for various
language constructs including types, functions, expressions, statements,
and control flow.
"""


#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz


# ============================================================================
# Header and boilerplate tests
# ============================================================================


def test_codegen_includes_standard_headers(codegen_single):
    """Test that generated C includes standard headers."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;
        func main() -> int { return 0; }
        """,
    )

    if c_code is None:
        return  # CBackend not available

    assert "#include <stdint.h>" in c_code
    assert "#include <stdbool.h>" in c_code
    assert "#include <stddef.h>" in c_code


# ============================================================================
# Basic function generation
# ============================================================================


def test_codegen_simple_function(codegen_single):
    """Test generation of simple function with no parameters."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func get_zero() -> int {
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    # Should have declaration
    assert "l0_int l0_main_get_zero(void);" in c_code

    # Should have definition
    assert "l0_int l0_main_get_zero(void)" in c_code
    assert "return 0;" in c_code


def test_codegen_function_with_parameters(codegen_single):
    """Test generation of function with multiple parameters."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func add(a: int, b: int) -> int {
            return a + b;
        }
        """,
    )

    if c_code is None:
        return

    # Declaration
    assert "l0_int l0_main_add(l0_int a, l0_int b);" in c_code

    # Definition
    assert "l0_int l0_main_add(l0_int a, l0_int b)" in c_code
    assert "return (_rt_iadd(a, b));" in c_code


def test_codegen_extern_function_declaration(codegen_single):
    """Test that extern functions are declared not mangled."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        extern func rt_print(x: int) -> void;

        func main() -> int {
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    # Should have extern C declaration
    assert "void (rt_print)(l0_int x);" in c_code

    # Should NOT have definition body
    count = c_code.count("void (rt_print)(")
    assert count == 1  # Once in declaration only


# ============================================================================
# Struct generation
# ============================================================================


def test_codegen_simple_struct(codegen_single):
    """Test generation of simple struct."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func main() -> int { return 0; }
        """,
    )

    if c_code is None:
        return

    # Forward declaration
    assert "struct l0_main_Point;" in c_code

    # Definition
    assert "struct l0_main_Point {" in c_code
    assert "l0_int x;" in c_code
    assert "l0_int y;" in c_code


def test_codegen_struct_with_various_types(codegen_single):
    """Test struct with different field types."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Data {
            flag: bool;
            count: int;
            name: string;
        }

        func main() -> int { return 0; }
        """,
    )

    if c_code is None:
        return

    assert "l0_bool flag;" in c_code
    assert "l0_int count;" in c_code
    assert "l0_string name;" in c_code


def test_codegen_struct_with_pointer_field(codegen_single):
    """Test struct with pointer field."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Node {
            value: int;
            next: Node*;
        }

        func main() -> int { return 0; }
        """,
    )

    if c_code is None:
        return

    assert "struct l0_main_Node* next;" in c_code


# ============================================================================
# Enum generation (tagged unions)
# ============================================================================


def test_codegen_simple_enum(codegen_single):
    """Test generation of enum as tagged union."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        enum Option {
            None;
            Some(value: int);
        }

        func main() -> int { return 0; }
        """,
    )

    if c_code is None:
        return

    # Tag enum
    assert "enum l0_main_Option_tag {" in c_code
    assert "l0_main_Option_None," in c_code
    assert "l0_main_Option_Some," in c_code

    # Tagged union
    assert "struct l0_main_Option {" in c_code
    assert "enum l0_main_Option_tag tag;" in c_code
    assert "union {" in c_code
    assert ".None" in c_code or "None" in c_code  # variant name
    assert ".Some" in c_code or "Some" in c_code


def test_codegen_enum_with_multiple_fields(codegen_single):
    """Test enum variant with multiple payload fields."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        enum Expr {
            Int(value: int);
            Add(left: Expr*, right: Expr*);
        }

        func main() -> int { return 0; }
        """,
    )

    if c_code is None:
        return

    # Tag values
    assert "l0_main_Expr_Int," in c_code
    assert "l0_main_Expr_Add," in c_code

    # Payload fields
    assert "l0_int value;" in c_code
    assert "struct l0_main_Expr* left;" in c_code
    assert "struct l0_main_Expr* right;" in c_code


# ============================================================================
# Expression generation
# ============================================================================


def test_codegen_arithmetic_expressions(codegen_single):
    """Test generation of arithmetic expressions."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func compute(a: int, b: int) -> int {
            let sum: int = a + b;
            let diff: int = a - b;
            let prod: int = a * b;
            let quot: int = a / b;
            let rem: int = a % b;
            return sum;
        }
        """,
    )

    if c_code is None:
        return

    # UB-free integer operations
    assert "_rt_iadd(a, b)" in c_code
    assert "_rt_isub(a, b)" in c_code
    assert "_rt_imul(a, b)" in c_code
    assert "_rt_idiv(a, b)" in c_code
    assert "_rt_imod(a, b)" in c_code


def test_codegen_comparison_expressions(codegen_single):
    """Test generation of comparison expressions."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func compare(a: int, b: int) -> bool {
            let lt: bool = a < b;
            let le: bool = a <= b;
            let gt: bool = a > b;
            let ge: bool = a >= b;
            let eq: bool = a == b;
            let ne: bool = a != b;
            return lt;
        }
        """,
    )

    if c_code is None:
        return

    assert "(a < b)" in c_code
    assert "(a <= b)" in c_code
    assert "(a > b)" in c_code
    assert "(a >= b)" in c_code
    assert "(a == b)" in c_code
    assert "(a != b)" in c_code


def test_codegen_logical_expressions(codegen_single):
    """Test generation of logical expressions."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func logic(a: bool, b: bool) -> bool {
            let and_result: bool = a && b;
            let or_result: bool = a || b;
            let not_result: bool = !a;
            return and_result;
        }
        """,
    )

    if c_code is None:
        return

    assert "l0_bool l0_cond_" in c_code
    assert "__cond_true_" in c_code
    assert "__cond_false_" in c_code
    assert "(!a)" in c_code


def test_codegen_unary_expressions(codegen_single):
    """Test generation of unary expressions."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func unary(x: int, p: int*) -> int {
            let neg: int = -x;
            let deref: int = *p;
            return neg;
        }
        """,
    )

    if c_code is None:
        return

    assert "(-x)" in c_code
    assert "(*p)" in c_code


def test_codegen_field_access(codegen_single):
    """Test generation of field access expressions."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func get_x(p: Point) -> int {
            return p.x;
        }

        func get_x_ptr(p: Point*) -> int {
            return p.x;
        }
        """,
    )

    if c_code is None:
        return

    # Value access uses dot
    assert "(p).x" in c_code

    # Pointer access uses arrow
    assert "(p)->x" in c_code


def test_codegen_array_indexing(codegen_single):
    """Test generation of array indexing."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func get_elem(arr: int*, i: int) -> int {
            return arr[i];
        }
        """,
    )

    if c_code is None:
        return

    assert "(arr)[i]" in c_code


# ============================================================================
# Statement generation
# ============================================================================


def test_codegen_let_statement(codegen_single):
    """Test generation of let statements."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func main() -> int {
            let x: int = 42;
            let y: int = x + 1;
            return y;
        }
        """,
    )

    if c_code is None:
        return

    assert "l0_int x = 42;" in c_code
    assert "l0_int y = (_rt_iadd(x, 1));" in c_code


def test_codegen_assignment_statement(codegen_single):
    """Test generation of assignment statements."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func main() -> int {
            let x: int = 0;
            x = 42;
            return x;
        }
        """,
    )

    if c_code is None:
        return

    assert " = 42;" in c_code


def test_codegen_if_statement(codegen_single):
    """Test generation of if statements."""
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

    if c_code is None:
        return

    assert "if ((x < 0))" in c_code
    assert "else" in c_code
    assert "return (-x);" in c_code


def test_codegen_while_statement(codegen_single):
    """Test generation of while statements."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func count_to(n: int) -> int {
            let i: int = 0;
            while (i < n) {
                i = i + 1;
            }
            return i;
        }
        """,
    )

    if c_code is None:
        return

    assert "while (1)" in c_code
    assert "__cond_true_" in c_code
    assert " = (_rt_iadd(i, 1));" in c_code


def test_codegen_return_statement(codegen_single):
    """Test generation of return statements."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func get_value() -> int {
            return 42;
        }

        func do_nothing() -> void {
            return;
        }
        """,
    )

    if c_code is None:
        return

    assert "return 42;" in c_code
    assert "return;" in c_code


# ============================================================================
# Match statement generation (switch lowering)
# ============================================================================


def test_codegen_match_simple(codegen_single):
    """Test generation of simple match statement."""
    c_code, _ = codegen_single(
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
        """,
    )

    if c_code is None:
        return

    # Should have switch on tag
    assert "switch ((_scrutinee).tag)" in c_code

    # Should have case statements
    assert "case l0_main_Option_Some:" in c_code
    assert "case l0_main_Option_None:" in c_code

    # Should NOT contain break statements (since we return from each arm)
    assert not "break;" in c_code


def test_codegen_match_with_wildcard(codegen_single):
    """Test generation of match with wildcard pattern."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        enum Result {
            Ok(value: int);
            Err(code: int);
        }

        func is_ok(r: Result) -> bool {
            match (r) {
                Ok(v) => {
                    return true;
                }
                _ => {
                    return false;
                }
            }
        }
        """,
    )

    if c_code is None:
        return

    # Wildcard becomes default case
    assert "default:" in c_code


def test_codegen_match_binds_pattern_variables(codegen_single):
    """Test that match arms bind pattern variables."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        enum Expr {
            Int(value: int);
        }

        func get_value(e: Expr*) -> int {
            match (*e) {
                Int(value) => {
                    return value;
                }
            }
        }
        """,
    )

    if c_code is None:
        return

    # Should bind pattern variable
    assert "l0_int value = (_scrutinee).data.Int.value;" in c_code


# ============================================================================
# Constructor generation
# ============================================================================


def test_codegen_struct_constructor(codegen_single):
    """Test that struct constructors generate C initializers."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func make_point(a: int, b: int) -> Point {
            return Point(a, b);
        }
        """,
    )

    if c_code is None:
        return

    # Should NOT generate function call syntax
    assert "Point(a, b)" not in c_code or ".x =" in c_code

    # Should generate designated initializer
    assert ".x = a" in c_code
    assert ".y = b" in c_code


def test_codegen_enum_constructor(codegen_single):
    """Test that enum constructors generate tagged union initializers."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        enum Option {
            None;
            Some(value: int);
        }

        func make_some(x: int) -> Option {
            return Some(x);
        }
        """,
    )

    if c_code is None:
        return

    # Should NOT generate function call syntax
    assert "Some(x)" not in c_code or ".tag =" in c_code

    # Should generate tagged union initializer
    assert ".tag = l0_main_Option_Some" in c_code
    assert ".data" in c_code


# ============================================================================
# Name mangling tests
# ============================================================================


def test_codegen_name_mangling_basic(codegen_single):
    """Test basic name mangling for functions and types."""
    c_code, _ = codegen_single(
        "mymodule",
        """
        module mymodule;

        struct Data {
            value: int;
        }

        func process(d: Data) -> int {
            return d.value;
        }
        """,
    )

    if c_code is None:
        return

    # Struct should be mangled
    assert "l0_mymodule_Data" in c_code

    # Function should be mangled
    assert "l0_mymodule_process" in c_code


def test_codegen_name_mangling_dotted_module(codegen_single):
    """Test name mangling with dotted module names."""
    c_code, _ = codegen_single(
        "app.util",
        """
        module app.util;

        func helper() -> int {
            return 42;
        }
        """,
    )

    if c_code is None:
        return

    # Dots should become underscores
    assert "l0_app_util_helper" in c_code


def test_codegen_no_name_collision(codegen_single):
    """Test that similarly-named items don't collide."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
        }

        func Point() -> int {
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    # Struct and function should have different mangled names
    assert "struct l0_main_Point" in c_code
    assert "l0_int l0_main_Point(void)" in c_code


# ============================================================================
# Type mapping tests
# ============================================================================


def test_codegen_type_mapping_builtins(codegen_single):
    """Test that L0 builtins map to correct C types."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func types(i: int, b: bool, s: string) -> void {
            return;
        }
        """,
    )

    if c_code is None:
        return

    assert "l0_int i" in c_code
    assert "l0_bool b" in c_code
    assert "l0_string s" in c_code


def test_codegen_type_mapping_pointers(codegen_single):
    """Test that pointer types map correctly."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func pointers(p1: int*, p2: int**) -> int* {
            return p1;
        }
        """,
    )

    if c_code is None:
        return

    assert "l0_int* p1" in c_code
    assert "l0_int** p2" in c_code
    assert "l0_int*" in c_code.split("pointers")[0]  # return type


def test_codegen_type_mapping_nullable(codegen_single):
    """Test that nullable types map to pointers."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func nullable(x: int*?) -> int*? {
            return x;
        }
        """,
    )

    if c_code is None:
        return

    # Currently nullable maps to pointer
    assert "l0_int*" in c_code


# ============================================================================
# Edge cases and special scenarios
# ============================================================================


def test_codegen_empty_function_body(codegen_single):
    """Test generation of function with empty body (void return)."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func noop() -> void {
            return;
        }
        """,
    )

    if c_code is None:
        return

    assert "void l0_main_noop(void)" in c_code
    assert "return;" in c_code


def test_codegen_nested_expressions(codegen_single):
    """Test generation of deeply nested expressions."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func nested(a: int, b: int, c: int) -> int {
            return (a + b) * (c - a) / b;
        }
        """,
    )

    if c_code is None:
        return

    # Should have proper parenthesization
    assert "((_rt_iadd(a, b))" in c_code or "((_rt_isub(c, a))" in c_code


def test_codegen_literals(codegen_single):
    """Test generation of various literal types."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func literals() -> int {
            let i: int = 42;
            let b: bool = true;
            let s: string = "hello";
            return i;
        }
        """,
    )

    if c_code is None:
        return

    assert "42" in c_code
    assert "1" in c_code  # true -> 1
    assert '"hello"' in c_code


def test_codegen_multiple_functions(codegen_single):
    """Test generation of multiple functions in correct order."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func add(a: int, b: int) -> int {
            return a + b;
        }

        func sub(a: int, b: int) -> int {
            return a - b;
        }

        func main() -> int {
            return add(10, sub(5, 2));
        }
        """,
    )

    if c_code is None:
        return

    # All functions should be present
    assert "l0_main_add" in c_code
    assert "l0_main_sub" in c_code
    assert "int main(int argc, char **argv)" in c_code

    # Declarations should come before definitions
    decl_section = c_code.split("/* Function definitions */")[0]
    def_section = c_code.split("/* Function definitions */")[1]

    assert "l0_int l0_main_add(l0_int a, l0_int b);" in decl_section
    assert "l0_int l0_main_add(l0_int a, l0_int b)\n{" in def_section


def test_codegen_cast_expression(codegen_single):
    """Test generation of same-type cast expressions."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func cast_test(x: int) -> int {
            return x as int;
        }
        """,
    )

    if c_code is None:
        return

    # Same-type casts should lower as no-ops.
    assert "return x;" in c_code
    assert "((l0_int)(x))" not in c_code


def test_codegen_parenthesized_expression(codegen_single):
    """Test that parentheses are preserved."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        func paren_test(a: int, b: int) -> int {
            return (a + b);
        }
        """,
    )

    if c_code is None:
        return
