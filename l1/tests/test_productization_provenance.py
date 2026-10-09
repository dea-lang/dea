# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Package metadata identity and safe source generation regressions."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_stage2_l1c
import productization_provenance as provenance
from productization_inventory import inventory_payload


@pytest.fixture
def capture(tmp_path, monkeypatch):
    monkeypatch.setattr(provenance.platform, "system", lambda: "Linux")
    monkeypatch.setattr(provenance.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(build_stage2_l1c, "compiler_build_env", lambda env: (
        {**env, "L1_CC": "/native compiler/gcc", "L1_CFLAGS": "-O2 -D_RT_QUARANTINE_MAX_COUNT=256"},
        ["--check-basic"]))
    calls = []

    def command(args, **kwargs):
        calls.append((args, kwargs))
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return "a" * 40 + "\n"
        if args[:2] == ["git", "status"]:
            return " M tracked.l1\n"
        return {"l0": "Dea language / L0 compiler (Stage 2)",
                "l1": "Dea language / L1 compiler (Stage 1)",
                "l2": "Dea language / L1 compiler (Stage 2)",
                "gcc": 'gcc "quoted" \\ path caf\u00e9\nsecond line'}[Path(args[0]).name]

    monkeypatch.setattr(provenance.subprocess, "check_output", command)
    kwargs = dict(root=tmp_path, env={"DEA_DIST_VERSION": "1.2.3", "SECRET": "do-not-record"},
                  upstream=Path("l0"), stage1=Path("l1"), stage2=Path("l2"),
                  stage1_options=["--check-basic"], preparation_inputs={"include/dea_rt.h": "b" * 64},
                  now=datetime(2026, 10, 7, 12, 0, tzinfo=timezone(timedelta(hours=2))))
    return kwargs, calls


def test_single_snapshot_agrees_with_inventory_and_version(capture, tmp_path):
    kwargs, calls = capture
    snapshot, build_env = provenance.collect_provenance(**kwargs)
    metadata = snapshot.metadata()
    assert metadata["package_version"] == "1.2.3"
    assert metadata["maturity"] == "development"
    evidence = metadata["provenance"]
    assert evidence["build_time"] == "2026-10-07T10:00:00Z"
    assert evidence["build_id"] == "aaaaaaaaaaaa-20261007-100000"
    assert evidence["source"]["tree_state"] == "dirty"
    assert evidence["source"]["url"] == "https://github.com/dea-lang/dea"
    assert evidence["self_build"]["cflags"] == build_env["L1_CFLAGS"]
    assert "preparation_identity" not in evidence
    assert "do-not-record" not in snapshot.version_text()
    assert json.loads(snapshot.version_text().split("\n", 1)[1]) == metadata
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "VERSION").write_text(snapshot.version_text())
    record = inventory_payload(payload, metadata)
    assert record["provenance"] == evidence
    assert len(calls) == 6
    # A caller cannot mutate the snapshot after a compiler has embedded it.
    expected = snapshot.metadata()
    metadata["provenance"]["bootstrap"].clear()
    kwargs["preparation_inputs"].clear()
    assert snapshot.metadata() == expected
    assert snapshot.metadata()["provenance"]["preparation_inputs"] == {"include/dea_rt.h": "b" * 64}


def test_overlay_escapes_metadata_and_retains_identity_helpers(capture):
    kwargs, _ = capture
    snapshot, _ = provenance.collect_provenance(**kwargs)
    text = snapshot.build_info_module()
    assert 'return "1.2.3";' in text
    assert 'return "' + "a" * 40 + '+dirty";' in text
    assert 'return "gcc \\"quoted\\" \\\\ path caf\u00e9";' in text
    assert 'sb_append(sb, "\\nmaturity: development");' in text
    assert "func build_info_identity_with_version" in text
    assert "return true;" in text


@pytest.mark.parametrize("value", ["../bad", "a/b", "a\\b", "a b", "a\nb", 'a"b', "-flag", "caf\u00e9"])
def test_reject_unsafe_version(value):
    with pytest.raises(ValueError, match="DEA_DIST_VERSION"):
        provenance.package_version({"DEA_DIST_VERSION": value})


def test_version_default_ignores_other_release_sources():
    assert provenance.package_version({"DEA_DIST_VERSION": "  ", "GITHUB_REF_NAME": "v9.0.0"}) == "dev"
    assert provenance.package_version({"DEA_DIST_VERSION": " 1.2.3+test "}) == "1.2.3+test"


@pytest.mark.parametrize("system,machine,env,target", [
    ("Linux", "x86_64", {}, ("linux", "x86_64")),
    ("Darwin", "x86_64", {}, ("macos", "x86_64")),
    ("Darwin", "arm64", {}, ("macos", "arm64")),
    ("Windows", "AMD64", {"MSYSTEM": "UCRT64"}, ("windows", "x86_64")),
])
def test_host_matrix(system, machine, env, target):
    assert provenance.host_target(system, machine, env) == target


@pytest.mark.parametrize("system,machine,env", [
    ("Linux", "aarch64", {}), ("Windows", "AMD64", {}),
    ("Windows", "AMD64", {"MSYSTEM": "MINGW64"}), ("unknown", "x86_64", {}),
])
def test_reject_unsupported_host(system, machine, env):
    with pytest.raises(ValueError):
        provenance.host_target(system, machine, env)


@pytest.mark.parametrize("changes", [
    {"preparation_inputs": {}}, {"preparation_inputs": {"../escape": "b" * 64}},
    {"preparation_inputs": {"include/input.h": "bad"}}, {"preparation_identity": ""},
    {"now": datetime(2026, 10, 7)}, {"stage1_options": [None]}, {"stage1_options": "--flag"},
])
def test_invalid_inputs_fail_before_compiler_probes(capture, changes):
    kwargs, calls = capture
    with pytest.raises(ValueError):
        provenance.collect_provenance(**(kwargs | changes))
    assert not calls


def test_unknown_git_evidence_and_exported_identity(capture, monkeypatch):
    kwargs, _ = capture
    original = provenance.subprocess.check_output

    def command(args, **kw):
        if args[0] == "git":
            raise subprocess.CalledProcessError(128, args)
        return original(args, **kw)

    monkeypatch.setattr(provenance.subprocess, "check_output", command)
    snapshot, _ = provenance.collect_provenance(**kwargs, preparation_identity="service-owned-D")
    evidence = snapshot.metadata()["provenance"]
    assert evidence["source"]["revision"] == evidence["source"]["tree_state"] == "unknown"
    assert evidence["preparation_identity"] == "service-owned-D"


def test_wrong_seed_identity_does_not_fall_back(capture, monkeypatch):
    kwargs, _ = capture
    monkeypatch.setattr(provenance.subprocess, "check_output", lambda *args, **kw: "unrelated compiler")
    with pytest.raises(ValueError, match="identity"):
        provenance.collect_provenance(**kwargs)


def test_docs_and_compiler_reject_the_same_unsafe_version(monkeypatch):
    import docs_artifacts
    monkeypatch.setenv("DEA_DIST_VERSION", "../escape")
    with pytest.raises(ValueError, match="DEA_DIST_VERSION"):
        docs_artifacts.package_version(provenance.L1_ROOT)


def test_failed_compiler_probe_is_not_unknown_provenance(capture, monkeypatch):
    kwargs, _ = capture

    def fail(*args, **kw):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(provenance.subprocess, "check_output", fail)
    with pytest.raises(subprocess.CalledProcessError):
        provenance.collect_provenance(**kwargs)
