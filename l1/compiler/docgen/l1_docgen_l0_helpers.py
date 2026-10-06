# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Shared L1 source helpers for docs generation."""

from __future__ import annotations

from functools import lru_cache
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def module_name_for_source_path(source_path: str) -> str | None:
    """Return the declared module name for an L0/Python source path."""
    path = Path(source_path)
    if path.suffix in {".l0", ".l1"} and not path.is_absolute() and path.exists():
        match = re.search(
            r"^\s*module\s+([A-Za-z_][A-Za-z0-9_.]*)\s*;",
            path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return match.group(1)
    if path.suffix in {".l0", ".l1", ".py"}:
        return path.stem
    return None


@lru_cache(maxsize=None)
def _read_source_lines(source_path: str) -> tuple[str, ...]:
    path = Path(source_path)
    return tuple(path.read_text(encoding="utf-8").splitlines())


def _member_source_path(memberdef: ET.Element) -> str:
    location = memberdef.find("location")
    if location is None:
        return ""
    return location.attrib.get("file", "")


def _member_start_line(memberdef: ET.Element) -> int | None:
    location = memberdef.find("location")
    if location is None:
        return None
    line_text = location.attrib.get("declline") or location.attrib.get("line")
    if not line_text:
        return None
    try:
        line = int(line_text)
    except ValueError:
        return None
    return line if line > 0 else None


def _strip_line_comment(line: str) -> str:
    return line.split("//", 1)[0].rstrip()


def _normalize_l0_declaration_text(text: str) -> str:
    normalized = " ".join(part for part in (_strip_line_comment(line).strip() for line in text.splitlines()) if part)
    normalized = re.sub(r"\(\s*", "(", normalized)
    normalized = re.sub(r"\s*\)", ")", normalized)
    normalized = re.sub(r"\s*,\s*", ", ", normalized)
    normalized = re.sub(r":\s*", ": ", normalized)
    normalized = re.sub(r"\s*->\s*", " -> ", normalized)
    normalized = re.sub(r"\s*\*\s*", "*", normalized)
    normalized = re.sub(r"\s*;\s*$", "", normalized)
    normalized = re.sub(r"\s*\{\s*$", "", normalized)
    return normalized.strip()


def _declaration_matches_member(memberdef: ET.Element, declaration: str) -> bool:
    name = memberdef.findtext("name", default="").strip()
    if not name:
        return False

    kind = memberdef.attrib.get("kind", "")
    if kind == "function":
        return re.match(rf"^(?:unsafe\s+)?(?:extern\s+)?func\s+{re.escape(name)}\s*\(", declaration) is not None
    if kind in {"variable", "typedef"}:
        return any(
            re.match(pattern, declaration) is not None
            for pattern in (
                rf"^let\s+{re.escape(name)}\b",
                rf"^type\s+{re.escape(name)}\b",
                rf"^{re.escape(name)}\s*:",
            )
        )
    return False


def _find_declaration_start_index(
    memberdef: ET.Element,
    lines: tuple[str, ...],
    start_index: int,
    *,
    max_scan_lines: int = 64,
) -> int | None:
    search_end = min(len(lines), start_index + max_scan_lines)
    for index in range(start_index, search_end):
        candidate = _normalize_l0_declaration_text(lines[index])
        if not candidate:
            continue
        if _declaration_matches_member(memberdef, candidate):
            return index
    return None


def extract_l0_member_declaration(memberdef: ET.Element) -> str | None:
    """Recover the original L0 declaration text for a member from source."""
    source_path = _member_source_path(memberdef)
    start_line = _member_start_line(memberdef)
    if not source_path or start_line is None:
        return None

    path = Path(source_path)
    if not path.exists():
        return None

    lines = _read_source_lines(str(path.resolve()))
    if start_line > len(lines):
        return None

    declaration_start_index = _find_declaration_start_index(memberdef, lines, start_line - 1)
    if declaration_start_index is None:
        return None

    kind = memberdef.attrib.get("kind", "")
    collected: list[str] = []
    for line in lines[declaration_start_index:]:
        collected.append(line)
        code = _strip_line_comment(line)
        if kind == "function":
            if "{" in code or ";" in code:
                break
        elif kind in {"variable", "typedef"}:
            if ";" in code:
                break
        else:
            return None

    declaration = _normalize_l0_declaration_text("\n".join(collected))
    if not declaration or not _declaration_matches_member(memberdef, declaration):
        return None
    return declaration


def extract_l0_enum_variants(memberdef: ET.Element) -> list[str]:
    """Recover L0 enum variants from the original source body."""
    location = memberdef.find("location")
    if location is None:
        return []
    source_file = location.attrib.get("file", "")
    start_text = location.attrib.get("bodystart") or location.attrib.get("line")
    end_text = location.attrib.get("bodyend") or location.attrib.get("line")
    if not source_file or not start_text or not end_text:
        return []

    path = Path(source_file)
    if path.is_absolute() or not path.exists():
        return []

    try:
        start = int(start_text)
        end = int(end_text)
    except ValueError:
        return []

    if start <= 0 or end < start:
        return []

    variants: list[str] = []
    lines = _read_source_lines(str(path.resolve()))
    for line in lines[start:end]:
        stripped = line.strip()
        if not stripped or stripped in {"{", "}"}:
            continue
        if stripped.startswith("//"):
            continue
        code = line.split("//", 1)[0].strip()
        if not code or code == "}":
            continue
        if code.endswith(";"):
            code = code[:-1].rstrip()
        if code:
            variants.append(code)
    return variants
