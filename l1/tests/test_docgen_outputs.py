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


@pytest.mark.parametrize('order', [('stage1', 'stage2'), ('stage2', 'stage1'), ('all',)])
def test_independent_stage_outputs(tmp_path, monkeypatch, order):
    def generate(args):
        args.output_dir.mkdir()
        (args.output_dir / 'stage').write_text(args.stage)
    monkeypatch.setattr(l1_docgen, '_generate_stage', generate)
    for stage in order:
        assert l1_docgen.main(['--stage', stage, '--output-dir', str(tmp_path)]) == 0
    for stage in ('stage1', 'stage2'):
        assert (tmp_path / stage / 'stage').read_text() == stage


@pytest.mark.parametrize('stage', ['stage1', 'stage2'])
def test_isolated_navigation(stage):
    env = Environment(loader=FileSystemLoader(ROOT / 'scripts/docs/templates'))
    for template in ('mainpage_html.md.j2', 'mcss_conf.py.in', 'html_api_page.j2', 'html_api_group.j2'):
        text = env.get_template(template).render(stage=stage, root_prefix='.')
        other = 'stage2' if stage == 'stage1' else 'stage1'
        assert f'{other}.html' not in text
        assert f'../pdf/dea_l1_{stage}_api_reference.pdf' in text
        assert f'Dea/L1 Stage {stage[-1]}' in text


def test_failed_stage_preserves_output_but_invalidates_bundle(tmp_path, monkeypatch):
    for stage in ('stage1', 'stage2'):
        (tmp_path / stage).mkdir()
        (tmp_path / stage / 'old').write_text(stage)
    bundle = tmp_path / 'artifacts/dea_l1_stage2_autodocs.tar.gz'
    bundle.parent.mkdir()
    bundle.write_text('old success')
    monkeypatch.setattr(gen_docs, 'require_command', lambda *a: None)
    def fail(*args, **kwargs):
        raise SystemExit('strict failure')
    monkeypatch.setattr(gen_docs, 'run_logged', fail)
    assert gen_docs.main(['--stage', 'stage2', '--strict', '--pdf', '--artifacts', '--output-dir', str(tmp_path)]) == 1
    assert not bundle.exists()
    assert (tmp_path / 'stage1/old').read_text() == 'stage1'
    assert (tmp_path / 'stage2/old').read_text() == 'stage2'


def test_preview_is_not_distributable(tmp_path, monkeypatch):
    monkeypatch.setattr(gen_docs, "REPO_ROOT", tmp_path)
    assert gen_docs.main(['--pdf-fast', '--strict', '--artifacts']) == 1


def test_missing_tool_invalidates_prior_bundle(tmp_path, monkeypatch):
    bundle = tmp_path / 'artifacts/dea_l1_stage2_autodocs.tar.gz'
    bundle.parent.mkdir()
    bundle.write_text('old')
    def missing(*args):
        raise RuntimeError('missing tool')
    monkeypatch.setattr(gen_docs, 'require_command', missing)
    assert gen_docs.main(['--stage','stage2','--strict','--pdf','--artifacts','--output-dir',str(tmp_path)]) == 1
    assert not bundle.exists()


def test_source_function_completeness_rejects_silent_loss(tmp_path):
    source = tmp_path / 'source.l1'
    source.write_text('func missing() -> uint;\n')
    xml = tmp_path / 'xml'
    xml.mkdir()
    (xml / 'index.xml').write_text('<doxygenindex/>')
    with pytest.raises(ValueError, match='missing'):
        l1_docgen._verify_source_functions(tmp_path, l1_docgen.SourceManifest([Path('source.l1')]), xml)


@pytest.mark.parametrize('order', [('stage1','stage2'), ('stage2','stage1'), ('all',)])
def test_wrapper_transactions_keep_previews_and_artifacts_independent(tmp_path, monkeypatch, order):
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
            stage = command[command.index('--stage') + 1]
            output = Path(command[command.index('--output-dir') + 1]) / stage
            (output / 'html').mkdir(parents=True)
            (output / 'html/index.html').write_text(f'<a href="../pdf/dea_l1_{stage}_api_reference.pdf">{stage}</a>')
            (output / 'markdown').mkdir()
            (output / 'markdown/index.md').write_text(stage)
            (output / 'doxygen/latex').mkdir(parents=True)
        else:
            latex = Path(command[command.index('-C') + 1])
            (latex / 'refman.pdf').write_bytes(b'%PDF-1.7\nfixture\n%%EOF\n')
            (latex / 'refman.log').write_text('complete')
            (latex / 'refman.ind').write_text('index')
    monkeypatch.setattr(gen_docs, 'run_logged', run)
    snapshots = {}
    for selected in order:
        assert gen_docs.main(['--stage',selected,'--strict','--pdf','--artifacts']) == 0
        for stage, before in snapshots.items():
            assert {p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in repo.rglob('*') if p.is_file() and (f'/{stage}/' in str(p) or f'_{stage}_' in p.name)} == before
        for stage in (('stage1','stage2') if selected == 'all' else (selected,)):
            snapshots[stage] = {p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in repo.rglob('*') if p.is_file() and (f'/{stage}/' in str(p) or f'_{stage}_' in p.name)}
    for stage in ('stage1','stage2'):
        assert (repo / f'build/preview/{stage}/markdown/index.md').read_text() == stage
        assert (repo / f'build/docs/artifacts/dea_l1_{stage}_autodocs.tar.gz').is_file()
