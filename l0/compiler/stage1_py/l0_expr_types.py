# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from l0_analysis import AnalysisResult
from l0_ast import BoolLiteral, ByteLiteral, CallExpr, Expr, IntLiteral, LetDecl, NullLiteral, ParenExpr, StringLiteral, VarRef
from l0_check_state import CheckerState
from l0_check_lookup import SemanticLookup
from l0_check_compat import TypeCompatibility
from l0_check_patterns import PatternAnalysis
from l0_check_liveness import ExpressionLiveness
from l0_check_flow import StatementFlow
from l0_check_expr import ExpressionInference
from l0_resolve import resolve_symbol
from l0_symbols import SymbolKind
from l0_types import NullableType, StructType, Type, format_type


class ExpressionTypeChecker:
    """Coordinate expression and statement checking for one analysis result."""

    def __init__(self, analysis: AnalysisResult) -> None:
        """Create the checker state and its semantic collaborators.

        Args:
            analysis: The analysis result whose types and diagnostics are populated.

        Raises:
            ValueError: If the analysis has no compilation unit.
        """
        self.state = CheckerState(analysis)
        self.lookup = SemanticLookup(state=self.state)
        self.compat = TypeCompatibility()
        self.patterns = PatternAnalysis(lookup=self.lookup, state=self.state)
        self.liveness = ExpressionLiveness(state=self.state)
        self.expr = ExpressionInference(compat=self.compat, liveness=self.liveness, lookup=self.lookup, state=self.state)
        self.flow = StatementFlow(compat=self.compat, expr=self.expr, liveness=self.liveness, lookup=self.lookup, patterns=self.patterns, state=self.state)

    def check(self) -> None:
        """Check expressions in module initializers and non-extern functions.

        This is the main entry point for expression analysis. It should be
        called after top-level signature resolution is complete and local scopes have been built.
        """
        if self.state.cu is None:
            self.state._error(
                None,
                "[TYP-0001] no compilation unit available for expression type checking"
            )
            return

        for env in self.state.module_envs.values():
            self.state._current_module = env.name
            for symbol in env.locals.values():
                if isinstance(symbol.node, LetDecl) and symbol.type is not None:
                    self._check_top_level_initializer(symbol.node, symbol.type)
        self.state._current_module = None

        for key, func_env in self.state.func_envs.items():
            if func_env.func.name not in self.state.module_envs[func_env.module_name].locals:
                continue  # Name resolution already rejected the declaration.
            func_type = self.state.func_types.get(key)
            if func_type is None:
                # SignatureResolver should have produced this already
                self.state._error(
                    None,
                    f"[TYP-0002] missing function type for '{func_env.module_name}::{func_env.func.name}'; skipping type check",
                )
                continue

            if func_env.func.is_extern:
                continue

            self.flow._check_function(func_env, func_type)

    def _check_top_level_initializer(self, decl: LetDecl, expected: Type) -> None:
        """Check a module binding's type and static initializer.

        Args:
            decl: Binding in the current module.
            expected: Binding type resolved during signature analysis.
        """
        if expected == self.state.void_type:
            self.state._error(decl, "[TYP-0050] variable cannot have type 'void'")
            return
        start = len(self.state.diagnostics)
        actual = self.expr._infer_expr(decl.value)
        if actual is None or any(d.kind == "error" for d in self.state.diagnostics[start:]):
            return
        if not self.compat._can_assign(expected, actual):
            target = expected.inner if isinstance(expected, NullableType) else expected
            value = self.compat._const_int_value(decl.value) if target == self.state.byte_type else None
            if value is None:
                self.state._error(decl, f"[TYP-0310] initializer for '{decl.name}' type mismatch: "
                                        f"{format_type(expected)} and {format_type(actual)}")
                return
            if not 0 <= value <= 255:
                self.state._error(decl, f"[TYP-0700] integer literal {value} is outside 0..255 for target type 'byte'")
                return
        invalid = self._non_static_initializer(decl.value)
        if invalid is not None:
            self.state._error(invalid, "[TYP-0054] A top-level let initializer must be static.")

    def _non_static_initializer(self, expr: Expr) -> Expr | None:
        """Find the first non-static operand of a successfully typed initializer.

        Args:
            expr: Expression in the current module.

        Returns:
            The offending expression, or None for a static initializer.
        """
        if isinstance(expr, ParenExpr):
            return self._non_static_initializer(expr.inner)
        if isinstance(expr, (IntLiteral, ByteLiteral, BoolLiteral, StringLiteral, NullLiteral)):
            return None
        if isinstance(expr, CallExpr):
            if expr.bare_callee_name() == "sizeof":
                return None
            if expr.bare_callee_name() == "ord":
                return self._non_static_initializer(expr.args[0])
        name = expr.callee if isinstance(expr, CallExpr) else expr
        if not isinstance(name, VarRef):
            return expr
        assert self.state._current_module is not None
        symbol = resolve_symbol(self.state.module_envs, self.state._current_module,
                                name.name, module_path=name.module_path).symbol
        if symbol is None:
            return expr
        if isinstance(expr, VarRef):
            # Type checking already verified that a bare variant has no fields.
            return None if symbol.kind is SymbolKind.ENUM_VARIANT else expr
        if symbol.kind not in (SymbolKind.STRUCT, SymbolKind.ENUM_VARIANT) and not (
            symbol.kind is SymbolKind.TYPE_ALIAS and isinstance(symbol.type, StructType)
        ):
            return expr
        for arg in expr.args:
            invalid = self._non_static_initializer(arg)
            if invalid is not None:
                return invalid
        return None
