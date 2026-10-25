#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Generate the complete L2 native C support reference, without a bootstrap.

This inventory covers maintained production C, not the L1 compiler implementation
or L2 language bindings. L2 has no compiler-language autodocs pipeline yet.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "scripts"))
from docgen_function_inventory import collect_undocumented_functions
from docgen_c_contracts import normalize_fresh_xml_parameter_docs


def build_source_manifest(root: Path) -> list[Path]:
    """Return exact production C inputs relative to the L2 root.

    Args:
        root: L2 source root.

    Returns:
        Sorted owned runtime and compiler-support C/header paths. Tests,
        benchmark evidence, generated files, and vendored code are excluded.
    """
    return sorted({path.relative_to(root)
                   for directory in ("compiler/shared/runtime", "compiler/support")
                   for pattern in ("*.h", "*.c")
                   for path in (root / directory).rglob(pattern)})


def doxyfile_text(shadow: Path, output: Path, files: list[Path]) -> str:
    """Render a native-only Doxygen configuration with explicit source inputs.

    Args:
        shadow: Unmodified source-copy root.
        output: Generated output root.
        files: Production sources relative to the shadow root.

    Returns:
        Configuration preserving original declaration and body line numbers.
    """
    inputs = " ".join('"' + (shadow / path).as_posix() + '"' for path in files)
    return f'''PROJECT_NAME = "Dea/L2 Native C API"
OUTPUT_DIRECTORY = "{output.as_posix()}"
INPUT = {inputs}
FILE_PATTERNS = *.h *.c
FULL_PATH_NAMES = YES
STRIP_FROM_PATH = "{shadow.as_posix()}"
STRIP_FROM_INC_PATH = "{shadow.as_posix()}"
EXTRACT_ALL = YES
EXTRACT_STATIC = YES
PREDEFINED = SIPHASH_IMPLEMENTATION DEA_TRACE_ARC DEA_TRACE_MEMORY
HIDE_UNDOC_MEMBERS = NO
JAVADOC_AUTOBRIEF = YES
QT_AUTOBRIEF = YES
WARN_IF_UNDOCUMENTED = NO
WARN_IF_DOC_ERROR = YES
WARN_LOGFILE = "{(output / 'warnings.log').as_posix()}"
QUIET = YES
GENERATE_XML = YES
GENERATE_HTML = NO
GENERATE_LATEX = YES
SOURCE_BROWSER = YES
XML_PROGRAMLISTING = NO
VERBATIM_HEADERS = NO
'''



def render_native_html(root: Path, config: Path, output: Path, work: Path) -> None:
    """Render native contracts using a private enum-summary template override.

    m.css omits value detail tables for undocumented enum values. Their inline
    summary links still need real targets, so place the targets on those visible
    values instead of altering vendored templates or creating hidden findings.

    Args:
        root: L2 source root for subprocess execution.
        config: Existing Doxygen configuration pointing at the final XML tree.
        output: Reference output directory.
        work: Private directory for renderer configuration and templates.

    Raises:
        RuntimeError: The vendored template no longer matches the override.
        subprocess.CalledProcessError: HTML rendering failed.
    """
    renderer_root = ROOT.parent / 'tools/m.css/documentation'
    templates = work / 'templates'
    templates.mkdir(exist_ok=True)
    template = (renderer_root / 'templates/doxygen/entry-enum.html').read_text(encoding='utf-8')
    original = '<a href="#{{ value.id }}" class="m-doc">'
    replacement = ('<a href="{% if enum.base_url != compound.url %}{{ enum.base_url }}{% endif %}#{{ value.id }}" '
                   'class="m-doc"{% if not enum.has_value_details and enum.base_url == compound.url %} '
                   'id="{{ value.id }}"{% endif %}>')
    if original not in template:
        raise RuntimeError('m.css enum template changed; review native inline-value anchors')
    (templates / 'entry-enum.html').write_text(template.replace(original, replacement), encoding='utf-8')
    mcss_config = work / 'mcss_conf.py'
    mcss_config.write_text(f"DOXYFILE = {str(config)!r}\nOUTPUT = {str(output / 'html')!r}\n"
                           "PROJECT_TITLE = 'Dea/L2 Native C API'\nSHOW_UNDOCUMENTED = True\n", encoding='utf-8')
    subprocess.run([sys.executable, str(renderer_root / 'doxygen.py'), str(mcss_config),
                    '--no-doxygen', '--templates', str(templates)], cwd=root, check=True)

def generate(root: Path, output: Path, *, strict: bool = False, pdf: bool = False) -> None:
    """Generate native C references and an informational undocumented report.

    Args:
        root: L2 source root.
        output: Output directory.
        strict: Reject Doxygen warnings.
        pdf: Build the complete Doxygen LaTeX reference PDF.

    Raises:
        RuntimeError: Strict generation emitted warnings or the PDF is absent.
        subprocess.CalledProcessError: Doxygen or the LaTeX build failed.
    """
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # A fresh inventory must not pick up old XML compounds or HTML pages.
    for name in ('xml', 'html', 'latex', 'pdf'):
        if (output / name).is_dir():
            shutil.rmtree(output / name)
    files = build_source_manifest(root)
    (output / 'sources.txt').write_text(''.join(path.as_posix() + '\n' for path in files), encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='dea-l2-c-docs-') as temporary:
        work = Path(temporary)
        shadow = work / 'shadow'
        for relative in files:
            destination = shadow / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / relative, destination)
        config = work / 'Doxyfile'
        config.write_text(doxyfile_text(shadow, output, files), encoding='utf-8')
        subprocess.run(['doxygen', str(config)], check=True, cwd=root)
        normalize_fresh_xml_parameter_docs(output / 'xml')
        render_native_html(root, config, output, work)
        entries = collect_undocumented_functions(output / 'xml', root)
    lines = ['# Undocumented Functions', '']
    lines.extend(f'{path}:{line} {name}' if line else f'{path} {name}' for path, line, name in entries)
    if not entries:
        lines.append('No undocumented functions found.')
    (output / 'undocumented-functions.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    warnings = output / 'warnings.log'
    if strict and warnings.exists() and warnings.read_text(encoding='utf-8').strip():
        raise RuntimeError(f'Doxygen emitted warnings; see {warnings}')
    if pdf:
        subprocess.run(['make'], cwd=output / 'latex', check=True)
        target = output / 'pdf/dea_l2_native_api_reference.pdf'
        target.parent.mkdir(parents=True, exist_ok=True)
        source = output / 'latex/refman.pdf'
        if not source.exists():
            raise RuntimeError('LaTeX did not produce the complete reference PDF')
        shutil.copy2(source, target)


def main() -> None:
    """Parse the bootstrap-independent native documentation command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('build/docs/native'))
    parser.add_argument('--strict', action='store_true')
    parser.add_argument('--pdf', action='store_true')
    args = parser.parse_args()
    generate(ROOT, args.output_dir, strict=args.strict, pdf=args.pdf)


if __name__ == '__main__':
    main()
