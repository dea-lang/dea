# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from typing import List, Optional, NoReturn, Tuple
from l0_analysis import AnalysisResult, VarRefResolution
from l0_ast import Node, TypeRef, FuncDecl, EnumDecl, EnumVariant, LetStmt, Expr, IntLiteral, StringLiteral, BoolLiteral, VarRef, UnaryOp, BinaryOp, CallExpr, IndexExpr, FieldAccessExpr, ParenExpr, CastExpr, NullLiteral, TypeExpr, TryExpr, NewExpr, ByteLiteral
from l0_c_emitter import CEmitter
from l0_internal_error import InternalCompilerError, ICELocation
from l0_name_resolver import Symbol, SymbolKind
from l0_resolve import resolve_symbol, resolve_type_ref
from l0_scope_context import ScopeContext
from l0_types import Type, BuiltinType, StructType, EnumType, PointerType, NullableType


@dataclass
class BackendState:
    """Canonical backend state, scopes, semantic queries, and source context."""

    analysis: AnalysisResult

    emitter: CEmitter = field(default_factory=CEmitter)

    current_module: Optional[str] = None

    _current_func_result: Optional[Type] = None

    _current_scope: Optional[ScopeContext] = None

    _loop_cleanup_scope_stack: List[Tuple[ScopeContext, ScopeContext]] = field(default_factory=list)

    _switch_depth: int = 0

    _loop_label_stack: List[Tuple[str, str]] = field(default_factory=list)

    _label_counter: int = 0

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

    def _is_int_assignable(self, typ: Type) -> bool:
        """Check if a type is assignable to an integer.

        Args:
            typ: The type to check.

        Returns:
            True if it's an 'int' or 'byte' builtin type.
        """
        return typ in (BuiltinType("int"), BuiltinType("byte"))

    def _is_binary_op_enabled(self, typ: Type) -> bool:
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

    def _pointer_type_or_none(self, ty: Optional[Type]) -> Optional[PointerType]:
        """Return the represented pointer type for pointer-shaped values."""
        if isinstance(ty, PointerType):
            return ty
        if isinstance(ty, NullableType) and isinstance(ty.inner, PointerType):
            return ty.inner
        return None

    def _lookup_local_var_type(self, var_name: str) -> Optional[Type]:
        """Look up a local variable's type in the current scope chain.

        Searches declared_vars (includes both locals and parameters).

        Args:
            var_name: The name of the variable to look up.

        Returns:
            The variable's Type, or None if not found.
        """
        mangled_name = self.emitter.names.mangle_identifier(var_name)
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

        mangled_name = self.emitter.names.mangle_identifier(expr.name)
        scope = self._current_scope
        while scope is not None:
            for owned_name, _ in scope.owned_vars:
                if owned_name == mangled_name:
                    return mangled_name
            scope = scope.parent
        return None

    def ice(self, message: str, *, node: Optional[Node] = None) -> NoReturn:
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

    def _expect_expr_type(self, expr: Expr) -> Type:
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

    def _emit_line_directive(self, node: Node) -> None:
        """Emit #line directive if node has span info and context allows it.

        Args:
            node: The AST node containing span information.
        """
        self.emitter.state.emit_line_directive(node, self.current_module)

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

    def _resolve_type_ref(self, tref: TypeRef, module_name: str):
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

    def _int_type_size(self, src_ty: Type):
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
