#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Common logic for symbol and type reference resolution in the L0 compiler.

This module provides utility functions used by various compiler stages to
lookup symbols and resolve AST type references into semantic types.
"""

from dataclasses import dataclass
from enum import Enum, auto
from collections.abc import Callable

from l0_ast import TypeRef
from l0_symbols import ModuleEnv, Symbol, SymbolKind
from l0_types import (
    Type,
    BuiltinType,
    StructType,
    EnumType,
    PointerType,
    NullableType,
    get_builtin_type,
    L0_PRIMITIVE_TYPES,
)


class ResolveErrorKind(Enum):
    """Kinds of errors that can occur during symbol resolution."""
    UNKNOWN_MODULE = auto()
    MODULE_NOT_IMPORTED = auto()
    UNKNOWN_SYMBOL = auto()
    AMBIGUOUS_SYMBOL = auto()


class TypeResolveErrorKind(Enum):
    """Kinds of errors that can occur during type resolution."""
    UNKNOWN_TYPE = auto()
    NOT_A_TYPE = auto()
    UNRESOLVED_ALIAS = auto()
    VARIANT_AS_TYPE = auto()
    UNKNOWN_MODULE = auto()
    MODULE_NOT_IMPORTED = auto()
    INVALID_NULLABLE_VOID = auto()
    AMBIGUOUS_TYPE = auto()


@dataclass(frozen=True)
class SymbolResolution:
    """The result of a symbol resolution attempt.

    Attributes:
        symbol: The resolved Symbol if successful, otherwise None.
        error: The kind of error that occurred, or None if successful.
        module_name: The name of the module where resolution was attempted.
        name: The name of the symbol being resolved.
        ambiguous_modules: Tuple of module names if resolution failed due to ambiguity.
    """
    symbol: Symbol | None
    error: ResolveErrorKind | None
    module_name: str
    name: str
    ambiguous_modules: tuple[str, ...] | None = None


@dataclass(frozen=True)
class TypeResolution:
    """The result of a type reference resolution attempt.

    Attributes:
        type: The resolved Type if successful, otherwise None.
        error: The kind of error that occurred, or None if successful.
        module_name: The name of the module where resolution was attempted.
        name: The name of the type being resolved.
        symbol: The Symbol object corresponding to the type, if applicable.
        ambiguous_modules: Tuple of module names if resolution failed due to ambiguity.
    """
    type: Type | None
    error: TypeResolveErrorKind | None
    module_name: str
    name: str
    symbol: Symbol | None = None
    ambiguous_modules: tuple[str, ...] | None = None


def _is_imported(current_env: ModuleEnv, module_name: str) -> bool:
    """Check if a module is explicitly imported by the current environment."""
    return any(imp.name == module_name for imp in current_env.module.imports)


def resolve_symbol(
        module_envs: dict[str, ModuleEnv],
        current_module: str,
        name: str,
        module_path: list[str] | None = None,
        *,
        require_import: bool = True,
) -> SymbolResolution:
    """Resolve a symbol by name, optionally qualified by module path.

    Args:
        module_envs: The mapping of module names to their environments.
        current_module: The name of the module performing the lookup.
        name: The name of the symbol to resolve.
        module_path: Optional list of module components for qualified names.
        require_import: Whether to require an explicit import for qualified lookups.

    Returns:
        A SymbolResolution object containing the result or error information.
    """
    module_name = ".".join(module_path) if module_path else current_module
    current_env = module_envs.get(current_module)

    # Treat lookups qualified with the current module as unqualified
    if module_path is not None and module_name == current_module:
        module_path = None

    if module_path and require_import:
        if current_env is None:
            return SymbolResolution(None, ResolveErrorKind.UNKNOWN_MODULE, module_name, name)
        if not _is_imported(current_env, module_name):
            return SymbolResolution(None, ResolveErrorKind.MODULE_NOT_IMPORTED, module_name, name)

    env = module_envs.get(module_name)
    if env is None:
        return SymbolResolution(None, ResolveErrorKind.UNKNOWN_MODULE, module_name, name)

    sym = env.locals.get(name) if module_path else env.all.get(name)
    if sym is None:
        # For unqualified lookups, check if the name is ambiguous
        if not module_path and name in env.ambiguous_imports:
            modules = tuple(env.ambiguous_imports[name])
            return SymbolResolution(None, ResolveErrorKind.AMBIGUOUS_SYMBOL,
                                    module_name, name, ambiguous_modules=modules)
        return SymbolResolution(None, ResolveErrorKind.UNKNOWN_SYMBOL, module_name, name)

    return SymbolResolution(sym, None, module_name, name)


def resolve_type_ref(
        module_envs: dict[str, ModuleEnv],
        current_module: str,
        tref: TypeRef,
        module_path: list[str] | None = None,
        *,
        resolve_alias: Callable[[Symbol], Type | None] | None = None,
        require_import: bool = True,
) -> TypeResolution:
    """Resolve an AST TypeRef into a semantic Type.

    Args:
        module_envs: The mapping of module names to their environments.
        current_module: The name of the module performing the resolution.
        tref: The TypeRef AST node.
        module_path: Optional list of module components for qualified types.
        resolve_alias: Optional callback to resolve type aliases.
        require_import: Whether to require an explicit import for qualified lookups.

    Returns:
        A TypeResolution object containing the result or error information.
    """
    base_name = tref.name

    if module_path is None and base_name in L0_PRIMITIVE_TYPES:
        base: Type = get_builtin_type(base_name)
        if tref.is_nullable and base_name == "void" and tref.pointer_depth == 0:
            return TypeResolution(None, TypeResolveErrorKind.INVALID_NULLABLE_VOID, current_module, base_name)
        t: Type = base
        for _ in range(tref.pointer_depth):
            t = PointerType(t)
        if tref.is_nullable:
            t = NullableType(t)
        return TypeResolution(t, None, current_module, base_name)

    sym_result = resolve_symbol(
        module_envs,
        current_module,
        base_name,
        module_path,
        require_import=require_import,
    )

    if sym_result.symbol is None:
        if sym_result.error is ResolveErrorKind.UNKNOWN_MODULE:
            err = TypeResolveErrorKind.UNKNOWN_MODULE
        elif sym_result.error is ResolveErrorKind.MODULE_NOT_IMPORTED:
            err = TypeResolveErrorKind.MODULE_NOT_IMPORTED
        elif sym_result.error is ResolveErrorKind.AMBIGUOUS_SYMBOL:
            return TypeResolution(
                None, TypeResolveErrorKind.AMBIGUOUS_TYPE, sym_result.module_name, base_name,
                ambiguous_modules=sym_result.ambiguous_modules,
            )
        else:
            err = TypeResolveErrorKind.UNKNOWN_TYPE
        return TypeResolution(None, err, sym_result.module_name, base_name)

    sym = sym_result.symbol
    if sym.kind is SymbolKind.STRUCT:
        base = StructType(sym.module.name, sym.name)
    elif sym.kind is SymbolKind.ENUM:
        base = EnumType(sym.module.name, sym.name)
    elif sym.kind is SymbolKind.TYPE_ALIAS:
        base = resolve_alias(sym) if resolve_alias is not None else sym.type
        if base is None:
            return TypeResolution(None, TypeResolveErrorKind.UNRESOLVED_ALIAS, sym_result.module_name, base_name, sym)
    elif sym.kind is SymbolKind.ENUM_VARIANT:
        return TypeResolution(None, TypeResolveErrorKind.VARIANT_AS_TYPE, sym_result.module_name, base_name, sym)
    else:
        return TypeResolution(None, TypeResolveErrorKind.NOT_A_TYPE, sym_result.module_name, base_name, sym)

    if tref.is_nullable and isinstance(base, BuiltinType) and base.name == "void" and tref.pointer_depth == 0:
        return TypeResolution(None, TypeResolveErrorKind.INVALID_NULLABLE_VOID, sym_result.module_name, base_name, sym)

    t = base
    for _ in range(tref.pointer_depth):
        t = PointerType(t)

    if tref.is_nullable:
        t = NullableType(t)

    return TypeResolution(t, None, sym_result.module_name, base_name, sym)
