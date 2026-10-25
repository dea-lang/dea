# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Normalize lexical C parameter declarators without losing nested types."""

from __future__ import annotations

import re


IDENT = re.compile(r"^[A-Za-z_]\w*$")
TYPE_WORDS = set("void char short int long float double signed unsigned const volatile restrict _Bool struct union enum".split())


def parameter_list(tokens: list[str]) -> list[str]:
    """Normalize a parameter list, including names in callback signatures.

    Args:
        tokens: Tokens inside one function parameter-list delimiter pair.

    Returns:
        Parameter type tokens with named declarators removed recursively.
    """
    result = []
    part = []
    depth = 0
    for value in tokens + [","]:
        if value == "," and depth == 0:
            result.extend([*parameter_type(part), ","])
            part = []
        else:
            part.append(value)
            depth += (value in {"(", "["}) - (value in {")", "]"})
    return result


def parameter_type(tokens: list[str]) -> list[str]:
    """Remove a parameter's declarator name while retaining its nested types.

    Args:
        tokens: Tokens declaring one parameter, possibly a callback.

    Returns:
        The parameter's lexical type without parameter names.
    """
    result = list(tokens)
    # Callback declarators contain a name in (*name), then their own list.
    for index in range(len(result) - 2):
        if result[index:index + 2] != ["(", "*"]:
            continue
        cursor = index + 2
        while cursor < len(result) and result[cursor] in {"const", "volatile", "restrict"}:
            cursor += 1
        if cursor < len(result) and IDENT.fullmatch(result[cursor]) and result[cursor] not in TYPE_WORDS:
            del result[cursor]
        closing = next((i for i in range(index + 2, len(result)) if result[i] == ")"), None)
        if closing is not None and closing + 1 < len(result) and result[closing + 1] == "(":
            depth = 1
            end = closing + 2
            while end < len(result) and depth:
                depth += (result[end] == "(") - (result[end] == ")")
                end += 1
            if depth == 0:
                result[closing + 2:end - 1] = parameter_list(result[closing + 2:end - 1])[:-1]
        return result
    array = result.index("[") if "[" in result else len(result)
    names = [index for index, value in enumerate(result[:array]) if IDENT.fullmatch(value)]
    if names:
        last = names[-1]
        qualifiers = {"const", "volatile", "restrict"}
        preceding_type = [result[index] for index in names[:-1] if result[index] not in qualifiers]
        if (result[last] not in TYPE_WORDS and preceding_type
                and (last + 1 == array or all(value in qualifiers for value in result[last + 1:array]))
                and not (last == 1 and result[0] in {"struct", "union", "enum"})):
            del result[last]
    return result
