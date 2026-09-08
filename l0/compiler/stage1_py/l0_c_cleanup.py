# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass
from collections.abc import Callable
from l0_signatures import EnumInfo
from l0_types import Type, StructType, EnumType, PointerType, NullableType
from l0_c_names import CNames
from l0_c_state import CEmitterState
from l0_c_values import CValues


@dataclass
class CCleanup:
    """Recursive value cleanup and allocation/ARC runtime operations."""

    names: CNames
    state: CEmitterState
    values: CValues

    def emit_value_cleanup(self, c_expr: str, ty: Type) -> None:
        """Emit C code to clean up an owned by-value variable.

        Args:
            c_expr: C expression evaluating to the value.
            ty: The L0 Type of the value.
        """
        self._emit_cleanup_by_type(c_expr, ty)

    def _emit_cleanup_by_type(self, c_expr: str, ty: Type) -> None:
        """Emit recursive cleanup code for any ARC-managed data inside a type.

        Args:
            c_expr: C expression evaluating to the by-value object to clean up.
            ty: The L0 type describing ``c_expr``.

        See Also:
            `emit_value_cleanup`: Public entry point for by-value cleanup emission.
            `_emit_enum_value_cleanup`: Handles enum-specific cleanup lowering.
        """
        if self.state.analysis.is_arc_type(ty):
            self.state.out.emit(f"rt_string_release({c_expr});")
            return

        if isinstance(ty, NullableType):
            if isinstance(ty.inner, PointerType):
                return
            if not self.state.analysis.has_arc_data(ty.inner):
                return
            self.state.out.emit(f"if ({self.values.emit_optional_has_value(c_expr)}) {{")
            self.state.out.indent()
            self._emit_cleanup_by_type(self.values.emit_optional_value(c_expr), ty.inner)
            self.state.out.dedent()
            self.state.out.emit("}")
            return

        if isinstance(ty, StructType):
            info = self.state._get_struct_info(ty, strict=False)
            if info is None:
                return

            for field_ in info.fields:
                self._emit_cleanup_by_type(self.values.emit_field_access(c_expr, field_.name, False), field_.type)
            return

        if isinstance(ty, EnumType):
            self._emit_enum_value_cleanup(c_expr, ty)

    def _emit_enum_value_cleanup(self, c_expr: str, enum_type: EnumType) -> None:
        """Emit C cleanup code for an enum by-value variable."""
        self._emit_enum_cleanup_switch(
            enum_type,
            self.values.emit_enum_tag_access(c_expr),
            lambda variant_name, field_name: self.values.emit_enum_payload_field_access(c_expr, variant_name, field_name),
            missing_info_is_ice=False,
        )

    def _emit_enum_cleanup_switch(
        self,
        enum_type: EnumType,
        c_tag_expr: str,
        field_expr_for_variant_field: Callable[[str, str], str],
        *,
        missing_info_is_ice: bool,
    ) -> None:
        """Emit a cleanup switch over the active variant of an enum value.

        Args:
            enum_type: Enum type whose payload cleanup is being emitted.
            c_tag_expr: C expression yielding the enum tag to switch on.
            field_expr_for_variant_field: Callback that maps variant and field
                names to the corresponding C lvalue expression.
            missing_info_is_ice: Whether missing enum metadata should raise an
                internal compiler error.

        See Also:
            `_emit_enum_value_cleanup`: Uses this helper for by-value enum cleanup.
            `_iter_variant_cleanup_fields`: Supplies the field names paired with types.
        """
        enum_info = self.state._get_enum_info(enum_type, strict=missing_info_is_ice)
        if enum_info is None:
            return

        c_enum_name = self.names.mangle_enum_name(enum_type.module, enum_type.name)

        if not self._enum_has_arc_data(enum_info):
            return

        self.state.out.emit(f"switch ({c_tag_expr}) {{")

        for variant_name, variant_info in enum_info.variants.items():
            if not any(self.state.analysis.has_arc_data(ft) for ft in variant_info.field_types):
                continue

            tag_value = f"{c_enum_name}_{variant_name}"
            self.state.out.emit(f"case {tag_value}: {{")
            self.state.out.indent()

            for field_name, field_type in self._iter_variant_cleanup_fields(
                enum_type,
                variant_name,
                variant_info.field_types,
            ):
                field_expr = field_expr_for_variant_field(variant_name, field_name)
                self._emit_field_cleanup(field_expr, field_type)

            self.state.out.emit("break;")
            self.state.out.dedent()
            self.state.out.emit("}")

        self.state.out.emit("default: break;")
        self.state.out.emit("}")

    def _iter_variant_cleanup_fields(
        self,
        enum_type: EnumType,
        variant_name: str,
        variant_field_types: list[Type],
    ) -> list[tuple[str, Type]]:
        """Pair variant field names with their resolved field types.

        Args:
            enum_type: Enum type owning the variant.
            variant_name: Variant whose fields are being cleaned up.
            variant_field_types: Resolved payload field types for the variant.

        Returns:
            A list of ``(field_name, field_type)`` pairs, or an empty list when
            the AST declaration cannot be matched to the resolved payload types.

        See Also:
            `find_variant_decl`: Retrieves the source declaration used for field names.
            `_emit_enum_cleanup_switch`: Consumes these pairs to emit cleanup code.
        """
        variant_decl = self.state.find_variant_decl(
            enum_type.module,
            enum_type.name,
            variant_name,
        )
        if variant_decl is None:
            return []
        if len(variant_decl.fields) != len(variant_field_types):
            return []
        return [
            (field_decl.name, field_type)
            for field_decl, field_type in zip(variant_decl.fields, variant_field_types)
        ]

    def _enum_has_arc_data(self, enum_info: EnumInfo) -> bool:
        """Report whether any enum payload field requires ARC-aware cleanup.

        Args:
            enum_info: Resolved enum metadata to inspect.

        Returns:
            ``True`` if any variant payload contains ARC-managed data.

        See Also:
            `_emit_enum_cleanup_switch`: Skips switch emission when this is false.
        """
        return any(
            any(self.state.analysis.has_arc_data(ft) for ft in variant_info.field_types)
            for variant_info in enum_info.variants.values()
        )

    def emit_struct_cleanup(self, c_ptr_expr: str, struct_type: StructType) -> None:
        """Emit cleanup code for all owned fields in a struct.

        Args:
            c_ptr_expr: C expression evaluating to a pointer to the struct.
            struct_type: The L0 struct type.
        """
        info = self.state._get_struct_info(struct_type, strict=True)

        self.state.out.emit(f"if ({c_ptr_expr} != NULL) {{")
        self.state.out.indent()

        for field_ in info.fields:
            field_expr = f"{c_ptr_expr}->{field_.name}"
            self._emit_field_cleanup(field_expr, field_.type)

        self.state.out.dedent()
        self.state.out.emit("}")

    def emit_enum_cleanup(self, c_ptr_expr: str, enum_type: EnumType) -> None:
        """Emit cleanup code for owned fields in an enum's active variant.

        Args:
            c_ptr_expr: C expression evaluating to a pointer to the enum.
            enum_type: The L0 enum type.
        """
        enum_info = self.state._get_enum_info(enum_type, strict=True)
        if not self._enum_has_arc_data(enum_info):
            return

        self.state.out.emit(f"if ({c_ptr_expr} != NULL) {{")
        self.state.out.indent()
        self._emit_enum_cleanup_switch(
            enum_type,
            f"{c_ptr_expr}->tag",
            lambda variant_name, field_name: f"{c_ptr_expr}->data.{variant_name}.{field_name}",
            missing_info_is_ice=True,
        )

        self.state.out.dedent()
        self.state.out.emit("}")

    def _emit_field_cleanup(self, field_expr: str, field_type: Type) -> None:
        """Emit recursive cleanup for a field."""
        self._emit_cleanup_by_type(field_expr, field_type)

    def emit_drop_finish_call(self, c_ptr_expr: str) -> None:
        """Emit the runtime call that completes a generated drop."""
        self.state.out.emit(f"_rt_drop_finish_impl((void*)({c_ptr_expr}), __FILE__, __LINE__);")

    def emit_string_retain(self, c_expr: str) -> None:
        """Emit an ARC string retain runtime call.

        Args:
            c_expr: C expression evaluating to an l0_string.
        """
        self.state.out.emit(f"rt_string_retain({c_expr});")

    def emit_string_release(self, c_expr: str) -> None:
        """Emit an ARC string release runtime call.

        Args:
            c_expr: C expression evaluating to an l0_string.
        """
        self.state.out.emit(f"rt_string_release({c_expr});")

    def emit_alloc_obj(self, c_ptr_type: str, c_base_type: str, c_temp_name: str) -> None:
        """Emit a heap allocation runtime call.

        Args:
            c_ptr_type: C pointer type string.
            c_base_type: C base object type string.
            c_temp_name: Name of temporary to hold the pointer.
        """
        self.state.out.emit(f"{c_ptr_type} {c_temp_name} = ({c_ptr_type})_rt_alloc_obj((l0_int)sizeof({c_base_type}));")
