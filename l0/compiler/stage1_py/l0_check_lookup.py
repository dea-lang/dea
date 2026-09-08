# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass
from l0_ast import Node, Expr, VarRef, UnaryOp, IndexExpr, FieldAccessExpr, TypeAliasDecl
from l0_logger import log_debug
from l0_resolve import resolve_symbol, resolve_type_ref, TypeResolveErrorKind, ResolveErrorKind
from l0_symbols import SymbolKind
from l0_types import Type, StructType, EnumType, format_type
from l0_check_state import CheckerState


@dataclass
class SemanticLookup:
    """Local and type lookup, declaration rules, and qualifier validation."""

    state: CheckerState

    def _declare_local(self, name: str, typ: Type, node: Node) -> None:
        """Declare a local variable in the innermost scope.

        Args:
            name: The name of the variable.
            typ: The resolved Type of the variable.
            node: The AST node where the declaration occurs.
        """
        assert self.state._local_scopes, "no active scope"
        local = self.state._local_scopes[-1]
        if name in local:
            self.state._error(node,
                        f"[TYP-0020] local variable '{name}' already declared in this scope with type '{format_type(local[name])}'")
            return None

        if self._lookup_local(name) is not None:
            self.state._warn(node, f"[TYP-0021] local variable '{name}' shadows variable from outer scope")

        if self.state._current_func_env is not None:
            module_name = self.state._current_func_env.module_name
            sym_result = resolve_symbol(self.state.module_envs, module_name, name)
            sym = sym_result.symbol
            if sym is not None and sym.kind is SymbolKind.ENUM_VARIANT:
                if sym.module.name != module_name:
                    self.state._warn(
                        node,
                        f"[TYP-0023] local variable '{name}' shadows imported enum variant '{sym.module.name}::{name}'",
                    )
                else:
                    self.state._warn(
                        node,
                        f"[TYP-0022] local variable '{name}' shadows enum variant '{sym.module.name}::{name}'",
                    )
            elif sym is not None and sym.kind in (SymbolKind.FUNC, SymbolKind.STRUCT,
                                                  SymbolKind.ENUM, SymbolKind.TYPE_ALIAS):
                kind_label = sym.kind.name.lower().replace("_", " ")
                if sym.module.name != module_name:
                    self.state._warn(
                        node,
                        f"[TYP-0025] local variable '{name}' shadows imported "
                        f"{kind_label} '{sym.module.name}::{name}'",
                    )
                else:
                    self.state._warn(
                        node,
                        f"[TYP-0025] local variable '{name}' shadows "
                        f"{kind_label} '{sym.module.name}::{name}'",
                    )
            elif sym is None and sym_result.error is ResolveErrorKind.AMBIGUOUS_SYMBOL:
                modules_str = "', '".join(sym_result.ambiguous_modules)
                self.state._warn(
                    node,
                    f"[TYP-0024] local variable '{name}' shadows ambiguous imported symbol "
                    f"(from modules '{modules_str}')",
                )

        local[name] = typ
        self.state._alive_scopes[-1][name] = True
        return None

    def _lookup_local(self, name: str) -> Type | None:
        """Look up a local variable's type in the scope stack."""
        for scope in reversed(self.state._local_scopes):
            if name in scope:
                return scope[name]
        return None

    def _lookup_local_scope_index(self, name: str) -> int | None:
        """Return scope index where local resolves (nearest scope wins)."""
        for idx in range(len(self.state._local_scopes) - 1, -1, -1):
            if name in self.state._local_scopes[idx]:
                return idx
        return None

    def _try_resolve_type_name(
            self,
            name: str,
            *,
            node: Node | None = None,
            module_path: list[str] | None = None,
    ) -> Type | None:
        """Try to resolve an identifier as a type name."""
        assert self.state._current_func_env is not None
        module_name = self.state._current_func_env.module_name

        sym_result = resolve_symbol(self.state.module_envs, module_name, name, module_path=module_path)
        sym = sym_result.symbol
        if sym is None:
            if module_path and sym_result.error in (ResolveErrorKind.UNKNOWN_MODULE,
                                                    ResolveErrorKind.MODULE_NOT_IMPORTED):
                qualified_name = f"{'.'.join(module_path)}::{name}"
                if node is not None:
                    if sym_result.error is ResolveErrorKind.UNKNOWN_MODULE:
                        self.state._error(
                            node,
                            f"[TYP-0300] unknown type '{qualified_name}' (unknown module '{sym_result.module_name}')",
                        )
                    else:
                        self.state._error(
                            node,
                            f"[TYP-0301] unknown type '{qualified_name}' (module '{sym_result.module_name}' not imported)",
                        )
            elif sym_result.error is ResolveErrorKind.AMBIGUOUS_SYMBOL and node is not None:
                modules_str = "', '".join(sym_result.ambiguous_modules)
                hints = " or ".join(f"'{m}::{name}'" for m in sym_result.ambiguous_modules)
                self.state._error(
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
            ctx = getattr(self.state.analysis, "context", None)
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

    def _resolve_type_ref(self, tref) -> Type | None:
        """Resolve a TypeRef to a semantic Type."""
        if self.state._current_func_env is None:
            return None

        # Reject overqualified type references (e.g. color::Color::Red as a type)
        if self._reject_name_qualifier(tref, tref.name, tref.name_qualifier, tref.module_path):
            return None

        module_name = self.state._current_func_env.module_name
        result = resolve_type_ref(self.state.module_envs, module_name, tref, module_path=tref.module_path)
        if result.type is None:
            if result.error is TypeResolveErrorKind.INVALID_NULLABLE_VOID:
                self.state._error(tref, "[TYP-0278] type 'void' cannot be nullable")
                return None
            if result.error is TypeResolveErrorKind.VARIANT_AS_TYPE:
                return None
            if result.error is TypeResolveErrorKind.AMBIGUOUS_TYPE:
                modules_str = "', '".join(result.ambiguous_modules)
                hints = " or ".join(f"'{m}::{result.name}'" for m in result.ambiguous_modules)
                self.state._error(
                    tref,
                    f"[TYP-0279] ambiguous type '{result.name}' (imported from modules '{modules_str}'); "
                    f"use {hints} to disambiguate",
                )
                return None
            if result.error is TypeResolveErrorKind.UNKNOWN_TYPE:
                self.state._error(
                    tref,
                    f"[TYP-0279] unknown type '{result.name}' in module '{result.module_name}'",
                )
                return None
            if result.error in (TypeResolveErrorKind.UNKNOWN_MODULE, TypeResolveErrorKind.MODULE_NOT_IMPORTED):
                self.state._error(
                    tref,
                    f"[TYP-0279] unknown type '{result.name}' in module '{result.module_name}'",
                )
                return None
            if result.error is TypeResolveErrorKind.UNRESOLVED_ALIAS:
                self.state._error(
                    tref,
                    f"[TYP-0270] type alias '{result.name}' in module '{module_name}'"
                    " does not have a resolved type",
                )
                return None
            if result.error is TypeResolveErrorKind.NOT_A_TYPE:
                self.state._error(
                    tref,
                    f"[TYP-0271] symbol '{result.name}' in module '{module_name}' "
                    f"is not a type (kind={result.symbol.kind.name})",
                )
                return None

        return result.type

    def _reject_name_qualifier(
            self,
            node: Node,
            name: str,
            name_qualifier: list[str] | None,
            module_path: list[str] | None,
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
        self.state._error(
            node,
            f"[TYP-0158] nested symbol path '{full}': "
            f"paths must have the form 'module::symbol' (did you mean '{simple}'?)",
        )
        return True

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
