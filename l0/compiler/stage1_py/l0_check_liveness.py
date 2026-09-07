# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass
from l0_analysis import VarRefResolution
from l0_ast import Stmt, LetStmt, AssignStmt, ExprStmt, Expr, VarRef, UnaryOp, BinaryOp, CallExpr, IndexExpr, FieldAccessExpr, ParenExpr, CastExpr, TryExpr, NewExpr
from l0_check_state import CheckerState


@dataclass
class ExpressionLiveness:
    """Expression-only liveness and try-operator inspection."""

    state: CheckerState

    def _expr_contains_try(self, expr: Expr) -> bool:
        """Check if an expression contains a '?' try operator."""
        if isinstance(expr, TryExpr):
            return True
        if isinstance(expr, UnaryOp):
            return self._expr_contains_try(expr.operand)
        if isinstance(expr, BinaryOp):
            return self._expr_contains_try(expr.left) or self._expr_contains_try(expr.right)
        if isinstance(expr, CallExpr):
            if self._expr_contains_try(expr.callee):
                return True
            return any(self._expr_contains_try(arg) for arg in expr.args)
        if isinstance(expr, IndexExpr):
            return self._expr_contains_try(expr.array) or self._expr_contains_try(expr.index)
        if isinstance(expr, FieldAccessExpr):
            return self._expr_contains_try(expr.obj)
        if isinstance(expr, ParenExpr):
            return self._expr_contains_try(expr.inner)
        if isinstance(expr, CastExpr):
            return self._expr_contains_try(expr.expr)
        if isinstance(expr, NewExpr):
            return any(self._expr_contains_try(arg) for arg in expr.args)
        return False

    def _stmt_contains_try(self, stmt: Stmt) -> bool:
        """Check if a statement contains a '?' try operator."""
        if isinstance(stmt, LetStmt):
            return self._expr_contains_try(stmt.value)
        if isinstance(stmt, AssignStmt):
            return self._expr_contains_try(stmt.target) or self._expr_contains_try(stmt.value)
        if isinstance(stmt, ExprStmt):
            return self._expr_contains_try(stmt.expr)
        return False

    def _check_expr_liveness(self, expr: Expr) -> None:
        """Replay only local-variable use checks for an already typed expression."""
        if isinstance(expr, VarRef):
            if self.state.analysis.var_ref_resolution.get(id(expr)) is VarRefResolution.LOCAL:
                alive = self.state._lookup_alive(expr.name)
                if alive is False:
                    self.state._error(expr, f"[TYP-0150] use of dropped variable '{expr.name}'")
            return
        if isinstance(expr, UnaryOp):
            self._check_expr_liveness(expr.operand)
        elif isinstance(expr, BinaryOp):
            self._check_expr_liveness(expr.left)
            self._check_expr_liveness(expr.right)
        elif isinstance(expr, CallExpr):
            self._check_expr_liveness(expr.callee)
            for arg in expr.args:
                self._check_expr_liveness(arg)
        elif isinstance(expr, IndexExpr):
            self._check_expr_liveness(expr.array)
            self._check_expr_liveness(expr.index)
        elif isinstance(expr, FieldAccessExpr):
            self._check_expr_liveness(expr.obj)
        elif isinstance(expr, ParenExpr):
            self._check_expr_liveness(expr.inner)
        elif isinstance(expr, CastExpr):
            self._check_expr_liveness(expr.expr)
        elif isinstance(expr, NewExpr):
            for arg in expr.args:
                self._check_expr_liveness(arg)
        elif isinstance(expr, TryExpr):
            self._check_expr_liveness(expr.expr)
