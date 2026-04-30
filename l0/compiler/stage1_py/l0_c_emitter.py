"""C Code Emitter.

Handles C-specific code emission. Knows how to emit C syntax, but not why or when.
All high-level orchestration logic and decisions live in the Backend.
"""

#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from typing import Dict, List, NoReturn, Optional, Set, Tuple

from l0_analysis import AnalysisResult
from l0_ast import (
    EnumDecl, EnumVariant, FuncDecl, LetDecl, StructDecl,
)
from l0_internal_error import InternalCompilerError, ICELocation
from l0_signatures import EnumInfo, StructInfo
from l0_string_escape import decode_l0_string_token, encode_c_string_bytes
from l0_types import Type, BuiltinType, StructType, EnumType, PointerType, NullableType, FuncType, format_type


@dataclass
class CCodeBuilder:
    """Helper for building C code with indentation tracking.

    Attributes:
        lines: List of emitted code lines.
        indent_level: Current indentation depth.
        indent_str: String used for a single level of indentation. Defaults to 4 spaces.
    """
    lines: List[str] = field(default_factory=list)
    indent_level: int = 0
    indent_str: str = "    "  # 4 spaces

    def indent(self) -> None:
        """Increase the indentation level."""
        self.indent_level += 1

    def dedent(self) -> None:
        """Decrease the indentation level.

        Raises:
            AssertionError: If indentation level is already zero.
        """
        assert self.indent_level > 0, "dedent below zero"
        self.indent_level -= 1

    def emit(self, line: str = "") -> None:
        """Emit a line with current indentation.

        Args:
            line: The C code line to emit. If empty, emits a blank line.
        """
        if line:
            self.lines.append(self.indent_str * self.indent_level + line)
        else:
            self.lines.append("")

    def emit_raw(self, line: str) -> None:
        """Emit a line without indentation.

        Args:
            line: The C code line to emit directly.
        """
        self.lines.append(line)

    def to_string(self) -> str:
        """Combine all lines into a single string.

        Returns:
            The complete C source code string with a trailing newline.
        """
        return "\n".join(self.lines) + "\n"  # Ensure trailing newline


@dataclass
class CEmitter:
    """C-specific code emitter.

    Responsibilities:

    - Emit C syntax (knows C keywords, syntax, conventions).
    - Name mangling for C.
    - Type emission (L0 types -> C types).
    - Statement/expression emission to C.
    - Cleanup code emission (HOW to clean, not when/why).

    Does NOT:

    - Make decisions about what to emit.
    - Perform semantic analysis.
    - Manage scopes or lifetimes (queries backend for this).

    Attributes:
        C_KEYWORDS: Set of C keywords and restricted identifiers to be mangled.
        analysis: Full front-end analysis result.
        current_module: Name of the module currently being emitted.
        out: CCodeBuilder instance for output generation.
    """

    # C keywords that need to be mangled to avoid compilation errors
    C_KEYWORDS: Set[str] = field(default_factory=lambda: {
        # C89/C99 keywords
        'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do',
        'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if',
        'inline', 'int', 'long', 'register', 'restrict', 'return', 'short',
        'signed', 'sizeof', 'static', 'struct', 'switch', 'typedef', 'union',
        'unsigned', 'void', 'volatile', 'while',
        # C23 additions
        'alignas', 'alignof', 'atomic', 'bool', 'complex', 'imaginary',
        # Other identifiers to avoid
        'NULL', 'null', 'bool', 'true', 'false', 'asm', 'offsetof', 'typeof',
    })

    # Analysis data (set by Backend after construction)
    analysis: Optional[AnalysisResult] = None
    current_module: Optional[str] = None

    def set_analysis(self, analysis: AnalysisResult) -> None:
        """Initialize emitter with analysis data.

        Args:
            analysis: The AnalysisResult containing the compilation products.
        """
        self.analysis = analysis

    # Output builder
    out: CCodeBuilder = field(default_factory=CCodeBuilder)

    # Temporary variable counter for unique naming
    _tmp_counter: int = 0

    # Optional wrapper tracking (C-specific representation of T?)
    _opt_wrappers: Dict[str, Type] = field(default_factory=dict)
    _opt_emitted: Set[str] = field(default_factory=set)

    def get_output(self) -> str:
        """Get the generated C code.

        Returns:
            The complete generated C code string.
        """
        return self.out.to_string()

    # ============================================================================
    # Type Queries
    # ============================================================================

    def find_variant_decl(
            self, module_name: str, enum_name: str, variant_name: str
    ) -> Optional[EnumVariant]:
        """Look up an enum variant's AST declaration.

        Args:
            module_name: Name of the module containing the enum.
            enum_name: Name of the enum.
            variant_name: Name of the variant to find.

        Returns:
            The EnumVariant node if found, otherwise None.
        """
        if self.analysis.cu is None:
            return None
        module = self.analysis.cu.modules.get(module_name)
        if not module:
            return None
        for decl in module.decls:
            if isinstance(decl, EnumDecl) and decl.name == enum_name:
                for variant in decl.variants:
                    if variant.name == variant_name:
                        return variant
        return None

    def ice(self, message: str, node: Optional[object] = None) -> NoReturn:
        """Raise an internal compiler error with context.

        Args:
            message: Descriptive error message.
            node: Optional AST node to provide source location information.

        Raises:
            InternalCompilerError: Always raised with provided context.
        """
        filename = None
        if self.current_module and self.analysis.cu:
            mod = self.analysis.cu.modules.get(self.current_module)
            if mod:
                filename = mod.filename
        span = getattr(node, "span", None) if node else None
        raise InternalCompilerError(message, ICELocation(filename=filename, span=span))

    # ============================================================================
    # Name Mangling (C-specific)
    # ============================================================================

    def mangle_struct_name(self, module_name: str, struct_name: str) -> str:
        """Mangle a struct name to avoid C namespace collisions.

        Args:
            module_name: Module name.
            struct_name: L0 struct name.

        Returns:
            Mangled C struct name (e.g., "l0_module_Point").
        """
        mangled_module = module_name.replace(".", "_")
        return f"l0_{mangled_module}_{struct_name}"

    def mangle_enum_name(self, module_name: str, enum_name: str) -> str:
        """Mangle an enum name.

        Args:
            module_name: Module name.
            enum_name: L0 enum name.

        Returns:
            Mangled C enum name.
        """
        mangled_module = module_name.replace(".", "_")
        return f"l0_{mangled_module}_{enum_name}"

    def mangle_function_name(self, module_name: str, func_name: str) -> str:
        """Mangle a function name.

        Args:
            module_name: Module name.
            func_name: L0 function name.

        Returns:
            Mangled C function name.
        """
        mangled_module = module_name.replace(".", "_")
        return f"l0_{mangled_module}_{func_name}"

    def mangle_let_name(self, module_name: str, let_name: str) -> str:
        """Mangle a top-level let name to C identifier.

        Args:
            module_name: Module name.
            let_name: L0 constant name.

        Returns:
            Mangled C identifier.
        """
        safe_module = module_name.replace(".", "_")
        safe_name = let_name
        if safe_name in self.C_KEYWORDS:
            safe_name = f"l0_kw_{safe_name}"
        return f"l0_{safe_module}_{safe_name}"

    def mangle_identifier(self, name: str) -> str:
        """Mangle an identifier if it conflicts with C keywords or L0 names.

        Used for local variables, parameters, and pattern variables.
        Appends '__v' suffix to avoid C keyword conflicts. Also mangles names
        starting with '_' or 'l0_'/'L0_' to avoid clashes with runtime names.

        Args:
            name: The L0 identifier to mangle.

        Returns:
            The safe C identifier.
        """
        if name in self.C_KEYWORDS or name.endswith("__v") or name.startswith("l0_") or name.startswith("L0_") or name.startswith("_"):
            return f"{name}__v"
        return name

    def fresh_tmp(self, kind: str = "tmp") -> str:
        """Generate a unique temporary variable name.

        Args:
            kind: Category of temporary (e.g., "tmp", "ptr", "try").

        Returns:
            Unique C identifier like "l0_tmp_1", "l0_ptr_2", etc.
        """
        self._tmp_counter += 1
        return f"l0_{kind}_{self._tmp_counter}"

    # ============================================================================
    # Intrinsic Emission
    # ============================================================================

    def emit_sizeof_type(self, typ: Type) -> str:
        """Emit C code for sizeof a given L0 type.

        Args:
            typ: The type to measure.

        Returns:
            A C expression like "((l0_int)sizeof(l0_int))".
        """
        c_type = self.emit_type(typ)
        return f"((l0_int)sizeof({c_type}))"

    def emit_ord(self, c_enum_expr: str) -> str:
        """Emit C code for ord(enum_value) intrinsic.

        Args:
            c_enum_expr: C expression evaluating to an enum value.

        Returns:
            A C expression that extracts the tag field and casts to l0_int.
        """
        return f"((l0_int)(({c_enum_expr}).tag))"

    # ============================================================================
    # Type Emission (L0 types -> C types)
    # ============================================================================

    def emit_type(self, typ: Type) -> str:
        """Convert an L0 Type to its C representation.

        Args:
            typ: The L0 Type to convert.

        Returns:
            A C type string (e.g., "l0_int", "struct l0_main_Point*").

        Raises:
            InternalCompilerError: If the type kind is unknown or unsupported.
        """
        if isinstance(typ, BuiltinType):
            if typ.name == "int":
                return "l0_int"
            elif typ.name == "byte":
                return "l0_byte"
            elif typ.name == "bool":
                return "l0_bool"
            elif typ.name == "string":
                return "l0_string"
            elif typ.name == "void":
                return "void"
            else:
                self.ice(f"[ICE-1290] unknown builtin type '{format_type(typ)}'", None)

        elif isinstance(typ, StructType):
            c_name = self.mangle_struct_name(typ.module, typ.name)
            return f"struct {c_name}"

        elif isinstance(typ, EnumType):
            c_name = self.mangle_enum_name(typ.module, typ.name)
            return f"struct {c_name}"

        elif isinstance(typ, PointerType):
            inner_c_type = self.emit_type(typ.inner)
            return f"{inner_c_type}*"

        elif isinstance(typ, NullableType):
            # Niche-optimize only pointer-shaped optionals: T*? is just T* (nullable pointer).
            if isinstance(typ.inner, PointerType):
                return self.emit_type(typ.inner)

            # General case: value-optional wrapper.
            return self._opt_wrapper_name_for_inner(typ.inner)

        elif isinstance(typ, FuncType):
            # Function pointer type
            self.ice(f"[ICE-1291] function pointer type emission not implemented", None)

        else:
            self.ice(f"[ICE-9299] unknown type kind for type emission: {type(typ)}", None)

    def _is_niche_nullable(self, t: NullableType) -> bool:
        """Check if a nullable type uses niche optimization (pointer-shaped)."""
        return isinstance(t.inner, PointerType)

    def is_niche_nullable(self, t: NullableType) -> bool:
        """Public check for niche-optimized (pointer-shaped) nullable types.

        Args:
            t: The NullableType to check.

        Returns:
            True if the type is represented as a nullable pointer in C.
        """
        return self._is_niche_nullable(t)

    def _opt_key_for_type(self, t: Type) -> str:
        """Generate a unique key for an optional wrapper type name."""
        if isinstance(t, BuiltinType):
            return t.name
        if isinstance(t, StructType):
            return f"s_{self.mangle_struct_name(t.module, t.name)}"
        if isinstance(t, EnumType):
            return f"e_{self.mangle_enum_name(t.module, t.name)}"
        if isinstance(t, PointerType):
            return f"p_{self._opt_key_for_type(t.inner)}"
        if isinstance(t, NullableType):
            # Nullable-as-a-value can appear as an inner type via aliases.
            return f"n_{self._opt_key_for_type(t.inner)}"
        if isinstance(t, FuncType):
            return "fn"
        return "unk"

    def _opt_wrapper_name_for_inner(self, inner: Type) -> str:
        """Generate C typedef name for optional wrapper of given inner type."""
        return f"l0_opt_{self._opt_key_for_type(inner)}"

    def emit_none_value_for_nullable(self, t: NullableType) -> str:
        """Emit C code for the L0 'null' value of a nullable type.

        Args:
            t: The NullableType.

        Returns:
            C code string representing the 'none' state.
        """
        if isinstance(t.inner, PointerType):
            return "NULL"
        wrapper_name = self._opt_wrapper_name_for_inner(t.inner)
        return f"(({wrapper_name}){{.has_value = 0}})"

    def emit_some_value_for_nullable(self, t: NullableType, c_inner_expr: str) -> str:
        """Emit C code for wrapping a value in 'some' for a nullable type.

        Args:
            t: The NullableType.
            c_inner_expr: C expression for the inner value.

        Returns:
            C code string representing the 'some' state.
        """
        if isinstance(t.inner, PointerType):
            return c_inner_expr
        wrapper_name = self._opt_wrapper_name_for_inner(t.inner)
        return f"(({wrapper_name}){{.has_value = 1, .value = {c_inner_expr}}})"

    def emit_null_literal(self, expected_type: Optional[Type], *, for_initializer: bool = False) -> str:
        """Emit a null literal appropriate for the expected type.

        Args:
            expected_type: The type expected in this context.
            for_initializer: If True, uses C initializer syntax ({0}).

        Returns:
            C code for the null value.

        Raises:
            InternalCompilerError: If expected type is not nullable or a pointer.
        """
        if isinstance(expected_type, (NullableType, PointerType)):
            if isinstance(expected_type, PointerType) or self._is_niche_nullable(expected_type):
                return "NULL"
            if for_initializer:
                return "{0}"
            return self.emit_none_value_for_nullable(expected_type)
        self.ice(f"[ICE-1292] invalid expected type for null literal: '{format_type(expected_type)}'", None)

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
            return self.emit_cast(self.emit_type(dst_type), c_expr)
        self.ice(f"[ICE-1293] unsupported widening cast {format_type(src_type)} -> {format_type(dst_type)}", None)

    def emit_pointer_type(self, base_type: Type) -> str:
        """Emit C pointer type for a base type.

        Args:
            base_type: The L0 type to point to.

        Returns:
            C type string (e.g., "l0_int*").
        """
        return f"{self.emit_type(base_type)}*"

    def emit_enum_tag(self, enum_type: EnumType, variant_name: str) -> str:
        """Emit C tag enum value for an enum variant.

        Args:
            enum_type: The L0 enum type.
            variant_name: The name of the variant.

        Returns:
            The mangled C enum tag identifier.
        """
        c_enum_name = self.mangle_enum_name(enum_type.module, enum_type.name)
        return f"{c_enum_name}_{variant_name}"

    # ============================================================================
    # Output Formatting Utilities
    # ============================================================================

    def emit_section_comment(self, text: str) -> None:
        """Emit a decorative section comment.

        Args:
            text: The comment text.
        """
        self.out.emit(f"/* {text} */")

    def emit_module_comment(self, module_name: str) -> None:
        """Emit a module metadata comment.

        Args:
            module_name: The name of the module.
        """
        self.out.emit(f"/* Module: {module_name} */")

    def emit_module_separator(self, module_name: str) -> None:
        """Emit a decorative module separator.

        Args:
            module_name: The name of the module.
        """
        self.out.emit("/* -------------------------------- */")
        self.out.emit(f"/* Module: {module_name} */")
        self.out.emit("/* -------------------------------- */")

    def emit_unreachable_comment(self) -> None:
        """Emit an unreachable code comment for debugging."""
        self.out.emit("/* unreachable code here */")

    def emit_unreachable_marker(self, reason: str = "unreachable") -> None:
        """Emit a runtime panic call for unreachable code paths.

        Args:
            reason: Description of why the path is unreachable.
        """
        # escape reason string for C
        c_reason = encode_c_string_bytes(reason.encode("utf-8"))
        self.out.emit(f'L0_UNREACHABLE("{c_reason}");')

    # ============================================================================
    # Top-Level Structure Emission
    # ============================================================================

    def emit_header(self) -> None:
        """Emit C header boilerplate, SipHash implementation, and L0 runtime."""
        self.out.emit("/* Generated by l0c, the Dea/L0 compiler. Do not edit. */")
        self.out.emit()
        self.out.emit("#include <stdint.h>")
        self.out.emit("#include <stdbool.h>")
        self.out.emit("#include <stddef.h>")
        self.out.emit()
        self.out.emit("/* Include SipHash runtime implementation in main translation unit */")
        self.out.emit("#define SIPHASH_IMPLEMENTATION")
        self.out.emit('#include "dea_siphash.h"')
        self.out.emit()
        self.out.emit("/* L0 runtime header */")
        if self.analysis.context.trace_arc:
            self.out.emit("#define L0_TRACE_ARC 1")
        if self.analysis.context.trace_memory:
            self.out.emit("#define L0_TRACE_MEMORY 1")
        self.out.emit('#include "l0_runtime.h"')
        self.out.emit()

    def emit_line_directive(self, node, current_module: str) -> None:
        """Emit #line directive for debugging generated C.

        Args:
            node: AST node with span information.
            current_module: Name of the current module.
        """
        if not self.analysis.context.emit_line_directives:
            return
        if node is None or node.span is None:
            return
        filename = None
        if current_module and self.analysis.cu:
            mod = self.analysis.cu.modules.get(current_module)
            if mod:
                filename = mod.filename or f"{current_module}.l0"
        if filename:
            escaped_filename = encode_c_string_bytes(str(filename).replace("\\", "/").encode("utf-8"))
            self.out.emit(f'#line {node.span.start_line} "{escaped_filename}"')

    def emit_forward_decls(self) -> None:
        """Emit forward declarations for all structs and enums in compilation unit."""
        self.out.emit("/* Forward declarations */")

        for module in self.analysis.cu.modules.values():
            for decl in module.decls:
                if isinstance(decl, StructDecl):
                    c_name = self.mangle_struct_name(module.name, decl.name)
                    self.out.emit(f"struct {c_name};")
                elif isinstance(decl, EnumDecl):
                    c_name = self.mangle_enum_name(module.name, decl.name)
                    self.out.emit(f"struct {c_name};")

        self.out.emit()

    def emit_struct(self, module_name: str, decl: StructDecl, struct_info: StructInfo) -> None:
        """Emit a complete C struct definition.

        Args:
            module_name: Name of the module.
            decl: StructDecl AST node.
            struct_info: Resolved type information for the struct.
        """
        c_name = self.mangle_struct_name(module_name, decl.name)
        guard = f"L0_DEFINED_{c_name}"
        self.out.emit(f"#ifndef {guard}")
        self.out.emit(f"#define {guard}")
        self.out.emit(f"struct {c_name} {{")
        self.out.indent()

        # Emit fields
        for field_info in struct_info.fields:
            c_type = self.emit_type(field_info.type)
            self.out.emit(f"{c_type} {field_info.name};")

        if not struct_info.fields:
            # Empty struct - add dummy field, as empty structs are not allowed in standard C (C99)
            self.out.emit("char __dummy__;")

        self.out.dedent()
        self.out.emit("};")
        self.out.emit("#endif")
        self.out.emit()

    def emit_enum(self, module_name: str, decl: EnumDecl, enum_info: EnumInfo) -> None:
        """Emit an L0 enum as a C tagged union.

        Args:
            module_name: Name of the module.
            decl: EnumDecl AST node.
            enum_info: Resolved type information for the enum.

        Raises:
            InternalCompilerError: If variant information is missing.
        """
        c_name = self.mangle_enum_name(module_name, decl.name)
        guard = f"L0_DEFINED_{c_name}"
        tag_enum_name = f"{c_name}_tag"

        self.out.emit(f"#ifndef {guard}")
        self.out.emit(f"#define {guard}")

        # Emit tag enum
        self.out.emit(f"enum {tag_enum_name} {{")
        self.out.indent()

        for variant in decl.variants:
            tag_value = f"{c_name}_{variant.name}"
            self.out.emit(f"{tag_value},")

        self.out.dedent()
        self.out.emit("};")
        self.out.emit()

        # Emit tagged union struct
        self.out.emit(f"struct {c_name} {{")
        self.out.indent()
        self.out.emit(f"enum {tag_enum_name} tag;")

        # Emit union of variant payloads
        self.out.emit("union {")
        self.out.indent()

        for variant in decl.variants:
            variant_info = enum_info.variants.get(variant.name)
            if variant_info is None:
                self.ice(f"[ICE-1271] missing VariantInfo for {module_name}.{decl.name}.{variant.name}", variant)

            if not variant_info.field_types:
                # Empty variant - still need a struct for uniform access
                self.out.emit(f"struct {{ char __dummy__; }} {variant.name};")
            else:
                # Variant with fields
                field_decls = []
                for field_, ftype in zip(variant.fields, variant_info.field_types):
                    c_type = self.emit_type(ftype)
                    field_decls.append(f"{c_type} {field_.name}")

                fields_str = "; ".join(field_decls) + ";"
                self.out.emit(f"struct {{ {fields_str} }} {variant.name};")

        self.out.dedent()
        self.out.emit("} data;")

        self.out.dedent()
        self.out.emit("};")
        self.out.emit("#endif")
        self.out.emit()

    def emit_let_declaration(self, module_name: str, decl: LetDecl, let_type: Type, let_initializer_callback) -> None:
        """Emit a single top-level let declaration as a static variable.

        Args:
            module_name: Module containing the let.
            decl: Let declaration AST node.
            let_type: Resolved type of the let.
            let_initializer_callback: Callback to emit initializer expression string.
        """
        c_type = self.emit_type(let_type)
        c_name = self.mangle_let_name(module_name, decl.name)
        c_init = let_initializer_callback(decl.value, let_type)
        self.out.emit(f"static {c_type} {c_name} = {c_init};")

    def emit_top_level_let_cleanup(self) -> None:
        """Emit final cleanup for ARC-managed top-level lets before process exit."""
        if self.analysis is None or self.analysis.cu is None:
            return
        for module in self.analysis.cu.modules.values():
            for decl in module.decls:
                if not isinstance(decl, LetDecl):
                    continue
                let_type = self.analysis.let_types.get((module.name, decl.name))
                if let_type is None or not self.analysis.has_arc_data(let_type):
                    continue
                self.emit_value_cleanup(self.mangle_let_name(module.name, decl.name), let_type)

    def emit_function_declaration(self, module_name: str, decl: FuncDecl, func_type: FuncType) -> None:
        """Emit a single function declaration signature.

        Args:
            module_name: Name of the module.
            decl: FuncDecl AST node.
            func_type: Resolved signature of the function.
        """
        # CRITICAL: extern functions are NOT mangled - they're the FFI boundary
        if decl.is_extern:
            # Wrap extern function names in parens to prevent macro expansion
            # (e.g. if an extern function is implemented as a macro in the C runtime)
            c_name = f"({decl.name})"
        else:
            c_name = self.mangle_function_name(module_name, decl.name)

        c_return_type = self.emit_type(func_type.result)

        # Parameter list
        if not func_type.params:
            params_str = "void"
        else:
            param_strs = []
            for param, ptype in zip(decl.params, func_type.params):
                c_ptype = self.emit_type(ptype)
                c_param_name = self.mangle_identifier(param.name)
                param_strs.append(f"{c_ptype} {c_param_name}")
            params_str = ", ".join(param_strs)

        self.out.emit(f"{c_return_type} {c_name}({params_str});")

    def emit_function_definition_header(self, module_name: str, decl: FuncDecl, func_type: FuncType) -> None:
        """Emit function definition header (signature and opening brace).

        Args:
            module_name: Name of the module.
            decl: FuncDecl AST node.
            func_type: Resolved signature of the function.
        """
        c_name = self.mangle_function_name(module_name, decl.name)
        c_return_type = self.emit_type(func_type.result)

        # Parameter list
        if not func_type.params:
            params_str = "void"
        else:
            param_strs = []
            for param, ptype in zip(decl.params, func_type.params):
                c_ptype = self.emit_type(ptype)
                c_param_name = self.mangle_identifier(param.name)
                param_strs.append(f"{c_ptype} {c_param_name}")
            params_str = ", ".join(param_strs)

        # Function header
        self.out.emit(f"{c_return_type} {c_name}({params_str})")
        self.out.emit("{")
        self.out.indent()

    def emit_function_definition_footer(self) -> None:
        """Emit function definition footer (closing brace)."""
        self.out.dedent()
        self.out.emit("}")
        self.out.emit()

    def emit_main_wrapper(self, entry_module: str, func_type: FuncType) -> None:
        """Emit C main() wrapper that calls the L0 entry function.

        Args:
            entry_module: Name of the entry module.
            func_type: Resolved signature of the L0 main function.
        """
        self.out.emit("/* C entry point wrapper */")
        self.out.emit(f"int main(int argc, char **argv)")
        self.out.emit("{")
        self.out.indent()

        # Take care of argc/argv
        self.out.emit("_rt_init_args(argc, argv);")

        # Determine return type and call
        mangled_name = self.mangle_function_name(entry_module, "main")
        c_return_type = self.emit_type(func_type.result)

        if c_return_type == "l0_int":
            self.out.emit(f"int l0_exit_code = (int) {mangled_name}();")
        elif c_return_type == "bool":
            self.out.emit(f"bool result = {mangled_name}();")
            self.out.emit("int l0_exit_code = result ? 0 : 1;")
        else:
            self.out.emit(f"{mangled_name}();")
            self.out.emit("int l0_exit_code = 0;")

        self.emit_top_level_let_cleanup()
        self.out.emit("return l0_exit_code;")
        self.out.dedent()
        self.out.emit("}")
        self.out.emit()

    # ============================================================================
    # Optional Wrapper Emission (C-specific T? representation)
    # ============================================================================

    def _collect_opt_wrappers_from_type(self, t: Type) -> None:
        """Recursively collect optional wrapper types needed."""
        if isinstance(t, NullableType):
            if not self._is_niche_nullable(t):
                name = self._opt_wrapper_name_for_inner(t.inner)
                self._opt_wrappers[name] = t.inner
                # Inner itself may be another nullable-by-value (nested aliases), so recurse.
                self._collect_opt_wrappers_from_type(t.inner)
            else:
                # Pointer? -> no wrapper, but still traverse the pointer's inner for completeness.
                self._collect_opt_wrappers_from_type(t.inner)
            return

        if isinstance(t, PointerType):
            self._collect_opt_wrappers_from_type(t.inner)
            return

        if isinstance(t, FuncType):
            for p in t.params:
                self._collect_opt_wrappers_from_type(p)
            self._collect_opt_wrappers_from_type(t.result)
            return

    def _is_early_inner(self, inner: Type) -> bool:
        """Check if an inner type wrapper can be emitted before user definitions."""
        if isinstance(inner, BuiltinType):
            return True
        # Nullable-by-value of a builtin is also early (depends on its own wrapper).
        if isinstance(inner, NullableType) and not self._is_niche_nullable(inner):
            return self._is_early_inner(inner.inner)
        return False

    def _emit_optional_wrapper(self, name: str, inner: Type) -> None:
        """Emit one collected optional wrapper typedef.

        Args:
            name: Wrapper typedef name.
            inner: Inner wrapped type.
        """
        if name in self._opt_emitted:
            return

        c_inner = self.emit_type(inner)  # may itself be another l0_opt_...

        # Emit #ifndef guard so generated wrappers do not conflict.
        self.out.emit(f"#ifndef {name.upper()}_DEFINED")
        self.out.emit(f"#define {name.upper()}_DEFINED")
        self.out.emit(f"typedef struct {{ l0_bool has_value; {c_inner} value; }} {name};")
        self.out.emit(f"#endif /* {name.upper()}_DEFINED */")
        self.out.emit()
        self._opt_emitted.add(name)

    def emit_optional_wrapper_for_defined_type(self, inner: Type) -> None:
        """Emit the collected optional wrapper for a just-defined user type.

        Args:
            inner: Just-defined struct or enum type.
        """
        name = self._opt_wrapper_name_for_inner(inner)
        stored = self._opt_wrappers.get(name)
        if stored is None:
            return
        self._emit_optional_wrapper(name, stored)

    def prepare_optional_wrappers(self) -> None:
        """Scan all compilation unit types and collect required optional wrappers."""
        self._opt_wrappers.clear()
        self._opt_emitted.clear()

        # Function signatures
        for ft in self.analysis.func_types.values():
            self._collect_opt_wrappers_from_type(ft)

        # Struct fields / enum payloads
        for info in self.analysis.struct_infos.values():
            for f in info.fields:
                self._collect_opt_wrappers_from_type(f.type)

        for einfo in self.analysis.enum_infos.values():
            for v in einfo.variants.values():
                for ft in v.field_types:
                    self._collect_opt_wrappers_from_type(ft)

        # Also scan inferred expr types (covers locals/temps that never appear in sigs)
        for t in self.analysis.expr_types.values():
            self._collect_opt_wrappers_from_type(t)

    def emit_optional_wrappers(self, *, early: bool) -> None:
        """Emit C typedef declarations for collected optional wrapper types.

        Args:
            early: If True, emit wrappers for builtins only.
                   If False, emit wrappers for user-defined structs/enums.
        """
        # Emit typedefs for all needed wrappers whose inner types are ready at this phase.
        items = sorted(self._opt_wrappers.items(), key=lambda kv: kv[0])
        for name, inner in items:
            if self._is_early_inner(inner) != early:
                continue
            self._emit_optional_wrapper(name, inner)

    # ============================================================================
    # Cleanup Emission (HOW to emit cleanup code)
    # ============================================================================

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
        if self.analysis.is_arc_type(ty):
            self.out.emit(f"rt_string_release({c_expr});")
            return

        if isinstance(ty, NullableType):
            if isinstance(ty.inner, PointerType):
                return
            if not self.analysis.has_arc_data(ty.inner):
                return
            self.out.emit(f"if ({self.emit_optional_has_value(c_expr)}) {{")
            self.out.indent()
            self._emit_cleanup_by_type(self.emit_optional_value(c_expr), ty.inner)
            self.out.dedent()
            self.out.emit("}")
            return

        if isinstance(ty, StructType):
            info = self._get_struct_info(ty, strict=False)
            if info is None:
                return

            for field_ in info.fields:
                self._emit_cleanup_by_type(self.emit_field_access(c_expr, field_.name, False), field_.type)
            return

        if isinstance(ty, EnumType):
            self._emit_enum_value_cleanup(c_expr, ty)

    def _emit_enum_value_cleanup(self, c_expr: str, enum_type: EnumType) -> None:
        """Emit C cleanup code for an enum by-value variable."""
        self._emit_enum_cleanup_switch(
            enum_type,
            self.emit_enum_tag_access(c_expr),
            lambda variant_name, field_name: self.emit_enum_payload_field_access(c_expr, variant_name, field_name),
            missing_info_is_ice=False,
        )

    def _emit_enum_cleanup_switch(
        self,
        enum_type: EnumType,
        c_tag_expr: str,
        field_expr_for_variant_field,
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
        enum_info = self._get_enum_info(enum_type, strict=missing_info_is_ice)
        if enum_info is None:
            return

        c_enum_name = self.mangle_enum_name(enum_type.module, enum_type.name)

        if not self._enum_has_arc_data(enum_info):
            return

        self.out.emit(f"switch ({c_tag_expr}) {{")

        for variant_name, variant_info in enum_info.variants.items():
            if not any(self.analysis.has_arc_data(ft) for ft in variant_info.field_types):
                continue

            tag_value = f"{c_enum_name}_{variant_name}"
            self.out.emit(f"case {tag_value}: {{")
            self.out.indent()

            for field_name, field_type in self._iter_variant_cleanup_fields(
                enum_type,
                variant_name,
                variant_info.field_types,
            ):
                field_expr = field_expr_for_variant_field(variant_name, field_name)
                self._emit_field_cleanup(field_expr, field_type)

            self.out.emit("break;")
            self.out.dedent()
            self.out.emit("}")

        self.out.emit("default: break;")
        self.out.emit("}")

    def _iter_variant_cleanup_fields(
        self,
        enum_type: EnumType,
        variant_name: str,
        variant_field_types: List[Type],
    ) -> List[Tuple[str, Type]]:
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
        variant_decl = self.find_variant_decl(
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
            any(self.analysis.has_arc_data(ft) for ft in variant_info.field_types)
            for variant_info in enum_info.variants.values()
        )

    def _get_struct_info(self, struct_type: StructType, *, strict: bool) -> Optional[StructInfo]:
        """Look up resolved metadata for a struct type.

        Args:
            struct_type: Struct type whose metadata is needed.
            strict: Whether a missing entry should raise an internal compiler error.

        Returns:
            The matching ``StructInfo`` when available, otherwise ``None``.

        See Also:
            `emit_struct_cleanup`: Requires strict struct metadata during emission.
        """
        info = self.analysis.struct_infos.get((struct_type.module, struct_type.name))
        if info is None and strict:
            self.ice(f"[ICE-1270] missing StructInfo for {struct_type.module}.{struct_type.name}", None)
        return info

    def _get_enum_info(self, enum_type: EnumType, *, strict: bool) -> Optional[EnumInfo]:
        """Look up resolved metadata for an enum type.

        Args:
            enum_type: Enum type whose metadata is needed.
            strict: Whether a missing entry should raise an internal compiler error.

        Returns:
            The matching ``EnumInfo`` when available, otherwise ``None``.

        See Also:
            `_emit_enum_cleanup_switch`: Uses enum metadata to enumerate payload fields.
        """
        info = self.analysis.enum_infos.get((enum_type.module, enum_type.name))
        if info is None and strict:
            self.ice(f"[ICE-1080] missing EnumInfo for {enum_type.module}.{enum_type.name}", None)
        return info

    def emit_struct_cleanup(self, c_ptr_expr: str, struct_type: StructType) -> None:
        """Emit cleanup code for all owned fields in a struct.

        Args:
            c_ptr_expr: C expression evaluating to a pointer to the struct.
            struct_type: The L0 struct type.
        """
        info = self._get_struct_info(struct_type, strict=True)

        self.out.emit(f"if ({c_ptr_expr} != NULL) {{")
        self.out.indent()

        for field_ in info.fields:
            field_expr = f"{c_ptr_expr}->{field_.name}"
            self._emit_field_cleanup(field_expr, field_.type)

        self.out.dedent()
        self.out.emit("}")

    def emit_enum_cleanup(self, c_ptr_expr: str, enum_type: EnumType) -> None:
        """Emit cleanup code for owned fields in an enum's active variant.

        Args:
            c_ptr_expr: C expression evaluating to a pointer to the enum.
            enum_type: The L0 enum type.
        """
        enum_info = self._get_enum_info(enum_type, strict=True)
        if not self._enum_has_arc_data(enum_info):
            return

        self.out.emit(f"if ({c_ptr_expr} != NULL) {{")
        self.out.indent()
        self._emit_enum_cleanup_switch(
            enum_type,
            f"{c_ptr_expr}->tag",
            lambda variant_name, field_name: f"{c_ptr_expr}->data.{variant_name}.{field_name}",
            missing_info_is_ice=True,
        )

        self.out.dedent()
        self.out.emit("}")

    def _emit_field_cleanup(self, field_expr: str, field_type: Type) -> None:
        """Emit recursive cleanup for a field."""
        self._emit_cleanup_by_type(field_expr, field_type)

    # ============================================================================
    # Expression Emission (C syntax for expressions)
    # ============================================================================

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

    # ============================================================================
    # Lvalue Emission (C syntax for lvalues)
    # ============================================================================

    def emit_deref_lvalue(self, ptr_expr: str) -> str:
        """Emit C code for a dereference lvalue: (*ptr)."""
        return f"(*{ptr_expr})"

    def emit_field_lvalue(self, obj: str, field: str, is_pointer: bool) -> str:
        """Emit C code for a field access lvalue."""
        return f"{obj}->{field}" if is_pointer else f"{obj}.{field}"

    def emit_index_lvalue(self, base: str, index: str) -> str:
        """Emit C code for an index lvalue: base[idx]."""
        return f"{base}[{index}]"

    # ============================================================================
    # Constructor Emission (C syntax for struct/enum constructors)
    # ============================================================================

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
        c_struct_name = self.mangle_struct_name(struct_type.module, struct_type.name)
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
        c_enum_name = self.mangle_enum_name(enum_type.module, enum_type.name)
        tag_value = self.emit_enum_tag(enum_type, variant_name)
        return self.emit_variant_constructor(c_enum_name, variant_name, tag_value, payload_inits)

    def emit_variant_static_initializer_for_type(
            self,
            enum_type: EnumType,
            variant_name: str,
            payload_inits: List[Tuple[str, str]],
    ) -> str:
        """Emit a static-storage tagged union initializer for a given L0 enum type."""

        tag_value = self.emit_enum_tag(enum_type, variant_name)
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

    # ============================================================================
    # Statement Emission (C syntax for statements)
    # ============================================================================

    def emit_expr_stmt(self, c_expr: str) -> None:
        """Emit an expression as a statement.

        Args:
            c_expr: C expression string.
        """
        self.out.emit(f"{c_expr};")

    def emit_return_stmt(self, c_value: Optional[str]) -> None:
        """Emit a C return statement.

        Args:
            c_value: Optional C expression string to return.
        """
        if c_value is not None:
            self.out.emit(f"return {c_value};")
        else:
            self.out.emit("return;")

    def emit_exit_switch(self) -> None:
        """Emit a C break statement to exit a switch block."""
        self.out.emit("break;")

    def emit_label(self, label: str) -> None:
        """Emit a C label followed by a null statement.

        Args:
            label: C label identifier.
        """
        self.out.dedent()
        self.out.emit(f"{label}:;")
        self.out.indent()

    def emit_goto(self, label: str) -> None:
        """Emit a C goto statement.

        Args:
            label: Target C label identifier.
        """
        self.out.emit(f"goto {label};")

    def emit_block_start(self) -> None:
        """Emit an opening brace and increase indentation."""
        self.out.emit("{")
        self.out.indent()

    def emit_block_end(self) -> None:
        """Emit a closing brace and decrease indentation."""
        self.out.dedent()
        self.out.emit("}")

    def emit_while_header(self, c_cond: str) -> None:
        """Emit a C while loop header.

        Args:
            c_cond: C expression for the loop condition.
        """
        self.out.emit(f"while ({c_cond})")

    def emit_if_header(self, c_cond: str) -> None:
        """Emit a C if statement header.

        Args:
            c_cond: C expression for the condition.
        """
        self.out.emit(f"if ({c_cond})")

    def emit_else(self) -> None:
        """Emit a C else keyword."""
        self.out.emit("else")

    def emit_for_loop_start(self) -> None:
        """Emit a decorative comment and opening brace for a for loop block."""
        self.out.emit("// for loop")
        self.out.emit("{")
        self.out.indent()

    def emit_for_loop_end(self) -> None:
        """Emit closing brace for a for loop block."""
        self.out.dedent()
        self.out.emit("}")

    def emit_let_decl(self, c_type: str, c_var_name: str, c_init: str) -> None:
        """Emit a C local variable declaration with initializer.

        Args:
            c_type: C type string.
            c_var_name: C identifier.
            c_init: C initializer expression string.
        """
        self.out.emit(f"{c_type} {c_var_name} = {c_init};")

    def emit_assignment(self, c_target: str, c_value: str) -> None:
        """Emit a simple C assignment statement.

        Args:
            c_target: C lvalue expression.
            c_value: C expression for the value.
        """
        self.out.emit(f"{c_target} = {c_value};")

    def emit_pointer_assignment(self, c_ptr_name: str, c_value: str) -> None:
        """Emit a C assignment through a pointer.

        Args:
            c_ptr_name: C expression evaluating to a pointer.
            c_value: C expression for the value.
        """
        self.out.emit(f"*{c_ptr_name} = {c_value};")

    def emit_temp_decl(self, c_type: str, c_temp_name: str, c_value: str) -> None:
        """Emit a C temporary variable declaration with initializer.

        Args:
            c_type: C type string.
            c_temp_name: C identifier for temporary.
            c_value: C initializer expression string.
        """
        self.out.emit(f"{c_type} {c_temp_name} = {c_value};")

    def emit_string_retain(self, c_expr: str) -> None:
        """Emit an ARC string retain runtime call.

        Args:
            c_expr: C expression evaluating to an l0_string.
        """
        self.out.emit(f"rt_string_retain({c_expr});")

    def emit_string_release(self, c_expr: str) -> None:
        """Emit an ARC string release runtime call.

        Args:
            c_expr: C expression evaluating to an l0_string.
        """
        self.out.emit(f"rt_string_release({c_expr});")

    def emit_comment(self, comment: str) -> None:
        """Emit a C block comment.

        Args:
            comment: The comment text.
        """
        self.out.emit(f"/* {comment} */")

    def emit_match_scrutinee_decl(self, c_type: str, c_expr: str) -> None:
        """Emit the scrutinee declaration for a match/case statement.

        Args:
            c_type: C type string of scrutinee.
            c_expr: C expression for scrutinee value.
        """
        self.out.emit(f"{c_type} _scrutinee = {c_expr};")

    def emit_switch_start(self, c_expr: str) -> None:
        """Emit a C switch statement header and opening brace.

        Args:
            c_expr: C expression to switch on.
        """
        self.out.emit(f"switch ({c_expr}) {{")

    def emit_match_switch_start(self, scrutinee_name: str) -> None:
        """Emit a match switch over an enum tag.

        Args:
            scrutinee_name: Identifier of the scrutinee variable.
        """
        self.emit_switch_start(self.emit_enum_tag_access(scrutinee_name))

    def emit_switch_end(self) -> None:
        """Emit a C switch statement closing brace."""
        self.out.emit("}")

    def emit_case_label(self, c_tag_value: str) -> None:
        """Emit a C case label.

        Args:
            c_tag_value: The constant C tag identifier or literal.
        """
        self.out.emit(f"case {c_tag_value}:")

    def emit_default_label(self) -> None:
        """Emit a C default case label."""
        self.out.emit("default:")

    def emit_drop_call(self, c_ptr_expr: str) -> None:
        """Emit a heap memory release runtime call.

        Args:
            c_ptr_expr: C expression evaluating to the object pointer.
        """
        self.out.emit(f"_rt_drop((void*){c_ptr_expr});")

    def emit_null_assignment(self, c_var: str) -> None:
        """Emit a NULL assignment to a variable.

        Args:
            c_var: C lvalue expression.
        """
        self.out.emit(f"{c_var} = NULL;")

    def emit_alloc_obj(self, c_ptr_type: str, c_base_type: str, c_temp_name: str) -> None:
        """Emit a heap allocation runtime call.

        Args:
            c_ptr_type: C pointer type string.
            c_base_type: C base object type string.
            c_temp_name: Name of temporary to hold the pointer.
        """
        self.out.emit(f"{c_ptr_type} {c_temp_name} = ({c_ptr_type})_rt_alloc_obj((l0_int)sizeof({c_base_type}));")

    def emit_struct_init(self, c_temp_name: str, c_base_type: str, c_init_str: str) -> None:
        """Emit an object initialization through a pointer.

        Args:
            c_temp_name: Name of the pointer variable.
            c_base_type: C base object type string.
            c_init_str: C compound initializer body.
        """
        self.out.emit(f"*{c_temp_name} = ({c_base_type}){{ {c_init_str} }};")

    def emit_struct_init_from_fields(
            self,
            c_temp_name: str,
            base_type: Type,
            field_inits: List[Tuple[str, str]]
    ) -> None:
        """Emit struct initialization using positional field values.

        Args:
            c_temp_name: Name of the pointer variable.
            base_type: L0 base object type.
            field_inits: List of (field_name, c_value) tuples.
        """
        c_base_type = self.emit_type(base_type)
        init_str = ", ".join(f".{name} = {value}" for name, value in field_inits)
        self.emit_struct_init(c_temp_name, c_base_type, init_str)

    def emit_enum_variant_init(
            self,
            c_temp_name: str,
            enum_type: EnumType,
            variant_name: str,
            payload_inits: List[Tuple[str, str]]
    ) -> None:
        """Emit enum variant initialization for a heap-allocated enum.

        Args:
            c_temp_name: Name of the pointer variable.
            enum_type: L0 enum type.
            variant_name: Name of the active variant.
            payload_inits: List of (field_name, c_value) tuples for payload.
        """
        c_base_type = self.emit_type(enum_type)
        tag_value = self.emit_enum_tag(enum_type, variant_name)
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
        self.out.emit(f"*{c_temp_name} = ({c_base_type}){{ 0 }};")

    def emit_try_check_niche(self, c_tmp: str, ret_none: str) -> None:
        """Emit a NULL check for a niche-optimized optional.

        Args:
            c_tmp: C identifier of the temporary holding the optional.
            ret_none: C expression for the 'none' return value.
        """
        self.out.emit(f"if {self.emit_pointer_null_check(c_tmp, '==')} return {ret_none};")

    def emit_try_check_value(self, c_tmp: str, ret_none: str) -> None:
        """Emit a has_value check for a value-optional.

        Args:
            c_tmp: C identifier of the temporary holding the optional.
            ret_none: C expression for the 'none' return value.
        """
        self.out.emit(f"if {self.emit_null_check_eq(c_tmp)} return {ret_none};")

    def emit_try_extract_value(self, c_tmp: str) -> str:
        """Emit C code to extract the inner value from an optional.

        Args:
            c_tmp: C identifier of the temporary holding the optional.

        Returns:
            C expression string for the extracted value.
        """
        return f"({self.emit_optional_value(c_tmp)})"
