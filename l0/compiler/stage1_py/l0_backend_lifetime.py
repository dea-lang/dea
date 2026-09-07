# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from l0_ast import DropStmt, Expr, StringLiteral, ParenExpr, CastExpr
from l0_scope_context import ScopeContext
from l0_types import Type, StructType, EnumType, NullableType, format_type
from l0_backend_convert import OwnershipConversion
from l0_backend_state import BackendState


@dataclass
class ValueLifetime:
    """ARC materialization, value retention/cleanup, and drop operations."""

    convert: OwnershipConversion
    state: BackendState

    def _is_unwrap_cast_from_place(self, expr: Expr) -> bool:
        """Check if a cast expression still borrows from an existing owner.

        Outer parentheses are ownership-transparent. Owner-producing ARC
        value-optional wraps are excluded.

        Args:
            expr: The expression to check.

        Returns:
            True for non-owner-producing casts whose source is a place.
        """
        while isinstance(expr, ParenExpr):
            expr = expr.inner
        if not isinstance(expr, CastExpr) or not self.state._is_place_expr(expr.expr):
            return False

        src_ty = self.state.analysis.expr_types.get(id(expr.expr))
        dst_ty = self.state.analysis.expr_types.get(id(expr))
        if (
            isinstance(dst_ty, NullableType)
            and self.state._types_equal(src_ty, dst_ty.inner)
            and not self.state.emitter.types.is_niche_nullable(dst_ty)
            and self.state.analysis.has_arc_data(dst_ty.inner)
        ):
            return False
        return True

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
            self.state.analysis.has_arc_data(expr_type)
            and not self.state._is_place_expr(expr)
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
        temp = self.state.emitter.names.fresh_tmp("arc")
        self.state.emitter.statements.emit_temp_decl(self.state.emitter.types.emit_type(expr_type), temp, c_expr)
        self.state._current_scope.add_owned(temp, expr_type)
        return temp

    def _emit_cleanup_at_scope_exit(self, scope: ScopeContext) -> None:
        """Emit cleanup at scope exit.

        Only cleans variables declared in THIS scope that have owned fields.

        Args:
            scope: The scope being exited.
        """
        for var_name, var_type in reversed(scope.owned_vars):
            if self.state.analysis.has_arc_data(var_type):
                self._emit_value_cleanup(var_name, var_type)

    def _emit_value_cleanup(self, c_expr: str, ty: Type) -> None:
        """Emit cleanup code for a by-value variable before reassignment.

        Similar to _emit_field_cleanup, but expects c_expr to be a direct
        value reference (not a pointer), so uses '.' instead of '->'.

        Args:
            c_expr: C expression for the value (e.g., "x__v", "obj.field")
            ty: The type of the value being cleaned up
        """
        self.state.emitter.cleanup.emit_value_cleanup(c_expr, ty)

    def _emit_struct_cleanup(self, c_ptr_expr: str, struct_type: StructType) -> None:
        """Emit cleanup code for all owned fields in a struct.

        Recursively handles nested structs (by-value fields).

        Args:
            c_ptr_expr: C expression evaluating to a pointer to the struct.
            struct_type: The struct type.
        """
        self.state.emitter.cleanup.emit_struct_cleanup(c_ptr_expr, struct_type)

    def _emit_enum_cleanup(self, c_ptr_expr: str, enum_type: EnumType) -> None:
        """Emit cleanup code for owned fields in an enum's active variant.

        Uses switch on tag to only clean up the fields that are actually present.

        Args:
            c_ptr_expr: C expression evaluating to a pointer to the enum.
            enum_type: The enum type.
        """
        self.state.emitter.cleanup.emit_enum_cleanup(c_ptr_expr, enum_type)

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
        if self.state.analysis.is_arc_type(ty):
            self.state.emitter.cleanup.emit_string_retain(c_expr)
            return

        if isinstance(ty, NullableType):
            if self.state.emitter.types.is_niche_nullable(ty):
                return
            if not self.state.analysis.has_arc_data(ty.inner):
                return

            self.state.emitter.statements.emit_if_header(self.state.emitter.values.emit_optional_has_value(c_expr))
            self.state.emitter.statements.emit_block_start()
            self._emit_retain_for_copied_value(self.state.emitter.values.emit_optional_value(c_expr), ty.inner)
            self.state.emitter.statements.emit_block_end()
            return

        if isinstance(ty, StructType):
            info = self.state.analysis.struct_infos.get((ty.module, ty.name))
            if info is None:
                return
            for field in info.fields:
                self._emit_retain_for_copied_value(self.state.emitter.values.emit_field_access(c_expr, field.name, False), field.type)
            return

        if isinstance(ty, EnumType):
            enum_info = self.state.analysis.enum_infos.get((ty.module, ty.name))
            if enum_info is None:
                return

            self.state.emitter.statements.emit_switch_start(self.state.emitter.values.emit_enum_tag_access(c_expr))
            for variant_name, variant_info in enum_info.variants.items():
                c_tag = self.state.emitter.names.emit_enum_tag(ty, variant_name)
                self.state.emitter.statements.emit_case_label(c_tag)
                self.state.emitter.statements.emit_block_start()

                variant_decl = self.state.find_variant_decl(ty.module, ty.name, variant_name)
                if variant_decl is None:
                    self.state.ice(f"[ICE-1304] missing variant decl for {ty.module}.{ty.name}.{variant_name}")

                for field, field_ty in zip(variant_decl.fields, variant_info.field_types):
                    field_expr = self.state.emitter.values.emit_enum_payload_field_access(c_expr, variant_name, field.name)
                    self._emit_retain_for_copied_value(field_expr, field_ty)

                self.state.emitter.statements.emit_exit_switch()
                self.state.emitter.statements.emit_block_end()

            self.state.emitter.declarations.emit_unreachable_marker("retain")
            self.state.emitter.statements.emit_switch_end()

    def _emit_copy_expr_with_retains(self, c_expr: str, ty: Type) -> str:
        """Materialize copied values in a temp and emit retain logic when needed.

        Args:
            c_expr: C expression evaluating to the value.
            ty: The type of the value.

        Returns:
            The name of the temporary containing the copied and retained value.
        """
        if not self.state.analysis.has_arc_data(ty):
            return c_expr

        temp = self.state.emitter.names.fresh_tmp("copy")
        self.state.emitter.statements.emit_temp_decl(self.state.emitter.types.emit_type(ty), temp, c_expr)
        self._emit_retain_for_copied_value(temp, ty)
        return temp

    def _emit_drop(self, stmt: DropStmt, module_name: str) -> None:
        """Emit drop statement with automatic cleanup of owned fields.

        For structs: releases all string fields.
        For enums: switches on tag, releases strings in active variant.
        Then calls the drop-finish helper to release the memory.

        Args:
            stmt: The DropStmt AST node.
            module_name: Name of current module.

        Raises:
            InternalCompilerError: If variable is undefined or not a pointer.
        """
        c_name = self.state.emitter.names.mangle_identifier(stmt.name)

        # Look up the type from the scope chain first (for local variables)
        var_type = self.state._lookup_local_var_type(stmt.name)

        # If not found in scope, try module environment (for parameters, etc.)
        if var_type is None:
            var_sym = self.state._lookup_symbol(stmt.name, module_name)
            if var_sym is None:
                self.state.ice(f"[ICE-1060] undefined variable in drop: {stmt.name}", node=stmt)
            var_type = var_sym.type

        ptr_type = self.state._pointer_type_or_none(var_type)
        if ptr_type is None:
            self.state.ice(f"[ICE-1061] drop requires pointer type, got '{format_type(var_type)}'", node=stmt)

        inner_type = ptr_type.inner
        drop_tmp = self.state.emitter.names.fresh_tmp("drop")
        c_ptr_type = self.state.emitter.types.emit_type(ptr_type)
        self.state.emitter.statements.emit_temp_decl(
            c_ptr_type,
            drop_tmp,
            self.state.emitter.values.emit_drop_begin_expr(
                c_name,
                c_ptr_type,
                self.convert._sizeof_expr_for_type(inner_type),
                self.convert._alignof_expr_for_type(inner_type),
            ),
        )

        # Emit cleanup for owned fields before freeing.
        if isinstance(inner_type, StructType):
            self._emit_struct_cleanup(drop_tmp, inner_type)
        elif isinstance(inner_type, EnumType):
            self._emit_enum_cleanup(drop_tmp, inner_type)
        elif self.state.analysis.is_arc_type(inner_type):
            # Release the ARC value before freeing the container
            c_cond = self.state.emitter.values.emit_pointer_null_check(drop_tmp, "!=")
            self.state.emitter.statements.emit_if_header(c_cond)
            self.state.emitter.statements.emit_block_start()
            self.state.emitter.cleanup.emit_string_release(f"*{drop_tmp}")
            self.state.emitter.statements.emit_block_end()
        # For other builtin types or other pointers, no special cleanup needed

        # Emit the actual drop
        self.state.emitter.cleanup.emit_drop_finish_call(drop_tmp)
        self.state.emitter.statements.emit_null_assignment(c_name)
