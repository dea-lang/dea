# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from typing import Dict, Optional, Set
from l0_types import Type, BuiltinType, StructType, EnumType, PointerType, NullableType, FuncType, format_type
from l0_c_names import CNames
from l0_c_state import CEmitterState


@dataclass
class CTypes:
    """C type representation and optional-wrapper collection/emission."""

    names: CNames
    state: CEmitterState
    _opt_wrappers: Dict[str, Type] = field(default_factory=dict)
    _opt_emitted: Set[str] = field(default_factory=set)

    def emit_sizeof_type(self, typ: Type) -> str:
        """Emit C code for sizeof a given L0 type.

        Args:
            typ: The type to measure.

        Returns:
            A C expression like "((l0_int)sizeof(l0_int))".
        """
        c_type = self.emit_type(typ)
        return f"((l0_int)sizeof({c_type}))"

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
                self.state.ice(f"[ICE-1290] unknown builtin type '{format_type(typ)}'", None)

        elif isinstance(typ, StructType):
            c_name = self.names.mangle_struct_name(typ.module, typ.name)
            return f"struct {c_name}"

        elif isinstance(typ, EnumType):
            c_name = self.names.mangle_enum_name(typ.module, typ.name)
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
            self.state.ice(f"[ICE-1291] function pointer type emission not implemented", None)

        else:
            self.state.ice(f"[ICE-9299] unknown type kind for type emission: {type(typ)}", None)

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
            return f"s_{self.names.mangle_struct_name(t.module, t.name)}"
        if isinstance(t, EnumType):
            return f"e_{self.names.mangle_enum_name(t.module, t.name)}"
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
        self.state.ice(f"[ICE-1292] invalid expected type for null literal: '{format_type(expected_type)}'", None)

    def emit_pointer_type(self, base_type: Type) -> str:
        """Emit C pointer type for a base type.

        Args:
            base_type: The L0 type to point to.

        Returns:
            C type string (e.g., "l0_int*").
        """
        return f"{self.emit_type(base_type)}*"

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
        self.state.out.emit(f"#ifndef {name.upper()}_DEFINED")
        self.state.out.emit(f"#define {name.upper()}_DEFINED")
        self.state.out.emit(f"typedef struct {{ l0_bool has_value; {c_inner} value; }} {name};")
        self.state.out.emit(f"#endif /* {name.upper()}_DEFINED */")
        self.state.out.emit()
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
        for ft in self.state.analysis.func_types.values():
            self._collect_opt_wrappers_from_type(ft)

        # Struct fields / enum payloads
        for info in self.state.analysis.struct_infos.values():
            for f in info.fields:
                self._collect_opt_wrappers_from_type(f.type)

        for einfo in self.state.analysis.enum_infos.values():
            for v in einfo.variants.values():
                for ft in v.field_types:
                    self._collect_opt_wrappers_from_type(ft)

        # Also scan inferred expr types (covers locals/temps that never appear in sigs)
        for t in self.state.analysis.expr_types.values():
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
