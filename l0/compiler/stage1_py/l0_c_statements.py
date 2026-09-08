# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass
from l0_types import Type, EnumType
from l0_c_names import CNames
from l0_c_state import CEmitterState
from l0_c_types import CTypes
from l0_c_values import CValues


@dataclass
class CStatements:
    """C statement, control-flow, and initialization syntax."""

    names: CNames
    state: CEmitterState
    types: CTypes
    values: CValues

    def emit_expr_stmt(self, c_expr: str) -> None:
        """Emit an expression as a statement.

        Args:
            c_expr: C expression string.
        """
        self.state.out.emit(f"{c_expr};")

    def emit_return_stmt(self, c_value: str | None) -> None:
        """Emit a C return statement.

        Args:
            c_value: Optional C expression string to return.
        """
        if c_value is not None:
            self.state.out.emit(f"return {c_value};")
        else:
            self.state.out.emit("return;")

    def emit_exit_switch(self) -> None:
        """Emit a C break statement to exit a switch block."""
        self.state.out.emit("break;")

    def emit_label(self, label: str) -> None:
        """Emit a C label followed by a null statement.

        Args:
            label: C label identifier.
        """
        self.state.out.dedent()
        self.state.out.emit(f"{label}:;")
        self.state.out.indent()

    def emit_goto(self, label: str) -> None:
        """Emit a C goto statement.

        Args:
            label: Target C label identifier.
        """
        self.state.out.emit(f"goto {label};")

    def emit_block_start(self) -> None:
        """Emit an opening brace and increase indentation."""
        self.state.out.emit("{")
        self.state.out.indent()

    def emit_block_end(self) -> None:
        """Emit a closing brace and decrease indentation."""
        self.state.out.dedent()
        self.state.out.emit("}")

    def emit_while_header(self, c_cond: str) -> None:
        """Emit a C while loop header.

        Args:
            c_cond: C expression for the loop condition.
        """
        self.state.out.emit(f"while ({c_cond})")

    def emit_if_header(self, c_cond: str) -> None:
        """Emit a C if statement header.

        Args:
            c_cond: C expression for the condition.
        """
        self.state.out.emit(f"if ({c_cond})")

    def emit_else(self) -> None:
        """Emit a C else keyword."""
        self.state.out.emit("else")

    def emit_for_loop_start(self) -> None:
        """Emit a decorative comment and opening brace for a for loop block."""
        self.state.out.emit("// for loop")
        self.state.out.emit("{")
        self.state.out.indent()

    def emit_for_loop_end(self) -> None:
        """Emit closing brace for a for loop block."""
        self.state.out.dedent()
        self.state.out.emit("}")

    def emit_let_decl(self, c_type: str, c_var_name: str, c_init: str) -> None:
        """Emit a C local variable declaration with initializer.

        Args:
            c_type: C type string.
            c_var_name: C identifier.
            c_init: C initializer expression string.
        """
        self.state.out.emit(f"{c_type} {c_var_name} = {c_init};")

    def emit_assignment(self, c_target: str, c_value: str) -> None:
        """Emit a simple C assignment statement.

        Args:
            c_target: C lvalue expression.
            c_value: C expression for the value.
        """
        self.state.out.emit(f"{c_target} = {c_value};")

    def emit_pointer_assignment(self, c_ptr_name: str, c_value: str) -> None:
        """Emit a C assignment through a pointer.

        Args:
            c_ptr_name: C expression evaluating to a pointer.
            c_value: C expression for the value.
        """
        self.state.out.emit(f"*{c_ptr_name} = {c_value};")

    def emit_checked_pointer_assignment(self, c_ptr_name: str, c_base_type: str, c_value: str) -> None:
        """Emit an assignment through a runtime-checked object pointer."""
        checked = self.values.emit_checked_ptr_access_for_base(c_ptr_name, c_base_type, "_RT_ACCESS_WRITE")
        self.state.out.emit(f"*{checked} = {c_value};")

    def emit_temp_decl(self, c_type: str, c_temp_name: str, c_value: str) -> None:
        """Emit a C temporary variable declaration with initializer.

        Args:
            c_type: C type string.
            c_temp_name: C identifier for temporary.
            c_value: C initializer expression string.
        """
        self.state.out.emit(f"{c_type} {c_temp_name} = {c_value};")

    def emit_comment(self, comment: str) -> None:
        """Emit a C block comment.

        Args:
            comment: The comment text.
        """
        self.state.out.emit(f"/* {comment} */")

    def emit_match_scrutinee_decl(self, c_type: str, c_expr: str) -> None:
        """Emit the scrutinee declaration for a match/case statement.

        Args:
            c_type: C type string of scrutinee.
            c_expr: C expression for scrutinee value.
        """
        self.state.out.emit(f"{c_type} _scrutinee = {c_expr};")

    def emit_switch_start(self, c_expr: str) -> None:
        """Emit a C switch statement header and opening brace.

        Args:
            c_expr: C expression to switch on.
        """
        self.state.out.emit(f"switch ({c_expr}) {{")

    def emit_match_switch_start(self, scrutinee_name: str) -> None:
        """Emit a match switch over an enum tag.

        Args:
            scrutinee_name: Identifier of the scrutinee variable.
        """
        self.emit_switch_start(self.values.emit_enum_tag_access(scrutinee_name))

    def emit_switch_end(self) -> None:
        """Emit a C switch statement closing brace."""
        self.state.out.emit("}")

    def emit_case_label(self, c_tag_value: str) -> None:
        """Emit a C case label.

        Args:
            c_tag_value: The constant C tag identifier or literal.
        """
        self.state.out.emit(f"case {c_tag_value}:")

    def emit_default_label(self) -> None:
        """Emit a C default case label."""
        self.state.out.emit("default:")

    def emit_null_assignment(self, c_var: str) -> None:
        """Emit a NULL assignment to a variable.

        Args:
            c_var: C lvalue expression.
        """
        self.state.out.emit(f"{c_var} = NULL;")

    def emit_struct_init(self, c_temp_name: str, c_base_type: str, c_init_str: str) -> None:
        """Emit an object initialization through a pointer.

        Args:
            c_temp_name: Name of the pointer variable.
            c_base_type: C base object type string.
            c_init_str: C compound initializer body.
        """
        checked = self.values.emit_checked_ptr_access_for_base(c_temp_name, c_base_type, "_RT_ACCESS_WRITE")
        self.state.out.emit(f"*{checked} = ({c_base_type}){{ {c_init_str} }};")

    def emit_struct_init_from_fields(
            self,
            c_temp_name: str,
            base_type: Type,
            field_inits: list[tuple[str, str]]
    ) -> None:
        """Emit struct initialization using positional field values.

        Args:
            c_temp_name: Name of the pointer variable.
            base_type: L0 base object type.
            field_inits: List of (field_name, c_value) tuples.
        """
        c_base_type = self.types.emit_type(base_type)
        init_str = ", ".join(f".{name} = {value}" for name, value in field_inits)
        self.emit_struct_init(c_temp_name, c_base_type, init_str)

    def emit_enum_variant_init(
            self,
            c_temp_name: str,
            enum_type: EnumType,
            variant_name: str,
            payload_inits: list[tuple[str, str]]
    ) -> None:
        """Emit enum variant initialization for a heap-allocated enum.

        Args:
            c_temp_name: Name of the pointer variable.
            enum_type: L0 enum type.
            variant_name: Name of the active variant.
            payload_inits: List of (field_name, c_value) tuples for payload.
        """
        c_base_type = self.types.emit_type(enum_type)
        tag_value = self.names.emit_enum_tag(enum_type, variant_name)
        if not payload_inits:
            init_str = f".tag = {tag_value}"
        else:
            payload_str = ", ".join(f".{name} = {value}" for name, value in payload_inits)
            init_str = f".tag = {tag_value}, .data = {{ .{variant_name} = {{ {payload_str} }} }}"
        self.emit_struct_init(c_temp_name, c_base_type, init_str)

    def emit_zero_init(self, c_temp_name: str, c_base_type: str) -> None:
        """Emit zero-initialization through a pointer.

        Args:
            c_temp_name: Name of the pointer variable.
            c_base_type: C base object type string.
        """
        checked = self.values.emit_checked_ptr_access_for_base(c_temp_name, c_base_type, "_RT_ACCESS_WRITE")
        self.state.out.emit(f"*{checked} = ({c_base_type}){{ 0 }};")

    def emit_try_check_niche(self, c_tmp: str, ret_none: str) -> None:
        """Emit a NULL check for a niche-optimized optional.

        Args:
            c_tmp: C identifier of the temporary holding the optional.
            ret_none: C expression for the 'none' return value.
        """
        self.state.out.emit(f"if {self.values.emit_pointer_null_check(c_tmp, '==')} return {ret_none};")

    def emit_try_check_value(self, c_tmp: str, ret_none: str) -> None:
        """Emit a has_value check for a value-optional.

        Args:
            c_tmp: C identifier of the temporary holding the optional.
            ret_none: C expression for the 'none' return value.
        """
        self.state.out.emit(f"if {self.values.emit_null_check_eq(c_tmp)} return {ret_none};")

    def emit_try_extract_value(self, c_tmp: str) -> str:
        """Emit C code to extract the inner value from an optional.

        Args:
            c_tmp: C identifier of the temporary holding the optional.

        Returns:
            C expression string for the extracted value.
        """
        return f"({self.values.emit_optional_value(c_tmp)})"
