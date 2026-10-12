# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Local L1 release policy, workflow wiring, and mocked publication regression tests."""

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "l1/tests"))
import l1_release as release
from test_distribution import package
from docs_artifacts import create_bundle, unpack_bundle
from distribution_archive import DOCS_PATH, write_archive, digest
from productization_inventory import install_payload
from productization_provenance import PackageProvenance

SOURCE = "a" * 40
TAG = "l1-v0.1.0"


class FakeGitHub:
    """Record remote effects without accessing GitHub."""

    def __init__(self):
        self.calls = []
        self.source = SOURCE
        self.tag_source = None
        self.release = None

    def api(self, path, data=None, *, method="GET"):
        self.calls.append((method, path, data))
        if path == "":
            return {"default_branch": "main"}
        if path.startswith("commits/"):
            return {"sha": self.source}
        if path.startswith("actions/runs/"):
            return {"created_at": "2026-10-11T08:09:10Z"}
        if path.startswith("git/ref/tags/"):
            return None if self.tag_source is None else {"object": {"type": "commit", "sha": self.tag_source}}
        if path == "git/refs":
            self.tag_source = data["sha"]
            return {}
        if path == "releases" and method == "POST":
            self.release = {**data, "id": 123, "assets": []}
            return self.release
        if path.startswith("releases/assets/") and method == "DELETE":
            asset_id = int(path.rsplit("/", 1)[1])
            self.release["assets"] = [a for a in self.release["assets"] if a["id"] != asset_id]
            return None
        if path.startswith("releases"):
            if method == "PATCH":
                self.release.update(data)
            return self.release
        raise AssertionError(path)

    def upload(self, tag, assets):
        self.calls.append(("UPLOAD", tag, None))
        self.release["assets"] = [{"name": p.name, "size": p.stat().st_size, "digest": "sha256:" + digest(p)} for p in assets]


@pytest.mark.parametrize("tag,version", [(TAG, "0.1.0"), ("l1-v12.34.56", "12.34.56"),
    ("l1-snapshot-20261011-0809-aaaaaaa", "snapshot-20261011-0809-aaaaaaa")])
def test_tag_conversion(tag, version):
    assert release.package_version(tag, SOURCE) == version


@pytest.mark.parametrize("tag", ["l0-v1.2.3", "v1.2.3", "l1-v01.2.3", "l1-v1.2", "l1-v1.2.3-rc.1",
    "l1-v1.2.3+build", "l1-v1.2.3\n", "l1-snapshot-20260230-0809-aaaaaaa", "l1-snapshot-20261011-0809-bbbbbbb"])
def test_bad_tag_rejected(tag):
    with pytest.raises(ValueError):
        release.package_version(tag, SOURCE)


def test_snapshot_identity_survives_moving_branch_and_rerun():
    api = FakeGitHub()
    first = release.identity(api, kind="snapshot", ref="main", tag="", run_id="12")
    assert first["tag"] == "l1-snapshot-20261011-0809-aaaaaaaaaaaa"
    assert first["requested_tag"] == ""
    api.source = "b" * 40
    api.calls.clear()
    assert release.identity(api, kind="snapshot", ref="main", tag="", run_id="12", saved=first) == first
    assert api.calls == []
    with pytest.raises(ValueError, match="another request"):
        release.identity(api, kind="snapshot", ref="main", tag="", run_id="13", saved=first)


def test_release_event_and_snapshot_tags_are_separate():
    api = FakeGitHub()
    api.tag_source = SOURCE
    record = release.identity(api, kind="release", ref=SOURCE, tag=TAG, run_id="12")
    release.ensure_tag(api, record)
    assert all(method == "GET" for method, _, _ in api.calls)
    with pytest.raises(ValueError):
        release.identity(api, kind="release", ref="b" * 40, tag=TAG, run_id="12")
    with pytest.raises(ValueError):
        release.identity(api, kind="snapshot", ref=SOURCE, tag=TAG, run_id="12")


def test_snapshot_tag_creation_is_idempotent_and_never_moves_tags():
    api = FakeGitHub()
    record = release.identity(api, kind="snapshot", ref="", tag="", run_id="12")
    release.ensure_tag(api, record)
    release.ensure_tag(api, record)
    assert sum(method == "POST" for method, _, _ in api.calls) == 1
    api.tag_source = "b" * 40
    with pytest.raises(ValueError, match="never move"):
        release.ensure_tag(api, record)


@pytest.mark.parametrize("native", ["C:\\build with spaces\\archive.zip", "C:/build with spaces/archive.zip",
                                    "C:\\build with spaces/archive.zip", "\\\\host\\share\\build with spaces\\archive.zip"])
def test_windows_result_paths_on_any_host(native):
    assert release.archive_basename(native, "windows-x86_64") == "archive.zip"
    assert release.archive_basename(native.replace("archive.zip", "different.zip"), "windows-x86_64") != "archive.zip"


def test_posix_result_paths_preserve_literal_backslashes():
    assert release.archive_basename("/build with spaces/archive.tar.gz", "linux-x86_64") == "archive.tar.gz"
    for path in ("relative.zip", "C:relative.zip"):
        with pytest.raises(ValueError):
            release.archive_basename(path, "windows-x86_64")


def test_notes_use_reachable_level_tags_and_full_history(tmp_path):
    # Tags are confined to this disposable fixture repository, never the working repository.
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()
    git("init", "-b", "main")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    def commit(name):
        (tmp_path / "shared").write_text(name)
        git("add", "shared")
        git("commit", "-m", name)
        return git("rev-parse", "HEAD")
    first = commit("First shared change")
    assert "Initial L1 publication" in release.release_notes(tmp_path, TAG, first)
    git("tag", "l1-v0.0.1")
    commit("Second shared change")
    git("tag", "l1-snapshot-20261010-0809-aaaaaaa")
    commit("Third shared change")
    git("tag", "l0-v99.0.0")
    git("tag", "l1-v01.0.0")
    source = commit("Fourth shared change")
    git("checkout", "-b", "other", first)
    commit("Unreachable change")
    git("tag", "l1-v99.0.0")
    git("checkout", "main")
    notes = release.release_notes(tmp_path, TAG, source)
    assert "since `l1-v0.0.1`" in notes
    assert "Second shared change" in notes and "Fourth shared change" in notes
    assert "Unreachable change" not in notes
    notes = release.release_notes(tmp_path, "l1-snapshot-20261011-0809-aaaaaaa", source)
    assert "since `l1-snapshot-20261010-0809-aaaaaaa`" in notes
    assert "Second shared change" not in notes and "Third shared change" in notes


@pytest.fixture
def asset_evidence(package, tmp_path, monkeypatch):
    payload, _, metadata, _ = package
    docs_source = {"revision": SOURCE, "tree_state": "clean", "input_digest": "a" * 64}
    monkeypatch.setattr(release, "source_identity", lambda root: docs_source)
    bundle = tmp_path / "canonical.tar.gz"
    create_bundle(tmp_path / "docs", bundle, version="0.1.0", source=docs_source,
                  tools={key: "fixture" for key in ("doxygen", "pdflatex", "python", "mcss")})
    unpack_bundle(bundle, tmp_path / "canonical-docs", version="0.1.0", source=docs_source)
    shutil.rmtree(payload / DOCS_PATH)
    shutil.copytree(tmp_path / "canonical-docs/dea-l1-autodocs", payload / DOCS_PATH)
    evidence, reports = tmp_path / "evidence", tmp_path / "reports"
    evidence.mkdir(); reports.mkdir()
    for host in sorted(release.HOSTS):
        host_payload = tmp_path / ("payload-" + host)
        shutil.copytree(payload, host_payload)
        meta = copy.deepcopy(metadata)
        meta.update(package_version="0.1.0", os=host.split("-")[0], arch=host.split("-")[1])
        meta["provenance"]["source"] = {"url": "https://github.com/dea-lang/dea", "revision": SOURCE, "tree_state": "clean"}
        if meta["os"] == "windows":
            for name in ("bin/l1c.cmd", "bin/l1-env.cmd"):
                (host_payload / name).write_text("@echo off\n")
        (host_payload / "VERSION").write_text(PackageProvenance(json.dumps(meta)).version_text())
        prefix = tmp_path / ("prefix-" + host)
        install_payload(host_payload, prefix, meta)
        directory = evidence / host; directory.mkdir()
        suffix = ".zip" if meta["os"] == "windows" else ".tar.gz"
        archive = directory / f"dea-l1-lang_0.1.0_{host}_20261011-080910{suffix}"
        write_archive(prefix, archive, windows=meta["os"] == "windows")
        archive_path = "C:\\build with spaces\\" + archive.name if meta["os"] == "windows" else "/build with spaces/" + archive.name
        result = {**meta, "schema_version": 2, "level": "l1", "archive_path": archive_path,
                  "archive_sha256": digest(archive), "archive_size": archive.stat().st_size,
                  "docs_source": docs_source, "docs_bundle_sha256": digest(bundle)}
        (directory / "result.json").write_text(json.dumps(result))
        (directory / "harness").mkdir()
        for name in release.HARNESS:
            shutil.copyfile(ROOT / "l1/scripts" / name, directory / "harness" / name)
        (reports / host).mkdir()
        report = {k: result[k] for k in ("schema_version", "archive_sha256", "package_version", "os", "arch")}
        (reports / host / "acceptance.json").write_text(json.dumps({**report, "status": "passed"}))
    return evidence, reports, bundle, tmp_path / "staged assets"


def stage(fixture):
    return release.stage_assets(ROOT, *fixture, tag=TAG, source=SOURCE)


def test_seven_assets_checksums_and_identical_pdf(asset_evidence):
    assets = stage(asset_evidence)
    assert len(assets) == 7
    output = asset_evidence[-1]
    lines = (output / "SHA256SUMS").read_text().splitlines()
    assert len(lines) == 6
    assert set(lines) == {f"{digest(p)}  {p.name}" for p in assets if p.name != "SHA256SUMS"}
    assert (output / f"dea_l1_api_reference-{TAG}.pdf").read_bytes().startswith(b"%PDF-")


@pytest.mark.parametrize("problem", ["missing-host", "unexpected-host", "failed-report", "wrong-report-digest", "wrong-report-host",
    "wrong-source", "wrong-version", "wrong-docs-digest", "old-schema", "stage-field", "tampered-archive", "extra-archive", "tampered-harness", "wrong-docs"])
def test_aggregation_rejects_bad_or_mixed_evidence(asset_evidence, problem):
    evidence, reports, bundle, output = asset_evidence
    host = "linux-x86_64"
    path = evidence / host / "result.json"
    result = json.loads(path.read_text())
    report_path = reports / host / "acceptance.json"
    report = json.loads(report_path.read_text())
    if problem == "missing-host": shutil.rmtree(reports / host)
    elif problem == "unexpected-host": (evidence / "linux-arm64").mkdir()
    elif problem == "failed-report": report["status"] = "failed"
    elif problem == "wrong-report-digest": report["archive_sha256"] = "b" * 64
    elif problem == "wrong-report-host": report["os"] = "windows"
    elif problem == "wrong-source": result["provenance"]["source"]["revision"] = "b" * 40
    elif problem == "wrong-version": result["package_version"] = "0.2.0"
    elif problem == "wrong-docs-digest": result["docs_bundle_sha256"] = "b" * 64
    elif problem == "old-schema": result["schema_version"] = 1
    elif problem == "stage-field": result["stage"] = 2
    elif problem == "tampered-archive": (evidence / host / release.archive_basename(result["archive_path"], host)).write_bytes(b"bad")
    elif problem == "extra-archive": (evidence / host / "unexpected.zip").write_bytes(b"bad")
    elif problem == "tampered-harness": (evidence / host / "harness/smoke_dist.py").write_text("bad")
    elif problem == "wrong-docs": bundle.write_bytes(b"bad")
    path.write_text(json.dumps(result))
    if report_path.exists(): report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError): stage(asset_evidence)
    assert not output.exists()


@pytest.mark.parametrize("publish_release", [False, True])
def test_draft_then_publish_preserves_l0_latest(tmp_path, publish_release):
    assets = []
    names = [f"dea-l1-lang_0.1.0_{host}_20261011-080910" + (".zip" if host.startswith("windows") else ".tar.gz")
             for host in sorted(release.HOSTS)]
    names += [f"dea_l1_autodocs-{TAG}.tar.gz", f"dea_l1_api_reference-{TAG}.pdf", "SHA256SUMS"]
    for name in names:
        path = tmp_path / name
        path.write_text(name)
        assets.append(path)
    api = FakeGitHub(); api.tag_source = SOURCE
    release.publish(api, tag=TAG, source=SOURCE, assets=assets, notes="Development toolchain", publish_release=publish_release)
    assert api.release["draft"] is not publish_release
    assert api.release["make_latest"] == "false" and api.release["prerelease"] is False
    assert [method for method, _, _ in api.calls if method != "GET"] == ["POST", "UPLOAD", "PATCH"]
    if not publish_release:
        api.calls.clear()
        release.publish(api, tag=TAG, source=SOURCE, assets=assets, notes="Updated", publish_release=True)
        assert [method for method, _, _ in api.calls if method != "GET"] == ["UPLOAD", "PATCH"]
    api.calls.clear()
    with pytest.raises(ValueError, match="immutable"):
        release.publish(api, tag=TAG, source=SOURCE, assets=assets, notes="Bad", publish_release=True)
    assert all(method == "GET" for method, _, _ in api.calls)


@pytest.mark.parametrize("problem", ["target", "extra", "upload-failure", "corrupt-upload"])
def test_publication_failure_never_publishes(tmp_path, monkeypatch, problem):
    path = tmp_path / "asset"; path.write_text("bytes")
    api = FakeGitHub(); api.tag_source = SOURCE
    api.release = {"id": 123, "tag_name": TAG, "target_commitish": SOURCE, "draft": True, "prerelease": False, "assets": []}
    if problem == "target": api.release["target_commitish"] = "b" * 40
    if problem == "extra": api.release["assets"] = [{"name": "unexpected"}]
    def fail_upload(*args): raise ValueError("upload failed")
    if problem == "upload-failure": monkeypatch.setattr(api, "upload", fail_upload)
    if problem == "corrupt-upload": monkeypatch.setattr(api, "upload", lambda *args: None)
    with pytest.raises(ValueError):
        release.publish(api, tag=TAG, source=SOURCE, assets=[path], notes="notes", publish_release=True)
    assert api.release["draft"] is True
    assert not any(method == "PATCH" for method, _, _ in api.calls)


def test_workflow_graph_permissions_inputs_and_attempt_isolation():
    for kind in ("snapshot", "release"):
        data = yaml.load((ROOT / f".github/workflows/l1-{kind}.yml").read_text(), Loader=yaml.BaseLoader)
        prepare = "prepare-snapshot" if kind == "snapshot" else "validate-release"
        assert data["permissions"] == {"contents": "read"}
        jobs = data["jobs"]
        assert jobs["build-docs"]["needs"] == prepare
        assert set(jobs["build-dist"]["needs"]) == {prepare, "build-docs"}
        assert jobs["verify-dist"]["needs"] == "build-dist"
        assert set(jobs["publish-release"]["needs"]) == {prepare, "build-docs", "build-dist", "verify-dist"}
        assert jobs["build-dist"]["strategy"] == jobs["verify-dist"]["strategy"]
        assert {r["platform"] for r in jobs["build-dist"]["strategy"]["matrix"]["include"]} == release.HOSTS
        assert not any(s.get("uses", "").startswith("actions/checkout") for s in jobs["verify-dist"]["steps"])
        for name, job in jobs.items():
            if "steps" not in job: continue
            first = job["steps"][0]
            assert first["name"] == "Show inputs" and first["shell"] == "bash" and first["working-directory"] == "."
            assert first["env"]["INPUTS_JSON"] == "${{ toJSON(inputs) }}"
            assert 'echo "$INPUTS_JSON"' in first["run"] and '>> "$GITHUB_STEP_SUMMARY"' in first["run"]
            if job.get("permissions", {}).get("contents") == "write":
                assert name == "publish-release" or (kind == "snapshot" and name == prepare)
            for step in job["steps"]:
                if 'artifact@' in step.get('uses', ''):
                    identity = step.get('with', {}).get('name') == 'l1-release-identity'
                    if not identity:
                        selector = step['with'].get('name', step['with'].get('pattern', ''))
                        assert '${{ github.run_attempt }}' in selector
        publication = jobs['publish-release']
        assert publication['concurrency']['cancel-in-progress'] == 'false'
        assert 'outputs.tag' in publication['concurrency']['group']
        checkout = next(s for s in jobs['build-dist']['steps'] if s.get('uses', '').startswith('actions/checkout'))
        assert checkout['with']['ref'] == '${{ needs.' + prepare + '.outputs.source }}'
        steps = jobs['build-dist']['steps']
        assert next(i for i,s in enumerate(steps) if 'core.autocrlf false' in s.get('run','')) < steps.index(checkout)
        if kind == 'snapshot':
            assert data['on']['workflow_dispatch']['inputs']['publish_release']['default'] == 'true'
        else: assert data['on']['push']['tags'] == ['l1-v*']
    docs = yaml.load((ROOT / '.github/workflows/l1-docs-build.yml').read_text(), Loader=yaml.BaseLoader)
    assert set(docs['on']['workflow_call']['inputs']) == {'source_ref', 'package_version', 'release_tag'}
    steps = docs['jobs']['build-docs']['steps']
    assert steps[0]['name'] == 'Show inputs'
    assert any(s.get('run') == 'make -C l1 docs-artifacts' for s in steps)
    assert not any('pages' in s.get('uses', '') or 'blog' in s.get('run', '') for s in steps)


def test_retry_removes_only_old_matching_draft_assets(tmp_path):
    api = FakeGitHub()
    api.tag_source = SOURCE
    old = "dea-l1-lang_0.1.0_linux-x86_64_20261011-080910.tar.gz"
    new = tmp_path / "dea-l1-lang_0.1.0_linux-x86_64_20261011-101112.tar.gz"
    new.write_bytes(b"new archive")
    api.release = {"id": 123, "tag_name": TAG, "target_commitish": SOURCE, "draft": True,
                   "prerelease": False, "assets": [{"id": 456, "name": old}]}
    release.publish(api, tag=TAG, source=SOURCE, assets=[new], notes="notes", publish_release=False)
    assert ("DELETE", "releases/assets/456", None) in api.calls
    assert api.release["draft"] is True
    assert [a["name"] for a in api.release["assets"]] == [new.name]


def test_snapshot_publishes_as_prerelease(tmp_path):
    api = FakeGitHub()
    api.tag_source = SOURCE
    path = tmp_path / "SHA256SUMS"
    path.write_text("")
    tag = "l1-snapshot-20261011-0809-aaaaaaa"
    release.publish(api, tag=tag, source=SOURCE, assets=[path], notes="notes", publish_release=True)
    assert api.release["prerelease"] is True
    assert api.release["make_latest"] == "false"


def test_report_artifact_is_flat_and_success_only():
    for kind in ("release", "snapshot"):
        workflow = yaml.load((ROOT / f".github/workflows/l1-{kind}.yml").read_text(), Loader=yaml.BaseLoader)
        steps = workflow['jobs']['verify-dist']['steps']
        report = next(s for s in steps if s['name'] == 'Retain successful acceptance report')
        assert report['if'] == 'success()'
        assert report['with']['path'] == '${{ runner.temp }}/l1-acceptance/acceptance.json'
        assert report['with']['if-no-files-found'] == 'error'
        log = next(s for s in steps if s['name'] == 'Retain verification log')
        assert log['if'] == 'always()'


@pytest.mark.parametrize("problem", [None, "old-attempt", "missing-host", "extra-host"])
def test_attempt_isolation(tmp_path, problem):
    for category, prefix in (("evidence", "l1-dist-evidence"), ("reports", "l1-verification")):
        (tmp_path / category).mkdir()
        for host in release.HOSTS:
            (tmp_path / category / f"{prefix}-2-{host}").mkdir()
    folder = tmp_path / "reports/l1-verification-2-linux-x86_64"
    if problem == "old-attempt": folder.rename(folder.with_name("l1-verification-1-linux-x86_64"))
    if problem == "missing-host": folder.rmdir()
    if problem == "extra-host": (tmp_path / "reports/unexpected").mkdir()
    if problem:
        with pytest.raises(ValueError, match="rerun all jobs"):
            release.normalize_evidence(tmp_path, "2")
        assert (tmp_path / "evidence/l1-dist-evidence-2-linux-x86_64").is_dir()
    else:
        release.normalize_evidence(tmp_path, "2")
        assert {p.name for p in (tmp_path / "reports").iterdir()} == release.HOSTS


def test_rerun_without_identity_fails_before_remote_lookup(tmp_path, monkeypatch):
    api = FakeGitHub()
    monkeypatch.setattr(release, 'GitHub', lambda: api)
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '2')
    monkeypatch.setattr(sys, 'argv', ['l1_release.py', 'prepare'])
    with pytest.raises(ValueError, match='original run identity is unavailable'):
        release.main()
    assert api.calls == []


@pytest.mark.parametrize('code', [401, 403, 404, 500])
def test_api_errors_do_not_become_missing_releases(monkeypatch, code):
    from urllib.error import HTTPError
    monkeypatch.setenv('GITHUB_REPOSITORY', 'example/fixture')
    monkeypatch.setenv('GH_TOKEN', 'fixture-only')
    api = release.GitHub()
    def fail(*args, **kwargs):
        raise HTTPError('https://api.github.com/fixture', code, 'fixture failure', {}, None)
    monkeypatch.setattr(release, 'urlopen', fail)
    if code == 404:
        assert api.api('releases/tags/l1-v0.1.0') is None
    else:
        with pytest.raises(HTTPError): api.api('releases/tags/l1-v0.1.0')
    with pytest.raises(HTTPError): api.api('releases', {}, method='POST')
