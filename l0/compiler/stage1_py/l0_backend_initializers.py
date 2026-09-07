# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from l0_ast import Expr, IntLiteral, StringLiteral, BoolLiteral, VarRef, CallExpr, NullLiteral, NewExpr, ByteLiteral
from l0_name_resolver import SymbolKind
from l0_types import Type, StructType, EnumType
from l0_backend_state import BackendState


@dataclass
class StaticInitializers:
    """Static initializer classification and constructor recursion."""

    state: BackendState

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
            return self.state.emitter.values.emit_int_literal(expr.value)
        elif isinstance(expr, BoolLiteral):
            return self.state.emitter.values.emit_const_bool_literal(expr.value)
        elif isinstance(expr, ByteLiteral):
            return self.state.emitter.values.emit_byte_literal(expr.value)
        elif isinstance(expr, StringLiteral):
            return self.state.emitter.values.emit_const_string_literal(expr.value)
        elif isinstance(expr, NullLiteral):
            return self.state.emitter.types.emit_null_literal(expected_type, for_initializer=True)
        elif isinstance(expr, VarRef):
            return self._emit_bare_variant_static_initializer(expr, expected_type)
        elif isinstance(expr, CallExpr) and isinstance(expr.callee, VarRef):
            # Struct or enum variant construction: Point(1, 2) or Color.Red
            return self._emit_const_constructor(expr, expected_type)
        elif isinstance(expr, NewExpr):
            # Heap allocation not allowed in top-level let initializers
            self.state.ice(
                f"[ICE-1180] new expressions not allowed in top-level let initializers (use value construction instead)",
                node=expr)
        else:
            # Unsupported initializer
            self.state.ice(f"[ICE-1181] unsupported top-level let initializer: {type(expr).__name__}", node=expr)

    def _emit_bare_variant_static_initializer(self, expr: VarRef, expected_type: Type) -> str:
        """Emit a bare zero-argument enum variant for static initialization."""
        if not self.state.current_module:
            self.state.ice("[ICE-1030] current_module not set during bare variant let initialization", node=expr)
        if not isinstance(expected_type, EnumType):
            self.state.ice("[ICE-1033] bare enum variant initializer expected enum type", node=expr)

        sym = self.state._lookup_symbol(expr.name, self.state.current_module, module_path=expr.module_path)
        if sym is None:
            self.state.ice(f"[ICE-1031] unknown bare variant name: {expr.name}", node=expr)
        if sym.kind != SymbolKind.ENUM_VARIANT:
            self.state.ice(f"[ICE-1034] VarRef is not an enum variant constructor", node=expr)

        variant_decl = self.state.find_variant_decl(expected_type.module, expected_type.name, sym.name)
        if variant_decl is None:
            self.state.ice(f"[ICE-1052] missing variant decl for {expected_type.module}.{expected_type.name}.{sym.name}",
                     node=expr)
        if variant_decl is not sym.node:
            self.state.ice(f"[ICE-1033] bare enum variant does not belong to expected enum type", node=expr)
        if len(variant_decl.fields) != 0:
            self.state.ice(f"[ICE-1053] bare enum variant initializer requires zero payload fields", node=expr)

        return self.state.emitter.values.emit_variant_static_initializer_for_type(expected_type, sym.name, [])

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
        if not self.state.current_module:
            self.state.ice("[ICE-1030] current_module not set during let initialization", node=expr)

        sym = self.state._lookup_symbol(name, self.state.current_module, module_path=expr.callee.module_path)
        if sym is None:
            self.state.ice(f"[ICE-1031] unknown constructor name: {name}", node=expr)

        # Struct constructor
        if sym.kind == SymbolKind.STRUCT or (
                sym.kind == SymbolKind.TYPE_ALIAS and isinstance(expected_type, StructType)):
            if isinstance(expected_type, StructType):
                return self._emit_const_struct_constructor(expr, expected_type)
            self.state.ice(f"[ICE-1032] struct constructor but expected_type is not StructType", node=expr)

        # Enum variant constructor
        elif sym.kind == SymbolKind.ENUM_VARIANT:
            if isinstance(expected_type, EnumType):
                return self._emit_const_variant_constructor(expr, expected_type)
            self.state.ice(f"[ICE-1033] enum variant constructor but expected_type is not EnumType", node=expr)

        else:
            self.state.ice(f"[ICE-1034] CallExpr is not a constructor", node=expr)

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
        info = self.state.analysis.struct_infos.get((struct_type.module, struct_type.name))
        if info is None:
            self.state.ice(f"[ICE-1040] missing StructInfo for {struct_type.module}.{struct_type.name}", node=expr)

        if len(info.fields) != len(expr.args):
            self.state.ice(
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
        return self.state.emitter.values.emit_struct_static_initializer_for_type(struct_type, field_inits)

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
        enum_info = self.state.analysis.enum_infos.get((enum_type.module, enum_type.name))
        if enum_info is None:
            self.state.ice(f"[ICE-1050] missing EnumInfo for {enum_type.module}.{enum_type.name}", node=expr)

        variant_info = enum_info.variants.get(variant_name)
        if variant_info is None:
            self.state.ice(f"[ICE-1051] missing VariantInfo for {variant_name}", node=expr)

        # Empty variant (no payload)
        if len(variant_info.field_types) == 0:
            return self.state.emitter.values.emit_variant_static_initializer_for_type(enum_type, variant_name, [])

        # Get field names from AST
        variant_decl = self.state.find_variant_decl(enum_type.module, enum_type.name, variant_name)
        if variant_decl is None:
            self.state.ice(f"[ICE-1052] missing variant decl for {enum_type.module}.{enum_type.name}.{variant_name}",
                     node=expr)

        if len(variant_decl.fields) != len(expr.args):
            self.state.ice(f"[ICE-1053] arity mismatch in variant constructor {variant_name}", node=expr)

        # Prepare payload initializers with constant expressions as (name, value) tuples
        payload_inits = []
        for idx, (field, arg) in enumerate(zip(variant_decl.fields, expr.args)):
            # Recursively emit constant initializer for each argument
            c_arg = self._emit_let_initializer(arg, variant_info.field_types[idx])
            payload_inits.append((field.name, c_arg))

        return self.state.emitter.values.emit_variant_static_initializer_for_type(enum_type, variant_name, payload_inits)
