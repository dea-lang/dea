# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Render Markdown API docs from Doxygen XML output."""

from __future__ import annotations

import html
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .l0_docgen_l0_helpers import extract_l0_enum_variants, extract_l0_member_declaration, module_name_for_source_path


def _heading_slug(value: str) -> str:
    """Return a PyCharm-compatible heading fragment slug."""
    normalized = value.lower().replace("`", "").replace(":", "")
    normalized = re.sub(r"[^a-z0-9_\-\s]+", "", normalized)
    normalized = re.sub(r"[\s\-]+", "-", normalized).strip("-")
    return normalized or "section"


def _compound_label(compounddef: ET.Element) -> str:
    name = compounddef.findtext("compoundname", default="").strip()
    return name or compounddef.attrib["id"]


def _compound_heading(compounddef: ET.Element) -> str:
    kind = compounddef.attrib["kind"].title()
    return f"{kind} `{_compound_label(compounddef)}`"


def _definition_symbol_name(definition: str) -> str:
    tokens = definition.split()
    if not tokens:
        return ""
    return tokens[-1].lstrip("*&").strip()


def _member_qualified_label(memberdef: ET.Element) -> str:
    qualified = memberdef.findtext("qualifiedname", default="").strip()
    if qualified:
        return qualified
    definition = memberdef.findtext("definition", default="").strip()
    if definition:
        candidate = _definition_symbol_name(definition)
        if candidate:
            return candidate
    return memberdef.findtext("name", default=memberdef.attrib["id"]).strip()


def _member_kind_label(memberdef: ET.Element) -> str:
    kind = memberdef.attrib.get("kind", "")
    if kind == "variable":
        type_text = _inner_text(memberdef.find("type")).strip()
        definition = memberdef.findtext("definition", default="").strip()
        if type_text == "type" or definition.startswith("type "):
            return "Type Alias"
    labels = {
        "function": "Function",
        "variable": "Variable",
        "enum": "Enum",
        "typedef": "Type Alias",
        "define": "Macro",
        "friend": "Friend",
        "property": "Property",
        "event": "Event",
        "signal": "Signal",
        "slot": "Slot",
        "prototype": "Prototype",
    }
    return labels.get(kind, "Symbol")


def _is_l0_compound(compounddef: ET.Element | None) -> bool:
    if compounddef is None:
        return False
    location = compounddef.find("location")
    source_path = location.attrib.get("file", "") if location is not None else ""
    return source_path.endswith(".l0")


def _member_heading(memberdef: ET.Element, owner: ET.Element | None = None) -> str:
    is_compound_member_data = (
        owner is not None
        and owner.attrib.get("kind") in {"struct", "class", "union"}
        and memberdef.attrib.get("kind") == "variable"
    )
    if is_compound_member_data and not _is_l0_compound(owner):
        return f"Member Data `{_member_qualified_label(memberdef)}`"
    if (
        owner is not None
        and _is_l0_compound(owner)
        and owner.attrib.get("kind") in {"struct", "class", "union"}
        and memberdef.attrib.get("kind") == "variable"
    ):
        owner_label = _compound_label(owner).split("::")[-1]
        field_name = memberdef.findtext("name", default=memberdef.attrib["id"]).strip()
        return f"{owner_label} Field `{field_name}`"
    return f"{_member_kind_label(memberdef)} `{_member_qualified_label(memberdef)}`"


def compound_anchor(compounddef: ET.Element) -> str:
    """Return a stable anchor for a compound."""
    return _heading_slug(_compound_heading(compounddef))


def member_anchor(memberdef: ET.Element, owner: ET.Element | None = None) -> str:
    """Return a stable anchor for a member."""
    return _heading_slug(_member_heading(memberdef, owner))


@dataclass(frozen=True)
class LinkTarget:
    """A rendered Markdown link target."""

    path: Path
    anchor: str


@dataclass(frozen=True)
class HtmlBrowseEntry:
    """An entry for the curated HTML browse pages."""

    title: str
    source_path: str
    url: str
    reference_links: list["HtmlReferenceLink"]


@dataclass(frozen=True)
class HtmlReferenceLink:
    """A dedicated Doxygen reference page reachable from a curated page."""

    label: str
    kind: str
    url: str


def _label_match_keys(label: str) -> list[str]:
    """Return possible label keys for cross-language symbol matching."""
    raw = label.strip().strip("`")
    keys: list[str] = []
    for key in (raw, raw.split("::")[-1], raw.split(".")[-1]):
        if key and key not in keys:
            keys.append(key)
    return keys


def _preferred_scope_prefix(current_page: Path) -> str | None:
    posix = current_page.as_posix()
    if posix.startswith("compiler/stage1_py/"):
        return "compiler/stage1_py/"
    if posix.startswith("compiler/stage2_l0/"):
        return "compiler/stage2_l0/"
    return None


def _stage_scope_prefix(path: Path) -> str | None:
    posix = path.as_posix()
    if posix.startswith("compiler/stage1_py/"):
        return "compiler/stage1_py/"
    if posix.startswith("compiler/stage2_l0/"):
        return "compiler/stage2_l0/"
    return None


def _resolve_stage1_label_target(
    target: LinkTarget | None,
    label: str,
    current_page: Path,
    stage1_label_targets: dict[str, LinkTarget] | None,
) -> LinkTarget | None:
    """Prefer same-scope symbol targets for ambiguous labels in scoped docs."""
    preferred_scope = _preferred_scope_prefix(current_page)
    if preferred_scope is None:
        return target
    if not stage1_label_targets:
        return target
    if target is not None and target.path.as_posix().startswith(preferred_scope):
        return target
    for key in _label_match_keys(label):
        candidate = stage1_label_targets.get(key)
        if candidate is not None:
            return candidate
    # Prevent Stage 2 docs from leaking Stage 1 symbol links when no Stage 2 match exists.
    if target is not None:
        target_scope = _stage_scope_prefix(target.path)
        if (
            preferred_scope == "compiler/stage2_l0/"
            and target_scope is not None
            and target_scope != preferred_scope
        ):
            return None
    return target


def _inner_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _ref_href(target: LinkTarget, current_page: Path) -> str:
    """Return a markdown href for a reference target."""
    if target.path == current_page:
        return f"#{target.anchor}"
    rel = os.path.relpath(target.path, start=current_page.parent).replace("\\", "/")
    return f"{rel}#{target.anchor}"


def _render_inline(
    element: ET.Element | None,
    ref_targets: dict[str, LinkTarget],
    current_page: Path,
    stage1_label_targets: dict[str, LinkTarget] | None = None,
) -> str:
    if element is None:
        return ""

    def render(node: ET.Element) -> str:
        out = node.text or ""
        for child in node:
            if child.tag == "ref":
                label = _inner_text(child)
                refid = child.attrib.get("refid", "")
                target = ref_targets.get(refid)
                target = _resolve_stage1_label_target(target, label, current_page, stage1_label_targets)
                if target is not None:
                    out += f"[{label}]({_ref_href(target, current_page)})"
                elif label:
                    out += f"`{label}`"
            elif child.tag == "computeroutput":
                if child.find(".//ref") is not None:
                    out += render(child)
                else:
                    out += f"`{_inner_text(child)}`"
            elif child.tag == "bold":
                out += f"**{_inner_text(child)}**"
            elif child.tag == "emphasis":
                out += f"*{_inner_text(child)}*"
            elif child.tag == "linebreak":
                out += "  \n"
            elif child.tag == "sp":
                out += " "
            else:
                out += render(child)
            out += child.tail or ""
        return out

    return render(element).strip()


def _extract_params(
    desc: ET.Element | None,
    ref_targets: dict[str, LinkTarget],
    current_page: Path,
    stage1_label_targets: dict[str, LinkTarget] | None = None,
) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if desc is None:
        return items
    for plist in desc.findall(".//parameterlist[@kind='param']"):
        for item in plist.findall("parameteritem"):
            name = item.findtext("parameternamelist/parametername", default="").strip()
            description = _render_inline(item.find("parameterdescription"), ref_targets, current_page, stage1_label_targets)
            items.append((name, description))
    return items


def _extract_returns(
    desc: ET.Element | None,
    ref_targets: dict[str, LinkTarget],
    current_page: Path,
    stage1_label_targets: dict[str, LinkTarget] | None = None,
) -> str:
    if desc is None:
        return ""
    sections = [
        _render_inline(section, ref_targets, current_page, stage1_label_targets)
        for section in desc.findall(".//simplesect[@kind='return']")
    ]
    return "\n\n".join(section for section in sections if section)


def _extract_body(
    desc: ET.Element | None,
    ref_targets: dict[str, LinkTarget],
    current_page: Path,
    stage1_label_targets: dict[str, LinkTarget] | None = None,
) -> str:
    if desc is None:
        return ""

    def normalize_l0_signature_lines(text: str) -> str:
        pattern = re.compile(
            r"extern\s+func\s+\[(?P<label>[^\]]+)\]\((?P<href>[^)]+)\)"
            r"(?P<args>\([^)]*\))?\s*->\s*(?P<ret>[^;\n]+);"
        )

        def replace(match: re.Match[str]) -> str:
            label = match.group("label").strip()
            args = (match.group("args") or "").strip()
            ret = match.group("ret").strip()
            if args and "(" not in label:
                label = f"{label}{args}"
            link_label = f"func {label} -> {ret}"
            return f"extern [{link_label}]({match.group('href')});"

        return pattern.sub(replace, text)

    def render_list(list_node: ET.Element, ordered: bool) -> list[str]:
        items: list[str] = []
        for item in list_node.findall("listitem"):
            item_blocks: list[str] = []
            for para in item.findall("para"):
                rendered = render_para(para)
                if rendered:
                    item_blocks.extend(rendered)
            text = " ".join(block.strip() for block in item_blocks if block.strip()).strip()
            if text:
                items.append(text)
        if not ordered:
            return [f"- {item}" for item in items]
        return [f"{index}. {item}" for index, item in enumerate(items, start=1)]

    def render_para(para: ET.Element) -> list[str]:
        blocks: list[str] = []
        fragments: list[str] = []

        def flush_paragraph() -> None:
            paragraph = " ".join(fragment.strip() for fragment in fragments if fragment.strip()).strip()
            if paragraph:
                blocks.append(paragraph)
            fragments.clear()

        if para.text and para.text.strip():
            fragments.append(para.text.strip())

        for child in para:
            if child.tag in {"parameterlist", "simplesect"}:
                if child.tail and child.tail.strip():
                    fragments.append(child.tail.strip())
                continue
            if child.tag == "programlisting":
                flush_paragraph()
                code = "\n".join("".join(codeline.itertext()) for codeline in child.findall("codeline"))
                if code.strip():
                    blocks.append(f"```text\n{code.rstrip()}\n```")
                continue
            if child.tag == "itemizedlist":
                flush_paragraph()
                blocks.extend(render_list(child, ordered=False))
                continue
            if child.tag == "orderedlist":
                flush_paragraph()
                blocks.extend(render_list(child, ordered=True))
                continue
            if child.tag == "ref":
                label = _inner_text(child)
                refid = child.attrib.get("refid", "")
                target = ref_targets.get(refid)
                target = _resolve_stage1_label_target(target, label, current_page, stage1_label_targets)
                if target is not None:
                    fragments.append(f"[{label}]({_ref_href(target, current_page)})")
                elif label:
                    fragments.append(f"`{label}`")
            else:
                rendered = _render_inline(child, ref_targets, current_page, stage1_label_targets)
                if rendered:
                    fragments.append(rendered)
            if child.tail and child.tail.strip():
                fragments.append(child.tail.strip())

        flush_paragraph()
        return blocks

    blocks: list[str] = []
    for para in desc.findall("para"):
        blocks.extend(render_para(para))
    return normalize_l0_signature_lines("\n\n".join(blocks))


def _extract_simplesects(
    desc: ET.Element | None,
    kind: str,
    ref_targets: dict[str, LinkTarget],
    current_page: Path,
    stage1_label_targets: dict[str, LinkTarget] | None = None,
) -> list[str]:
    if desc is None:
        return []
    return [
        rendered
        for rendered in (
            _render_inline(section, ref_targets, current_page, stage1_label_targets)
            for section in desc.findall(f".//simplesect[@kind='{kind}']")
        )
        if rendered
    ]


def _normalize_l0_type_text(type_text: str) -> str:
    text = " ".join(type_text.split())
    text = re.sub(r"\s*\*\s*", "*", text)
    return text


def _normalize_l0_signature_text(signature: str) -> str:
    text = " ".join(signature.split())
    text = re.sub(r":\s*", ": ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\(\s*", "(", text)
    text = re.sub(r"\s*\)", ")", text)
    text = re.sub(r"\s*->\s*", " -> ", text)
    text = re.sub(r"\s*\*\s*", "*", text)
    return text.strip()


def _sanitize_anonymous_type_text(type_text: str) -> str:
    text = " ".join(type_text.split())
    if "::@" not in text:
        return text
    if text.startswith("struct "):
        return "struct"
    if text.startswith("union "):
        return "union"
    return re.sub(r"::@\d+", "", text).strip()


def _member_bitfield(memberdef: ET.Element) -> str:
    bitfield = memberdef.findtext("bitfield", default="").strip()
    if not bitfield:
        return ""
    return f": {bitfield}"


def _structured_l0_function_signature(memberdef: ET.Element) -> str | None:
    name = memberdef.findtext("name", default="").strip()
    return_type = _sanitize_anonymous_type_text(_normalize_l0_type_text(_inner_text(memberdef.find("type"))))
    if not name or not return_type or return_type == "func":
        return None

    rendered_params: list[str] = []
    for param in memberdef.findall("param"):
        param_type = _sanitize_anonymous_type_text(_normalize_l0_type_text(_inner_text(param.find("type"))))
        param_name = param.findtext("declname", default="").strip()
        if param_name and param_type:
            rendered_params.append(f"{param_name}: {param_type}")
        elif param_name:
            rendered_params.append(param_name)
        elif param_type:
            rendered_params.append(param_type)

    prefix = "extern func" if memberdef.attrib.get("extern") == "yes" else "func"
    return _normalize_l0_signature_text(f"{prefix} {name}({', '.join(rendered_params)}) -> {return_type}")


def _member_signature(memberdef: ET.Element, owner: ET.Element | None = None) -> str:
    location = memberdef.find("location")
    source_path = location.attrib.get("file", "") if location is not None else ""
    is_l0 = Path(source_path).suffix == ".l0"
    if is_l0:
        source_declaration = extract_l0_member_declaration(memberdef)
        if source_declaration is not None:
            return source_declaration
    if memberdef.attrib.get("kind") == "variable":
        definition = memberdef.findtext("definition", default="").strip()
        initializer = memberdef.findtext("initializer", default="").strip()
        if _member_kind_label(memberdef) == "Type Alias":
            signature = definition or memberdef.findtext("name", default="")
            if initializer:
                signature = f"{signature} {initializer}".strip()
            return signature
        type_text = _sanitize_anonymous_type_text(_normalize_l0_type_text(_inner_text(memberdef.find("type"))))
        name = memberdef.findtext("name", default="").strip()
        bitfield_suffix = _member_bitfield(memberdef)
        is_compound_member_data = (
            owner is not None
            and owner.attrib.get("kind") in {"struct", "class", "union"}
            and memberdef.attrib.get("kind") == "variable"
        )
        if is_compound_member_data:
            if _is_l0_compound(owner):
                if name and type_text:
                    return f"{name}: {type_text}"
            else:
                if bitfield_suffix and name in {
                    "auto",
                    "bool",
                    "char",
                    "const",
                    "double",
                    "enum",
                    "extern",
                    "float",
                    "inline",
                    "int",
                    "long",
                    "register",
                    "restrict",
                    "short",
                    "signed",
                    "static",
                    "struct",
                    "typedef",
                    "union",
                    "unsigned",
                    "void",
                    "volatile",
                }:
                    type_text = f"{type_text} {name}".strip()
                    name = ""
                if type_text and name:
                    signature = f"{type_text} {name}"
                else:
                    signature = type_text or definition or memberdef.findtext("name", default="")
                if bitfield_suffix:
                    signature = f"{signature}{bitfield_suffix}"
                return signature
        qualified = memberdef.findtext("qualifiedname", default="").strip()
        if "::" in qualified and is_l0:
            if name and type_text:
                return f"{name}: {type_text}"
    if is_l0 and memberdef.attrib.get("kind") == "function":
        structured_signature = _structured_l0_function_signature(memberdef)
        if structured_signature is not None:
            return structured_signature
    definition = memberdef.findtext("definition", default="").strip()
    args = memberdef.findtext("argsstring", default="").strip()
    if definition and args:
        signature = f"{definition}{args}"
    else:
        signature = definition or args or memberdef.findtext("name", default="")
    if is_l0:
        normalized = _normalize_l0_signature_text(signature)
        if (
            memberdef.attrib.get("kind") == "function"
            and memberdef.attrib.get("extern") == "yes"
            and normalized.startswith("func ")
        ):
            normalized = f"extern {normalized}"
        return normalized
    return signature


def _render_member(
    memberdef: ET.Element,
    heading_level: int,
    ref_targets: dict[str, LinkTarget],
    current_page: Path,
    stage1_label_targets: dict[str, LinkTarget] | None = None,
    owner: ET.Element | None = None,
) -> str:
    anchor = member_anchor(memberdef, owner)
    heading = _member_heading(memberdef, owner)
    name = memberdef.findtext("name", default=memberdef.attrib["id"])
    signature = _member_signature(memberdef, owner)
    brief = _extract_body(memberdef.find("briefdescription"), ref_targets, current_page, stage1_label_targets)
    detail = _extract_body(memberdef.find("detaileddescription"), ref_targets, current_page, stage1_label_targets)
    params = _extract_params(memberdef.find("detaileddescription"), ref_targets, current_page, stage1_label_targets)
    returns = _extract_returns(memberdef.find("detaileddescription"), ref_targets, current_page, stage1_label_targets)
    see_also = _extract_simplesects(
        memberdef.find("detaileddescription"), "see", ref_targets, current_page, stage1_label_targets
    )
    enum_values: list[str] = []
    if memberdef.attrib.get("kind") == "enum":
        enum_values = extract_l0_enum_variants(memberdef)
        if not enum_values:
            enum_values = [enumvalue.findtext("name", default="").strip() for enumvalue in memberdef.findall("enumvalue")]

    parts = [f'<a id="{anchor}"></a>', f'{"#" * heading_level} {heading}', "", "```text", signature or name, "```"]
    if brief:
        parts.extend(["", brief])
    if detail and detail != brief:
        parts.extend(["", detail])
    if enum_values:
        parts.extend(["", "Variants:"])
        parts.extend(f"- `{value}`" for value in enum_values if value)
    if params:
        parts.extend(["", "Parameters:"])
        parts.extend(f"- `{param}`: {description}" for param, description in params)
    if returns:
        parts.extend(["", f"Returns: {returns}"])
    if see_also:
        parts.extend(["", "See also:"])
        parts.extend(f"- {item}" for item in see_also)
    return "\n".join(parts).rstrip()


def _render_compound_section(
    compounddef: ET.Element,
    heading_level: int,
    ref_targets: dict[str, LinkTarget],
    current_page: Path,
    stage1_label_targets: dict[str, LinkTarget] | None = None,
) -> str:
    heading = _compound_heading(compounddef)
    parts = [
        f'<a id="{compound_anchor(compounddef)}"></a>',
        f'{"#" * heading_level} {heading}',
    ]
    body = _extract_body(compounddef.find("briefdescription"), ref_targets, current_page, stage1_label_targets)
    detail = _extract_body(compounddef.find("detaileddescription"), ref_targets, current_page, stage1_label_targets)
    see_also = _extract_simplesects(
        compounddef.find("detaileddescription"), "see", ref_targets, current_page, stage1_label_targets
    )
    if body:
        parts.extend(["", body])
    if detail and detail != body:
        parts.extend(["", detail])
    if see_also:
        parts.extend(["", "See also:"])
        parts.extend(f"- {item}" for item in see_also)

    members: list[str] = []
    for section in compounddef.findall("sectiondef"):
        for memberdef in section.findall("memberdef"):
            members.append(
                _render_member(
                    memberdef,
                    heading_level + 1,
                    ref_targets,
                    current_page,
                    stage1_label_targets,
                    owner=compounddef,
                )
            )
    if members:
        parts.extend(["", *members])
    return "\n".join(parts).rstrip()


def _relative_page_path(source_path: str) -> Path:
    return Path(source_path).with_suffix(".md")


def _display_language(source_path: str, raw_language: str) -> str:
    path = Path(source_path)
    if path.suffix == ".l0":
        return "Dea/L0"
    if path.suffix == ".py":
        return "Python"
    if path.suffix == ".h":
        return "C"
    return raw_language or "Unknown"


def _source_struct_ranges(source_path: str) -> list[tuple[int, int]]:
    path = Path(source_path)
    if path.is_absolute() or not path.exists():
        return []

    struct_start_re = re.compile(r"^\s*struct\s+[A-Za-z_][A-Za-z0-9_]*\s*\{")
    ranges: list[tuple[int, int]] = []
    active_start: int | None = None
    depth = 0

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if active_start is None and struct_start_re.match(line):
            active_start = line_no
            depth = line.count("{") - line.count("}")
            if depth <= 0:
                ranges.append((active_start, line_no))
                active_start = None
                depth = 0
            continue

        if active_start is not None:
            depth += line.count("{")
            depth -= line.count("}")
            if depth <= 0:
                ranges.append((active_start, line_no))
                active_start = None
                depth = 0

    return ranges


def _line_range(compounddef: ET.Element) -> tuple[int, int] | None:
    location = compounddef.find("location")
    if location is None:
        return None
    start_text = location.attrib.get("bodystart") or location.attrib.get("line")
    end_text = location.attrib.get("bodyend") or location.attrib.get("line")
    if not start_text or not end_text:
        return None
    try:
        start = int(start_text)
        end = int(end_text)
    except ValueError:
        return None
    if start <= 0 or end < start:
        return None
    return start, end


def _member_line(memberdef: ET.Element) -> int | None:
    location = memberdef.find("location")
    if location is None:
        return None
    line_text = location.attrib.get("line")
    if not line_text:
        return None
    try:
        line = int(line_text)
    except ValueError:
        return None
    return line if line > 0 else None


def _file_level_memberdefs(file_compound: ET.Element, compounds: dict[str, ET.Element]) -> list[ET.Element]:
    file_location = file_compound.find("location")
    file_path = file_location.attrib.get("file", "") if file_location is not None else ""
    nested_ranges: list[tuple[int, int]] = list(_source_struct_ranges(file_path))
    nested_member_names: set[str] = set()
    nested_compounds: list[ET.Element] = []
    seen_ids: set[str] = set()

    for tag in ["innernamespace", "innerclass", "innerstruct", "innerunion"]:
        for inner in file_compound.findall(tag):
            target = compounds.get(inner.attrib.get("refid", ""))
            if target is None:
                continue
            target_id = target.attrib.get("id", "")
            if target_id in seen_ids:
                continue
            seen_ids.add(target_id)
            nested_compounds.append(target)

    if file_path:
        for target in compounds.values():
            if target.attrib.get("kind") not in {"namespace", "class", "struct", "union"}:
                continue
            location = target.find("location")
            if location is None or location.attrib.get("file", "") != file_path:
                continue
            target_id = target.attrib.get("id", "")
            if target_id == file_compound.attrib.get("id", "") or target_id in seen_ids:
                continue
            seen_ids.add(target_id)
            nested_compounds.append(target)

    for target in nested_compounds:
        line_range = _line_range(target)
        if line_range is not None:
            nested_ranges.append(line_range)
        for section in target.findall("sectiondef"):
            for memberdef in section.findall("memberdef"):
                nested_member_names.add(memberdef.findtext("name", default=""))

    members: list[ET.Element] = []
    for section in file_compound.findall("sectiondef"):
        for memberdef in section.findall("memberdef"):
            line = _member_line(memberdef)
            if line is not None and any(start <= line <= end for start, end in nested_ranges):
                if memberdef.attrib.get("kind") == "variable" and memberdef.findtext("type", default="").strip() != "type":
                    continue
            if memberdef.attrib.get("kind") == "variable":
                name = memberdef.findtext("name", default="")
                if name in nested_member_names and memberdef.findtext("type", default="").strip() != "type":
                    continue
            members.append(memberdef)
    return members


def _build_scope_label_targets(compounds: dict[str, ET.Element], scope_prefix: str) -> dict[str, LinkTarget]:
    """Build unique same-scope label-to-target mappings for ambiguous cross-refs."""
    candidates: dict[str, set[LinkTarget]] = {}
    for compounddef in compounds.values():
        location = compounddef.find("location")
        source_path = location.attrib.get("file", "") if location is not None else ""
        if not source_path.startswith(scope_prefix):
            continue
        page_path = _relative_page_path(source_path)
        target = LinkTarget(page_path, compound_anchor(compounddef))
        label = _compound_label(compounddef)
        for key in _label_match_keys(label):
            candidates.setdefault(key, set()).add(target)
    return {key: next(iter(values)) for key, values in candidates.items() if len(values) == 1}


def _build_scope_compound_id_targets(compounds: dict[str, ET.Element], scope_prefix: str) -> dict[str, str]:
    """Build unique same-scope label-to-compound-id mappings for raw HTML rewrites."""
    candidates: dict[str, set[str]] = {}
    for compounddef in compounds.values():
        location = compounddef.find("location")
        source_path = location.attrib.get("file", "") if location is not None else ""
        if not source_path.startswith(scope_prefix):
            continue
        compound_id = compounddef.attrib.get("id", "")
        if not compound_id:
            continue
        label = _compound_label(compounddef)
        for key in _label_match_keys(label):
            candidates.setdefault(key, set()).add(compound_id)
    return {key: next(iter(values)) for key, values in candidates.items() if len(values) == 1}


def render_markdown_site(xml_dir: Path, output_dir: Path, templates_dir: Path, *, stage: str = "all") -> None:
    """Render a Markdown API site from Doxygen XML."""
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    file_template = env.get_template("markdown_file.md.j2")
    index_template = env.get_template("markdown_index.md.j2")

    compounds: dict[str, ET.Element] = {}
    file_compounds: list[ET.Element] = []
    ref_targets: dict[str, LinkTarget] = {}

    for xml_path in sorted(xml_dir.glob("*.xml")):
        if xml_path.name == "index.xml":
            continue
        root = ET.parse(xml_path).getroot()
        compounddef = root.find("compounddef")
        if compounddef is None:
            continue
        compounds[compounddef.attrib["id"]] = compounddef
        location = compounddef.find("location")
        source_path = location.attrib.get("file") if location is not None else ""
        if source_path:
            page_path = _relative_page_path(source_path)
            ref_targets[compounddef.attrib["id"]] = LinkTarget(page_path, compound_anchor(compounddef))
            for memberdef in compounddef.findall(".//memberdef"):
                ref_targets[memberdef.attrib["id"]] = LinkTarget(page_path, member_anchor(memberdef, owner=compounddef))
        if compounddef.attrib["kind"] == "file" and source_path and not source_path.endswith("docs-mainpage.md"):
            file_compounds.append(compounddef)

    stage1_label_targets = _build_scope_label_targets(compounds, "compiler/stage1_py/")
    stage2_label_targets = _build_scope_label_targets(compounds, "compiler/stage2_l0/")

    stage1_pages: list[dict[str, str]] = []
    stage2_pages: list[dict[str, str]] = []
    shared_pages: list[dict[str, str]] = []

    for compounddef in file_compounds:
        location = compounddef.find("location")
        if location is None:
            continue
        source_path = location.attrib["file"]
        current_page = _relative_page_path(source_path)
        page_path = output_dir / current_page
        page_path.parent.mkdir(parents=True, exist_ok=True)
        preferred_label_targets: dict[str, LinkTarget] | None = None
        if source_path.startswith("compiler/stage1_py/"):
            preferred_label_targets = stage1_label_targets
        elif source_path.startswith("compiler/stage2_l0/"):
            preferred_label_targets = stage2_label_targets

        includes = [include.text or "" for include in compounddef.findall("includes")]
        toc: list[dict[str, str]] = []
        body_parts: list[str] = []

        for memberdef in _file_level_memberdefs(compounddef, compounds):
            toc.append(
                {
                    "label": memberdef.findtext("name", default=memberdef.attrib["id"]),
                    "anchor": member_anchor(memberdef, owner=compounddef),
                }
            )
            body_parts.append(
                _render_member(
                    memberdef,
                    2,
                    ref_targets,
                    current_page,
                    preferred_label_targets,
                    owner=compounddef,
                )
            )

        for tag in ["innernamespace", "innerclass", "innerstruct"]:
            for inner in compounddef.findall(tag):
                refid = inner.attrib.get("refid", "")
                target = compounds.get(refid)
                if target is None:
                    continue
                label = target.findtext("compoundname", default=refid)
                toc.append({"label": label, "anchor": compound_anchor(target)})
                body_parts.append(_render_compound_section(target, 2, ref_targets, current_page, preferred_label_targets))

        summary = _extract_body(compounddef.find("briefdescription"), ref_targets, current_page, preferred_label_targets)
        detail = _extract_body(compounddef.find("detaileddescription"), ref_targets, current_page, preferred_label_targets)
        if detail and detail != summary:
            summary = f"{summary}\n\n{detail}".strip()

        page_content = file_template.render(
            title=source_path,
            module_name=module_name_for_source_path(source_path),
            source_path=source_path,
            language=_display_language(source_path, compounddef.attrib.get("language", "Unknown")),
            summary=summary,
            includes=includes,
            toc=toc,
            body="\n\n".join(part for part in body_parts if part),
        ).strip() + "\n"
        page_path.write_text(page_content, encoding="utf-8")

        page_entry = {"href": current_page.as_posix(), "label": source_path}
        if page_entry["href"].startswith("compiler/stage1_py/"):
            stage1_pages.append(page_entry)
        elif page_entry["href"].startswith("compiler/stage2_l0/"):
            stage2_pages.append(page_entry)
        else:
            shared_pages.append(page_entry)

    index_path = output_dir / "index.md"
    index_path.write_text(
        index_template.render(
            stage=stage,
            stage1=sorted(stage1_pages, key=lambda page: page["href"]),
            stage2=sorted(stage2_pages, key=lambda page: page["href"]),
            shared=sorted(shared_pages, key=lambda page: page["href"]),
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _markdown_title(markdown_text: str) -> str:
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "API Page"


def _markdown_source_path(markdown_text: str) -> str | None:
    for line in markdown_text.splitlines():
        match = re.match(r"^Source:\s+`([^`]+)`", line.strip())
        if match:
            return match.group(1)
    return None


def _markdown_without_title(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            body_start = index + 1
            while body_start < len(lines) and not lines[body_start].strip():
                body_start += 1
            return "\n".join(lines[body_start:])
    return markdown_text


def _inline_markdown_to_html(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda match: f'<a href="{html.escape(match.group(2).replace(".md", ".html"), quote=True)}">{match.group(1)}</a>',
        escaped,
    )
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    return escaped


def _markdown_to_html(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    output: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith("<a ") and stripped.endswith("</a>"):
            output.append(stripped)
            index += 1
            continue

        if stripped.startswith("```"):
            index += 1
            code_lines: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            output.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
            index += 1
            continue

        if stripped.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(lines[index].strip()[2:])
                index += 1
            output.append("<ul>")
            output.extend(f"<li>{_inline_markdown_to_html(item)}</li>" for item in items)
            output.append("</ul>")
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            output.append(f"<h{level}>{_inline_markdown_to_html(heading_match.group(2))}</h{level}>")
            index += 1
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate or candidate.startswith("```") or candidate.startswith("- ") or candidate.startswith("<a "):
                break
            if re.match(r"^(#{1,6})\s+", candidate):
                break
            paragraph_lines.append(candidate)
            index += 1
        output.append(f"<p>{_inline_markdown_to_html(' '.join(paragraph_lines))}</p>")

    return "\n".join(output)


def _markdown_page_to_html_path(markdown_root: Path, markdown_path: Path, html_root: Path) -> Path:
    return html_root / "api" / markdown_path.relative_to(markdown_root).with_suffix(".html")


def _relative_href(page_path: Path, target_path: Path) -> str:
    return os.path.relpath(target_path, start=page_path.parent).replace("\\", "/")


def _reference_kind(tag: str, refid: str, target_compound: ET.Element | None = None) -> str:
    compound_kind = target_compound.attrib.get("kind", "") if target_compound is not None else ""
    if compound_kind == "struct":
        return "Struct"
    if compound_kind == "class":
        return "Class"
    if compound_kind == "union":
        return "Union"
    if refid.startswith("struct"):
        return "Struct"
    if refid.startswith("class"):
        return "Class"
    if refid.startswith("union"):
        return "Union"
    kind_labels = {"innerclass": "Class", "innerstruct": "Struct", "innerunion": "Union"}
    return kind_labels[tag]


def _collect_reference_pages(xml_dir: Path, markdown_root: Path, html_root: Path) -> dict[str, list[HtmlReferenceLink]]:
    page_refs: dict[str, list[HtmlReferenceLink]] = {}
    compounds_by_id = _collect_compounds_by_id(xml_dir)

    for xml_path in sorted(xml_dir.glob("*.xml")):
        if xml_path.name == "index.xml":
            continue
        root = ET.parse(xml_path).getroot()
        compounddef = root.find("compounddef")
        if compounddef is None or compounddef.attrib.get("kind") != "file":
            continue

        location = compounddef.find("location")
        if location is None or "file" not in location.attrib:
            continue

        source_path = location.attrib["file"]
        if Path(source_path).is_absolute():
            continue

        markdown_path = markdown_root / Path(source_path).with_suffix(".md")
        if not markdown_path.exists():
            continue

        page_key = markdown_path.relative_to(markdown_root).as_posix()
        page_html = _markdown_page_to_html_path(markdown_root, markdown_path, html_root)

        refs: list[HtmlReferenceLink] = []
        for tag in ["innerclass", "innerstruct", "innerunion"]:
            for inner in compounddef.findall(tag):
                refid = inner.attrib.get("refid", "")
                if not refid:
                    continue
                target = html_root / f"{refid}.html"
                if not target.exists():
                    continue
                refs.append(
                    HtmlReferenceLink(
                        label=(inner.text or refid).strip(),
                        kind=_reference_kind(tag, refid, compounds_by_id.get(refid)),
                        url=target.relative_to(html_root).as_posix(),
                    )
                )

        refs.sort(key=lambda item: (item.kind, item.label))
        if refs:
            page_refs[page_key] = refs

    return page_refs


def _collect_file_compounds(xml_dir: Path) -> dict[str, ET.Element]:
    compounds: dict[str, ET.Element] = {}
    for xml_path in sorted(xml_dir.glob("*.xml")):
        if xml_path.name == "index.xml":
            continue
        root = ET.parse(xml_path).getroot()
        compounddef = root.find("compounddef")
        if compounddef is None or compounddef.attrib.get("kind") != "file":
            continue
        location = compounddef.find("location")
        if location is None or "file" not in location.attrib:
            continue
        source_path = location.attrib["file"]
        if Path(source_path).is_absolute():
            continue
        compounds[Path(source_path).with_suffix(".md").as_posix()] = compounddef
    return compounds


def _collect_compounds_by_id(xml_dir: Path) -> dict[str, ET.Element]:
    compounds: dict[str, ET.Element] = {}
    for xml_path in sorted(xml_dir.glob("*.xml")):
        if xml_path.name == "index.xml":
            continue
        root = ET.parse(xml_path).getroot()
        compounddef = root.find("compounddef")
        if compounddef is None:
            continue
        compounds[compounddef.attrib["id"]] = compounddef
    return compounds


def _normalize_one_line(text: str) -> str:
    return " ".join(text.split())


def _build_stage1_hub_markdown(
    rel: Path,
    compounddef: ET.Element,
    compounds_by_id: dict[str, ET.Element],
) -> str:
    current_page = rel
    summary = _extract_body(compounddef.find("briefdescription"), {}, current_page)
    detail = _extract_body(compounddef.find("detaileddescription"), {}, current_page)
    if detail and detail != summary:
        summary = f"{summary}\n\n{detail}".strip()

    parts = [
        f"# {compounddef.find('location').attrib['file']}",
        "",
        f"Source: `{compounddef.find('location').attrib['file']}`",
        f"Language: `{_display_language(compounddef.find('location').attrib['file'], compounddef.attrib.get('language', 'Unknown'))}`",
    ]
    if summary:
        parts.extend(["", summary])

    members: list[str] = []
    seen_members: set[str] = set()

    def add_members(owner: ET.Element) -> None:
        for section in owner.findall("sectiondef"):
            for memberdef in section.findall("memberdef"):
                member_id = memberdef.attrib.get("id", "")
                if member_id and member_id in seen_members:
                    continue
                if member_id:
                    seen_members.add(member_id)
                name = memberdef.findtext("name", default=memberdef.attrib.get("id", "symbol"))
                brief = _normalize_one_line(_extract_body(memberdef.find("briefdescription"), {}, current_page))
                signature = _normalize_one_line(_member_signature(memberdef))
                item = f"- `{name}`"
                if signature and signature != name:
                    item += f": `{signature}`"
                if brief:
                    item += f" - {brief}"
                members.append(item)

    add_members(compounddef)
    for inner in compounddef.findall("innernamespace"):
        refid = inner.attrib.get("refid", "")
        target = compounds_by_id.get(refid)
        if target is not None:
            add_members(target)

    if members:
        parts.extend(["", "## Module Members", "", *members])

    return "\n".join(parts).rstrip() + "\n"


def _collect_browse_entries(
    markdown_root: Path,
    html_root: Path,
    page_refs: dict[str, list[HtmlReferenceLink]],
) -> dict[str, list[HtmlBrowseEntry]]:
    groups: dict[str, list[HtmlBrowseEntry]] = {"stage1": [], "stage2": [], "shared": []}

    for markdown_path in sorted(markdown_root.rglob("*.md")):
        if markdown_path.name == "index.md":
            continue
        rel = markdown_path.relative_to(markdown_root)
        markdown_text = markdown_path.read_text(encoding="utf-8")
        title = _markdown_title(markdown_text)
        source_path = _markdown_source_path(markdown_text) or rel.with_suffix("").as_posix()
        target = _markdown_page_to_html_path(markdown_root, markdown_path, html_root)
        entry = HtmlBrowseEntry(
            title=title,
            source_path=source_path,
            url=target.relative_to(html_root).as_posix(),
            reference_links=page_refs.get(rel.as_posix(), []),
        )
        rel_posix = rel.as_posix()
        if rel_posix.startswith("compiler/stage1_py/"):
            groups["stage1"].append(entry)
        elif rel_posix.startswith("compiler/stage2_l0/"):
            groups["stage2"].append(entry)
        elif rel_posix.startswith("compiler/shared/"):
            groups["shared"].append(entry)
    return groups


def render_raw_reference_backlinks(xml_dir: Path, markdown_root: Path, html_root: Path) -> None:
    """Add backlinks from raw Doxygen symbol pages to curated source overviews."""
    compounds_by_id = _collect_compounds_by_id(xml_dir)
    stage1_ids = _build_scope_compound_id_targets(compounds_by_id, "compiler/stage1_py/")
    stage2_ids = _build_scope_compound_id_targets(compounds_by_id, "compiler/stage2_l0/")

    for xml_path in sorted(xml_dir.glob("*.xml")):
        if xml_path.name == "index.xml":
            continue
        root = ET.parse(xml_path).getroot()
        compounddef = root.find("compounddef")
        if compounddef is None or compounddef.attrib.get("kind") not in {"class", "struct", "union"}:
            continue

        location = compounddef.find("location")
        if location is None or "file" not in location.attrib:
            continue
        source_path = location.attrib["file"]
        if Path(source_path).is_absolute():
            continue

        markdown_path = markdown_root / Path(source_path).with_suffix(".md")
        if not markdown_path.exists():
            continue

        raw_html_path = html_root / f"{compounddef.attrib['id']}.html"
        if not raw_html_path.exists():
            continue

        curated_html_path = _markdown_page_to_html_path(markdown_root, markdown_path, html_root)
        if not curated_html_path.exists():
            continue

        href = _relative_href(raw_html_path, curated_html_path)
        href += f"#{compound_anchor(compounddef)}"
        source_name = Path(source_path).name
        module_name = module_name_for_source_path(source_path) or Path(source_path).stem
        backlink = (
            f'<p>Defined in module <code>{html.escape(module_name)}</code> '
            f'(<a href="{html.escape(href)}">{html.escape(source_name)}</a>).</p>'
        )

        original_content = raw_html_path.read_text(encoding="utf-8")
        content = original_content

        preferred_scope = _preferred_scope_prefix(Path(source_path).with_suffix(".md"))
        preferred_ids: dict[str, str] | None = None
        if preferred_scope == "compiler/stage1_py/":
            preferred_ids = stage1_ids
        elif preferred_scope == "compiler/stage2_l0/":
            preferred_ids = stage2_ids

        if preferred_ids:
            link_pattern = re.compile(r'<a href="([^"]+)" class="m-doc">([^<]+)</a>')

            def rewrite_link(match: re.Match[str]) -> str:
                href = match.group(1)
                label = html.unescape(match.group(2))
                target_file, sep, fragment = href.partition("#")
                if "/" in target_file or not target_file.endswith(".html"):
                    return match.group(0)
                target_id = Path(target_file).stem
                target_compound = compounds_by_id.get(target_id)
                target_scope = None
                if target_compound is not None:
                    target_location = target_compound.find("location")
                    target_source = target_location.attrib.get("file", "") if target_location is not None else ""
                    target_scope = _preferred_scope_prefix(Path(target_source).with_suffix(".md"))
                if target_scope == preferred_scope:
                    return match.group(0)
                for key in _label_match_keys(label):
                    candidate_id = preferred_ids.get(key)
                    if candidate_id and candidate_id != target_id:
                        candidate_href = f"{candidate_id}.html"
                        if sep:
                            candidate_href += f"#{fragment}"
                        return f'<a href="{candidate_href}" class="m-doc">{match.group(2)}</a>'
                return match.group(0)

            content = link_pattern.sub(rewrite_link, content)

        if backlink in content:
            if content != original_content:
                raw_html_path.write_text(content, encoding="utf-8")
            continue

        marker = "</h1>"
        insert_at = content.find(marker)
        if insert_at == -1:
            continue

        updated = content[: insert_at + len(marker)] + "\n        " + backlink + content[insert_at + len(marker) :]
        raw_html_path.write_text(updated, encoding="utf-8")


def _collect_file_compound_targets(xml_dir: Path, markdown_root: Path, html_root: Path) -> dict[str, Path]:
    targets: dict[str, Path] = {}
    for xml_path in sorted(xml_dir.glob("*.xml")):
        if xml_path.name == "index.xml":
            continue
        root = ET.parse(xml_path).getroot()
        compounddef = root.find("compounddef")
        if compounddef is None or compounddef.attrib.get("kind") != "file":
            continue
        location = compounddef.find("location")
        if location is None or "file" not in location.attrib:
            continue
        source_path = location.attrib["file"]
        if Path(source_path).is_absolute():
            continue
        markdown_path = markdown_root / Path(source_path).with_suffix(".md")
        if not markdown_path.exists():
            continue
        targets[compounddef.attrib["id"]] = _markdown_page_to_html_path(markdown_root, markdown_path, html_root)
    return targets


def _scope_hub_target(source_path: str, html_root: Path) -> Path | None:
    normalized = source_path.replace("\\", "/").rstrip("/")
    if normalized.startswith("compiler/stage1_py/"):
        return html_root / "stage1.html"
    if normalized.startswith("compiler/stage2_l0/"):
        return html_root / "stage2.html"
    if normalized.startswith("compiler/shared/"):
        return html_root / "shared.html"
    return None


def rewrite_and_prune_raw_html_surface(xml_dir: Path, markdown_root: Path, html_root: Path) -> None:
    """Retarget raw symbol links to curated pages and prune raw hierarchy pages."""
    file_targets = _collect_file_compound_targets(xml_dir, markdown_root, html_root)

    file_link_pattern = re.compile(r'href="(?P<target>[A-Za-z0-9_]+)\.html(?:#[^"]*)?"')

    for raw_html_path in sorted(html_root.glob("*.html")):
        content = raw_html_path.read_text(encoding="utf-8")

        def replace_link(match: re.Match[str]) -> str:
            target_id = match.group("target")
            target = file_targets.get(target_id)
            if target is None:
                return match.group(0)
            return f'href="{html.escape(_relative_href(raw_html_path, target), quote=True)}"'

        rewritten = file_link_pattern.sub(replace_link, content)
        if rewritten != content:
            raw_html_path.write_text(rewritten, encoding="utf-8")

    dir_ids: set[str] = set()
    for xml_path in sorted(xml_dir.glob("*.xml")):
        if xml_path.name == "index.xml":
            continue
        root = ET.parse(xml_path).getroot()
        compounddef = root.find("compounddef")
        if compounddef is None:
            continue
        kind = compounddef.attrib.get("kind")
        if kind == "dir":
            dir_ids.add(compounddef.attrib["id"])

    for file_id in file_targets:
        raw_file_page = html_root / f"{file_id}.html"
        if raw_file_page.exists():
            raw_file_page.unlink()

    for dir_id in dir_ids:
        raw_dir_page = html_root / f"{dir_id}.html"
        if raw_dir_page.exists():
            raw_dir_page.unlink()

    for top_level in ("files.html", "dirs.html"):
        top_level_path = html_root / top_level
        if top_level_path.exists():
            top_level_path.unlink()


def normalize_search_result_urls(html_root: Path) -> None:
    """Patch m.css search output so relative result URLs work from nested pages."""
    search_js_path = html_root / "search-v2.js"
    if not search_js_path.exists():
        return

    content = search_js_path.read_text(encoding="utf-8")
    updated = content

    old_href = 'href="\' + results[i].url + \'"'
    new_href = 'href="\' + this.resolveResultUrl(results[i].url) + \'"'
    if new_href not in updated and old_href in updated:
        updated = updated.replace(old_href, new_href, 1)

    helper_marker = "resolveResultUrl: function(url) {"
    render_marker = "    renderResults: /* istanbul ignore next */ function(resultsSuggestedTabAutocompletion) {"
    helper_block = (
        "    resolveResultUrl: function(url) {\n"
        "        if(!url || url[0] == '#' || url[0] == '/' || /^[A-Za-z][A-Za-z0-9+.-]*:/.test(url))\n"
        "            return url;\n"
        "\n"
        "        let scripts = document.getElementsByTagName('script');\n"
        "        for(let i = scripts.length - 1; i >= 0; --i) {\n"
        "            let src = scripts[i].src || scripts[i].getAttribute('src');\n"
        "            if(src && /(?:^|\\/)search-v[0-9]+\\.js(?:[?#].*)?$/.test(src))\n"
        "                return new URL(url, src).href;\n"
        "        }\n"
        "\n"
        "        return new URL(url, window.location.href).href;\n"
        "    },\n"
        "\n"
    )
    if helper_marker not in updated and render_marker in updated:
        updated = updated.replace(render_marker, helper_block + render_marker, 1)

    if new_href not in updated or helper_marker not in updated:
        raise RuntimeError(
            "failed to patch search-v2.js for root-normalized result URLs; "
            "m.css output format likely changed"
        )

    if updated != content:
        search_js_path.write_text(updated, encoding="utf-8")


def render_curated_html_site(xml_dir: Path, markdown_root: Path, html_root: Path, templates_dir: Path, *, stage: str = "all") -> None:
    """Render curated HTML browse pages and HTML equivalents of generated Markdown."""
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    env.globals.update(stage=stage)
    page_template = env.get_template("html_api_page.j2")
    group_template = env.get_template("html_api_group.j2")
    page_refs = _collect_reference_pages(xml_dir, markdown_root, html_root)
    file_compounds = _collect_file_compounds(xml_dir)
    compounds_by_id = _collect_compounds_by_id(xml_dir)

    for markdown_path in sorted(markdown_root.rglob("*.md")):
        if markdown_path.name == "index.md":
            continue
        html_path = _markdown_page_to_html_path(markdown_root, markdown_path, html_root)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_text = markdown_path.read_text(encoding="utf-8")
        rel = markdown_path.relative_to(markdown_root)
        source_path = _markdown_source_path(markdown_text) or rel.with_suffix("").as_posix()
        reference_links = [
            {
                "label": reference.label,
                "kind": reference.kind,
                "url": _relative_href(html_path, html_root / reference.url),
            }
            for reference in page_refs.get(rel.as_posix(), [])
        ]
        body_markdown = _markdown_without_title(markdown_text)
        if rel.as_posix().startswith("compiler/stage1_py/"):
            compounddef = file_compounds.get(rel.as_posix())
            if compounddef is not None:
                body_markdown = _markdown_without_title(
                    _build_stage1_hub_markdown(rel, compounddef, compounds_by_id)
                )
        html_path.write_text(
            page_template.render(
                title=_markdown_title(markdown_text),
                module_name=module_name_for_source_path(source_path),
                body=_markdown_to_html(body_markdown),
                source_path=source_path,
                reference_links=reference_links,
                root_prefix=os.path.relpath(html_root, start=html_path.parent).replace("\\", "/"),
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    groups = _collect_browse_entries(markdown_root, html_root, page_refs)
    page_titles = {"stage1": "Stage 1", "stage2": "Stage 2", "shared": "Shared"}
    for group_name, entries in groups.items():
        if stage != "all" and group_name not in {stage, "shared"}:
            continue
        page_path = html_root / f"{group_name}.html"
        page_path.write_text(
            group_template.render(
                title=page_titles[group_name],
                entries=[
                    {
                        "title": entry.title,
                        "source_path": entry.source_path,
                        "url": _relative_href(page_path, html_root / entry.url),
                        "reference_links": [
                            {
                                "label": reference.label,
                                "kind": reference.kind,
                                "url": _relative_href(page_path, html_root / reference.url),
                            }
                            for reference in entry.reference_links
                        ],
                    }
                    for entry in entries
                ],
                root_prefix=".",
            ).strip()
            + "\n",
            encoding="utf-8",
        )


def render_compat_redirect_pages(xml_dir: Path, markdown_root: Path, html_root: Path, templates_dir: Path) -> None:
    """Render compatibility pages for missing raw Doxygen URLs."""
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    redirect_template = env.get_template("html_redirect.j2")

    for xml_path in sorted(xml_dir.glob("*.xml")):
        if xml_path.name == "index.xml":
            continue
        root = ET.parse(xml_path).getroot()
        compounddef = root.find("compounddef")
        if compounddef is None:
            continue
        kind = compounddef.attrib.get("kind", "")
        if kind not in {"namespace", "file", "dir"}:
            continue

        location = compounddef.find("location")
        if location is None or "file" not in location.attrib:
            continue
        source_path = location.attrib["file"]
        if Path(source_path).is_absolute():
            continue
        alias_path = html_root / f"{compounddef.attrib['id']}.html"
        if alias_path.exists():
            continue

        if kind == "dir":
            target = _scope_hub_target(source_path, html_root)
            if target is None or not target.exists():
                continue
            target_href = _relative_href(alias_path, target)
            alias_path.write_text(
                redirect_template.render(
                    title=compounddef.findtext("compoundname", default=compounddef.attrib["id"]),
                    target_href=target_href,
                    root_prefix=".",
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            continue

        markdown_path = markdown_root / Path(source_path).with_suffix(".md")
        if not markdown_path.exists():
            continue

        target = _markdown_page_to_html_path(markdown_root, markdown_path, html_root)
        if not target.exists():
            continue

        target_href = _relative_href(alias_path, target)
        if kind == "namespace":
            target_href += f"#{compound_anchor(compounddef)}"

        alias_path.write_text(
            redirect_template.render(
                title=compounddef.findtext("compoundname", default=compounddef.attrib["id"]),
                target_href=target_href,
                root_prefix=".",
            ).strip()
            + "\n",
            encoding="utf-8",
        )
