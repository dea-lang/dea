#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Validate definition-owned C contracts without compiling or rewriting sources."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

from c_declarators import IDENT, parameter_list as _parameter_list, parameter_type as _parameter_type


ROOT = Path(__file__).resolve().parents[1]
EXCLUSIONS = {
    "tools/": "vendored third-party sources",
    "editors/tree-sitter-dea/src/tree_sitter/": "Tree-sitter upstream support headers",
    "editors/tree-sitter-dea/src/parser.c": "generated Tree-sitter parser",
    "l0/compiler/stage2_l0/tests/fixtures/backend_golden/": "generated backend golden C",
}
LEXEME = re.compile(r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\[\s\S]|[^"\\])*"|\'(?:\\[\s\S]|[^\'\\])*\'')
TOKEN = re.compile(r"[A-Za-z_]\w*|\.\.\.|\S")


@dataclass(frozen=True)
class Comment:
    """One lexical block comment, excluding comment-like bytes in literals."""

    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Function:
    """One physical function declaration or definition and its C type identity."""

    name: str
    start: int
    end: int
    line: int
    definition: bool
    static: bool
    signature: tuple[str, ...]


def lexical_source(text: str) -> tuple[str, list[Comment]]:
    """Mask comments and literals while preserving offsets and source lines.

    Args:
        text: Original C source.

    Returns:
        The masked source and its block comments in source order.
    """
    comments = []

    def mask(match):
        value = match.group()
        if value.startswith("/*"):
            comments.append(Comment(match.start(), match.end(), value))
        return "".join("\n" if char == "\n" else " " for char in value)

    masked = LEXEME.sub(mask, text)
    # Macro bodies can contain function-shaped code; they are not C definitions.
    masked = re.sub(r"^[ \t]*#(?:[^\n]*\\\n)*[^\n]*", lambda m: re.sub(r"[^\n]", " ", m.group()),
                    masked, flags=re.MULTILINE)
    return masked, comments


def executable_tokens(text: str) -> tuple[str, ...]:
    """Return C tokens including literal and directive spelling, without comments.

    Args:
        text: Source before or after a documentation-only edit.

    Returns:
        Tokens suitable for asserting comment-only equivalence.
    """
    spliced = re.sub(r"\\\r?\n", "", text)
    clean = LEXEME.sub(lambda m: " " if m.group().startswith(("/*", "//")) else m.group(), spliced)
    pattern = re.compile(r'(?:u8|[LuU])?"(?:\\[\s\S]|[^"\\])*"|(?:[LuU])?\'(?:\\[\s\S]|[^\'\\])*\'|'
                         r'[A-Za-z_]\w*|(?:\d|\.\d)(?:[eEpP][+-]|[\w.])*|'
                         r'%:%:|>>=|<<=|\.\.\.|##|<:|:>|<%|%>|%:|\?\?[=/\'()!<>-]|->|\+\+|--|&&|\|\||<=|>=|==|!=|\*=|/=|%=|\+=|-=|&=|\^=|\|=|<<|>>|[^\s]')
    result = []
    for line in clean.splitlines():
        # Adjacency after a macro name distinguishes function-like and object-like
        # macros even though ordinary C whitespace is not executable syntax.
        if re.match(r"^[ \t]*#[ \t]*define[ \t]+[A-Za-z_]\w*\(", line):
            result.append("<function-like-macro>")
        result.extend(pattern.findall(line))
        if line.lstrip().startswith("#"):
            result.append("<directive-end>")
    return tuple(result)


def _domain(path: Path) -> str:
    """Separate level-owned C ABIs before comparing declaration signatures.

    Args:
        path: Repository-relative source path.

    Returns:
        Its language-level name, or the shared-code domain.
    """
    return path.parts[0] if path.parts and re.fullmatch(r"l\d+", path.parts[0]) else "shared"


def _typedef_aliases(sources: list[tuple[Path, str]]) -> dict[str, dict[str, tuple[str, ...]]]:
    """Collect unambiguous simple typedef aliases within each language level.

    This intentionally does not infer arbitrary C type equivalence. It bridges
    maintained scalar and record aliases such as dea_int/l0_int; conflicting,
    callback, array, and anonymous-record typedefs remain lexical identities.

    Args:
        sources: Repository-relative paths and their complete C source.

    Returns:
        Domain-keyed aliases that have one consistent target spelling.
    """
    candidates = {}
    pattern = re.compile(r"\btypedef\s+([^;{}()\[\]]+?)\s+(\w+)\s*;")
    for path, text in sources:
        masked, _ = lexical_source(text)
        domain = candidates.setdefault(_domain(path), {})
        for match in pattern.finditer(masked):
            domain.setdefault(match[2], set()).add(tuple(TOKEN.findall(match[1])))
    return {domain: {name: next(iter(targets)) for name, targets in aliases.items() if len(targets) == 1}
            for domain, aliases in candidates.items()}


def _resolved_signature(signature: tuple[str, ...], aliases: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    """Expand known typedef chains without collapsing tags or ambiguous names.

    Args:
        signature: Parameter-name-free lexical function signature.
        aliases: Unambiguous aliases for this function's language level.

    Returns:
        Signature with simple typedef aliases expanded recursively.
    """
    def expand(tokens, active):
        result = []
        for index, token in enumerate(tokens):
            if (token in aliases and token not in active
                    and (index == 0 or tokens[index - 1] not in {"struct", "union", "enum"})):
                result.extend(expand(aliases[token], active | {token}))
            else:
                result.append(token)
        return result

    return tuple(expand(signature, set()))


def functions(text: str) -> list[Function]:
    """Find physical top-level functions, including conditional alternatives.

    This is a lexical convention checker, not a C preprocessor or type checker.
    Macro-generated functions are checked through real Doxygen inventory tests.

    Args:
        text: Original C source.

    Returns:
        Function occurrences with source offsets and parameter-name-free types.
    """
    masked, _ = lexical_source(text)
    tokens = list(TOKEN.finditer(masked))
    words = [token.group() for token in tokens]
    pairs = {}
    stacks = {"(": [], "{": []}
    for index, word in enumerate(words):
        if word in stacks:
            stacks[word].append(index)
        elif word in {"}", ")"}:
            stack = stacks["{" if word == "}" else "("]
            if stack:
                pairs[stack.pop()] = index
    found = []
    start = 0
    index = 0
    while index < len(tokens):
        word = words[index]
        if word not in {"{", ";", "}"}:
            index += 1
            continue
        chunk = words[start:index]
        candidate = None
        cursor = start
        while cursor < index:
            if words[cursor] == "(" and cursor in pairs:
                closing = pairs[cursor]
                if (closing == cursor + 2 and IDENT.fullmatch(words[cursor + 1])
                        and closing + 1 < index and words[closing + 1] == "("
                        and closing + 1 in pairs):
                    # Parenthesized names intentionally bypass function-like macros.
                    candidate = (closing + 1, pairs[closing + 1], words[cursor + 1], cursor)
                    break
                if cursor > start and closing < index and IDENT.fullmatch(words[cursor - 1]):
                    name = words[cursor - 1]
                    if name not in {"__attribute__", "__declspec", "sizeof", "_Static_assert", "alignof"}:
                        candidate = (cursor, closing, name, cursor - 1)
                        break
                cursor = closing
            cursor += 1
        if candidate and "typedef" not in chunk and "=" not in chunk:
            opening, closing, name, prefix_end = candidate
            prefix = [value for value in words[start:prefix_end] if value not in {"extern", "static", "inline"}]
            if prefix:
                params = _parameter_list(words[opening + 1:closing])
                end = pairs.get(index, index) if word == "{" else index
                found.append(Function(name, tokens[start].start(), tokens[end].end(),
                                      text.count("\n", 0, tokens[start].start()) + 1,
                                      word == "{", "static" in chunk,
                                      tuple([*prefix, "(", *params, ")"])))
            if word == "{":
                index = pairs.get(index, index)
        elif word == "{" and chunk != ["extern"]:
            index = pairs.get(index, index)
        start = index + 1
        index += 1
    return found


def preceding_comment(text: str, function: Function) -> Comment | None:
    """Find a block immediately before a function's declaration tokens."""
    _, comments = lexical_source(text)
    previous = next((comment for comment in reversed(comments) if comment.end <= function.start), None)
    return previous if previous and not text[previous.end:function.start].strip() else None


def brief(comment: str) -> str:
    """Extract the canonical first sentence without its optional brief tag.

    Args:
        comment: Ordinary or Doxygen block, including delimiters.

    Returns:
        The brief sentence with source-line wrapping reduced to spaces.
    """
    body = comment[3:-2] if comment.startswith(("/**", "/*!")) else comment[2:-2]
    lines = [re.sub(r"^\s*\* ?", "", line).strip() for line in body.splitlines()]
    paragraph = []
    for line in lines:
        if not line and paragraph:
            break
        if line.startswith(("@brief ", "\\brief ")):
            line = line[7:]
        elif line.startswith(("@", "\\")):
            break
        if line:
            paragraph.append(line)
    flattened = " ".join(paragraph)
    sentence = re.search(r"[.!?](?=\s|$)", flattened)
    return flattened[:sentence.end()] if sentence else flattened


def exclusion(path: Path) -> str | None:
    """Return the documented vendor/generated exclusion for a relative path."""
    spelling = path.as_posix()
    return next((reason for prefix, reason in EXCLUSIONS.items() if spelling.startswith(prefix)), None)


def tracked_sources(root: Path = ROOT) -> list[Path]:
    """Enumerate tracked C files without silently ignoring maintained fixtures."""
    result = subprocess.run(["git", "ls-files", "-z", "--", "*.c", "*.h"], cwd=root,
                            capture_output=True, check=True)
    return [Path(name) for name in result.stdout.decode().split("\0") if name]


def validate(root: Path, paths: list[Path]) -> list[str]:
    """Check autobrief, spacing, contracts, and matching header prototype briefs.

    Args:
        root: Checkout or fixture directory.
        paths: Relative C/header paths to inspect together.

    Returns:
        Source-located errors, with unrelated functions kept separate.
    """
    errors = []
    declarations = []
    definitions = []
    sources = [(path, (root / path).read_text(encoding="utf-8")) for path in paths if not exclusion(path)]
    aliases = _typedef_aliases(sources)
    for path, text in sources:
        if exclusion(path):
            continue
        _, comments = lexical_source(text)
        for comment in comments:
            prefix = text[:comment.start]
            lines = prefix.split("\n")
            if lines[-1].strip() or (len(lines) > 1 and lines[-2].strip()):
                errors.append(f"{path.as_posix()}:{len(lines)}: block comment needs a blank source line before it")
            for command in re.finditer(r"(?<![\w@\\])(?:@|\\)brief\b", comment.text):
                line = text.count("\n", 0, comment.start + command.start()) + 1
                errors.append(f"{path.as_posix()}:{line}: use Javadoc autobrief: start with the brief sentence and omit explicit @brief or \\brief commands")
        for function in functions(text):
            comment = preceding_comment(text, function)
            location = f"{path.as_posix()}:{function.line}: {function.name}"
            if function.definition:
                if not comment or not comment.text.startswith("/**\n"):
                    errors.append(f"{location}: definition needs an immediately preceding multiline Doxygen contract")
                elif not brief(comment.text):
                    errors.append(f"{location}: contract needs a brief sentence")
                elif (not re.fullmatch(r"/\*\*\n(?:[ \t]+\*(?: [^\n]*)?\n)*[ \t]+\*/", comment.text)
                      or re.search(r"(?:@|\\)(?:file|struct|union|enum|typedef|def|var|class)\b", comment.text)):
                    errors.append(f"{location}: contract needs function-owned Doxygen content lines prefixed with ` *`")
                definitions.append((path, function, comment))
            elif path.suffix == ".h":
                if not comment or not re.fullmatch(r"/\* [^\n]* \*/", comment.text) or comment.text.startswith("/**"):
                    errors.append(f"{location}: prototype needs an ordinary one-line brief comment")
                declarations.append((path, function, comment))
    for path, function, comment in declarations:
        if not comment:
            continue
        domain = _domain(path)
        signature = _resolved_signature(function.signature, aliases.get(domain, {}))
        matches = [(candidate, contract) for other, candidate, contract in definitions
                   if _domain(other) == domain
                   and candidate.name == function.name
                   and _resolved_signature(candidate.signature, aliases.get(domain, {})) == signature
                   and (not (function.static or candidate.static) or other == path)]
        for candidate, contract in matches:
            if contract and brief(contract.text) != comment.text[2:-2].strip():
                errors.append(f"{path.as_posix()}:{function.line}: {function.name}: header brief differs from definition")
                break
    return errors


def main() -> int:
    """Validate the maintained C inventory and report explicit exclusions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="Optional repository-relative C/header paths")
    args = parser.parse_args()
    paths = args.paths or tracked_sources()
    errors = validate(ROOT, paths)
    for error in errors:
        print(error)
    maintained = [path for path in paths if not exclusion(path)]
    print(f"C documentation: {len(maintained)} maintained files, {len(paths) - len(maintained)} vendor/generated exclusions, {len(errors)} errors.")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
