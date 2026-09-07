# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from typing import List, Tuple
from l0_string_escape import decode_l0_string_token, encode_c_string_bytes
from l0_types import BuiltinType, StructType, EnumType, format_type
from l0_c_names import CNames
from l0_c_state import CEmitterState
from l0_c_types import CTypes


@dataclass
class CValues:
    """C value, pointer-access, lvalue, and constructor syntax."""

    names: CNames
    state: CEmitterState
    types: CTypes

    def emit_ord(self, c_enum_expr: str) -> str:
        """Emit C code for ord(enum_value) intrinsic.

        Args:
            c_enum_expr: C expression evaluating to an enum value.

        Returns:
            A C expression that extracts the tag field and casts to l0_int.
        """
        return f"((l0_int)(({c_enum_expr}).tag))"

    def emit_widen_int(self, c_expr: str, src_type: BuiltinType, dst_type: BuiltinType) -> str:
        """Emit C code for implicit integer widening.

        Args:
            c_expr: C expression evaluating to the source value.
            src_type: The smaller source type.
            dst_type: The larger destination type.

        Returns:
            C code string for the widening cast.

        Raises:
            InternalCompilerError: If the widening path is unsupported.
        """
        if src_type.name == dst_type.name:
            return c_expr
        if src_type.name == "byte" and dst_type.name == "int":
            return self.emit_cast(self.types.emit_type(dst_type), c_expr)
        self.state.ice(f"[ICE-1293] unsupported widening cast {format_type(src_type)} -> {format_type(dst_type)}", None)

    def emit_int_literal(self, value: int) -> str:
        """Emit C code for an integer literal.

        Args:
            value: The integer value.

        Returns:
            C literal string (handles INT32_MIN edge case).
        """
        # Special-case the min 32-bit int to avoid negative literal issues
        if value == -2147483648:
            return "INT32_MIN"
        return str(value)

    def emit_byte_literal(self, value: str) -> str:
        """Emit C code for a byte literal.

        Args:
            value: The byte literal character.

        Returns:
            C casted character literal.
        """
        return f"((l0_byte)'{value}')"

    def emit_string_literal(self, value: str) -> str:
        """Emit C code for an ARC string literal.

        Args:
            value: The L0 string token payload.

        Returns:
            C L0_STRING_CONST expression.
        """
        c_bytes, c_len = self._string_token_to_c_bytes_and_len(value)
        return f"((l0_string)L0_STRING_CONST(\"{c_bytes}\", {c_len}))"

    def emit_const_string_literal(self, value: str) -> str:
        """Emit C code for a static string literal initializer.

        Args:
            value: The L0 string token payload.

        Returns:
            C L0_STRING_CONST macro expression.
        """
        c_bytes, c_len = self._string_token_to_c_bytes_and_len(value)
        return f"L0_STRING_CONST(\"{c_bytes}\", {c_len})"

    def _string_token_to_c_bytes_and_len(self, value: str) -> tuple[str, int]:
        """Decode an L0 string token payload and encode as C string-literal bytes."""
        decoded = decode_l0_string_token(value)
        return encode_c_string_bytes(decoded), len(decoded)

    def emit_bool_literal(self, value: bool) -> str:
        """Emit C code for a boolean literal expression.

        Args:
            value: The boolean value.

        Returns:
            "1" for true, "0" for false.
        """
        return "1" if value else "0"

    def emit_const_bool_literal(self, value: bool) -> str:
        """Emit C code for a boolean literal in a static initializer.

        Args:
            value: The boolean value.

        Returns:
            "true" or "false".
        """
        return "true" if value else "false"

    def emit_var_ref(self, c_name: str) -> str:
        """Emit C code for a variable reference identifier.

        Args:
            c_name: Mangled C identifier.

        Returns:
            The identifier string.
        """
        return c_name

    def emit_unary_op(self, op: str, c_operand: str) -> str:
        """Emit C code for a unary operation.

        Args:
            op: C unary operator string.
            c_operand: C expression for the operand.

        Returns:
            C unary expression string.
        """
        return f"({op}{c_operand})"

    def emit_negated_condition(self, c_cond: str) -> str:
        """Emit a negated condition expression for control-flow lowering."""
        return self.emit_unary_op("!", self.emit_paren_expr(c_cond))

    def emit_binary_op(self, op: str, c_left: str, c_right: str) -> str:
        """Emit C code for a simple binary operation.

        Args:
            op: C binary operator string.
            c_left: C expression for left operand.
            c_right: C expression for right operand.

        Returns:
            C binary expression string.
        """
        return f"({c_left} {op} {c_right})"

    def emit_condition_binary_op(self, op: str, c_left: str, c_right: str) -> str:
        """Emit a top-level binary condition for direct statement headers."""
        return f"{c_left} {op} {c_right}"

    def emit_checked_int_div(self, c_left: str, c_right: str) -> str:
        """Emit C code for checked integer division runtime call."""
        return f"(_rt_idiv({c_left}, {c_right}))"

    def emit_checked_int_mod(self, c_left: str, c_right: str) -> str:
        """Emit C code for checked integer modulo runtime call."""
        return f"(_rt_imod({c_left}, {c_right}))"

    def emit_checked_int_mul(self, c_left: str, c_right: str) -> str:
        """Emit C code for checked integer multiplication runtime call."""
        return f"(_rt_imul({c_left}, {c_right}))"

    def emit_checked_int_add(self, c_left: str, c_right: str) -> str:
        """Emit C code for checked integer addition runtime call."""
        return f"(_rt_iadd({c_left}, {c_right}))"

    def emit_checked_int_sub(self, c_left: str, c_right: str) -> str:
        """Emit C code for checked integer subtraction runtime call."""
        return f"(_rt_isub({c_left}, {c_right}))"

    def emit_function_call(self, c_func_name: str, c_args: str) -> str:
        """Emit C code for a function call.

        Args:
            c_func_name: C identifier or expression for the function.
            c_args: Comma-separated C expression string for arguments.

        Returns:
            C function call expression string.
        """
        return f"{c_func_name}({c_args})"

    def emit_field_access(self, c_obj: str, field_name: str, is_pointer: bool) -> str:
        """Emit C code for field access using '.' or '->'.

        Args:
            c_obj: C expression for the object.
            field_name: The field identifier.
            is_pointer: True if the object is a pointer.

        Returns:
            C field access expression string.
        """
        if is_pointer:
            return f"({c_obj})->{field_name}"
        else:
            return f"({c_obj}).{field_name}"

    def emit_paren_expr(self, c_inner: str) -> str:
        """Emit C code for a parenthesized expression.

        Args:
            c_inner: The inner C expression string.

        Returns:
            Parenthesized expression string.
        """
        return f"({c_inner})"

    def emit_cast(self, c_type: str, c_inner: str) -> str:
        """Emit C code for a type cast.

        Args:
            c_type: Target C type string.
            c_inner: Expression to cast.

        Returns:
            C cast expression string.
        """
        return f"(({c_type})({c_inner}))"

    def emit_checked_ptr_access(
        self,
        c_ptr_expr: str,
        c_ptr_type: str,
        c_required_size: str,
        c_required_align: str,
        access_mode: str = "_RT_ACCESS_READ",
    ) -> str:
        """Emit a runtime-checked pointer access expression.

        Declares one static per-call-site cache slot so the runtime validates
        repeated accesses from the same site with a single range check.
        """
        site = self.names.fresh_tmp("site")
        self.state.out.emit(f"static _rt_ptr_site {site};")
        self.state.restore_active_line_directive()
        return (
            f"(({c_ptr_type})_rt_check_ptr_site(&{site}, (void*)({c_ptr_expr}), "
            f"(l0_int)({c_required_size}), (l0_int)({c_required_align}), "
            f"{access_mode}, __FILE__, __LINE__))"
        )

    def emit_checked_ptr_index_access(
        self,
        c_base_expr: str,
        c_index_expr: str,
        c_ptr_type: str,
        c_element_size: str,
        c_required_align: str,
        access_mode: str = "_RT_ACCESS_READ",
    ) -> str:
        """Emit a runtime-checked indexed pointer access expression."""
        site = self.names.fresh_tmp("site")
        self.state.out.emit(f"static _rt_ptr_site {site};")
        self.state.restore_active_line_directive()
        return (
            f"(({c_ptr_type})_rt_check_index_ptr_site(&{site}, (void*)({c_base_expr}), "
            f"(l0_int)({c_index_expr}), (l0_int)({c_element_size}), "
            f"(l0_int)({c_required_align}), {access_mode}, __FILE__, __LINE__))"
        )

    def emit_checked_ptr_access_for_base(
        self,
        c_ptr_expr: str,
        c_base_type: str,
        access_mode: str = "_RT_ACCESS_READ",
    ) -> str:
        """Emit a runtime-checked pointer to a complete object of ``c_base_type``."""
        return self.emit_checked_ptr_access(
            c_ptr_expr,
            f"{c_base_type}*",
            f"sizeof({c_base_type})",
            f"_RT_ALIGNOF({c_base_type})",
            access_mode,
        )

    def emit_drop_begin_expr(
        self,
        c_ptr_expr: str,
        c_ptr_type: str,
        c_required_size: str,
        c_required_align: str,
    ) -> str:
        """Emit the expression that validates and begins a generated drop."""
        return (
            f"(({c_ptr_type})_rt_drop_begin_impl((void*)({c_ptr_expr}), "
            f"(l0_int)({c_required_size}), (l0_int)({c_required_align}), __FILE__, __LINE__))"
        )

    def emit_checked_narrow_cast(self, c_dst_type: str, c_inner: str) -> str:
        """Emit C code for a checked narrowing cast runtime call."""
        return f"(_rt_narrow_{c_dst_type}({c_inner}))"

    def emit_unwrap_ptr(self, c_dst_type: str, c_inner: str, type_str: str) -> str:
        """Emit C code for unwrapping a pointer-shaped optional runtime check."""
        return f"(({c_dst_type}) _unwrap_ptr({c_inner}, \"{type_str}\"))"

    def emit_unwrap_opt(self, c_src_type: str, c_inner: str, type_str: str) -> str:
        """Emit C code for unwrapping a value-optional runtime check."""
        return f"((({c_src_type}*) _unwrap_opt(&({c_inner}), \"{type_str}\"))->value)"

    def emit_null_check_eq(self, c_expr: str) -> str:
        """Emit C code for null equality check (opt == null)."""
        return f"(!({self.emit_optional_has_value(c_expr)}))"

    def emit_null_check_ne(self, c_expr: str) -> str:
        """Emit C code for null inequality check (opt != null)."""
        return self.emit_optional_has_value(c_expr)

    def emit_pointer_null_check(self, c_expr: str, op: str) -> str:
        """Emit C code for pointer null comparison.

        Args:
            c_expr: C expression for the pointer.
            op: Comparison operator (e.g., "==", "!=").

        Returns:
            C comparison expression string.
        """
        return f"({c_expr} {op} NULL)"

    def emit_condition_pointer_null_check(self, c_expr: str, op: str) -> str:
        """Emit a top-level pointer null comparison for direct statement headers."""
        return f"{c_expr} {op} NULL"

    def emit_optional_has_value(self, c_expr: str) -> str:
        """Emit C code for reading an optional wrapper's has-value flag."""
        return f"({c_expr}).has_value"

    def emit_optional_value(self, c_expr: str) -> str:
        """Emit C code for reading an optional wrapper's payload value."""
        return f"({c_expr}).value"

    def emit_enum_tag_access(self, c_expr: str) -> str:
        """Emit C code for reading an enum tag."""
        return f"({c_expr}).tag"

    def emit_enum_payload_field_access(self, c_expr: str, variant: str, field: str) -> str:
        """Emit C code for reading a field from an enum payload."""
        return f"({c_expr}).data.{variant}.{field}"

    def emit_string_equals_call(self, lhs: str, rhs: str) -> str:
        """Emit the runtime string-equality helper call."""
        return f"rt_string_equals({lhs}, {rhs})"

    def emit_string_concat_call(self, lhs: str, rhs: str) -> str:
        """Emit the runtime string-concatenation helper call."""
        return f"rt_string_concat({lhs}, {rhs})"

    def emit_string_compare_call(self, op: str, lhs: str, rhs: str) -> str:
        """Emit the runtime string-compare helper call wrapped in a relational check."""
        return f"(rt_string_compare({lhs}, {rhs}) {op} 0)"

    def emit_condition_string_compare_call(self, op: str, lhs: str, rhs: str) -> str:
        """Emit a top-level string relational check for direct statement headers."""
        return f"rt_string_compare({lhs}, {rhs}) {op} 0"

    def emit_discard_expr(self, c_expr: str) -> str:
        """Emit a statement-context discard wrapper for an expression."""
        return f"(void)({c_expr})"

    def emit_deref_lvalue(self, ptr_expr: str) -> str:
        """Emit C code for a dereference lvalue: (*ptr)."""
        return f"(*{ptr_expr})"

    def emit_field_lvalue(self, obj: str, field: str, is_pointer: bool) -> str:
        """Emit C code for a field access lvalue."""
        return f"{obj}->{field}" if is_pointer else f"{obj}.{field}"

    def emit_index_lvalue(self, base: str, index: str) -> str:
        """Emit C code for an index lvalue: base[idx]."""
        return f"{base}[{index}]"

    def emit_struct_constructor(self, c_struct_name: str, field_inits: List[Tuple[str, str]]) -> str:
        """Emit C code for a struct compound literal constructor.

        Args:
            c_struct_name: Mangled C struct name.
            field_inits: List of (field_name, c_value) tuples.

        Returns:
            C compound literal: (struct name){ .f1 = v1, .f2 = v2 }.
        """
        if not field_inits:
            return f"(struct {c_struct_name}){{ 0 }}"

        inits_str = ", ".join(f".{name} = {value}" for name, value in field_inits)
        return f"(struct {c_struct_name}){{ {inits_str} }}"

    def emit_struct_static_initializer(self, field_inits: List[Tuple[str, str]]) -> str:
        """Emit a brace-only struct initializer for static storage duration."""

        if not field_inits:
            return "{ 0 }"

        inits_str = ", ".join(f".{name} = {value}" for name, value in field_inits)
        return f"{{ {inits_str} }}"

    def emit_struct_constructor_for_type(self, struct_type: StructType, field_inits: List[Tuple[str, str]]) -> str:
        """Emit a C struct constructor for an L0 struct type."""
        c_struct_name = self.names.mangle_struct_name(struct_type.module, struct_type.name)
        return self.emit_struct_constructor(c_struct_name, field_inits)

    def emit_struct_static_initializer_for_type(
            self,
            struct_type: StructType,
            field_inits: List[Tuple[str, str]],
    ) -> str:
        """Emit a static-storage struct initializer for an L0 struct type."""

        del struct_type
        return self.emit_struct_static_initializer(field_inits)

    def emit_variant_constructor(
            self,
            c_enum_name: str,
            variant_name: str,
            tag_value: str,
            payload_inits: List[Tuple[str, str]]
    ) -> str:
        """Emit C code for an enum variant tagged union literal.

        Args:
            c_enum_name: Mangled C enum name.
            variant_name: Name of the variant.
            tag_value: C tag value.
            payload_inits: List of (field_name, c_value) tuples for payload.

        Returns:
            C tagged union literal string.
        """
        if not payload_inits:
            return f"(struct {c_enum_name}){{ .tag = {tag_value} }}"

        payload_str = ", ".join(f".{name} = {value}" for name, value in payload_inits)
        return f"(struct {c_enum_name}){{ .tag = {tag_value}, .data = {{ .{variant_name} = {{ {payload_str} }} }} }}"

    def emit_variant_static_initializer(
            self,
            variant_name: str,
            tag_value: str,
            payload_inits: List[Tuple[str, str]],
    ) -> str:
        """Emit a brace-only enum tagged-union initializer for static storage duration."""

        if not payload_inits:
            return f"{{ .tag = {tag_value} }}"

        payload_str = ", ".join(f".{name} = {value}" for name, value in payload_inits)
        return f"{{ .tag = {tag_value}, .data = {{ .{variant_name} = {{ {payload_str} }} }} }}"

    def emit_variant_constructor_for_type(
            self,
            enum_type: EnumType,
            variant_name: str,
            payload_inits: List[Tuple[str, str]]
    ) -> str:
        """Emit a tagged union constructor for a given L0 enum type."""
        c_enum_name = self.names.mangle_enum_name(enum_type.module, enum_type.name)
        tag_value = self.names.emit_enum_tag(enum_type, variant_name)
        return self.emit_variant_constructor(c_enum_name, variant_name, tag_value, payload_inits)

    def emit_variant_static_initializer_for_type(
            self,
            enum_type: EnumType,
            variant_name: str,
            payload_inits: List[Tuple[str, str]],
    ) -> str:
        """Emit a static-storage tagged union initializer for a given L0 enum type."""

        tag_value = self.names.emit_enum_tag(enum_type, variant_name)
        return self.emit_variant_static_initializer(variant_name, tag_value, payload_inits)

    def emit_pattern_binding_init(self, scrutinee: str, variant: str, field: str) -> str:
        """Emit C code for accessing a variant field during pattern matching.

        Args:
            scrutinee: Name of the scrutinee variable.
            variant: Name of the variant being matched.
            field: Name of the payload field being extracted.

        Returns:
            C field access expression string.
        """
        return self.emit_enum_payload_field_access(scrutinee, variant, field)
