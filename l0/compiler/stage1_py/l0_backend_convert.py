# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass
from l0_ast import Node, CallExpr
from l0_types import Type, BuiltinType, NullableType, format_type
from l0_backend_state import BackendState


@dataclass
class OwnershipConversion:
    """Checked pointer access and ownership-preserving value conversions."""

    state: BackendState

    def _sizeof_expr_for_type(self, ty: Type) -> str:
        """Return a C ``sizeof`` expression for the runtime access extent."""
        if isinstance(ty, BuiltinType) and ty.name == "void":
            return "1"
        return f"sizeof({self.state.emitter.types.emit_type(ty)})"

    def _alignof_expr_for_type(self, ty: Type) -> str:
        """Return a C alignment expression for the runtime access target."""
        if isinstance(ty, BuiltinType) and ty.name == "void":
            return "1"
        return f"_RT_ALIGNOF({self.state.emitter.types.emit_type(ty)})"

    def _emit_checked_pointer_expr(
        self,
        c_ptr_expr: str,
        ptr_ty: Type,
        node: Node | None = None,
        access_mode: str = "_RT_ACCESS_READ",
    ) -> str:
        """Emit a pointer expression checked for one pointee-sized access."""
        represented_ptr = self.state._pointer_type_or_none(ptr_ty)
        if represented_ptr is None:
            self.state.ice(f"[ICE-1245] expected pointer type, got '{format_type(ptr_ty)}'", node=node)

        c_ptr_ty = self.state.emitter.types.emit_type(represented_ptr)
        required_size = self._sizeof_expr_for_type(represented_ptr.inner)
        required_align = self._alignof_expr_for_type(represented_ptr.inner)
        return self.state.emitter.values.emit_checked_ptr_access(c_ptr_expr, c_ptr_ty, required_size, required_align, access_mode)

    def _emit_pointer_index_lvalue(
        self,
        c_base: str,
        c_index: str,
        base_ty: Type,
        node: Node | None = None,
        access_mode: str = "_RT_ACCESS_WRITE",
    ) -> str:
        """Emit a checked pointer-index lvalue expression."""
        ptr_ty = self.state._pointer_type_or_none(base_ty)
        if ptr_ty is None:
            self.state.ice(f"[ICE-1246] expected pointer index base, got '{format_type(base_ty)}'", node=node)

        c_ptr_ty = self.state.emitter.types.emit_type(ptr_ty)
        checked = self.state.emitter.values.emit_checked_ptr_index_access(
            c_base,
            c_index,
            c_ptr_ty,
            self._sizeof_expr_for_type(ptr_ty.inner),
            self._alignof_expr_for_type(ptr_ty.inner),
            access_mode,
        )
        return self.state.emitter.values.emit_deref_lvalue(checked)

    def _convert_expr_with_expected_type(self, c_expr: str, natural_ty: Type | None, expected: Type) -> str:
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

        if self.state._types_equal(natural_ty, expected):
            return c_expr

        # T → T? (wrap in Some)
        if isinstance(expected, NullableType) and self.state._types_equal(expected.inner, natural_ty):
            if self.state.emitter.types.is_niche_nullable(expected):
                return c_expr  # pointer-to-pointer, no wrapping needed
            return self.state.emitter.types.emit_some_value_for_nullable(expected, c_expr)

        # byte → int (implicit widening)
        if (isinstance(natural_ty, BuiltinType) and natural_ty.name == "byte" and
                isinstance(expected, BuiltinType) and expected.name == "int"):
            return self.state.emitter.values.emit_widen_int(c_expr, natural_ty, expected)

        # No type conversion needed
        return c_expr

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
        if self.state.emitter.types.is_niche_nullable(src_ty):
            return self.state.emitter.values.emit_unwrap_ptr(c_dst, c_inner, format_type(src_ty))

        # Value-optionals: empty is !has_value.
        c_src = self.state.emitter.types.emit_type(src_ty)
        tmp = self.state.emitter.names.fresh_tmp("unwrap")
        self.state.emitter.statements.emit_temp_decl(c_src, tmp, c_inner)
        return self.state.emitter.values.emit_unwrap_opt(c_src, tmp, format_type(src_ty))

    def _emit_sizeof_intrinsic(self, expr: CallExpr) -> str:
        """Emit sizeof intrinsic.

        Args:
            expr: The sizeof call expression.

        Returns:
            A C sizeof expression string.

        Raises:
            InternalCompilerError: If target type cannot be resolved.
        """
        target_ty = self.state.analysis.intrinsic_targets.get(id(expr))
        if target_ty is None:
            self.state.ice("[ICE-1120] failed to resolve sizeof target type", node=expr)

        return self.state.emitter.types.emit_sizeof_type(target_ty)
