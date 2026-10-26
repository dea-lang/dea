# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""CI routing, explicit predecessor handoffs, and opt-in isolation regressions."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_bootstrap as ci
from dea_tooling import bootstrap


def workflow(relative):
    """Read workflow values as strings, preserving GitHub's on/off input choices."""
    return yaml.load((ROOT / relative).read_text(), Loader=yaml.BaseLoader)


def step(document, name):
    """Find one named workflow step."""
    return next(item for item in document if item.get("name") == name)


def toolchain(root, *, installed=False, windows=False):
    """Create a complete selected L1 layout for mocked native construction."""
    for relative in ("bin/l1c", "bin/l1c.native", "include/dea_rt.h", "include/l1_real.h",
                     "interfaces/std/types.l1m"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    if windows:
        (root / "bin/l1c.cmd").write_text("Windows fixture")
    if installed:
        manifest = root / "share/dea/l1/install-manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text('{"level":"l1","state":"complete"}')
    return root / "bin/l1c"


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    root = tmp_path / "checkout with spaces"
    for level in ("l0", "l1", "l2"):
        (root / level).mkdir(parents=True)
    calls = []

    def run(command, *, env, **kwargs):
        calls.append((command, dict(env)))
        if command[0] == "make":
            if command[2] == str(root / "l1") and command[3] == "build":
                toolchain(root / "l1/build/dea")
            if command[2] == str(root / "l1") and command[3] == "install":
                toolchain(Path(command[4].removeprefix("PREFIX=")), installed=True)
            return subprocess.CompletedProcess(command, 0)
        assert command[-1] == "--version"
        level = "L0" if "l0c-stage2" in command[0] else "L1"
        return subprocess.CompletedProcess(command, 0, f"Dea language / {level} compiler\n", "")

    monkeypatch.setattr(ci.subprocess, "run", run)
    return root, calls


def make_calls(calls):
    """Return actual Make invocations and their bootstrap environments."""
    return [(command, env) for command, env in calls if command[0] == "make"]


def test_completed_predecessors_are_reused_without_construction(checkout):
    root, calls = checkout
    l0 = root / "l0/build/dea/bin/l0c-stage2"
    l0.parent.mkdir(parents=True)
    l0.write_text("fixture")
    l1 = toolchain(root / "l1/build/dea")
    output = root / "outputs"
    source = {"CI_MAKE_TARGET": "test-ci", "GITHUB_OUTPUT": str(output)}
    ci.run_delegate("l0", source, root=root)
    ci.run_delegate("l1", {**source, "CI_BOOTSTRAP_L0C": str(l0)}, root=root)
    ci.run_delegate("l2", {**source, "CI_BOOTSTRAP_L0C": str(l0), "CI_BOOTSTRAP_L1C": str(l1),
                           "CI_BOOTSTRAP_MODE": "development"}, root=root)
    makes = make_calls(calls)
    assert [command[2:] for command, _ in makes] == [[str(root / level), "test-ci"]
                                                     for level in ("l0", "l1", "l2")]
    assert makes[1][1]["L1_BOOTSTRAP_L0C"] == str(l0)
    assert makes[2][1]["L2_BOOTSTRAP_L1C"] == str(l1)
    assert makes[2][1]["L2_BOOTSTRAP_MODE"] == "development"
    assert output.read_text().splitlines() == [f"bootstrap_l0c={l0}", f"bootstrap_l1c={l1}"]


@pytest.mark.parametrize("mode", ["installed", "development"])
def test_missing_l1_is_prepared_once_in_selected_mode(checkout, mode):
    root, calls = checkout
    temporary = root / "runner temporary"
    ci.run_delegate("l2", {"CI_MAKE_TARGET": "test-ci", "CI_BOOTSTRAP_MODE": mode,
                           "RUNNER_TEMP": str(temporary)}, root=root)
    makes = make_calls(calls)
    assert len(makes) == 2
    assert makes[0][0][2:4] == [str(root / "l1"), "build" if mode == "development" else "install"]
    assert makes[1][0][2:] == [str(root / "l2"), "test-ci"]
    prefix = root / "l1/build/dea" if mode == "development" else temporary / "l2-bootstrap-l1"
    assert makes[1][1]["L2_BOOTSTRAP_L1C"] == str(prefix / "bin/l1c")


@pytest.mark.parametrize("level,variable", [("l1", "CI_BOOTSTRAP_L0C"), ("l2", "CI_BOOTSTRAP_L1C")])
def test_invalid_explicit_handoff_fails_without_make(checkout, level, variable):
    root, calls = checkout
    with pytest.raises(RuntimeError):
        ci.run_delegate(level, {"CI_MAKE_TARGET": "test-ci", variable: str(root / "missing"),
                                "CI_BOOTSTRAP_MODE": "development"}, root=root)
    assert make_calls(calls) == []


def test_no_compiler_output_does_not_construct_one(checkout):
    root, calls = checkout
    output = root / "outputs"
    ci.run_delegate("l1", {"CI_MAKE_TARGET": "test-docgen", "GITHUB_OUTPUT": str(output)}, root=root)
    assert [command[3:] for command, _ in make_calls(calls)] == [["test-docgen"]]
    assert output.read_text() == "bootstrap_l1c=\n"


def test_failed_validation_does_not_publish_handoff(checkout, monkeypatch):
    root, _ = checkout
    output = root / "outputs"
    toolchain(root / "l1/build/dea")
    monkeypatch.setattr(ci, "make_target", lambda *args: (_ for _ in ()).throw(RuntimeError("failed suite")))
    with pytest.raises(RuntimeError, match="failed suite"):
        ci.run_delegate("l1", {"CI_MAKE_TARGET": "test-ci", "GITHUB_OUTPUT": str(output)}, root=root)
    assert not output.exists()


@pytest.mark.parametrize("windows", [False, True])
def test_handoff_uses_native_host_launcher(checkout, monkeypatch, windows):
    root, calls = checkout
    compiler = toolchain(root / "selected toolchain", windows=True)
    monkeypatch.setattr(bootstrap, "is_windows_host", lambda: windows)
    ci.run_delegate("l2", {"CI_MAKE_TARGET": "test-ci", "CI_BOOTSTRAP_L1C": str(compiler),
                           "CI_BOOTSTRAP_MODE": "development"}, root=root)
    selected = compiler.with_suffix(".cmd") if windows else compiler
    assert calls[0][0] == [str(selected), "--version"]
    assert make_calls(calls)[0][1]["L2_BOOTSTRAP_L1C"] == str(selected)


@pytest.mark.skipif(os.name == "nt", reason="POSIX routing script exercised on native POSIX runners")
@pytest.mark.parametrize("default", ["false", "true"])
@pytest.mark.parametrize("event", ["push", "pull_request"])
@pytest.mark.parametrize("changed,expected", [("l2/compiler/src/parser.l1", True), ("scripts/helper.py", True),
                                             ("l0/compiler/source.l0", False), ("l1/compiler/source.l0", False),
                                             ("work/proposals/example.md", False)])
def test_automatic_l2_routing(tmp_path, default, event, changed, expected):
    result = route(tmp_path, default=default, event=event, changed=changed)
    assert result["run_l2"] == str(default == "true" and expected).lower()
    assert result["run_l0"] == str(changed.startswith(("l0/", "scripts/"))).lower()
    assert result["run_l1"] == str(changed.startswith(("l1/", "scripts/"))).lower()


@pytest.mark.skipif(os.name == "nt", reason="POSIX routing script exercised on native POSIX runners")
@pytest.mark.parametrize("default", ["false", "true"])
@pytest.mark.parametrize("manual", ["default", "on", "off"])
def test_manual_override(tmp_path, default, manual):
    result = route(tmp_path, default=default, event="workflow_dispatch", manual=manual)
    enabled = manual == "on" or (manual == "default" and default == "true")
    assert result["run_l2"] == str(enabled).lower()
    assert result["run_l0"] == result["run_l1"] == "true"


@pytest.mark.skipif(os.name == "nt", reason="POSIX routing script exercised on native POSIX runners")
@pytest.mark.parametrize("default", ["false", "true"])
@pytest.mark.parametrize("missing", ["base", "endpoints"])
def test_unavailable_diff_respects_l2_default(tmp_path, default, missing):
    result = route(tmp_path, default=default, event="push", missing=missing)
    assert result["run_l2"] == default
    assert result["run_l0"] == result["run_l1"] == "true"


@pytest.mark.skipif(os.name == "nt", reason="POSIX routing script exercised on native POSIX runners")
@pytest.mark.parametrize("event", ["push", "pull_request"])
@pytest.mark.parametrize("changed", [
    "l1/compiler/src/parser.l0",
    "l1/compiler/docgen/l1_docgen.py",
    "l1/compiler/shared/l1/stdlib/std/unit.l1",
    "l1/compiler/shared/runtime/include/dea_rt.h",
    "l1/compiler/support/compiler_support.c",
    "l1/compiler/tests/parser_test.l0",
    "l1/docs/README.md",
    "l1/tests/test_docgen_filters.py",
    "l1/scripts/docs/templates/doxyfile.in",
    "l1/scripts/gen_docs.py",
    "l1/scripts/docs_artifacts.py",
    "l1/scripts/productization_provenance.py",
    "l1/scripts/docker_wine.py",
    "l1/Makefile",
    "l1/pyproject.toml",
    "l1/README.md",
    "l1/README-WINDOWS.md",
    "l1/AGENTS.md",
    "l1/CLAUDE.md",
    "tools/m.css/documentation/doxygen.py",
    "scripts/dea_tooling/bootstrap.py",
    "pyproject.toml",
    "uv.lock",
    "Makefile",
    "README.md",
    "CONTRIBUTING.md",
    "CLAUDE.md",
    "THIRD_PARTY_NOTICES",
    ".github/workflows/l1-docs-validate.yml",
    ".github/workflows/ci.yml",
    ".github/actions/l1-ci/action.yml",
])
def test_l1_docs_routing_selects_reference_inputs(tmp_path, event, changed):
    result = route(tmp_path, default="false", event=event, changed=changed)
    assert result["run_l1_docs"] == "true"


@pytest.mark.skipif(os.name == "nt", reason="POSIX routing script exercised on native POSIX runners")
@pytest.mark.parametrize("event", ["push", "pull_request"])
@pytest.mark.parametrize("changed", [
    "l0/compiler/stage1_py/l0_ast.py",
    "l0/compiler/shared/l0/stdlib/std/unit.l0",
    "l0/docs/README.md",
    "l2/compiler/src/parser.l1",
    "l2/compiler/docgen/l2_docgen.py",
    "l2/docs/README.md",
    "l1/work/plans/features/example.md",
    "work/proposals/example.md",
    "l1/tests/test_parser.py",
    "editors/vscode/package.json",
])
def test_l1_docs_routing_ignores_unrelated_changes(tmp_path, event, changed):
    result = route(tmp_path, default="true", event=event, changed=changed)
    assert result["run_l1_docs"] == "false"


@pytest.mark.skipif(os.name == "nt", reason="POSIX routing script exercised on native POSIX runners")
@pytest.mark.parametrize("changed,expected", [
    ("l0/compiler/stage1_py/l0_ast.py", "true"),
    ("l0/compiler/shared/l0/stdlib/std/unit.l0", "true"),
    ("l0/docs/README.md", "true"),
    ("l1/compiler/src/parser.l0", "false"),
    ("l1/compiler/docgen/l1_docgen.py", "false"),
    ("l2/compiler/src/parser.l1", "false"),
    ("tools/m.css/documentation/doxygen.py", "true"),
    ("scripts/dea_tooling/bootstrap.py", "false"),
    (".github/workflows/l1-docs-validate.yml", "true"),
    (".github/actions/l1-ci/action.yml", "false"),
])
def test_l1_docs_routing_preserves_l0_docs_selection(tmp_path, changed, expected):
    result = route(tmp_path, default="false", event="push", changed=changed)
    assert result["run_docs"] == expected


@pytest.mark.skipif(os.name == "nt", reason="POSIX routing script exercised on native POSIX runners")
@pytest.mark.parametrize("default", ["false", "true"])
@pytest.mark.parametrize("manual", ["default", "on", "off"])
def test_manual_runs_select_l1_docs_independently_of_l2(tmp_path, default, manual):
    result = route(tmp_path, default=default, event="workflow_dispatch", manual=manual)
    assert result["run_l1_docs"] == result["run_docs"] == "true"


@pytest.mark.skipif(os.name == "nt", reason="POSIX routing script exercised on native POSIX runners")
@pytest.mark.parametrize("default", ["false", "true"])
@pytest.mark.parametrize("missing", ["base", "endpoints"])
def test_unavailable_diff_selects_l1_docs(tmp_path, default, missing):
    result = route(tmp_path, default=default, event="push", missing=missing)
    assert result["run_l1_docs"] == result["run_docs"] == "true"


def route(tmp_path, *, default, event, changed="", manual="default", missing=""):
    """Execute the actual workflow routing script with controlled Git answers."""
    document = workflow(".github/workflows/ci.yml")
    script = step(document["jobs"]["route-levels"]["steps"], "Decide level routing")["run"]
    git = tmp_path / "git"
    git.write_text('#!/bin/sh\ncase "$1" in\n'
                   'rev-parse) [ "$DIFF_MISSING" != endpoints ];;\n'
                   'diff) printf "%s\\n" "$DIFF_CHANGED";;\nesac\n')
    git.chmod(0o755)
    output = tmp_path / "output"
    env = {**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
           "EVENT_NAME": event, "L2_CI_DEFAULT_ENABLED": default, "INPUT_RUN_L2_CI": manual,
           "BEFORE_SHA": "" if missing == "base" else "base", "PUSH_SHA": "head",
           "PR_BASE_SHA": "base", "PR_HEAD_SHA": "head", "GITHUB_OUTPUT": str(output),
           "DIFF_CHANGED": changed, "DIFF_MISSING": missing}
    result = subprocess.run(["bash", "-eu", "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return dict(line.split("=", 1) for line in output.read_text().splitlines())


def test_workflow_handoffs_and_isolation_are_wired():
    unified = workflow(".github/workflows/ci.yml")
    assert unified["env"]["L2_CI_DEFAULT_ENABLED"] == "false"
    inputs = unified["on"]["workflow_dispatch"]["inputs"]
    assert inputs["run_l2_ci"]["options"] == ["default", "on", "off"]
    assert inputs["l2_run_isolation"]["default"] == "false"
    steps = unified["jobs"]["unified"]["steps"]
    l0, l1, l2 = [step(steps, f"Run {level} CI delegate") for level in ("L0", "L1", "L2")]
    assert l1["with"]["bootstrap_l0c"] == "${{ steps.l0-delegate.outputs.bootstrap_l0c }}"
    assert l2["with"]["bootstrap_l1c"] == "${{ steps.l1-delegate.outputs.bootstrap_l1c }}"
    assert l2["with"]["bootstrap_mode"] == "development"
    assert "run_l2 == 'true'" in l2["if"]
    for level in ("l0", "l1"):
        action = workflow(f".github/actions/{level}-ci/action.yml")
        assert f"bootstrap_{level}c" in action["outputs"]
        for item in action["runs"]["steps"]:
            if item["name"].startswith(f"Run {level.upper()} Make target"):
                assert f"scripts/ci_bootstrap.py {level}" in item["run"]
    action = workflow(".github/actions/l2-ci/action.yml")
    assert action["inputs"]["bootstrap_mode"]["default"] == "installed"
    assert action["inputs"]["run_isolation"]["default"] == "false"
    isolation = step(action["runs"]["steps"], "Verify Linux checkout and bootstrap isolation")
    assert isolation["if"] == "runner.os == 'Linux' && inputs.run_isolation == 'true'"
    assert "l1/Dockerfile" in isolation["run"] and "test-isolation" in isolation["run"]
    standalone = workflow(".github/workflows/l2-ci.yml")
    for trigger in ("workflow_call", "workflow_dispatch"):
        assert standalone["on"][trigger]["inputs"]["run_isolation"]["default"] == "false"
    delegate = step(standalone["jobs"]["bootstrap"]["steps"], "Run L2 CI delegate")
    assert delegate["with"]["run_isolation"] == "${{ inputs.run_isolation }}"


@pytest.mark.parametrize("filename,job", [
    ("ci.yml", "unified"),
    ("l0-ci.yml", "test-extended"),
    ("l1-ci.yml", "bootstrap"),
    ("l2-ci.yml", "bootstrap"),
    ("l0-docs-build.yml", "build-docs"),
    ("l0-docs-validate.yml", "validate-docs"),
    ("l1-docs-build.yml", "build-docs"),
    ("l1-docs-validate.yml", "validate-docs"),
    ("l1-productization-acceptance.yml", "docs"),
])
def test_doxygen_setup_precedes_every_native_or_documentation_consumer(filename, job):
    steps = workflow(f".github/workflows/{filename}")["jobs"][job]["steps"]
    setups = [i for i, item in enumerate(steps) if item.get("uses") == "./.github/actions/setup-doxygen"]
    assert len(setups) == 1
    setup_index = setups[0]
    checkout = next(i for i, item in enumerate(steps) if item.get("uses", "").startswith("actions/checkout@"))
    consumers = [i for i, item in enumerate(steps)
                 if item.get("uses", "").startswith("./.github/actions/l")
                 or "gen_docs.py" in item.get("run", "") or "docs-artifacts" in item.get("run", "")]
    assert consumers and checkout < setup_index < min(consumers)
    assert not any("apt-get install" in item.get("run", "") and "doxygen" in item["run"] for item in steps)
    if any(item.get("uses", "").startswith("./.github/actions/l") for item in steps):
        windows = step(steps, "Show Windows environment")
        assert 'command -v doxygen' in windows["run"]
        assert 'test "$(doxygen --version)"' in windows["run"]
        assert "steps.doxygen.outputs.version" in windows["run"]
        assert windows["shell"] == "msys2 {0}"
        assert steps[setup_index]["id"] == "doxygen"


def test_doxygen_action_regressions():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable")
    result = subprocess.run([node, "--test", str(ROOT / ".github/actions/setup-doxygen/setup.test.cjs")],
                            cwd=ROOT, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
