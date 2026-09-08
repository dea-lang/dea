#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Top-level signature resolution for the L0 compiler.

This module provides the SignatureResolver class which resolves types for
function parameters, return values, struct fields, enum payloads, and type aliases.
"""

from dataclasses import dataclass

from l0_ast import Node, TypeRef, FuncDecl, FieldDecl, StructDecl, EnumVariant, EnumDecl, TypeAliasDecl, LetDecl, \
    IntLiteral, BoolLiteral, ByteLiteral, StringLiteral, NullLiteral, CallExpr, VarRef, Expr
from l0_compilation import CompilationUnit
from l0_diagnostics import Diagnostic, diag_from_node
from l0_symbols import SymbolKey, ModuleEnv, SymbolKind, Symbol
from l0_types import (
    L0_PRIMITIVE_TYPES,
    Type,
    BuiltinType,
    StructType,
    EnumType,
    PointerType,
    NullableType,
    FuncType,
    get_builtin_type,
)
from l0_resolve import resolve_symbol, resolve_type_ref, TypeResolveErrorKind


@dataclass
class StructFieldInfo:
    """Information about a single struct field.

    Attributes:
        name: The name of the field.
        type: The resolved Type of the field.
    """
    name: str
    type: Type


@dataclass
class StructInfo:
    """Resolved type information for a struct.

    Attributes:
        struct_type: The base StructType.
        fields: List of StructFieldInfo objects for all fields.
    """
    struct_type: StructType
    fields: list[StructFieldInfo]


@dataclass
class EnumVariantInfo:
    """Information about a single enum variant.

    Attributes:
        name: The name of the variant.
        field_types: List of resolved types for the variant's payload fields.
    """
    name: str
    field_types: list[Type]


@dataclass
class EnumInfo:
    """Resolved type information for an enum.

    Attributes:
        enum_type: The base EnumType.
        variants: Mapping from variant names to their variant info.
    """
    enum_type: EnumType
    variants: dict[str, EnumVariantInfo]


class SignatureResolver:
    """Resolves top-level type signatures across all modules.

    The resolver processes:
    - Function signatures (parameters and return types).
    - Struct field types.
    - Enum variant payload types.
    - Type alias targets.
    - Module-level constant (let) types.

    It also performs cycle detection for value-type definitions.

    Attributes:
        cu: The compilation unit being processed.
        module_envs: Mapping of module names to their environments.
        diagnostics: Collected list of resolution diagnostics.
        func_types: Resolved function signatures keyed by (module, name).
        struct_infos: Resolved struct definitions keyed by (module, name).
        enum_infos: Resolved enum definitions keyed by (module, name).
        let_types: Resolved constant types keyed by (module, name).
    """

    def __init__(self, cu: CompilationUnit, module_envs: dict[str, ModuleEnv]):
        """Initialize the signature resolver.

        Args:
            cu: The compilation unit.
            module_envs: Environments produced by name resolution.
        """
        self.cu = cu
        self.module_envs = module_envs

        self.diagnostics: list[Diagnostic] = []

        # Side tables, keyed by (module_name, decl_name)
        self.func_types: dict[SymbolKey, FuncType] = {}
        self.struct_infos: dict[SymbolKey, StructInfo] = {}
        self.enum_infos: dict[SymbolKey, EnumInfo] = {}
        self.let_types: dict[SymbolKey, Type] = {}

    def resolve(self) -> None:
        """Resolve all top-level signatures in the compilation unit.

        This iterates through all modules and their declarations, populating
        the resolution tables and reporting any errors found.
        """
        for module in self.cu.modules.values():
            env = self.module_envs[module.name]
            self._resolve_module_signatures(env)

        # After resolving all signatures, detect value-type cycles
        self._detect_value_type_cycles()

    # --- internal helpers ---

    def _resolve_module_signatures(self, env: ModuleEnv) -> None:
        """Resolve all declarations within a single module."""
        for decl in env.module.decls:
            if isinstance(decl, StructDecl):
                self._resolve_struct(env, decl)
            elif isinstance(decl, EnumDecl):
                self._resolve_enum(env, decl)
            elif isinstance(decl, FuncDecl):
                self._resolve_func(env, decl)
            elif isinstance(decl, TypeAliasDecl):
                self._resolve_type_alias(env, decl)
            elif isinstance(decl, LetDecl):
                self._resolve_let(env, decl)

    def _emit(self, diag: Diagnostic) -> None:
        """Add a diagnostic to the collection."""
        self.diagnostics.append(diag)

    # --- type resolution core ---

    def _resolve_type_ref(
            self,
            env: ModuleEnv,
            tref: TypeRef,
            alias_stack: set[SymbolKey] | None = None,
    ) -> Type | None:
        """Resolve a TypeRef in the context of a module environment.

        Args:
            env: The current module environment.
            tref: The TypeRef AST node to resolve.
            alias_stack: Stack of aliases being resolved (for cycle detection).

        Returns:
            The resolved Type if successful, otherwise None.
        """
        if tref.name_qualifier is not None:
            full = "::".join(tref.name_qualifier + [tref.name])
            if tref.module_path:
                full = f"{'.'.join(tref.module_path)}::{full}"
            simple = tref.name
            if tref.module_path:
                simple = f"{'.'.join(tref.module_path)}::{tref.name}"
            self._emit(diag_from_node(
                kind="error",
                message=f"[SIG-0018] nested symbol path '{full}': "
                        f"paths must have the form 'module::symbol' (did you mean '{simple}'?)",
                module_name=env.name, filename=env.module.filename, node=tref,
            ))
            return None

        result = resolve_type_ref(
            self.module_envs,
            env.name,
            tref,
            module_path=tref.module_path,
            resolve_alias=lambda sym: self._resolve_type_alias_symbol(env, sym, alias_stack),
        )
        if result.type is None:
            if result.error is TypeResolveErrorKind.AMBIGUOUS_TYPE:
                modules_str = "', '".join(result.ambiguous_modules)
                hints = " or ".join(f"'{m}::{result.name}'" for m in result.ambiguous_modules)
                self._emit(
                    diag_from_node(
                        kind="error",
                        message=(
                            f"[SIG-0019] ambiguous type '{result.name}' (imported from modules "
                            f"'{modules_str}'); use {hints} to disambiguate"
                        ),
                        module_name=env.name,
                        filename=env.module.filename,
                        node=tref,
                    )
                )
                return None
            if result.error is TypeResolveErrorKind.UNKNOWN_TYPE:
                self._emit(
                    diag_from_node(
                        kind="error",
                        message=f"[SIG-0019] unknown type '{result.name}' in module '{env.name}'",
                        module_name=env.name,
                        filename=env.module.filename,
                        node=tref,
                    )
                )
                return None
            if result.error in (TypeResolveErrorKind.UNKNOWN_MODULE, TypeResolveErrorKind.MODULE_NOT_IMPORTED):
                self._emit(
                    diag_from_node(
                        kind="error",
                        message=f"[SIG-0019] unknown type '{result.name}' in module '{env.name}'",
                        module_name=env.name,
                        filename=env.module.filename,
                        node=tref,
                    )
                )
                return None
            if result.error is TypeResolveErrorKind.UNRESOLVED_ALIAS:
                return None
            if result.error is TypeResolveErrorKind.INVALID_NULLABLE_VOID:
                self._emit(
                    diag_from_node(
                        kind="error",
                        message="[SIG-0011] type 'void' cannot be nullable",
                        module_name=env.name,
                        filename=env.module.filename,
                        node=tref,
                    )
                )
                return None
            if result.error in (TypeResolveErrorKind.NOT_A_TYPE, TypeResolveErrorKind.VARIANT_AS_TYPE):
                self._emit(
                    diag_from_node(
                        kind="error",
                        message=(
                            f"[SIG-0010] symbol '{result.name}' in module '{env.name}' "
                            f"is not a type (kind={result.symbol.kind.name})"
                        ),
                        module_name=env.name,
                        filename=env.module.filename,
                        node=tref,
                    )
                )
                return None

        return result.type

    def _resolve_type_alias_symbol(
            self,
            env: ModuleEnv,
            sym: Symbol,
            alias_stack: set[SymbolKey] | None = None,
    ) -> Type | None:
        """Resolve a TYPE_ALIAS symbol to its target Type.

        Caches the result in `sym.type`. Detects recursive alias cycles.

        Args:
            env: Current module environment.
            sym: The type alias symbol to resolve.
            alias_stack: Set of alias identifiers currently being resolved.

        Returns:
            The target Type if successful, otherwise None.
        """
        if sym.type is not None:
            return sym.type

        key = (sym.module.name, sym.name)

        if alias_stack is None:
            alias_stack = set()

        if key in alias_stack:
            self._emit(
                diag_from_node(
                    kind="error",
                    message=(
                        f"[SIG-0020] cyclic type alias involving '{sym.name}' in module "
                        f"'{sym.module.name}'"
                    ),
                    module_name=env.name,
                    filename=sym.module.filename,
                    node=(sym.node if isinstance(sym.node, Node) else None)
                )
            )
            return None

        alias_stack.add(key)

        decl = sym.node
        if not isinstance(decl, TypeAliasDecl):
            # Defensive check - this should not happen if name resolution is correct
            self._emit(
                diag_from_node(
                    kind="error",
                    message=(
                        f"[SIG-9029] internal error: TYPE_ALIAS symbol '{sym.name}' does not "
                        f"reference a TypeAliasDecl"
                    ),
                    module_name=env.name,
                    filename=env.module.filename,
                    node=(decl if isinstance(decl, Node) else None),
                )
            )
            alias_stack.remove(key)
            return None

        target_tref = decl.target
        target_type = self._resolve_type_ref(env, target_tref, alias_stack)

        alias_stack.remove(key)

        if target_type is not None:
            sym.type = target_type
        return target_type

    # --- per decl kind ---

    def _resolve_struct(self, env: ModuleEnv, decl: StructDecl) -> None:
        """Resolve field types for a struct declaration."""
        struct_sym = env.locals.get(decl.name)
        if struct_sym is None:
            return

        struct_ty = StructType(env.name, decl.name)
        struct_sym.type = struct_ty

        fields_info: list[StructFieldInfo] = []

        for field in decl.fields:
            assert isinstance(field, FieldDecl)
            ftype = self._resolve_type_ref(env, field.type)
            if ftype is None:
                # error already emitted
                continue
            fields_info.append(StructFieldInfo(name=field.name, type=ftype))

        key = (env.name, decl.name)
        self.struct_infos[key] = StructInfo(struct_type=struct_ty, fields=fields_info)

    def _resolve_enum(self, env: ModuleEnv, decl: EnumDecl) -> None:
        """Resolve variant payload types for an enum declaration."""
        enum_sym = env.locals.get(decl.name)
        if enum_sym is None:
            return

        enum_ty = EnumType(env.name, decl.name)
        enum_sym.type = enum_ty

        variant_infos: dict[str, EnumVariantInfo] = {}

        for variant in decl.variants:
            assert isinstance(variant, EnumVariant)
            field_types: list[Type] = []
            for field in variant.fields:
                assert isinstance(field, FieldDecl)
                ftype = self._resolve_type_ref(env, field.type)
                if ftype is None:
                    continue
                field_types.append(ftype)
            variant_infos[variant.name] = EnumVariantInfo(
                name=variant.name, field_types=field_types
            )

        key = (env.name, decl.name)
        self.enum_infos[key] = EnumInfo(enum_type=enum_ty, variants=variant_infos)

        # Also annotate enum-variant symbols with their (tuple) payload type
        for variant in decl.variants:
            sym = env.locals.get(variant.name)
            if sym is not None and sym.kind == SymbolKind.ENUM_VARIANT:
                info = variant_infos[variant.name]
                # Represent variant as a function-like type: (payload...) -> EnumType
                sym.type = FuncType(tuple(info.field_types), enum_ty)

    def _resolve_func(self, env: ModuleEnv, decl: FuncDecl) -> None:
        """Resolve parameter and return types for a function declaration."""
        func_sym = env.locals.get(decl.name)
        if func_sym is None:
            return

        param_types: list[Type] = []
        ok = True

        for param in decl.params:
            ptype = self._resolve_type_ref(env, param.type)
            if ptype is None:
                ok = False
                continue
            param_types.append(ptype)

        result_type = self._resolve_type_ref(env, decl.return_type)
        if result_type is None:
            ok = False

        if not ok:
            return

        ft = FuncType(tuple(param_types), result_type)
        func_sym.type = ft

        key = (env.name, decl.name)
        self.func_types[key] = ft

    def _resolve_type_alias(self, env: ModuleEnv, decl: TypeAliasDecl) -> None:
        """Resolve the target type for a type alias."""
        alias_sym = env.locals.get(decl.name)
        if alias_sym is None:
            return

        self._resolve_type_alias_symbol(env, alias_sym, alias_stack=None)

    def _resolve_let(self, env: ModuleEnv, decl: LetDecl) -> None:
        """Resolve or infer the type for a module-level 'let' binding."""
        let_sym = env.locals.get(decl.name)
        if let_sym is None:
            return

        # Resolve type annotation if present
        if decl.type is not None:
            let_type = self._resolve_type_ref(env, decl.type)
            if let_type is None:
                return
        else:
            # Infer type from initializer for simple literals
            let_type = self._infer_literal_type(env, decl.value)
            if let_type is None:
                self._emit(
                    diag_from_node(
                        kind="error",
                        message=f"[SIG-0030] cannot infer type for let '{decl.name}' - type annotation required for non-literal initializers",
                        module_name=env.name,
                        filename=env.module.filename,
                        node=decl
                    )
                )
                return

        let_sym.type = let_type
        key = (env.name, decl.name)
        self.let_types[key] = let_type

    def _infer_literal_type(self, env: ModuleEnv, expr : Expr) -> Type | None:
        """Infer type from simple literal expressions and struct/enum construction."""
        if isinstance(expr, IntLiteral):
            return get_builtin_type("int")
        elif isinstance(expr, BoolLiteral):
            return get_builtin_type("bool")
        elif isinstance(expr, ByteLiteral):
            return get_builtin_type("byte")
        elif isinstance(expr, StringLiteral):
            return get_builtin_type("string")
        elif isinstance(expr, NullLiteral):
            # Cannot infer type from null - need annotation
            return None
        elif isinstance(expr, VarRef):
            sym_result = resolve_symbol(self.module_envs, env.name, expr.name, module_path=expr.module_path)
            sym = sym_result.symbol
            if sym is not None and self._symbol_is_zero_arg_enum_variant(sym):
                return self._enum_type_for_variant_symbol(sym)
            return None
        elif isinstance(expr, CallExpr) and isinstance(expr.callee, VarRef):
            # Struct or enum variant construction: Point(1, 2) or Color.Red
            name = expr.callee.name
            sym_result = resolve_symbol(self.module_envs, env.name, name, module_path=expr.callee.module_path)
            sym = sym_result.symbol
            if sym is None:
                return None

            if sym.kind is SymbolKind.STRUCT:
                return StructType(sym.module.name, sym.name)

            if sym.kind is SymbolKind.TYPE_ALIAS and isinstance(sym.type, StructType):
                return sym.type

            if sym.kind is SymbolKind.ENUM_VARIANT:
                for decl in sym.module.decls:
                    if isinstance(decl, EnumDecl):
                        for variant in decl.variants:
                            if variant.name == name:
                                return EnumType(sym.module.name, decl.name)
                return None

            return None
        else:
            # Non-literal expressions need type annotation
            return None

    def _symbol_is_zero_arg_enum_variant(self, sym: Symbol) -> bool:
        """Return whether a symbol names a zero-argument enum variant."""
        return (
            sym.kind is SymbolKind.ENUM_VARIANT
            and isinstance(sym.node, EnumVariant)
            and len(sym.node.fields) == 0
        )

    def _enum_type_for_variant_symbol(self, sym: Symbol) -> EnumType | None:
        """Return the owning enum type for an enum variant symbol."""
        for decl in sym.module.decls:
            if isinstance(decl, EnumDecl):
                for variant in decl.variants:
                    if variant is sym.node:
                        return EnumType(sym.module.name, decl.name)
        return None

    def _extract_value_type_dependencies(self, typ: Type) -> set[SymbolKey]:
        """Extract type dependencies for value fields only (pointer-free)."""
        if isinstance(typ, PointerType):
            # Pointers don't create dependencies
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

    def _detect_value_type_cycles(self) -> None:
        """Detect and report cycles in value-type definitions.

        Value-type cycles (where A contains B and B contains A directly) create
        infinite-size types and are prohibited. Pointers must be used to
        break such cycles.
        """
        # dependency graph maps (module, type) to the set of (module, type) it depends on for value fields
        graph: dict[SymbolKey, set[SymbolKey]] = {}

        # Process all structs
        for (mod_name, struct_name), struct_info in self.struct_infos.items():
            key = (mod_name, struct_name)
            deps = set()

            for field in struct_info.fields:
                field_deps = self._extract_value_type_dependencies(field.type)
                deps.update(field_deps)

            graph[key] = deps

        # Process all enums
        for (mod_name, enum_name), enum_info in self.enum_infos.items():
            key = (mod_name, enum_name)
            deps = set()

            for variant_info in enum_info.variants.values():
                for field_type in variant_info.field_types:
                    field_deps = self._extract_value_type_dependencies(field_type)
                    deps.update(field_deps)

            graph[key] = deps

        # Perform topological sort to detect cycles
        from collections import deque

        in_degree = {node: len(graph[node]) for node in graph}
        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        processed = []

        while queue:
            node = queue.popleft()
            processed.append(node)

            # Reduce in-degree of dependents
            for dependent in graph:
                if node in graph[dependent]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        # Check for cycles
        if len(processed) != len(graph):
            # Find nodes involved in cycle
            unresolved = [node for node in graph if node not in processed]

            # Format cycle details for error message
            cycle_parts = []
            for node in unresolved[:3]:  # Limit to first 3 for readability
                deps = [f"{m}::{n}" for m, n in graph.get(node, set()) if (m, n) in unresolved]
                node_str = f"{node[0]}::{node[1]}"
                if deps:
                    cycle_parts.append(f"{node_str} depends on {', '.join(deps)}")

            cycle_desc = "; ".join(cycle_parts)

            # Find a struct or enum decl in the cycle to attach the diagnostic to
            first_node = unresolved[0]
            module = self.cu.modules.get(first_node[0])
            target_decl = None

            if module:
                for decl in module.decls:
                    if isinstance(decl, (StructDecl, EnumDecl)) and decl.name == first_node[1]:
                        target_decl = decl
                        break

            self._emit(
                diag_from_node(
                    kind="error",
                    message=(
                        f"[SIG-0040] Value-type cycle detected: {cycle_desc}. "
                        f"This creates infinite-size types. "
                        f"Consider using pointers to break the cycle."
                    ),
                    module_name=first_node[0],
                    filename=module.filename if module else None,
                    node=target_decl
                )
            )
