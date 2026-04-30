#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""L0 Code Generation Backend.

Orchestrates code generation from a fully-analyzed L0 compilation unit.

This backend is language-agnostic - it handles the "WHAT" and "WHEN" of code generation,
while delegating the "HOW" to a pluggable emitter (e.g., CEmitter for C99 output).

Responsibilities:
- Manage compilation unit structure and dependency ordering
- Resolve types, symbols, and scopes
- Track variable lifetimes and schedule cleanup
- Coordinate with emitter for target-specific code generation

The backend contains zero knowledge of target language syntax.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, NoReturn, Tuple, Any

from l0_analysis import AnalysisResult, VarRefResolution
from l0_ast import (
    FuncDecl, StructDecl, EnumDecl, EnumVariant, LetDecl,
    Stmt, Block, LetStmt, AssignStmt, ExprStmt, IfStmt, WhileStmt, ReturnStmt, DropStmt, MatchStmt, CaseStmt, Expr,
    IntLiteral, StringLiteral, BoolLiteral, VarRef, UnaryOp, BinaryOp, CallExpr, IndexExpr,
    FieldAccessExpr, ParenExpr, CastExpr, VariantPattern, WildcardPattern, NullLiteral, TypeExpr, TryExpr, NewExpr,
    BreakStmt, ContinueStmt, ForStmt, ByteLiteral, WithStmt,
)
from l0_c_emitter import CEmitter
from l0_internal_error import InternalCompilerError, ICELocation
from l0_logger import log_debug, log_stage
from l0_name_resolver import Symbol, SymbolKind
from l0_resolve import resolve_symbol, resolve_type_ref
from l0_scope_context import ScopeContext
from l0_types import (
    Type, BuiltinType, StructType, EnumType, PointerType, NullableType, FuncType, format_type,
)


@dataclass
class Backend:
    """Language-agnostic code generation backend.

    Orchestrates code generation by:
    - Managing compilation unit structure and emission order.
    - Resolving types and symbols.
    - Tracking variable scopes and lifetimes.
    - Scheduling cleanup operations.
    - Delegating all target-specific code emission to the emitter.

    The backend decides WHAT to emit and WHEN, but not HOW (that's the emitter's job).
    This allows the same backend logic to work with different emitters (C, LLVM IR, WASM, etc.).

    Attributes:
        analysis: Full front-end analysis result.
        emitter: Target-specific emitter (handles all code emission).
        current_module: Name of the module currently being processed.
    """

    analysis: AnalysisResult

    # Target-specific emitter (handles all code emission)
    emitter: CEmitter = field(default_factory=CEmitter)

    # Name mangling state
    current_module: Optional[str] = None

    # Current function return type (for return statement type checking)
    _current_func_result: Optional[Type] = None

    # Scope tracking for string cleanup
    _current_scope: Optional[ScopeContext] = None

    # Stack of (continue_cleanup_scope, break_cleanup_scope) for loops
    _loop_cleanup_scope_stack: List[Tuple[ScopeContext, ScopeContext]] = field(default_factory=list)

    # Nesting depth inside C switch statements (match/case)
    _switch_depth: int = 0

    # Stack of (break_label, continue_label) for loops — used for goto case inside switch
    _loop_label_stack: List[Tuple[str, str]] = field(default_factory=list)

    # Counter for generating unique labels
    _label_counter: int = 0

    # Track if next statement is unreachable (after return)
    _next_stmt_unreachable: bool = False

    def __post_init__(self):
        """Initialize emitter with analysis data."""
        self.emitter.set_analysis(self.analysis)

    def _fresh_label(self, prefix: str) -> str:
        """Generate a unique C label name.

        Args:
            prefix: Prefix for the label name.

        Returns:
            A unique label string.
        """
        self._label_counter += 1
        return f"__{prefix}_{self._label_counter}"

    def _push_scope(self) -> ScopeContext:
        """Enter a new scope.

        Returns:
            The newly created ScopeContext.
        """
        new_scope = ScopeContext(parent=self._current_scope)
        self._current_scope = new_scope
        return new_scope

    def _pop_scope(self) -> None:
        """Exit current scope.

        Raises:
            InternalCompilerError: If there is no current scope to pop.
        """
        if self._current_scope is None:
            self.ice("[ICE-1330] scope underflow")
        self._current_scope = self._current_scope.parent

    def _types_equal(self, a: Type, b: Type) -> bool:
        """Check if two types are structurally equal.

        Args:
            a: First type.
            b: Second type.

        Returns:
            True if types are equal, False otherwise.
        """
        if type(a) != type(b):
            # Different kinds of types
            return False
        if isinstance(a, BuiltinType) and isinstance(b, BuiltinType):
            return a.name == b.name
        if isinstance(a, PointerType) and isinstance(b, PointerType):
            return self._types_equal(a.inner, b.inner)
        if isinstance(a, NullableType) and isinstance(b, NullableType):
            return self._types_equal(a.inner, b.inner)
        if isinstance(a, StructType) and isinstance(b, StructType):
            return a.module == b.module and a.name == b.name
        if isinstance(a, EnumType) and isinstance(b, EnumType):
            return a.module == b.module and a.name == b.name
        return False

    def _is_int_assignable(self, typ) -> bool:
        """Check if a type is assignable to an integer.

        Args:
            typ: The type to check.

        Returns:
            True if it's an 'int' or 'byte' builtin type.
        """
        return typ in (BuiltinType("int"), BuiltinType("byte"))

    def _is_binary_op_enabled(self, typ) -> bool:
        """Check if a type supports binary operations.

        Currently only int, byte, and bool support binary operations.

        Args:
            typ: The type to check.

        Returns:
            True if binary operations are supported for the type.
        """
        if isinstance(typ, BuiltinType):
            return typ.name in ("int", "byte", "bool")
        return False

    def _is_place_expr(self, expr: Expr) -> bool:
        """Check if an expression refers to an existing binding.

        Args:
            expr: The expression to check.

        Returns:
            True if expr refers to an existing binding (retain on copy).
            False if expr produces a fresh value (ownership transfer, no retain).
        """
        if isinstance(expr, VarRef):
            return True
        if isinstance(expr, UnaryOp) and expr.op == "*":  # dereference
            return True
        if isinstance(expr, IndexExpr):
            return True
        if isinstance(expr, FieldAccessExpr):
            return True
        if isinstance(expr, ParenExpr):
            return self._is_place_expr(expr.inner)
        # CallExpr, literals, cast, etc. produce fresh values
        return False

    def _is_unwrap_cast_from_place(self, expr: Expr) -> bool:
        """Check if a cast expression still refers to an existing owner.

        Args:
            expr: The expression to check.

        Returns:
            True for casts whose source is a place.
        """
        if not isinstance(expr, CastExpr):
            return False
        return self._is_place_expr(expr.expr)

    def _needs_arc_temp(self, expr: Expr) -> bool:
        """Check if a non-place rvalue with ARC data needs temp materialization.

        String literals are static constants and don't need cleanup.

        Args:
            expr: The expression to check.

        Returns:
            True if temp materialization is needed.
        """
        if isinstance(expr, StringLiteral):
            return False
        return True

    def _should_materialize_arc_temp(self, expr: Expr, expr_type: Type) -> bool:
        """Check if an ARC expression should be hoisted to a cleanup temp.

        Args:
            expr: The expression to check.
            expr_type: The type of the expression.

        Returns:
            True if the expression should be materialized into a temporary.
        """
        return (
            self.analysis.has_arc_data(expr_type)
            and not self._is_place_expr(expr)
            and not self._is_unwrap_cast_from_place(expr)
            and self._needs_arc_temp(expr)
        )

    def _materialize_arc_temp(self, c_expr: str, expr_type: Type) -> str:
        """Materialize an ARC rvalue into a scope-owned temporary for automatic cleanup.

        Args:
            c_expr: The C expression string.
            expr_type: The type of the expression.

        Returns:
            The name of the generated temporary variable.
        """
        temp = self.emitter.fresh_tmp("arc")
        self.emitter.emit_temp_decl(self.emitter.emit_type(expr_type), temp, c_expr)
        self._current_scope.add_owned(temp, expr_type)
        return temp

    def _has_side_effects(self, expr: Expr) -> bool:
        """Check if the expression has side effects or contains function calls.

        Such expressions should be evaluated once and cached in a temporary to avoid
        multiple evaluation when used in contexts like assignment with ARC operations.

        Args:
            expr: The expression to check.

        Returns:
            True if the expression has potential side effects.
        """
        if isinstance(expr, (IntLiteral, ByteLiteral, StringLiteral, BoolLiteral, NullLiteral)):
            return False

        if isinstance(expr, VarRef):
            return False

        if isinstance(expr, CallExpr):
            return True  # Function calls always have potential side effects

        if isinstance(expr, NewExpr):
            return True  # Allocation has side effects

        if isinstance(expr, UnaryOp):
            return self._has_side_effects(expr.operand)

        if isinstance(expr, BinaryOp):
            return self._has_side_effects(expr.left) or self._has_side_effects(expr.right)

        if isinstance(expr, CastExpr):
            return self._has_side_effects(expr.expr)

        if isinstance(expr, ParenExpr):
            return self._has_side_effects(expr.inner)

        if isinstance(expr, FieldAccessExpr):
            return self._has_side_effects(expr.obj)

        if isinstance(expr, IndexExpr):
            return self._has_side_effects(expr.array) or self._has_side_effects(expr.index)

        if isinstance(expr, TryExpr):
            return self._has_side_effects(expr.expr)

        if isinstance(expr, TypeExpr):
            return False

        # Default: treat as having side effects to be safe
        return True

    def _lookup_local_var_type(self, var_name: str) -> Optional[Type]:
        """Look up a local variable's type in the current scope chain.

        Searches declared_vars (includes both locals and parameters).

        Args:
            var_name: The name of the variable to look up.

        Returns:
            The variable's Type, or None if not found.
        """
        mangled_name = self.emitter.mangle_identifier(var_name)
        scope = self._current_scope
        while scope is not None:
            for declared_name, declared_type in scope.declared_vars:
                if declared_name == mangled_name:
                    return declared_type
            scope = scope.parent
        return None

    def _lookup_owned_local_name(self, expr: VarRef) -> Optional[str]:
        """Return the mangled local name when a VarRef resolves to an owned local binding.

        Parameters are local VarRefs but are not owned by the callee, so they do not
        appear in owned_vars and return None.

        Args:
            expr: The variable reference expression.

        Returns:
            The mangled local name if it's an owned binding, otherwise None.
        """
        resolution = self.analysis.var_ref_resolution.get(id(expr))
        if resolution is not VarRefResolution.LOCAL:
            return None

        mangled_name = self.emitter.mangle_identifier(expr.name)
        scope = self._current_scope
        while scope is not None:
            for owned_name, _ in scope.owned_vars:
                if owned_name == mangled_name:
                    return mangled_name
            scope = scope.parent
        return None

    def _extract_value_type_dependencies(self, typ: Type) -> Set[Tuple[str, str]]:
        """Extract type dependencies for VALUE fields only.

        Value-type fields create dependencies (types must be fully defined).
        Pointer-type fields do NOT create dependencies (forward declarations suffice).

        Examples:
        - StructType("main", "Point") -> {("main", "Point")}
        - EnumType("main", "Status") -> {("main", "Status")}
        - PointerType(StructType("main", "Node")) -> {} (no dependency, forward decl works)
        - NullableType(PointerType(...)) -> {} (pointer-optional, no dependency)
        - NullableType(BuiltinType("int")) -> {} (value-optional of builtin, no dependency)
        - NullableType(StructType("main", "Point")) -> {("main", "Point")} (value-optional of struct)
        - BuiltinType("int") -> {} (no dependency)

        Args:
            typ: The type to extract dependencies from.

        Returns:
            Set of (module, name) tuples for types that must be defined first.
        """
        if isinstance(typ, PointerType):
            # Pointers don't create dependencies - forward declarations handle them
            return set()

        elif isinstance(typ, NullableType):
            # Nullable pointer (T*?) - no dependency
            if isinstance(typ.inner, PointerType):
                return set()
            # Value-optional of user type (T?) - depends on T
            return self._extract_value_type_dependencies(typ.inner)

        elif isinstance(typ, StructType):
            return {(typ.module, typ.name)}

        elif isinstance(typ, EnumType):
            return {(typ.module, typ.name)}

        elif isinstance(typ, BuiltinType):
            return set()

        elif isinstance(typ, FuncType):
            return set()

        else:
            # Unknown type - conservatively return no dependencies
            return set()

    def _build_type_dependency_graph(self) -> Dict[Tuple[str, str], Set[Tuple[str, str]]]:
        """Build dependency graph for type definitions.

        A type X depends on type Y if X has a VALUE field of type Y.
        Pointer fields do NOT create dependencies (forward declarations handle them).

        Returns:
            Dict mapping (module, type_name) -> Set of (module, type_name) dependencies.
        """
        graph = {}

        # Process all structs
        for (mod_name, struct_name), struct_info in self.analysis.struct_infos.items():
            key = (mod_name, struct_name)
            deps = set()

            for field in struct_info.fields:
                field_deps = self._extract_value_type_dependencies(field.type)
                deps.update(field_deps)

            graph[key] = deps

        # Process all enums
        for (mod_name, enum_name), enum_info in self.analysis.enum_infos.items():
            key = (mod_name, enum_name)
            deps = set()

            for variant_info in enum_info.variants.values():
                for field_type in variant_info.field_types:
                    field_deps = self._extract_value_type_dependencies(field_type)
                    deps.update(field_deps)

            graph[key] = deps

        return graph

    def _find_cycle_details(
            self,
            graph: Dict[Tuple[str, str], Set[Tuple[str, str]]],
            unresolved: List[Tuple[str, str]]
    ) -> str:
        """Find and format cycle details for error message.

        Args:
            graph: The type dependency graph.
            unresolved: List of unresolved nodes.

        Returns:
            A string describing the detected cycle details.
        """
        # Simple approach: list unresolved nodes and their dependencies
        details = []
        for node in unresolved[:5]:  # Limit to first 5 for readability
            deps = [f"{m}::{n}" for m, n in graph.get(node, set()) if (m, n) in unresolved]
            node_str = f"{node[0]}::{node[1]}"
            if deps:
                details.append(f"{node_str} -> {', '.join(deps)}")
            else:
                details.append(node_str)

        return "; ".join(details)

    def _topological_sort(
            self,
            graph: Dict[Tuple[str, str], Set[Tuple[str, str]]]
    ) -> List[Tuple[str, str]]:
        """Perform topological sort on type dependency graph using Kahn's algorithm.

        Args:
            graph: The type dependency graph.

        Returns:
            List of (module, type_name) in dependency order (dependencies first).

        Raises:
            InternalCompilerError: On cycles (value-type cycles are impossible in valid L0).
        """
        from collections import deque

        # Calculate in-degree for each node (number of dependencies)
        # Nodes with in-degree 0 have no dependencies and can be emitted first
        in_degree = {node: len(graph[node]) for node in graph}

        # Start with nodes that have no dependencies
        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            # Reduce in-degree of dependents
            for dependent in graph:
                if node in graph[dependent]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        # Check for cycles
        if len(result) != len(graph):
            # Find nodes involved in cycle for error message
            unresolved = [node for node in graph if node not in result]
            cycle_details = self._find_cycle_details(graph, unresolved)
            self.ice(
                f"[ICE-1340] Value-type cycle detected in type definitions: {cycle_details}. "
                f"This indicates either a compiler bug or an invalid type checker state."
            )

        return result

    def _find_struct_decl(self, module_name: str, struct_name: str) -> Optional[StructDecl]:
        """Find the StructDecl AST node for a given struct.

        Args:
            module_name: Name of the module.
            struct_name: Name of the struct.

        Returns:
            The StructDecl if found, otherwise None.
        """
        module = self.analysis.cu.modules.get(module_name)
        if not module:
            return None

        for decl in module.decls:
            if isinstance(decl, StructDecl) and decl.name == struct_name:
                return decl

        return None

    def _find_enum_decl(self, module_name: str, enum_name: str) -> Optional[EnumDecl]:
        """Find the EnumDecl AST node for a given enum.

        Args:
            module_name: Name of the module.
            enum_name: Name of the enum.

        Returns:
            The EnumDecl if found, otherwise None.
        """
        module = self.analysis.cu.modules.get(module_name)
        if not module:
            return None

        for decl in module.decls:
            if isinstance(decl, EnumDecl) and decl.name == enum_name:
                return decl

        return None

    def generate(self) -> str:
        """Main entry point: generate complete C source for the compilation unit.

        Returns:
            C source code as a string.

        Raises:
            ValueError: If there is no compilation unit or if there are semantic errors.
        """
        log_stage(self.analysis.context, "Generating C code")
        if self.analysis.cu is None:
            raise ValueError("Cannot generate code without a compilation unit")

        if self.analysis.has_errors():
            raise ValueError("Cannot generate code with semantic errors")

        log_debug(self.analysis.context, "Preparing optional wrapper types")
        # Prepare optional wrapper types
        self.emitter.prepare_optional_wrappers()

        log_debug(self.analysis.context, "Emitting header and forward declarations")
        # Emit header and forward declarations
        self.emitter.emit_header()
        self.emitter.emit_forward_decls()

        # Value-optionals of builtins (int?, bool?, string?) must exist before structs that use them.
        self.emitter.emit_section_comment("Optional wrapper types (builtins / early)")
        self.emitter.emit_optional_wrappers(early=True)

        # Emit type definitions in dependency order
        # Build dependency graph and topologically sort to handle both:
        # - structs that contain enum values (need enum defined first)
        # - enums that contain struct values (need struct defined first)
        self.emitter.emit_section_comment("Type definitions (dependency-ordered)")
        dep_graph = self._build_type_dependency_graph()
        sorted_types = self._topological_sort(dep_graph)

        # Emit types in dependency order
        for module_name, type_name in sorted_types:
            if (module_name, type_name) in self.analysis.struct_infos:
                struct_decl = self._find_struct_decl(module_name, type_name)
                struct_info = self.analysis.struct_infos[(module_name, type_name)]
                if struct_decl:
                    self.current_module = module_name
                    self.emitter.current_module = module_name
                    self.emitter.emit_struct(module_name, struct_decl, struct_info)
                    self.emitter.emit_optional_wrapper_for_defined_type(StructType(module_name, type_name))
            elif (module_name, type_name) in self.analysis.enum_infos:
                enum_decl = self._find_enum_decl(module_name, type_name)
                enum_info = self.analysis.enum_infos[(module_name, type_name)]
                if enum_decl:
                    self.current_module = module_name
                    self.emitter.current_module = module_name
                    self.emitter.emit_enum(module_name, enum_decl, enum_info)
                    self.emitter.emit_optional_wrapper_for_defined_type(EnumType(module_name, type_name))

        # Value-optionals of user-defined structs/enums (if any)
        self.emitter.emit_section_comment("Optional wrapper types (late)")
        self.emitter.emit_optional_wrappers(early=False)

        # Emit top-level let declarations (module-level constants/variables)
        self._emit_let_declarations()

        # Emit function declarations and definitions
        self._emit_function_declarations()
        self._emit_function_definitions()

        # Emit C main() wrapper if entry module has a main function
        self._emit_main_wrapper_if_needed()

        return self.emitter.out.to_string()

    # -------------------------------------------------------------------------
    # Internal compiler error handling
    # -------------------------------------------------------------------------

    def ice(self, message: str, *, node=None) -> NoReturn:
        """Raise an internal compiler error.

        Args:
            message: The error message.
            node: Optional AST node associated with the error.

        Raises:
            InternalCompilerError: Always raised with the provided message and location.
        """
        filename = None
        if self.current_module and self.analysis.cu is not None:
            mod = self.analysis.cu.modules.get(self.current_module)
            if mod is not None:
                filename = mod.filename
        span = getattr(node, "span", None) if node is not None else None
        raise InternalCompilerError(message, ICELocation(filename=filename, span=span))

    def _expect_expr_type(self, expr) -> Type:
        """Look up an expression's type and fail if missing.

        Args:
            expr: The expression to look up.

        Returns:
            The resolved Type of the expression.

        Raises:
            InternalCompilerError: If the type is missing from the analysis.
        """
        ty = self.analysis.expr_types.get(id(expr))
        if ty is None:
            self.ice("[ICE-1310] missing inferred type for expression", node=expr)
        return ty

    def _emit_line_directive(self, node) -> None:
        """Emit #line directive if node has span info and context allows it.

        Args:
            node: The AST node containing span information.
        """
        self.emitter.emit_line_directive(node, self.current_module)

    # -------------------------------------------------------------------------
    # Top-level let declarations
    # -------------------------------------------------------------------------

    def _emit_let_declarations(self) -> None:
        """Emit static global variables for top-level let declarations."""
        if not self.analysis.let_types:
            return  # No let declarations to emit

        self.emitter.emit_section_comment("Top-level let declarations")

        for module in self.analysis.cu.modules.values():
            self.current_module = module.name
            self.emitter.current_module = module.name
            module_has_lets = False

            for decl in module.decls:
                if isinstance(decl, LetDecl):
                    if not module_has_lets:
                        self.emitter.emit_module_comment(module.name)
                        module_has_lets = True
                    self._emit_let_declaration(module.name, decl)

    def _emit_let_declaration(self, module_name: str, decl: LetDecl) -> None:
        """Emit a single top-level let declaration as a static variable.

        Args:
            module_name: Name of the module containing the declaration.
            decl: The LetDecl AST node.
        """
        # Get the resolved type
        let_type = self.analysis.let_types.get((module_name, decl.name))
        if not let_type:
            # If type is not resolved yet, skip
            return

        # Delegate to emitter with callback for initializer
        self.emitter.emit_let_declaration(module_name, decl, let_type, self._emit_let_initializer)

    def _emit_let_initializer(self, expr: Expr, expected_type: Type) -> str:
        """Generate C initializer expression for a top-level let.

        Supports compile-time constant literals and struct/enum construction.

        Args:
            expr: The initializer expression.
            expected_type: The expected type of the constant.

        Returns:
            A C initializer expression string.

        Raises:
            InternalCompilerError: If the initializer is not constant or supported.
        """
        if isinstance(expr, IntLiteral):
            return self.emitter.emit_int_literal(expr.value)
        elif isinstance(expr, BoolLiteral):
            return self.emitter.emit_const_bool_literal(expr.value)
        elif isinstance(expr, ByteLiteral):
            return self.emitter.emit_byte_literal(expr.value)
        elif isinstance(expr, StringLiteral):
            return self.emitter.emit_const_string_literal(expr.value)
        elif isinstance(expr, NullLiteral):
            return self.emitter.emit_null_literal(expected_type, for_initializer=True)
        elif isinstance(expr, VarRef):
            return self._emit_bare_variant_static_initializer(expr, expected_type)
        elif isinstance(expr, CallExpr) and isinstance(expr.callee, VarRef):
            # Struct or enum variant construction: Point(1, 2) or Color.Red
            return self._emit_const_constructor(expr, expected_type)
        elif isinstance(expr, NewExpr):
            # Heap allocation not allowed in top-level let initializers
            self.ice(
                f"[ICE-1180] new expressions not allowed in top-level let initializers (use value construction instead)",
                node=expr)
        else:
            # Unsupported initializer
            self.ice(f"[ICE-1181] unsupported top-level let initializer: {type(expr).__name__}", node=expr)

    def _emit_bare_variant_static_initializer(self, expr: VarRef, expected_type: Type) -> str:
        """Emit a bare zero-argument enum variant for static initialization."""
        if not self.current_module:
            self.ice("[ICE-1030] current_module not set during bare variant let initialization", node=expr)
        if not isinstance(expected_type, EnumType):
            self.ice("[ICE-1033] bare enum variant initializer expected enum type", node=expr)

        sym = self._lookup_symbol(expr.name, self.current_module, module_path=expr.module_path)
        if sym is None:
            self.ice(f"[ICE-1031] unknown bare variant name: {expr.name}", node=expr)
        if sym.kind != SymbolKind.ENUM_VARIANT:
            self.ice(f"[ICE-1034] VarRef is not an enum variant constructor", node=expr)

        variant_decl = self.find_variant_decl(expected_type.module, expected_type.name, sym.name)
        if variant_decl is None:
            self.ice(f"[ICE-1052] missing variant decl for {expected_type.module}.{expected_type.name}.{sym.name}",
                     node=expr)
        if variant_decl is not sym.node:
            self.ice(f"[ICE-1033] bare enum variant does not belong to expected enum type", node=expr)
        if len(variant_decl.fields) != 0:
            self.ice(f"[ICE-1053] bare enum variant initializer requires zero payload fields", node=expr)

        return self.emitter.emit_variant_static_initializer_for_type(expected_type, sym.name, [])

    def _emit_const_constructor(self, expr: CallExpr, expected_type: Type) -> str:
        """Emit a constant struct or enum constructor for static initialization.

        Similar to _try_emit_constructor but only handles constant expressions.

        Args:
            expr: The constructor call expression.
            expected_type: The expected struct or enum type.

        Returns:
            A C initializer string.

        Raises:
            InternalCompilerError: If symbol or constructor type is invalid.
        """
        assert isinstance(expr.callee, VarRef)
        name = expr.callee.name

        # Look up the symbol
        if not self.current_module:
            self.ice("[ICE-1030] current_module not set during let initialization", node=expr)

        sym = self._lookup_symbol(name, self.current_module, module_path=expr.callee.module_path)
        if sym is None:
            self.ice(f"[ICE-1031] unknown constructor name: {name}", node=expr)

        # Struct constructor
        if sym.kind == SymbolKind.STRUCT or (
                sym.kind == SymbolKind.TYPE_ALIAS and isinstance(expected_type, StructType)):
            if isinstance(expected_type, StructType):
                return self._emit_const_struct_constructor(expr, expected_type)
            self.ice(f"[ICE-1032] struct constructor but expected_type is not StructType", node=expr)

        # Enum variant constructor
        elif sym.kind == SymbolKind.ENUM_VARIANT:
            if isinstance(expected_type, EnumType):
                return self._emit_const_variant_constructor(expr, expected_type)
            self.ice(f"[ICE-1033] enum variant constructor but expected_type is not EnumType", node=expr)

        else:
            self.ice(f"[ICE-1034] CallExpr is not a constructor", node=expr)

    def _emit_const_struct_constructor(self, expr: CallExpr, struct_type: StructType) -> str:
        """Emit constant struct constructor for static initialization.

        Args:
            expr: The constructor call expression.
            struct_type: The struct type.

        Returns:
            A C struct initializer string.

        Raises:
            InternalCompilerError: If struct info is missing or argument count mismatches.
        """
        # Look up struct info to get field names and types
        info = self.analysis.struct_infos.get((struct_type.module, struct_type.name))
        if info is None:
            self.ice(f"[ICE-1040] missing StructInfo for {struct_type.module}.{struct_type.name}", node=expr)

        if len(info.fields) != len(expr.args):
            self.ice(
                f"[ICE-1041] argument count mismatch in struct constructor: expected {len(info.fields)}, got {len(expr.args)}",
                node=expr)

        # Prepare field initializers with constant expressions as (name, value) tuples
        field_inits = []
        for field, arg in zip(info.fields, expr.args):
            # Recursively emit constant initializer for each argument
            c_arg = self._emit_let_initializer(arg, field.type)
            field_inits.append((field.name, c_arg))

        # File-scope static initializers must use brace-only initializers; nested
        # compound literals are rejected by gcc under strict C99 here.
        return self.emitter.emit_struct_static_initializer_for_type(struct_type, field_inits)

    def _emit_const_variant_constructor(self, expr: CallExpr, enum_type: EnumType) -> str:
        """Emit constant enum variant constructor for static initialization.

        Args:
            expr: The variant call expression.
            enum_type: The enum type.

        Returns:
            A C enum variant initializer string.

        Raises:
            InternalCompilerError: If variant info or declaration is missing.
        """
        assert isinstance(expr.callee, VarRef)
        variant_name = expr.callee.name

        # Look up variant info
        enum_info = self.analysis.enum_infos.get((enum_type.module, enum_type.name))
        if enum_info is None:
            self.ice(f"[ICE-1050] missing EnumInfo for {enum_type.module}.{enum_type.name}", node=expr)

        variant_info = enum_info.variants.get(variant_name)
        if variant_info is None:
            self.ice(f"[ICE-1051] missing VariantInfo for {variant_name}", node=expr)

        # Empty variant (no payload)
        if len(variant_info.field_types) == 0:
            return self.emitter.emit_variant_static_initializer_for_type(enum_type, variant_name, [])

        # Get field names from AST
        variant_decl = self.find_variant_decl(enum_type.module, enum_type.name, variant_name)
        if variant_decl is None:
            self.ice(f"[ICE-1052] missing variant decl for {enum_type.module}.{enum_type.name}.{variant_name}",
                     node=expr)

        if len(variant_decl.fields) != len(expr.args):
            self.ice(f"[ICE-1053] arity mismatch in variant constructor {variant_name}", node=expr)

        # Prepare payload initializers with constant expressions as (name, value) tuples
        payload_inits = []
        for idx, (field, arg) in enumerate(zip(variant_decl.fields, expr.args)):
            # Recursively emit constant initializer for each argument
            c_arg = self._emit_let_initializer(arg, variant_info.field_types[idx])
            payload_inits.append((field.name, c_arg))

        return self.emitter.emit_variant_static_initializer_for_type(enum_type, variant_name, payload_inits)

    # -------------------------------------------------------------------------
    # Function declarations and definitions
    # -------------------------------------------------------------------------

    def _emit_function_declarations(self) -> None:
        """Emit forward declarations for all functions."""
        self.emitter.emit_section_comment("Function declarations")

        for module in self.analysis.cu.modules.values():
            self.current_module = module.name
            self.emitter.current_module = module.name
            self.emitter.emit_module_comment(module.name)

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
        func_type = self.analysis.func_types.get((module_name, decl.name))
        if not func_type:
            self.ice(f"[ICE-1150] missing FuncType for {module_name}.{decl.name}", node=decl)

        # Delegate to emitter
        self.emitter.emit_function_declaration(module_name, decl, func_type)

    def _emit_function_definitions(self) -> None:
        """Emit function definitions (bodies)."""
        self.emitter.emit_section_comment("Function definitions")

        for module in self.analysis.cu.modules.values():
            self.current_module = module.name
            self.emitter.current_module = module.name
            self.emitter.emit_module_separator(module.name)

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
        if self._current_scope is not None:
            self.ice(f"[ICE-1160] scope not reset before function {module_name}.{decl.name}")

        self._emit_line_directive(decl)

        func_type = self.analysis.func_types.get((module_name, decl.name))
        if not func_type:
            return

        # Emit function header via emitter
        self.emitter.emit_function_definition_header(module_name, decl, func_type)

        # Set up function scope (backend responsibility)
        func_scope = self._push_scope()
        self._next_stmt_unreachable = False

        # An ARC-typed parameter reassigned anywhere in the body is defensively
        # retained on entry and registered as owned, so the scope-exit release
        # balances the entry retain on every control-flow path.
        reassigned = self._collect_reassigned_arc_params(decl, func_type)
        for param, ptype in zip(decl.params, func_type.params):
            c_param_name = self.emitter.mangle_identifier(param.name)
            if param.name in reassigned:
                self._emit_retain_for_copied_value(c_param_name, ptype)
                func_scope.add_owned(c_param_name, ptype)
            else:
                func_scope.add_declared(c_param_name, ptype)

        # Emit body (backend responsibility - statement emission)
        saved = self._current_func_result
        self._current_func_result = func_type.result
        try:
            self._emit_block_sequence(decl.body, module_name)
        finally:
            self._current_func_result = saved

        # Cleanup if function falls through (void functions / missing return)
        if not self._next_stmt_unreachable:
            self._emit_cleanup_at_scope_exit(func_scope)

        self._pop_scope()

        # Emit function footer via emitter
        self.emitter.emit_function_definition_footer()

    def _emit_main_wrapper_if_needed(self) -> None:
        """If the entry module has a main function, emit a C main() wrapper.

        This allows us to consistently mangle all L0 functions (including main)
        while still providing the expected C entry point.
        """
        if not self.analysis.cu.entry_name:
            return

        entry_env = self.analysis.module_envs.get(self.analysis.cu.entry_name)
        if not entry_env:
            return

        main_symbol = entry_env.locals.get("main")
        if not main_symbol or main_symbol.kind != SymbolKind.FUNC:
            return

        # Get the function type to determine return type
        func_type = self.analysis.func_types.get((self.analysis.cu.entry_name, "main"))
        if not func_type:
            return

        # Delegate to emitter
        self.emitter.emit_main_wrapper(self.analysis.cu.entry_name, func_type)

    # -------------------------------------------------------------------------
    # Cleanup helpers
    # -------------------------------------------------------------------------

    def _scope_chain_has_cleanup(self) -> bool:
        """Check if any scope in the chain has cleanup requirements.

        Returns:
            True if any scope has a with-cleanup or owned ARC variables.
        """
        scope = self._current_scope
        while scope is not None:
            if ((scope.with_cleanup_block is not None or scope.with_cleanup_inline)
                    and not scope.with_cleanup_in_progress):
                return True
            for _, var_type in scope.owned_vars:
                if self.analysis.has_arc_data(var_type):
                    return True
            scope = scope.parent
        return False

    def _emit_cleanup_for_return(self, returned_var: Optional[str] = None) -> None:
        """Emit cleanup logic for a return statement.

        Walks up scope chain, executes any with-statement cleanup data,
        then cleans ALL owned variables (except return value).
        The with-cleanup runs first because user cleanup code may reference
        variables whose owned resources (e.g. string refcounts) are released
        by the automatic owned-var cleanup.

        Args:
            returned_var: Mangled name of variable being returned (to skip cleanup).
        """
        scope = self._current_scope
        while scope is not None:
            if (
                    (scope.with_cleanup_block is not None or scope.with_cleanup_inline)
                    and not scope.with_cleanup_in_progress
            ):
                scope.with_cleanup_in_progress = True
                try:
                    self._emit_with_cleanup_from_scope(scope, self.current_module)
                finally:
                    scope.with_cleanup_in_progress = False
            for var_name, var_type in reversed(scope.owned_vars):
                if var_name == returned_var:
                    continue  # Don't clean the return value
                if self.analysis.has_arc_data(var_type):
                    self._emit_value_cleanup(var_name, var_type)
            scope = scope.parent

    def _emit_cleanup_for_loop_exit(self, *, is_break: bool) -> None:
        """Emit cleanup for break/continue.

        Walks from current scope up to and including the innermost loop cleanup target,
        executing any with-statement cleanup data along the way.
        The with-cleanup runs before owned-var cleanup (see
        ``_emit_cleanup_for_return`` for rationale).

        Args:
            is_break: True if cleaning for 'break', False for 'continue'.

        Raises:
            InternalCompilerError: If called outside of a loop.
        """
        if not self._loop_cleanup_scope_stack:
            # Shouldn't happen if semantic analysis caught it
            self.ice("[ICE-1020] break/continue outside of loop")

        continue_scope, break_scope = self._loop_cleanup_scope_stack[-1]
        target_scope = break_scope if is_break else continue_scope

        scope = self._current_scope
        while scope is not None:
            if (
                    (scope.with_cleanup_block is not None or scope.with_cleanup_inline)
                    and not scope.with_cleanup_in_progress
            ):
                scope.with_cleanup_in_progress = True
                try:
                    self._emit_with_cleanup_from_scope(scope, self.current_module)
                finally:
                    scope.with_cleanup_in_progress = False
            for var_name, var_type in reversed(scope.owned_vars):
                if self.analysis.has_arc_data(var_type):
                    self._emit_value_cleanup(var_name, var_type)

            if scope is target_scope:
                break  # Stop after cleaning the selected loop scope itself

            scope = scope.parent

    def _emit_cleanup_at_scope_exit(self, scope: ScopeContext) -> None:
        """Emit cleanup at scope exit.

        Only cleans variables declared in THIS scope that have owned fields.

        Args:
            scope: The scope being exited.
        """
        for var_name, var_type in reversed(scope.owned_vars):
            if self.analysis.has_arc_data(var_type):
                self._emit_value_cleanup(var_name, var_type)

    def _emit_with_cleanup_from_scope(self, scope: ScopeContext, module_name: str) -> None:
        """Emit with-statement cleanup for a scope.

        Args:
            scope: The scope containing cleanup logic.
            module_name: Name of current module.
        """
        if scope.with_cleanup_block is None and not scope.with_cleanup_inline:
            return

        old_with_cleanup_in_progress = scope.with_cleanup_in_progress
        scope.with_cleanup_in_progress = True
        try:
            # Wrap in a nested block so cleanup declarations get their own C scope
            # (mirrors L0 scoping rules and isolates inline cleanup statements).
            self.emitter.emit_block_start()
            cleanup_scope = self._push_scope()
            if scope.with_cleanup_block is not None:
                self._emit_block_sequence(scope.with_cleanup_block, module_name)
            else:
                for stmt in scope.with_cleanup_inline or []:
                    self._emit_stmt(stmt, module_name)
            if not self._next_stmt_unreachable:
                self._emit_cleanup_at_scope_exit(cleanup_scope)
            self._pop_scope()
            self.emitter.emit_block_end()
        finally:
            scope.with_cleanup_in_progress = old_with_cleanup_in_progress

    def _emit_value_cleanup(self, c_expr: str, ty: Type) -> None:
        """Emit cleanup code for a by-value variable before reassignment.

        Similar to _emit_field_cleanup, but expects c_expr to be a direct
        value reference (not a pointer), so uses '.' instead of '->'.

        Args:
            c_expr: C expression for the value (e.g., "x__v", "obj.field")
            ty: The type of the value being cleaned up
        """
        self.emitter.emit_value_cleanup(c_expr, ty)

    def _emit_struct_cleanup(self, c_ptr_expr: str, struct_type: StructType) -> None:
        """Emit cleanup code for all owned fields in a struct.

        Recursively handles nested structs (by-value fields).

        Args:
            c_ptr_expr: C expression evaluating to a pointer to the struct.
            struct_type: The struct type.
        """
        self.emitter.emit_struct_cleanup(c_ptr_expr, struct_type)

    def _emit_enum_cleanup(self, c_ptr_expr: str, enum_type: EnumType) -> None:
        """Emit cleanup code for owned fields in an enum's active variant.

        Uses switch on tag to only clean up the fields that are actually present.

        Args:
            c_ptr_expr: C expression evaluating to a pointer to the enum.
            enum_type: The enum type.
        """
        self.emitter.emit_enum_cleanup(c_ptr_expr, enum_type)

    # -------------------------------------------------------------------------
    # Statement emission
    # -------------------------------------------------------------------------

    def _emit_block_sequence(self, block: Block, module_name: str) -> None:
        """Emit statements in a block.

        Args:
            block: The Block AST node.
            module_name: Name of current module.
        """
        for stmt in block.stmts:
            self._emit_stmt(stmt, module_name)

        return None

    def _emit_stmt(self, stmt: Stmt, module_name: str) -> None:
        """Emit a single statement.

        Args:
            stmt: The Stmt AST node.
            module_name: Name of current module.

        Raises:
            InternalCompilerError: If statement type is unsupported.
        """

        self._emit_line_directive(stmt)

        if self._next_stmt_unreachable:
            self.emitter.emit_unreachable_comment()

        # Handle different statement types:
        if isinstance(stmt, LetStmt):
            # let name: Type = expr; | let name = expr;
            return self._emit_let(stmt, module_name)

        elif isinstance(stmt, AssignStmt):
            # target = expr;
            return self._emit_reassignment(stmt)

        elif isinstance(stmt, ExprStmt):
            # expr;
            c_expr = self._emit_expr(stmt.expr, is_statement=True)
            if c_expr:  # Only emit if not empty (empty for no-op comments)
                expr_ty = self.analysis.expr_types.get(id(stmt.expr))
                if expr_ty and self._should_materialize_arc_temp(stmt.expr, expr_ty):
                    self._materialize_arc_temp(c_expr, expr_ty)
                else:
                    self.emitter.emit_expr_stmt(c_expr)
            return None

        elif isinstance(stmt, IfStmt):
            # if (expr) stmt [else stmt]
            return self._emit_if_else(stmt, module_name)


        elif isinstance(stmt, WhileStmt):
            # while (expr) { stmt... }
            return self._emit_while(stmt, module_name)

        elif isinstance(stmt, ForStmt):
            # for (init; cond; update) { stmt... }
            return self._emit_for(stmt, module_name)

        elif isinstance(stmt, ReturnStmt):
            # return [expr];
            return self._emit_return(stmt)

        elif isinstance(stmt, DropStmt):
            self._emit_drop(stmt, module_name)
            return None

        elif isinstance(stmt, MatchStmt):
            self._emit_match(stmt, module_name)
            return None

        elif isinstance(stmt, WithStmt):
            self._emit_with(stmt, module_name)
            return None

        elif isinstance(stmt, CaseStmt):
            self._emit_case(stmt, module_name)
            return None

        elif isinstance(stmt, Block):
            # { stmt... }
            return self._emit_block(stmt, module_name)

        elif isinstance(stmt, BreakStmt):
            # break;
            self._emit_cleanup_for_loop_exit(is_break=True)
            break_label, _ = self._loop_label_stack[-1]
            self.emitter.emit_goto(break_label)
            self._next_stmt_unreachable = True
            return None

        elif isinstance(stmt, ContinueStmt):
            # continue;
            self._emit_cleanup_for_loop_exit(is_break=False)
            _, continue_label = self._loop_label_stack[-1]
            self.emitter.emit_goto(continue_label)
            self._next_stmt_unreachable = True
            return None

        else:
            self.ice(f"[ICE-1250] unsupported statement type for code generation: {type(stmt).__name__}", node=stmt)

    def _emit_block(self, stmt: Block, module_name: str) -> Any:
        """Emit a block statement with its own scope.

        Args:
            stmt: The Block AST node.
            module_name: Name of current module.
        """
        self.emitter.emit_block_start()

        block_scope = self._push_scope()
        self._emit_block_sequence(stmt, module_name)

        # Emit cleanup only if code is reachable
        if not self._next_stmt_unreachable:
            self._emit_cleanup_at_scope_exit(block_scope)

        self._pop_scope()
        self.emitter.emit_block_end()
        return None

    def _emit_return(self, stmt: ReturnStmt) -> Any:
        """Emit a return statement with cleanup.

        Args:
            stmt: The ReturnStmt AST node.
        """
        if stmt.value is None:
            if self._current_scope is not None:
                self._emit_cleanup_for_return()
            self.emitter.emit_return_stmt(None)
        else:
            returned_var = None
            use_move_return = False
            if isinstance(stmt.value, VarRef):
                returned_var = self._lookup_owned_local_name(stmt.value)
                use_move_return = returned_var is not None

            emit_return_value = (
                self._emit_expr_with_expected_type
                if use_move_return
                else self._emit_owned_expr_with_expected_type
            )

            # Evaluate return expression first so ARC temps materialized during
            # expression emission are visible to cleanup scheduling.
            c_value = emit_return_value(stmt.value, self._current_func_result)

            needs_cleanup = (self._current_scope is not None
                             and self._scope_chain_has_cleanup())
            if needs_cleanup:
                # Keep return value alive across cleanup to avoid use-after-free.
                ret_tmp = self.emitter.fresh_tmp("ret")
                c_ret_type = self.emitter.emit_type(self._current_func_result)
                self.emitter.emit_temp_decl(c_ret_type, ret_tmp, c_value)
                self._emit_cleanup_for_return(returned_var)
                self.emitter.emit_return_stmt(ret_tmp)
            else:
                self.emitter.emit_return_stmt(c_value)

        # Mark subsequent code as unreachable
        self._next_stmt_unreachable = True
        return None

    def _emit_condition_branch(self, expr: Expr, true_label: str, false_label: str) -> None:
        """Emit control flow for one condition expression with short-circuit semantics.

        This path is used only for statement conditions so ARC temps emitted by
        expression lowering stay inside the correct structural block instead of
        being hoisted into an enclosing `if (...)` or `while (...)` header.

        Args:
            expr: Condition expression to lower.
            true_label: Jump target when the condition is true.
            false_label: Jump target when the condition is false.
        """
        if isinstance(expr, ParenExpr):
            self._emit_condition_branch(expr.inner, true_label, false_label)
            return

        if isinstance(expr, BinaryOp) and expr.op == "&&":
            rhs_label = self._fresh_label("cond_rhs")
            self._emit_condition_branch(expr.left, rhs_label, false_label)
            self.emitter.emit_label(rhs_label)
            self._emit_condition_branch(expr.right, true_label, false_label)
            return

        if isinstance(expr, BinaryOp) and expr.op == "||":
            rhs_label = self._fresh_label("cond_rhs")
            self._emit_condition_branch(expr.left, true_label, rhs_label)
            self.emitter.emit_label(rhs_label)
            self._emit_condition_branch(expr.right, true_label, false_label)
            return

        self.emitter.emit_block_start()
        leaf_scope = self._push_scope()
        c_cond = self._emit_condition_expr(expr)
        self.emitter.emit_if_header(c_cond)
        self.emitter.emit_block_start()
        self._emit_cleanup_at_scope_exit(leaf_scope)
        self.emitter.emit_goto(true_label)
        self.emitter.emit_block_end()
        self._emit_cleanup_at_scope_exit(leaf_scope)
        self._pop_scope()
        self.emitter.emit_block_end()
        self.emitter.emit_goto(false_label)

    def _emit_condition_expr(self, expr: Expr) -> str:
        """Emit a top-level condition expression for direct statement headers."""
        if isinstance(expr, ParenExpr):
            return self._emit_condition_expr(expr.inner)
        if isinstance(expr, BinaryOp):
            return self._emit_binary_op(expr, expr.op, expr.left, expr.right, for_condition=True)
        return self._emit_expr(expr)

    def _emit_condition_value(self, expr: Expr) -> str:
        """Evaluate a statement condition into a stable boolean temporary.

        The returned temp is safe to reference from an `if`/`while` header
        because any ARC temps created while evaluating the condition are scoped
        to the emitted condition block and cleaned before control continues.

        Args:
            expr: Condition expression to lower.

        Returns:
            Name of the generated boolean temp.
        """
        cond_tmp = self.emitter.fresh_tmp("cond")
        self.emitter.emit_temp_decl(
            self.emitter.emit_type(BuiltinType("bool")),
            cond_tmp,
            self.emitter.emit_bool_literal(False),
        )

        true_label = self._fresh_label("cond_true")
        false_label = self._fresh_label("cond_false")
        end_label = self._fresh_label("cond_end")

        self.emitter.emit_block_start()
        self._emit_condition_branch(expr, true_label, false_label)
        self.emitter.emit_label(true_label)
        self.emitter.emit_assignment(cond_tmp, self.emitter.emit_bool_literal(True))
        self.emitter.emit_goto(end_label)
        self.emitter.emit_label(false_label)
        self.emitter.emit_label(end_label)
        self.emitter.emit_block_end()
        return cond_tmp

    def _emit_while(self, stmt: WhileStmt, module_name: str) -> Any:
        """Emit a while loop.

        Args:
            stmt: The WhileStmt AST node.
            module_name: Name of current module.
        """
        break_label = self._fresh_label("lbrk")
        continue_label = self._fresh_label("lcont")
        self._loop_label_stack.append((break_label, continue_label))

        self.emitter.emit_while_header(self.emitter.emit_bool_literal(True))
        self.emitter.emit_block_start()

        c_cond = self._emit_condition_value(stmt.cond)
        self.emitter.emit_if_header(self.emitter.emit_negated_condition(c_cond))
        self.emitter.emit_block_start()
        self.emitter.emit_goto(break_label)
        self.emitter.emit_block_end()

        loop_scope = self._push_scope()
        self._loop_cleanup_scope_stack.append((loop_scope, loop_scope))

        self._emit_block_sequence(stmt.body, module_name)

        if not self._next_stmt_unreachable:
            self._emit_cleanup_at_scope_exit(loop_scope)

        self.emitter.emit_label(continue_label)

        self._loop_cleanup_scope_stack.pop()
        self._pop_scope()
        self.emitter.emit_block_end()

        self.emitter.emit_label(break_label)
        self._loop_label_stack.pop()
        self._next_stmt_unreachable = False
        return None

    def _emit_for(self, stmt: ForStmt, module_name: str) -> Any:
        """Emit a for loop.

        Args:
            stmt: The ForStmt AST node.
            module_name: Name of current module.
        """
        break_label = self._fresh_label("lbrk")
        continue_label = self._fresh_label("lcont")
        self._loop_label_stack.append((break_label, continue_label))

        outer_scope = self._push_scope()

        self.emitter.emit_for_loop_start()

        if stmt.init:
            self._emit_stmt(stmt.init, module_name)

        self.emitter.emit_while_header(self.emitter.emit_bool_literal(True))

        self.emitter.emit_block_start()
        if stmt.cond:
            c_cond = self._emit_condition_value(stmt.cond)
            self.emitter.emit_if_header(self.emitter.emit_negated_condition(c_cond))
            self.emitter.emit_block_start()
            self.emitter.emit_goto(break_label)
            self.emitter.emit_block_end()
        self.emitter.emit_block_start()
        loop_scope = self._push_scope()
        self._loop_cleanup_scope_stack.append((loop_scope, outer_scope))

        self._emit_block_sequence(stmt.body, module_name)
        body_fallthrough_reachable = not self._next_stmt_unreachable
        if body_fallthrough_reachable:
            self._emit_cleanup_at_scope_exit(loop_scope)

        self._loop_cleanup_scope_stack.pop()
        self._pop_scope()  # Pop loop_scope
        self.emitter.emit_block_end()

        self._next_stmt_unreachable = False
        self.emitter.emit_label(continue_label)

        if stmt.update:
            self._emit_stmt(stmt.update, module_name)

        self.emitter.emit_block_end()

        self._emit_cleanup_at_scope_exit(outer_scope)

        self._pop_scope()  # Pop outer_scope
        self.emitter.emit_for_loop_end()

        self.emitter.emit_label(break_label)
        self._loop_label_stack.pop()
        self._next_stmt_unreachable = False
        return None

    def _emit_if_else(self, stmt: IfStmt, module_name: str) -> Any:
        """Emit an if-else statement.

        Args:
            stmt: The IfStmt AST node.
            module_name: Name of current module.
        """
        c_cond = self._emit_condition_value(stmt.cond)
        self.emitter.emit_if_header(c_cond)

        self._next_stmt_unreachable = False  # Each branch starts reachable
        then_unreachable = self._gen_if_else_branch(stmt.then_stmt, module_name)

        if stmt.else_stmt:
            self.emitter.emit_else()
            self._next_stmt_unreachable = False  # Each branch starts reachable
            else_unreachable = self._gen_if_else_branch(stmt.else_stmt, module_name)
            # Unreachable after if-else only if BOTH branches are unreachable
            self._next_stmt_unreachable = then_unreachable and else_unreachable

        else:
            # No else: code after is always reachable (condition could be false)
            self._next_stmt_unreachable = False

        return None

    def _gen_if_else_branch(self, stmt: Stmt, module_name: str) -> bool:
        """Emit a branch of an if/else.

        Args:
            stmt: The statement in the branch.
            module_name: Name of current module.

        Returns:
            True if branch is unreachable at end.
        """
        if isinstance(stmt, Block):
            self._emit_block(stmt, module_name)
        else:
            wrapped = Block(stmts=[stmt], span=stmt.span)
            self._emit_block(wrapped, module_name)

        return self._next_stmt_unreachable

    def _iter_body_stmts(self, stmt: Optional[Stmt]):
        """Yield every statement reachable from stmt, recursing into block-bearing nodes.

        Args:
            stmt: The root statement (or None).

        Yields:
            Every Stmt in the sub-tree, including stmt itself.
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
            if self.analysis.has_arc_data(ptype)
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

    def _emit_reassignment(self, stmt: AssignStmt) -> None:
        """Emit an assignment statement.

        Args:
            stmt: The AssignStmt AST node.

        Raises:
            InternalCompilerError: If types are missing or emission fails.
        """
        # Resolve source and destination types
        src_ty = self.analysis.expr_types.get(id(stmt.value))
        dst_ty = self.analysis.expr_types.get(id(stmt.target))

        if src_ty is None or dst_ty is None:
            self.ice("[ICE-1240] missing inferred type for assignment", node=stmt)

        # Handle complex lvalues: if the target contains side effects (like function calls),
        # we must evaluate the pointer/object/index part ONCE to avoid multiple evaluation
        # during the release/assign/retain sequence for ARC types.
        c_target = self._emit_lvalue_with_caching(stmt.target)

        # Use _emit_expr_with_expected_type for type conversion
        c_value = self._emit_owned_expr_with_expected_type(stmt.value, dst_ty)
        if c_target is None or c_value is None:
            self.ice("[ICE-1241] failed to emit assignment", node=stmt)

        if self.analysis.has_arc_data(dst_ty):
            temp = self.emitter.fresh_tmp("tmp")
            self.emitter.emit_temp_decl(self.emitter.emit_type(dst_ty), temp, c_value)
            self._emit_value_cleanup(c_target, dst_ty)
            self.emitter.emit_assignment(c_target, temp)
        else:
            self.emitter.emit_assignment(c_target, c_value)

        return None

    def _emit_lvalue_with_caching(self, target: Expr) -> str:
        """Emit an lvalue expression, caching sub-expressions with side effects.

        For targets like `*(func_call())`, the pointer expression `func_call()` must
        be evaluated exactly once, not multiple times during release/assign/retain.

        Args:
            target: The lvalue expression.

        Returns:
            A C lvalue expression string.

        Raises:
            InternalCompilerError: If types are missing for complex lvalues.
        """
        # Case 1: Dereference with side effects in operand
        if isinstance(target, UnaryOp) and target.op == "*":
            if self._has_side_effects(target.operand):
                # Evaluate pointer expression once into a temporary
                ptr_ty = self.analysis.expr_types.get(id(target.operand))
                if ptr_ty is None:
                    self.ice("[ICE-1242] missing type for dereference operand", node=target.operand)
                ptr_temp = self.emitter.fresh_tmp("ptr")
                c_ptr_expr = self._emit_expr(target.operand)
                self.emitter.emit_temp_decl(self.emitter.emit_type(ptr_ty), ptr_temp, c_ptr_expr)
                return self.emitter.emit_deref_lvalue(ptr_temp)

        # Case 2: Field access with side effects in object expression
        if isinstance(target, FieldAccessExpr):
            if self._has_side_effects(target.obj):
                obj_ty = self.analysis.expr_types.get(id(target.obj))
                if obj_ty is None:
                    self.ice("[ICE-1243] missing type for field access object", node=target.obj)
                obj_temp = self.emitter.fresh_tmp("obj")
                c_obj_expr = self._emit_expr(target.obj)
                self.emitter.emit_temp_decl(self.emitter.emit_type(obj_ty), obj_temp, c_obj_expr)
                is_pointer = isinstance(obj_ty, PointerType)
                return self.emitter.emit_field_lvalue(obj_temp, target.field, is_pointer)

        # Case 3: Index access with side effects in index expression
        if isinstance(target, IndexExpr):
            base_has_effects = self._has_side_effects(target.array)
            index_has_effects = self._has_side_effects(target.index)

            if base_has_effects or index_has_effects:
                c_base = self._emit_expr(target.array)
                c_index = self._emit_expr(target.index)

                if base_has_effects:
                    base_ty = self.analysis.expr_types.get(id(target.array))
                    if base_ty is None:
                        self.ice("[ICE-1244] missing type for index base", node=target.array)
                    base_temp = self.emitter.fresh_tmp("base")
                    self.emitter.emit_temp_decl(self.emitter.emit_type(base_ty), base_temp, c_base)
                    c_base = base_temp

                if index_has_effects:
                    idx_temp = self.emitter.fresh_tmp("idx")
                    self.emitter.emit_temp_decl("l0_int", idx_temp, c_index)
                    c_index = idx_temp

                return self.emitter.emit_index_lvalue(c_base, c_index)

        # Case 4: Parenthesized expression - unwrap and recurse
        if isinstance(target, ParenExpr):
            return self._emit_lvalue_with_caching(target.inner)

        # Default: no side effects, use normal emission
        return self._emit_expr(target)

    def _emit_let(self, stmt: LetStmt, module_name: str) -> Any:
        """Emit a local 'let' declaration.

        Args:
            stmt: The LetStmt AST node.
            module_name: Name of current module.

        Raises:
            InternalCompilerError: If type cannot be inferred.
        """
        # Resolve declared type (if any) or use inferred type
        var_ty = None
        if stmt.type is not None:
            var_ty = self._resolve_type_ref(stmt.type, module_name)
        if var_ty is None:
            var_ty = self.analysis.expr_types.get(id(stmt.value))

        if var_ty is None:
            self.ice(f"[ICE-1170] missing inferred type for let initializer '{stmt.name}'", node=stmt.value)

        c_var_name = self.emitter.mangle_identifier(stmt.name)
        c_type = self.emitter.emit_type(var_ty)

        # Use _emit_expr_with_expected_type for type conversion
        c_init = self._emit_owned_expr_with_expected_type(stmt.value, var_ty)
        self.emitter.emit_let_decl(c_type, c_var_name, c_init)

        # Track ALL variables in scope
        if self._current_scope is not None:
            self._current_scope.add_owned(c_var_name, var_ty)
        return None

    def _resolve_let_type(self, stmt: LetStmt, module_name: str) -> Type:
        """Resolve concrete type for a let declaration.

        Args:
            stmt: The LetStmt AST node.
            module_name: Name of current module.

        Returns:
            The resolved Type.

        Raises:
            InternalCompilerError: If type cannot be inferred.
        """
        var_ty = None
        if stmt.type is not None:
            var_ty = self._resolve_type_ref(stmt.type, module_name)
        if var_ty is None:
            var_ty = self.analysis.expr_types.get(id(stmt.value))
        if var_ty is None:
            self.ice(f"[ICE-1170] missing inferred type for let initializer '{stmt.name}'", node=stmt.value)
        return var_ty

    def _emit_with_cleanup_header_let_predecl(self, stmt: LetStmt, module_name: str) -> Optional[Type]:
        """Predeclare a nullable `with`-header let for cleanup-block form.

        Nullable lets are predeclared as `null` so cleanup code can
        reference them on header `?` failure paths.

        Non-nullable lets use the normal declaration+initializer path and return None here.

        Args:
            stmt: The LetStmt AST node.
            module_name: Name of current module.

        Returns:
            The Type if it was a nullable let, otherwise None.
        """
        var_ty = self._resolve_let_type(stmt, module_name)
        if not isinstance(var_ty, NullableType):
            return None

        c_var_name = self.emitter.mangle_identifier(stmt.name)
        c_type = self.emitter.emit_type(var_ty)
        c_zero = self.emitter.emit_null_literal(var_ty, for_initializer=True)
        self.emitter.emit_let_decl(c_type, c_var_name, c_zero)

        if self._current_scope is not None:
            self._current_scope.add_owned(c_var_name, var_ty)

        return var_ty

    def _emit_with_cleanup_header_let_assign(self, stmt: LetStmt, var_ty: Type) -> None:
        """Emit initializer assignment for a predeclared cleanup-block let.

        Args:
            stmt: The LetStmt AST node.
            var_ty: The resolved type of the let.
        """
        c_var_name = self.emitter.mangle_identifier(stmt.name)
        c_value = self._emit_owned_expr_with_expected_type(stmt.value, var_ty)
        self.emitter.emit_assignment(c_var_name, c_value)

    def _emit_retain_for_copied_value(self, c_expr: str, ty: Type) -> None:
        """Emit retain operations for a copied owned value.

        Used when copying from place expressions so source and destination own
        independent references.

        Args:
            c_expr: C expression evaluating to the value.
            ty: The type of the value.

        Raises:
            InternalCompilerError: If variant decl is missing for enum types.
        """
        if self.analysis.is_arc_type(ty):
            self.emitter.emit_string_retain(c_expr)
            return

        if isinstance(ty, NullableType):
            if self.emitter.is_niche_nullable(ty):
                return
            if not self.analysis.has_arc_data(ty.inner):
                return

            self.emitter.emit_if_header(self.emitter.emit_optional_has_value(c_expr))
            self.emitter.emit_block_start()
            self._emit_retain_for_copied_value(self.emitter.emit_optional_value(c_expr), ty.inner)
            self.emitter.emit_block_end()
            return

        if isinstance(ty, StructType):
            info = self.analysis.struct_infos.get((ty.module, ty.name))
            if info is None:
                return
            for field in info.fields:
                self._emit_retain_for_copied_value(self.emitter.emit_field_access(c_expr, field.name, False), field.type)
            return

        if isinstance(ty, EnumType):
            enum_info = self.analysis.enum_infos.get((ty.module, ty.name))
            if enum_info is None:
                return

            self.emitter.emit_switch_start(self.emitter.emit_enum_tag_access(c_expr))
            for variant_name, variant_info in enum_info.variants.items():
                c_tag = self.emitter.emit_enum_tag(ty, variant_name)
                self.emitter.emit_case_label(c_tag)
                self.emitter.emit_block_start()

                variant_decl = self.find_variant_decl(ty.module, ty.name, variant_name)
                if variant_decl is None:
                    self.ice(f"[ICE-1304] missing variant decl for {ty.module}.{ty.name}.{variant_name}")

                for field, field_ty in zip(variant_decl.fields, variant_info.field_types):
                    field_expr = self.emitter.emit_enum_payload_field_access(c_expr, variant_name, field.name)
                    self._emit_retain_for_copied_value(field_expr, field_ty)

                self.emitter.emit_exit_switch()
                self.emitter.emit_block_end()

            self.emitter.emit_unreachable_marker("retain")
            self.emitter.emit_switch_end()

    def _emit_copy_expr_with_retains(self, c_expr: str, ty: Type) -> str:
        """Materialize copied values in a temp and emit retain logic when needed.

        Args:
            c_expr: C expression evaluating to the value.
            ty: The type of the value.

        Returns:
            The name of the temporary containing the copied and retained value.
        """
        if not self.analysis.has_arc_data(ty):
            return c_expr

        temp = self.emitter.fresh_tmp("copy")
        self.emitter.emit_temp_decl(self.emitter.emit_type(ty), temp, c_expr)
        self._emit_retain_for_copied_value(temp, ty)
        return temp

    def _emit_match(self, stmt: MatchStmt, module_name: str) -> None:
        """Emit a match statement as a switch on the tag field.

        Args:
            stmt: The MatchStmt AST node.
            module_name: Name of current module.

        Raises:
            InternalCompilerError: If types or patterns are unsupported.
        """
        scrutinee_expr_type = self.analysis.expr_types.get(id(stmt.expr))
        if not scrutinee_expr_type:
            self.ice("[ICE-1190] missing inferred type for match scrutinee", node=stmt.expr)

        c_scrutinee_type = self.emitter.emit_type(scrutinee_expr_type)
        c_scrutinee_expr = self._emit_expr(stmt.expr)

        self.emitter.emit_block_start()
        outer_scope = self._push_scope()
        self.emitter.emit_match_scrutinee_decl(c_scrutinee_type, c_scrutinee_expr)
        if self._is_unwrap_cast_from_place(stmt.expr) and self.analysis.has_arc_data(scrutinee_expr_type):
            self._emit_retain_for_copied_value("_scrutinee", scrutinee_expr_type)

        # Track _scrutinee for cleanup only for rvalue expressions with owned types
        if not self._is_place_expr(stmt.expr):
            if self.analysis.has_arc_data(scrutinee_expr_type):
                outer_scope.add_owned("_scrutinee", scrutinee_expr_type)

        self._switch_depth += 1
        self.emitter.emit_match_switch_start("_scrutinee")

        arms_unreachable = 0

        for arm in stmt.arms:
            # Emit case label
            if isinstance(arm.pattern, WildcardPattern):
                self.emitter.emit_default_label()
            elif isinstance(arm.pattern, VariantPattern):
                if isinstance(scrutinee_expr_type, EnumType):
                    tag_value = self.emitter.emit_enum_tag(scrutinee_expr_type, arm.pattern.name)
                    self.emitter.emit_case_label(tag_value)
                else:
                    self.ice("[ICE-1191] match arm cannot be lowered to a C switch case", node=arm.pattern)
            else:
                self.ice("[ICE-1192] unsupported match pattern", node=arm.pattern)

            self.emitter.emit_block_start()

            # Create scope for arm (pattern variables + body locals)
            arm_scope = self._push_scope()
            self._next_stmt_unreachable = False

            # Bind pattern variables inside the arm scope
            if isinstance(arm.pattern, VariantPattern) and isinstance(scrutinee_expr_type, EnumType):
                self._emit_pattern_bindings(arm.pattern, scrutinee_expr_type, arm_scope)

            # Emit arm body
            self._emit_block_sequence(arm.body, module_name)

            # Cleanup if arm didn't terminate
            if not self._next_stmt_unreachable:
                self._emit_cleanup_at_scope_exit(arm_scope)
                self.emitter.emit_exit_switch()

            if self._next_stmt_unreachable:
                arms_unreachable += 1

            self._pop_scope()

            self.emitter.emit_block_end()

        self.emitter.emit_switch_end()
        self._switch_depth -= 1

        # Code after match is unreachable only if ALL arms are unreachable
        self._next_stmt_unreachable = (arms_unreachable == len(stmt.arms))

        if self._next_stmt_unreachable:
            self.emitter.emit_unreachable_marker("'match'")
        else:
            self._emit_cleanup_at_scope_exit(outer_scope)

        self._pop_scope()
        self.emitter.emit_block_end()

    def _emit_case(self, stmt: CaseStmt, module_name: str) -> None:
        """Emit a case statement as a scalar switch or string if/else chain.

        Args:
            stmt: The CaseStmt AST node.
            module_name: Name of current module.

        Raises:
            InternalCompilerError: If types or literals are unsupported.
        """
        scrutinee_expr_type = self.analysis.expr_types.get(id(stmt.expr))
        if not scrutinee_expr_type:
            self.ice("[ICE-1193] missing inferred type for case scrutinee", node=stmt.expr)

        c_scrutinee_type = self.emitter.emit_type(scrutinee_expr_type)
        c_scrutinee_expr = self._emit_expr(stmt.expr)

        total_arms = len(stmt.arms) + (1 if stmt.else_arm is not None else 0)
        arms_unreachable = 0

        self.emitter.emit_block_start()
        outer_scope = self._push_scope()
        self.emitter.emit_match_scrutinee_decl(c_scrutinee_type, c_scrutinee_expr)
        if self._is_unwrap_cast_from_place(stmt.expr) and self.analysis.has_arc_data(scrutinee_expr_type):
            self._emit_retain_for_copied_value("_scrutinee", scrutinee_expr_type)

        # Track _scrutinee for cleanup only for rvalue expressions with owned types
        if not self._is_place_expr(stmt.expr):
            if self.analysis.has_arc_data(scrutinee_expr_type):
                outer_scope.add_owned("_scrutinee", scrutinee_expr_type)

        if isinstance(scrutinee_expr_type, BuiltinType) and scrutinee_expr_type.name == "string":
            if not stmt.arms and stmt.else_arm is not None:
                arm_scope = self._push_scope()
                self._next_stmt_unreachable = False
                self._emit_stmt(stmt.else_arm.body, module_name)

                if not self._next_stmt_unreachable:
                    self._emit_cleanup_at_scope_exit(arm_scope)

                if self._next_stmt_unreachable:
                    arms_unreachable += 1

                self._pop_scope()
            else:
                for index, arm in enumerate(stmt.arms):
                    c_literal = self._emit_case_literal(arm.literal)
                    condition = self.emitter.emit_string_equals_call("_scrutinee", c_literal)
                    if index == 0:
                        self.emitter.emit_if_header(condition)
                    else:
                        self.emitter.emit_else()
                        self.emitter.emit_if_header(condition)

                    self.emitter.emit_block_start()

                    arm_scope = self._push_scope()
                    self._next_stmt_unreachable = False
                    self._emit_stmt(arm.body, module_name)

                    if not self._next_stmt_unreachable:
                        self._emit_cleanup_at_scope_exit(arm_scope)

                    if self._next_stmt_unreachable:
                        arms_unreachable += 1

                    self._pop_scope()

                    self.emitter.emit_block_end()

                if stmt.else_arm is not None:
                    self.emitter.emit_else()
                    self.emitter.emit_block_start()

                    arm_scope = self._push_scope()
                    self._next_stmt_unreachable = False
                    self._emit_stmt(stmt.else_arm.body, module_name)

                    if not self._next_stmt_unreachable:
                        self._emit_cleanup_at_scope_exit(arm_scope)

                    if self._next_stmt_unreachable:
                        arms_unreachable += 1

                    self._pop_scope()

                    self.emitter.emit_block_end()
        else:
            self._switch_depth += 1
            self.emitter.emit_switch_start("_scrutinee")

            for arm in stmt.arms:
                self.emitter.emit_case_label(self._emit_case_literal(arm.literal))
                self.emitter.emit_block_start()

                arm_scope = self._push_scope()
                self._next_stmt_unreachable = False
                self._emit_stmt(arm.body, module_name)

                if not self._next_stmt_unreachable:
                    self._emit_cleanup_at_scope_exit(arm_scope)
                    self.emitter.emit_exit_switch()

                if self._next_stmt_unreachable:
                    arms_unreachable += 1

                self._pop_scope()

                self.emitter.emit_block_end()

            if stmt.else_arm is not None:
                self.emitter.emit_default_label()
                self.emitter.emit_block_start()

                arm_scope = self._push_scope()
                self._next_stmt_unreachable = False
                self._emit_stmt(stmt.else_arm.body, module_name)

                if not self._next_stmt_unreachable:
                    self._emit_cleanup_at_scope_exit(arm_scope)
                    self.emitter.emit_exit_switch()

                if self._next_stmt_unreachable:
                    arms_unreachable += 1

                self._pop_scope()

                self.emitter.emit_block_end()

            self.emitter.emit_switch_end()
            self._switch_depth -= 1

        if total_arms == 0:
            self._next_stmt_unreachable = False
        else:
            # Without else, some value may not match any arm, so code after is always reachable
            self._next_stmt_unreachable = (
                    stmt.else_arm is not None
                    and arms_unreachable == total_arms
            )

        if self._next_stmt_unreachable:
            self.emitter.emit_unreachable_marker("'case'")
        else:
            self._emit_cleanup_at_scope_exit(outer_scope)

        self._pop_scope()
        self.emitter.emit_block_end()

    def _emit_case_literal(self, expr: Expr) -> str:
        """Emit a constant literal for a case statement.

        Args:
            expr: The literal expression.

        Returns:
            A C constant string.

        Raises:
            InternalCompilerError: If literal type is unsupported.
        """
        if isinstance(expr, IntLiteral):
            return self.emitter.emit_int_literal(expr.value)
        if isinstance(expr, ByteLiteral):
            return self.emitter.emit_byte_literal(expr.value)
        if isinstance(expr, BoolLiteral):
            return self.emitter.emit_bool_literal(expr.value)
        if isinstance(expr, StringLiteral):
            return self.emitter.emit_string_literal(expr.value)

        self.ice("[ICE-1194] unsupported case literal type", node=expr)

    def _emit_pattern_bindings(
            self,
            pattern: VariantPattern,
            enum_type: EnumType,
            arm_scope: ScopeContext
    ) -> None:
        """Emit pattern variable bindings and add them to arm scope.

        Args:
            pattern: The variant pattern.
            enum_type: The enum type.
            arm_scope: The scope for the match arm.

        Raises:
            InternalCompilerError: If variant decl is missing.
        """
        variant_decl = self.find_variant_decl(
            enum_type.module,
            enum_type.name,
            pattern.name
        )
        if not variant_decl:
            return

        enum_info = self.analysis.enum_infos.get((enum_type.module, enum_type.name))
        if not enum_info:
            return

        variant_info = enum_info.variants.get(pattern.name)
        if not variant_info:
            return

        if len(pattern.vars) != len(variant_decl.fields):
            return  # Arity mismatch caught by type checker

        for pat_var, field_decl, field_type in zip(
                pattern.vars,
                variant_decl.fields,
                variant_info.field_types
        ):
            c_ftype = self.emitter.emit_type(field_type)
            c_pat_var = self.emitter.mangle_identifier(pat_var)

            # Delegate C-specific pattern binding syntax to emitter
            c_init = self.emitter.emit_pattern_binding_init("_scrutinee", pattern.name, field_decl.name)
            self.emitter.emit_let_decl(c_ftype, c_pat_var, c_init)

            # Add to scope for type lookup.
            # Pattern variables are borrowed from scrutinee, not owned,
            # thus add_declared() is used, not add_owned().
            arm_scope.add_declared(c_pat_var, field_type)

    def _emit_with(self, stmt: WithStmt, module_name: str) -> None:
        """Emit a with statement.

        Inline => form (LIFO cleanup):
            Emit init statements, then body, then cleanup statements in reverse order.

        Cleanup block form:
            Emit init statements, then body, then cleanup block statements.

        Cleanup is emitted at block end and before every early exit
        (return, break, continue). The scope stores cleanup data so
        ``_emit_cleanup_for_return`` and ``_emit_cleanup_for_loop_exit``
        can emit it before leaving.

        The body and cleanup block are each emitted as real nested C blocks
        so that any declarations inside them do not collide with the header
        scope (e.g., legal L0 shadowing like ``let x`` in both the header
        and body).

        Args:
            stmt: The WithStmt AST node.
            module_name: Name of current module.
        """
        self.emitter.emit_block_start()
        with_scope = self._push_scope()

        if stmt.cleanup_body is not None:
            with_scope.with_cleanup_block = stmt.cleanup_body
        else:
            # Register inline cleanup incrementally so a TryExpr (`?`) failure
            # in header item N can still clean up items 0..N-1.
            with_scope.with_cleanup_inline = []

        predeclared_nullable_lets: Dict[int, Type] = {}
        if stmt.cleanup_body is not None:
            # First pass: predeclare nullable lets so cleanup on early header
            # failure can reference all nullable header names.
            for item in stmt.items:
                if isinstance(item.init, LetStmt):
                    predecl_ty = self._emit_with_cleanup_header_let_predecl(item.init, module_name)
                    if predecl_ty is not None:
                        predeclared_nullable_lets[id(item.init)] = predecl_ty

        # Emit all init statements in the header scope.
        for item in stmt.items:
            if stmt.cleanup_body is not None and isinstance(item.init, LetStmt):
                predecl_ty = predeclared_nullable_lets.get(id(item.init))
                if predecl_ty is not None:
                    self._emit_with_cleanup_header_let_assign(item.init, predecl_ty)
                else:
                    self._emit_let(item.init, module_name)
            else:
                self._emit_stmt(item.init, module_name)

            if stmt.cleanup_body is None and item.cleanup is not None:
                assert with_scope.with_cleanup_inline is not None
                # LIFO order: latest successful item cleans first.
                with_scope.with_cleanup_inline.insert(0, item.cleanup)

        # Emit body as a nested block so its declarations get their own
        # C scope (mirrors L0 scoping rules).
        self.emitter.emit_block_start()
        body_scope = self._push_scope()
        self._emit_block_sequence(stmt.body, module_name)
        if not self._next_stmt_unreachable:
            self._emit_cleanup_at_scope_exit(body_scope)
        body_unreachable = self._next_stmt_unreachable
        self._pop_scope()
        self.emitter.emit_block_end()

        # Emit cleanup at normal exit (only if code is reachable).
        # User cleanup runs before automatic owned-var cleanup so that
        # cleanup code can still reference the with-header variables.
        if not body_unreachable:
            self._emit_with_cleanup_from_scope(with_scope, module_name)
            self._emit_cleanup_at_scope_exit(with_scope)

        self._pop_scope()
        self.emitter.emit_block_end()

    def _emit_drop(self, stmt: DropStmt, module_name: str) -> None:
        """Emit drop statement with automatic cleanup of owned fields.

        For structs: releases all string fields.
        For enums: switches on tag, releases strings in active variant.
        Then calls _rt_drop() to free the memory.

        Args:
            stmt: The DropStmt AST node.
            module_name: Name of current module.

        Raises:
            InternalCompilerError: If variable is undefined or not a pointer.
        """
        c_name = self.emitter.mangle_identifier(stmt.name)

        # Look up the type from the scope chain first (for local variables)
        var_type = self._lookup_local_var_type(stmt.name)

        # If not found in scope, try module environment (for parameters, etc.)
        if var_type is None:
            var_sym = self._lookup_symbol(stmt.name, module_name)
            if var_sym is None:
                self.ice(f"[ICE-1060] undefined variable in drop: {stmt.name}", node=stmt)
            var_type = var_sym.type

        if not (isinstance(var_type, PointerType) or
                isinstance(var_type, NullableType) and isinstance(var_type.inner, PointerType)):
            self.ice(f"[ICE-1061] drop requires pointer type, got '{format_type(var_type)}'", node=stmt)

        if isinstance(var_type, NullableType) and isinstance(var_type.inner, PointerType):
            inner_type = var_type.inner.inner
        else:
            inner_type = var_type.inner

        # Emit cleanup for owned fields before freeing
        if isinstance(inner_type, StructType):
            self._emit_struct_cleanup(c_name, inner_type)
        elif isinstance(inner_type, EnumType):
            self._emit_enum_cleanup(c_name, inner_type)
        elif self.analysis.is_arc_type(inner_type):
            # Release the ARC value before freeing the container
            c_cond = self.emitter.emit_pointer_null_check(c_name, "!=")
            self.emitter.emit_if_header(c_cond)
            self.emitter.emit_block_start()
            self.emitter.emit_string_release(f"*{c_name}")
            self.emitter.emit_block_end()
        # For other builtin types or other pointers, no special cleanup needed

        # Emit the actual drop
        self.emitter.emit_drop_call(c_name)
        self.emitter.emit_null_assignment(c_name)

    # -------------------------------------------------------------------------
    # Intrinsic emission
    # -------------------------------------------------------------------------

    def _try_emit_intrinsic(self, expr: CallExpr) -> Optional[str]:
        """Expand compiler intrinsics inline.

        Args:
            expr: The call expression to check.

        Returns:
            C code string if it is an intrinsic, otherwise None.
        """
        if not isinstance(expr.callee, VarRef):
            return None

        name = expr.callee.name

        if name == "sizeof":
            return self._emit_sizeof_intrinsic(expr)

        if name == "ord":
            return self._emit_ord_intrinsic(expr)

        # Not an intrinsic
        return None

    def _emit_sizeof_intrinsic(self, expr: CallExpr) -> str:
        """Emit sizeof intrinsic.

        Args:
            expr: The sizeof call expression.

        Returns:
            A C sizeof expression string.

        Raises:
            InternalCompilerError: If target type cannot be resolved.
        """
        target_ty = self.analysis.intrinsic_targets.get(id(expr))
        if target_ty is None:
            self.ice("[ICE-1120] failed to resolve sizeof target type", node=expr)

        return self.emitter.emit_sizeof_type(target_ty)

    def _emit_ord_intrinsic(self, expr: CallExpr) -> str:
        """Emit ord(enum_value) intrinsic.

        Returns 0-based ordinal of enum variant.

        Args:
            expr: The ord call expression.

        Returns:
            A C expression string for the ordinal value.

        Raises:
            InternalCompilerError: If argument count is incorrect.
        """
        if len(expr.args) != 1:
            self.ice("[ICE-1121] ord expects exactly 1 argument", node=expr)

        arg = expr.args[0]
        c_arg = self._emit_expr(arg)

        return self.emitter.emit_ord(c_arg)

    # -------------------------------------------------------------------------
    # Constructor emission
    # -------------------------------------------------------------------------

    def _try_emit_constructor(self, expr: CallExpr) -> Optional[str]:
        """Check if expr is a constructor call and emit appropriate initialization.

        Struct: Point(1, 2) -> { .x = 1, .y = 2 }
        Enum: Int(42) -> { .tag = Expr_Int, .data = { .Int = { .value = 42 } } }

        Args:
            expr: The call expression to check.

        Returns:
            C code string if this is a constructor, otherwise None.
        """
        assert isinstance(expr.callee, VarRef)
        name = expr.callee.name

        # Look up the symbol to check if this is actually a constructor
        if self.current_module:
            sym = self._lookup_symbol(name, self.current_module, module_path=expr.callee.module_path)
            if sym is None:
                return None

            # Only treat as constructor if the symbol is a struct (or type alias to one), or enum variant
            if sym.kind is SymbolKind.STRUCT or (
                    sym.kind is SymbolKind.TYPE_ALIAS and isinstance(sym.type, StructType)):
                # Get the struct type from expression type
                expr_type = self.analysis.expr_types.get(id(expr))
                if isinstance(expr_type, StructType):
                    return self._emit_struct_constructor(expr, expr_type)

            elif sym.kind == SymbolKind.ENUM_VARIANT:
                # Get the enum type from expression type
                expr_type = self.analysis.expr_types.get(id(expr))
                if isinstance(expr_type, EnumType):
                    return self._emit_variant_constructor(expr, expr_type)

        # Not a constructor
        return None

    def _emit_struct_constructor(self, expr: CallExpr, struct_type: StructType) -> str:
        """Emit struct constructor as C designated initializer.

        Point(1, 2) -> (struct l0_modulename_Point){ .x = 1, .y = 2 }

        Args:
            expr: The constructor call expression.
            struct_type: The struct type.

        Returns:
            A C struct initializer expression string.

        Raises:
            InternalCompilerError: If struct info is missing or argument count mismatches.
        """
        # Look up struct info to get field names
        info = self.analysis.struct_infos.get((struct_type.module, struct_type.name))
        if info is None:
            self.ice(f"[ICE-1280] missing StructInfo for {struct_type.module}.{struct_type.name}", node=expr)
        if len(info.fields) != len(expr.args):
            self.ice(
                f"[ICE-1281] argument count mismatch in struct constructor for {struct_type.module}.{struct_type.name}: "
                f"expected {len(info.fields)}, got {len(expr.args)}", node=expr)

        # Prepare field initializers as (name, value) tuples
        field_inits = []
        for field, arg in zip(info.fields, expr.args):
            c_arg = self._emit_owned_expr_with_expected_type(arg, field.type)
            field_inits.append((field.name, c_arg))

        # Delegate C-specific formatting to emitter
        return self.emitter.emit_struct_constructor_for_type(struct_type, field_inits)

    def _emit_variant_constructor(self, expr: CallExpr, enum_type: EnumType) -> str:
        """Emit enum variant constructor as C tagged union initializer.

        Example:
            Int(42) -> (struct l0_modulename_Int){ .tag = l0_modulename_Int_Int, .data.Int.value = 42 }

        Args:
            expr: The variant call expression.
            enum_type: The enum type.

        Returns:
            A C variant initializer expression string.

        Raises:
            InternalCompilerError: If variant info or declaration is missing.
        """
        assert isinstance(expr.callee, VarRef)
        variant_name = expr.callee.name

        # Look up variant info to get field names
        enum_info = self.analysis.enum_infos.get((enum_type.module, enum_type.name))
        if enum_info is None:
            self.ice(f"[ICE-1300] missing EnumInfo for {enum_type.module}.{enum_type.name}", node=expr)

        variant_info = enum_info.variants.get(variant_name)
        if variant_info is None:
            self.ice(f"[ICE-1301] missing VariantInfo for {variant_name}", node=expr)

        # Empty payload variant
        if len(variant_info.field_types) == 0:
            return self.emitter.emit_variant_constructor_for_type(enum_type, variant_name, [])

        # Get field names from AST
        variant_decl = self.find_variant_decl(enum_type.module, enum_type.name, variant_name)
        if variant_decl is None:
            self.ice(f"[ICE-1302] missing variant decl for {enum_type.module}.{enum_type.name}.{variant_name}",
                     node=expr)
        if len(variant_decl.fields) != len(expr.args):
            self.ice(f"[ICE-1303] arity mismatch in variant constructor {variant_name}", node=expr)

        # Prepare payload initializers as (name, value) tuples
        payload_inits = []
        for idx, (field, arg) in enumerate(zip(variant_decl.fields, expr.args)):
            c_arg = self._emit_owned_expr_with_expected_type(arg, variant_info.field_types[idx])
            payload_inits.append((field.name, c_arg))

        # Delegate C-specific formatting to emitter
        return self.emitter.emit_variant_constructor_for_type(enum_type, variant_name, payload_inits)

    # -------------------------------------------------------------------------
    # `new` / `drop`
    # -------------------------------------------------------------------------

    def _emit_new_expr(self, expr: NewExpr) -> str:
        """Emit a heap allocation `new` expression.

        Args:
            expr: The NewExpr AST node.

        Returns:
            A C expression string for the newly allocated pointer.

        Raises:
            InternalCompilerError: If type or symbol resolution fails, or if args mismatch.
        """
        # Allocate and return a non-null heap pointer for a single object.
        new_ty = self.analysis.expr_types.get(id(expr))
        if new_ty is None or not isinstance(new_ty, PointerType):
            self.ice("[ICE-1200] missing inferred pointer type for new expression", node=expr)

        base_ty = new_ty.inner
        c_base = self.emitter.emit_type(base_ty)
        c_ptr_ty = self.emitter.emit_pointer_type(base_ty)
        tmp = self.emitter.fresh_tmp("new")

        # Allocate memory
        self.emitter.emit_alloc_obj(c_ptr_ty, c_base, tmp)

        # If no args and not an enum variant, zero-initialize
        # (Enum variants need proper tag initialization even with no payload)
        if not expr.args and not isinstance(base_ty, EnumType):
            self.emitter.emit_zero_init(tmp, c_base)
            return tmp

        # Initialize when needed
        if isinstance(base_ty, StructType):
            info = self.analysis.struct_infos.get((base_ty.module, base_ty.name))
            if info is None:
                self.ice(f"[ICE-1210] missing StructInfo for {base_ty.module}.{base_ty.name}", node=expr)
            # Designated init by field order (positional args)
            inits: List[Tuple[str, str]] = []
            for field, arg in zip(info.fields, expr.args):
                c_arg = self._emit_owned_expr_with_expected_type(arg, field.type)
                inits.append((field.name, c_arg))
            self.emitter.emit_struct_init_from_fields(tmp, base_ty, inits)

        elif isinstance(base_ty, EnumType):
            # `new` for enums is only allowed via a variant constructor name.
            assert self.current_module is not None
            variant_name = expr.type_ref.name
            sym = self._lookup_symbol(variant_name, self.current_module, module_path=expr.type_ref.module_path)
            if sym is None or sym.kind != SymbolKind.ENUM_VARIANT:
                self.ice("[ICE-1220] new enum allocation missing variant symbol (type checker invariant violated)",
                         node=expr)

            enum_info = self.analysis.enum_infos.get((base_ty.module, base_ty.name))
            if enum_info is None:
                self.ice(f"[ICE-1221] missing EnumInfo for {base_ty.module}.{base_ty.name}", node=expr)

            vinfo = enum_info.variants.get(variant_name)
            if vinfo is None:
                self.ice(f"[ICE-1222] unknown enum variant '{variant_name}' for {base_ty.module}.{base_ty.name}",
                         node=expr)

            # Empty payload variant
            if len(vinfo.field_types) == 0:
                self.emitter.emit_enum_variant_init(tmp, base_ty, variant_name, [])
            else:
                # Get field names from AST
                variant_decl = self.find_variant_decl(base_ty.module, base_ty.name, variant_name)
                if variant_decl is None:
                    self.ice(f"[ICE-1223] missing variant decl for {base_ty.module}.{base_ty.name}.{variant_name}",
                             node=expr)
                if len(variant_decl.fields) != len(expr.args):
                    self.ice(
                        f"[ICE-1224] arity mismatch in new {variant_name}: expected {len(variant_decl.fields)}, got {len(expr.args)}",
                        node=expr)
                payload_inits: List[Tuple[str, str]] = []
                for idx, (field, arg) in enumerate(zip(variant_decl.fields, expr.args)):
                    c_arg = self._emit_owned_expr_with_expected_type(arg, vinfo.field_types[idx])
                    payload_inits.append((field.name, c_arg))
                self.emitter.emit_enum_variant_init(tmp, base_ty, variant_name, payload_inits)

        elif isinstance(base_ty, BuiltinType):
            if len(expr.args) == 1:
                c_arg = self._emit_expr(expr.args[0])
                self.emitter.emit_pointer_assignment(tmp, c_arg)
            else:
                self.ice(
                    f"[ICE-1230] new expression with multiple args not supported for builtin type '{format_type(base_ty)}'",
                    node=expr)

        else:
            if len(expr.args) == 1:
                c_arg = self._emit_expr(expr.args[0])
                self.emitter.emit_pointer_assignment(tmp, c_arg)
            else:
                # multiple args not supported for other types
                self.ice(
                    f"[ICE-1231] new expression with multiple args not supported for type '{format_type(base_ty)}'",
                    node=expr)

        return tmp

    # -------------------------------------------------------------------------
    # Expression emission
    # -------------------------------------------------------------------------

    def _convert_expr_with_expected_type(self, c_expr: str, natural_ty: Optional[Type], expected: Type) -> str:
        """Convert a pre-emitted expression into the expected type when required.

        Args:
            c_expr: The C expression string.
            natural_ty: The natural type of the expression.
            expected: The expected type.

        Returns:
            A C expression string, potentially wrapped or widened.
        """
        if natural_ty is None:
            return c_expr

        if self._types_equal(natural_ty, expected):
            return c_expr

        # T → T? (wrap in Some)
        if isinstance(expected, NullableType) and self._types_equal(expected.inner, natural_ty):
            if self.emitter.is_niche_nullable(expected):
                return c_expr  # pointer-to-pointer, no wrapping needed
            return self.emitter.emit_some_value_for_nullable(expected, c_expr)

        # byte → int (implicit widening)
        if (isinstance(natural_ty, BuiltinType) and natural_ty.name == "byte" and
                isinstance(expected, BuiltinType) and expected.name == "int"):
            return self.emitter.emit_widen_int(c_expr, natural_ty, expected)

        # No type conversion needed
        return c_expr

    def _emit_expr_with_expected_type(self, e: Expr, expected: Type) -> str:
        """Emit expression with implicit type conversion to expected type.

        Args:
            e: The expression to emit.
            expected: The expected type.

        Returns:
            A C expression string.

        Raises:
            InternalCompilerError: If null literal is assigned to invalid type.
        """

        # Special case: null literal
        if isinstance(e, NullLiteral):
            if isinstance(expected, (NullableType, PointerType)):
                return self.emitter.emit_null_literal(expected)
            self.ice(f"[ICE-1090] invalid expected type for null literal: '{format_type(expected)}'", node=e)

        natural_ty = self.analysis.expr_types.get(id(e))
        c_expr = self._emit_expr(e)
        return self._convert_expr_with_expected_type(c_expr, natural_ty, expected)

    def _emit_owned_expr_with_expected_type(self, e: Expr, expected: Type) -> str:
        """Emit expression for contexts that create a new owner.

        This applies retain-on-copy when a place expression is copied into an
        owned destination, while delegating regular type conversion to
        `_emit_expr_with_expected_type`.

        Args:
            e: The expression to emit.
            expected: The expected type.

        Returns:
            A C expression string.
        """
        natural_ty = self.analysis.expr_types.get(id(e))

        if isinstance(e, NullLiteral):
            return self._emit_expr_with_expected_type(e, expected)

        c_expr = self._emit_expr(e)
        place_like = self._is_place_expr(e) or self._is_unwrap_cast_from_place(e)

        if natural_ty is None or not place_like:
            return self._convert_expr_with_expected_type(c_expr, natural_ty, expected)

        if self._types_equal(natural_ty, expected):
            return self._emit_copy_expr_with_retains(c_expr, expected)

        if isinstance(expected, NullableType) and self._types_equal(expected.inner, natural_ty):
            if self.emitter.is_niche_nullable(expected):
                return c_expr
            retained_inner = self._emit_copy_expr_with_retains(c_expr, natural_ty)
            return self.emitter.emit_some_value_for_nullable(expected, retained_inner)

        return self._convert_expr_with_expected_type(c_expr, natural_ty, expected)

    def _emit_expr(self, expr: Expr, *, is_statement: bool = False) -> str:
        """Emit an expression and return the C code.

        Args:
            expr: The expression to emit.
            is_statement: True if the expression is used as a statement.

        Returns:
            A C expression string, or empty string if used as a statement and no-op.

        Raises:
            InternalCompilerError: If expression type is unsupported or resolution fails.
        """
        if isinstance(expr, IntLiteral):
            if is_statement:
                self.emitter.emit_comment(f"int literal {expr.value}")
                return ""
            return self.emitter.emit_int_literal(expr.value)

        if isinstance(expr, ByteLiteral):
            if is_statement:
                self.emitter.emit_comment(f"byte literal {expr.value}")
                return ""
            return self.emitter.emit_byte_literal(expr.value)

        elif isinstance(expr, StringLiteral):
            if is_statement:
                self.emitter.emit_comment(f'string literal "{expr.value}"')
                return ""
            return self.emitter.emit_string_literal(expr.value)

        elif isinstance(expr, BoolLiteral):
            if is_statement:
                self.emitter.emit_comment(f"bool literal {expr.value}")
                return ""
            return self.emitter.emit_bool_literal(expr.value)

        elif isinstance(expr, NullLiteral):
            if is_statement:
                self.emitter.emit_comment("null literal")
                return ""
            # null literal handling in expression context depends on expected type
            expected_ty = self.analysis.expr_types.get(id(expr))
            if expected_ty is None:
                self.ice("[ICE-1091] missing expected type for null literal", node=expr)
            if isinstance(expected_ty, (NullableType, PointerType)):
                return self.emitter.emit_null_literal(expected_ty)
            self.ice(f"[ICE-1090] invalid expected type for null literal: '{format_type(expected_ty)}'", node=expr)

        elif isinstance(expr, VarRef):
            # Check if this is a function or top-level let reference and use mangled name
            # CRITICAL: extern functions are NOT mangled (FFI boundary)
            resolution = self.analysis.var_ref_resolution.get(id(expr))
            if resolution is None:
                self.ice(f"[ICE-1102] missing VarRef resolution for '{expr.name}'", node=expr)
            if resolution is VarRefResolution.LOCAL:
                if is_statement:
                    self.emitter.emit_comment(f"var ref {expr.name}")
                    return ""
                return self.emitter.emit_var_ref(self.emitter.mangle_identifier(expr.name))
            if self.current_module:
                sym = self._lookup_symbol(expr.name, self.current_module, module_path=expr.module_path)
                if sym and sym.kind == SymbolKind.FUNC:
                    if self._is_extern_function(sym):
                        # Don't mangle extern functions
                        return self.emitter.emit_var_ref(expr.name)
                    else:
                        # Mangle regular L0 functions
                        return self.emitter.emit_var_ref(self.emitter.mangle_function_name(sym.module.name, expr.name))
                elif sym and sym.kind == SymbolKind.LET:
                    # Mangle top-level let bindings
                    return self.emitter.emit_var_ref(self.emitter.mangle_let_name(sym.module.name, expr.name))
                elif sym and sym.kind == SymbolKind.ENUM_VARIANT:
                    # Bare zero-arg variant constructor (e.g. `Red` as alias for `Red()`)
                    expr_type = self.analysis.expr_types.get(id(expr))
                    if isinstance(expr_type, EnumType):
                        return self.emitter.emit_variant_constructor_for_type(expr_type, expr.name, [])
            self.ice(f"[ICE-1103] unresolved VarRef '{expr.name}' after type checking", node=expr)

        elif isinstance(expr, UnaryOp):
            c_operand = self._emit_expr(expr.operand)
            return self.emitter.emit_unary_op(expr.op, c_operand)

        elif isinstance(expr, BinaryOp):
            return self._emit_binary_op(expr, expr.op, expr.left, expr.right)

        elif isinstance(expr, CallExpr):

            if isinstance(expr.callee, VarRef):
                # Check for intrinsic first
                intrinsic_result = self._try_emit_intrinsic(expr)
                if intrinsic_result is not None:
                    return intrinsic_result

                # Check for constructor call (struct or enum variant)
                constructor_init = self._try_emit_constructor(expr)
                if constructor_init is not None:
                    return constructor_init

                # Regular function call - look up and mangle the name
                # CRITICAL: extern functions are NOT mangled (FFI boundary)
                if self.current_module:
                    sym = self._lookup_symbol(expr.callee.name, self.current_module,
                                              module_path=expr.callee.module_path)
                    if sym and sym.kind == SymbolKind.FUNC:
                        if self._is_extern_function(sym):
                            # Don't mangle extern functions
                            c_func_name = expr.callee.name
                        else:
                            # Mangle regular L0 functions
                            c_func_name = self.emitter.mangle_function_name(sym.module.name, expr.callee.name)

                        func_ty = sym.type if isinstance(sym.type, FuncType) else None
                        if func_ty and len(func_ty.params) == len(expr.args):
                            c_arg_parts = []
                            for a, p in zip(expr.args, func_ty.params):
                                c_a = self._emit_expr_with_expected_type(a, p)
                                a_ty = self.analysis.expr_types.get(id(a))
                                if a_ty and self._should_materialize_arc_temp(a, a_ty):
                                    c_a = self._materialize_arc_temp(c_a, a_ty)
                                c_arg_parts.append(c_a)
                            c_args = ", ".join(c_arg_parts)
                        else:
                            c_arg_parts = []
                            for a in expr.args:
                                c_a = self._emit_expr(a)
                                a_ty = self.analysis.expr_types.get(id(a))
                                if a_ty and self._should_materialize_arc_temp(a, a_ty):
                                    c_a = self._materialize_arc_temp(c_a, a_ty)
                                c_arg_parts.append(c_a)
                            c_args = ", ".join(c_arg_parts)
                        return self.emitter.emit_function_call(c_func_name, c_args)

                self.ice("[ICE-1100] unresolved function call target after type checking", node=expr)
            else:
                # Complex callee expression
                c_callee = self._emit_expr(expr.callee)
                c_arg_parts = []
                for a in expr.args:
                    c_a = self._emit_expr(a)
                    a_ty = self.analysis.expr_types.get(id(a))
                    if a_ty and self._should_materialize_arc_temp(a, a_ty):
                        c_a = self._materialize_arc_temp(c_a, a_ty)
                    c_arg_parts.append(c_a)
                c_args = ", ".join(c_arg_parts)
                return self.emitter.emit_function_call(f"({c_callee})", c_args)

        elif isinstance(expr, IndexExpr):
            self.ice("[ICE-1899] IndexExpr not yet implemented", node=expr)

        elif isinstance(expr, FieldAccessExpr):
            c_obj = self._emit_expr(expr.obj)
            # Determine if we need . or ->
            obj_type = self.analysis.expr_types.get(id(expr.obj))
            is_pointer = isinstance(obj_type, PointerType)
            return self.emitter.emit_field_access(c_obj, expr.field, is_pointer)

        elif isinstance(expr, ParenExpr):
            c_inner = self._emit_expr(expr.inner)
            return self.emitter.emit_paren_expr(c_inner)


        elif isinstance(expr, CastExpr):
            # Emit inner expression first
            c_inner = self._emit_expr(expr.expr)

            assert self.current_module is not None
            # Resolve source and destination types
            src_ty = self.analysis.expr_types.get(id(expr.expr))
            dst_ty = self._resolve_type_ref(expr.target_type, self.current_module)
            if dst_ty is None:
                self.ice("[ICE-1110] failed to resolve cast target type", node=expr.target_type)
            c_dst = self.emitter.emit_type(dst_ty)

            if src_ty == dst_ty:
                return c_inner

            # Checked narrowing cast (T -> T_small): emit runtime check + abort on overflow.
            if (self._is_int_assignable(src_ty) and self._is_int_assignable(dst_ty) and
                    self._int_type_size(src_ty) > self._int_type_size(dst_ty)):
                return self.emitter.emit_checked_narrow_cast(c_dst, c_inner)

            # Checked wrap cast (T -> T?): emit appropriate optional construction.
            if isinstance(dst_ty, NullableType):
                # Pointer-shaped optionals (niche): construct pointer or NULL.
                if self.emitter.is_niche_nullable(dst_ty):
                    return self.emitter.emit_cast(c_dst, c_inner)

                # value-optional: construct wrapper
                if isinstance(expr.expr, NullLiteral):
                    return self.emitter.emit_null_literal(dst_ty)
                if self._is_place_expr(expr.expr) and self.analysis.has_arc_data(dst_ty.inner):
                    retained = self._emit_copy_expr_with_retains(c_inner, dst_ty.inner)
                    return self.emitter.emit_some_value_for_nullable(dst_ty, retained)
                return self.emitter.emit_some_value_for_nullable(dst_ty, c_inner)

            # Checked unwrap cast (T? -> T): emit a runtime check + abort on empty.
            if isinstance(src_ty, NullableType) and dst_ty == src_ty.inner:
                return self._emit_unwrap(c_dst, c_inner, src_ty)

            # Default: plain C cast
            return self.emitter.emit_cast(c_dst, c_inner)

        elif isinstance(expr, NewExpr):
            return self._emit_new_expr(expr)

        elif isinstance(expr, TryExpr):
            c_inner = self._emit_expr(expr.expr)
            src_ty = self.analysis.expr_types.get(id(expr.expr))

            if not isinstance(src_ty, NullableType):
                self.ice("[ICE-1130] TryExpr operand is not nullable (type checker invariant violated)", node=expr)

            tmp = self.emitter.fresh_tmp("try")
            c_tmp_ty = self.emitter.emit_type(src_ty)
            self.emitter.emit_temp_decl(c_tmp_ty, tmp, c_inner)

            # Build the "return none" for the *enclosing* function.
            if not isinstance(self._current_func_result, NullableType):
                self.ice("[ICE-1131] TryExpr used in non-nullable function (type checker invariant violated)",
                         node=expr)

            ret_none = self.emitter.emit_null_literal(self._current_func_result)

            needs_cleanup = (self._current_scope is not None
                             and self._scope_chain_has_cleanup())

            if self.emitter.is_niche_nullable(src_ty):
                if needs_cleanup:
                    self.emitter.emit_if_header(self.emitter.emit_condition_pointer_null_check(tmp, "=="))
                    self.emitter.emit_block_start()
                    self._emit_cleanup_for_return()
                    self.emitter.emit_return_stmt(ret_none)
                    self.emitter.emit_block_end()
                else:
                    self.emitter.emit_try_check_niche(tmp, ret_none)
                return tmp  # unwraps to the pointer itself

            if needs_cleanup:
                self.emitter.emit_if_header(self.emitter.emit_null_check_eq(tmp))
                self.emitter.emit_block_start()
                self._emit_cleanup_for_return()
                self.emitter.emit_return_stmt(ret_none)
                self.emitter.emit_block_end()
            else:
                self.emitter.emit_try_check_value(tmp, ret_none)
            extracted = self.emitter.emit_try_extract_value(tmp)
            if is_statement:
                # In statement context, ARC payloads must remain a real value expression
                # so ExprStmt can materialize/release them correctly.
                if self.analysis.has_arc_data(src_ty.inner):
                    return extracted
                return self.emitter.emit_discard_expr(extracted)
            return extracted

        self.ice(f"[ICE-9149] unknown expression type: {type(expr).__name__}", node=expr)

    def _emit_unwrap(self, c_dst: str, c_inner: str, src_ty: NullableType) -> str:
        """Emit code to unwrap a nullable value.

        Args:
            c_dst: C type of destination.
            c_inner: C expression of nullable value.
            src_ty: The NullableType.

        Returns:
            C code for unwrapped value.
        """
        # Pointer-shaped optionals (niche): empty is NULL.
        if self.emitter.is_niche_nullable(src_ty):
            return self.emitter.emit_unwrap_ptr(c_dst, c_inner, format_type(src_ty))

        # Value-optionals: empty is !has_value.
        c_src = self.emitter.emit_type(src_ty)
        tmp = self.emitter.fresh_tmp("unwrap")
        self.emitter.emit_temp_decl(c_src, tmp, c_inner)
        return self.emitter.emit_unwrap_opt(c_src, tmp, format_type(src_ty))

    def _emit_binary_op(
            self, expr_node: Expr, expr_op: str, expr_left: Expr, expr_right: Expr, *, for_condition: bool = False
    ) -> str:
        """Emit code for a binary operation.

        Args:
            expr_node: The BinaryOp AST node.
            expr_op: The operator string.
            expr_left: The left operand.
            expr_right: The right operand.

        Returns:
            C code string for the operation.

        Raises:
            InternalCompilerError: If types are missing, mismatch, or operation is unsupported.
        """
        if expr_op in ("&&", "||"):
            return self._emit_condition_value(expr_node)

        # Special-case: nullable wrapper compared with null
        if expr_op in ("==", "!=") and (isinstance(expr_left, NullLiteral) or isinstance(expr_right, NullLiteral)):
            other = expr_right if isinstance(expr_left, NullLiteral) else expr_left
            other_ty = self.analysis.expr_types.get(id(other))
            c_other = self._emit_expr(other)

            if isinstance(other_ty, NullableType) and not self.emitter.is_niche_nullable(other_ty):
                # value-optional: (opt == null) <=> !opt.has_value
                if expr_op == "==":
                    return self.emitter.emit_null_check_eq(c_other)
                else:  # expr_op == "!="
                    return self.emitter.emit_null_check_ne(c_other)

            # sanity check: should be pointer or pointer-optional
            if not isinstance(other_ty, (PointerType, NullableType)):
                self.ice(f"[ICE-1010] invalid null comparison: {c_other} {expr_op} NULL")

            # pointer / pointer-optional: compare with NULL
            if for_condition:
                return self.emitter.emit_condition_pointer_null_check(c_other, expr_op)
            return self.emitter.emit_pointer_null_check(c_other, expr_op)

        c_left = self._emit_expr(expr_left)
        c_right = self._emit_expr(expr_right)

        left_ty = self.analysis.expr_types.get(id(expr_left))
        right_ty = self.analysis.expr_types.get(id(expr_right))

        if left_ty is None or right_ty is None:
            self.ice("[ICE-1013] missing inferred type for binary operation", node=expr_node)

        # String equality/relational lowering via runtime helpers.
        if (
                isinstance(left_ty, BuiltinType) and left_ty.name == "string"
                and isinstance(right_ty, BuiltinType) and right_ty.name == "string"
        ):
            if self._should_materialize_arc_temp(expr_left, left_ty):
                c_left = self._materialize_arc_temp(c_left, left_ty)
            if self._should_materialize_arc_temp(expr_right, right_ty):
                c_right = self._materialize_arc_temp(c_right, right_ty)
            if expr_op in ("==", "!="):
                c_cmp = self.emitter.emit_string_equals_call(c_left, c_right)
                if expr_op == "!=":
                    return self.emitter.emit_unary_op("!", c_cmp)
                return c_cmp
            if expr_op == "+":
                return self.emitter.emit_string_concat_call(c_left, c_right)
            if expr_op in ("<", "<=", ">", ">="):
                if for_condition:
                    return self.emitter.emit_condition_string_compare_call(expr_op, c_left, c_right)
                return self.emitter.emit_string_compare_call(expr_op, c_left, c_right)

        # UB-free integer operators
        if expr_op in ("/", "%", "*", "+", "-"):
            if not (self._is_int_assignable(left_ty) and self._is_int_assignable(right_ty)):
                self.ice(f"[ICE-1011] non-int {expr_op} lowering not implemented")
            if expr_op == "/":
                return self.emitter.emit_checked_int_div(c_left, c_right)
            elif expr_op == "%":
                return self.emitter.emit_checked_int_mod(c_left, c_right)
            elif expr_op == "*":
                return self.emitter.emit_checked_int_mul(c_left, c_right)
            elif expr_op == "+":
                return self.emitter.emit_checked_int_add(c_left, c_right)
            elif expr_op == "-":
                return self.emitter.emit_checked_int_sub(c_left, c_right)
            else:
                return self.ice(f"[ICE-1012] {expr_op} lowering not implemented")

        # Typechecker allows mixed int/byte for numeric comparisons and equality.
        # Lower those directly instead of tripping the strict same-type ICE guard.
        if (
                expr_op in ("<", "<=", ">", ">=", "==", "!=")
                and self._is_int_assignable(left_ty)
                and self._is_int_assignable(right_ty)
        ):
            if for_condition:
                return self.emitter.emit_condition_binary_op(expr_op, c_left, c_right)
            return self.emitter.emit_binary_op(expr_op, c_left, c_right)

        if left_ty != right_ty:
            self.ice("[ICE-1014] type mismatch in binary operation", node=expr_node)

        if not self._is_binary_op_enabled(left_ty):
            self.ice(f"[ICE-1015] {expr_op} lowering not implemented for type '{format_type(left_ty)}'", node=expr_node)

        if for_condition:
            return self.emitter.emit_condition_binary_op(expr_op, c_left, c_right)
        return self.emitter.emit_binary_op(expr_op, c_left, c_right)

    # -------------------------------------------------------------------------
    # Type resolution helpers
    # -------------------------------------------------------------------------

    def _resolve_type_ref(self, tref, module_name: str):
        """Resolve an AST TypeRef into an l0_types.Type.

        This is needed so `let x: int? = null;` uses the declared type (int?) instead of
        the initializer type (null).

        Args:
            tref: The TypeRef AST node.
            module_name: Name of current module.

        Returns:
            The resolved Type.
        """
        result = resolve_type_ref(self.analysis.module_envs, module_name, tref)
        return result.type

    def _lookup_symbol(self, name: str, current_module_name: str, module_path: Optional[List[str]] = None) -> Optional[
        Symbol]:
        """Look up a symbol in the current module's environment.

        This is used to determine which module a function is defined in
        so we can generate the correct mangled name.

        Args:
            name: The name of the symbol.
            current_module_name: Name of current module.
            module_path: Optional module path for qualified names.

        Returns:
            The resolved Symbol, or None if not found.
        """
        result = resolve_symbol(self.analysis.module_envs, current_module_name, name, module_path=module_path)
        return result.symbol

    def _is_extern_function(self, sym: Symbol) -> bool:
        """Check if a symbol is an 'extern' function.

        Args:
            sym: The symbol to check.

        Returns:
            True if it is an extern function.
        """
        if sym.kind is SymbolKind.FUNC:
            return isinstance(sym.node, FuncDecl) and sym.node.is_extern
        return False

    def find_variant_decl(
            self, module_name: str, enum_name: str, variant_name: str
    ) -> Optional[EnumVariant]:
        """Find the EnumVariant AST node for a given variant in an enum.

        This is needed to get field names when binding pattern variables,
        since pattern variables are positional, but we need to access fields by name.

        Args:
            module_name: Name of module containing the enum.
            enum_name: Name of the enum.
            variant_name: Name of the variant.

        Returns:
            The EnumVariant AST node if found, otherwise None.
        """
        module = self.analysis.cu.modules.get(module_name)
        if not module:
            return None

        # Find the enum declaration
        for decl in module.decls:
            if isinstance(decl, EnumDecl) and decl.name == enum_name:
                # Find the variant within the enum
                for variant in decl.variants:
                    if variant.name == variant_name:
                        return variant
                break

        return None

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def _int_type_size(self, src_ty):
        """Get the byte size of an integer builtin type.

        Args:
            src_ty: The type to check.

        Returns:
            Byte size (1 for byte, 4 for int).

        Raises:
            InternalCompilerError: If type is not an integer builtin.
        """
        match src_ty:
            case BuiltinType(name="byte"):
                return 1
            case BuiltinType(name="int"):
                return 4
            case _:
                self.ice("[ICE-1320] unknown integer type for size determination")
