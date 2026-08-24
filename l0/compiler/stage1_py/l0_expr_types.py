#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Expression-level type checking for the L0 compiler."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List, Set, Tuple

from l0_analysis import AnalysisResult, VarRefResolution
from l0_ast import (
    Node, Stmt, Block, LetStmt, AssignStmt, ExprStmt, IfStmt, WhileStmt,
    ReturnStmt, MatchArm, MatchStmt, CaseStmt, Expr, IntLiteral, StringLiteral, BoolLiteral,
    NullLiteral, VarRef, UnaryOp, BinaryOp, CallExpr, IndexExpr, FieldAccessExpr, ParenExpr, CastExpr, VariantPattern,
    TryExpr, TypeExpr, DropStmt, NewExpr, WildcardPattern, BreakStmt, ContinueStmt, ForStmt, ByteLiteral,
    TypeAliasDecl, WithStmt)
from l0_compilation import CompilationUnit
from l0_diagnostics import diag_from_node
from l0_locals import FunctionEnv
from l0_logger import log_debug
from l0_resolve import resolve_symbol, resolve_type_ref, TypeResolveErrorKind, ResolveErrorKind
from l0_string_escape import decode_l0_string_token, EscapeDecodeError
from l0_symbols import ModuleEnv, SymbolKind, Symbol
from l0_types import (
    Type,
    FuncType,
    BuiltinType,
    StructType,
    EnumType,
    get_builtin_type,
    PointerType,
    NullableType,
    NullType,
    get_null_type,
    format_type, )


class StmtFlow(Enum):
    """Reachability after checking a statement or block."""

    FALLTHROUGH = "fallthrough"
    RETURNS = "returns"
    STOPS = "stops"


@dataclass
class LoopFlowCapture:
    """Liveness states for loop-control exits from one loop body."""

    break_states: List[List[Dict[str, bool]]] = field(default_factory=list)
    continue_states: List[List[Dict[str, bool]]] = field(default_factory=list)


@dataclass
class ExpressionTypeChecker:
    """Expression-level type checker for L0.

    This checker implements:
      - Expression typing: literals, variables, operators, calls, constructors,
        casts, dereference, indexing, field access, try-operator, sizeof.
      - Structs and enums: construction, field access, variant patterns, ord.
      - Function calls: argument validation and signature matching.
      - Type compatibility: int, bool, string, pointers, nullability.
      - Statement checking: let (with inference), return, if, while, match, drop.
      - Control flow: return path analysis, unreachable code detection.
      - Memory safety: flow-sensitive liveness for dropped variables.

    Attributes:
        analysis: The AnalysisResult to populate with types and diagnostics.
    """
    analysis: AnalysisResult

    def __post_init__(self) -> None:
        """Initialize checker with analysis data and cache builtin types."""
        if self.analysis.cu is None:
            raise ValueError("ExpressionTypeChecker requires a non-empty CompilationUnit")

        self.cu: CompilationUnit = self.analysis.cu
        self.module_envs: Dict[str, ModuleEnv] = self.analysis.module_envs
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
        self._current_func_env: Optional[FunctionEnv] = None
        self._current_func_type: Optional[FuncType] = None
        self._local_scopes: List[Dict[str, Type]] = []
        self._alive_scopes: List[Dict[str, bool]] = []  # definite liveness (True=usable)
        self._return_paths: bool = False  # does current path guarantee a return?
        self._breakable_loop_depth: int = 0  # depth of loops allowing 'break'/'continue'
        self._next_stmt_unreachable: bool = False  # is next statement unreachable?
        self._suppress_diagnostics: bool = False
        self._suppress_liveness_diagnostics: bool = False
        self._liveness_diagnostics_only: bool = False
        self._loop_flow_capture_stack: List[LoopFlowCapture] = []
        # Stack of guards for cleanup-block references to header vars that may
        # be uninitialized on header `?` failure paths.
        self._cleanup_header_ref_guard_stack: List[Tuple[int, Set[str]]] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def check(self) -> None:
        """Run expression/type checking for all non-extern functions.

        This is the main entry point for expression analysis. It should be
        called after top-level signature resolution is complete and local scopes have been built.
        """
        if self.cu is None:
            self._error(
                None,
                "[TYP-0001] no compilation unit available for expression type checking"
            )
            return

        for key, func_env in self.func_envs.items():
            func_type = self.func_types.get(key)
            if func_type is None:
                # SignatureResolver should have produced this already
                self._error(
                    None,
                    f"[TYP-0002] missing function type for '{func_env.module_name}::{func_env.func.name}'; skipping type check",
                )
                continue

            if func_env.func.is_extern:
                continue

            self._check_function(func_env, func_type)

    # ------------------------------------------------------------------
    # Function / block / statement traversal
    # ------------------------------------------------------------------

    def _check_function(self, func_env: FunctionEnv, func_type: FuncType) -> None:
        """Check a single function definition.

        Args:
            func_env: The function's environment containing AST and module info.
            func_type: The function's resolved signature.
        """
        self._current_func_env = func_env
        self._current_func_type = func_type

        # Root scope: one frame containing parameters
        self._local_scopes = [self._make_param_scope(func_env, func_type)]
        self._alive_scopes = [self._make_param_alive_scope(func_env)]

        # Track whether the function body guarantees a return along all paths.
        self._return_paths = False
        self._check_block(func_env.func.body, check_return_paths=True, push_new_scope=False)
        self._breakable_loop_depth = 0
        self._next_stmt_unreachable = False
        guarantees_return = self._return_paths

        # Only require guaranteed return when result type is non-void.
        is_void_result = self._is_void(func_type.result)
        if not is_void_result and not guarantees_return:
            self._error(
                func_env.func,
                f"[TYP-0010] not all control paths return a value of type '{format_type(func_type.result)}'",
            )

        self._local_scopes = []
        self._current_func_env = None
        self._current_func_type = None

    def _make_param_scope(self, func_env: FunctionEnv, func_type: FuncType) -> Dict[str, Type]:
        """Create a name-to-type mapping for function parameters."""
        scope: Dict[str, Type] = {}
        func = func_env.func
        for param, param_ty in zip(func.params, func_type.params):
            scope[param.name] = param_ty
        return scope

    def _make_param_alive_scope(self, func_env: FunctionEnv) -> Dict[str, bool]:
        """Initialize liveness tracking for function parameters."""
        scope: Dict[str, bool] = {}
        func = func_env.func
        for param in func.params:
            scope[param.name] = True
        return scope

    # Basic lexical scope stack (function body and nested blocks)

    def _push_scope(self) -> None:
        """Enter a new lexical scope."""
        self._local_scopes.append({})
        self._alive_scopes.append({})

    def _pop_scope(self) -> None:
        """Exit the current lexical scope."""
        assert self._local_scopes, "scope stack underflow"
        self._local_scopes.pop()
        self._alive_scopes.pop()

    def _declare_local(self, name: str, typ: Type, node: Node) -> None:
        """Declare a local variable in the innermost scope.

        Args:
            name: The name of the variable.
            typ: The resolved Type of the variable.
            node: The AST node where the declaration occurs.
        """
        assert self._local_scopes, "no active scope"
        local = self._local_scopes[-1]
        if name in local:
            self._error(node,
                        f"[TYP-0020] local variable '{name}' already declared in this scope with type '{format_type(local[name])}'")
            return None

        if self._lookup_local(name) is not None:
            self._warn(node, f"[TYP-0021] local variable '{name}' shadows variable from outer scope")

        if self._current_func_env is not None:
            module_name = self._current_func_env.module_name
            sym_result = resolve_symbol(self.module_envs, module_name, name)
            sym = sym_result.symbol
            if sym is not None and sym.kind is SymbolKind.ENUM_VARIANT:
                if sym.module.name != module_name:
                    self._warn(
                        node,
                        f"[TYP-0023] local variable '{name}' shadows imported enum variant '{sym.module.name}::{name}'",
                    )
                else:
                    self._warn(
                        node,
                        f"[TYP-0022] local variable '{name}' shadows enum variant '{sym.module.name}::{name}'",
                    )
            elif sym is not None and sym.kind in (SymbolKind.FUNC, SymbolKind.STRUCT,
                                                  SymbolKind.ENUM, SymbolKind.TYPE_ALIAS):
                kind_label = sym.kind.name.lower().replace("_", " ")
                if sym.module.name != module_name:
                    self._warn(
                        node,
                        f"[TYP-0025] local variable '{name}' shadows imported "
                        f"{kind_label} '{sym.module.name}::{name}'",
                    )
                else:
                    self._warn(
                        node,
                        f"[TYP-0025] local variable '{name}' shadows "
                        f"{kind_label} '{sym.module.name}::{name}'",
                    )
            elif sym is None and sym_result.error is ResolveErrorKind.AMBIGUOUS_SYMBOL:
                modules_str = "', '".join(sym_result.ambiguous_modules)
                self._warn(
                    node,
                    f"[TYP-0024] local variable '{name}' shadows ambiguous imported symbol "
                    f"(from modules '{modules_str}')",
                )

        local[name] = typ
        self._alive_scopes[-1][name] = True
        return None

    def _lookup_local(self, name: str) -> Optional[Type]:
        """Look up a local variable's type in the scope stack."""
        for scope in reversed(self._local_scopes):
            if name in scope:
                return scope[name]
        return None

    def _lookup_local_scope_index(self, name: str) -> Optional[int]:
        """Return scope index where local resolves (nearest scope wins)."""
        for idx in range(len(self._local_scopes) - 1, -1, -1):
            if name in self._local_scopes[idx]:
                return idx
        return None

    def _is_guarded_cleanup_header_ref(self, name: str, scope_index: int) -> bool:
        """True when a local resolves to a guarded maybe-uninitialized header let."""
        for header_scope_index, guarded_names in reversed(self._cleanup_header_ref_guard_stack):
            if scope_index == header_scope_index and name in guarded_names:
                return True
        return False

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

    def _lookup_alive(self, name: str) -> Optional[bool]:
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

    def _clone_alive_scopes(self) -> List[Dict[str, bool]]:
        """Clone the current definite-liveness stack."""
        return [dict(scope) for scope in self._alive_scopes]

    def _meet_alive_scopes(self, *states: List[Dict[str, bool]]) -> None:
        """Keep a binding alive only when every incoming state keeps it alive."""
        self._alive_scopes = self._meet_alive_state(*states)

    def _meet_alive_state(self, *states: List[Dict[str, bool]]) -> List[Dict[str, bool]]:
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

    def _check_dead_liveness_block(self, block: Block, *, check_return_paths: bool) -> StmtFlow:
        """Type-check an unreachable branch without exporting liveness or loop exits."""
        saved_alive = self._clone_alive_scopes()
        saved_unreachable = self._next_stmt_unreachable
        saved_return_paths = self._return_paths
        saved_capture_stack = self._loop_flow_capture_stack
        saved_suppress_liveness = self._suppress_liveness_diagnostics
        self._next_stmt_unreachable = False
        self._loop_flow_capture_stack = []
        self._suppress_liveness_diagnostics = True
        try:
            return self._check_block(block, check_return_paths=check_return_paths, push_new_scope=False)
        finally:
            self._alive_scopes = saved_alive
            self._next_stmt_unreachable = saved_unreachable
            self._return_paths = saved_return_paths
            self._loop_flow_capture_stack = saved_capture_stack
            self._suppress_liveness_diagnostics = saved_suppress_liveness

    def _check_update_from_backedge_states(
        self,
        update: Optional[Stmt],
        states: List[List[Dict[str, bool]]],
    ) -> List[List[Dict[str, bool]]]:
        """Check a for-update statement from all reachable body backedges."""
        if not states:
            if update is not None:
                saved_alive = self._clone_alive_scopes()
                saved_unreachable = self._next_stmt_unreachable
                self._next_stmt_unreachable = False
                self._check_stmt(update)
                self._alive_scopes = saved_alive
                self._next_stmt_unreachable = saved_unreachable
            return []
        if update is None:
            return [[dict(scope) for scope in state] for state in states]

        self._alive_scopes = self._meet_alive_state(*states)
        update_flow = self._check_stmt(update)
        if update_flow is StmtFlow.FALLTHROUGH:
            return [self._clone_alive_scopes()]
        return []

    def _check_loop_iteration(
        self,
        body: Block,
        *,
        cond: Optional[Expr] = None,
        update: Optional[Stmt] = None,
        check_return_paths: bool = False,
    ) -> Tuple[LoopFlowCapture, List[List[Dict[str, bool]]], StmtFlow]:
        """Check one loop iteration and return captured flow states."""
        if cond is not None:
            self._infer_expr(cond)

        capture = LoopFlowCapture()
        self._loop_flow_capture_stack.append(capture)
        self._breakable_loop_depth += 1
        try:
            body_flow = self._check_block(body, check_return_paths=check_return_paths)
        finally:
            self._breakable_loop_depth -= 1
            self._loop_flow_capture_stack.pop()

        backedge_states = [[dict(scope) for scope in state] for state in capture.continue_states]
        if body_flow is StmtFlow.FALLTHROUGH:
            backedge_states.append(self._clone_alive_scopes())
        backedge_states = self._check_update_from_backedge_states(update, backedge_states)
        return capture, backedge_states, body_flow

    def _loop_liveness_fixed_point(
        self,
        pre_loop: List[Dict[str, bool]],
        body: Block,
        *,
        cond: Optional[Expr] = None,
        update: Optional[Stmt] = None,
    ) -> Tuple[List[Dict[str, bool]], LoopFlowCapture, List[List[Dict[str, bool]]]]:
        """Converge loop-head liveness and diagnose later-iteration uses."""
        head = self._clone_alive_scopes()
        saved_unreachable = self._next_stmt_unreachable
        while True:
            self._alive_scopes = [dict(scope) for scope in head]
            old_suppress = self._suppress_diagnostics
            self._suppress_diagnostics = True
            try:
                _, backedge_states, _ = self._check_loop_iteration(
                    body,
                    cond=cond,
                    update=update,
                )
            finally:
                self._suppress_diagnostics = old_suppress
                self._next_stmt_unreachable = saved_unreachable
            next_head = self._meet_alive_state(pre_loop, *backedge_states)
            if next_head == head:
                head = next_head
                break
            head = next_head

        self._alive_scopes = [dict(scope) for scope in head]
        old_liveness_only = self._liveness_diagnostics_only
        self._liveness_diagnostics_only = True
        try:
            capture, backedge_states, _ = self._check_loop_iteration(
                body,
                cond=cond,
                update=update,
            )
        finally:
            self._liveness_diagnostics_only = old_liveness_only
            self._next_stmt_unreachable = saved_unreachable
        self._alive_scopes = head
        return head, capture, backedge_states

    def _check_block(
        self,
        block: Block,
        *,
        check_return_paths: bool = False,
        push_new_scope: bool = True,
    ) -> StmtFlow:
        """Check a block of statements.

        Args:
            block: The Block node.
            check_return_paths: Whether to track return paths in this block.
            push_new_scope: Whether to push a new lexical scope for this block.
        """
        if push_new_scope:
            self._push_scope()
        try:
            unreachable_warning_issued = False
            guarantees_return = False
            block_flow = StmtFlow.FALLTHROUGH
            check_or_not = check_return_paths
            for stmt in block.stmts:
                unreachable_before_stmt = guarantees_return or self._next_stmt_unreachable
                pre_unreachable_alive = self._clone_alive_scopes()
                active_capture = self._loop_flow_capture_stack[-1] if self._loop_flow_capture_stack else None
                pre_break_count = len(active_capture.break_states) if active_capture is not None else 0
                pre_continue_count = len(active_capture.continue_states) if active_capture is not None else 0
                # Check for unreachable code after a guaranteed return
                if guarantees_return and not unreachable_warning_issued:
                    self._warn(stmt, "[TYP-0031] unreachable code after 'return'")
                    unreachable_warning_issued = True
                if self._next_stmt_unreachable and not unreachable_warning_issued:
                    self._warn(stmt, "[TYP-0030] unreachable code")
                    unreachable_warning_issued = True
                # Check the statement
                stmt_flow = self._check_stmt(stmt, check_return_paths=check_or_not)
                if unreachable_before_stmt:
                    self._alive_scopes = pre_unreachable_alive
                    if active_capture is not None:
                        del active_capture.break_states[pre_break_count:]
                        del active_capture.continue_states[pre_continue_count:]
                    continue
                # Update return path tracking
                if check_return_paths:
                    guarantees_return = guarantees_return or self._return_paths
                    if guarantees_return:
                        check_or_not = False  # no need to check further statements
                if stmt_flow is StmtFlow.RETURNS:
                    block_flow = StmtFlow.RETURNS
                elif stmt_flow is StmtFlow.STOPS:
                    block_flow = StmtFlow.STOPS
                if stmt_flow is not StmtFlow.FALLTHROUGH:
                    self._next_stmt_unreachable = True

            if check_return_paths:
                self._return_paths = guarantees_return
            return block_flow
        finally:
            self._next_stmt_unreachable = False  # reset for outer scope
            if push_new_scope:
                self._pop_scope()

    def _check_stmt(self, stmt: Stmt, *, check_return_paths: bool = False) -> StmtFlow:
        """Check a single statement.

        Args:
            stmt: The Stmt node.
            check_return_paths: Whether to update return path tracking.
        """

        if check_return_paths:
            self._return_paths = False  # reset before checking this statement

        if isinstance(stmt, ReturnStmt):
            self._check_return(stmt)
            if check_return_paths:
                self._return_paths = True
            return StmtFlow.RETURNS

        if isinstance(stmt, ExprStmt):
            self._infer_expr(stmt.expr)
            return StmtFlow.FALLTHROUGH

        if isinstance(stmt, LetStmt):
            annot_ty = None  # type from annotation (if any)
            value_ty = None  # type from expression

            # Resolve annotation if present
            if stmt.type is not None:
                annot_ty = self._resolve_type_ref(stmt.type)
                if annot_ty is None:  # error in type ref
                    self._error(stmt.type, f"[TYP-0040] cannot resolve type annotation for variable '{stmt.name}'")
                    return StmtFlow.FALLTHROUGH
                if annot_ty is get_builtin_type("void"):
                    self._error(stmt, "[TYP-0050] variable cannot have type 'void'")
                    return StmtFlow.FALLTHROUGH
                # Infer initializer type in the context of annotation
                value_ty = self._infer_expr(stmt.value,
                                            widening_type=annot_ty,
                                            context_code="TYP-0310",
                                            context_descriptor=f"initializer for variable '{stmt.name}'")
                if value_ty is None:
                    # Error already reported by _infer_expr
                    return StmtFlow.FALLTHROUGH

            # When widening_type is provided, _infer_expr already checks compatibility
            if annot_ty is not None:
                self._declare_local(stmt.name, annot_ty, stmt)
                return StmtFlow.FALLTHROUGH

            # No annotation: infer from initializer
            value_ty = self._infer_expr(stmt.value, context_descriptor=f"initializer for variable '{stmt.name}'")

            # Type inference
            if value_ty is None:
                # Error in expression, can't infer (should have been reported already)
                self._error(stmt, f"[TYP-0051] initializer for '{stmt.name}' type mismatch")
                return StmtFlow.FALLTHROUGH
            elif isinstance(value_ty, NullType):
                self._error(stmt, "[TYP-0052] cannot infer type from 'null'; explicit type required")
                return StmtFlow.FALLTHROUGH
            elif self._is_void(value_ty):
                self._error(stmt.value, "[TYP-0053] initializer is 'void', cannot assign to variable")
                return StmtFlow.FALLTHROUGH
            else:
                self._declare_local(stmt.name, value_ty, stmt)

            return StmtFlow.FALLTHROUGH

        if isinstance(stmt, AssignStmt):
            # A bare assignment target may revive a dropped variable, but the
            # old value remains dead while the RHS is evaluated.
            prior_alive = None
            if isinstance(stmt.target, VarRef):
                prior_alive = self._lookup_alive(stmt.target.name)
                self._set_alive(stmt.target.name, True)

            # Infer target type first, then use it as context for value
            target_ty = self._infer_expr(stmt.target)

            if isinstance(stmt.target, VarRef) and prior_alive is not None:
                self._set_alive(stmt.target.name, prior_alive)

            if target_ty is not None:
                # Use target type as widening context for the value
                value_ty = self._infer_expr(
                    stmt.value,
                    widening_type=target_ty,
                    context_code="TYP-0311",
                    context_descriptor=f"assignment to {self._describe_lvalue(stmt.target)}",
                )
            else:
                # Target type inference failed, still check value for errors
                value_ty = self._infer_expr(stmt.value)

            if isinstance(stmt.target, VarRef) and value_ty is not None:
                self._set_alive(stmt.target.name, True)

            return StmtFlow.FALLTHROUGH

        if isinstance(stmt, DropStmt):
            var_ty = self._lookup_local(stmt.name)
            if var_ty is None:
                assert self._current_func_env is not None
                sym_result = resolve_symbol(
                    self.module_envs,
                    self._current_func_env.module_name,
                    stmt.name,
                )
                if sym_result.symbol is not None and sym_result.symbol.kind is SymbolKind.LET:
                    self._error(stmt, f"[TYP-0063] cannot drop module-level let '{stmt.name}'")
                    return StmtFlow.FALLTHROUGH
                self._error(stmt, f"[TYP-0060] unknown variable '{stmt.name}'")
                return StmtFlow.FALLTHROUGH

            is_ptr = isinstance(var_ty, PointerType)
            is_opt_ptr = isinstance(var_ty, NullableType) and isinstance(var_ty.inner, PointerType)
            if not (is_ptr or is_opt_ptr):
                self._error(stmt, f"[TYP-0061] cannot drop non-pointer type '{format_type(var_ty)}'")
                return StmtFlow.FALLTHROUGH

            alive = self._lookup_alive(stmt.name)
            if alive is False:
                self._error(stmt, f"[TYP-0062] use of dropped variable '{stmt.name}'")
                return StmtFlow.FALLTHROUGH

            self._set_alive(stmt.name, False)
            return StmtFlow.FALLTHROUGH

        if isinstance(stmt, IfStmt):
            cond_ty = self._infer_expr(stmt.cond, context_descriptor="condition in if statement")

            if cond_ty is not None and not self._is_bool(cond_ty):
                self._error(stmt, "[TYP-0070] if condition must have type 'bool'")

            pre_unreachable = self._next_stmt_unreachable
            pre_alive = [dict(scope) for scope in self._alive_scopes]

            # then branch
            self._next_stmt_unreachable = False
            then_flow = self._check_stmt(stmt.then_stmt, check_return_paths=check_return_paths)
            then_alive = [dict(scope) for scope in self._alive_scopes]
            then_returns = self._return_paths
            then_unreachable = self._next_stmt_unreachable

            # else branch
            else_returns = False
            else_unreachable = False
            else_flow = StmtFlow.FALLTHROUGH
            fallthrough_states: List[List[Dict[str, bool]]] = []
            if then_flow is StmtFlow.FALLTHROUGH:
                fallthrough_states.append(then_alive)
            if stmt.else_stmt is not None:
                # Restore pre-if liveness
                self._alive_scopes = [dict(scope) for scope in pre_alive]
                self._next_stmt_unreachable = False
                else_flow = self._check_stmt(stmt.else_stmt, check_return_paths=check_return_paths)
                else_alive = [dict(scope) for scope in self._alive_scopes]
                else_returns = self._return_paths
                else_unreachable = self._next_stmt_unreachable
                if else_flow is StmtFlow.FALLTHROUGH:
                    fallthrough_states.append(else_alive)
            else:
                # Without an else, the false branch falls through unchanged.
                fallthrough_states.append(pre_alive)

            if fallthrough_states:
                self._alive_scopes = self._meet_alive_state(*fallthrough_states)
                stmt_flow = StmtFlow.FALLTHROUGH
            elif then_flow is StmtFlow.RETURNS and else_flow is StmtFlow.RETURNS:
                self._alive_scopes = [dict(scope) for scope in pre_alive]
                stmt_flow = StmtFlow.RETURNS
            else:
                self._alive_scopes = [dict(scope) for scope in pre_alive]
                stmt_flow = StmtFlow.STOPS

            if check_return_paths:
                # An if-else guarantees a return only if BOTH branches do.
                # An if without an else never guarantees a return.
                self._return_paths = then_returns and else_returns

            if pre_unreachable:
                self._next_stmt_unreachable = True
            elif stmt.else_stmt is not None:
                self._next_stmt_unreachable = then_unreachable and else_unreachable
            else:
                self._next_stmt_unreachable = False

            return stmt_flow

        if isinstance(stmt, WhileStmt):
            cond_ty = self._infer_expr(stmt.cond, context_descriptor="condition in while loop")
            if cond_ty is not None and not self._is_bool(cond_ty):
                self._error(stmt, "[TYP-0080] while condition must have type 'bool'")

            pre_alive = self._clone_alive_scopes()
            capture, backedge_states, _ = self._check_loop_iteration(
                stmt.body,
                cond=stmt.cond,
                check_return_paths=check_return_paths,
            )
            next_head = self._meet_alive_state(pre_alive, *backedge_states)
            if next_head != pre_alive:
                _, capture, backedge_states = self._loop_liveness_fixed_point(
                    pre_alive,
                    stmt.body,
                    cond=stmt.cond,
                )
            after_states = [pre_alive, *capture.break_states, *backedge_states]
            self._alive_scopes = self._meet_alive_state(*after_states)
            if check_return_paths:
                self._return_paths = False
            return StmtFlow.FALLTHROUGH

        if isinstance(stmt, ForStmt):
            self._push_scope()
            try:
                init_returns = False
                init_flow = StmtFlow.FALLTHROUGH
                if stmt.init:
                    init_flow = self._check_stmt(stmt.init, check_return_paths=check_return_paths)
                    init_returns = self._return_paths if check_return_paths else False

                if stmt.cond:
                    cond_ty = self._infer_expr(stmt.cond)
                    if cond_ty is not None and not self._is_bool(cond_ty):
                        self._error(stmt, "[TYP-0090] for loop condition must have type 'bool'")

                pre_loop_alive = self._clone_alive_scopes()
                if init_flow is not StmtFlow.FALLTHROUGH:
                    active_capture = self._loop_flow_capture_stack[-1] if self._loop_flow_capture_stack else None
                    pre_break_count = len(active_capture.break_states) if active_capture is not None else 0
                    pre_continue_count = len(active_capture.continue_states) if active_capture is not None else 0
                    saved_unreachable = self._next_stmt_unreachable
                    try:
                        self._next_stmt_unreachable = False
                        self._check_loop_iteration(
                            stmt.body,
                            cond=stmt.cond,
                            update=stmt.update,
                            check_return_paths=False,
                        )
                    finally:
                        self._alive_scopes = [dict(scope) for scope in pre_loop_alive]
                        self._next_stmt_unreachable = saved_unreachable
                        if active_capture is not None:
                            del active_capture.break_states[pre_break_count:]
                            del active_capture.continue_states[pre_continue_count:]
                    if check_return_paths:
                        self._return_paths = init_returns
                    return init_flow

                capture, backedge_states, _ = self._check_loop_iteration(
                    stmt.body,
                    cond=stmt.cond,
                    update=stmt.update,
                    check_return_paths=check_return_paths,
                )
                next_head = self._meet_alive_state(pre_loop_alive, *backedge_states)
                if next_head != pre_loop_alive:
                    _, capture, backedge_states = self._loop_liveness_fixed_point(
                        pre_loop_alive,
                        stmt.body,
                        cond=stmt.cond,
                        update=stmt.update,
                    )
                after_states = [pre_loop_alive, *capture.break_states, *backedge_states]
                self._alive_scopes = self._meet_alive_state(*after_states)
                if check_return_paths:
                    self._return_paths = init_returns
                return StmtFlow.FALLTHROUGH
            finally:
                self._pop_scope()

        if isinstance(stmt, CaseStmt):
            scrutinee_ty = self._infer_expr(stmt.expr)
            allowed_case_types = {"int", "byte", "bool", "string"}

            if not (isinstance(scrutinee_ty, BuiltinType) and scrutinee_ty.name in allowed_case_types):
                self._error(
                    stmt,
                    f"[TYP-0106] 'case' scrutinee must have type 'int', 'byte', 'bool', or 'string', "
                    f"got '{format_type(scrutinee_ty)}'",
                )
                scrutinee_ty = None

            seen_literals: Dict[object, Expr] = {}
            all_arms_return = len(stmt.arms) + (1 if stmt.else_arm is not None else 0) > 0
            pre_case_alive = self._clone_alive_scopes()
            pre_case_unreachable = self._next_stmt_unreachable
            pre_case_return_paths = self._return_paths
            fallthrough_states: List[List[Dict[str, bool]]] = []

            for arm in stmt.arms:
                literal_info = self._case_literal_info(arm.literal)
                if literal_info is None:
                    self._error(arm, "[TYP-0107] 'case' arm literal must be int, byte, bool, or string")
                else:
                    literal_ty, literal_value = literal_info
                    if scrutinee_ty is not None and literal_ty != scrutinee_ty:
                        self._error(
                            arm.literal,
                            f"[TYP-0107] 'case' arm literal type '{format_type(literal_ty)}' "
                            f"does not match scrutinee type '{format_type(scrutinee_ty)}'",
                        )
                    else:
                        if literal_value in seen_literals:
                            self._error(
                                arm.literal,
                                "[TYP-0108] duplicate literal value in 'case' statement",
                            )
                        else:
                            seen_literals[literal_value] = arm.literal

                self._alive_scopes = [dict(scope) for scope in pre_case_alive]
                self._next_stmt_unreachable = False
                self._return_paths = False
                arm_flow = StmtFlow.FALLTHROUGH
                self._push_scope()
                try:
                    check_or_not = check_return_paths
                    if isinstance(arm.body, Block):
                        arm_flow = self._check_block(arm.body, check_return_paths=check_or_not, push_new_scope=False)
                    else:
                        arm_flow = self._check_stmt(arm.body, check_return_paths=check_or_not)
                    this_arm_returns = arm_flow is StmtFlow.RETURNS
                    all_arms_return = all_arms_return and this_arm_returns
                finally:
                    self._pop_scope()
                if arm_flow is StmtFlow.FALLTHROUGH:
                    fallthrough_states.append(self._clone_alive_scopes())

            else_arm_flow = StmtFlow.FALLTHROUGH
            if stmt.else_arm is not None:
                self._alive_scopes = [dict(scope) for scope in pre_case_alive]
                self._next_stmt_unreachable = False
                self._return_paths = False
                else_arm_flow = StmtFlow.FALLTHROUGH
                self._push_scope()
                try:
                    check_or_not = check_return_paths
                    if isinstance(stmt.else_arm.body, Block):
                        else_arm_flow = self._check_block(
                            stmt.else_arm.body,
                            check_return_paths=check_or_not,
                            push_new_scope=False,
                        )
                    else:
                        else_arm_flow = self._check_stmt(stmt.else_arm.body, check_return_paths=check_or_not)
                    this_arm_returns = else_arm_flow is StmtFlow.RETURNS
                    all_arms_return = all_arms_return and this_arm_returns
                finally:
                    self._pop_scope()
                if else_arm_flow is StmtFlow.FALLTHROUGH:
                    fallthrough_states.append(self._clone_alive_scopes())
            else:
                fallthrough_states.append([dict(scope) for scope in pre_case_alive])

            if check_return_paths:
                self._return_paths = stmt.else_arm is not None and all_arms_return
            else:
                self._return_paths = pre_case_return_paths

            if stmt.else_arm is not None and all_arms_return:
                self._alive_scopes = [dict(scope) for scope in pre_case_alive]
                self._next_stmt_unreachable = pre_case_unreachable
                return StmtFlow.RETURNS
            if fallthrough_states:
                self._alive_scopes = self._meet_alive_state(*fallthrough_states)
                self._next_stmt_unreachable = pre_case_unreachable
                return StmtFlow.FALLTHROUGH
            self._alive_scopes = [dict(scope) for scope in pre_case_alive]
            self._next_stmt_unreachable = pre_case_unreachable
            return StmtFlow.STOPS

        if isinstance(stmt, MatchStmt):
            # Type the scrutinee
            scrutinee_ty = self._infer_expr(stmt.expr)

            if not isinstance(scrutinee_ty, EnumType):
                self._error(stmt, f"[TYP-0100] match expression must have enum type, got '{format_type(scrutinee_ty)}'")
                return StmtFlow.FALLTHROUGH

            enum_info = self.enum_infos.get((scrutinee_ty.module, scrutinee_ty.name))
            defined_variants = set(enum_info.variants.keys()) if enum_info is not None else set()
            explicit_variants = {
                arm.pattern.name for arm in stmt.arms if isinstance(arm.pattern, VariantPattern)
            }
            wildcard_is_unreachable = enum_info is not None and explicit_variants == defined_variants
            reachable_arm_count = sum(
                not (isinstance(arm.pattern, WildcardPattern) and wildcard_is_unreachable)
                for arm in stmt.arms
            )
            all_arms_return = reachable_arm_count > 0
            pre_match_alive = self._clone_alive_scopes()
            pre_match_unreachable = self._next_stmt_unreachable
            fallthrough_states: List[List[Dict[str, bool]]] = []

            # Check each arm with pattern variables in scope
            for arm in stmt.arms:
                assert isinstance(arm, MatchArm)

                self._alive_scopes = [dict(scope) for scope in pre_match_alive]
                self._next_stmt_unreachable = False
                self._return_paths = False

                # Push a new scope for this arm
                self._push_scope()
                arm_flow = StmtFlow.FALLTHROUGH
                arm_is_reachable = not (
                    isinstance(arm.pattern, WildcardPattern) and wildcard_is_unreachable
                )
                try:
                    # Bind pattern variables if this is a variant pattern
                    if isinstance(arm.pattern, VariantPattern) and isinstance(scrutinee_ty, EnumType):
                        invalid_variant = False
                        if self._reject_name_qualifier(
                                arm.pattern, arm.pattern.name,
                                arm.pattern.name_qualifier, arm.pattern.module_path
                        ):
                            invalid_variant = True
                        elif arm.pattern.module_path is not None:
                            assert self._current_func_env is not None
                            module_name = self._current_func_env.module_name
                            sym_result = resolve_symbol(
                                self.module_envs,
                                module_name,
                                arm.pattern.name,
                                module_path=arm.pattern.module_path,
                            )
                            sym = sym_result.symbol
                            qualified = f"{'.'.join(arm.pattern.module_path)}::{arm.pattern.name}"
                            if sym is None:
                                if sym_result.error is ResolveErrorKind.UNKNOWN_MODULE:
                                    self._error(
                                        arm.pattern,
                                        f"[TYP-0102] unknown variant '{qualified}' for enum '{format_type(scrutinee_ty)}'"
                                        f" (unknown module '{sym_result.module_name}')",
                                    )
                                elif sym_result.error is ResolveErrorKind.MODULE_NOT_IMPORTED:
                                    self._error(
                                        arm.pattern,
                                        f"[TYP-0102] unknown variant '{qualified}' for enum '{format_type(scrutinee_ty)}'"
                                        f" (module '{sym_result.module_name}' not imported)",
                                    )
                                else:
                                    self._error(
                                        arm.pattern,
                                        f"[TYP-0102] unknown variant '{qualified}' for enum '{format_type(scrutinee_ty)}'",
                                    )
                                invalid_variant = True
                            elif sym.kind is not SymbolKind.ENUM_VARIANT:
                                self._error(
                                    arm.pattern,
                                    f"[TYP-0102] unknown variant '{qualified}' for enum '{format_type(scrutinee_ty)}'",
                                )
                                invalid_variant = True
                            elif sym.module.name != scrutinee_ty.module:
                                self._error(
                                    arm.pattern,
                                    f"[TYP-0102] unknown variant '{qualified}' for enum '{format_type(scrutinee_ty)}'",
                                )
                                invalid_variant = True

                        # Look up the enum and variant info
                        enum_info = self.enum_infos.get((scrutinee_ty.module, scrutinee_ty.name))
                        if enum_info and not invalid_variant:
                            variant_info = enum_info.variants.get(arm.pattern.name)
                            if variant_info:
                                # Check arity matches
                                if len(arm.pattern.vars) == len(variant_info.field_types):
                                    # Bind each pattern variable to its field type
                                    for var_name, field_type in zip(arm.pattern.vars, variant_info.field_types):
                                        self._declare_local(var_name, field_type, arm)
                                else:
                                    self._error(
                                        arm.pattern,
                                        f"[TYP-0101] pattern variable count mismatch: variant '{arm.pattern.name}' "
                                        f"has {len(variant_info.field_types)} fields but pattern has "
                                        f"{len(arm.pattern.vars)} variables"
                                    )
                            else:
                                self._error(
                                    arm.pattern,
                                    f"[TYP-0102] unknown variant '{arm.pattern.name}' for enum '{format_type(scrutinee_ty)}'"
                                )

                    # Check the arm body with pattern variables in scope
                    # Don't call _check_block because it would push another scope
                    check_or_not = check_return_paths
                    if arm_is_reachable:
                        arm_flow = self._check_block(arm.body, check_return_paths=check_or_not, push_new_scope=False)
                        all_arms_return = all_arms_return and arm_flow is StmtFlow.RETURNS
                    else:
                        arm_flow = self._check_dead_liveness_block(
                            arm.body,
                            check_return_paths=check_or_not,
                        )

                finally:
                    self._pop_scope()
                if arm_is_reachable and arm_flow is StmtFlow.FALLTHROUGH:
                    fallthrough_states.append(self._clone_alive_scopes())

            if not enum_info:
                self._error(stmt, f"[TYP-0103] no type information for enum '{format_type(scrutinee_ty)}'")
                self._alive_scopes = [dict(scope) for scope in pre_match_alive]
                self._next_stmt_unreachable = pre_match_unreachable
                return StmtFlow.FALLTHROUGH

            # check that all variants are covered (or wildcard present)
            arm_variants = set(arm.pattern.name for arm in stmt.arms if isinstance(arm.pattern, VariantPattern))
            is_wildcard_present = any(isinstance(arm.pattern, WildcardPattern) for arm in stmt.arms)
            is_exhaustive = is_wildcard_present
            if not is_wildcard_present:
                if arm_variants == defined_variants:
                    is_exhaustive = True
                else:
                    missing_variants = defined_variants - arm_variants
                    self._error(
                        stmt,
                        f"[TYP-0104] non-exhaustive match: missing variants ("
                        f"{', '.join(missing_variants)}) for enum '{format_type(scrutinee_ty)}'"
                    )
            elif len(arm_variants) == len(enum_info.variants):
                # wildcard is a no-op if all variants are already covered
                self._warn(stmt,
                           f"[TYP-0105] unreachable wildcard pattern in match: all variants of "
                           f"enum '{format_type(scrutinee_ty)}' are already covered")

            if check_return_paths:
                # A match guarantees a return if it is exhaustive AND all arms return.
                self._return_paths = is_exhaustive and all_arms_return

            if not is_exhaustive:
                fallthrough_states.append([dict(scope) for scope in pre_match_alive])

            if is_exhaustive and all_arms_return:
                self._alive_scopes = [dict(scope) for scope in pre_match_alive]
                self._next_stmt_unreachable = pre_match_unreachable
                return StmtFlow.RETURNS
            if fallthrough_states:
                self._alive_scopes = self._meet_alive_state(*fallthrough_states)
                stmt_flow = StmtFlow.FALLTHROUGH
            else:
                self._alive_scopes = [dict(scope) for scope in pre_match_alive]
                stmt_flow = StmtFlow.STOPS
            self._next_stmt_unreachable = pre_match_unreachable
            return stmt_flow

        if isinstance(stmt, WithStmt):
            # Type-check items sequentially in a new scope
            self._push_scope()
            try:
                seen_header_try = False
                maybe_uninit_nonnullable: Set[str] = set()
                header_returns = False

                for item_index, item in enumerate(stmt.items):
                    init_has_try = self._stmt_contains_try(item.init)
                    self._check_stmt(item.init, check_return_paths=check_return_paths)

                    if check_return_paths and isinstance(item.init, ReturnStmt):
                        override = None
                        if stmt.cleanup_body is None:
                            for registered in reversed(stmt.items[:item_index + 1]):
                                cleanup = registered.cleanup
                                if isinstance(cleanup, ReturnStmt):
                                    override = "return"
                                    break
                                if isinstance(cleanup, (BreakStmt, ContinueStmt)):
                                    override = "loop"
                                    break
                        header_returns = override != "loop"

                    if init_has_try:
                        seen_header_try = True

                    if isinstance(item.init, LetStmt):
                        # If any prior (or current) header init can short-circuit via `?`,
                        # this let may be uninitialized along that failure path.
                        if seen_header_try:
                            let_ty = self._local_scopes[-1].get(item.init.name)
                            if let_ty is not None and not isinstance(let_ty, NullableType):
                                maybe_uninit_nonnullable.add(item.init.name)

                # Body in a nested scope
                body_flow = self._check_block(stmt.body, check_return_paths=check_return_paths)
                body_returns = self._return_paths if check_return_paths else False

                # Inline cleanups (=>) in reverse order (LIFO), only if reachable.
                inline_override = None
                for item in reversed(stmt.items):
                    if item.cleanup is not None:
                        cleanup_flow = self._check_stmt(item.cleanup, check_return_paths=check_return_paths)
                        if inline_override is None:
                            if cleanup_flow is StmtFlow.RETURNS:
                                inline_override = "return"
                            elif cleanup_flow is StmtFlow.STOPS:
                                inline_override = "loop"

                # Cleanup body in the item scope (not body scope)
                cleanup_body_returns = False
                cleanup_body_flow = StmtFlow.FALLTHROUGH
                if stmt.cleanup_body is not None:
                    header_scope_index = len(self._local_scopes) - 1
                    self._cleanup_header_ref_guard_stack.append((header_scope_index, maybe_uninit_nonnullable))
                    try:
                        cleanup_body_flow = self._check_block(
                            stmt.cleanup_body,
                            check_return_paths=check_return_paths,
                        )
                        cleanup_body_returns = self._return_paths if check_return_paths else False
                    finally:
                        self._cleanup_header_ref_guard_stack.pop()

                with_returns = False
                if check_return_paths:
                    if cleanup_body_returns or inline_override == "return":
                        self._return_paths = True
                        with_returns = True
                    elif inline_override == "loop":
                        self._return_paths = False
                    else:
                        self._return_paths = header_returns or body_returns
                        with_returns = self._return_paths
                elif cleanup_body_flow is StmtFlow.RETURNS or inline_override == "return":
                    with_returns = True
                elif inline_override is None and body_flow is StmtFlow.RETURNS:
                    with_returns = True

                if with_returns:
                    return StmtFlow.RETURNS
                if inline_override == "loop" or cleanup_body_flow is StmtFlow.STOPS:
                    return StmtFlow.STOPS
                return StmtFlow.FALLTHROUGH
            finally:
                self._pop_scope()

        # Handle standalone block statements (nested blocks)
        if isinstance(stmt, Block):
            return self._check_block(stmt, check_return_paths=check_return_paths)

        if isinstance(stmt, BreakStmt):
            if self._breakable_loop_depth < 1:
                self._error(stmt, "[TYP-0110] 'break' statement not within a loop")
                return StmtFlow.FALLTHROUGH
            else:
                if self._loop_flow_capture_stack:
                    self._loop_flow_capture_stack[-1].break_states.append(self._clone_alive_scopes())
                self._next_stmt_unreachable = True
            return StmtFlow.STOPS

        if isinstance(stmt, ContinueStmt):
            if self._breakable_loop_depth < 1:
                self._error(stmt, "[TYP-0120] 'continue' statement not within a loop")
                return StmtFlow.FALLTHROUGH
            else:
                if self._loop_flow_capture_stack:
                    self._loop_flow_capture_stack[-1].continue_states.append(self._clone_alive_scopes())
                self._next_stmt_unreachable = True
            return StmtFlow.STOPS

        # Unknown (should not happen if AST is well-formed)
        self._error(stmt, f"[TYP-0139] unknown statement type: {type(stmt).__name__}")
        return StmtFlow.FALLTHROUGH

    # ------------------------------------------------------------------
    # Expression typing
    # ------------------------------------------------------------------

    def _infer_type_expr(self, expr: TypeExpr) -> Optional[Type]:
        """TypeExpr is only valid as an argument to type-accepting intrinsics."""
        self._error(expr,
                    "[TYP-0290] type expression is only valid as argument to type-accepting intrinsics such as 'sizeof'")
        return None

    def _infer_expr(self, expr: Optional[Expr], *,
                    widening_type: Optional[Type] = None,
                    context_code: str = "TYP-0319",
                    context_descriptor: str = "expression") -> Optional[Type]:
        """Infer the type of an expression.

        Args:
            expr: The expression to type-check.
            widening_type: Optional expected type for context-sensitive checking.
            context_code: Diagnostic code for type mismatch.
            context_descriptor: Description of context for diagnostic.

        Returns:
            The resolved Type of the expression, or None on error.
        """
        if expr is None:
            return self._error(Expr(), "[TYP-0149] cannot infer type of None expression")

        # Memoization is safe for types, but a settled-loop diagnostic pass must
        # revisit variable references under the converged liveness state.
        existing = self.expr_types.get(id(expr))
        if existing is not None and not self._liveness_diagnostics_only:
            return existing

        result: Optional[Type]

        if isinstance(expr, IntLiteral):
            result = self.int_type

        elif isinstance(expr, ByteLiteral):
            result = self.byte_type

        elif isinstance(expr, StringLiteral):
            result = self.string_type

        elif isinstance(expr, BoolLiteral):
            result = self.bool_type

        elif isinstance(expr, NullLiteral):
            result = self.null_type

        elif isinstance(expr, VarRef):
            result = self._infer_var_ref(expr)

        elif isinstance(expr, UnaryOp):
            result = self._infer_unary(expr)

        elif isinstance(expr, BinaryOp):
            result = self._infer_binary(expr)

        elif isinstance(expr, CallExpr):
            result = self._infer_call(expr)

        elif isinstance(expr, IndexExpr):
            result = self._infer_index(expr)

        elif isinstance(expr, FieldAccessExpr):
            result = self._infer_field_access(expr)

        elif isinstance(expr, ParenExpr):
            result = self._infer_expr(expr.inner)

        elif isinstance(expr, CastExpr):
            result = self._infer_cast(expr)

        elif isinstance(expr, NewExpr):
            result = self._infer_new(expr)

        elif isinstance(expr, TypeExpr):
            return self._infer_type_expr(expr)

        elif isinstance(expr, TryExpr):
            result = self._infer_try(expr)

        else:
            result = None

        if result is not None:
            self.expr_types[id(expr)] = result  # Always store natural type

        if result is not None and widening_type is not None:
            # Check widening if provided from context
            # (e.g., assignment target, struct field, function arg, etc.)
            if not self._can_assign(widening_type, result):
                return self._error(
                    expr,
                    f"[{context_code}] {context_descriptor} type mismatch: "
                    f"expected '{format_type(widening_type)}', got '{format_type(result)}'",
                )

        return result

    def _infer_var_ref(self, expr: VarRef) -> Optional[Type]:
        """Infer type for a variable reference."""
        # Reject overqualified names early (e.g. color::Color::Red)
        if self._reject_name_qualifier(expr, expr.name, expr.name_qualifier, expr.module_path):
            return None

        # 1. Locals / parameters
        if expr.module_path is None:
            local_scope_idx = self._lookup_local_scope_index(expr.name)
            if local_scope_idx is not None:
                local_ty = self._local_scopes[local_scope_idx][expr.name]
                self.analysis.var_ref_resolution[id(expr)] = VarRefResolution.LOCAL
                if self._is_guarded_cleanup_header_ref(expr.name, local_scope_idx):
                    self._error(
                        expr,
                        f"[TYP-0156] 'cleanup' block references 'with' header variable '{expr.name}' "
                        f"that may be uninitialized on '?' header-failure path; "
                        f"use nullable type or inline '=>' cleanup"
                    )
                alive = self._lookup_alive(expr.name)
                if alive is False:
                    self._error(expr, f"[TYP-0150] use of dropped variable '{expr.name}'")
                return local_ty

        # 2. Module-level symbols (functions only, for now)
        assert self._current_func_env is not None
        module_name = self._current_func_env.module_name

        sym_result = resolve_symbol(self.module_envs, module_name, expr.name, module_path=expr.module_path)
        sym = sym_result.symbol
        if sym is None:
            qualified_name = (
                f"{'.'.join(expr.module_path)}::{expr.name}"
                if expr.module_path
                else expr.name
            )
            if sym_result.error is ResolveErrorKind.UNKNOWN_MODULE:
                self._error(
                    expr,
                    f"[TYP-0153] unknown identifier '{qualified_name}' (unknown module '{sym_result.module_name}')",
                )
            elif sym_result.error is ResolveErrorKind.MODULE_NOT_IMPORTED:
                self._error(
                    expr,
                    f"[TYP-0154] unknown identifier '{qualified_name}' (module '{sym_result.module_name}' not imported)",
                )
            elif sym_result.error is ResolveErrorKind.AMBIGUOUS_SYMBOL:
                modules_str = "', '".join(sym_result.ambiguous_modules)
                hints = " or ".join(f"'{m}::{expr.name}'" for m in sym_result.ambiguous_modules)
                self._error(
                    expr,
                    f"[TYP-0155] ambiguous identifier '{expr.name}' (imported from modules '{modules_str}'); "
                    f"use {hints} to disambiguate",
                )
            else:
                self._error(expr, f"[TYP-0159] unknown identifier '{qualified_name}'")
            return None

        if sym.kind is SymbolKind.FUNC and sym.type is not None:
            # Functions have a FuncType
            self.analysis.var_ref_resolution[id(expr)] = VarRefResolution.MODULE
            return sym.type

        if sym.kind is SymbolKind.LET and sym.type is not None:
            # Top-level let bindings have their resolved type
            self.analysis.var_ref_resolution[id(expr)] = VarRefResolution.MODULE
            return sym.type

        # Zero-arg enum variants can be used as bare identifiers (e.g. `Red` instead of `Red()`).
        if sym.kind is SymbolKind.ENUM_VARIANT and isinstance(sym.type, FuncType):
            self.analysis.var_ref_resolution[id(expr)] = VarRefResolution.MODULE
            variant_type = sym.type
            if len(variant_type.params) == 0:
                enum_type = variant_type.result
                if isinstance(enum_type, EnumType):
                    return enum_type
            # Variant has payload fields — bare usage is an error.
            self._error(
                expr,
                f"[TYP-0152] variant '{expr.name}' requires arguments; use '{expr.name}(...)' constructor syntax",
            )
            return None

        # Struct, enum, and other type symbols are not values by themselves.
        self._error(expr, f"[TYP-0151] symbol '{expr.name}' is not a value")
        return None

    def _infer_unary(self, expr: UnaryOp) -> Optional[Type]:
        """Infer type for a unary operation."""
        op = expr.op
        operand_ty = self._infer_expr(expr.operand)

        # Unary minus: int -> int
        if op == "-":
            if self._is_int_assignable(operand_ty):
                return self.int_type
            if operand_ty is not None:
                self._error(
                    expr,
                    f"[TYP-0160] unary '-' expects operand of type 'int', got '{format_type(operand_ty)}'",
                )
            return None

        # Logical not: bool -> bool
        if op == "!":
            if self._is_bool(operand_ty):
                return self.bool_type
            if operand_ty is not None:
                self._error(
                    expr,
                    f"[TYP-0161] unary '!' expects operand of type 'bool', got '{format_type(operand_ty)}'",
                )
            return None

        # Dereference: T* -> T
        if op == "*":
            if isinstance(operand_ty, PointerType):
                return operand_ty.inner
            if operand_ty is not None:
                self._error(
                    expr,
                    f"[TYP-0162] cannot dereference expression of type '{format_type(operand_ty)}'; "
                    "expected a pointer type",
                )
            return None

        return operand_ty

    def _infer_binary(self, expr: BinaryOp) -> Optional[Type]:
        """Infer type for a binary operation."""
        op = expr.op
        left_ty = self._infer_expr(expr.left)
        right_ty = self._infer_expr(expr.right)

        # string + string -> string
        if op == "+" and self._is_string(left_ty) and self._is_string(right_ty):
            return self.string_type

        # Arithmetic int ops -> int
        if op in {"+", "-", "*", "/", "%"}:
            return self._binary_expect_both_int(expr, left_ty, right_ty, result=self.int_type)

        # Comparison ops -> bool. Accept ints (existing) or two strings (lexicographic).
        if op in {"<", "<=", ">", ">="}:
            if self._is_string(left_ty) and self._is_string(right_ty):
                return self.bool_type
            return self._binary_expect_both_int(expr, left_ty, right_ty, result=self.bool_type)

        # Equality: same-type operands OR null check -> bool
        if op in {"==", "!="}:
            return self._binary_equality(expr, left_ty, right_ty)

        # Logical bool ops -> bool
        if op in {"&&", "||"}:
            return self._binary_expect_both_bool(expr, left_ty, right_ty, result=self.bool_type)

        # Future: bitwise, etc.

        return None

    def _binary_expect_both_int(
            self, expr: BinaryOp, left: Optional[Type], right: Optional[Type], result: Optional[Type]
    ) -> Optional[Type]:
        """Check that both operands of a binary op are int-assignable."""
        if self._is_int_assignable(left) and self._is_int_assignable(right):
            return result
        if left is not None and right is not None:
            self._error(
                expr,
                f"[TYP-0170] operator '{expr.op}' expects operands of type 'int', got "
                f"'{format_type(left)}' and '{format_type(right)}'",
            )
        return None

    def _binary_expect_both_bool(
            self, expr: BinaryOp, left: Optional[Type], right: Optional[Type], result: Optional[Type]
    ) -> Optional[Type]:
        """Check that both operands of a binary op are bool."""
        if self._is_bool(left) and self._is_bool(right):
            return result
        if left is not None and right is not None:
            self._error(
                expr,
                f"[TYP-0171] operator '{expr.op}' expects operands of type 'bool', got "
                f"'{format_type(left)}' and '{format_type(right)}'",
            )
        return None

    def _binary_equality(
            self, expr: BinaryOp, left: Optional[Type], right: Optional[Type]
    ) -> Optional[Type]:
        """Infer type for equality/inequality comparison."""
        if left is None or right is None:
            return None

        # Check for null comparison: One side is NullType, other is Nullable/Ptr
        is_null_check = (
                (isinstance(left, NullType) and self._is_nullable_or_ptr(right)) or
                (isinstance(right, NullType) and self._is_nullable_or_ptr(left))
        )

        # If it's not a null check, enforce both sides have the same type (or compatible)
        if not is_null_check and not (self._can_assign(right, left) or self._can_assign(left, right)):
            self._error(
                expr,
                f"[TYP-0172] equality operator '{expr.op}' requires both operands to have the "
                f"same type (or be a valid null check), got '{format_type(left)}' and '{format_type(right)}'",
            )
            return None

        # Restrict what types can be compared for equality (int, bool, string).
        if not is_null_check and not (
                self._is_int_assignable(left) or self._is_bool(left) or self._is_string(left)
        ):
            self._error(
                expr,
                f"[TYP-0173] equality not supported for type '{format_type(left)}'",
            )
            return None

        return self.bool_type

    def _try_infer_intrinsic(self, expr: CallExpr) -> Optional[Type]:
        """Handle compiler intrinsics calls."""
        if not isinstance(expr.callee, VarRef):
            return None

        name = expr.callee.name

        if name == "sizeof":
            return self._infer_sizeof_intrinsic(expr)

        if name == "ord":
            return self._infer_ord_intrinsic(expr)

        # Not an intrinsic
        return None

    def _infer_sizeof_intrinsic(self, expr: CallExpr) -> Type:
        """Handle sizeof(T) or sizeof(expr) intrinsic."""
        if len(expr.args) != 1:
            self._error(expr, "[TYP-0241] sizeof expects exactly 1 argument")
            return self.int_type

        arg = expr.args[0]

        if isinstance(arg, TypeExpr):
            # sizeof(T) - direct type argument
            target_ty = self._resolve_type_ref(arg.type_ref)
            if target_ty is None:
                return self.int_type
            if self._is_void(target_ty):
                self._error(expr, "[TYP-0240] cannot take sizeof(void)")
            # Store resolved type for codegen
            self._store_sizeof_target(expr, target_ty)
            return self.int_type

        if isinstance(arg, VarRef):
            # Could be sizeof(TypeName) or sizeof(variable)
            # Try resolving as type first
            target_ty = self._try_resolve_type_name(arg.name, node=arg, module_path=arg.module_path)
            if target_ty is not None:
                if self._is_void(target_ty):
                    self._error(expr, "[TYP-0240] cannot take sizeof(void)")
                self._store_sizeof_target(expr, target_ty)
                return self.int_type

            # Fall through to treat as expression

        # sizeof(expr) - use expression's type
        arg_ty = self._infer_expr(arg)
        if arg_ty is None:
            return self.int_type
        if self._is_void(arg_ty):
            self._error(expr, "[TYP-0240] cannot take sizeof(void)")
        self._store_sizeof_target(expr, arg_ty)
        return self.int_type

    def _try_resolve_type_name(
            self,
            name: str,
            *,
            node: Optional[Node] = None,
            module_path: Optional[List[str]] = None,
    ) -> Optional[Type]:
        """Try to resolve an identifier as a type name."""
        assert self._current_func_env is not None
        module_name = self._current_func_env.module_name

        sym_result = resolve_symbol(self.module_envs, module_name, name, module_path=module_path)
        sym = sym_result.symbol
        if sym is None:
            if module_path and sym_result.error in (ResolveErrorKind.UNKNOWN_MODULE,
                                                    ResolveErrorKind.MODULE_NOT_IMPORTED):
                qualified_name = f"{'.'.join(module_path)}::{name}"
                if node is not None:
                    if sym_result.error is ResolveErrorKind.UNKNOWN_MODULE:
                        self._error(
                            node,
                            f"[TYP-0300] unknown type '{qualified_name}' (unknown module '{sym_result.module_name}')",
                        )
                    else:
                        self._error(
                            node,
                            f"[TYP-0301] unknown type '{qualified_name}' (module '{sym_result.module_name}' not imported)",
                        )
            elif sym_result.error is ResolveErrorKind.AMBIGUOUS_SYMBOL and node is not None:
                modules_str = "', '".join(sym_result.ambiguous_modules)
                hints = " or ".join(f"'{m}::{name}'" for m in sym_result.ambiguous_modules)
                self._error(
                    node,
                    f"[TYP-0303] ambiguous identifier '{name}' (imported from modules '{modules_str}'); "
                    f"use {hints} to disambiguate",
                )
            return None

        if sym.kind == SymbolKind.STRUCT:
            return StructType(module=sym.module.name, name=name)
        if sym.kind == SymbolKind.ENUM:
            return EnumType(module=sym.module.name, name=name)
        if sym.kind == SymbolKind.TYPE_ALIAS:
            # Prefer the resolved target type computed by SignatureResolver.
            if sym.type is not None:
                return sym.type

            # Graceful fallback: try resolving from the AST node if it is a TypeAliasDecl.
            # This shouldn't normally happen (pass ordering should resolve aliases first),
            # so we only log at debug level and avoid crashing.
            ctx = getattr(self.analysis, "context", None)
            if isinstance(sym.node, TypeAliasDecl):
                log_debug(
                    ctx,
                    f"Type alias '{name}' in module '{module_name}' was not resolved yet; falling back to decl.target",
                )
                return self._resolve_type_ref(sym.node.target)

            log_debug(
                ctx,
                f"TYPE_ALIAS symbol '{name}' in module '{module_name}' has unexpected node type "
                f"{type(sym.node).__name__}; treating as non-type",
            )
            return None

        return None

    def _store_sizeof_target(self, expr: CallExpr, target_ty: Type) -> None:
        """Store the resolved sizeof target type for codegen."""
        self.analysis.intrinsic_targets[id(expr)] = target_ty

    def _infer_ord_intrinsic(self, expr: CallExpr) -> Type:
        """Handle ord(enum_value) intrinsic - returns 0-based ordinal of enum variant."""
        if len(expr.args) != 1:
            self._error(expr, "[TYP-0242] ord expects exactly 1 argument")
            return self.int_type

        arg = expr.args[0]
        arg_ty = self._infer_expr(arg)

        if arg_ty is None:
            return self.int_type

        if not isinstance(arg_ty, EnumType):
            self._error(expr, f"[TYP-0243] ord expects an enum value, got '{format_type(arg_ty)}'")
            return self.int_type

        return self.int_type

    def _infer_call(self, expr: CallExpr) -> Optional[Type]:
        """Infer type for a function or constructor call."""
        # Check for intrinsic calls first
        if isinstance(expr.callee, VarRef):
            intrinsic_result = self._try_infer_intrinsic(expr)
            if intrinsic_result is not None:
                return intrinsic_result

        # Only allow calling plain identifiers.
        if not isinstance(expr.callee, VarRef):
            self._error(expr, "[TYP-0180] callee must be a function name")
            # Still traverse arguments to type-check them.
            for arg in expr.args:
                self._infer_expr(arg)
            return None

        # Reject overqualified callee names early (e.g. color::Color::Red(...))
        if isinstance(expr.callee, VarRef) and self._reject_name_qualifier(
                expr, expr.callee.name, expr.callee.name_qualifier, expr.callee.module_path
        ):
            return None

        assert self._current_func_env is not None
        module_name = self._current_func_env.module_name

        sym_result = resolve_symbol(self.module_envs, module_name, expr.callee.name,
                                    module_path=expr.callee.module_path)
        sym = sym_result.symbol
        if sym is None:
            qualified_name = (
                f"{'.'.join(expr.callee.module_path)}::{expr.callee.name}"
                if expr.callee.module_path
                else expr.callee.name
            )
            if sym_result.error is ResolveErrorKind.UNKNOWN_MODULE:
                self._error(
                    expr,
                    f"[TYP-0189] unknown identifier '{qualified_name}' (unknown module '{sym_result.module_name}')",
                )
            elif sym_result.error is ResolveErrorKind.MODULE_NOT_IMPORTED:
                self._error(
                    expr,
                    f"[TYP-0189] unknown identifier '{qualified_name}' (module '{sym_result.module_name}' not imported)",
                )
            elif sym_result.error is ResolveErrorKind.AMBIGUOUS_SYMBOL:
                modules_str = "', '".join(sym_result.ambiguous_modules)
                hints = " or ".join(f"'{m}::{expr.callee.name}'" for m in sym_result.ambiguous_modules)
                self._error(
                    expr,
                    f"[TYP-0189] ambiguous identifier '{expr.callee.name}' (imported from modules '{modules_str}'); "
                    f"use {hints} to disambiguate",
                )
            else:
                self._error(expr, f"[TYP-0189] unknown identifier '{qualified_name}'")
            return None

        # Handle struct constructors or type-alias-to-struct constructors
        if sym.kind is SymbolKind.STRUCT or (sym.kind is SymbolKind.TYPE_ALIAS and isinstance(sym.type, StructType)):
            return self._infer_struct_constructor(expr, sym)

        # Handle enum variant constructors
        if sym.kind is SymbolKind.ENUM_VARIANT:
            return self._infer_variant_constructor(expr, sym)

        # Handle regular function calls
        if sym.kind is not SymbolKind.FUNC:
            self._error(expr, f"[TYP-0181] symbol '{expr.callee.name}' is not callable")
            return None

        callee_ty = sym.type
        if not isinstance(callee_ty, FuncType):
            if callee_ty is not None:
                self._error(expr, "[TYP-0182] callee is not a function")
            return None

        # Arity check
        expected_arity = len(callee_ty.params)
        given_arity = len(expr.args)
        if expected_arity != given_arity:
            self._error(
                expr,
                f"[TYP-0183] function call has wrong number of arguments: "
                f"expected {expected_arity}, got {given_arity}",
            )

        # Type-check arguments
        for index, arg in enumerate(expr.args):
            if index < len(callee_ty.params):
                param_ty = callee_ty.params[index]
                self._infer_expr(arg, widening_type=param_ty,
                                 context_code="TYP-0312",
                                 context_descriptor=f"argument {index + 1} to function '{expr.callee.name}'")
        return callee_ty.result

    def _infer_struct_constructor(self, expr: CallExpr, sym: Symbol) -> Optional[Type]:
        """Infer type for a struct constructor call."""
        assert isinstance(expr.callee, VarRef)
        if sym.kind is SymbolKind.TYPE_ALIAS and isinstance(sym.type, StructType):
            # Type alias to struct
            struct_type = sym.type
            module_name = struct_type.module
            struct_name = struct_type.name
        else:
            # Direct struct
            module_name = sym.module.name
            struct_name = expr.callee.name
            struct_type = StructType(module_name, struct_name)

        # Look up struct info to get field types
        info = self.struct_infos.get((module_name, struct_name))
        if info is None:
            self._error(expr, f"[TYP-0190] no type information for struct '{struct_name}'")
            return None

        # Arity check
        expected_arity = len(info.fields)
        given_arity = len(expr.args)
        if expected_arity != given_arity:
            self._error(
                expr,
                f"[TYP-0191] struct constructor '{struct_name}' expects {expected_arity} "
                f"argument(s), got {given_arity}",
            )

        # Type-check arguments against field types
        for index, arg in enumerate(expr.args):
            if index < len(info.fields):
                field_info = info.fields[index]
                self._infer_expr(arg, widening_type=field_info.type,
                                 context_code="TYP-0313",
                                 context_descriptor=f"argument {index + 1} to struct constructor '{struct_name}' for field '{field_info.name}'")

        return struct_type

    def _infer_variant_constructor(self, expr: CallExpr, sym: Symbol) -> Optional[Type]:
        """Infer type for an enum variant constructor call."""
        assert isinstance(expr.callee, VarRef)
        variant_name = expr.callee.name

        # The variant's type should be a FuncType: (payload...) -> EnumType
        # This was set by SignatureResolver
        if not isinstance(sym.type, FuncType):
            self._error(expr, f"[TYP-0200] variant '{variant_name}' has no type information")
            return None

        variant_type = sym.type
        enum_type = variant_type.result

        if not isinstance(enum_type, EnumType):
            self._error(expr, f"[TYP-9209] internal error: variant '{variant_name}' does not produce enum type")
            return None

        # Arity check
        expected_arity = len(variant_type.params)
        given_arity = len(expr.args)
        if expected_arity != given_arity:
            self._error(
                expr,
                f"[TYP-0201] variant constructor '{variant_name}' expects {expected_arity} "
                f"argument(s), got {given_arity}",
            )

        # Type-check arguments against payload types
        for index, arg in enumerate(expr.args):
            if index < len(variant_type.params):
                param_ty = variant_type.params[index]
                self._infer_expr(arg,
                                 widening_type=param_ty,
                                 context_code="TYP-0314",
                                 context_descriptor=f"argument {index + 1} to variant constructor '{variant_name}'")

        return enum_type

    def _infer_index(self, expr: IndexExpr) -> Optional[Type]:
        """Infer type for an indexing expression."""
        array_ty = self._infer_expr(expr.array)
        index_ty = self._infer_expr(expr.index)

        if index_ty is not None and not self._is_int_assignable(index_ty):
            self._error(expr, f"[TYP-0210] index expression must have type 'int', got '{format_type(index_ty)}'")

        if isinstance(array_ty, NullableType):
            self._error(
                expr,
                f"[TYP-0211] cannot index into nullable type '{format_type(array_ty)}'; indexing is not yet supported",
            )
            return None

        # if isinstance(array_ty, ArrayType): # TODO Uncomment when ArrayType is defined (buffers and slices)
        #     return array_ty.inner

        if array_ty is not None:
            self._error(
                expr,
                f"[TYP-0212] cannot index into expression of type '{format_type(array_ty)}'; indexing is not yet supported",
            )

        return None

    def _infer_field_access(self, expr: FieldAccessExpr) -> Optional[Type]:
        """Infer type for a field access expression."""
        obj_ty = self._infer_expr(expr.obj)

        if isinstance(obj_ty, NullableType) and isinstance(obj_ty.inner, StructType):
            self._error(
                expr,
                f"[TYP-0220] cannot access field '{expr.field}' on nullable struct '{format_type(obj_ty)}'; expected a non-null struct",
            )
            return None

        # Dereference pointer to struct if needed
        if isinstance(obj_ty, PointerType) and isinstance(obj_ty.inner, StructType):
            obj_ty = obj_ty.inner

        if isinstance(obj_ty, StructType):
            info = self.struct_infos.get((obj_ty.module, obj_ty.name))
            if info is None:
                return None

            for field_info in info.fields:
                if field_info.name == expr.field:
                    return field_info.type

            self._error(
                expr,
                f"[TYP-0221] struct '{format_type(obj_ty)}' has no field '{expr.field}'",
            )
            return None

        if obj_ty is not None:
            self._error(
                expr,
                f"[TYP-0222] cannot access field '{expr.field}' on non-struct type '{format_type(obj_ty)}'",
            )

        return None

    def _infer_cast(self, expr: CastExpr) -> Optional[Type]:
        """Infer type for a cast expression and validate compatibility."""
        expr_ty = self._infer_expr(expr.expr)
        if expr_ty is None:
            return None

        target_ty = self._resolve_type_ref(expr.target_type)
        if target_ty is None:
            return None

        # Explicit int -> byte casts with compile-time-known values are checked in analysis.
        if (
                isinstance(expr_ty, BuiltinType)
                and expr_ty.name == "int"
                and isinstance(target_ty, BuiltinType)
                and target_ty.name == "byte"
        ):
            const_int = self._get_const_int_for_explicit_cast(expr.expr)
            if const_int is not None and (const_int < 0 or const_int > 255):
                return self._error(
                    expr,
                    f"[TYP-0700] explicit cast from 'int' to 'byte' overflows: {const_int} is outside 0..255",
                )

        # Explicit unwrap from nullable pointer to pointer cannot be proven-null.
        if (
                isinstance(expr_ty, NullableType)
                and isinstance(expr_ty.inner, PointerType)
                and isinstance(target_ty, PointerType)
                and self._types_equal(target_ty, expr_ty.inner)
                and self._is_const_null_for_explicit_cast(expr.expr)
        ):
            return self._error(
                expr,
                f"[TYP-0701] explicit cast from '{format_type(expr_ty)}' to '{format_type(target_ty)}' is null at compile time",
            )

        # Allow the cast if the types are assignable
        if self._can_assign(target_ty, expr_ty, allow_promotion=True):
            return target_ty

        return self._error(
            expr, f"[TYP-0230] cannot cast from '{format_type(expr_ty)}' to '{format_type(target_ty)}'"
        )

    def _infer_try(self, expr: TryExpr) -> Optional[Type]:
        """Infer type for a '?' try operator expression."""
        if self._current_func_type is None:
            return None

        inner_ty = self._infer_expr(expr.expr)
        if inner_ty is None:
            return None

        if not isinstance(inner_ty, NullableType):
            self._error(expr, f"[TYP-0250] cannot apply '?' to non-nullable type '{format_type(inner_ty)}'")
            return None

        if not isinstance(self._current_func_type.result, NullableType):
            self._error(expr, "[TYP-0251] cannot use '?' in a function that does not return a nullable type (T?)")
            return None

        return inner_ty.inner

    # ------------------------------------------------------------------
    # Return statements
    # ------------------------------------------------------------------

    def _check_return(self, stmt: ReturnStmt) -> None:
        """Check return statement validity and type compatibility."""
        if self._current_func_type is None:
            self._error(stmt, "[TYP-0260] return statement outside of function")
            return

        expected = self._current_func_type.result
        if stmt.value is None:
            if not self._can_assign(expected, self.void_type):
                self._error(stmt,
                            f"[TYP-0315] return value type mismatch: expected '{format_type(expected)}', got 'void'")
        else:
            # Use expected type as widening context for return value, and delegate type checking to _infer_expr
            self._infer_expr(stmt.value,
                             widening_type=expected,
                             context_code="TYP-0315",
                             context_descriptor="return value")

    # ------------------------------------------------------------------
    # Helpers: TypeRef resolution (mirrors SignatureResolver logic)
    # ------------------------------------------------------------------

    def _resolve_type_ref(self, tref) -> Optional[Type]:
        """Resolve a TypeRef to a semantic Type."""
        if self._current_func_env is None:
            return None

        # Reject overqualified type references (e.g. color::Color::Red as a type)
        if self._reject_name_qualifier(tref, tref.name, tref.name_qualifier, tref.module_path):
            return None

        module_name = self._current_func_env.module_name
        result = resolve_type_ref(self.module_envs, module_name, tref, module_path=tref.module_path)
        if result.type is None:
            if result.error is TypeResolveErrorKind.INVALID_NULLABLE_VOID:
                self._error(tref, "[TYP-0278] type 'void' cannot be nullable")
                return None
            if result.error is TypeResolveErrorKind.VARIANT_AS_TYPE:
                return None
            if result.error is TypeResolveErrorKind.AMBIGUOUS_TYPE:
                modules_str = "', '".join(result.ambiguous_modules)
                hints = " or ".join(f"'{m}::{result.name}'" for m in result.ambiguous_modules)
                self._error(
                    tref,
                    f"[TYP-0279] ambiguous type '{result.name}' (imported from modules '{modules_str}'); "
                    f"use {hints} to disambiguate",
                )
                return None
            if result.error is TypeResolveErrorKind.UNKNOWN_TYPE:
                self._error(
                    tref,
                    f"[TYP-0279] unknown type '{result.name}' in module '{result.module_name}'",
                )
                return None
            if result.error in (TypeResolveErrorKind.UNKNOWN_MODULE, TypeResolveErrorKind.MODULE_NOT_IMPORTED):
                self._error(
                    tref,
                    f"[TYP-0279] unknown type '{result.name}' in module '{result.module_name}'",
                )
                return None
            if result.error is TypeResolveErrorKind.UNRESOLVED_ALIAS:
                self._error(
                    tref,
                    f"[TYP-0270] type alias '{result.name}' in module '{module_name}'"
                    " does not have a resolved type",
                )
                return None
            if result.error is TypeResolveErrorKind.NOT_A_TYPE:
                self._error(
                    tref,
                    f"[TYP-0271] symbol '{result.name}' in module '{module_name}' "
                    f"is not a type (kind={result.symbol.kind.name})",
                )
                return None

        return result.type

    # ------------------------------------------------------------------
    # Helpers: diagnostics and type comparisons
    # ------------------------------------------------------------------

    def _can_assign(self, target: Type, source: Type, *, allow_promotion=False) -> bool:
        """Check if 'source' type can be assigned to 'target' type."""
        # Exact match
        if self._types_equal(target, source):
            return True

        # Null assignment
        if isinstance(source, NullType):
            if isinstance(target, NullableType):
                return True

        # Allow widening for certain built-in types (byte -> int)
        if isinstance(source, BuiltinType) and isinstance(target, BuiltinType):
            if source.name == "byte" and target.name == "int":
                return True

        # Checked narrowing for built-in types (int -> byte) in casts
        if allow_promotion and isinstance(source, BuiltinType) and isinstance(target, BuiltinType):
            # Allow int -> byte in checked contexts (casts)
            if source.name == "int" and target.name == "byte":
                return True

        # Allow widening non-nullable to nullable promotion (T -> T?)
        if isinstance(target, NullableType):
            if self._can_assign(target.inner, source):
                return True

        # Nullable to non-nullable demotion (T? -> T) only if allowed (e.g., in casts)
        if allow_promotion and not isinstance(target, NullableType) and isinstance(source, NullableType):
            if self._can_assign(target, source.inner):
                return True

        # Recursive checks for Nullable types
        if isinstance(source, NullableType) and isinstance(target, NullableType):
            # T1? -> T2? if T1 -> T2
            return self._can_assign(target.inner, source.inner)

        # Recursive checks for Pointer types
        if isinstance(source, PointerType) and isinstance(target, PointerType):
            # T1* -> T2* if T1 -> T2 or T2 is void or T1 is void
            if self._is_void(target.inner) or self._is_void(source.inner):
                return True
            return self._can_assign(target.inner, source.inner)

        return False

    def _is_nullable_or_ptr(self, t: Type) -> bool:
        """Check if type is nullable or a pointer."""
        return isinstance(t, (NullableType, PointerType))

    def _error(self, node: Optional[Node], message: str) -> None:
        """Report an error diagnostic."""
        self._diagnostic(node, message, kind="error")

    def _warn(self, node: Optional[Node], message: str) -> None:
        """Report a warning diagnostic."""
        self._diagnostic(node, message, kind="warning")

    def _diagnostic(self, node: Optional[Node], message: str, kind: str = "info") -> None:
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

    def _is_int_assignable(self, typ: Optional[Type]) -> bool:
        """Check if type is 'int' or 'byte'."""
        return isinstance(typ, BuiltinType) and (typ.name == "int" or typ.name == "byte")

    def _get_const_int_for_explicit_cast(self, expr: Expr) -> Optional[int]:
        """Extract a compile-time integer value from a cast operand when available."""
        if isinstance(expr, IntLiteral):
            return expr.value
        if isinstance(expr, ParenExpr):
            return self._get_const_int_for_explicit_cast(expr.inner)
        if isinstance(expr, UnaryOp) and expr.op == "-":
            inner = self._get_const_int_for_explicit_cast(expr.operand)
            if inner is not None:
                return -inner
        return None

    def _is_const_null_for_explicit_cast(self, expr: Expr) -> bool:
        """Check whether a cast operand is provably null at compile time."""
        if isinstance(expr, NullLiteral):
            return True
        if isinstance(expr, ParenExpr):
            return self._is_const_null_for_explicit_cast(expr.inner)
        if isinstance(expr, CastExpr):
            return self._is_const_null_for_explicit_cast(expr.expr)
        return False

    def _is_bool(self, typ: Optional[Type]) -> bool:
        """Check if type is 'bool'."""
        return isinstance(typ, BuiltinType) and typ.name == "bool"

    def _is_string(self, typ: NullType | Type) -> bool:
        """Check if type is 'string'."""
        return isinstance(typ, BuiltinType) and typ.name == "string"

    def _case_literal_info(self, expr: Expr) -> Optional[tuple[Type, object]]:
        """Get type and value for a case arm literal."""
        if isinstance(expr, IntLiteral):
            return self.int_type, expr.value
        if isinstance(expr, ByteLiteral):
            decoded = self._decode_escaped_bytes(expr.value, expr)
            if decoded is None or len(decoded) != 1:
                return None
            value = decoded[0]
            return self.byte_type, value
        if isinstance(expr, BoolLiteral):
            return self.bool_type, expr.value
        if isinstance(expr, StringLiteral):
            decoded = self._decode_escaped_bytes(expr.value, expr)
            if decoded is None:
                return None
            return self.string_type, decoded
        return None

    def _decode_escaped_bytes(self, text: str, node: Node) -> Optional[bytes]:
        """Decode a string literal, reporting errors."""
        try:
            return decode_l0_string_token(text)
        except EscapeDecodeError as err:
            if err.code == "invalid_unicode_escape":
                self._error(node, "[TYP-0109] invalid unicode escape in 'case' literal")
                return None
            if err.code == "unicode_out_of_range":
                self._error(node, "[TYP-0109] unicode escape out of range in 'case' literal")
                return None
            self._error(node, "[TYP-0109] invalid escape in 'case' literal")
            return None

    def _is_void(self, typ: Type) -> bool:
        """Check if type is 'void'."""
        return isinstance(typ, BuiltinType) and typ.name == "void"

    def _types_equal(self, a: Type, b: Type) -> bool:
        """Check if two types are exactly the same."""
        return a == b

    def _describe_lvalue(self, expr: Expr) -> str:
        """Generate a human-readable description of an lvalue expression."""
        if isinstance(expr, VarRef):
            return f"variable '{expr.name}'"
        elif isinstance(expr, FieldAccessExpr):
            return f"field '{expr.field}'"
        elif isinstance(expr, IndexExpr):
            return "array element"
        elif isinstance(expr, UnaryOp) and expr.op == "*":
            return "dereferenced pointer"
        else:
            return "expression"

    def _reject_name_qualifier(
            self,
            node: Node,
            name: str,
            name_qualifier: Optional[List[str]],
            module_path: Optional[List[str]],
    ) -> bool:
        """Check for and reject unsupported qualified name syntax (::)."""
        if name_qualifier is None:
            return False
        full = "::".join(name_qualifier + [name])
        if module_path:
            full = f"{'.'.join(module_path)}::{full}"
        simple = name
        if module_path:
            simple = f"{'.'.join(module_path)}::{name}"
        self._error(
            node,
            f"[TYP-0158] nested symbol path '{full}': "
            f"paths must have the form 'module::symbol' (did you mean '{simple}'?)",
        )
        return True

    def _infer_new(self, expr: NewExpr) -> Optional[Type]:
        """Infer type for a 'new' heap allocation expression."""
        if self._current_func_env is None:
            return self._error(expr, f"[TYP-9288] internal error: 'new' outside function context")

        module_name = self._current_func_env.module_name
        mod_env = self.module_envs.get(module_name)

        if mod_env is None:
            return self._error(expr, f"[TYP-9289] internal error: no module env for '{module_name}'")

        base_ty = self._resolve_type_ref(expr.type_ref)

        if base_ty is None:
            # Type resolution failed - check if it's an enum variant constructor (e.g., new CaseA(42))
            sym_result = resolve_symbol(
                self.module_envs,
                module_name,
                expr.type_ref.name,
                module_path=expr.type_ref.module_path,
            )
            sym = sym_result.symbol
            if sym and sym.kind is SymbolKind.ENUM_VARIANT:
                enum_ty = self._infer_variant_constructor(
                    CallExpr(callee=VarRef(name=expr.type_ref.name, module_path=expr.type_ref.module_path),
                             args=expr.args),
                    sym,
                )
                return PointerType(enum_ty) if enum_ty else None
            return self._error(expr, f"[TYP-0280] unknown type in 'new' expression")

        if isinstance(base_ty, EnumType):
            return self._error(expr, f"[TYP-0281] cannot allocate enum type '{format_type(base_ty)}' without a variant")

        if isinstance(base_ty, StructType):
            info = self.struct_infos.get((base_ty.module, base_ty.name))
            if info is None:
                return self._error(expr, f"[TYP-0282] missing struct info for {base_ty.module}.{base_ty.name}")

            if len(expr.args) > 0:
                if len(expr.args) != len(info.fields):
                    self._error(expr,
                                f"[TYP-0283] struct '{base_ty.name}' expects {len(info.fields)} argument(s), got {len(expr.args)}")

                for field, arg in zip(info.fields, expr.args):
                    self._infer_expr(arg, widening_type=field.type,
                                     context_code="TYP-0316",
                                     context_descriptor=f"field '{field.name}' of struct '{base_ty.name}'")

        else:
            # Non-struct types (builtins, pointers, nullable): expect 0 or 1 argument
            if len(expr.args) > 1:
                self._error(expr,
                            f"[TYP-0285] 'new {format_type(base_ty)}' expects at most 1 argument, got {len(expr.args)}")
            elif len(expr.args) == 1:
                arg_ty = self._infer_expr(expr.args[0])
                if arg_ty is not None and not self._can_assign(base_ty, arg_ty):
                    self._error(expr.args[0],
                                f"[TYP-0286] cannot initialize '{format_type(base_ty)}' with value of type '{format_type(arg_ty)}'")

        return PointerType(base_ty)
