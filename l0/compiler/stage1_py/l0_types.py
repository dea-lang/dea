#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Semantic type system definitions for the L0 compiler.

This module provides classes for representing all types supported by the
L0 language, including primitives, pointers, optionals, and user-defined types.
"""

from dataclasses import dataclass
from typing import Tuple, Dict, Optional

# ========================================
# The current semantic type system for L0.
# ========================================

L0_PRIMITIVE_TYPES = ("bool", "byte", "int", "string", "void")


def is_builtin_type_name(name: str) -> bool:
    """Return whether ``name`` is in the canonical L0 primitive inventory."""
    return name in L0_PRIMITIVE_TYPES


class Type:
    """Base class for all semantic types.

    Used as a common marker; concrete types are represented by specialized
    dataclasses.
    """
    pass


@dataclass(frozen=True)
class BuiltinType(Type):
    """A built-in primitive type.

    Attributes:
        name: The name of the type (e.g., "int", "bool").
    """
    name: str


@dataclass(frozen=True)
class StructType(Type):
    """A user-defined struct type.

    Attributes:
        module: The name of the module where the struct is defined.
        name: The name of the struct.
    """
    module: str
    name: str


@dataclass(frozen=True)
class EnumType(Type):
    """A user-defined enum type.

    Attributes:
        module: The name of the module where the enum is defined.
        name: The name of the enum.
    """
    module: str
    name: str


@dataclass(frozen=True)
class PointerType(Type):
    """A pointer to another type (T*).

    Attributes:
        inner: The Type being pointed to.
    """
    inner: Type


@dataclass(frozen=True)
class NullableType(Type):
    """A nullable (optional) wrapper for another type (T?).

    Attributes:
        inner: The Type that may be null.
    """
    inner: Type


@dataclass(frozen=True)
class FuncType(Type):
    """A function signature type.

    Attributes:
        params: Tuple of parameter Types.
        result: The return Type of the function.
    """
    params: Tuple[Type, ...]
    result: Type


@dataclass(frozen=True)
class NullType(Type):
    """The type of the 'null' literal."""
    pass


# --- helpers for builtins ---

_BUILTIN_CACHE: Dict[str, BuiltinType] = {}
_NULL_TYPE = NullType()


def get_builtin_type(name: str) -> BuiltinType:
    """Get or create a canonical BuiltinType for a given name.

    Args:
        name: The primitive type name.

    Returns:
        The cached or new BuiltinType instance.

    Raises:
        ValueError: If ``name`` is not in the canonical primitive inventory.
    """
    if not is_builtin_type_name(name):
        raise ValueError(f"unknown L0 builtin type: {name}")
    if name not in _BUILTIN_CACHE:
        _BUILTIN_CACHE[name] = BuiltinType(name)
    return _BUILTIN_CACHE[name]


def get_null_type() -> NullType:
    """Get the canonical NullType instance.

    Returns:
        The singleton NullType instance.
    """
    return _NULL_TYPE

# --- type stringification for debugging ---

def format_type(t: Optional[Type]) -> str:
    """Format a type into a human-readable string.

    Args:
        t: The Type to format, or None.

    Returns:
        A string representation of the type (e.g., "int*", "std::Point?").
    """
    if t is None:
        return "<none>"
    elif isinstance(t, BuiltinType):
        return t.name
    elif isinstance(t, StructType):
        return f"{t.module}::{t.name}"
    elif isinstance(t, EnumType):
        return f"{t.module}::{t.name}"
    elif isinstance(t, PointerType):
        return f"{format_type(t.inner)}*"
    elif isinstance(t, NullableType):
        return f"{format_type(t.inner)}?"
    elif isinstance(t, FuncType):
        params_str = ", ".join(format_type(p) for p in t.params)
        return f"func({params_str}) -> {format_type(t.result)}"
    elif isinstance(t, NullType):
        return "null"
    else:
        # Fallback (should not happen)
        return repr(t)
