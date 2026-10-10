# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Cleanup regressions through real Makefiles and disposable filesystem trees."""

from pathlib import Path, PurePosixPath, PureWindowsPath
import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from dea_tooling import cleanup


@pytest.fixture(params=[("l0", "DEA_BUILD_DIR"), ("l1", "L1_BUILD_DIR"), ("l2", "L2_BUILD_DIR")])
def checkout(tmp_path, request):
    level, variable = request.param
    if not (ROOT / level / "Makefile").is_file():
        pytest.skip(f"{level} is absent in this isolated checkout")
    root = tmp_path / "checkout with spaces" / level
    root.mkdir(parents=True)
    shutil.copy2(ROOT / level / "Makefile", root / "Makefile")
    helpers = root.parent / "scripts/dea_tooling"
    helpers.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/dea_tooling/cleanup.py", helpers / "cleanup.py")
    for directory in ("compiler", "docs", "scripts", "tests", "examples", "work", "docker"):
        put(root / directory / "source-sentinel", "source")
    put(root.parent / "sibling/source-sentinel", "sibling")
    return root, variable


def put(path, content="generated"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def run_make(checkout, target, selected="build/dea", *, success=True):
    root, variable = checkout
    env = {k: v for k, v in os.environ.items() if k not in {"MAKEFLAGS", "MFLAGS", "MAKELEVEL"}}
    command = ["make", "--no-print-directory", "-j4", target, f"{variable}={selected}",
               f"PYTHON={sys.executable}"]
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    assert (root / "compiler/source-sentinel").read_text() == "source"
    assert (root.parent / "sibling/source-sentinel").read_text() == "sibling"
    return result


def test_standard_cleanup_preserves_custom_tree_and_sources(checkout):
    root, _ = checkout
    for name in ("build/dea/bin/compiler", "build/.hidden/file", "build/.stamp", "a.out", "a.exe",
                 "compiler/a.out", "compiler/tests/.tmp-probe", "compiler/stage2_l0/tests/.tmp-probe"):
        put(root / name)
    put(root / "out/custom/bin/compiler")
    run_make(checkout, "clean", "out/custom")
    assert list((root / "build").iterdir()) == []
    assert (root / "out/custom/bin/compiler").is_file()
    assert not (root / "a.out").exists()
    assert not (root / "compiler/tests/.tmp-probe").exists()
    run_make(checkout, "clean", "out/custom")


def test_cleanup_reports_groups_and_isolated_files(checkout):
    root, _ = checkout
    for name in ("build/dea/bin/compiler", "build/.hidden/file", "a.out", "compiler/a.exe",
                 "compiler/tests/.tmp-one", "compiler/tests/.tmp-two"):
        put(root / name)
    result = run_make(checkout, "clean")
    reports = [line for line in result.stdout.splitlines() if line.startswith("cleanup:")]
    assert reports == [
        f"cleanup: removing contents of {str(root / 'build')!r} (including hidden entries)",
        f"cleanup: removing {str(root / 'a.out')!r}",
        f"cleanup: removing {str(root / 'compiler/a.exe')!r}",
        f"cleanup: removing files matching {str(root / 'compiler/tests/.tmp*')!r}",
    ]
    assert ".tmp-one" not in result.stdout
    assert "bin/compiler" not in result.stdout
    repeated = run_make(checkout, "clean")
    assert "cleanup: nothing to remove" in repeated.stdout
    assert "cleanup: removing" not in repeated.stdout


@pytest.mark.parametrize("absolute", [False, True])
def test_full_cleanup_removes_complete_custom_tree(checkout, absolute):
    root, _ = checkout
    custom = root / "out/custom space"
    for name in ("bin/compiler", "lib/runtime.a", "runtime/object.o", "include/dea_rt.h", "cache/key", ".hidden"):
        put(custom / name)
    put(root / "build/.hidden")
    put(root / "out/other/keep")
    selected = str(custom if absolute else custom.relative_to(root))
    result = run_make(checkout, "clean-all", selected)
    assert f"cleanup: removing {str(custom)!r}" in result.stdout
    assert f"cleanup: removing contents of {str(root / 'build')!r}" in result.stdout
    assert "bin/compiler" not in result.stdout
    assert not custom.exists()
    assert not (root / "build/.hidden").exists()
    assert (root / "out/other/keep").exists()
    run_make(checkout, "clean-all", selected)


@pytest.mark.parametrize("selected", ["", ".", "..", "../sibling", "/", "compiler", "compiler/generated",
                                       "docs", "scripts", "tests", "examples", "work", "docker",
                                       "Compiler/generated", ".git", "out/../compiler", "Makefile"])
def test_invalid_full_cleanup_fails_before_deleting_standard_outputs(checkout, selected):
    root, _ = checkout
    put(root / "build/keep")
    result = run_make(checkout, "clean-all", selected, success=False)
    assert "cleanup:" in result.stderr
    assert "cleanup: removing" not in result.stdout
    assert (root / "build/keep").exists()


def test_external_absolute_directory_rejected(checkout, tmp_path):
    outside = tmp_path / "external tree"
    put(outside / "keep")
    run_make(checkout, "clean-all", str(outside), success=False)
    assert (outside / "keep").exists()


def symlink_or_skip(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")


@pytest.mark.parametrize("alias", ["build", "out"])
def test_directory_alias_is_rejected_before_cleanup(checkout, alias):
    root, _ = checkout
    symlink_or_skip(root / alias, root.parent / "sibling")
    run_make(checkout, "clean-all", f"{alias}/nested", success=False)
    assert (root / alias).is_symlink()


def test_generated_symlink_is_unlinked_without_following(checkout):
    root, _ = checkout
    (root / "build").mkdir()
    symlink_or_skip(root / "build/alias", root.parent / "sibling")
    run_make(checkout, "clean")
    assert not (root / "build/alias").is_symlink()


def test_runtime_or_build_only_cleanup(checkout):
    root, variable = checkout
    custom = root / "out/custom space"
    for name in ("runtime/object", "lib/archive", "include/dea_rt.h", "include/l1_real.h", "include/keep", "bin/compiler"):
        put(custom / name)
    put(root / "build/keep")
    target = "clean-dea-build" if variable == "DEA_BUILD_DIR" else "clean-runtime"
    result = run_make(checkout, target, "out/custom space")
    reported = (custom,) if target == "clean-dea-build" else (
        custom / "runtime", custom / "lib", custom / "include/dea_rt.h", custom / "include/l1_real.h")
    assert [line for line in result.stdout.splitlines() if line.startswith("cleanup:")] == [
        f"cleanup: removing {str(path)!r}" for path in reported]
    if target == "clean-dea-build":
        assert not custom.exists()
    else:
        assert not (custom / "runtime").exists()
        assert not (custom / "lib").exists()
        assert not (custom / "include/dea_rt.h").exists()
        assert not (custom / "include/l1_real.h").exists()
        assert (custom / "include/keep").exists()
        assert (custom / "bin/compiler").exists()
    assert (root / "build/keep").exists()
    run_make(checkout, target, "out/custom space")
    run_make(checkout, target, "", success=False)
    run_make(checkout, target, "compiler", success=False)


def test_runtime_include_alias_rejects_before_removing_objects(checkout):
    root, variable = checkout
    if variable == "DEA_BUILD_DIR":
        pytest.skip("L0 has no clean-runtime target")
    selected = root / "out/custom"
    put(selected / "runtime/keep")
    symlink_or_skip(selected / "include", root / "compiler")
    run_make(checkout, "clean-runtime", "out/custom", success=False)
    assert (selected / "runtime/keep").exists()


@pytest.mark.parametrize("path", [PurePosixPath("out/custom space"), PureWindowsPath(r"out\custom space"),
                                   PureWindowsPath(r"out/custom space\nested")])
def test_portable_custom_namespace(path):
    cleanup.validate_relative_directory(path)


@pytest.mark.parametrize("path", [PurePosixPath("compiler/out"), PureWindowsPath(r"Compiler\out"),
                                   PureWindowsPath(r"docs/mixed\out"), PureWindowsPath(r"C:\out\custom"),
                                   PureWindowsPath(r"\\host\share\out"), PureWindowsPath(r"..\out"),
                                   PurePosixPath("/out/custom"), PureWindowsPath(r"C:out")])
def test_portable_unsafe_namespace(path):
    with pytest.raises(ValueError):
        cleanup.validate_relative_directory(path)


def test_deletion_failure_is_reported(tmp_path, monkeypatch, capsys):
    put(tmp_path / "build/dea/keep")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SELECTED_BUILD", "build/dea")
    monkeypatch.setattr(sys, "argv", ["cleanup", "clean-all", "--build-variable", "SELECTED_BUILD"])

    def denied(path):
        raise PermissionError("fixture denial")

    monkeypatch.setattr(cleanup.shutil, "rmtree", denied)
    assert cleanup.main() == 1
    output = capsys.readouterr()
    assert "fixture denial" in output.err
    assert "cleanup: removing contents of" in output.out
    assert "nothing to remove" not in output.out
    assert (tmp_path / "build/dea/keep").exists()


def test_l0_direct_cleanup_api_validates_and_propagates_errors(tmp_path, monkeypatch):
    # Exercise the legacy direct API as well as the shared Make entrypoint.
    if not (ROOT / "l0/scripts/dist_tools_lib.py").is_file():
        pytest.skip("L0 is absent in this isolated checkout")
    sys.path.insert(0, str(ROOT / "l0/scripts"))
    spec = importlib.util.spec_from_file_location("cleanup_l0_dist_tools", ROOT / "l0/scripts/dist_tools_lib.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    put(tmp_path / "compiler/keep")
    layout = module.normalize_dea_build_dir("compiler")
    with pytest.raises(ValueError):
        module.remove_dea_build_tree(layout)
    put(tmp_path / "out/custom/keep")
    layout = module.normalize_dea_build_dir("out/custom")

    def denied(path):
        raise PermissionError("fixture denial")

    monkeypatch.setattr(cleanup.shutil, "rmtree", denied)
    with pytest.raises(PermissionError, match="fixture denial"):
        module.remove_dea_build_tree(layout)


def test_default_full_cleanup_removes_hidden_build_entries(checkout):
    root, _ = checkout
    put(root / "build/dea/.hidden")
    put(root / "build/.outside-selected")
    run_make(checkout, "clean-all")
    assert not (root / "build/dea").exists()
    assert not (root / "build/.outside-selected").exists()


def test_transient_parent_alias_rejects_before_standard_cleanup(checkout):
    root, _ = checkout
    put(root / "build/keep")
    symlink_or_skip(root / "compiler/tests", root.parent / "sibling")
    run_make(checkout, "clean", success=False)
    assert (root / "build/keep").exists()


def test_literal_special_characters_in_build_directory(tmp_path):
    custom = tmp_path / "out/custom ' ; & $(literal)"
    put(custom / "bin/compiler")
    cleanup.clean_level(tmp_path, "clean-build", str(custom))
    assert not custom.exists()


def test_unexpected_executable_directory_is_preserved(checkout):
    root, _ = checkout
    put(root / "build/keep")
    put(root / "a.out/keep")
    run_make(checkout, "clean", success=False)
    assert (root / "a.out/keep").exists()
    assert (root / "build/keep").exists()


def test_runtime_include_file_rejects_before_removing_objects(tmp_path):
    put(tmp_path / "out/runtime/keep")
    put(tmp_path / "out/include")
    with pytest.raises(ValueError, match="must be a directory"):
        cleanup.clean_level(tmp_path, "clean-runtime", "out")
    assert (tmp_path / "out/runtime/keep").exists()
