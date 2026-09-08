"""
Basic expression type checker tests.
"""

#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from conftest import has_error_code

from l0_ast import FuncDecl, ReturnStmt
from l0_types import BuiltinType


def test_add_function_ok(analyze_single):
    result = analyze_single(
        "main",
        """
        module main;

        func add(a: int, b: int) -> int {
            return a + b;
        }
        """,
    )

    assert not result.has_errors()

    mod = result.cu.modules["main"]
    func = next(d for d in mod.decls if isinstance(d, FuncDecl) and d.name == "add")
    ret = next(s for s in func.body.stmts if isinstance(s, ReturnStmt))
    expr = ret.value

    t = result.expr_types[id(expr)]
    assert isinstance(t, BuiltinType)
    assert t.name == "int"


def test_expression_dispatch_preserves_subclasses_cache_and_unknown_nodes(analyze_single):
    from l0_ast import Expr, IntLiteral, ParenExpr
    from l0_expr_types import ExpressionTypeChecker

    class CustomIntLiteral(IntLiteral):
        pass

    analysis = analyze_single("main", "module main;")
    checker = ExpressionTypeChecker(analysis)
    literal = CustomIntLiteral(42)
    wrapped = ParenExpr(literal)
    unknown = Expr()

    assert checker.expr._infer_expr(wrapped) == BuiltinType("int")
    assert analysis.expr_types[id(literal)] == BuiltinType("int")
    assert analysis.expr_types[id(wrapped)] == BuiltinType("int")
    assert checker.expr._infer_expr(unknown) is None
    assert id(unknown) not in analysis.expr_types

    # Cached expression types continue to take precedence over node dispatch.
    analysis.expr_types[id(wrapped)] = BuiltinType("byte")
    assert checker.expr._infer_expr(wrapped) == BuiltinType("byte")


def test_call_wrong_arity(analyze_single):
    result = analyze_single(
        "main",
        """
        module main;

        func callee(x: int) -> int {
            return x;
        }

        func caller() -> int {
            return callee(1, 2);
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0183")


def test_return_wrong_type(analyze_single):
    result = analyze_single(
        "main",
        """
        module main;

        func f() -> int {
            return true;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0315")


def test_return_void_in_non_void_function(analyze_single):
    result = analyze_single(
        "main",
        """
        module main;

        func f() -> int {
            return;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0315")


def test_invalid_return_expr_does_not_add_return_type_mismatch(analyze_single):
    result = analyze_single(
        "main",
        """
        module main;

        func f() -> int {
            return missing_name;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0159")
    assert not has_error_code(result.diagnostics, "TYP-0315")
