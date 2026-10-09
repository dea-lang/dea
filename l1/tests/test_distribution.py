# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Distribution round trips, hostile archives, and failure-safe publication."""

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from types import SimpleNamespace
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dist_toolchain as dist
import distribution_archive as archives
import smoke_dist
from docs_artifacts import create_bundle, unpack_bundle
from productization_inventory import MANIFEST_PATH, install_payload, read_inventory
from productization_provenance import PackageProvenance


@pytest.fixture
def package(tmp_path):
    payload = tmp_path / "payload"
    payload.mkdir()
    for name in archives.BASE_FILES - {MANIFEST_PATH, "VERSION"}:
        path = payload / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
        path.chmod(0o755 if name.startswith("bin/") else 0o644)
    for name in archives.DOCUMENTS:
        source = ROOT / "docs/user" / Path(name).name
        shutil.copyfile(source, payload / name)
    support = {}
    for name in ("interfaces/std/io.l1m", "shared/l1/stdlib/std/io.l1", "shared/runtime/src/dea_rt_io.c",
                 "shared/runtime/internal/private.h", "include/dea_rt.h", "include/l1_real.h"):
        path = payload / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("support\n")
        support[name] = archives.digest(path)
    metadata = {"package_version": "dev", "maturity": "development", "os": "linux", "arch": "x86_64",
                "provenance": {"source": {"revision": "fixture", "tree_state": "clean"},
                               "build_time": "2026-10-08T09:10:11Z", "preparation_inputs": support}}
    (payload / "VERSION").write_text(PackageProvenance(json.dumps(metadata)).version_text())
    docs = tmp_path / "docs"
    (docs / "html").mkdir(parents=True)
    (docs / "pdf").mkdir()
    (docs / "html/index.html").write_text('<a href="../pdf/dea_l1_stage2_api_reference.pdf">PDF</a>')
    (docs / "pdf/dea_l1_stage2_api_reference.pdf").write_bytes(b"%PDF-1.7\nfixture\n%%EOF\n")
    bundle = tmp_path / "docs.tar.gz"
    source = {**metadata["provenance"]["source"], "input_digest": "a" * 64}
    create_bundle(docs, bundle, stage="stage2", version="dev", source=source,
                  tools={key: "fixture" for key in ("doxygen", "pdflatex", "python", "mcss")})
    unpack_bundle(bundle, tmp_path / "docs-unpacked", stage="stage2", version="dev", source=source)
    shutil.copytree(tmp_path / "docs-unpacked/dea-l1-stage2-autodocs", payload / archives.DOCS_PATH)
    prefix = tmp_path / "prefix"
    install_payload(payload, prefix, metadata)
    return payload, prefix, metadata, bundle


@pytest.mark.parametrize("windows", [False, True])
def test_archive_roundtrip_curated_contents_and_modes(package, tmp_path, windows):
    payload, prefix, metadata, _ = package
    if windows:
        metadata["os"] = "windows"
        for name in archives.WINDOWS_FILES:
            (payload / name).write_text("@echo off\n")
            (payload / name).chmod(0o755)
        (payload / "VERSION").write_text(PackageProvenance(json.dumps(metadata)).version_text())
        install_payload(payload, prefix, metadata)
    path = tmp_path / ("dist.zip" if windows else "dist.tar.gz")
    archives.write_archive(prefix, path, windows=windows)
    extracted = archives.extract_archive(path, tmp_path / "unrelated extraction")
    assert read_inventory(extracted) == read_inventory(prefix)
    if os.name != "nt":
        assert (extracted / "bin/l1c").stat().st_mode & 0o111
    assert not (extracted / "bin/l1c-stage1").exists()


def test_tar_modes_come_from_inventory_not_host_stat(package, tmp_path, monkeypatch):
    """Windows synthesizes writable modes even after chmod to portable modes."""
    _, prefix, _, _ = package
    original = tarfile.TarFile.gettarinfo

    def windows_modes(self, *args, **kwargs):
        info = original(self, *args, **kwargs)
        info.mode = 0o777 if info.isdir() else 0o666
        return info

    monkeypatch.setattr(tarfile.TarFile, "gettarinfo", windows_modes)
    path = tmp_path / "portable.tar.gz"
    archives.write_archive(prefix, path, windows=False)
    expected = {entry["path"]: entry["mode"] for entry in read_inventory(prefix)["entries"]}
    with tarfile.open(path) as archive:
        for member in archive.getmembers():
            assert member.mode == (0o755 if member.isdir() else expected[member.name.removeprefix("dea-l1/")])
    archives.extract_archive(path, tmp_path / "extracted")


@pytest.mark.parametrize("problem", ["extra", "directory", "excluded", "digest", "mode", "incomplete", "version",
                                    "docs-stage", "docs-pdf", "docs-source", "docs-remote", "docs-link", "readme-link",
                                    "preparation"])
def test_distribution_rejects_invalid_payload(package, problem):
    payload, prefix, metadata, _ = package
    if problem in {"extra", "directory"}:
        if problem == "extra":
            (prefix / "unowned").write_text("scratch")
        else:
            (prefix / "empty-scratch").mkdir()
    elif problem == "digest":
        (prefix / "bin/l1c").write_text("tamper")
    elif problem == "mode":
        if os.name == "nt":
            pytest.skip("Windows does not enforce POSIX executable modes")
        (prefix / "bin/l1c").chmod(0o644)
    elif problem == "incomplete":
        manifest = prefix / MANIFEST_PATH
        record = json.loads(manifest.read_text())
        record.update(state="incomplete", previous_entries=record["entries"])
        manifest.write_text(json.dumps(record))
    else:
        if problem == "excluded":
            (payload / "retained.c").write_text("scratch")
        elif problem == "version":
            (payload / "VERSION").write_text("other")
        elif problem == "readme-link":
            (payload / "README.md").write_text("[checkout](../../compiler/README.md)")
        elif problem == "preparation":
            metadata["provenance"]["preparation_inputs"] = {}
        else:
            root = payload / archives.DOCS_PATH
            doc = json.loads((root / "manifest.json").read_text())
            if problem == "docs-stage":
                doc["stage"] = 1
            elif problem == "docs-pdf":
                doc["full_pdf"] = False
            elif problem == "docs-source":
                doc["source"]["revision"] = "different"
            else:
                value = '<script src="https://example.com/remote.js"></script>' if problem == "docs-remote" else '<a href="missing.html">missing</a>'
                (root / "html/index.html").write_text(value)
                doc["files"]["html/index.html"] = archives.digest(root / "html/index.html")
            (root / "manifest.json").write_text(json.dumps(doc))
        install_payload(payload, prefix, metadata)
    with pytest.raises(ValueError):
        archives.verify_distribution(prefix)


@pytest.mark.parametrize("windows", [False, True])
@pytest.mark.parametrize("problem", ["traversal", "absolute", "drive", "backslash", "duplicate", "root", "alias",
                                    "parent-alias", "case", "device", "extra", "hardlink"])
def test_hostile_members_rejected_before_any_extraction(package, tmp_path, windows, problem):
    _, prefix, _, _ = package
    path = tmp_path / ("hostile.zip" if windows else "hostile.tar.gz")
    archives.write_archive(prefix, path, windows=windows)
    name = {"traversal": "dea-l1/../../escape", "absolute": "/escape", "drive": "C:/escape",
            "backslash": "dea-l1/..\\escape", "duplicate": "dea-l1/VERSION", "root": "other/file",
            "alias": "dea-l1/bin/escape", "parent-alias": "dea-l1/bin", "case": "dea-l1/version",
            "device": "dea-l1/device", "extra": "dea-l1/unowned", "hardlink": "dea-l1/hard"}[problem]
    if windows:
        with zipfile.ZipFile(path, "a") as archive:
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            kind = 0o120777 if problem in {"alias", "parent-alias"} else 0o020644 if problem == "device" else 0o100644
            info.external_attr = kind << 16
            archive.writestr(info, "../../escape" if problem in {"alias", "parent-alias"} else "data")
    else:
        original = tmp_path / "original.tar.gz"
        path.rename(original)
        with tarfile.open(original) as source, tarfile.open(path, "w:gz") as archive:
            for member in source.getmembers():
                archive.addfile(member, source.extractfile(member) if member.isfile() else None)
            info = tarfile.TarInfo(name)
            info.mode = 0o644
            if problem in {"alias", "parent-alias", "hardlink"}:
                info.type = tarfile.LNKTYPE if problem == "hardlink" else tarfile.SYMTYPE
                info.linkname = "../../escape"
                archive.addfile(info)
            elif problem == "device":
                info.type = tarfile.CHRTYPE
                archive.addfile(info)
            else:
                info.size = 4
                archive.addfile(info, io.BytesIO(b"data"))
    destination = tmp_path / "extracted"
    with pytest.raises(ValueError):
        archives.extract_archive(path, destination)
    assert not destination.exists()
    assert not (tmp_path / "escape").exists()


@pytest.fixture
def builder(package, tmp_path, monkeypatch):
    payload, _, metadata, bundle = package
    root = tmp_path / "checkout/l1"
    root.mkdir(parents=True)
    monkeypatch.setattr(dist, "REPO_ROOT", root)
    def install(prefix, env, *, make):
        assert Path(env["DOCS_ARTIFACT"]).read_bytes() == bundle.read_bytes()
        assert Path(env["DOCS_ARTIFACT"]) != bundle
        install_payload(payload, Path(prefix), metadata)
        return Path(prefix)
    monkeypatch.setattr(dist, "install", install)
    return {"DOCS_ARTIFACT": str(bundle), "DIST_RESULT": str(tmp_path / "result.json")}


def test_distribution_result_matches_exact_archive(builder):
    path = dist.distribute(builder)
    assert path.name == "dea-l1-lang_dev_linux-x86_64_20261008-091011.tar.gz"
    result = json.loads(Path(builder["DIST_RESULT"]).read_text())
    assert result["schema_version"] == 1 and result["stage"] == 2
    assert result["archive_path"] == str(path)
    assert result["archive_sha256"] == archives.digest(path)
    assert result["archive_size"] == path.stat().st_size
    assert result["docs_bundle_sha256"] == archives.digest(Path(builder["DOCS_ARTIFACT"]))
    # Same name must not clobber a prior archive, or retain its success record.
    original = path.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        dist.distribute(builder)
    assert path.read_bytes() == original
    assert not Path(builder["DIST_RESULT"]).exists()


def test_result_is_optional_and_publication_replaces_closed_json(builder, monkeypatch):
    destination = Path(builder["DIST_RESULT"])
    records = []
    replace = dist.os.replace
    def inspect(source, target):
        if Path(target) == destination:
            assert Path(source).parent == destination.parent
            record = json.loads(Path(source).read_text())
            assert Path(record["archive_path"]).is_file()
            assert not destination.exists()
            records.append(record)
        return replace(source, target)
    monkeypatch.setattr(dist.os, "replace", inspect)
    first = dist.distribute(builder)
    assert records and json.loads(destination.read_text()) == records[0]
    first.unlink()
    destination.unlink()
    assert dist.distribute({"DOCS_ARTIFACT": builder["DOCS_ARTIFACT"]}).is_file()
    assert not destination.exists()


@pytest.mark.parametrize("step", ["docs", "install", "verify", "write", "extract", "archive-publication", "result-write", "result-publication"])
def test_failed_invocation_never_leaves_stale_success(builder, monkeypatch, step):
    result = Path(builder["DIST_RESULT"])
    result.write_text('{"archive_path":"stale"}')
    def failure(*args, **kwargs):
        raise OSError("injected failure")
    if step == "docs":
        builder["DOCS_ARTIFACT"] = ""
    elif step in {"install", "verify", "write", "extract"}:
        monkeypatch.setattr(dist, {"install": "install", "verify": "verify_distribution",
                                  "write": "write_archive", "extract": "extract_archive"}[step], failure)
    elif step == "result-write":
        original = dist.json.dump
        def dump(record, *args, **kwargs):
            if "archive_path" in record:
                return failure()
            return original(record, *args, **kwargs)
        monkeypatch.setattr(dist.json, "dump", dump)
    else:
        original = dist.os.replace
        def replace(source, destination):
            if (step == "result-publication" and Path(destination) == result or
                    step == "archive-publication" and str(destination).endswith(".tar.gz")):
                return failure()
            return original(source, destination)
        monkeypatch.setattr(dist.os, "replace", replace)
    with pytest.raises((ValueError, OSError)):
        dist.distribute(builder)
    assert not result.exists()
    assert not list(result.parent.glob(".dist-result-*"))
    assert not list((dist.REPO_ROOT / "dist").glob(".dist-*"))


@pytest.mark.parametrize("target", ["source", "docs", "symlink", "hardlink", "relative", "archive"])
def test_result_preflight_preserves_unsafe_destinations(builder, tmp_path, target):
    source = dist.REPO_ROOT / "source.json"
    source.write_text("preserve")
    result = tmp_path / "unsafe.json"
    if target == "source":
        result = source
    elif target == "docs":
        result.write_text("preserve")
        builder["DOCS_ARTIFACT"] = str(result)
    elif target == "symlink":
        result.symlink_to(source)
    elif target == "hardlink":
        os.link(source, result)
    elif target == "relative":
        result = Path("relative.json")
    else:
        result = tmp_path / "archive.tar.gz"
        result.write_text("preserve")
    builder["DIST_RESULT"] = str(result)
    with pytest.raises(ValueError):
        dist.distribute(builder)
    assert source.read_text() == "preserve"
    if result.exists():
        assert result.read_text() == "preserve"


@pytest.mark.parametrize("key_style", [str.upper, str.lower, str.title])
def test_windows_smoke_environment_ignores_variable_name_case(tmp_path, monkeypatch, key_style):
    """Copied Windows environments retain case-insensitive selector semantics."""
    compiler = tmp_path / "host compiler/bin/gcc.exe"
    system_root = tmp_path / "Windows directory"
    source = {key_style(key): value for key, value in {
        "SYSTEMROOT": str(system_root), "PATH": "checkout/l1/build/dea/bin",
        "L1_CC": str(compiler), "L1_HOME": "checkout/l1", "L0_HOME": "checkout/l0",
        "PYTHONPATH": "checkout/python", "VIRTUAL_ENV": "checkout/.venv",
        "MAKEFLAGS": "inherited", "COMSPEC": "cmd.exe",
    }.items()}
    original = dict(source)
    monkeypatch.setattr(smoke_dist, "os", SimpleNamespace(name="nt", pathsep=";"))
    monkeypatch.setattr(smoke_dist.shutil, "which", lambda name: str(compiler) if name == str(compiler) else None)

    env = smoke_dist.smoke_environment(tmp_path, source)

    assert source == original
    assert env["SYSTEMROOT"] == str(system_root)
    assert env["PATH"].split(";") == [str(compiler.resolve().parent), str(system_root / "System32")]
    assert env["L1_CC"] == env["L1_RUNTIME_CC"] == str(compiler.resolve())
    assert env["L1_HOME"] == str(tmp_path / "absent-source")
    assert env["COMSPEC"] == "cmd.exe"
    assert not {"L0_HOME", "PYTHONPATH", "VIRTUAL_ENV", "MAKEFLAGS"} & env.keys()
    assert all(key == key.upper() for key in env)


def test_smoke_relocates_and_rejects_corruption_before_execution(package, tmp_path, monkeypatch):
    _, prefix, _, _ = package
    path = tmp_path / "dist.tar.gz"
    archives.write_archive(prefix, path, windows=False)
    called = []
    def run(prefix, work, env):
        called.append(prefix)
        assert " " in prefix.name and not (prefix.parent / "extracted/dea-l1").exists()
        assert work != prefix and not work.is_relative_to(ROOT)
        assert not any("dea/l1/build" in value for value in env["PATH"].split(os.pathsep))
    monkeypatch.setattr(smoke_dist, "run_smoke", run)
    smoke_dist.smoke(path, dict(os.environ))
    assert called and not called[0].exists()
    called.clear()
    original = tmp_path / "original.tar.gz"
    path.rename(original)
    with tarfile.open(original) as source, tarfile.open(path, "w:gz") as archive:
        for member in source.getmembers():
            if member.name == "dea-l1/bin/l1c":
                data = b"tampered"
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            else:
                archive.addfile(member, source.extractfile(member) if member.isfile() else None)
    with pytest.raises(ValueError, match="verification failed"):
        smoke_dist.smoke(path, dict(os.environ))
    assert not called


@pytest.mark.parametrize("windows", [False, True])
def test_safe_relative_launcher_alias_survives_roundtrip(package, tmp_path, windows):
    payload, prefix, metadata, _ = package
    (payload / "bin/l1c").unlink()
    try:
        (payload / "bin/l1c").symlink_to("l1c-stage2")
    except OSError:
        pytest.skip("symlink creation unavailable")
    install_payload(payload, prefix, metadata)
    path = tmp_path / ("alias.zip" if windows else "alias.tar.gz")
    archives.write_archive(prefix, path, windows=windows)
    extracted = archives.extract_archive(path, tmp_path / "extracted")
    assert (extracted / "bin/l1c").is_symlink()
    assert os.readlink(extracted / "bin/l1c") == "l1c-stage2"


@pytest.mark.parametrize("target,variable", [("dist", "DOCS_ARTIFACT"), ("smoke-dist", "ARCHIVE")])
def test_public_commands_fail_without_build_on_missing_input(tmp_path, target, variable):
    result = tmp_path / "result ' ; &.json"
    result.write_text("stale")
    run = subprocess.run(["make", "--no-print-directory", "-s", target, f"{variable}=",
                          f"DIST_RESULT={result}", f"PYTHON={sys.executable}", "L1_BOOTSTRAP_L0C=/absent"],
                         cwd=ROOT, capture_output=True, text=True)
    assert run.returncode != 0 and variable in run.stderr and not run.stdout
    if target == "dist":
        assert not result.exists()
    dry = subprocess.run(["make", "--no-print-directory", "-n", target, "PYTHON=/absent"],
                         cwd=ROOT, capture_output=True, text=True)
    assert dry.returncode == 0
