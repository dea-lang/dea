# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from l0_analysis import AnalysisResult
from l0_ast import LetDecl
from l0_check_state import CheckerState
from l0_check_lookup import SemanticLookup
from l0_check_compat import TypeCompatibility
from l0_check_patterns import PatternAnalysis
from l0_check_liveness import ExpressionLiveness
from l0_check_flow import StatementFlow
from l0_check_expr import ExpressionInference


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
                    self.expr._infer_expr(symbol.node.value)
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
