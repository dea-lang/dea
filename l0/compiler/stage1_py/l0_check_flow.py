# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass
from l0_ast import Stmt, Block, LetStmt, AssignStmt, ExprStmt, IfStmt, WhileStmt, ReturnStmt, MatchArm, MatchStmt, CaseStmt, Expr, VarRef, VariantPattern, DropStmt, WildcardPattern, BreakStmt, ContinueStmt, ForStmt, WithStmt
from l0_locals import FunctionEnv
from l0_resolve import resolve_symbol
from l0_symbols import SymbolKind
from l0_types import FuncType, BuiltinType, EnumType, get_builtin_type, PointerType, NullableType, NullType, format_type
from l0_check_compat import TypeCompatibility
from l0_check_expr import ExpressionInference
from l0_check_liveness import ExpressionLiveness
from l0_check_lookup import SemanticLookup
from l0_check_patterns import PatternAnalysis
from l0_check_state import CheckerState
from l0_check_state import StmtFlow, LoopFlowCapture


@dataclass
class StatementFlow:
    """Statement traversal and loop-liveness fixed points as one recursive algorithm."""

    compat: TypeCompatibility
    expr: ExpressionInference
    liveness: ExpressionLiveness
    lookup: SemanticLookup
    patterns: PatternAnalysis
    state: CheckerState

    def _check_function(self, func_env: FunctionEnv, func_type: FuncType) -> None:
        """Check a single function definition.

        Args:
            func_env: The function's environment containing AST and module info.
            func_type: The function's resolved signature.
        """
        self.state._current_func_env = func_env
        self.state._current_func_type = func_type

        # Root scope: one frame containing parameters
        self.state._local_scopes = [self.state._make_param_scope(func_env, func_type)]
        self.state._alive_scopes = [self.state._make_param_alive_scope(func_env)]

        # Track whether the function body guarantees a return along all paths.
        self.state._return_paths = False
        self._check_block(func_env.func.body, check_return_paths=True, push_new_scope=False)
        self.state._breakable_loop_depth = 0
        self.state._next_stmt_unreachable = False
        guarantees_return = self.state._return_paths

        # Only require guaranteed return when result type is non-void.
        is_void_result = self.compat._is_void(func_type.result)
        if not is_void_result and not guarantees_return:
            self.state._error(
                func_env.func,
                f"[TYP-0010] not all control paths return a value of type '{format_type(func_type.result)}'",
            )

        self.state._local_scopes = []
        self.state._current_func_env = None
        self.state._current_func_type = None

    def _check_dead_liveness_block(self, block: Block, *, check_return_paths: bool) -> StmtFlow:
        """Type-check an unreachable branch without exporting liveness or loop exits."""
        saved_alive = self.state._clone_alive_scopes()
        saved_unreachable = self.state._next_stmt_unreachable
        saved_return_paths = self.state._return_paths
        saved_capture_stack = self.state._loop_flow_capture_stack
        saved_suppress_liveness = self.state._suppress_liveness_diagnostics
        self.state._next_stmt_unreachable = False
        self.state._loop_flow_capture_stack = []
        self.state._suppress_liveness_diagnostics = True
        try:
            return self._check_block(block, check_return_paths=check_return_paths, push_new_scope=False)
        finally:
            self.state._alive_scopes = saved_alive
            self.state._next_stmt_unreachable = saved_unreachable
            self.state._return_paths = saved_return_paths
            self.state._loop_flow_capture_stack = saved_capture_stack
            self.state._suppress_liveness_diagnostics = saved_suppress_liveness

    def _check_update_from_backedge_states(
        self,
        update: Stmt | None,
        states: list[list[dict[str, bool]]],
    ) -> list[list[dict[str, bool]]]:
        """Check a for-update statement from all reachable body backedges."""
        if not states:
            if update is not None:
                saved_alive = self.state._clone_alive_scopes()
                saved_unreachable = self.state._next_stmt_unreachable
                self.state._next_stmt_unreachable = False
                self._check_stmt(update)
                self.state._alive_scopes = saved_alive
                self.state._next_stmt_unreachable = saved_unreachable
            return []
        if update is None:
            return [[dict(scope) for scope in state] for state in states]

        self.state._alive_scopes = self.state._meet_alive_state(*states)
        update_flow = self._check_stmt(update)
        if update_flow is StmtFlow.FALLTHROUGH:
            return [self.state._clone_alive_scopes()]
        return []

    def _check_loop_iteration(
        self,
        body: Block,
        *,
        update: Stmt | None = None,
        check_return_paths: bool = False,
    ) -> tuple[LoopFlowCapture, list[list[dict[str, bool]]], StmtFlow]:
        """Check one loop iteration and return captured flow states."""
        capture = LoopFlowCapture()
        self.state._loop_flow_capture_stack.append(capture)
        self.state._breakable_loop_depth += 1
        try:
            body_flow = self._check_block(body, check_return_paths=check_return_paths)
        finally:
            self.state._breakable_loop_depth -= 1
            self.state._loop_flow_capture_stack.pop()

        backedge_states = [[dict(scope) for scope in state] for state in capture.continue_states]
        if body_flow is StmtFlow.FALLTHROUGH:
            backedge_states.append(self.state._clone_alive_scopes())
        backedge_states = self._check_update_from_backedge_states(update, backedge_states)
        return capture, backedge_states, body_flow

    def _loop_liveness_fixed_point(
        self,
        pre_loop: list[dict[str, bool]],
        body: Block,
        *,
        cond: Expr | None = None,
        update: Stmt | None = None,
    ) -> tuple[list[dict[str, bool]], LoopFlowCapture, list[list[dict[str, bool]]]]:
        """Converge loop-head liveness and diagnose later-iteration uses."""
        head = self.state._clone_alive_scopes()
        saved_unreachable = self.state._next_stmt_unreachable
        while True:
            self.state._alive_scopes = [dict(scope) for scope in head]
            old_suppress = self.state._suppress_diagnostics
            old_liveness_only = self.state._liveness_diagnostics_only
            self.state._suppress_diagnostics = True
            self.state._liveness_diagnostics_only = True
            try:
                _, backedge_states, _ = self._check_loop_iteration(
                    body,
                    update=update,
                )
            finally:
                self.state._liveness_diagnostics_only = old_liveness_only
                self.state._suppress_diagnostics = old_suppress
                self.state._next_stmt_unreachable = saved_unreachable
            next_head = self.state._meet_alive_state(pre_loop, *backedge_states)
            if next_head == head:
                head = next_head
                break
            head = next_head

        self.state._alive_scopes = [dict(scope) for scope in head]
        old_liveness_only = self.state._liveness_diagnostics_only
        self.state._liveness_diagnostics_only = True
        try:
            if cond is not None:
                self.expr._infer_expr(cond)
            capture, backedge_states, _ = self._check_loop_iteration(
                body,
                update=update,
            )
        finally:
            self.state._liveness_diagnostics_only = old_liveness_only
            self.state._next_stmt_unreachable = saved_unreachable
        self.state._alive_scopes = head
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
            self.state._push_scope()
        try:
            unreachable_warning_issued = False
            guarantees_return = False
            block_flow = StmtFlow.FALLTHROUGH
            check_or_not = check_return_paths
            for stmt in block.stmts:
                unreachable_before_stmt = guarantees_return or self.state._next_stmt_unreachable
                pre_unreachable_alive = self.state._clone_alive_scopes()
                active_capture = self.state._loop_flow_capture_stack[-1] if self.state._loop_flow_capture_stack else None
                pre_break_count = len(active_capture.break_states) if active_capture is not None else 0
                pre_continue_count = len(active_capture.continue_states) if active_capture is not None else 0
                # Check for unreachable code after a guaranteed return
                if guarantees_return and not unreachable_warning_issued:
                    self.state._warn(stmt, "[TYP-0031] unreachable code after 'return'")
                    unreachable_warning_issued = True
                if self.state._next_stmt_unreachable and not unreachable_warning_issued:
                    self.state._warn(stmt, "[TYP-0030] unreachable code")
                    unreachable_warning_issued = True
                # Check the statement
                stmt_flow = self._check_stmt(stmt, check_return_paths=check_or_not)
                if unreachable_before_stmt:
                    self.state._alive_scopes = pre_unreachable_alive
                    if active_capture is not None:
                        del active_capture.break_states[pre_break_count:]
                        del active_capture.continue_states[pre_continue_count:]
                    continue
                # Update return path tracking
                if check_return_paths:
                    guarantees_return = guarantees_return or self.state._return_paths
                    if guarantees_return:
                        check_or_not = False  # no need to check further statements
                if stmt_flow is StmtFlow.RETURNS:
                    block_flow = StmtFlow.RETURNS
                elif stmt_flow is StmtFlow.STOPS:
                    block_flow = StmtFlow.STOPS
                if stmt_flow is not StmtFlow.FALLTHROUGH:
                    self.state._next_stmt_unreachable = True

            if check_return_paths:
                self.state._return_paths = guarantees_return
            return block_flow
        finally:
            self.state._next_stmt_unreachable = False  # reset for outer scope
            if push_new_scope:
                self.state._pop_scope()

    def _check_stmt(self, stmt: Stmt, *, check_return_paths: bool = False) -> StmtFlow:
        """Check a single statement.

        Args:
            stmt: The Stmt node.
            check_return_paths: Whether to update return path tracking.
        """

        if check_return_paths:
            self.state._return_paths = False  # reset before checking this statement

        if isinstance(stmt, ReturnStmt):
            self._check_return(stmt)
            if check_return_paths:
                self.state._return_paths = True
            return StmtFlow.RETURNS

        if isinstance(stmt, ExprStmt):
            self.expr._infer_expr(stmt.expr)
            return StmtFlow.FALLTHROUGH

        if isinstance(stmt, LetStmt):
            annot_ty = None  # type from annotation (if any)
            value_ty = None  # type from expression

            # Resolve annotation if present
            if stmt.type is not None:
                annot_ty = self.lookup._resolve_type_ref(stmt.type)
                if annot_ty is None:  # error in type ref
                    self.state._error(stmt.type, f"[TYP-0040] cannot resolve type annotation for variable '{stmt.name}'")
                    return StmtFlow.FALLTHROUGH
                if annot_ty is get_builtin_type("void"):
                    self.state._error(stmt, "[TYP-0050] variable cannot have type 'void'")
                    return StmtFlow.FALLTHROUGH
                # Infer initializer type in the context of annotation
                value_ty = self.expr._infer_expr(stmt.value,
                                            widening_type=annot_ty,
                                            context_code="TYP-0310",
                                            context_descriptor=f"initializer for variable '{stmt.name}'")
                if value_ty is None:
                    # Error already reported by _infer_expr
                    return StmtFlow.FALLTHROUGH

            # When widening_type is provided, _infer_expr already checks compatibility
            if annot_ty is not None:
                self.lookup._declare_local(stmt.name, annot_ty, stmt)
                return StmtFlow.FALLTHROUGH

            # No annotation: infer from initializer
            value_ty = self.expr._infer_expr(stmt.value, context_descriptor=f"initializer for variable '{stmt.name}'")

            # Type inference
            if value_ty is None:
                # Error in expression, can't infer (should have been reported already)
                self.state._error(stmt, f"[TYP-0051] initializer for '{stmt.name}' type mismatch")
                return StmtFlow.FALLTHROUGH
            elif isinstance(value_ty, NullType):
                self.state._error(stmt, "[TYP-0052] cannot infer type from 'null'; explicit type required")
                return StmtFlow.FALLTHROUGH
            elif self.compat._is_void(value_ty):
                self.state._error(stmt.value, "[TYP-0053] initializer is 'void', cannot assign to variable")
                return StmtFlow.FALLTHROUGH
            else:
                self.lookup._declare_local(stmt.name, value_ty, stmt)

            return StmtFlow.FALLTHROUGH

        if isinstance(stmt, AssignStmt):
            # A bare assignment target may revive a dropped variable, but the
            # old value remains dead while the RHS is evaluated.
            prior_alive = None
            if isinstance(stmt.target, VarRef):
                prior_alive = self.state._lookup_alive(stmt.target.name)
                self.state._set_alive(stmt.target.name, True)

            # Infer target type first, then use it as context for value
            target_ty = self.expr._infer_expr(stmt.target)

            if isinstance(stmt.target, VarRef) and prior_alive is not None:
                self.state._set_alive(stmt.target.name, prior_alive)

            if target_ty is not None:
                # Use target type as widening context for the value
                value_ty = self.expr._infer_expr(
                    stmt.value,
                    widening_type=target_ty,
                    context_code="TYP-0311",
                    context_descriptor=f"assignment to {self.lookup._describe_lvalue(stmt.target)}",
                )
            else:
                # Target type inference failed, still check value for errors
                value_ty = self.expr._infer_expr(stmt.value)

            if isinstance(stmt.target, VarRef) and value_ty is not None:
                self.state._set_alive(stmt.target.name, True)

            return StmtFlow.FALLTHROUGH

        if isinstance(stmt, DropStmt):
            var_ty = self.lookup._lookup_local(stmt.name)
            if var_ty is None:
                assert self.state._current_func_env is not None
                sym_result = resolve_symbol(
                    self.state.module_envs,
                    self.state._current_func_env.module_name,
                    stmt.name,
                )
                if sym_result.symbol is not None and sym_result.symbol.kind is SymbolKind.LET:
                    self.state._error(stmt, f"[TYP-0063] cannot drop module-level let '{stmt.name}'")
                    return StmtFlow.FALLTHROUGH
                self.state._error(stmt, f"[TYP-0060] unknown variable '{stmt.name}'")
                return StmtFlow.FALLTHROUGH

            is_ptr = isinstance(var_ty, PointerType)
            is_opt_ptr = isinstance(var_ty, NullableType) and isinstance(var_ty.inner, PointerType)
            if not (is_ptr or is_opt_ptr):
                self.state._error(stmt, f"[TYP-0061] cannot drop non-pointer type '{format_type(var_ty)}'")
                return StmtFlow.FALLTHROUGH

            alive = self.state._lookup_alive(stmt.name)
            if alive is False:
                self.state._error(stmt, f"[TYP-0062] use of dropped variable '{stmt.name}'")
                return StmtFlow.FALLTHROUGH

            self.state._set_alive(stmt.name, False)
            return StmtFlow.FALLTHROUGH

        if isinstance(stmt, IfStmt):
            cond_ty = self.expr._infer_expr(stmt.cond, context_descriptor="condition in if statement")

            if cond_ty is not None and not self.compat._is_bool(cond_ty):
                self.state._error(stmt, "[TYP-0070] if condition must have type 'bool'")

            pre_unreachable = self.state._next_stmt_unreachable
            pre_alive = [dict(scope) for scope in self.state._alive_scopes]

            # then branch
            self.state._next_stmt_unreachable = False
            then_flow = self._check_stmt(stmt.then_stmt, check_return_paths=check_return_paths)
            then_alive = [dict(scope) for scope in self.state._alive_scopes]
            then_returns = self.state._return_paths
            then_unreachable = self.state._next_stmt_unreachable

            # else branch
            else_returns = False
            else_unreachable = False
            else_flow = StmtFlow.FALLTHROUGH
            fallthrough_states: list[list[dict[str, bool]]] = []
            if then_flow is StmtFlow.FALLTHROUGH:
                fallthrough_states.append(then_alive)
            if stmt.else_stmt is not None:
                # Restore pre-if liveness
                self.state._alive_scopes = [dict(scope) for scope in pre_alive]
                self.state._next_stmt_unreachable = False
                else_flow = self._check_stmt(stmt.else_stmt, check_return_paths=check_return_paths)
                else_alive = [dict(scope) for scope in self.state._alive_scopes]
                else_returns = self.state._return_paths
                else_unreachable = self.state._next_stmt_unreachable
                if else_flow is StmtFlow.FALLTHROUGH:
                    fallthrough_states.append(else_alive)
            else:
                # Without an else, the false branch falls through unchanged.
                fallthrough_states.append(pre_alive)

            if fallthrough_states:
                self.state._alive_scopes = self.state._meet_alive_state(*fallthrough_states)
                stmt_flow = StmtFlow.FALLTHROUGH
            elif then_flow is StmtFlow.RETURNS and else_flow is StmtFlow.RETURNS:
                self.state._alive_scopes = [dict(scope) for scope in pre_alive]
                stmt_flow = StmtFlow.RETURNS
            else:
                self.state._alive_scopes = [dict(scope) for scope in pre_alive]
                stmt_flow = StmtFlow.STOPS

            if check_return_paths:
                # An if-else guarantees a return only if BOTH branches do.
                # An if without an else never guarantees a return.
                self.state._return_paths = then_returns and else_returns

            if pre_unreachable:
                self.state._next_stmt_unreachable = True
            elif stmt.else_stmt is not None:
                self.state._next_stmt_unreachable = then_unreachable and else_unreachable
            else:
                self.state._next_stmt_unreachable = False

            return stmt_flow

        if isinstance(stmt, WhileStmt):
            cond_ty = self.expr._infer_expr(stmt.cond, context_descriptor="condition in while loop")
            if cond_ty is not None and not self.compat._is_bool(cond_ty):
                self.state._error(stmt, "[TYP-0080] while condition must have type 'bool'")

            pre_alive = self.state._clone_alive_scopes()
            capture, backedge_states, _ = self._check_loop_iteration(
                stmt.body,
                check_return_paths=check_return_paths,
            )
            next_head = self.state._meet_alive_state(pre_alive, *backedge_states)
            if next_head != pre_alive:
                _, capture, backedge_states = self._loop_liveness_fixed_point(
                    pre_alive,
                    stmt.body,
                    cond=stmt.cond,
                )
            after_states = [pre_alive, *capture.break_states, *backedge_states]
            self.state._alive_scopes = self.state._meet_alive_state(*after_states)
            if check_return_paths:
                self.state._return_paths = False
            return StmtFlow.FALLTHROUGH

        if isinstance(stmt, ForStmt):
            self.state._push_scope()
            try:
                init_returns = False
                init_flow = StmtFlow.FALLTHROUGH
                if stmt.init:
                    init_flow = self._check_stmt(stmt.init, check_return_paths=check_return_paths)
                    init_returns = self.state._return_paths if check_return_paths else False

                if stmt.cond:
                    cond_ty = self.expr._infer_expr(stmt.cond)
                    if cond_ty is not None and not self.compat._is_bool(cond_ty):
                        self.state._error(stmt, "[TYP-0090] for loop condition must have type 'bool'")

                pre_loop_alive = self.state._clone_alive_scopes()
                if init_flow is not StmtFlow.FALLTHROUGH:
                    active_capture = self.state._loop_flow_capture_stack[-1] if self.state._loop_flow_capture_stack else None
                    pre_break_count = len(active_capture.break_states) if active_capture is not None else 0
                    pre_continue_count = len(active_capture.continue_states) if active_capture is not None else 0
                    saved_unreachable = self.state._next_stmt_unreachable
                    try:
                        self.state._next_stmt_unreachable = False
                        self._check_loop_iteration(
                            stmt.body,
                            update=stmt.update,
                            check_return_paths=False,
                        )
                    finally:
                        self.state._alive_scopes = [dict(scope) for scope in pre_loop_alive]
                        self.state._next_stmt_unreachable = saved_unreachable
                        if active_capture is not None:
                            del active_capture.break_states[pre_break_count:]
                            del active_capture.continue_states[pre_continue_count:]
                    if check_return_paths:
                        self.state._return_paths = init_returns
                    return init_flow

                capture, backedge_states, _ = self._check_loop_iteration(
                    stmt.body,
                    update=stmt.update,
                    check_return_paths=check_return_paths,
                )
                next_head = self.state._meet_alive_state(pre_loop_alive, *backedge_states)
                if next_head != pre_loop_alive:
                    _, capture, backedge_states = self._loop_liveness_fixed_point(
                        pre_loop_alive,
                        stmt.body,
                        cond=stmt.cond,
                        update=stmt.update,
                    )
                after_states = [pre_loop_alive, *capture.break_states, *backedge_states]
                self.state._alive_scopes = self.state._meet_alive_state(*after_states)
                if check_return_paths:
                    self.state._return_paths = init_returns
                return StmtFlow.FALLTHROUGH
            finally:
                self.state._pop_scope()

        if isinstance(stmt, CaseStmt):
            scrutinee_ty = self.expr._infer_expr(stmt.expr)
            allowed_case_types = {"int", "byte", "bool", "string"}

            if not (isinstance(scrutinee_ty, BuiltinType) and scrutinee_ty.name in allowed_case_types):
                self.state._error(
                    stmt,
                    f"[TYP-0106] 'case' scrutinee must have type 'int', 'byte', 'bool', or 'string', "
                    f"got '{format_type(scrutinee_ty)}'",
                )
                scrutinee_ty = None

            seen_literals: dict[object, Expr] = {}
            all_arms_return = len(stmt.arms) + (1 if stmt.else_arm is not None else 0) > 0
            pre_case_alive = self.state._clone_alive_scopes()
            pre_case_unreachable = self.state._next_stmt_unreachable
            pre_case_return_paths = self.state._return_paths
            fallthrough_states: list[list[dict[str, bool]]] = []

            for arm in stmt.arms:
                literal_info = self.patterns._case_literal_info(arm.literal)
                if literal_info is None:
                    self.state._error(arm, "[TYP-0107] 'case' arm literal must be int, byte, bool, or string")
                else:
                    literal_ty, literal_value = literal_info
                    if scrutinee_ty is not None and literal_ty != scrutinee_ty:
                        self.state._error(
                            arm.literal,
                            f"[TYP-0107] 'case' arm literal type '{format_type(literal_ty)}' "
                            f"does not match scrutinee type '{format_type(scrutinee_ty)}'",
                        )
                    else:
                        if literal_value in seen_literals:
                            self.state._error(
                                arm.literal,
                                "[TYP-0108] duplicate literal value in 'case' statement",
                            )
                        else:
                            seen_literals[literal_value] = arm.literal

                self.state._alive_scopes = [dict(scope) for scope in pre_case_alive]
                self.state._next_stmt_unreachable = False
                self.state._return_paths = False
                arm_flow = StmtFlow.FALLTHROUGH
                self.state._push_scope()
                try:
                    check_or_not = check_return_paths
                    if isinstance(arm.body, Block):
                        arm_flow = self._check_block(arm.body, check_return_paths=check_or_not, push_new_scope=False)
                    else:
                        arm_flow = self._check_stmt(arm.body, check_return_paths=check_or_not)
                    this_arm_returns = arm_flow is StmtFlow.RETURNS
                    all_arms_return = all_arms_return and this_arm_returns
                finally:
                    self.state._pop_scope()
                if arm_flow is StmtFlow.FALLTHROUGH:
                    fallthrough_states.append(self.state._clone_alive_scopes())

            else_arm_flow = StmtFlow.FALLTHROUGH
            if stmt.else_arm is not None:
                self.state._alive_scopes = [dict(scope) for scope in pre_case_alive]
                self.state._next_stmt_unreachable = False
                self.state._return_paths = False
                else_arm_flow = StmtFlow.FALLTHROUGH
                self.state._push_scope()
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
                    self.state._pop_scope()
                if else_arm_flow is StmtFlow.FALLTHROUGH:
                    fallthrough_states.append(self.state._clone_alive_scopes())
            else:
                fallthrough_states.append([dict(scope) for scope in pre_case_alive])

            if check_return_paths:
                self.state._return_paths = stmt.else_arm is not None and all_arms_return
            else:
                self.state._return_paths = pre_case_return_paths

            if stmt.else_arm is not None and all_arms_return:
                self.state._alive_scopes = [dict(scope) for scope in pre_case_alive]
                self.state._next_stmt_unreachable = pre_case_unreachable
                return StmtFlow.RETURNS
            if fallthrough_states:
                self.state._alive_scopes = self.state._meet_alive_state(*fallthrough_states)
                self.state._next_stmt_unreachable = pre_case_unreachable
                return StmtFlow.FALLTHROUGH
            self.state._alive_scopes = [dict(scope) for scope in pre_case_alive]
            self.state._next_stmt_unreachable = pre_case_unreachable
            return StmtFlow.STOPS

        if isinstance(stmt, MatchStmt):
            # Type the scrutinee
            scrutinee_ty = self.expr._infer_expr(stmt.expr)

            if not isinstance(scrutinee_ty, EnumType):
                self.state._error(stmt, f"[TYP-0100] match expression must have enum type, got '{format_type(scrutinee_ty)}'")
                return StmtFlow.FALLTHROUGH

            enum_info = self.state.enum_infos.get((scrutinee_ty.module, scrutinee_ty.name))
            coverage = self.patterns._match_coverage(stmt, scrutinee_ty, enum_info)
            all_arms_return = coverage.reachable_arm_count > 0
            pre_match_alive = self.state._clone_alive_scopes()
            pre_match_unreachable = self.state._next_stmt_unreachable
            fallthrough_states: list[list[dict[str, bool]]] = []

            # Check each arm with pattern variables in scope
            for arm_index, arm in enumerate(stmt.arms):
                assert isinstance(arm, MatchArm)

                self.state._alive_scopes = [dict(scope) for scope in pre_match_alive]
                self.state._next_stmt_unreachable = False
                self.state._return_paths = False

                # Push a new scope for this arm
                self.state._push_scope()
                arm_flow = StmtFlow.FALLTHROUGH
                arm_is_reachable = not (
                    isinstance(arm.pattern, WildcardPattern) and coverage.wildcard_is_unreachable
                )
                try:
                    # Bind payload variables only from the canonical validated variant.
                    validated_name = coverage.validated_variant_names[arm_index]
                    if isinstance(arm.pattern, VariantPattern) and enum_info is not None and validated_name is not None:
                        variant_info = enum_info.variants[validated_name]
                        for var_name, field_type in zip(arm.pattern.vars, variant_info.field_types):
                            self.lookup._declare_local(var_name, field_type, arm)

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
                    self.state._pop_scope()
                if arm_is_reachable and arm_flow is StmtFlow.FALLTHROUGH:
                    fallthrough_states.append(self.state._clone_alive_scopes())

            if not enum_info:
                self.state._error(stmt, f"[TYP-0103] no type information for enum '{format_type(scrutinee_ty)}'")
                self.state._alive_scopes = [dict(scope) for scope in pre_match_alive]
                self.state._next_stmt_unreachable = pre_match_unreachable
                return StmtFlow.FALLTHROUGH

            is_exhaustive = self.patterns._check_exhaustiveness(stmt, scrutinee_ty, coverage)

            if check_return_paths:
                # A match guarantees a return if it is exhaustive AND all arms return.
                self.state._return_paths = is_exhaustive and all_arms_return

            if not is_exhaustive:
                fallthrough_states.append([dict(scope) for scope in pre_match_alive])

            if is_exhaustive and all_arms_return:
                self.state._alive_scopes = [dict(scope) for scope in pre_match_alive]
                self.state._next_stmt_unreachable = pre_match_unreachable
                return StmtFlow.RETURNS
            if fallthrough_states:
                self.state._alive_scopes = self.state._meet_alive_state(*fallthrough_states)
                stmt_flow = StmtFlow.FALLTHROUGH
            else:
                self.state._alive_scopes = [dict(scope) for scope in pre_match_alive]
                stmt_flow = StmtFlow.STOPS
            self.state._next_stmt_unreachable = pre_match_unreachable
            return stmt_flow

        if isinstance(stmt, WithStmt):
            # Type-check items sequentially in a new scope
            self.state._push_scope()
            try:
                seen_header_try = False
                maybe_uninit_nonnullable: set[str] = set()
                header_returns = False

                for item_index, item in enumerate(stmt.items):
                    init_has_try = self.liveness._stmt_contains_try(item.init)
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
                            let_ty = self.state._local_scopes[-1].get(item.init.name)
                            if let_ty is not None and not isinstance(let_ty, NullableType):
                                maybe_uninit_nonnullable.add(item.init.name)

                # Body in a nested scope
                body_flow = self._check_block(stmt.body, check_return_paths=check_return_paths)
                body_returns = self.state._return_paths if check_return_paths else False

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
                    header_scope_index = len(self.state._local_scopes) - 1
                    self.state._cleanup_header_ref_guard_stack.append((header_scope_index, maybe_uninit_nonnullable))
                    try:
                        cleanup_body_flow = self._check_block(
                            stmt.cleanup_body,
                            check_return_paths=check_return_paths,
                        )
                        cleanup_body_returns = self.state._return_paths if check_return_paths else False
                    finally:
                        self.state._cleanup_header_ref_guard_stack.pop()

                with_returns = False
                if check_return_paths:
                    if cleanup_body_returns or inline_override == "return":
                        self.state._return_paths = True
                        with_returns = True
                    elif inline_override == "loop":
                        self.state._return_paths = False
                    else:
                        self.state._return_paths = header_returns or body_returns
                        with_returns = self.state._return_paths
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
                self.state._pop_scope()

        # Handle standalone block statements (nested blocks)
        if isinstance(stmt, Block):
            return self._check_block(stmt, check_return_paths=check_return_paths)

        if isinstance(stmt, BreakStmt):
            if self.state._breakable_loop_depth < 1:
                self.state._error(stmt, "[TYP-0110] 'break' statement not within a loop")
                return StmtFlow.FALLTHROUGH
            else:
                if self.state._loop_flow_capture_stack:
                    self.state._loop_flow_capture_stack[-1].break_states.append(self.state._clone_alive_scopes())
                self.state._next_stmt_unreachable = True
            return StmtFlow.STOPS

        if isinstance(stmt, ContinueStmt):
            if self.state._breakable_loop_depth < 1:
                self.state._error(stmt, "[TYP-0120] 'continue' statement not within a loop")
                return StmtFlow.FALLTHROUGH
            else:
                if self.state._loop_flow_capture_stack:
                    self.state._loop_flow_capture_stack[-1].continue_states.append(self.state._clone_alive_scopes())
                self.state._next_stmt_unreachable = True
            return StmtFlow.STOPS

        # Unknown (should not happen if AST is well-formed)
        self.state._error(stmt, f"[TYP-0139] unknown statement type: {type(stmt).__name__}")
        return StmtFlow.FALLTHROUGH

    def _check_return(self, stmt: ReturnStmt) -> None:
        """Check return statement validity and type compatibility."""
        if self.state._current_func_type is None:
            self.state._error(stmt, "[TYP-0260] return statement outside of function")
            return

        expected = self.state._current_func_type.result
        if stmt.value is None:
            if not self.compat._can_assign(expected, self.state.void_type):
                self.state._error(stmt,
                            f"[TYP-0315] return value type mismatch: expected '{format_type(expected)}', got 'void'")
        else:
            # Use expected type as widening context for return value, and delegate type checking to _infer_expr
            self.expr._infer_expr(stmt.value,
                             widening_type=expected,
                             context_code="TYP-0315",
                             context_descriptor="return value")
