# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Independent output transactions and stage navigation."""
from pathlib import Path
import sys
import pytest
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from compiler.docgen import l1_docgen
import gen_docs


def test_canonical_reference_transaction(tmp_path, monkeypatch):
    def generate(args):
        args.output_dir.mkdir()
        (args.output_dir / 'identity').write_text('canonical L1')
    monkeypatch.setattr(l1_docgen, '_generate_reference', generate)
    assert l1_docgen.main(['--output-dir', str(tmp_path)]) == 0
    assert (tmp_path / 'reference/identity').read_text() == 'canonical L1'


def test_canonical_navigation():
    env = Environment(loader=FileSystemLoader(ROOT / 'scripts/docs/templates'))
    for template in ('mainpage_html.md.j2', 'mcss_conf.py.in', 'html_api_page.j2', 'html_api_group.j2'):
        text = env.get_template(template).render(root_prefix='.')
        assert 'stage1.html' not in text and 'stage2.html' not in text
        assert '../pdf/dea_l1_api_reference.pdf' in text
        assert 'Dea/L1' in text and 'Stage' not in text


def test_failed_reference_preserves_output_but_invalidates_bundle(tmp_path, monkeypatch):
    (tmp_path / 'reference').mkdir()
    (tmp_path / 'reference/old').write_text('previous reference')
    bundle = tmp_path / 'artifacts/dea_l1_autodocs.tar.gz'
    bundle.parent.mkdir()
    bundle.write_text('old success')
    monkeypatch.setattr(gen_docs, 'require_command', lambda *a: None)
    def fail(*args, **kwargs):
        raise SystemExit('strict failure')
    monkeypatch.setattr(gen_docs, 'run_logged', fail)
    assert gen_docs.main(['--strict', '--pdf', '--artifacts', '--output-dir', str(tmp_path)]) == 1
    assert not bundle.exists()
    assert (tmp_path / 'reference/old').read_text() == 'previous reference'


def test_stage_selection_is_rejected():
    with pytest.raises(ValueError, match='one canonical compiler'):
        gen_docs.parse_args(['--stage', 'stage1'])
    with pytest.raises(SystemExit):
        l1_docgen.parse_args(['--stage', 'stage2'])


def test_preview_is_not_distributable(tmp_path, monkeypatch):
    monkeypatch.setattr(gen_docs, "REPO_ROOT", tmp_path)
    assert gen_docs.main(['--pdf-fast', '--strict', '--artifacts']) == 1


def test_missing_tool_invalidates_prior_bundle(tmp_path, monkeypatch):
    bundle = tmp_path / 'artifacts/dea_l1_autodocs.tar.gz'
    bundle.parent.mkdir()
    bundle.write_text('old')
    def missing(*args):
        raise RuntimeError('missing tool')
    monkeypatch.setattr(gen_docs, 'require_command', missing)
    assert gen_docs.main(['--strict','--pdf','--artifacts','--output-dir',str(tmp_path)]) == 1
    assert not bundle.exists()


def test_source_function_completeness_rejects_silent_loss(tmp_path):
    source = tmp_path / 'source.l1'
    source.write_text('func missing() -> uint;\n')
    xml = tmp_path / 'xml'
    xml.mkdir()
    (xml / 'index.xml').write_text('<doxygenindex/>')
    with pytest.raises(ValueError, match='missing'):
        l1_docgen._verify_source_functions(tmp_path, l1_docgen.SourceManifest([Path('source.l1')]), xml)


def test_wrapper_publishes_matching_preview_and_artifact(tmp_path, monkeypatch):
    import hashlib
    import sys
    repo = tmp_path / 'l1'
    repo.mkdir()
    mcss = tmp_path / 'tools/m.css/documentation'
    mcss.mkdir(parents=True)
    (mcss / 'doxygen.py').write_text('fixture renderer')
    monkeypatch.setattr(gen_docs, 'REPO_ROOT', repo)
    monkeypatch.setattr(gen_docs, 'venv_python', lambda: sys.executable)
    monkeypatch.setattr(gen_docs, 'require_command', lambda *args: None)
    monkeypatch.setattr(gen_docs, 'source_identity', lambda *args: {'revision':'fixture','tree_state':'clean','input_digest':'a'*64})
    monkeypatch.setattr(gen_docs.subprocess, 'check_output', lambda *args, **kwargs: 'fixture version\n')
    def run(command, log, **kwargs):
        if '-m' in command:
            output = Path(command[command.index('--output-dir') + 1]) / 'reference'
            (output / 'html').mkdir(parents=True)
            (output / 'html/index.html').write_text(f'<a href="../pdf/dea_l1_api_reference.pdf">reference</a>')
            (output / 'markdown').mkdir()
            (output / 'markdown/index.md').write_text('reference')
            (output / 'doxygen/latex').mkdir(parents=True)
        else:
            latex = Path(command[command.index('-C') + 1])
            (latex / 'refman.pdf').write_bytes(b'%PDF-1.7\nfixture\n%%EOF\n')
            (latex / 'refman.log').write_text('complete')
            (latex / 'refman.ind').write_text('index')
    monkeypatch.setattr(gen_docs, 'run_logged', run)
    assert gen_docs.main(['--strict','--pdf','--artifacts']) == 0
    assert (repo / 'build/preview/reference/markdown/index.md').read_text() == 'reference'
    assert (repo / 'build/docs/artifacts/dea_l1_autodocs.tar.gz').is_file()
