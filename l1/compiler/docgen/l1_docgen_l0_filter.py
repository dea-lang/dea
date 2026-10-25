# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Helpers for rewriting L0 and L1 sources for Doxygen consumption."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import re

_SOURCE_TOKEN_RE = re.compile(
    r'''//[^\r\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[A-Za-z_][A-Za-z0-9_]*|\s+|.''',
    re.DOTALL,
)
_FUNC_START_RE = re.compile(r"^(?P<indent>\s*)(?P<prefix>(?:unsafe\s+)?(?:extern\s+)?)func\s+[A-Za-z_][A-Za-z0-9_]*\s*\(")


@dataclass(frozen=True)
class EnumDeclaration:
    """Original enum name, brace offsets, and semicolon-delimited variant spans."""

    name: str
    body_start: int
    body_end: int
    variants: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class _BracedDeclaration:
    """Declaration name, brace offsets, and semicolon-delimited member spans."""

    name: str
    body_start: int
    body_end: int
    members: tuple[tuple[int, int], ...]


def _iter_braced_declarations(source: str, keyword: str) -> Iterator[_BracedDeclaration]:
    """Locate complete top-level declarations, ignoring comments and literals.

    Args:
        source: Original Dea source or textual module interface.
        keyword: Declaration keyword to locate.

    Yields:
        Declarations with absolute character offsets into source. Member
        spans exclude their terminating semicolons and retain original text.
    """
    depth = 0
    awaiting_name = False
    declaration_name: str | None = None
    body_start: int | None = None
    member_start = 0
    nesting = 0
    members: list[tuple[int, int]] = []
    for match in _SOURCE_TOKEN_RE.finditer(source):
        token = match.group()
        if token.isspace() or token.startswith(("//", "/*")):
            continue
        if body_start is not None:
            if token == "}" and nesting == 0:
                assert declaration_name is not None
                yield _BracedDeclaration(declaration_name, body_start, match.start(), tuple(members))
                declaration_name = None
                body_start = None
            elif token in {"(", "[", "{"}:
                nesting += 1
            elif token in {")", "]", "}"}:
                nesting -= 1
            elif token == ";" and nesting == 0:
                members.append((member_start, match.start()))
                member_start = match.end()
            continue
        if awaiting_name:
            declaration_name = token
            awaiting_name = False
            continue
        if declaration_name is not None:
            if token == "{":
                body_start = match.start()
                member_start = match.end()
                nesting = 0
                members = []
                continue
            declaration_name = None
        if token == keyword and depth == 0:
            awaiting_name = True
        elif token == "{":
            depth += 1
        elif token == "}":
            depth -= 1


def iter_enum_declarations(source: str) -> Iterator[EnumDeclaration]:
    """Locate complete top-level enums while ignoring comments and literals.

    Args:
        source: Original Dea source or textual module interface.

    Yields:
        Enum declarations with absolute character offsets into source. Variant
        spans exclude their terminating semicolons and retain original text.
    """
    for declaration in _iter_braced_declarations(source, "enum"):
        yield EnumDeclaration(
            declaration.name, declaration.body_start, declaration.body_end, declaration.members
        )


def _apply_edits(source: str, edits: list[tuple[int, int, str]]) -> str:
    """Apply non-overlapping replacements in source order.

    Args:
        source: Original source text.
        edits: Ordered start offsets, end offsets, and replacement text.

    Returns:
        Source text with the replacements applied.
    """
    output: list[str] = []
    retained_start = 0
    for start, end, replacement in edits:
        output.extend((source[retained_start:start], replacement))
        retained_start = end
    output.append(source[retained_start:])
    return "".join(output)


def _rewrite_enum_declarations(source: str) -> str:
    """Translate enum syntax for Doxygen without moving source lines.

    Args:
        source: Dea source with export manifests already removed.

    Returns:
        C-like enums with payloads blanked, variant separators converted to
        commas, and closing semicolons. Original variant text remains available
        to renderers through the source spans.
    """
    edits: list[tuple[int, int, str]] = []
    for declaration in iter_enum_declarations(source):
        for start, end in declaration.variants:
            tokens = [
                match for match in _SOURCE_TOKEN_RE.finditer(source, start, end)
                if not match.group().isspace() and not match.group().startswith(("//", "/*"))
            ]
            if len(tokens) > 1 and tokens[1].group() == "(":
                nesting = 0
                for token in tokens[1:]:
                    if token.group() == "(":
                        nesting += 1
                    elif token.group() == ")":
                        nesting -= 1
                        if nesting == 0:
                            payload_start, payload_end = tokens[1].start(), token.end()
                            blanked = re.sub(r"[^\r\n]", " ", source[payload_start:payload_end])
                            edits.append((payload_start, payload_end, blanked))
                            break
            edits.append((end, end + 1, ","))
        edits.append((declaration.body_end + 1, declaration.body_end + 1, ";"))
    return _apply_edits(source, edits)


def _strip_export_manifests(source: str) -> str:
    """Blank complete top-level export manifests without moving source text.

    Comments and quoted literals are single tokens, so their braces, keywords,
    and semicolons cannot start or end a manifest. Exported opaque groups are
    removed with the rest of their manifest.

    Args:
        source: Original Dea source or textual module interface.

    Returns:
        Source with complete export manifests replaced by spaces, retaining
        every carriage return and newline and all text outside the manifests.
    """
    output: list[str] = []
    depth = 0
    export_start: int | None = None
    retained_start = 0
    for match in _SOURCE_TOKEN_RE.finditer(source):
        token = match.group()
        if export_start is not None:
            if token == ";":
                output.append(source[retained_start:export_start])
                output.append(re.sub(r"[^\r\n]", " ", source[export_start:match.end()]))
                retained_start = match.end()
                export_start = None
        elif token == "export" and depth == 0:
            export_start = match.start()
        elif token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
    output.append(source[retained_start:])
    return "".join(output)


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


def _rewrite_struct_declarations(source: str) -> str:
    """Translate struct fields and terminators without moving source lines.

    Args:
        source: L0/L1 source after export and enum adaptation.

    Returns:
        C-like structs retaining field comments and original line endings.
    """
    edits: list[tuple[int, int, str]] = []
    for declaration in _iter_braced_declarations(source, "struct"):
        for start, end in declaration.members:
            matches = list(_SOURCE_TOKEN_RE.finditer(source, start, end))
            tokens = [
                match for match in matches
                if not match.group().isspace() and not match.group().startswith(("//", "/*"))
            ]
            if len(tokens) < 3 or tokens[1].group() != ":":
                continue
            field_type = _format_decl_type("".join(token.group() for token in tokens[2:]))
            trivia = "".join(
                match.group() for match in matches
                if match.start() >= tokens[0].end()
                and (match.group().isspace() or match.group().startswith(("//", "/*")))
            )
            if not trivia.strip() and "\n" not in trivia and "\r" not in trivia:
                trivia = ""
            edits.append((tokens[0].start(), end + 1, f"{field_type} {tokens[0].group()}{trivia};"))
        edits.append((declaration.body_end + 1, declaration.body_end + 1, ";"))
    return _apply_edits(source, edits)


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


def _top_level_function_lines(source: str) -> set[int]:
    """Find function declaration lines outside comments, literals, and bodies.

    Args:
        source: Source text with original line positions.

    Returns:
        Zero-based line numbers containing top-level function keywords.
    """
    lines: set[int] = set()
    depth = 0
    line = 0
    for match in _SOURCE_TOKEN_RE.finditer(source):
        token = match.group()
        if token == "func" and depth == 0:
            lines.add(line)
        elif token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
        line += token.count("\n")
    return lines


def transform_l0_for_doxygen(source: str) -> str:
    """Rewrite L0/L1 declarations while retaining source line numbers.

    Args:
        source: Original Dea source or textual module interface.

    Returns:
        C-like declarations for Doxygen; renderers recover original signatures.

    Raises:
        ValueError: A function signature cannot be represented.
    """
    normalized = _rewrite_struct_declarations(_rewrite_enum_declarations(_strip_export_manifests(source)))
    function_lines = _top_level_function_lines(normalized)
    lines = normalized.splitlines(keepends=True)
    output: list[str] = []
    func_signature_lines: list[str] = []

    for line_number, line in enumerate(lines):
        alias = re.match(r"^\s*type\s+(\w+)\s*=\s*(.*);\s*$", line)
        if alias:
            output.append(f"typedef {_format_decl_type(alias[2])} {alias[1]};\n")
            continue
        if re.match(r"^\s*(?:module|import|fingerprint|entry)\b", line):
            output.append("\n")
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

        if line_number in function_lines and _FUNC_START_RE.match(line):
            func_signature_lines = [line]
            if "{" in line or ";" in line:
                rewritten = _rewrite_function_signature(func_signature_lines)
                if rewritten is None:
                    output.extend(func_signature_lines)
                else:
                    output.append(rewritten + "\n" * (len(func_signature_lines) - 1))
                func_signature_lines = []
            continue

        output.append(line)

    if func_signature_lines:
        output.extend(func_signature_lines)

    return "".join(output)
