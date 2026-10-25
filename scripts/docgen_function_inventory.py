# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Collect undocumented functions using Doxygen's declaration/body identities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from c_declarators import parameter_type


@dataclass(frozen=True)
class _Occurrence:
    """One XML occurrence and the explicit locations identifying its function."""

    source: str
    line: int | None
    name: str
    documented: bool
    identity: tuple[object, ...]
    anchors: tuple[tuple[object, ...], ...]


def _positive_line(value: str | None) -> int | None:
    """Return a positive XML line number, or None for unavailable metadata."""
    try:
        number = int(value or "")
    except ValueError:
        return None
    return number if number > 0 else None


def _text(element: ET.Element | None, typedefs: dict[str, ET.Element] | None = None) -> str:
    """Return XML text with insignificant C token spacing removed."""
    if element is None:
        return ""

    def expanded(node: ET.Element, visited: frozenset[str]) -> str:
        result = node.text or ""
        for child in node:
            reference = child.get("refid", "")
            if typedefs and child.tag == "ref" and reference in typedefs and reference not in visited:
                result += expanded(typedefs[reference], visited | {reference})
            else:
                result += expanded(child, visited)
            result += child.tail or ""
        return result

    return " ".join(re.findall(r"\w+|[^\w\s]", expanded(element, frozenset())))


def _binding(path: str) -> str:
    """Keep translated Dea and native C bindings in separate inventories."""
    suffix = Path(path).suffix
    return "C" if suffix in {".c", ".h"} else suffix


def _own_documentation(source_root: Path | None, source: str, line: int | None) -> bool:
    """Recognize a binding's own preceding contract after a cross-binding merge.

    Doxygen sometimes attaches a native C body to a translated Dea declaration.
    Its copied contract cannot establish documentation for that Dea binding.
    """
    if source_root is None or line is None:
        return False
    path = source_root / source
    if not path.is_file():
        return False
    prefix = "".join(path.read_text(encoding="utf-8").splitlines(keepends=True)[:line - 1])
    # The signature may span lines, but cannot cross another declaration/body.
    # Remove ordinary comments from its intervening declaration trivia first.
    blocks = list(re.finditer(r"/\*\*(?!\*)(.*?)\*/", prefix, re.DOTALL))
    if not blocks:
        return False
    block = blocks[-1]
    gap = re.sub(r"/\*.*?\*/|//[^\n]*", "", prefix[block.end():], flags=re.DOTALL)
    if re.search(r"[@\\](?:file|mainpage|page|namespace|defgroup|addtogroup|struct|union|enum|typedef|def|var|class)\b", block.group(1)):
        return False
    content = re.sub(r"[\s*]", "", block.group(1))
    return bool(content) and not re.search(r"[;{}]", gap)



def _expand_alias_tokens(tokens: list[str], aliases: dict[str, str]) -> tuple[str, ...]:
    """Expand unambiguous typedef names appearing inside callback signatures."""
    def expand_sequence(sequence: list[str], visited: frozenset[str]) -> list[str]:
        result = []
        for index, token in enumerate(sequence):
            # Tags inhabit a separate C namespace. `struct Node` must not
            # expand the typedef Node a second time into `struct struct Node`.
            if (index and sequence[index - 1] in {"struct", "union", "enum"}) or token not in aliases or token in visited:
                result.append(token)
            else:
                target = re.findall(r"[A-Za-z_]\w*|\.\.\.|\S", aliases[token])
                result.extend(expand_sequence(target, visited | {token}))
        return result
    return tuple(expand_sequence(tokens, frozenset()))


def _occurrences(xml_dir: Path, source_root: Path | None) -> list[_Occurrence]:
    """Read functions without conflating source languages or static linkage."""
    result = []
    compounds = [ET.parse(path) for path in sorted(xml_dir.glob("*.xml")) if path.name != "index.xml"]
    # Resolve explicit typedef references, preserving pointer/array structure.
    # This recognizes e.g. L0 dea_int/l0_int declarations of the same C ABI.
    typedefs = {member.get("id", ""): member.find("type")
                for tree in compounds for member in tree.findall(".//memberdef[@kind='typedef']")
                if member.get("id") and member.find("type") is not None and not member.findtext("argsstring")}
    alias_candidates: dict[tuple[str, str], set[str]] = {}
    for tree in compounds:
        for member in tree.findall(".//memberdef[@kind='typedef']"):
            location = member.find("location")
            if location is None or member.findtext("argsstring"):
                continue
            key = (_binding(location.get("file", "")), member.findtext("name", ""))
            alias_candidates.setdefault(key, set()).add(_text(member.find("type"), typedefs))
    aliases = {key: next(iter(targets)) for key, targets in alias_candidates.items() if len(targets) == 1}
    for tree in compounds:
        for member in tree.findall(".//memberdef[@kind='function']"):
            location = member.find("location")
            if location is None:
                continue
            source = location.get("file", "").strip()
            name = member.findtext("name", "").strip()
            if not source or not name:
                continue
            # Dea is translated to C for Doxygen. Its bindings must never be
            # treated as C implementations merely because XML says language=C.
            binding = _binding(source)
            local_aliases = {name: target for (domain, name), target in aliases.items() if domain == binding}
            parameters = tuple(_expand_alias_tokens(parameter_type(re.findall(r"[A-Za-z_]\w*|\.\.\.|\S",
                                      " ".join((_text(p.find("type"), typedefs), _text(p.find("argsstring")), _text(p.find("array")))))), local_aliases)
                               for p in member.findall("param"))
            identity = (
                binding, member.findtext("qualifiedname", name),
                _text(member.find("type"), typedefs), parameters,
                member.get("static", "no"), member.get("const", "no"),
                member.get("volatile", "no"), member.get("refqual", ""),
            )
            anchors: list[tuple[object, ...]] = []
            # Only Doxygen's explicit source relationship authorizes merging.
            # Equal names/signatures alone do not establish function identity.
            for path_key, line_key in (("file", "line"), ("declfile", "declline"), ("bodyfile", "bodystart")):
                path, line = location.get(path_key, ""), _positive_line(location.get(line_key))
                if path and line is not None and _binding(path) == binding:
                    anchors.append((path, line))
            if member.get("id"):
                anchors.append(("xml-id", member.get("id")))
            line = _positive_line(location.get("declline")) or _positive_line(location.get("line"))
            if location.get("declfile") and _positive_line(location.get("declline")):
                source = location.get("declfile", source)
            documented = any(
                section is not None and "".join(section.itertext()).strip()
                for section in (member.find(tag) for tag in ("briefdescription", "detaileddescription", "inbodydescription"))
            )
            body_path = location.get("bodyfile", "")
            if body_path and _binding(body_path) != binding:
                documented = _own_documentation(source_root, source, line)
            result.append(_Occurrence(source, line, name, documented, identity, tuple(anchors)))
    return result


def collect_undocumented_functions(xml_dir: Path, source_root: Path | None = None) -> list[tuple[str, int | None, str]]:
    """Report each undocumented function, merging explicit matching occurrences.

    A documented definition covers its matching declaration and vice versa.
    Matching requires the binding, qualified name, return and parameter types,
    linkage, and an XML identity or shared declaration/body location. Unrelated
    static functions, overloads, and Dea/C/Python bindings remain independent.

    Args:
        xml_dir: Directory containing Doxygen XML compounds.
        source_root: Original sources for resolving copied cross-binding docs.

    Returns:
        Sorted source path, declaration line, and function name triples.
    """
    occurrences = _occurrences(xml_dir, source_root)
    parents = list(range(len(occurrences)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    seen: dict[tuple[object, ...], int] = {}
    for index, occurrence in enumerate(occurrences):
        for anchor in occurrence.anchors:
            key = (occurrence.identity, anchor)
            if key in seen:
                parents[find(index)] = find(seen[key])
            else:
                seen[key] = index
    groups: dict[int, list[_Occurrence]] = {}
    for index, occurrence in enumerate(occurrences):
        groups.setdefault(find(index), []).append(occurrence)
    entries = []
    for group in groups.values():
        if any(occurrence.documented for occurrence in group):
            continue
        # Prefer the declaration when both the declaration and body are known.
        representative = min(group, key=lambda o: (Path(o.source).suffix != ".h", o.source, o.line or 0))
        entries.append((representative.source, representative.line, representative.name))
    return sorted(entries, key=lambda item: (item[0], item[1] or 0, item[2]))
