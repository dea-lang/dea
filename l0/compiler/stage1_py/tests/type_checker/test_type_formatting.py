# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Regression coverage for semantic type display in diagnostics and dumps."""

import pytest

from l0_types import (
    BuiltinType, EnumType, FuncType, NullableType, NullType, PointerType,
    StructType, Type, format_type,
)


@pytest.mark.parametrize(
    ("typ", "expected"),
    [
        (None, "<none>"),
        (BuiltinType("int"), "int"),
        (StructType("geometry", "Point"), "geometry::Point"),
        (EnumType("status", "Result"), "status::Result"),
        (NullableType(PointerType(StructType("geometry", "Point"))), "geometry::Point*?"),
        (PointerType(NullableType(BuiltinType("int"))), "int?*"),
        (FuncType((), BuiltinType("void")), "func() -> void"),
        (FuncType((BuiltinType("int"), NullableType(BuiltinType("string"))), NullType()),
         "func(int, string?) -> null"),
        (NullType(), "null"),
    ],
)
def test_format_type_preserves_nested_type_spelling(typ: Type | None, expected: str) -> None:
    assert format_type(typ) == expected


def test_format_type_accepts_subclasses_and_preserves_unknown_type_fallback() -> None:
    class CustomBuiltin(BuiltinType):
        pass

    class UnknownType(Type):
        def __repr__(self) -> str:
            return "<custom type>"

    assert format_type(CustomBuiltin("byte")) == "byte"
    assert format_type(UnknownType()) == "<custom type>"
