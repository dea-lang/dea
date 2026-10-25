# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Real-Doxygen contracts and precise declaration/definition report identities."""

from __future__ import annotations

from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from jinja2 import Environment, FileSystemLoader
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from docgen_function_inventory import collect_undocumented_functions
import docgen_doxygen
from docgen_doxygen import _merge_xml, _prefix_latex, render_mcss, run_isolated_doxygen


HEADER = '''/** @file */

/* Acquire one owned handle. */
int acquire(const char *name, int *out);

typedef int native_int;
struct Node { int value; };
typedef struct Node Node;

/* Read an ABI alias. */
native_int alias_value(native_int value);

/* Invoke the borrowed callback. */
void callback_value(int (*compare)(native_int left));

/* Inspect the borrowed node. */
void callback_node(void (*compare)(Node left));

/* A declaration without a contract. */
int pending(int value);

/**
 * Increment the borrowed value.
 * @param value Input value; ownership stays with the caller.
 * @return The incremented value; no operation can fail.
 */
static inline int header_helper(int value) { return value + 1; }
'''
SOURCE = '''/** @file */
#include "api.h"

/**
 * Acquire one owned handle.
 * Ownership of the successful handle transfers to the caller.
 * On failure, the output is unchanged and no resource is acquired.
 * @param name Borrowed name; it remains valid for this call.
 * @param out Borrowed output slot receiving the owned handle.
 * @return Zero on success, or minus one on failure.
 */
int acquire(const char *name, int *out) { return name && out ? 0 : -1; }

int pending(int value) { return value; }

/**
 * Read an ABI alias.
 * @param value Borrowed input.
 * @return The same integer.
 */
int alias_value(int value) { return value; }

/**
 * Invoke the borrowed callback.
 * @param apply Caller-owned callback; it is not retained.
 */
void callback_value(int (*apply)(int renamed)) { (void)apply; }

/**
 * Inspect the borrowed node.
 * @param apply Caller-owned callback; it is not retained.
 */
void callback_node(void (*apply)(struct Node renamed)) { (void)apply; }

/**
 * Return a private sentinel.
 * @return One; failure is impossible.
 */
static int private_name(void) { return 1; }
'''
OTHER = '''/** @file */

static int private_name(void) { return 2; }

static int acquire(const char *name, int *out) { return -1; }

int acquire(double value) { return 0; }

int overload(int first); int overload(double second);
'''
BINDING = '''/** @file */

int acquire(const char *name, int *out);
'''
DOCUMENTED_BINDING = '''/** @file */

/**
 * Acquire a language binding handle.
 * @param name Borrowed name.
 * @param out Output slot.
 * @return Binding result.
 */
int binding_documented(const char *name, int *out);
'''
SINGLE_HEADER = '''/** @file */

/* Hash the borrowed value. */
int header_library(int value);

#ifdef SIPHASH_IMPLEMENTATION

/**
 * Hash the borrowed value.
 * @param value Input bytes remain caller-owned.
 * @return The hash; no allocation or failure occurs.
 */
int header_library(int value) { return value; }
#endif
'''



def _line(text: str, declaration: str) -> int:
    """Return the one-based line of an exact fixture declaration."""
    return text.splitlines().index(declaration) + 1


def _run_doxygen(tmp_path: Path, level: str, *, header: str = HEADER, source: str = SOURCE, isolated: bool = True) -> Path:
    """Render the production template and extract all native contract fixtures."""
    if shutil.which('doxygen') is None:
        pytest.skip('Doxygen is unavailable')
    source_root = tmp_path / 'sources with spaces'
    source_root.mkdir()
    fixtures = {'api.h': header, 'api.c': source, 'other.c': OTHER,
                'binding.l0': BINDING, 'documented.l0': DOCUMENTED_BINDING, 'single.h': SINGLE_HEADER}
    for name, contents in fixtures.items():
        (source_root / name).write_text(contents, encoding='utf-8')
    output = tmp_path / 'reference'
    template = Environment(loader=FileSystemLoader(str(ROOT / level / 'scripts/docs/templates')))
    config = template.get_template('doxyfile.in').render(
        stage='stage2', project_number='test', output_directory=output.as_posix(),
        mainpage=(source_root / 'index.md').as_posix(),
        input_files=[(source_root / name).as_posix() for name in fixtures],
        strip_from_path=source_root.as_posix(), warn_logfile=(tmp_path / 'warnings.log').as_posix(),
        generate_xml='YES', generate_latex='YES',
    )
    (source_root / 'index.md').write_text('# Test API\n', encoding='utf-8')
    path = tmp_path / 'Doxyfile'
    path.write_text(config, encoding='utf-8')
    if isolated:
        run_isolated_doxygen(path, cwd=source_root)
    else:
        subprocess.run(['doxygen', str(path)], check=True, capture_output=True, text=True)
    return output


def _members(xml: Path) -> list[ET.Element]:
    """Read all extracted function occurrences."""
    return [member for path in xml.glob('*.xml')
            for member in ET.parse(path).findall('.//memberdef[@kind="function"]')]


@pytest.mark.parametrize('level', ['l0', 'l1'])
def test_real_doxygen_source_contract_and_locations(tmp_path: Path, level: str) -> None:
    output = _run_doxygen(tmp_path, level)
    assert not (tmp_path / 'warnings.log').read_text().strip()
    members = _members(output / 'xml')
    native = [member for member in members if member.findtext('name') == 'acquire'
              and member.find('location').get('file') in {'api.c', 'api.h'}]
    assert len(native) == 2
    # Production Javadoc autobrief splits the first sentence even when the
    # remaining contract continues in the same paragraph without an @brief.
    assert '@brief' not in SOURCE
    for member in native:
        assert ''.join(member.find('briefdescription').itertext()).strip() == 'Acquire one owned handle.'
        detail = ''.join(member.find('detaileddescription').itertext())
        assert 'Ownership of the successful handle transfers to the caller.' in detail
        assert 'On failure, the output is unchanged and no resource is acquired.' in detail
        description = ' '.join(member.itertext())
        for text in ('Acquire one owned handle.', 'Ownership of the successful handle transfers to the caller.',
                     'On failure, the output is unchanged and no resource is acquired.',
                     'Borrowed name; it remains valid for this call.',
                     'Borrowed output slot receiving the owned handle.',
                     'Zero on success, or minus one on failure.'):
            assert text in description
        params = member.findall('.//parameterlist[@kind="param"]/parameteritem')
        assert len(params) == 2
        assert member.find('.//simplesect[@kind="return"]') is not None
        location = member.find('location')
        assert location.get('bodyfile') == 'api.c'
        assert int(location.get('bodystart')) == _line(SOURCE, 'int acquire(const char *name, int *out) { return name && out ? 0 : -1; }')
        assert int(location.get('bodyend')) == int(location.get('bodystart'))
        if location.get('file') == 'api.h':
            assert location.get('declfile') == 'api.h'
            assert int(location.get('declline')) == _line(HEADER, 'int acquire(const char *name, int *out);')
        else:
            assert int(location.get('line')) == int(location.get('bodystart'))
    helper = next(member for member in members if member.findtext('name') == 'header_helper')
    assert ''.join(helper.find('briefdescription').itertext()).strip() == 'Increment the borrowed value.'
    assert helper.find('location').get('bodyfile') == 'api.h'
    assert int(helper.find('location').get('bodystart')) == _line(HEADER, 'static inline int header_helper(int value) { return value + 1; }')
    assert 'ownership stays with the caller' in ' '.join(helper.itertext())
    assert 'no operation can fail' in ' '.join(helper.itertext())
    single = [member for member in members if member.findtext('name') == 'header_library']
    assert single and all('Input bytes remain caller-owned.' in ' '.join(member.itertext()) for member in single)
    assert all(''.join(member.find('briefdescription').itertext()).strip() == 'Hash the borrowed value.' for member in single)
    assert all(member.find('location').get('bodyfile') == 'single.h' for member in single)
    assert all(int(member.find('location').get('bodystart')) == _line(SINGLE_HEADER, 'int header_library(int value) { return value; }') for member in single)
    latex = '\n'.join(path.read_text(encoding='utf-8') for path in (output / 'latex').glob('*.tex'))
    assert 'Ownership of the successful handle transfers to the caller.' in latex
    assert 'output is unchanged' in latex
    assert 'Borrowed name; it remains valid for this call.' in latex
    assert 'Borrowed output slot receiving the owned handle.' in latex
    assert 'Zero on success, or minus one on failure.' in latex
    assert 'Input bytes remain caller-owned.' in latex.replace(r'-\/', '-')
    assert 'no allocation or failure occurs' in latex
    entries = collect_undocumented_functions(output / 'xml', tmp_path / 'sources with spaces')
    assert ('api.h', _line(HEADER, 'int pending(int value);'), 'pending') in entries
    assert not any(path in {'api.c', 'api.h', 'single.h'} and name in {'acquire', 'header_helper', 'header_library'} for path, _, name in entries)
    # Isolated extraction keeps language bindings out of the native contract.
    binding = next(member for member in members if member.find('location').get('file') == 'binding.l0')
    assert not ''.join(binding.find('briefdescription').itertext()).strip()
    assert binding.find('location').get('bodyfile') is None
    assert ('binding.l0', 3, 'acquire') in entries
    assert entries.count(('other.c', _line(OTHER, 'int overload(int first); int overload(double second);'), 'overload')) == 2
    assert not any(path == 'documented.l0' for path, _, _ in entries)
    assert ('other.c', _line(OTHER, 'static int private_name(void) { return 2; }'), 'private_name') in entries
    assert ('other.c', _line(OTHER, 'static int acquire(const char *name, int *out) { return -1; }'), 'acquire') in entries
    assert ('other.c', _line(OTHER, 'int acquire(double value) { return 0; }'), 'acquire') in entries


@pytest.mark.parametrize('documented_file', ['api.h', 'api.c'])
def test_explicit_identity_covers_only_matching_occurrences(tmp_path: Path, documented_file: str) -> None:
    output = _run_doxygen(tmp_path, 'l1')
    candidates = {'acquire', 'alias_value', 'callback_value', 'callback_node'}
    # Older Doxygen does not associate callbacks whose nested parameter names
    # differ. Exercise every relationship it actually provides; independent XML
    # fixtures below cover callback identity without depending on its parser.
    linked = {member.findtext('name') for member in _members(output / 'xml')
              if member.findtext('name') in candidates
              and member.find('location').get('file') == 'api.h'
              and member.find('location').get('bodyfile') == 'api.c'}
    assert {'acquire', 'alias_value'} <= linked
    # Emulate versions that keep documentation on just one XML occurrence.
    # Keep real Doxygen locations, linkage, names, and parameter signatures.
    for path in (output / 'xml').glob('*.xml'):
        tree = ET.parse(path)
        for member in tree.findall('.//memberdef[@kind="function"]'):
            location = member.find('location')
            if member.findtext('name') in linked and location.get('file') != documented_file:
                for tag in ('briefdescription', 'detaileddescription', 'inbodydescription'):
                    section = member.find(tag)
                    if section is not None:
                        section.clear()
        tree.write(path, encoding='utf-8')
    entries = collect_undocumented_functions(output / 'xml')
    uncovered = [entry for entry in entries if entry[0] in {'api.c', 'api.h'} and entry[2] in linked]
    assert not uncovered, uncovered
    assert any(path == 'other.c' and name == 'acquire' for path, _, name in entries)
    assert ('binding.l0', 3, 'acquire') in entries


@pytest.mark.parametrize(('declaration', 'definition', 'matching_signature'), [
    ('int (*)(native_int left)', 'int (*)(int renamed)', True),
    ('void (*)(Node left)', 'void (*)(struct Node renamed)', True),
    ('int (*)(native_int left)', 'int (*)(double renamed)', False),
    ('void (*)(Node left)', 'void (*)(struct Other renamed)', False),
])
@pytest.mark.parametrize('documented_file', ['api.h', 'api.c'])
@pytest.mark.parametrize('bodyfile', [None, 'api.c', 'unrelated.c'])
def test_callback_contracts_require_explicit_matching_xml_identity(
        tmp_path: Path, declaration: str, definition: str, matching_signature: bool,
        documented_file: str, bodyfile: str | None) -> None:
    """Cover callback type equivalence and missing or unrelated source links."""
    root = ET.Element('doxygen')
    compound = ET.SubElement(root, 'compounddef')
    for name, target in [('native_int', 'int'), ('Node', 'struct Node')]:
        alias = ET.SubElement(compound, 'memberdef', kind='typedef', id=name)
        ET.SubElement(alias, 'name').text = name
        ET.SubElement(alias, 'type').text = target
        ET.SubElement(alias, 'location', file='api.h', line='1')
    for source, line, parameter, formal in [('api.h', 14, declaration, 'compare'), ('api.c', 27, definition, 'apply')]:
        member = ET.SubElement(compound, 'memberdef', kind='function', id=source + '_callback')
        ET.SubElement(member, 'type').text = 'void'
        ET.SubElement(member, 'name').text = 'callback'
        param = ET.SubElement(member, 'param')
        ET.SubElement(param, 'type').text = parameter
        ET.SubElement(param, 'declname').text = formal
        if source == documented_file:
            ET.SubElement(member, 'briefdescription').text = 'Invoke the borrowed callback.'
        location = ET.SubElement(member, 'location', file=source, line=str(line))
        if source == 'api.c':
            location.set('bodyfile', source)
            location.set('bodystart', str(line))
        elif bodyfile:
            location.set('bodyfile', bodyfile)
            location.set('bodystart', '27')
    ET.ElementTree(root).write(tmp_path / 'callbacks.xml', encoding='utf-8')
    entries = collect_undocumented_functions(tmp_path)
    if matching_signature and bodyfile == 'api.c':
        assert entries == []
    else:
        undocumented_file = 'api.c' if documented_file == 'api.h' else 'api.h'
        assert entries == [(undocumented_file, 27 if undocumented_file == 'api.c' else 14, 'callback')]


def test_legacy_cross_binding_xml_cannot_supply_a_native_contract(tmp_path: Path) -> None:
    output = _run_doxygen(tmp_path, 'l1', isolated=False)
    entries = collect_undocumented_functions(output / 'xml', tmp_path / 'sources with spaces')
    assert ('binding.l0', 3, 'acquire') in entries


def test_isolated_outputs_keep_graph_ids_numeric_and_reference_targets_distinct(tmp_path: Path) -> None:
    source = tmp_path / 'part/xml'
    source.mkdir(parents=True)
    (source / 'index.xml').write_text('<doxygenindex><compound refid="classA" kind="class"><name>A</name></compound></doxygenindex>')
    (source / 'classA.xml').write_text('''<doxygen><compounddef id="classA"><compoundname>A</compoundname>
<inheritancegraph><node id="1"><label>A</label><link refid="classA"/><link refid="classA" external="other.tag"/><childnode refid="2"/></node>
<node id="2"><label>B</label></node></inheritancegraph></compounddef></doxygen>''')
    output = tmp_path / 'combined'
    _merge_xml([('native_', source.parent)], output)
    tree = ET.parse(output / 'native_classA.xml')
    assert tree.find('compounddef').get('id') == 'native_classA'
    assert [node.get('id') for node in tree.findall('.//inheritancegraph/node')] == ['1', '2']
    assert tree.find('.//childnode').get('refid') == '2'
    assert tree.find('.//link').get('refid') == 'native_classA'
    assert tree.find('.//link[@external]').get('refid') == 'classA'
    text = r"\doxyref{\texttt{A}}{p.}{classA} \label{classA} \includegraphics[width=1cm]{classA_graph} \input{classA} \input{classA.tex}"
    result = _prefix_latex(text, 'native_', {'classA'}, {'classA_graph': 'native_classA_graph'})
    assert result == r"\doxyref{\texttt{A}}{p.}{native_classA} \label{native_classA} \includegraphics[width=1cm]{native_classA_graph} \input{native_classA} \input{native_classA.tex}"


def test_failed_group_retains_warnings_config_and_partial_outputs(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / 'input.l0'
    native = tmp_path / 'api.c'
    source.write_text('int language();')
    native.write_text('int native();')
    output = tmp_path / 'reference'
    warning = output / 'warnings.log'
    config = tmp_path / 'Doxyfile'
    config.write_text(f'''INPUT = "{source.as_posix()}" "{native.as_posix()}"
OUTPUT_DIRECTORY = "{output.as_posix()}"
WARN_LOGFILE = "{warning.as_posix()}"
GENERATE_XML = YES
GENERATE_LATEX = NO
''')
    def fail(command, **kwargs):
        group = Path(command[1]).read_text()
        group_output = Path(docgen_doxygen.shlex.split(docgen_doxygen._setting(group, 'OUTPUT_DIRECTORY'))[0])
        group_warning = Path(docgen_doxygen.shlex.split(docgen_doxygen._setting(group, 'WARN_LOGFILE'))[0])
        (group_output / 'xml').mkdir(parents=True)
        (group_output / 'xml/partial.xml').write_text('partial evidence')
        group_warning.write_text('extraction failure details\n')
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(docgen_doxygen.subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        run_isolated_doxygen(config, cwd=tmp_path)
    failure = output / 'extraction-failure/dea_l0'
    assert (failure / 'xml/partial.xml').read_text() == 'partial evidence'
    assert (failure / 'warnings.log').read_text() == 'extraction failure details\n'
    assert 'input.l0' in (failure / 'Doxyfile').read_text()
    assert warning.read_text() == 'extraction failure details\n'


def test_real_mcss_renders_combined_xml_without_rerunning_extraction(tmp_path: Path) -> None:
    import hashlib
    output = _run_doxygen(tmp_path, 'l1')
    xml = output / 'xml'
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in xml.iterdir() if path.is_file()}
    warning = (tmp_path / 'warnings.log').read_bytes()
    config = tmp_path / 'mcss_conf.py'
    config.write_text(f"DOXYFILE = {str(tmp_path / 'Doxyfile')!r}\nOUTPUT = {str(output / 'html')!r}\nSHOW_UNDOCUMENTED = True\n")
    render_mcss(ROOT / 'tools/m.css/documentation/doxygen.py', config, cwd=tmp_path)
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in xml.iterdir() if path.is_file()}
    assert after == before
    assert (tmp_path / 'warnings.log').read_bytes() == warning
    assert (output / 'html/index.html').is_file()
    assert list((output / 'html').glob('native_*api*.html'))


@pytest.mark.parametrize(('renderer', 'filename'), [
    ('doxygen', 'mcss_config.py'),
    ('python', 'mcss_config.py'),
    ('python', 'mcss_config'),
])
@pytest.mark.parametrize('relative', [False, True])
def test_mcss_cli_loads_registered_config_and_renders(tmp_path: Path, renderer: str, filename: str, relative: bool) -> None:
    """Execute both CLI loaders, including Python's extensionless configs."""
    config_dir = tmp_path / 'configuration with spaces'
    config_dir.mkdir()
    xml = config_dir / 'reference/xml'
    xml.mkdir(parents=True)
    (xml / 'index.xml').write_text('<doxygenindex version="1.9.8"/>', encoding='utf-8')
    (config_dir / 'Doxyfile').write_text('OUTPUT_DIRECTORY = reference\n', encoding='utf-8')
    config = config_dir / filename
    config.write_text('''from __future__ import annotations
from dataclasses import dataclass
import sys

assert sys.modules[__name__].__dict__ is globals()

@dataclass
class Configuration:
    fine_print: str = "Loaded registered m.css configuration"

DOXYFILE = 'Doxyfile'
OUTPUT = 'reference/html'
FINE_PRINT = Configuration().fine_print
FAVICON = None
STYLESHEETS = []
LINKS_NAVBAR1 = []
LINKS_NAVBAR2 = []
SEARCH_DISABLED = True
M_MATH_CACHE_FILE = ''
''', encoding='utf-8')
    selected = config.relative_to(tmp_path) if relative else config
    command = [sys.executable, '-W', 'error::DeprecationWarning',
               str(ROOT / 'tools/m.css/documentation' / (renderer + '.py')), str(selected)]
    if renderer == 'doxygen':
        command.append('--no-doxygen')
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    html = (config_dir / 'reference/html/index.html').read_text(encoding='utf-8')
    assert 'Loaded registered m.css configuration' in html


@pytest.mark.parametrize('renderer', ['doxygen', 'python'])
def test_mcss_cli_reports_configuration_exceptions(tmp_path: Path, renderer: str) -> None:
    """Keep configuration failures visible through the real CLI entry points."""
    config = tmp_path / 'broken_config.py'
    config.write_text('''import atexit
import sys

name = __name__
atexit.register(lambda: print('Configuration module removed:', name not in sys.modules))
raise RuntimeError('m.css configuration failure sentinel')
''', encoding='utf-8')
    result = subprocess.run([sys.executable, '-W', 'error::DeprecationWarning',
                             str(ROOT / 'tools/m.css/documentation' / (renderer + '.py')), str(config)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert 'RuntimeError: m.css configuration failure sentinel' in result.stderr
    assert 'Configuration module removed: True' in result.stdout


@pytest.mark.parametrize('spellings', [
    ['C:\\Dea checkout\\compiler/support\\api.c', 'C:/Dea checkout/compiler/support/api.h'],
    ['\\\\server\\shared docs\\runtime/api.c', '//server/shared docs/runtime/api.h'],
    ['/opt/Dea checkout/compiler/api.c', '/opt/Dea checkout/compiler/api.h'],
])
def test_production_config_paths_round_trip_without_host_dependent_rewriting(spellings: list[str]) -> None:
    # Production configs serialize filesystem paths with as_posix before quoting.
    # PureWindowsPath models that producer on a non-Windows validation host.
    expected = [PureWindowsPath(value).as_posix() if ':' in value or value.startswith(('\\\\', '//')) else value
                for value in spellings]
    config = 'INPUT = ' + ' '.join('"' + value + '"' for value in expected) + '\n'
    values = docgen_doxygen.shlex.split(docgen_doxygen._setting(config, 'INPUT'))
    assert values == expected
    groups = docgen_doxygen._groups([Path(value) for value in values])
    assert groups == [('native', [Path(value) for value in expected])]
    different = expected[0].replace('api.c', 'other.c')
    assert values[0] != different


def test_shared_body_metadata_does_not_merge_different_return_signatures(tmp_path: Path) -> None:
    output = _run_doxygen(tmp_path, 'l1')
    member = next(item for item in _members(output / 'xml')
                  if item.findtext('name') == 'callback_value' and item.find('location').get('file') == 'api.c')
    duplicate = ET.fromstring(ET.tostring(member))
    duplicate.find('type').clear()
    duplicate.find('type').text = 'double'
    for tag in ('briefdescription', 'detaileddescription', 'inbodydescription'):
        duplicate.find(tag).clear()
    root = ET.Element('doxygen')
    compound = ET.SubElement(root, 'compounddef')
    compound.append(duplicate)
    ET.ElementTree(root).write(output / 'xml/different_return.xml')
    entries = collect_undocumented_functions(output / 'xml')
    assert ('api.c', _line(SOURCE, 'void callback_value(int (*apply)(int renamed)) { (void)apply; }'), 'callback_value') in entries


@pytest.mark.parametrize('level', ['l0', 'l1'])
def test_real_doxygen_differing_formal_names_preserve_complete_contracts(tmp_path: Path, level: str, capfd) -> None:
    import re
    header = '''/** @file */

/* Combine the borrowed arguments. */
int combine(int right, int left, int result);
'''
    source = '''/** @file */
#include "api.h"

/**
 * Combine the borrowed arguments.
 *
 * The arguments remain caller-owned. Failure leaves the caller state unchanged.
 * @param left First definition argument remains borrowed.
 * @param right Second definition argument remains borrowed.
 * @param output Third definition argument remains borrowed.
 * @return The combined result, or minus one on failure.
 */
int combine(int left, int right, int output) { return left + right + output; }
'''
    output = _run_doxygen(tmp_path, level, header=header, source=source)
    members = [member for member in _members(output / 'xml') if member.findtext('name') == 'combine']
    assert len(members) == 2
    descriptions = ['First definition argument remains borrowed.', 'Second definition argument remains borrowed.',
                    'Third definition argument remains borrowed.']
    for member in members:
        location = member.find('location')
        is_header = location.get('file') == 'api.h'
        declaration_names = ['right', 'left', 'result'] if is_header else ['left', 'right', 'output']
        assert [parameter.findtext('declname') for parameter in member.findall('param')] == declaration_names
        assert member.findtext('argsstring') == ('(int right, int left, int result)' if is_header else '(int left, int right, int output)')
        assert location.get('bodyfile') == 'api.c'
        assert int(location.get('bodystart')) == _line(source, 'int combine(int left, int right, int output) { return left + right + output; }')
        if is_header:
            assert [parameter.findtext('defname') for parameter in member.findall('param')] == ['left', 'right', 'output']
            assert location.get('declline') == '4'
        labels = member.findall('.//parameterlist[@kind="param"]/parameteritem')
        assert [item.findtext('parameternamelist/parametername') for item in labels] == declaration_names
        assert [''.join(item.find('parameterdescription').itertext()).strip() for item in labels] == descriptions
    config = tmp_path / 'mcss_conf.py'
    config.write_text(f"DOXYFILE = {str(tmp_path / 'Doxyfile')!r}\nOUTPUT = {str(output / 'html')!r}\nSHOW_UNDOCUMENTED = True\n")
    render_mcss(ROOT / 'tools/m.css/documentation/doxygen.py', config, cwd=tmp_path)
    rendered = capfd.readouterr()
    assert "parameter description doesn't match parameter names" not in rendered.err
    for filename, names in [('native_api_8h', ['right', 'left', 'result']), ('native_api_8c', ['left', 'right', 'output'])]:
        html = (output / 'html' / (filename + '.html')).read_text()
        for name, description in zip(names, descriptions):
            assert re.search(r'<td(?:\s+[^>]*)?>' + name + r'</td>\s*<td>' + re.escape(description) + r'</td>', html)
        assert 'caller-owned' in html and 'caller state unchanged' in html
        assert 'minus one on failure' in html
        latex = (output / 'latex' / (filename + '.tex')).read_text()
        caption = re.search(r'\\begin\{DoxyParamCaption\}(.*?)\\end\{DoxyParamCaption\}', latex, re.DOTALL).group(1)
        # Doxygen 1.9.8 includes padding and the following comma in the name
        # field; newer releases put that separator in its own argument.
        caption_names = re.findall(r'\]\{\s*([A-Za-z_]\w*)\s*(?:,\s*)?\}', caption)
        assert len(caption_names) == 3
        # Doxygen's native TeX chooses the definition formals for its caption.
        # Keep its already-consistent table and the source-owned prose intact.
        for name, description in zip(caption_names, descriptions):
            assert re.search(r'\{\\em\s+' + re.escape(name) + r'\}\s*&\s*' + re.escape(description), latex)
        assert 'caller-owned' in latex.replace(r'-\/', '-') and 'caller state unchanged' in latex
        assert 'minus one on failure' in latex
    assert (tmp_path / 'sources with spaces/api.h').read_text() == header
    assert (tmp_path / 'sources with spaces/api.c').read_text() == source


def test_unknown_c_parameter_documentation_is_not_silently_dropped(tmp_path: Path) -> None:
    from docgen_c_contracts import normalize_fresh_xml_parameter_docs
    (tmp_path / 'api.xml').write_text('''<doxygen><compounddef><memberdef kind="function" id="api_1a">
<name>read</name><param><type>int</type><declname>value</declname><defname>input</defname></param>
<detaileddescription><para><parameterlist kind="param"><parameteritem><parameternamelist>
<parametername>unrelated</parametername></parameternamelist><parameterdescription><para>Must survive.</para>
</parameterdescription></parameteritem></parameterlist></para></detaileddescription><location file="api.h" line="3"/>
</memberdef></compounddef></doxygen>''')
    with pytest.raises(ValueError, match='unknown C documentation parameter.*unrelated'):
        normalize_fresh_xml_parameter_docs(tmp_path)


@pytest.mark.parametrize('level', ['l0', 'l1'])
def test_curated_source_links_use_only_rendered_fragments(tmp_path: Path, level: str, monkeypatch) -> None:
    import importlib
    sys.path.insert(0, str(ROOT))
    renderer = importlib.import_module(f'{level}.compiler.docgen.{level}_docgen_markdown')
    xml = tmp_path / 'xml'
    markdown = tmp_path / 'markdown'
    html = tmp_path / 'html'
    xml.mkdir()
    html.mkdir()
    source = 'compiler/shared/runtime/include/probe.h'
    io_source = 'compiler/shared/runtime/src/io.c'
    compounds = {
        'native_probe_8h': f'''<compounddef id="native_probe_8h" kind="file" language="C"><compoundname>probe.h</compoundname>
<innerclass refid="native_structOuter">Outer</innerclass><location file="{source}"/>
<sectiondef><memberdef kind="function" id="native_probe_8h_1aread"><name>read</name><definition>int read</definition><type>int</type><argsstring>()</argsstring>
<detaileddescription><para>See <ref refid="native_io_8c">io.c</ref>.</para></detaileddescription><location file="{source}" line="8"/>
</memberdef></sectiondef></compounddef>''',
        'native_io_8c': f'''<compounddef id="native_io_8c" kind="file" language="C"><compoundname>io.c</compoundname><location file="{io_source}"/>
<sectiondef><memberdef kind="function" id="native_io_8c_1acurrent"><name>current</name><definition>int current</definition><type>int</type><argsstring>()</argsstring>
<detaileddescription><para>See <ref refid="native_io_8c">io.c</ref>.</para></detaileddescription><location file="{io_source}" line="4"/>
</memberdef></sectiondef></compounddef>''',
        'native_structOuter': f'''<compounddef id="native_structOuter" kind="struct" language="C"><compoundname>Outer</compoundname>
<innerclass refid="native_unionOuter_data">Outer::(anonymous).data</innerclass><location file="{source}" line="2"/></compounddef>''',
        'native_unionOuter_data': f'''<compounddef id="native_unionOuter_data" kind="union" language="C"><compoundname>Outer::(anonymous).data</compoundname>
<location file="{source}" line="3"/></compounddef>''',
    }
    if level == 'l0':
        compounds.update({
            'python_probe_8py': '''<compounddef id="python_probe_8py" kind="file" language="Python"><compoundname>probe.py</compoundname>
<innerclass refid="python_classProbe">probe::Probe</innerclass><location file="compiler/stage1_py/probe.py"/></compounddef>''',
            'python_classProbe': '''<compounddef id="python_classProbe" kind="class" language="Python"><compoundname>probe::Probe</compoundname>
<location file="compiler/stage1_py/probe.py" line="3"/></compounddef>''',
        })
    for name, compound in compounds.items():
        (xml / (name + '.xml')).write_text('<doxygen>' + compound + '</doxygen>')
    for name in ('native_structOuter', 'native_unionOuter_data', *(['python_classProbe'] if level == 'l0' else [])):
        compound = ET.fromstring(compounds[name])
        source_path = compound.find('location').get('file')
        anchor = renderer.compound_anchor(compound)
        module = Path(source_path).stem
        old = f'<p>Defined in module <code>{module}</code> (<a href="api/{Path(source_path).with_suffix(".html").as_posix()}#{anchor}">{Path(source_path).name}</a>).</p>'
        (html / (name + '.html')).write_text('<html><h1>Record</h1>' + old + '</html>')
    monkeypatch.chdir(tmp_path)
    kwargs = {'stage': 'stage1'} if level == 'l0' else {}
    renderer.render_markdown_site(xml, markdown, ROOT / level / 'scripts/docs/templates', **kwargs)
    renderer.render_curated_html_site(xml, markdown, html, ROOT / level / 'scripts/docs/templates', **kwargs)
    renderer.render_raw_reference_backlinks(xml, markdown, html)
    nested = (html / 'native_unionOuter_data.html').read_text()
    assert 'href="api/compiler/shared/runtime/include/probe.html"' in nested
    assert '#union-outeranonymousdata' not in nested
    assert nested.count('Defined in module') == 1
    outer = (html / 'native_structOuter.html').read_text()
    assert 'href="api/compiler/shared/runtime/include/probe.html#struct-outer"' in outer
    header = (html / 'api/compiler/shared/runtime/include/probe.html').read_text()
    assert 'href="../src/io.html"' in header
    assert '#file-ioc' not in header
    self_page = (html / 'api/compiler/shared/runtime/src/io.html').read_text()
    assert 'href="io.html"' in self_page and '#file-ioc' not in self_page
    if level == 'l0':
        hub = (html / 'api/compiler/stage1_py/probe.html').read_text()
        assert 'id="class-probeprobe"' not in hub
        python = (html / 'python_classProbe.html').read_text()
        assert 'href="api/compiler/stage1_py/probe.html"' in python
        assert '#class-probeprobe' not in python
        assert python.count('Defined in module') == 1
