# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Acceptance handoff, isolated harness dependencies, and hosted isolation policy."""

import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from test_distribution import package  # Reuse the verified curated archive fixture.
import dist_toolchain
import distribution_archive as archives
import productization_acceptance as acceptance
import smoke_dist

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def evidence(package, tmp_path, monkeypatch):
    _, prefix, metadata, _ = package
    calls = []

    def distribute(env, *, make):
        archive = tmp_path / 'archive with spaces.tar.gz'
        archives.write_archive(prefix, archive, windows=False)
        docs = json.loads((prefix / archives.DOCS_PATH / 'manifest.json').read_text())
        record = {**metadata, 'schema_version': 1, 'level': 'l1', 'stage': 2,
                  'archive_path': str(archive), 'archive_size': archive.stat().st_size,
                  'archive_sha256': archives.digest(archive), 'docs_source': docs['source'],
                  'docs_bundle_sha256': 'a' * 64}
        Path(env['DIST_RESULT']).write_text(json.dumps(record))
        calls.append((env, make))
        return archive

    monkeypatch.setattr(dist_toolchain, 'distribute', distribute)
    destination = tmp_path / 'acceptance evidence'
    acceptance.build(destination, {'DOCS_ARTIFACT': '/docs bundle.tar.gz', 'L1_INSTALL_MAKE': 'selected-make'})
    return destination, calls


def test_transported_result_drives_smoke_and_report(evidence, tmp_path, monkeypatch):
    directory, calls = evidence
    transported = tmp_path / 'transported elsewhere'
    directory.rename(transported)
    record = json.loads((transported / 'result.json').read_text())
    Path(record['archive_path']).unlink()  # The original build path is unavailable.
    invoked = []
    monkeypatch.setattr(smoke_dist, 'smoke', lambda archive, env: invoked.append((archive, env)))
    acceptance.verify(transported, {'L1_CC': 'native-cc'})
    assert invoked == [(transported / Path(record['archive_path']).name, {'L1_CC': 'native-cc'})]
    assert calls[0][1] == 'selected-make'
    assert calls[0][0]['DOCS_ARTIFACT'] == '/docs bundle.tar.gz'
    assert not Path(calls[0][0]['DIST_RESULT']).exists()
    assert json.loads((transported / 'acceptance.json').read_text())['status'] == 'passed'


@pytest.mark.parametrize('field,value', [
    ('schema_version', 2), ('schema_version', True), ('schema_version', 1.0),
    ('stage', 1), ('stage', 2.0), ('level', 'l0'), ('maturity', 'stable'),
    ('archive_path', 'relative.tar.gz'), ('archive_size', 0), ('archive_sha256', '0' * 64),
    ('package_version', 'different'), ('provenance', {}), ('docs_source', {}),
    ('docs_bundle_sha256', 'invalid'), ('unexpected_field', 'invalid'),
])
def test_invalid_handoff_never_invokes_compiler(evidence, monkeypatch, field, value):
    directory, _ = evidence
    result = directory / 'result.json'
    record = json.loads(result.read_text())
    record[field] = value
    result.write_text(json.dumps(record))
    (directory / 'acceptance.json').write_text('stale success')
    monkeypatch.setattr(smoke_dist, 'smoke', lambda *args: pytest.fail('invalid result reached compiler'))
    with pytest.raises(ValueError):
        acceptance.verify(directory, {})
    assert not (directory / 'acceptance.json').exists()


def test_failed_smoke_does_not_publish_success(evidence, monkeypatch):
    directory, _ = evidence

    def fail(*args):
        raise ValueError('native execution failed')

    monkeypatch.setattr(smoke_dist, 'smoke', fail)
    with pytest.raises(ValueError, match='native execution failed'):
        acceptance.verify(directory, {})
    assert not (directory / 'acceptance.json').exists()


def test_failed_build_and_existing_output_are_not_success(tmp_path, monkeypatch):
    directory = tmp_path / 'evidence'

    def fail(*args, **kwargs):
        raise ValueError('build failed')

    monkeypatch.setattr(dist_toolchain, 'distribute', fail)
    with pytest.raises(ValueError, match='build failed'):
        acceptance.build(directory, {})
    assert not (directory / 'result.json').exists()
    with pytest.raises(FileExistsError):
        acceptance.build(directory, {})
    with pytest.raises(ValueError, match='absolute'):
        acceptance.build(Path('relative evidence'), {})


def test_copied_harness_imports_without_checkout_or_site_packages(evidence, tmp_path):
    directory, _ = evidence
    harness = directory / 'harness'
    assert {p.name for p in harness.iterdir()} == set(acceptance.HARNESS)
    # Isolated Python cannot import any checkout module or installed dependency.
    script = "import sys; sys.path.insert(0, sys.argv[1]); import smoke_dist, distribution_archive, productization_acceptance"
    result = subprocess.run([sys.executable, '-I', '-S', '-c', script, str(harness)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    record = json.loads((directory / 'result.json').read_text())
    (directory / Path(record['archive_path']).name).write_bytes(b'corrupt')
    result = subprocess.run([sys.executable, '-I', '-S', str(harness / 'productization_acceptance.py'),
                             '--phase', 'verify', '--directory', str(directory)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1
    assert 'size/digest disagrees' in result.stderr


def test_make_gate_is_explicit_and_does_not_generate_docs(tmp_path):
    destination = str(tmp_path / 'evidence with spaces')
    result = subprocess.run(['make', '-n', 'test-productization-acceptance', f'ACCEPTANCE_DIR={destination}'],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    assert 'scripts/productization_acceptance.py' in result.stdout
    assert 'gen_docs.py' not in result.stdout
    result = subprocess.run(['make', 'test-productization-acceptance', 'ACCEPTANCE_DIR='],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'ACCEPTANCE_DIR is required' in result.stderr


def test_workflow_uses_same_source_docs_and_fresh_verification_runners():
    workflow = yaml.load((ROOT.parent / '.github/workflows/l1-productization-acceptance.yml').read_text(),
                         Loader=yaml.BaseLoader)
    assert set(workflow['on']) == {'workflow_dispatch'}
    assert workflow['permissions'] == {'contents': 'read'}
    jobs = workflow['jobs']
    assert jobs['build']['needs'] == 'docs'
    assert jobs['verify']['needs'] == 'build'
    assert jobs['build']['strategy']['matrix'] == jobs['verify']['strategy']['matrix']
    assert len(jobs['build']['strategy']['matrix']['include']) == 4
    for job in ('docs', 'build'):
        checkout = next(s for s in jobs[job]['steps'] if s.get('uses', '').startswith('actions/checkout@'))
        assert checkout['with']['ref'] == '${{ github.sha }}'
    assert any('core.autocrlf false' in s.get('run', '') for s in jobs['build']['steps'])
    steps = jobs['verify']['steps']
    assert not any('checkout' in s.get('uses', '') for s in steps)
    verification = [s for s in steps if '--phase verify' in s.get('run', '')]
    assert len(verification) == 2  # POSIX and native UCRT64 Python.
    assert all('set -o pipefail' in s['run'] and ' -I ' in s['run'] for s in verification)


def test_invalid_environment_phase_cannot_report_success(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('ACCEPTANCE_PHASE', 'typo')
    monkeypatch.setenv('ACCEPTANCE_DIR', str(tmp_path / 'must not exist'))
    monkeypatch.setattr(sys, 'argv', ['productization_acceptance.py'])
    assert acceptance.main() == 1
    assert 'ACCEPTANCE_PHASE must be' in capsys.readouterr().err
    assert not (tmp_path / 'must not exist').exists()
