# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Preserve definition-owned C parameter contracts on declaration occurrences."""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


def normalize_fresh_xml_parameter_docs(xml_dir: Path) -> int:
    """Match copied C parameter documentation to each occurrence's formal names.

    Doxygen can copy a definition's complete contract onto its declaration while
    retaining the declaration's different formal names. m.css matches parameter
    descriptions against ``declname``, so copied ``defname`` labels must follow
    the explicit per-parameter correspondence. Names, signatures, prose, and
    source locations themselves stay unchanged.

    Call this once on freshly generated XML. Under the repository convention,
    the canonical contract belongs to the definition; simultaneous substitutions
    also handle declarations whose formal names are swapped.

    Args:
        xml_dir: Fresh Doxygen XML database, possibly combined across bindings.

    Returns:
        Number of parameter-documentation labels changed.

    Raises:
        ValueError: A documented name has no explicit formal correspondence,
            or differing formal names produce an ambiguous mapping.
    """
    changes = 0
    for path in sorted(xml_dir.glob('*.xml')):
        tree = ET.parse(path)
        changed = False
        for member in tree.findall('.//memberdef[@kind="function"]'):
            location = member.find('location')
            if location is None or Path(location.get('file', '')).suffix not in {'.c', '.h'}:
                continue
            declaration_names = set()
            aliases = {}
            for parameter in member.findall('param'):
                declaration = parameter.findtext('declname', '').strip()
                definition = parameter.findtext('defname', '').strip() or declaration
                if declaration:
                    declaration_names.add(declaration)
                if definition:
                    if definition in aliases and aliases[definition] != declaration:
                        raise ValueError(f'ambiguous C parameter correspondence in {member.get("id", "")}: {definition}')
                    aliases[definition] = declaration
            replacements = []
            for name in member.findall('.//parameterlist[@kind="param"]/parameteritem/parameternamelist/parametername'):
                original = (name.text or '').strip()
                if original in aliases:
                    replacement = aliases[original]
                    if not replacement:
                        raise ValueError(f'cannot attach C parameter documentation to an unnamed declaration in {member.get("id", "")}: {original}')
                elif original in declaration_names:
                    replacement = original
                else:
                    raise ValueError(f'unknown C documentation parameter in {member.get("id", "")}: {original}')
                replacements.append((name, original, replacement))
            # Read every original label before applying any substitution. In
            # particular, left->right and right->left must not cascade.
            for name, original, replacement in replacements:
                if original != replacement:
                    name.text = replacement
                    changes += 1
                    changed = True
        if changed:
            tree.write(path, encoding='utf-8', xml_declaration=True)
    return changes
