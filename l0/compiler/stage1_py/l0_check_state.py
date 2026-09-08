# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from enum import Enum
from l0_analysis import AnalysisResult, VarRefResolution
from l0_ast import Node, VarRef, CallExpr
from l0_compilation import CompilationUnit
from l0_diagnostics import diag_from_node
from l0_locals import FunctionEnv
from l0_symbols import ModuleEnv
from l0_types import Type, FuncType, BuiltinType, get_builtin_type, NullType, get_null_type


class StmtFlow(Enum):
    """Reachability after checking a statement or block."""

    FALLTHROUGH = "fallthrough"
    RETURNS = "returns"
    STOPS = "stops"

@dataclass
class LoopFlowCapture:
    """Liveness states for loop-control exits from one loop body."""

    break_states: list[list[dict[str, bool]]] = field(default_factory=list)
    continue_states: list[list[dict[str, bool]]] = field(default_factory=list)

@dataclass
class CheckerState:
    """Canonical checker state, lexical/liveness stacks, and diagnostic replay."""

    analysis: AnalysisResult

    def __post_init__(self) -> None:
        """Initialize checker with analysis data and cache builtin types."""
        if self.analysis.cu is None:
            raise ValueError("ExpressionTypeChecker requires a non-empty CompilationUnit")

        self.cu: CompilationUnit = self.analysis.cu
        self.module_envs: dict[str, ModuleEnv] = self.analysis.module_envs
        self.struct_infos = self.analysis.struct_infos
        self.enum_infos = self.analysis.enum_infos
        self.func_types = self.analysis.func_types
        self.func_envs = self.analysis.func_envs
        self.diagnostics = self.analysis.diagnostics
        self.expr_types = self.analysis.expr_types

        # Cached builtin types
        self.int_type: BuiltinType = get_builtin_type("int")
        self.byte_type: BuiltinType = get_builtin_type("byte")
        self.bool_type: BuiltinType = get_builtin_type("bool")
        self.string_type: BuiltinType = get_builtin_type("string")
        self.void_type: BuiltinType = get_builtin_type("void")
        self.null_type: NullType = get_null_type()

        # Per-function state (set in _check_function)
        self._current_func_env: FunctionEnv | None = None
        self._current_func_type: FuncType | None = None
        self._local_scopes: list[dict[str, Type]] = []
        self._alive_scopes: list[dict[str, bool]] = []  # definite liveness (True=usable)
        self._return_paths: bool = False  # does current path guarantee a return?
        self._breakable_loop_depth: int = 0  # depth of loops allowing 'break'/'continue'
        self._next_stmt_unreachable: bool = False  # is next statement unreachable?
        self._suppress_diagnostics: bool = False
        self._suppress_liveness_diagnostics: bool = False
        self._liveness_diagnostics_only: bool = False
        self._loop_flow_capture_stack: list[LoopFlowCapture] = []
        # Stack of guards for cleanup-block references to header vars that may
        # be uninitialized on header `?` failure paths.
        self._cleanup_header_ref_guard_stack: list[tuple[int, set[str]]] = []

    def _make_param_scope(self, func_env: FunctionEnv, func_type: FuncType) -> dict[str, Type]:
        """Create a name-to-type mapping for function parameters."""
        scope: dict[str, Type] = {}
        func = func_env.func
        for param, param_ty in zip(func.params, func_type.params):
            scope[param.name] = param_ty
        return scope

    def _make_param_alive_scope(self, func_env: FunctionEnv) -> dict[str, bool]:
        """Initialize liveness tracking for function parameters."""
        scope: dict[str, bool] = {}
        func = func_env.func
        for param in func.params:
            scope[param.name] = True
        return scope

    def _push_scope(self) -> None:
        """Enter a new lexical scope."""
        self._local_scopes.append({})
        self._alive_scopes.append({})

    def _pop_scope(self) -> None:
        """Exit the current lexical scope."""
        assert self._local_scopes, "scope stack underflow"
        self._local_scopes.pop()
        self._alive_scopes.pop()

    def _is_guarded_cleanup_header_ref(self, name: str, scope_index: int) -> bool:
        """True when a local resolves to a guarded maybe-uninitialized header let."""
        for header_scope_index, guarded_names in reversed(self._cleanup_header_ref_guard_stack):
            if scope_index == header_scope_index and name in guarded_names:
                return True
        return False

    def _lookup_alive(self, name: str) -> bool | None:
        """Check if a variable is currently alive (not dropped)."""
        for scope in reversed(self._alive_scopes):
            if name in scope:
                return scope[name]
        return None

    def _set_alive(self, name: str, alive: bool) -> None:
        """Set the liveness state of a variable."""
        for scope in reversed(self._alive_scopes):
            if name in scope:
                scope[name] = alive
                return

    def _clone_alive_scopes(self) -> list[dict[str, bool]]:
        """Clone the current definite-liveness stack."""
        return [dict(scope) for scope in self._alive_scopes]

    def _meet_alive_scopes(self, *states: list[dict[str, bool]]) -> None:
        """Keep a binding alive only when every incoming state keeps it alive."""
        self._alive_scopes = self._meet_alive_state(*states)

    def _meet_alive_state(self, *states: list[dict[str, bool]]) -> list[dict[str, bool]]:
        """Return the definite-liveness meet of several states."""
        if not states:
            return self._clone_alive_scopes()
        merged = [dict(scope) for scope in states[0]]
        for scope_index, scope in enumerate(merged):
            for name in scope:
                scope[name] = all(
                    scope_index < len(state)
                    and state[scope_index].get(name, False)
                    for state in states
                )
        return merged

    def _store_var_resolution(self, expr: VarRef, resolution: VarRefResolution) -> None:
        """Record stable resolution metadata outside liveness-only replay."""
        if not self._liveness_diagnostics_only:
            self.analysis.var_ref_resolution[id(expr)] = resolution

    def _store_sizeof_target(self, expr: CallExpr, target_ty: Type) -> None:
        """Store the resolved sizeof target type for codegen."""
        if not self._liveness_diagnostics_only:
            self.analysis.intrinsic_targets[id(expr)] = target_ty

    def _error(self, node: Node | None, message: str) -> None:
        """Report an error diagnostic."""
        self._diagnostic(node, message, kind="error")

    def _warn(self, node: Node | None, message: str) -> None:
        """Report a warning diagnostic."""
        self._diagnostic(node, message, kind="warning")

    def _diagnostic(self, node: Node | None, message: str, kind: str = "info") -> None:
        """Internal helper to create and append a diagnostic."""
        if self._suppress_diagnostics:
            return
        if self._suppress_liveness_diagnostics and (
            "[TYP-0062]" in message or "[TYP-0150]" in message
        ):
            return
        if self._liveness_diagnostics_only and not (
            "[TYP-0062]" in message or "[TYP-0150]" in message
        ):
            return
        mod_name = None
        filename = None
        if self.cu is not None and self._current_func_env is not None:
            mod_name = self._current_func_env.module_name
            mod = self.cu.modules.get(mod_name)
            if mod is not None:
                filename = mod.filename

        diagnostic = diag_from_node(
            kind=kind,
            message=message,
            module_name=mod_name,
            filename=filename,
            node=node,
        )
        if self._liveness_diagnostics_only:
            duplicate = any(
                existing.kind == diagnostic.kind
                and existing.message == diagnostic.message
                and existing.filename == diagnostic.filename
                and existing.line == diagnostic.line
                and existing.column == diagnostic.column
                for existing in self.diagnostics
            )
            if duplicate:
                return
        self.diagnostics.append(diagnostic)
