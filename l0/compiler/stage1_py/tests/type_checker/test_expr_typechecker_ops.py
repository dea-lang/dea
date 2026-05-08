"""
Tests for operator type checking in expressions.
"""

#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import pytest

from conftest import has_error_code
from l0_ast import FuncDecl, ReturnStmt
from l0_types import BuiltinType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_single_return_expr(result, module_name: str, func_name: str):
    mod = result.cu.modules[module_name]
    func = next(d for d in mod.decls if isinstance(d, FuncDecl) and d.name == func_name)
    ret = next(s for s in func.body.stmts if isinstance(s, ReturnStmt))
    return ret.value


# ---------------------------------------------------------------------------
# Positive tests: each operator family in a tiny function
# ---------------------------------------------------------------------------


def test_arithmetic_ops_int_to_int(analyze_single):
    src = """
    module main;

    func f(a: int, b: int) -> int {
        return a + b;
    }

    func g(a: int, b: int) -> int {
        return a - b;
    }

    func h(a: int, b: int) -> int {
        return a * b;
    }

    func k(a: int, b: int) -> int {
        return a / b;
    }

    func m(a: int, b: int) -> int {
        return a % b;
    }
    """

    result = analyze_single("main", src)
    assert not result.has_errors()

    for fname in ["f", "g", "h", "k", "m"]:
        expr = _get_single_return_expr(result, "main", fname)
        t = result.expr_types[id(expr)]
        assert isinstance(t, BuiltinType)
        assert t.name == "int"


def test_comparison_ops_int_to_bool(analyze_single):
    src = """
    module main;

    func lt(a: int, b: int) -> bool {
        return a < b;
    }

    func le(a: int, b: int) -> bool {
        return a <= b;
    }

    func gt(a: int, b: int) -> bool {
        return a > b;
    }

    func ge(a: int, b: int) -> bool {
        return a >= b;
    }
    """

    result = analyze_single("main", src)
    assert not result.has_errors()

    for fname in ["lt", "le", "gt", "ge"]:
        expr = _get_single_return_expr(result, "main", fname)
        t = result.expr_types[id(expr)]
        assert isinstance(t, BuiltinType)
        assert t.name == "bool"


def test_equality_ops_same_type_to_bool(analyze_single):
    src = """
    module main;

    func eq_int(a: int, b: int) -> bool {
        return a == b;
    }

    func ne_bool(a: bool, b: bool) -> bool {
        return a != b;
    }
    """

    result = analyze_single("main", src)
    assert not result.has_errors()

    for fname in ["eq_int", "ne_bool"]:
        expr = _get_single_return_expr(result, "main", fname)
        t = result.expr_types[id(expr)]
        assert isinstance(t, BuiltinType)
        assert t.name == "bool"


def test_logical_ops_bool_to_bool(analyze_single):
    src = """
    module main;

    func land(a: bool, b: bool) -> bool {
        return a && b;
    }

    func lor(a: bool, b: bool) -> bool {
        return a || b;
    }
    """

    result = analyze_single("main", src)
    assert not result.has_errors()

    for fname in ["land", "lor"]:
        expr = _get_single_return_expr(result, "main", fname)
        t = result.expr_types[id(expr)]
        assert isinstance(t, BuiltinType)
        assert t.name == "bool"


# ---------------------------------------------------------------------------
# Indexing and field access
# ---------------------------------------------------------------------------


def test_index_pointer_rejected(analyze_single):
    src = """
    module main;

    extern func buf() -> int*;

    func get(i: int) -> int {
        return buf()[i];
    }
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0212")
    assert any(
        d.message == "[TYP-0212] cannot index into expression of type 'int*'; indexing is not yet supported"
        for d in result.diagnostics
    )


def test_index_requires_int_index(analyze_single):
    src = """
    module main;

    extern func buf() -> int*;

    func get(flag: bool) -> int {
        return buf()[flag];
    }
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0210")


def test_index_requires_pointer_base(analyze_single):
    src = """
    module main;

    func f(x: int) -> int {
        return x[0];
    }
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0212")
    assert any(
        d.message == "[TYP-0212] cannot index into expression of type 'int'; indexing is not yet supported"
        for d in result.diagnostics
    )


def test_index_nullable_pointer_rejected(analyze_single):
    src = """
    module main;

    extern func maybe_buf() -> int*?;

    func get(i: int) -> int {
        let buf: int*? = maybe_buf();
        return buf[i];
    }
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0211")
    assert any(
        d.message == "[TYP-0211] cannot index into nullable type 'int*?'; indexing is not yet supported"
        for d in result.diagnostics
    )


def test_field_access_struct_field_type(analyze_single):
    src = """
    module main;

    struct Point {
        x: int;
        y: int;
    }

    extern func make_point() -> Point;

    func get_x() -> int {
        let p: Point = make_point();
        return p.x;
    }
    """

    result = analyze_single("main", src)
    assert not result.has_errors()

    expr = _get_single_return_expr(result, "main", "get_x")
    t = result.expr_types[id(expr)]
    assert isinstance(t, BuiltinType)
    assert t.name == "int"


def test_field_access_unknown_field(analyze_single):
    src = """
    module main;

    struct Point {
        x: int;
    }

    extern func make_point() -> Point;

    func get_y() -> int {
        let p: Point = make_point();
        return p.y;
    }
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0221")


def test_field_access_non_struct(analyze_single):
    src = """
    module main;

    func f(x: int) -> int {
        return x.value;
    }
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0222")


def test_field_access_nullable_struct_rejected(analyze_single):
    src = """
    module main;

    struct Point {
        x: int;
        y: int;
    }

    extern func maybe_point() -> Point?;

    func get_x() -> int {
        let p: Point? = maybe_point();
        return p.x;
    }
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0220")


# ---------------------------------------------------------------------------
# Cast expressions
# ---------------------------------------------------------------------------


def test_cast_sets_result_type(analyze_single):
    src = """
    module main;

    func f(x: int) -> int {
        let opt_x : int? = x as int?; // Upcast to nullable
        let nonnull_x : int = opt_x as int; // Downcast back to non-nullable
        return nonnull_x as int; // Cast to same type
    }
    """

    result = analyze_single("main", src)
    assert not result.has_errors()

    expr = _get_single_return_expr(result, "main", "f")
    t = result.expr_types[id(expr)]
    assert isinstance(t, BuiltinType)
    assert t.name == "int"


def test_cast_unknown_type_diagnostic(analyze_single):
    src = """
    module main;

    func f(x: int) -> int {
        return x as UnknownType;
    }
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0279")


@pytest.mark.parametrize("op", ["+", "-", "*", "/", "%"])
def test_arithmetic_rejects_non_int(op, analyze_single):
    src = f"""
    module main;

    func f(a: int, b: bool) -> int {{
        return a {op} b;
    }}
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0170")


@pytest.mark.parametrize("op", ["<", "<=", ">", ">="])
def test_comparison_rejects_non_int(op, analyze_single):
    src = f"""
    module main;

    func f(a: int, b: bool) -> bool {{
        return a {op} b;
    }}
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0170")


@pytest.mark.parametrize("op", ["==", "!="])
def test_equality_requires_same_type(op, analyze_single):
    src = f"""
    module main;

    func f(a: int, b: bool) -> bool {{
        return a {op} b;
    }}
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0172")


@pytest.mark.parametrize("op", ["==", "!="])
def test_string_equality_ok(op, analyze_single):
    src = f"""
    module main;

    func f(a: string, b: string) -> bool {{
        return a {op} b;
    }}
    """

    result = analyze_single("main", src)
    assert not result.has_errors()


@pytest.mark.parametrize("op", ["<", "<=", ">", ">="])
def test_string_relational_ok(op, analyze_single):
    src = f"""
    module main;

    func f(a: string, b: string) -> bool {{
        return a {op} b;
    }}
    """

    result = analyze_single("main", src)
    assert not result.has_errors()


@pytest.mark.parametrize("op", ["<", "<=", ">", ">=", "==", "!="])
def test_string_vs_int_still_rejected(op, analyze_single):
    src = f"""
    module main;

    func f(a: string, b: int) -> bool {{
        return a {op} b;
    }}
    """

    result = analyze_single("main", src)
    assert result.has_errors()


@pytest.mark.parametrize("op", ["&&", "||"])
def test_logical_requires_bool(op, analyze_single):
    src = f"""
    module main;

    func f(a: int, b: bool) -> bool {{
        return a {op} b;
    }}
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0171")


# ---------------------------------------------------------------------------
# Integration: calls and return still behave as before alongside other ops
# ---------------------------------------------------------------------------


def test_call_and_return_with_binary_ops(analyze_single):
    src = """
    module main;

    func add(a: int, b: int) -> int {
        return a + b;
    }

    func caller() -> bool {
        let x: int = add(1, 2);
        return x > 0;
    }
    """

    result = analyze_single("main", src)
    assert not result.has_errors()

    # Ensure the return expression in caller is typed as bool.
    expr = _get_single_return_expr(result, "main", "caller")
    t = result.expr_types[id(expr)]
    assert isinstance(t, BuiltinType)
    assert t.name == "bool"


def test_let_initializer_type_ok(analyze_single):
    src = """
    module main;

    func f(a: int, b: int) -> bool {
        let c: int = a + b;
        return c > 0;
    }
    """

    result = analyze_single("main", src)
    assert not result.has_errors()


def test_let_initializer_type_mismatch(analyze_single):
    src = """
    module main;

    func f(a: int, b: int) -> bool {
        let c: bool = a + b;
        return c;
    }
    """

    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0310")


# ---------------------------------------------------------------------------
# Unary operators: '-', '!', '*' (deref)
# ---------------------------------------------------------------------------


def test_unary_minus_int_to_int(analyze_single):
    src = """
    module main;

    func f(x: int) -> int {
        return -x;
    }

    func g() -> int {
        return -42;
    }
    """
    result = analyze_single("main", src)
    assert not result.has_errors()

    for fname in ["f", "g"]:
        expr = _get_single_return_expr(result, "main", fname)
        t = result.expr_types[id(expr)]
        assert isinstance(t, BuiltinType)
        assert t.name == "int"


def test_unary_minus_rejects_non_int(analyze_single):
    src = """
    module main;

    func f(flag: bool) -> int {
        return -flag;
    }
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0160")


def test_logical_not_bool_to_bool(analyze_single):
    src = """
    module main;

    func f(flag: bool) -> bool {
        return !flag;
    }

    func g() -> bool {
        return !true;
    }
    """
    result = analyze_single("main", src)
    assert not result.has_errors()

    for fname in ["f", "g"]:
        expr = _get_single_return_expr(result, "main", fname)
        t = result.expr_types[id(expr)]
        assert isinstance(t, BuiltinType)
        assert t.name == "bool"


def test_logical_not_rejects_non_bool(analyze_single):
    src = """
    module main;

    func f(x: int) -> bool {
        return !x;
    }
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0161")


def test_deref_pointer_to_inner_type(analyze_single):
    src = """
    module main;

    extern func provide_value() -> int*;

    func g(a: int, b: int) -> int {
        let ptr: int* = provide_value();
        let value: int = *ptr;
        return a - b + value;
    }

    func h(a: int, b: int) -> int {
        let ptr: int* = provide_value();
        return a - b + *ptr;
    }
    """
    result = analyze_single("main", src)
    assert not result.has_errors()

    # Ensure return expr of h is typed as int
    expr = _get_single_return_expr(result, "main", "h")
    t = result.expr_types[id(expr)]
    assert isinstance(t, BuiltinType)
    assert t.name == "int"


def test_deref_non_pointer_rejected(analyze_single):
    src = """
    module main;

    func f(x: int) -> int {
        return *x;
    }
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0162")


def test_deref_nullable_pointer_rejected(analyze_single):
    src = """
    module main;

    extern func maybe_value() -> int*?;

    func m() -> int {
        let ptr: int*? = maybe_value();
        // We trust the caller here; null checks will be a later feature.
        return *ptr;
    }
    """
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0162")
