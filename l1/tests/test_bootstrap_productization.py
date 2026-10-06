#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Fixture-based ownership, interruption, and prefix launcher regressions.

Shell probes stand in for the package compiler. Native installed-state and real
self-hosted package acceptance belong to the later compiler/install milestones.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest

L1_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(L1_ROOT / "scripts"))
import productization_inventory as inventory
import productization_launchers as launchers
from build_stage1_l1c import normalize_l1_build_dir
from dea_tooling.launchers import render_repo_env_script, render_prefix_native_wrapper


@pytest.fixture
def metadata():
    return {"package_version": "dev", "maturity": "development", "os": "linux", "arch": "x86_64",
            "provenance": {"source": "fixture", "bootstrap": "fixture", "build": "fixture"}}


@pytest.fixture
def payload(tmp_path):
    root = tmp_path / "payload inputs"
    (root / "bin").mkdir(parents=True)
    (root / "bin/probe").write_bytes(b"executable fixture\n")
    (root / "bin/probe").chmod(0o755)
    (root / "include").mkdir()
    (root / "include/input.h").write_bytes(b"public header fixture\n")
    return root


def tree_bytes(root):
    """Capture owned and unrelated file contents for preflight immutability checks."""
    if not root.exists():
        return {}
    return {path.relative_to(root).as_posix():
            ("alias", os.readlink(path)) if path.is_symlink() else ("file", path.read_bytes())
            for path in root.rglob("*") if path.is_symlink() or path.is_file()}


def write_manifest(prefix, record):
    path = prefix / inventory.MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")


def test_prefix_layout_is_separate_and_disjoint(tmp_path, payload):
    working = tmp_path / "source"
    working.mkdir()
    assert inventory.resolve_prefix("../prefix with spaces", working_dir=working) == tmp_path / "prefix with spaces"
    for candidate in ("", working, working.parent, payload, payload / "nested", payload.parent):
        with pytest.raises(inventory.InventoryError):
            inventory.resolve_prefix(candidate, working_dir=working, protected_paths=(payload,))
    with pytest.raises(ValueError, match="inside the L1 repository"):
        normalize_l1_build_dir(str(tmp_path / "external build"))


def test_install_listing_modes_and_relocation(tmp_path, payload, metadata):
    prefix = tmp_path / "installed"
    record = inventory.install_payload(payload, prefix, metadata)
    (prefix / "unrelated cache").mkdir()
    (prefix / "unrelated cache/user.o").write_bytes(b"unowned")
    expected = ["bin/probe", "include/input.h", inventory.MANIFEST_PATH]
    assert inventory.list_installed(prefix) == expected
    assert record["entries"][-1] == {"path": inventory.MANIFEST_PATH, "kind": "manifest", "mode": 0o644}
    assert inventory.read_inventory(prefix) == record
    relocated = tmp_path / "relocated prefix with spaces"
    prefix.rename(relocated)
    inventory.verify_payload(relocated, inventory.read_inventory(relocated))
    assert inventory.list_installed(relocated) == expected
    (relocated / "include/input.h").write_bytes(b"tampered")
    # Listing is metadata-only; artifact acceptance owns full digest checks.
    assert inventory.list_installed(relocated) == expected
    with pytest.raises(inventory.InventoryError, match="verification failed"):
        inventory.verify_payload(relocated, record)


def test_reinstall_removes_only_owned_files(tmp_path, payload, metadata):
    prefix = tmp_path / "installed"
    inventory.install_payload(payload, prefix, metadata)
    (prefix / "include/unrelated.h").write_bytes(b"preserve")
    (payload / "include/input.h").unlink()
    (payload / "include/replacement.h").write_bytes(b"new")
    metadata["package_version"] = "snapshot-fixture"
    record = inventory.install_payload(payload, prefix, metadata)
    assert not (prefix / "include/input.h").exists()
    assert (prefix / "include/unrelated.h").read_bytes() == b"preserve"
    assert record["package_version"] == "snapshot-fixture"
    inventory.verify_payload(prefix, record)


@pytest.mark.parametrize("collision", ["bin/probe", "include", inventory.MANIFEST_PATH])
def test_collisions_fail_before_mutation(tmp_path, payload, metadata, collision):
    prefix = tmp_path / "installed"
    path = prefix / collision
    path.parent.mkdir(parents=True)
    path.write_bytes(b"unowned content")
    before = tree_bytes(prefix)
    with pytest.raises(inventory.InventoryError):
        inventory.install_payload(payload, prefix, metadata)
    assert tree_bytes(prefix) == before


@pytest.mark.parametrize("unsafe", ["/absolute", "../escape", "a/../escape", "a//b", "a/./b",
                                    "C:/absolute", "a\\b", "a/CON.txt", "trailing.", "nul", "a\n"])
def test_unsafe_inventory_paths(unsafe, payload, metadata):
    record = inventory.inventory_payload(payload, metadata)
    record["entries"][0]["path"] = unsafe
    with pytest.raises(inventory.InventoryError):
        inventory.validate_inventory(record)


@pytest.mark.parametrize("change", ["schema", "stage", "state", "mode", "digest", "duplicate", "case",
                                    "parent", "missing-manifest", "provenance", "extra", "version"])
def test_malformed_metadata_rejected_unchanged(tmp_path, payload, metadata, change):
    prefix = tmp_path / "installed"
    record = inventory.install_payload(payload, prefix, metadata)
    if change == "schema":
        record["schema_version"] = True
    elif change == "stage":
        record["stage"] = 1
    elif change == "state":
        record["state"] = "unknown"
    elif change == "mode":
        record["entries"][0]["mode"] = 0o777
    elif change == "digest":
        record["entries"][0]["sha256"] = "bad"
    elif change == "duplicate":
        record["entries"].append(copy.deepcopy(record["entries"][0]))
    elif change == "case":
        entry = {**record["entries"][0], "path": "Bin/other"}
        record["entries"].append(entry)
    elif change == "parent":
        record["entries"].append({**record["entries"][0], "path": "bin"})
    elif change == "missing-manifest":
        record["entries"].pop()
    elif change == "provenance":
        record["provenance"] = {}
    elif change == "extra":
        record["unexpected"] = True
    elif change == "version":
        record["package_version"] = "../unsafe"
    write_manifest(prefix, record)
    before = tree_bytes(prefix)
    with pytest.raises(inventory.InventoryError):
        inventory.list_installed(prefix)
    with pytest.raises(inventory.InventoryError):
        inventory.install_payload(payload, prefix, metadata)
    assert tree_bytes(prefix) == before


def test_missing_unreadable_and_duplicate_json_metadata(tmp_path, payload, metadata, monkeypatch):
    prefix = tmp_path / "installed"
    with pytest.raises(inventory.InventoryError, match="repair or retry"):
        inventory.list_installed(prefix)
    inventory.install_payload(payload, prefix, metadata)
    manifest = prefix / inventory.MANIFEST_PATH
    read = Path.read_text

    def unreadable(path, *args, **kwargs):
        if path == manifest:
            raise PermissionError("fixture unreadable metadata")
        return read(path, *args, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(Path, "read_text", unreadable)
        with pytest.raises(inventory.InventoryError, match="unreadable metadata"):
            inventory.list_installed(prefix)
    manifest.write_text('{"state":"complete","state":"incomplete"}')
    with pytest.raises(inventory.InventoryError, match="duplicate inventory field"):
        inventory.list_installed(prefix)


@pytest.mark.skipif(os.name == "nt", reason="requires POSIX special files")
def test_metadata_special_file_rejected_without_opening(tmp_path, payload, metadata):
    prefix = tmp_path / "installed"
    manifest = prefix / inventory.MANIFEST_PATH
    manifest.parent.mkdir(parents=True)
    os.mkfifo(manifest)
    with pytest.raises(inventory.InventoryError, match="regular file"):
        inventory.list_installed(prefix)
    with pytest.raises(inventory.InventoryError, match="regular file"):
        inventory.install_payload(payload, prefix, metadata)


@pytest.mark.skipif(os.name == "nt", reason="Windows aliases use file copies")
def test_aliases_and_substituted_parents(tmp_path, payload, metadata):
    (payload / "bin/alias").symlink_to("probe")
    prefix = tmp_path / "installed"
    record = inventory.install_payload(payload, prefix, metadata)
    assert os.readlink(prefix / "bin/alias") == "probe"
    inventory.verify_payload(prefix, record)
    outside = tmp_path / "outside"
    (prefix / "include").rename(outside)
    (prefix / "include").symlink_to(outside, target_is_directory=True)
    before = tree_bytes(outside)
    with pytest.raises(inventory.InventoryError, match="unsafe destination parent"):
        inventory.install_payload(payload, prefix, metadata)
    assert tree_bytes(outside) == before


@pytest.mark.skipif(os.name == "nt", reason="Windows aliases use file copies")
@pytest.mark.parametrize("target", ["../../outside", "/absolute", "missing", "alias", "../include"])
def test_invalid_source_aliases(tmp_path, payload, metadata, target):
    (payload / "bin/alias").symlink_to(target)
    prefix = tmp_path / "installed"
    with pytest.raises(inventory.InventoryError):
        inventory.install_payload(payload, prefix, metadata)
    assert not prefix.exists()


@pytest.mark.parametrize("publication,operation", [(1, "write"), (1, "replace"), (2, "write"), (2, "replace")])
def test_metadata_publication_interruptions(tmp_path, payload, metadata, monkeypatch, publication, operation):
    prefix = tmp_path / "installed"
    inventory.install_payload(payload, prefix, metadata)
    before = tree_bytes(prefix)
    (payload / "bin/probe").write_bytes(b"replacement")
    original = inventory.json.dump if operation == "write" else inventory.os.replace
    calls = 0

    def interrupted(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == publication:
            if operation == "write":
                args[1].write('{"partial":')
            raise OSError("injected metadata publication interruption")
        return original(*args, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(inventory.json if operation == "write" else inventory.os,
                        "dump" if operation == "write" else "replace", interrupted)
        with pytest.raises(OSError, match="injected"):
            inventory.install_payload(payload, prefix, metadata)
    if publication == 1:
        assert tree_bytes(prefix) == before
        assert inventory.read_inventory(prefix)["state"] == "complete"
    else:
        assert inventory.read_inventory(prefix, require_complete=False)["state"] == "incomplete"
        with pytest.raises(inventory.InventoryError, match="incomplete"):
            inventory.list_installed(prefix)
    assert not list((prefix / Path(inventory.MANIFEST_PATH).parent).glob(".install-manifest-*"))
    record = inventory.install_payload(payload, prefix, metadata)
    inventory.verify_payload(prefix, record)


@pytest.mark.parametrize("operation", ["copy", "delete"])
def test_payload_interruption_retains_union_for_different_retry(tmp_path, payload, metadata, monkeypatch, operation):
    prefix = tmp_path / "installed"
    inventory.install_payload(payload, prefix, metadata)
    (payload / "include/input.h").unlink()
    (payload / "include/intermediate.h").write_bytes(b"intermediate")
    original_copy = shutil.copyfile
    original_unlink = Path.unlink

    def interrupted_copy(source, destination, *args, **kwargs):
        original_copy(source, destination, *args, **kwargs)
        if Path(destination).name == "intermediate.h":
            raise OSError("injected payload interruption")

    def interrupted_delete(path, *args, **kwargs):
        if path == prefix / "include/input.h":
            raise OSError("injected payload interruption")
        return original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as context:
        if operation == "copy":
            context.setattr(shutil, "copyfile", interrupted_copy)
        else:
            context.setattr(Path, "unlink", interrupted_delete)
        with pytest.raises(OSError, match="injected"):
            inventory.install_payload(payload, prefix, metadata)
    assert inventory.read_inventory(prefix, require_complete=False)["state"] == "incomplete"
    with pytest.raises(inventory.InventoryError, match="incomplete"):
        inventory.list_installed(prefix)
    (payload / "include/intermediate.h").unlink()
    (payload / "include/final.h").write_bytes(b"final")
    record = inventory.install_payload(payload, prefix, metadata)
    assert not (prefix / "include/input.h").exists()
    assert not (prefix / "include/intermediate.h").exists()
    inventory.verify_payload(prefix, record)


def test_verification_failure_keeps_recoverable_state(tmp_path, payload, metadata, monkeypatch):
    prefix = tmp_path / "installed"
    original_copy = shutil.copyfile

    def corrupt_copy(source, destination, *args, **kwargs):
        original_copy(source, destination, *args, **kwargs)
        Path(destination).write_bytes(b"corrupt")

    with monkeypatch.context() as context:
        context.setattr(shutil, "copyfile", corrupt_copy)
        with pytest.raises(inventory.InventoryError, match="verification failed"):
            inventory.install_payload(payload, prefix, metadata)
    assert inventory.read_inventory(prefix, require_complete=False)["state"] == "incomplete"
    inventory.install_payload(payload, prefix, metadata)


def test_inventory_source_destination_overlap(tmp_path, payload, metadata):
    before = tree_bytes(payload)
    for prefix in (payload, payload / "nested", payload.parent):
        with pytest.raises(inventory.InventoryError, match="overlaps"):
            inventory.install_payload(payload, prefix, metadata)
    assert tree_bytes(payload) == before


def test_unreadable_payload_directory_cannot_be_silently_omitted(tmp_path, payload, metadata, monkeypatch):
    scandir = os.scandir

    def unreadable(directory):
        if Path(directory) == payload / "include":
            raise PermissionError("injected unreadable payload directory")
        return scandir(directory)

    monkeypatch.setattr(os, "scandir", unreadable)
    prefix = tmp_path / "installed"
    with pytest.raises(inventory.InventoryError, match="cannot inventory payload directory"):
        inventory.install_payload(payload, prefix, metadata)
    assert not prefix.exists()


def test_substituted_hard_link_cannot_modify_inputs(tmp_path, payload, metadata):
    prefix = tmp_path / "installed"
    inventory.install_payload(payload, prefix, metadata)
    destination = prefix / "include/input.h"
    destination.unlink()
    os.link(payload / "include/input.h", destination)
    before = tree_bytes(prefix)
    with pytest.raises(inventory.InventoryError, match="hard links"):
        inventory.install_payload(payload, prefix, metadata)
    assert tree_bytes(prefix) == before
    assert (payload / "include/input.h").read_bytes() == b"public header fixture\n"


@pytest.mark.parametrize("operation", ["write", "replace"])
def test_first_inventory_publication_failure_has_no_payload(tmp_path, payload, metadata, monkeypatch, operation):
    prefix = tmp_path / "installed"

    def interrupted(*args, **kwargs):
        if operation == "write":
            args[1].write("partial metadata")
        raise OSError("injected first publication failure")

    with monkeypatch.context() as context:
        context.setattr(inventory.json if operation == "write" else inventory.os,
                        "dump" if operation == "write" else "replace", interrupted)
        with pytest.raises(OSError, match="injected"):
            inventory.install_payload(payload, prefix, metadata)
    assert tree_bytes(prefix) == {}
    inventory.install_payload(payload, prefix, metadata)


def write_probe_prefix(prefix, label):
    """Generate a relocated shell fixture exercising wrapper environment selection."""
    bin_dir = prefix / "bin"
    bin_dir.mkdir(parents=True)
    scripts = {"l1c": launchers.native_wrapper(), "l1c-stage2": launchers.native_wrapper(),
               "l1-env.sh": launchers.env_script(),
               "l1c-stage2.native": '#!/bin/sh\nprintf "%s\\n" '
               f'"{label}" "$L1_HOME" "${{L1_BUILD_DIR-unset}}" '
               '"$L1_SYSTEM" "$L1_RUNTIME_LIB" "$L1_STDLIB_CACHE" "$@"\nexit "${PROBE_EXIT-0}"\n'}
    for name, text in scripts.items():
        path = bin_dir / name
        path.write_text(text)
        path.chmod(0o755)


@pytest.mark.skipif(os.name == "nt", reason="POSIX execution; native Windows probes run separately")
@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_relocated_launchers_and_activation(tmp_path, shell):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")
    a = tmp_path / "prefix A with spaces"
    b = tmp_path / "prefix B with spaces"
    write_probe_prefix(a, "A")
    write_probe_prefix(b, "B")
    relocated = tmp_path / "relocated A with spaces"
    a.rename(relocated)
    a = relocated
    repo = tmp_path / "repo fixture"
    (repo / "compiler").mkdir(parents=True)
    (repo / "build/dea/bin").mkdir(parents=True)
    repo_env = repo / "build/dea/bin/l1-env.sh"
    repo_env.write_text(render_repo_env_script(repo_relative_from_bin="../../..", build_relative_from_repo="build/dea",
                                              env_script_name="l1-env.sh", env_script_label="l1-env",
                                              home_var_name="L1_HOME", compiler_env_var="L1_CC"))
    env = {**os.environ, "L1_HOME": "stale repo", "L1_BUILD_DIR": "stale build", "L1_SYSTEM": "explicit system",
           "L1_RUNTIME_LIB": "explicit runtime", "L1_STDLIB_CACHE": "explicit cache"}
    for name in ("l1c", "l1c-stage2"):
        result = subprocess.run([str(a / "bin" / name), "argument with spaces"], cwd=tmp_path,
                                env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == ["A", str(a), "unset", "explicit system", "explicit runtime",
                                               "explicit cache", "argument with spaces"]
        result = subprocess.run([str(a / "bin" / name)], cwd=tmp_path,
                                env={**env, "PROBE_EXIT": "17"}, capture_output=True)
        assert result.returncode == 17
    q = shlex.quote
    sequence = [a / "bin/l1-env.sh", b / "bin/l1-env.sh", a / "bin/l1-env.sh", repo_env,
                a / "bin/l1-env.sh", repo_env, a / "bin/l1-env.sh"]
    script = "\n".join(f"source {q(str(path))}" for path in sequence)
    script += '\nprintf "%s\\n" "$L1_HOME" "${L1_BUILD_DIR-unset}" "$PATH" "$(command -v l1c)"\nl1c\n'
    base_path = env["PATH"]
    env["PATH"] = f"{b / 'bin'}:{a / 'bin'}:{a / 'bin'}::{base_path}"
    result = subprocess.run([executable, "-fc", script], cwd=tmp_path, env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[:2] == [str(a), "unset"]
    assert lines[2].split(":") == [str(a / "bin"), str(repo_env.parent), str(b / "bin"), "", *base_path.split(":")]
    assert lines[3] == str(a / "bin/l1c")
    assert lines[4:] == ["A", str(a), "unset", "explicit system", "explicit runtime", "explicit cache"]
    result = subprocess.run([executable, str(a / "bin/l1-env.sh")], cwd=tmp_path, env=env, capture_output=True)
    assert result.returncode != 0 and b"must be sourced" in result.stderr


def test_l1_adapters_preserve_shared_prefix_defaults():
    before = render_prefix_native_wrapper(home_var_name="L0_HOME", native_name="l0c-stage2.native")
    assert 'if [ -z "${L0_HOME:-}" ]' in before
    assert "unset L1_BUILD_DIR" in launchers.native_wrapper()
    assert before == render_prefix_native_wrapper(home_var_name="L0_HOME", native_name="l0c-stage2.native")
    cmd = launchers.native_cmd_wrapper()
    assert "setlocal EnableExtensions DisableDelayedExpansion" in cmd
    assert cmd.endswith('set "_L1_EXITCODE=%ERRORLEVEL%"\nendlocal & exit /b %_L1_EXITCODE%\n')
    assert "MSYS2_TOOLCHAIN_BIN" in launchers.env_cmd_script()


@pytest.mark.skipif(os.name != "nt", reason="requires native cmd.exe")
@pytest.mark.parametrize("exitcode", [0, 17])
def test_native_cmd_wrapper_restores_parent_environment(tmp_path, exitcode):
    prefix = tmp_path / "prefix with spaces"
    (prefix / "bin").mkdir(parents=True)
    shutil.copyfile(os.environ["COMSPEC"], prefix / "bin/probe.exe")
    wrapper = prefix / "bin/l1c.cmd"
    wrapper.write_text(launchers.native_cmd_wrapper(native_name="probe.exe"))
    child = tmp_path / "child probe.cmd"
    child.write_text(f'@echo off\necho CHILD_HOME=%L1_HOME%\necho CHILD_BUILD=%L1_BUILD_DIR%\nexit /b {exitcode}\n')
    driver = tmp_path / "driver.cmd"
    driver.write_text(f'@echo off\ncall "{wrapper}" /d /c call "{child}"\n'
                      'echo RETURN=%ERRORLEVEL%\necho HOME=%L1_HOME%\necho BUILD=%L1_BUILD_DIR%\n'
                      'echo SCRIPT=%SCRIPT_DIR%\necho PREFIX=%PREFIX_ROOT%\n')
    env = {**os.environ, "L1_HOME": "sentinel home", "L1_BUILD_DIR": "sentinel build",
           "SCRIPT_DIR": "sentinel script", "PREFIX_ROOT": "sentinel prefix"}
    result = subprocess.run([os.environ["COMSPEC"], "/d", "/c", str(driver)], env=env,
                            cwd=tmp_path, text=True, capture_output=True)
    assert "CHILD_HOME=" + str(prefix).replace("/", "\\") in result.stdout
    assert "CHILD_BUILD=\n" in result.stdout
    assert f"RETURN={exitcode}" in result.stdout
    assert "HOME=sentinel home" in result.stdout and "BUILD=sentinel build" in result.stdout
    assert "SCRIPT=sentinel script" in result.stdout and "PREFIX=sentinel prefix" in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="requires native cmd.exe")
@pytest.mark.parametrize("toolchain_position", ["missing", "first", "last", "selected"])
@pytest.mark.parametrize("base_path", ["", r"C:\ordinary!%literal%\bin;C:\Program Files (x86)\bin", os.environ["PATH"]])
def test_native_cmd_activation_switches_prefixes(tmp_path, toolchain_position, base_path):
    a = tmp_path / "prefix A with spaces"
    b = tmp_path / "prefix B with spaces"
    for prefix in (a, b):
        (prefix / "bin").mkdir(parents=True)
        (prefix / "bin/l1-env.cmd").write_text(launchers.env_cmd_script())
    toolchain = a / "bin" if toolchain_position == "selected" else tmp_path / "toolchain bin"
    toolchain.mkdir(exist_ok=True)
    driver = tmp_path / "activation.cmd"
    driver.write_text('@echo off\n' + "\n".join(
        f'call "{prefix / "bin/l1-env.cmd"}"' for prefix in (a, b, a)
    ) + '\necho HOME=%L1_HOME%\necho PATH=%PATH%\n'
      'if defined L1_BUILD_DIR exit /b 1\necho SCRIPT=%SCRIPT_DIR%\n')
    # MSYS2 Python can render Windows paths with forward slashes. CMD resolves
    # its own script location with backslashes, so use that spelling for PATH.
    a_bin = str(a / "bin").replace("/", "\\")
    b_bin = str(b / "bin").replace("/", "\\")
    toolchain_bin = str(toolchain).replace("/", "\\")
    entries = [b_bin, a_bin, a_bin.upper(), "", *base_path.split(";")]
    remaining = [b_bin, "", *base_path.split(";")]
    if toolchain_position == "first":
        entries.insert(0, toolchain_bin.upper())
        remaining.insert(1, toolchain_bin.upper())
    elif toolchain_position == "last":
        entries.append(toolchain_bin)
        remaining.append(toolchain_bin)
    elif toolchain_position == "missing":
        remaining.insert(1, toolchain_bin)
    env = {**os.environ, "L1_HOME": "sentinel home", "L1_BUILD_DIR": "sentinel build",
           "SCRIPT_DIR": "sentinel script", "MSYS2_TOOLCHAIN_BIN": toolchain_bin,
           "PATH": ";".join(entries)}
    result = subprocess.run([os.environ["COMSPEC"], "/d", "/c", str(driver)], env=env,
                            cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "HOME=" + str(a).replace("/", "\\") in result.stdout
    actual_path = next(line.removeprefix("PATH=") for line in result.stdout.splitlines() if line.startswith("PATH="))
    assert actual_path.split(";") == [a_bin, *remaining]
    assert "SCRIPT=sentinel script" in result.stdout
