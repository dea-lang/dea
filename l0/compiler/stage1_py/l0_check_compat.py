# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass
from typing import Optional
from l0_ast import Expr, IntLiteral, NullLiteral, UnaryOp, ParenExpr, CastExpr
from l0_types import Type, BuiltinType, PointerType, NullableType, NullType


@dataclass
class TypeCompatibility:
    """Assignment, cast, and scalar type-compatibility rules."""


    def _can_assign(self, target: Type, source: Type, *, allow_promotion=False) -> bool:
        """Check if 'source' type can be assigned to 'target' type."""
        # Exact match
        if self._types_equal(target, source):
            return True

        # Null assignment
        if isinstance(source, NullType):
            if isinstance(target, NullableType):
                return True

        # Allow widening for certain built-in types (byte -> int)
        if isinstance(source, BuiltinType) and isinstance(target, BuiltinType):
            if source.name == "byte" and target.name == "int":
                return True

        # Checked narrowing for built-in types (int -> byte) in casts
        if allow_promotion and isinstance(source, BuiltinType) and isinstance(target, BuiltinType):
            # Allow int -> byte in checked contexts (casts)
            if source.name == "int" and target.name == "byte":
                return True

        # Allow widening non-nullable to nullable promotion (T -> T?)
        if isinstance(target, NullableType):
            if self._can_assign(target.inner, source):
                return True

        # Nullable to non-nullable demotion (T? -> T) only if allowed (e.g., in casts)
        if allow_promotion and not isinstance(target, NullableType) and isinstance(source, NullableType):
            if self._can_assign(target, source.inner):
                return True

        # Recursive checks for Nullable types
        if isinstance(source, NullableType) and isinstance(target, NullableType):
            # T1? -> T2? if T1 -> T2
            return self._can_assign(target.inner, source.inner)

        # Recursive checks for Pointer types
        if isinstance(source, PointerType) and isinstance(target, PointerType):
            # T1* -> T2* if T1 -> T2 or T2 is void or T1 is void
            if self._is_void(target.inner) or self._is_void(source.inner):
                return True
            return self._can_assign(target.inner, source.inner)

        return False

    def _is_nullable_or_ptr(self, t: Type) -> bool:
        """Check if type is nullable or a pointer."""
        return isinstance(t, (NullableType, PointerType))

    def _is_int_assignable(self, typ: Optional[Type]) -> bool:
        """Check if type is 'int' or 'byte'."""
        return isinstance(typ, BuiltinType) and (typ.name == "int" or typ.name == "byte")

    def _get_const_int_for_explicit_cast(self, expr: Expr) -> Optional[int]:
        """Extract a compile-time integer value from a cast operand when available."""
        if isinstance(expr, IntLiteral):
            return expr.value
        if isinstance(expr, ParenExpr):
            return self._get_const_int_for_explicit_cast(expr.inner)
        if isinstance(expr, UnaryOp) and expr.op == "-":
            inner = self._get_const_int_for_explicit_cast(expr.operand)
            if inner is not None:
                return -inner
        return None

    def _is_const_null_for_explicit_cast(self, expr: Expr) -> bool:
        """Check whether a cast operand is provably null at compile time."""
        if isinstance(expr, NullLiteral):
            return True
        if isinstance(expr, ParenExpr):
            return self._is_const_null_for_explicit_cast(expr.inner)
        if isinstance(expr, CastExpr):
            return self._is_const_null_for_explicit_cast(expr.expr)
        return False

    def _is_bool(self, typ: Optional[Type]) -> bool:
        """Check if type is 'bool'."""
        return isinstance(typ, BuiltinType) and typ.name == "bool"

    def _is_string(self, typ: NullType | Type) -> bool:
        """Check if type is 'string'."""
        return isinstance(typ, BuiltinType) and typ.name == "string"

    def _is_void(self, typ: Type) -> bool:
        """Check if type is 'void'."""
        return isinstance(typ, BuiltinType) and typ.name == "void"

    def _types_equal(self, a: Type, b: Type) -> bool:
        """Check if two types are exactly the same."""
        return a == b
