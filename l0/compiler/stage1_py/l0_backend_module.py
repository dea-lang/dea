# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass
from l0_ast import FuncDecl, LetDecl, Stmt, Block, AssignStmt, IfStmt, WhileStmt, MatchStmt, CaseStmt, VarRef, ForStmt, WithStmt
from l0_logger import log_debug, log_stage
from l0_name_resolver import SymbolKind
from l0_types import FuncType
from l0_backend_initializers import StaticInitializers
from l0_backend_lifetime import ValueLifetime
from l0_backend_lowering import Lowering
from l0_backend_ordering import TypeOrdering
from l0_backend_state import BackendState


@dataclass
class ModuleGeneration:
    """Translation-unit order, top-level declarations, and function lifecycle."""

    initializers: StaticInitializers
    lifetime: ValueLifetime
    lowering: Lowering
    ordering: TypeOrdering
    state: BackendState

    def generate(self) -> str:
        """Main entry point: generate complete C source for the compilation unit.

        Returns:
            C source code as a string.

        Raises:
            ValueError: If there is no compilation unit or if there are semantic errors.
        """
        log_stage(self.state.analysis.context, "Generating C code")
        if self.state.analysis.cu is None:
            raise ValueError("Cannot generate code without a compilation unit")

        if self.state.analysis.has_errors():
            raise ValueError("Cannot generate code with semantic errors")

        log_debug(self.state.analysis.context, "Preparing optional wrapper types")
        # Prepare optional wrapper types
        self.state.emitter.types.prepare_optional_wrappers()

        log_debug(self.state.analysis.context, "Emitting header and forward declarations")
        # Emit header and forward declarations
        self.state.emitter.declarations.emit_header()
        self.state.emitter.declarations.emit_forward_decls()

        # Value-optionals of builtins (int?, bool?, string?) must exist before structs that use them.
        self.state.emitter.declarations.emit_section_comment("Optional wrapper types (builtins / early)")
        self.state.emitter.types.emit_optional_wrappers(early=True)

        self.ordering._emit_type_definitions()

        # Value-optionals of user-defined structs/enums (if any)
        self.state.emitter.declarations.emit_section_comment("Optional wrapper types (late)")
        self.state.emitter.types.emit_optional_wrappers(early=False)

        # Emit top-level let declarations (module-level constants/variables)
        self._emit_let_declarations()

        # Emit function declarations and definitions
        self._emit_function_declarations()
        self._emit_function_definitions()

        # Emit C main() wrapper if entry module has a main function
        self._emit_main_wrapper_if_needed()

        return self.state.emitter.state.out.to_string()

    def _emit_let_declarations(self) -> None:
        """Emit static global variables for top-level let declarations."""
        if not self.state.analysis.let_types:
            return  # No let declarations to emit

        self.state.emitter.declarations.emit_section_comment("Top-level let declarations")

        for module in self.state.analysis.cu.modules.values():
            self.state.current_module = module.name
            self.state.emitter.state.current_module = module.name
            module_has_lets = False

            for decl in module.decls:
                if isinstance(decl, LetDecl):
                    if not module_has_lets:
                        self.state.emitter.declarations.emit_module_comment(module.name)
                        module_has_lets = True
                    self._emit_let_declaration(module.name, decl)

    def _emit_let_declaration(self, module_name: str, decl: LetDecl) -> None:
        """Emit a single top-level let declaration as a static variable.

        Args:
            module_name: Name of the module containing the declaration.
            decl: The LetDecl AST node.
        """
        # Get the resolved type
        let_type = self.state.analysis.let_types.get((module_name, decl.name))
        if not let_type:
            # If type is not resolved yet, skip
            return

        # Delegate to emitter with callback for initializer
        self.state.emitter.declarations.emit_let_declaration(module_name, decl, let_type, self.initializers._emit_let_initializer)

    def _emit_function_declarations(self) -> None:
        """Emit forward declarations for all functions."""
        self.state.emitter.declarations.emit_section_comment("Function declarations")

        for module in self.state.analysis.cu.modules.values():
            self.state.current_module = module.name
            self.state.emitter.state.current_module = module.name
            self.state.emitter.declarations.emit_module_comment(module.name)

            for decl in module.decls:
                if isinstance(decl, FuncDecl):
                    self._emit_function_declaration(module.name, decl)

    def _emit_function_declaration(self, module_name: str, decl: FuncDecl) -> None:
        """Emit a single function declaration.

        Args:
            module_name: Name of the module.
            decl: The FuncDecl AST node.

        Raises:
            InternalCompilerError: If FuncType is missing.
        """
        func_type = self.state.analysis.func_types.get((module_name, decl.name))
        if not func_type:
            self.state.ice(f"[ICE-1150] missing FuncType for {module_name}.{decl.name}", node=decl)

        # Delegate to emitter
        self.state.emitter.declarations.emit_function_declaration(module_name, decl, func_type)

    def _emit_function_definitions(self) -> None:
        """Emit function definitions (bodies)."""
        self.state.emitter.declarations.emit_section_comment("Function definitions")

        for module in self.state.analysis.cu.modules.values():
            self.state.current_module = module.name
            self.state.emitter.state.current_module = module.name
            self.state.emitter.declarations.emit_module_separator(module.name)

            for decl in module.decls:
                if isinstance(decl, FuncDecl) and not decl.is_extern:
                    self._emit_function_definition(module.name, decl)

    def _emit_function_definition(self, module_name: str, decl: FuncDecl) -> None:
        """Emit a complete function definition with body.

        Args:
            module_name: Name of the module.
            decl: The FuncDecl AST node.

        Raises:
            InternalCompilerError: If scope is not reset or FuncType is missing.
        """
        if self.state._current_scope is not None:
            self.state.ice(f"[ICE-1160] scope not reset before function {module_name}.{decl.name}")

        self.state._emit_line_directive(decl)

        func_type = self.state.analysis.func_types.get((module_name, decl.name))
        if not func_type:
            return

        # Emit function header via emitter
        self.state.emitter.declarations.emit_function_definition_header(module_name, decl, func_type)

        # Set up function scope (backend responsibility)
        func_scope = self.state._push_scope()
        self.state._next_stmt_unreachable = False

        # An ARC-typed parameter reassigned anywhere in the body is defensively
        # retained on entry and registered as owned, so the scope-exit release
        # balances the entry retain on every control-flow path.
        reassigned = self._collect_reassigned_arc_params(decl, func_type)
        for param, ptype in zip(decl.params, func_type.params):
            c_param_name = self.state.emitter.names.mangle_identifier(param.name)
            if param.name in reassigned:
                self.lifetime._emit_retain_for_copied_value(c_param_name, ptype)
                func_scope.add_owned(c_param_name, ptype)
            else:
                func_scope.add_declared(c_param_name, ptype)

        # Emit body (backend responsibility - statement emission)
        saved = self.state._current_func_result
        self.state._current_func_result = func_type.result
        try:
            self.lowering._emit_block_sequence(decl.body, module_name)
        finally:
            self.state._current_func_result = saved

        # Cleanup if function falls through (void functions / missing return)
        if not self.state._next_stmt_unreachable:
            self.lifetime._emit_cleanup_at_scope_exit(func_scope)

        self.state._pop_scope()

        # Emit function footer via emitter
        self.state.emitter.declarations.emit_function_definition_footer()

    def _emit_main_wrapper_if_needed(self) -> None:
        """If the entry module has a main function, emit a C main() wrapper.

        This allows us to consistently mangle all L0 functions (including main)
        while still providing the expected C entry point.
        """
        if not self.state.analysis.cu.entry_name:
            return

        entry_env = self.state.analysis.module_envs.get(self.state.analysis.cu.entry_name)
        if not entry_env:
            return

        main_symbol = entry_env.locals.get("main")
        if not main_symbol or main_symbol.kind != SymbolKind.FUNC:
            return

        # Get the function type to determine return type
        func_type = self.state.analysis.func_types.get((self.state.analysis.cu.entry_name, "main"))
        if not func_type:
            return

        # Delegate to emitter
        self.state.emitter.declarations.emit_main_wrapper(self.state.analysis.cu.entry_name, func_type)

    def _iter_body_stmts(self, stmt: Stmt | None):
        """Yield every statement reachable from stmt, recursing into block-bearing nodes.

        Args:
            stmt: The root statement (or None).

        Returns:
            An iterator over every `Stmt` in the sub-tree, including `stmt` itself.
        """
        if stmt is None:
            return
        yield stmt
        if isinstance(stmt, Block):
            for s in stmt.stmts:
                yield from self._iter_body_stmts(s)
        elif isinstance(stmt, IfStmt):
            yield from self._iter_body_stmts(stmt.then_stmt)
            yield from self._iter_body_stmts(stmt.else_stmt)
        elif isinstance(stmt, WhileStmt):
            yield from self._iter_body_stmts(stmt.body)
        elif isinstance(stmt, ForStmt):
            yield from self._iter_body_stmts(stmt.init)
            yield from self._iter_body_stmts(stmt.update)
            yield from self._iter_body_stmts(stmt.body)
        elif isinstance(stmt, MatchStmt):
            for arm in stmt.arms:
                yield from self._iter_body_stmts(arm.body)
        elif isinstance(stmt, WithStmt):
            for item in stmt.items:
                yield from self._iter_body_stmts(item.init)
                yield from self._iter_body_stmts(item.cleanup)
            yield from self._iter_body_stmts(stmt.body)
            yield from self._iter_body_stmts(stmt.cleanup_body)
        elif isinstance(stmt, CaseStmt):
            for arm in stmt.arms:
                yield from self._iter_body_stmts(arm.body)
            if stmt.else_arm is not None:
                yield from self._iter_body_stmts(stmt.else_arm.body)

    def _collect_reassigned_arc_params(self, decl: FuncDecl, func_type: FuncType) -> set:
        """Collect the names of ARC-typed parameters reassigned syntactically in the body.

        Any function whose body contains an ``AssignStmt`` whose target is a bare
        ``VarRef`` naming an ARC-typed parameter needs a defensive retain on that
        parameter at entry.

        Args:
            decl: The FuncDecl AST node.
            func_type: The resolved FuncType for the declaration.

        Returns:
            Set of parameter names (source names, not mangled) to retain at entry.
        """
        arc_params = {
            param.name
            for param, ptype in zip(decl.params, func_type.params)
            if self.state.analysis.has_arc_data(ptype)
        }
        if not arc_params:
            return set()

        hits = set()
        for stmt in self._iter_body_stmts(decl.body):
            if isinstance(stmt, AssignStmt) and isinstance(stmt.target, VarRef):
                name = stmt.target.name
                if name in arc_params:
                    hits.add(name)
        return hits
