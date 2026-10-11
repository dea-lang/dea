# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Regression checks for explicit upstream ownership and implementation routing."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import pytest

L2_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(L2_ROOT / "scripts"))
import build_l2c as builder
sys.path.insert(0, str(L2_ROOT / "compiler/scripts"))
import test_runner_common as runner
sys.path.insert(0, str(L2_ROOT / "compiler/tests"))
import l2c_cleanup_policy_ice_test as cleanup_ice
from dea_tooling import bootstrap


def test_no_implicit_or_development_bootstrap(monkeypatch, tmp_path):
    monkeypatch.delenv("L2_BOOTSTRAP_L1C", raising=False)
    with pytest.raises(RuntimeError, match="installed canonical L1"):
        builder.resolve_bootstrap()
    fake = tmp_path / "bin/l1c"
    fake.parent.mkdir()
    fake.write_text("development binary")
    monkeypatch.setenv("L2_BOOTSTRAP_L1C", str(fake))
    with pytest.raises(RuntimeError, match="complete installed L1 prefix"):
        builder.resolve_bootstrap()


def test_implementation_environment_does_not_borrow_target_or_sibling_inputs():
    source = {"L0_HOME": "sibling", "L1_HOME": "sibling", "L1_SYSTEM": "sibling/stdlib",
              "L1_BUILD_DIR": "sibling/build", "L1_RUNTIME_LIB": "sibling/lib",
              "L1_CC": "compiler with spaces", "L2_HOME": "owned", "PATH": "host tools"}
    result = builder.bootstrap_environment(source)
    assert result == {"L1_CC": "compiler with spaces", "L2_HOME": "owned", "PATH": "host tools",
                      "L1_STDLIB_CACHE": str(L2_ROOT / "build/dea/bootstrap-cache")}
    assert source["L1_HOME"] == "sibling"


def test_implementation_and_target_fixtures_have_distinct_languages(monkeypatch, tmp_path):
    bootstrap = tmp_path / "installed prefix/bin/l1c"
    monkeypatch.setattr(runner, "resolve_bootstrap", lambda: bootstrap)
    monkeypatch.setattr(runner, "implementation_support_args", lambda path: [])
    cases = runner.discover_implementation_tests()
    array = next(case for case in cases if case.name == "array_test")
    assert array.path.suffix == ".l1"
    command = runner.build_normal_test_command(array, tmp_path / "build")
    assert str(bootstrap) in command and str(array.path) in command
    assert "compiler/src" in command
    assert all(f.path.suffix == ".l2" for f in runner.CHILD_TRACE_FIXTURES)
    assert all(case.path.is_relative_to(L2_ROOT) for case in cases)
    assert not any("parity" in case.name or "stage" in case.name for case in cases)


def test_build_directory_and_native_paths_preserve_spaces(tmp_path):
    relative = "build/with spaces"
    layout = builder.normalize_l2_build_dir(relative)
    assert layout.bin_dir == L2_ROOT / relative / "bin"
    with pytest.raises(ValueError, match="inside the L2 repository"):
        builder.normalize_l2_build_dir(str(tmp_path))
    with pytest.raises(ValueError, match="empty"):
        builder.normalize_l2_build_dir("")


def test_explicit_implementation_flags_precede_compiler_runtime_defaults(monkeypatch):
    monkeypatch.setattr(builder, "host_compiler", lambda env: "/host C compiler")
    env, mode = builder.compiler_build_env({"L1_CFLAGS": "-DDEA_RT_CHECK_BASIC", "L2_COMPILER_RT_UNCHECKED": "1"})
    assert mode == ["--check-basic"]
    assert env["L1_CC"] == "/host C compiler"
    assert "-D_RT_QUARANTINE_MAX_COUNT=256" in env["L1_CFLAGS"]
    assert "L2_CFLAGS" not in env


def test_unusable_installed_bootstrap_has_actionable_diagnostic(monkeypatch, tmp_path):
    prefix = tmp_path / "installed prefix"
    manifest = prefix / "share/dea/l1/install-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"level": "l1", "state": "complete"}')
    monkeypatch.setenv("L2_BOOTSTRAP_L1C", str(prefix / "bin/l1c"))
    with pytest.raises(RuntimeError, match="did not start as a valid installed L1 compiler"):
        builder.resolve_bootstrap()


@pytest.mark.parametrize("windows", [False, True])
def test_cleanup_policy_ice_selects_host_bootstrap_launcher(monkeypatch, tmp_path, windows):
    """Use the installed command wrapper when invoking the L1 bootstrap."""

    compiler = tmp_path / "installed prefix/bin/l1c"
    compiler.parent.mkdir(parents=True)
    compiler.write_text("native wrapper")
    compiler.with_suffix(".cmd").write_text("Windows wrapper")
    monkeypatch.setattr(cleanup_ice, "bootstrap_compiler", lambda: compiler)
    monkeypatch.setattr(cleanup_ice, "build_support_objects", lambda *args, **kwargs: [])
    monkeypatch.setattr(bootstrap, "is_windows_host", lambda: windows)
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, b"", b"[ICE-1080]")

    monkeypatch.setattr(cleanup_ice.subprocess, "run", run)
    cleanup_ice.run_ice_case("missing_enum_info_ice", "module main;", "[ICE-1080]", tmp_path)
    expected = compiler.with_suffix(".cmd") if windows else compiler
    assert commands[0][0] == str(expected)
