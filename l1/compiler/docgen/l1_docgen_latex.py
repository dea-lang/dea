# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Normalize native Doxygen LaTeX output for L0 sources."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .l1_docgen_l0_helpers import extract_l0_enum_variants, extract_l0_member_declaration, module_name_for_source_path

_POINTER_MACRO = r"\texorpdfstring{$\ast$}{*}"
_ARROW_MACRO = r"\texorpdfstring{$\rightarrow$}{->}"
_FAT_ARROW_MACRO = r"\texorpdfstring{$\Rightarrow$}{=>}"
_FRONT_MATTER_BREAK = "l0docgenlinetwo"


def _escape_latex_texttt(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "_": r"\_",
        "#": r"\#",
        "$": r"\$",
        "%": r"\%",
        "&": r"\&",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def _escape_l0_declaration_for_latex(text: str) -> str:
    arrow_token = "L0DOCGENARROWTOKEN"
    pointer_token = "L0DOCGENPOINTERTOKEN"
    escaped = _escape_latex_texttt(text.replace("->", arrow_token).replace("*", pointer_token))
    return escaped.replace(arrow_token, _ARROW_MACRO).replace(pointer_token, _POINTER_MACRO)


def _normalize_signature_line(line: str) -> str:
    if not any(marker in line for marker in ("func ", "struct ", r"\item[{", ":")):
        return line
    normalized = re.sub(r":(?:\\\+)+", ": ", line)
    normalized = re.sub(r"\s+" + re.escape(_POINTER_MACRO), lambda _: _POINTER_MACRO, normalized)
    if r"\hspace{0.3cm}{\ttfamily [extern]}" in normalized and "func " in normalized:
        normalized = normalized.replace(r"\hspace{0.3cm}{\ttfamily [extern]}", "")
        normalized = re.sub(r"(?<!\S)func\s+", "extern func ", normalized, count=1)
    return normalized


def _normalize_prose_arrow_line(line: str) -> str:
    fat_arrow_token = "L0DOCGENFATARROWTOKEN"
    normalized = line.replace(r"-\/\texorpdfstring{$>$}{>}", _ARROW_MACRO)
    normalized = normalized.replace(r"-\/$>$", _ARROW_MACRO)
    normalized = normalized.replace(r"\texorpdfstring{\textrightarrow}{->}", _ARROW_MACRO)
    normalized = re.sub(r"(?<!\{)=>(?!\})", fat_arrow_token, normalized)
    normalized = normalized.replace(fat_arrow_token, _FAT_ARROW_MACRO)
    return normalized


def _insert_after_index(text: str, block: str) -> str:
    if block in text:
        return text
    match = re.search(r"(\\index\{[^\n]+\}\n)", text)
    if match is None:
        return text
    return text[: match.end()] + "\n" + block.rstrip() + "\n" + text[match.end() :]


def _normalize_public_attributes_section(text: str) -> str:
    start = text.find(r"\doxysubsubsection*{Public Attributes}")
    if start == -1:
        return text
    end = text.find(r"\doxysubsection{Detailed Description}", start)
    if end == -1:
        return text

    lines = text[start:end].splitlines()
    for index, line in enumerate(lines[:-1]):
        if line.strip() != r"\item":
            continue
        candidate = lines[index + 1]
        stripped = candidate.strip()
        if not stripped:
            continue
        match = re.match(r"^(?P<type>.+?)\s+(?P<name>\\doxymbox\{.+\}|[^\s]+)$", stripped)
        if match is None:
            continue
        indent = candidate[: len(candidate) - len(candidate.lstrip())]
        lines[index + 1] = indent + _normalize_signature_line(f"{match.group('name')}: {match.group('type')}")

    return text[:start] + "\n".join(lines) + text[end:]


def _normalize_member_data_signatures(text: str) -> str:
    pattern = re.compile(
        r"^(?P<indent>\s*)(?P<type>.+?)\s+[A-Za-z0-9\\+._]+::(?:\\\+)?(?P<name>.+)\}$",
        re.MULTILINE,
    )

    def replace(match: re.Match[str]) -> str:
        line = f"{match.group('name')}: {match.group('type')}}}"
        return match.group("indent") + _normalize_signature_line(line)

    return pattern.sub(replace, text)


def _normalize_tex_lines(text: str) -> str:
    normalized_lines = []
    for line in text.splitlines():
        line = _normalize_signature_line(line)
        line = _normalize_prose_arrow_line(line)
        normalized_lines.append(line)
    return "\n".join(normalized_lines) + "\n"


def _normalize_prose_arrows(text: str) -> str:
    return "\n".join(_normalize_prose_arrow_line(line) for line in text.splitlines()) + "\n"


def _normalize_titlepage_front_matter(text: str) -> str:
    pattern = re.compile(r"^(?P<indent>\s*)\[1ex\]\\large (?P<content>.*) \\\\$", re.MULTILINE)
    separator_re = re.compile(rf"\s+{re.escape(_FRONT_MATTER_BREAK)}\s+")

    def replace(match: re.Match[str]) -> str:
        content = match.group("content")
        separator_match = separator_re.search(content)
        if separator_match is None:
            return match.group(0)
        first_line = content[: separator_match.start()].strip()
        second_line = content[separator_match.end() :].strip()
        if not first_line or not second_line:
            return match.group(0)
        indent = match.group("indent")
        return "\n".join(
            (
                f"{indent}[1ex]\\large {first_line} \\\\",
                f"{indent}\\large {second_line} \\\\",
            )
        )

    return pattern.sub(replace, text, count=1)


def _normalize_l0_signature_links(text: str) -> str:
    pattern = re.compile(
        r"extern func \\(?P<kind>hyper|doxy)link\{(?P<target>[^}]+)\}\{(?P<label>[^}]*)\}"
        r"(?P<args>\([^)]*\))?\s*"
        + re.escape(_ARROW_MACRO)
        + r"\s*(?P<ret>[^;{}]+);"
    )

    def replace(match: re.Match[str]) -> str:
        label = match.group("label").strip()
        args = (match.group("args") or "").strip()
        ret = match.group("ret").strip()
        if args and "(" not in label:
            label = f"{label}{args}"
        link_label = f"func {label} {_ARROW_MACRO} {ret}"
        return rf"extern \{match.group('kind')}link{{{match.group('target')}}}{{{link_label}}};"

    return pattern.sub(replace, text)


def _normalize_link_display_name(text: str) -> str:
    normalized = text.replace(r"\+", "").replace(r"\_", "_")
    normalized = normalized.replace("{", "").replace("}", "")
    return normalized.strip()


def _member_name_link(member_id: str, line: str) -> str | None:
    latex_member_id = re.sub(r"_1([a-z])", r"_\1", member_id, count=1)
    pattern = re.compile(
        rf"(\\doxymbox\{{\\hyperlink\{{{re.escape(latex_member_id)}\}}\{{[^}}]+\}}\}}|"
        rf"\\hyperlink\{{{re.escape(latex_member_id)}\}}\{{[^}}]+\}})"
    )
    match = pattern.search(line)
    return match.group(1) if match is not None else None


def _find_balanced_brace_end(text: str, block_start: int) -> int | None:
    if block_start < 0 or block_start >= len(text) or text[block_start] != "{":
        return None

    depth = 0
    index = block_start
    while index < len(text):
        if text.startswith(r"\{", index) or text.startswith(r"\}", index):
            index += 2
            continue
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _detail_heading_title(memberdef: ET.Element) -> str | None:
    name = memberdef.findtext("name", default="").strip()
    if not name:
        return None
    title = _escape_latex_texttt(name)
    if memberdef.attrib.get("kind") == "function":
        title += "()"
    return title


def _find_detail_block_start_by_heading(text: str, memberdef: ET.Element) -> int | None:
    title = _detail_heading_title(memberdef)
    if title is None:
        return None

    header_tokens = [rf"\texorpdfstring{{{title}}}{{{title}}}", title]
    for token in header_tokens:
        token_index = text.find(token)
        while token_index != -1:
            header_start = text.rfind(r"\doxysubsubsection{", 0, token_index)
            if header_start != -1:
                header_end = text.find("\n", header_start)
                if header_end == -1:
                    header_end = len(text)
                next_subsection = text.find(r"\doxysubsubsection", header_end)
                search_end = next_subsection if next_subsection != -1 else len(text)
                block_start = text.find(r"{\footnotesize", header_end, search_end)
                if block_start != -1:
                    return block_start
            token_index = text.find(token, token_index + 1)
    return None


def _render_l0_declaration(
    declaration: str,
    memberdef: ET.Element,
    linked_name_tex: str | None = None,
) -> str:
    if linked_name_tex is None:
        return _escape_l0_declaration_for_latex(declaration)

    name = memberdef.findtext("name", default="").strip()
    if not name:
        return _escape_l0_declaration_for_latex(declaration)

    patterns = (
        rf"(?P<prefix>(?:extern\s+)?func\s+){re.escape(name)}(?P<suffix>\s*\(.*)$",
        rf"(?P<prefix>let\s+){re.escape(name)}(?P<suffix>\b.*)$",
        rf"(?P<prefix>type\s+){re.escape(name)}(?P<suffix>\b.*)$",
        rf"(?P<prefix>){re.escape(name)}(?P<suffix>\s*:.*)$",
    )
    for pattern in patterns:
        match = re.match(pattern, declaration)
        if match is not None:
            return (
                _escape_l0_declaration_for_latex(match.group("prefix"))
                + linked_name_tex
                + _escape_l0_declaration_for_latex(match.group("suffix"))
            )
    return _escape_l0_declaration_for_latex(declaration)


def _replace_member_summary_signature(text: str, memberdef: ET.Element, declaration: str) -> str:
    member_id = memberdef.attrib.get("id", "")
    if not member_id:
        return text
    latex_member_id = re.sub(r"_1([a-z])", r"_\1", member_id, count=1)

    pattern = re.compile(
        rf"^(?P<indent>\s*)(?P<line>.*\\hyperlink\{{{re.escape(latex_member_id)}\}}\{{[^}}]+\}}.*)$",
        re.MULTILINE,
    )

    def replace(match: re.Match[str]) -> str:
        linked_name = _member_name_link(member_id, match.group("line"))
        if linked_name is None:
            return match.group(0)
        return match.group("indent") + _render_l0_declaration(declaration, memberdef, linked_name)

    return pattern.sub(replace, text, count=1)


def _replace_member_detail_signature(text: str, memberdef: ET.Element, declaration: str) -> str:
    member_id = memberdef.attrib.get("id", "")
    block_start: int | None = None
    if member_id:
        latex_member_id = re.sub(r"_1([a-z])", r"_\1", member_id, count=1)
        label_token = rf"\label{{{latex_member_id}}}"
        label_index = text.find(label_token)
        if label_index != -1:
            block_start = text.rfind(r"{\footnotesize", 0, label_index)
    if block_start is None or block_start == -1:
        block_start = _find_detail_block_start_by_heading(text, memberdef)
    if block_start is None:
        return text

    block_end = _find_balanced_brace_end(text, block_start)
    if block_end is None:
        return text

    block = text[block_start:block_end + 1]
    header_match = re.match(r"(\{\\footnotesize.*?\\label\{[^}]+\}\s*)", block, re.DOTALL)
    if header_match is None:
        # \label may be outside the {\footnotesize ...} block (Doxygen <= 1.9.x).
        # Re-locate via heading to ensure we have the correct block.
        heading_start = _find_detail_block_start_by_heading(text, memberdef)
        if heading_start is not None:
            heading_end = _find_balanced_brace_end(text, heading_start)
            if heading_end is not None:
                block_start = heading_start
                block_end = heading_end
                block = text[block_start:block_end + 1]
                header_match = re.match(r"(\{\\footnotesize\s*(?:\\ttfamily\s*)?)", block)
    if header_match is None:
        return text

    header = header_match.group(1)
    if not header.endswith("\n"):
        header += "\n"
    replacement = header + _render_l0_declaration(declaration, memberdef) + "}"
    return text[:block_start] + replacement + text[block_end + 1 :]


def _apply_source_declarations(text: str, compounddef: ET.Element) -> str:
    for section in compounddef.findall("sectiondef"):
        for memberdef in section.findall("memberdef"):
            if memberdef.attrib.get("kind") not in {"function", "variable", "typedef"}:
                continue
            declaration = extract_l0_member_declaration(memberdef)
            if declaration is None:
                continue
            text = _replace_member_summary_signature(text, memberdef, declaration)
            text = _replace_member_detail_signature(text, memberdef, declaration)
    return text


def _retarget_l0_symbol_links(text: str, preferred_refids_by_name: dict[str, str]) -> str:
    pattern = re.compile(r"\\(?P<kind>hyper|doxy)link\{(?P<target>[^}]+)\}\{(?P<label>[^}]*)\}")

    def replace(match: re.Match[str]) -> str:
        target = match.group("target")
        if not target.startswith("classl0__"):
            return match.group(0)

        label = match.group("label")
        normalized_label = _normalize_link_display_name(label)
        if "." in normalized_label or normalized_label.startswith("l0_"):
            return match.group(0)

        preferred_target = preferred_refids_by_name.get(normalized_label)
        if not preferred_target or preferred_target == target:
            return match.group(0)

        return rf"\{match.group('kind')}link{{{preferred_target}}}{{{label}}}"

    return pattern.sub(replace, text)


def _variants_block(variants: list[str]) -> list[str]:
    lines = [r"\textbf{Variants:}\\", r"\begin{DoxyItemize}"]
    lines.extend(rf"\item \texttt{{{_escape_latex_texttt(variant)}}}" for variant in variants)
    lines.append(r"\end{DoxyItemize}")
    lines.append("")
    return lines


def _simplify_enum_summary_lists(text: str) -> str:
    lines = text.splitlines()
    idx = 0
    while idx < len(lines):
        if not lines[idx].startswith(r"\doxysubsubsection*{Enumerations}"):
            idx += 1
            continue

        section_begin = next(
            (line_idx for line_idx in range(idx + 1, len(lines)) if lines[line_idx].startswith(r"\begin{DoxyCompactItemize}")),
            None,
        )
        if section_begin is None:
            break
        section_end = next(
            (line_idx for line_idx in range(section_begin + 1, len(lines)) if r"\end{DoxyCompactItemize}" in lines[line_idx]),
            None,
        )
        if section_end is None:
            break

        item_idx = section_begin + 1
        while item_idx < section_end:
            if not lines[item_idx].startswith(r"\item"):
                item_idx += 1
                continue

            signature_idx = item_idx + 1
            while signature_idx < section_end and not lines[signature_idx].strip():
                signature_idx += 1
            if signature_idx >= section_end or not lines[signature_idx].startswith("enum "):
                item_idx = signature_idx
                continue

            description_idx = next(
                (
                    line_idx
                    for line_idx in range(signature_idx + 1, section_end + 1)
                    if lines[line_idx].startswith(r"\begin{DoxyCompactList}")
                ),
                None,
            )
            if description_idx is None:
                item_idx = signature_idx + 1
                continue

            simplified_signature = re.sub(r"\s*\\\{.*$", "", lines[signature_idx]).rstrip()
            lines[signature_idx:description_idx] = [simplified_signature]
            section_end -= description_idx - signature_idx - 1
            item_idx = signature_idx + 1

        idx = section_end + 1

    return "\n".join(lines) + "\n"


def _inject_enum_variants(text: str, file_compound: ET.Element) -> str:
    lines = text.splitlines()
    insertions: list[tuple[int, list[str]]] = []
    removals: list[tuple[int, int]] = []

    for section in file_compound.findall("sectiondef"):
        for memberdef in section.findall("memberdef"):
            if memberdef.attrib.get("kind") != "enum":
                continue
            source_variants = extract_l0_enum_variants(memberdef)
            if not source_variants:
                continue
            xml_variants = [
                enumvalue.findtext("name", default="").strip()
                for enumvalue in memberdef.findall("enumvalue")
                if enumvalue.findtext("name", default="").strip()
            ]
            if source_variants == xml_variants:
                continue

            name = memberdef.findtext("name", default="").strip()
            if not name:
                continue

            header_index = next(
                (idx for idx, line in enumerate(lines) if line.startswith(r"\doxysubsubsection") and f"{{{name}}}{{{name}}}" in line),
                None,
            )
            if header_index is None:
                continue

            enum_fields_index = next(
                (idx for idx in range(header_index, len(lines)) if lines[idx].startswith(r"\begin{DoxyEnumFields}")),
                None,
            )
            if enum_fields_index is None:
                continue

            enum_fields_end = next(
                (idx for idx in range(enum_fields_index, len(lines)) if lines[idx].startswith(r"\end{DoxyEnumFields}")),
                None,
            )
            if enum_fields_end is None:
                continue

            removals.append((enum_fields_index, enum_fields_end + 1))

            if any(
                line.startswith(r"\paragraph{Variants}") or line.startswith(r"\textbf{Variants:}\\")
                for line in lines[header_index:enum_fields_index]
            ):
                continue

            insertions.append((enum_fields_index, _variants_block(source_variants)))

    for start, end in reversed(removals):
        del lines[start:end]

    for insert_index, block in reversed(insertions):
        lines[insert_index:insert_index] = block

    return "\n".join(lines) + "\n"


def _normalize_file_tex(text: str, file_compound: ET.Element, preferred_refids_by_name: dict[str, str]) -> str:
    source_path = file_compound.find("location").attrib["file"]
    module_name = module_name_for_source_path(source_path)
    normalized = _normalize_tex_lines(text)
    normalized = _apply_source_declarations(normalized, file_compound)
    normalized = _simplify_enum_summary_lists(normalized)
    normalized = _inject_enum_variants(normalized, file_compound)
    normalized = _retarget_l0_symbol_links(normalized, preferred_refids_by_name)
    if module_name:
        normalized = _insert_after_index(
            normalized,
            rf"\textbf{{Module:}} \texttt{{{_escape_latex_texttt(module_name)}}}\par\medskip",
        )
    return normalized


def _normalize_symbol_tex(
    text: str,
    compounddef: ET.Element,
    preferred_refids_by_name: dict[str, str],
) -> str:
    normalized = _normalize_tex_lines(text)
    normalized = _normalize_public_attributes_section(normalized)
    normalized = _normalize_member_data_signatures(normalized)
    normalized = _apply_source_declarations(normalized, compounddef)
    normalized = _retarget_l0_symbol_links(normalized, preferred_refids_by_name)
    return normalized


def normalize_latex_site(xml_dir: Path, latex_dir: Path) -> None:
    """Normalize native Doxygen LaTeX output for L0 sources."""
    if not latex_dir.exists():
        return

    file_compounds_by_source: dict[str, ET.Element] = {}
    file_refids_by_source: dict[str, str] = {}
    preferred_refids_by_name: dict[str, str] = {}
    symbol_compounds: list[ET.Element] = []

    for xml_path in sorted(xml_dir.glob("*.xml")):
        if xml_path.name == "index.xml":
            continue
        root = ET.parse(xml_path).getroot()
        compounddef = root.find("compounddef")
        if compounddef is None:
            continue
        location = compounddef.find("location")
        source_path = location.attrib.get("file", "") if location is not None else ""
        if not source_path or Path(source_path).is_absolute() or Path(source_path).suffix not in {".l0", ".l1"}:
            continue
        kind = compounddef.attrib.get("kind", "")
        if kind == "file":
            file_compounds_by_source[source_path] = compounddef
            file_refids_by_source[source_path] = compounddef.attrib["id"]
            for section in compounddef.findall("sectiondef"):
                for memberdef in section.findall("memberdef"):
                    if memberdef.attrib.get("kind") == "enum":
                        name = memberdef.findtext("name", default="").strip()
                        refid = memberdef.attrib.get("id", "")
                        if name and refid:
                            preferred_refids_by_name.setdefault(name, refid)
        elif kind in {"struct", "union", "class"}:
            name = compounddef.findtext("compoundname", default="").strip()
            if name:
                preferred_refids_by_name.setdefault(name, compounddef.attrib["id"])
            symbol_compounds.append(compounddef)

    for source_path, file_compound in file_compounds_by_source.items():
        tex_path = latex_dir / f"{file_compound.attrib['id']}.tex"
        if not tex_path.exists():
            continue
        tex_path.write_text(
            _normalize_file_tex(tex_path.read_text(encoding="utf-8"), file_compound, preferred_refids_by_name),
            encoding="utf-8",
        )

    for compounddef in symbol_compounds:
        source_path = compounddef.find("location").attrib["file"]
        file_refid = file_refids_by_source.get(source_path)
        if not file_refid:
            continue
        tex_path = latex_dir / f"{compounddef.attrib['id']}.tex"
        if not tex_path.exists():
            continue
        tex_path.write_text(
            _normalize_symbol_tex(tex_path.read_text(encoding="utf-8"), compounddef, preferred_refids_by_name),
            encoding="utf-8",
        )

    refman_path = latex_dir / "refman.tex"
    if refman_path.exists():
        refman_path.write_text(
            _normalize_titlepage_front_matter(refman_path.read_text(encoding="utf-8")),
            encoding="utf-8",
        )

    for tex_path in sorted(latex_dir.glob("*.tex")):
        tex = tex_path.read_text(encoding="utf-8")
        tex = _normalize_prose_arrows(tex)
        tex = _normalize_l0_signature_links(tex)
        tex_path.write_text(tex, encoding="utf-8")
