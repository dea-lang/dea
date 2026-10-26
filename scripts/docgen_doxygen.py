# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Extract independent language bindings before combining Doxygen outputs."""

from __future__ import annotations

from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from docgen_c_contracts import normalize_fresh_xml_parameter_docs
from docgen_progress import phase


_BEGIN = '%--- Begin generated contents ---'
_END = '%--- End generated contents ---'


def _setting(config: str, name: str) -> str:
    """Read one scalar Doxygen configuration assignment."""
    match = re.search(r'^' + re.escape(name) + r'\s*=\s*(.*)$', config, re.MULTILINE)
    return match.group(1).strip() if match else ''


def _set(config: str, name: str, value: str) -> str:
    """Replace a configuration assignment without changing unrelated settings."""
    pattern = r'^' + re.escape(name) + r'\s*=.*$'
    line = name + ' = ' + value
    return re.sub(pattern, lambda _: line, config, flags=re.MULTILINE) if re.search(pattern, config, re.MULTILINE) else config + '\n' + line + '\n'


def _groups(inputs: list[Path]) -> list[tuple[str, list[Path]]]:
    """Keep native C, translated Dea, and Python bindings independent."""
    groups: dict[str, list[Path]] = {}
    for path in inputs:
        if path.suffix == '.md':
            continue
        if path.suffix in {'.h', '.c'}:
            # This adapter implements the same external ABI in a different
            # library from the runtime. Neither body documents the other.
            group = 'bridge' if path.parts[-3:] == ('compiler', 'support', 'interface_fingerprint.c') else 'native'
        elif path.suffix in {'.l0', '.l1', '.l2'}:
            group = 'dea_' + path.suffix[1:]
        else:
            group = 'python' if path.suffix == '.py' else 'other'
        groups.setdefault(group, []).append(path)
    order = ('dea_l0', 'dea_l1', 'dea_l2', 'python', 'native', 'bridge', 'other')
    return [(name, groups[name]) for name in order if name in groups]


def _merge_xml(parts: list[tuple[str, Path]], destination: Path) -> None:
    """Combine independently extracted XML with disjoint secondary identities."""
    destination.mkdir(parents=True, exist_ok=True)
    combined: ET.ElementTree | None = None
    for prefix, output in parts:
        source = output / 'xml'
        index = ET.parse(source / 'index.xml')
        roots: dict[Path, ET.ElementTree] = {path: ET.parse(path) for path in source.glob('*.xml')
                                           if path.name not in {'index.xml', 'Doxyfile.xml'}}
        identities = {node.get('id') for tree in roots.values() for node in tree.iter() if node.get('id') and not node.get('id').isdecimal()}
        identities.update(node.get('refid') for node in index.getroot().findall('compound') if node.get('refid'))
        for tree in [index, *roots.values()]:
            for node in tree.iter():
                for key in ('id', 'refid', 'compoundref'):
                    value = node.get(key)
                    if value in identities and not node.get("external"):
                        node.set(key, prefix + value)
        if combined is None:
            combined = index
        else:
            combined.getroot().extend(index.getroot())
        for path, tree in roots.items():
            tree.write(destination / (prefix + path.name), encoding='utf-8', xml_declaration=True)
        if not prefix:
            for path in source.iterdir():
                if path.suffix != '.xml' or path.name == 'Doxyfile.xml':
                    shutil.copy2(path, destination / path.name)
    assert combined is not None
    combined.write(destination / 'index.xml', encoding='utf-8', xml_declaration=True)


def _prefix_latex(text: str, prefix: str, stems: set[str], assets: dict[str, str] | None = None) -> str:
    """Keep independent LaTeX targets and included files from colliding."""
    if not prefix:
        return text
    text = re.sub(r'(\\(?:hypertarget|Hypertarget|label|hyperlink|ref|pageref|doxylink)\{)([^{}]+)(\})',
                  lambda match: match.group(1) + prefix + match.group(2) + match.group(3), text)
    text = re.sub(r'(\\(?:input|include)\{)([^{}]+)(\})',
                  lambda match: match.group(1) + (prefix if match.group(2).removesuffix('.tex') in stems else '') + match.group(2) + match.group(3), text)
    # Older Doxygen uses \doxyref{caption}{page text}{target}.
    edits = []
    for match in re.finditer(r"\\doxyref(?=\s*\{)", text):
        cursor = match.end()
        for argument in range(3):
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor >= len(text) or text[cursor] != "{":
                break
            start = cursor + 1
            depth = 1
            cursor += 1
            while cursor < len(text) and depth:
                if text[cursor] == "\\":
                    cursor += 2
                    continue
                depth += (text[cursor] == "{") - (text[cursor] == "}")
                cursor += 1
            if depth:
                break
            if argument == 2:
                edits.append((start, cursor - 1))
    for start, end in reversed(edits):
        text = text[:start] + prefix + text[start:end] + text[end:]
    if assets:
        text = re.sub(r"(\\includegraphics(?:\[[^\]]*\])?\{)([^{}]+)(\})",
                      lambda match: match.group(1) + assets.get(match.group(2), match.group(2)) + match.group(3), text)
    return text


def _merge_latex(parts: list[tuple[str, Path]], destination: Path) -> None:
    """Join generated reference chapters under one title page and final index."""
    destination.mkdir(parents=True, exist_ok=True)
    contents: list[str] = []
    refman = ''
    for prefix, output in parts:
        source = output / 'latex'
        stems = {path.stem for path in source.glob('*.tex')}
        images = {path.name: prefix + path.name for path in source.iterdir()
                  if path.suffix.lower() in {'.png', '.pdf', '.svg', '.eps', '.jpg', '.jpeg', '.dot', '.map'}}
        assets = dict(images)
        assets.update({Path(name).stem: Path(target).stem for name, target in images.items()})
        for path in source.iterdir():
            if path.suffix == '.tex':
                text = _prefix_latex(path.read_text(encoding='utf-8'), prefix, stems, assets)
                if path.name == 'refman.tex':
                    start, end = text.find(_BEGIN), text.find(_END)
                    if start < 0 or end < start:
                        raise ValueError('Doxygen LaTeX is missing its generated-content delimiters')
                    contents.append(text[start + len(_BEGIN):end].strip())
                    if not prefix:
                        refman = text
                else:
                    (destination / (prefix + path.name)).write_text(text, encoding='utf-8')
            elif path.is_file():
                target = destination / images.get(path.name, path.name)
                if not prefix or not target.exists():
                    shutil.copy2(path, target)
            elif not prefix:
                shutil.copytree(path, destination / path.name, dirs_exist_ok=True)
    start, end = refman.index(_BEGIN), refman.index(_END)
    refman = refman[:start + len(_BEGIN)] + '\n' + '\n'.join(contents) + '\n' + refman[end:]
    (destination / 'refman.tex').write_text(refman, encoding='utf-8')


def run_isolated_doxygen(config_path: Path, cwd: Path) -> None:
    """Extract each source binding separately and combine complete XML/LaTeX.

    Native prototypes and implementations stay together. Dea and Python cannot
    inherit native contracts simply because their transformed signatures match.
    Secondary XML IDs and LaTeX targets receive a private output prefix; source
    names, signatures, declaration locations, and body locations are unchanged.

    Args:
        config_path: Complete production Doxygen configuration.
        cwd: Level source root for the Doxygen subprocess.

    Raises:
        subprocess.CalledProcessError: An extraction failed.
        ValueError: A generated LaTeX reference cannot be safely combined.
    """
    config = config_path.read_text(encoding='utf-8')
    inputs = [Path(value) for value in shlex.split(_setting(config, 'INPUT'))]
    groups = _groups(inputs)
    output = Path(shlex.split(_setting(config, 'OUTPUT_DIRECTORY'))[0])
    warnings_path = Path(shlex.split(_setting(config, 'WARN_LOGFILE'))[0])
    xml_enabled = _setting(config, 'GENERATE_XML') == 'YES'
    latex_enabled = _setting(config, 'GENERATE_LATEX') == 'YES'
    output_kind = '/'.join(name for name, enabled in [('XML', xml_enabled), ('LaTeX', latex_enabled)] if enabled)
    if len(groups) <= 1:
        with phase(f'Doxygen {output_kind} extraction'):
            subprocess.run(['doxygen', str(config_path)], cwd=cwd, check=True)
        if xml_enabled:
            normalize_fresh_xml_parameter_docs(output / 'xml')
        return
    parts = []
    with tempfile.TemporaryDirectory(prefix='dea-docs-bindings-') as temporary:
        work = Path(temporary)
        attempts = []
        try:
            for index, (name, paths) in enumerate(groups):
                group_output = work / name
                group_warning = work / (name + '.log')
                group_inputs = paths + ([path for path in inputs if path.suffix == '.md'] if index == 0 else [])
                group_config = _set(config, 'INPUT', ' '.join('"' + path.as_posix() + '"' for path in group_inputs))
                group_config = _set(group_config, 'OUTPUT_DIRECTORY', '"' + group_output.as_posix() + '"')
                group_config = _set(group_config, 'WARN_LOGFILE', '"' + group_warning.as_posix() + '"')
                if index:
                    group_config = _set(group_config, 'USE_MDFILE_AS_MAINPAGE', '')
                group_path = work / (name + '.doxyfile')
                group_path.write_text(group_config, encoding='utf-8')
                attempts.append((name, group_output, group_warning, group_path))
                with phase(f'Doxygen {output_kind} extraction ({name})'):
                    subprocess.run(['doxygen', str(group_path)], cwd=cwd, check=True)
                parts.append(('' if index == 0 else name + '_', group_output))
            with phase(f'Combine Doxygen {output_kind} bindings'):
                if xml_enabled:
                    _merge_xml(parts, output / 'xml')
                    normalize_fresh_xml_parameter_docs(output / 'xml')
                if latex_enabled:
                    _merge_latex(parts, output / 'latex')
        except Exception:
            # The level wrapper preserves this output on failure. Do not lose
            # failed extraction evidence when the private work tree disappears.
            for name, group_output, group_warning, group_path in attempts:
                failure = output / 'extraction-failure' / name
                failure.mkdir(parents=True, exist_ok=True)
                if group_output.exists():
                    shutil.copytree(group_output, failure, dirs_exist_ok=True)
                shutil.copy2(group_path, failure / 'Doxyfile')
                if group_warning.exists():
                    shutil.copy2(group_warning, failure / 'warnings.log')
            raise
        finally:
            warnings_path.parent.mkdir(parents=True, exist_ok=True)
            warnings_path.write_text(''.join(warning.read_text(encoding='utf-8')
                                            for _, _, warning, _ in attempts if warning.exists()), encoding='utf-8')


def render_mcss(renderer: Path, config: Path, cwd: Path) -> None:
    """Render the combined database without running Doxygen a second time.

    Args:
        renderer: Vendored m.css renderer script.
        config: Complete m.css configuration selecting the combined XML tree.
        cwd: Level source root for the renderer subprocess.

    Raises:
        subprocess.CalledProcessError: Rendering failed.
    """
    with phase('Render m.css HTML'):
        subprocess.run([sys.executable, str(renderer), str(config), '--no-doxygen'], cwd=cwd, check=True)
