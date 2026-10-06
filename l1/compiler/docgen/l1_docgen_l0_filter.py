# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Helpers for rewriting L0 and L1 sources for Doxygen consumption."""

from __future__ import annotations

import re

_STRUCT_START_RE = re.compile(r"^(?P<indent>\s*)struct\s+[A-Za-z_][A-Za-z0-9_]*\s*\{\s*(?://.*)?$")
_ENUM_START_RE = re.compile(r"^(?P<indent>\s*)enum\s+[A-Za-z_][A-Za-z0-9_]*\s*\{\s*(?://.*)?$")
_FUNC_START_RE = re.compile(r"^(?P<indent>\s*)(?P<prefix>(?:unsafe\s+)?(?:extern\s+)?)func\s+[A-Za-z_][A-Za-z0-9_]*\s*\(")
_FIELD_RE = re.compile(
    r"^(?P<indent>\s*)(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<type>[^;]+?)\s*;\s*(?P<comment>//.*|/\*.*\*/)?$"
)
_ENUM_VALUE_RE = re.compile(
    r"^(?P<indent>\s*)(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<assign>\s*=\s*[^;]+)?\s*;\s*(?P<comment>//.*|/\*.*\*/)?$"
)


def _normalize_field_type(type_text: str) -> tuple[str, bool]:
    normalized = " ".join(type_text.split())
    is_nullable = normalized.endswith("?")
    if is_nullable:
        normalized = normalized[:-1].rstrip()
    return normalized, is_nullable


def _format_decl_type(type_text: str) -> str:
    normalized, is_nullable = _normalize_field_type(type_text)
    # Doxygen needs a C-like type; renderers recover the exact source signature.
    if "func(" in normalized or normalized.startswith("func ("):
        return "void*"
    return re.sub(r"\[[^]]*\]", "*", normalized).replace("?", "")


def _split_params(text: str) -> list[str]:
    """Split parameters only at top-level commas."""
    result = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            result.append(text[start:index])
            start = index + 1
    result.append(text[start:])
    return result


def _rewrite_function_signature(signature_lines: list[str]) -> str | None:
    normalized = " ".join(line.strip() for line in signature_lines)
    start = re.match(r"^(?P<prefix>(?:unsafe\s+)?(?:extern\s+)?)func\s+(?P<name>\w+)\s*\(", normalized)
    if start is None:
        return None
    depth = 1
    end = start.end()
    while end < len(normalized) and depth:
        if normalized[end] == "(":
            depth += 1
        elif normalized[end] == ")":
            depth -= 1
        end += 1
    if depth:
        raise ValueError(f"unbalanced documentation signature: {normalized}")
    tail = re.match(r"\s*(?:->\s*(?P<return>.*?))?\s*(?P<end>[{;])(?P<rest>.*)$", normalized[end:])
    if tail is None:
        raise ValueError(f"unsupported documentation signature: {normalized}")
    terminator = tail["end"]
    params_text = normalized[start.end():end - 1].strip()
    rendered_params: list[str] = []
    if params_text:
        for param in _split_params(params_text):
            name_and_type = param.strip()
            if not name_and_type:
                continue
            if ":" not in name_and_type:
                return None
            name, type_text = name_and_type.split(":", 1)
            rendered_params.append(f"{_format_decl_type(type_text)} {name.strip()}")

    return_type = _format_decl_type(tail.group("return") or "void")
    prefix = (start.group("prefix") or "").replace("unsafe ", "")
    comment = tail.group("rest")
    terminator_text = " {" if terminator == "{" else ";"
    return (
        f"{prefix}{return_type} {start.group('name')}"
        f"({', '.join(rendered_params)}){terminator_text}{comment}\n"
    )


def transform_l0_for_doxygen(source: str) -> str:
    """Rewrite L0/L1 declarations while retaining source line numbers.

    Args:
        source: Original Dea source or textual module interface.

    Returns:
        C-like declarations for Doxygen; renderers recover original signatures.

    Raises:
        ValueError: A function signature cannot be represented.
    """
    lines = source.splitlines(keepends=True)
    output: list[str] = []
    struct_depth = 0
    enum_depth = 0
    func_signature_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        alias = re.match(r"^\s*type\s+(\w+)\s*=\s*(.*);\s*$", line)
        if alias:
            output.append(f"typedef {_format_decl_type(alias[2])} {alias[1]};\n")
            continue
        if re.match(r"^\s*(?:module|import|fingerprint|entry)\b", line):
            output.append("\n")
            continue
        inline_struct = re.match(r"^(\s*struct\s+\w+\s*\{)(.*)(}\s*)$", line.strip())
        if inline_struct:
            fields = []
            for field in inline_struct[2].split(";"):
                if not field.strip():
                    continue
                name, type_text = field.split(":", 1)
                fields.append(f"{_format_decl_type(type_text)} {name.strip()};")
            output.append(inline_struct[1] + " ".join(fields) + "};\n")
            continue

        if func_signature_lines:
            func_signature_lines.append(line)
            if "{" in line or ";" in line:
                rewritten = _rewrite_function_signature(func_signature_lines)
                if rewritten is None:
                    output.extend(func_signature_lines)
                else:
                    output.append(rewritten + "\n" * (len(func_signature_lines) - 1))
                func_signature_lines = []
            continue

        if struct_depth == 0 and _STRUCT_START_RE.match(line):
            struct_depth = 1
            output.append(line)
            continue
        if enum_depth == 0 and _ENUM_START_RE.match(line):
            enum_depth = 1
            output.append(line)
            continue
        if struct_depth == 0 and enum_depth == 0 and _FUNC_START_RE.match(line):
            func_signature_lines = [line]
            if "{" in line or ";" in line:
                rewritten = _rewrite_function_signature(func_signature_lines)
                if rewritten is None:
                    output.extend(func_signature_lines)
                else:
                    output.append(rewritten + "\n" * (len(func_signature_lines) - 1))
                func_signature_lines = []
            continue

        if struct_depth > 0:
            struct_depth += line.count("{")
            struct_depth -= line.count("}")

            match = _FIELD_RE.match(line)
            if match and stripped != "}":
                field_type = _format_decl_type(match.group("type"))
                is_nullable = False
                nullable_note = " /* nullable */" if is_nullable else ""
                comment = f" {match.group('comment')}" if match.group("comment") else ""
                output.append(
                    f"{match.group('indent')}{field_type} {match.group('name')};{nullable_note}{comment}\n"
                )
                continue
            if stripped == "}":
                output.append(line.replace("}", "};", 1))
                continue

        if enum_depth > 0:
            enum_depth += line.count("{")
            enum_depth -= line.count("}")

            match = _ENUM_VALUE_RE.match(line)
            if match and stripped != "}":
                assign = match.group("assign") or ""
                comment = f" {match.group('comment')}" if match.group("comment") else ""
                output.append(f"{match.group('indent')}{match.group('name')}{assign},{comment}\n")
                continue
            if stripped == "}":
                output.append(line.replace("}", "};", 1))
                continue

        output.append(line)

    if func_signature_lines:
        output.extend(func_signature_lines)

    return "".join(output)
