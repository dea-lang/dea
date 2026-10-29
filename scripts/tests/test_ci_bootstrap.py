# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""CI routing, explicit predecessor handoffs, and opt-in isolation regressions."""

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
    (".github/workflows/l1-docs-validate.yml", "false"),
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


def route(tmp_path, *, default, event, changed="", manual="default", missing="", merge_missing=False):
    """Execute the actual workflow routing script with controlled Git answers."""
    document = workflow(".github/workflows/ci.yml")
    script = step(document["jobs"]["route-levels"]["steps"], "Decide level routing")["run"]
    git = tmp_path / "git"
    git.write_text('''#!/bin/sh
printf '%s\n' "$*" >> "$GIT_CALLS"
case "$1" in
  rev-parse)
    [ "$DIFF_MISSING" != endpoints ] || exit 1
    [ "$DIFF_MISSING" != recoverable ] || [ "$3" != 'base^{commit}' ] || [ -e "$RECOVERED" ] ;;
  fetch)
    [ "$DIFF_MISSING" = recoverable ] || exit 1
    touch "$RECOVERED" ;;
  merge-base)
    [ "$MERGE_MISSING" != true ] || exit 1
    printf '%s\n' ancestor ;;
  diff) printf '%s\n' "$DIFF_CHANGED" ;;
esac
''')
    git.chmod(0o755)
    output = tmp_path / "output"
    env = {**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
           "EVENT_NAME": event, "L2_CI_DEFAULT_ENABLED": default, "INPUT_RUN_L2_CI": manual,
           "BEFORE_SHA": "" if missing == "base" else "base", "PUSH_SHA": "head",
           "PR_BASE_SHA": "base", "PR_HEAD_SHA": "head", "GITHUB_OUTPUT": str(output),
           "DIFF_CHANGED": changed, "DIFF_MISSING": missing,
           "MERGE_MISSING": str(merge_missing).lower(), "RECOVERED": str(tmp_path / "recovered"),
           "GIT_CALLS": str(tmp_path / "git-calls")}
    result = subprocess.run(["bash", "-eu", "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return dict(line.split("=", 1) for line in output.read_text().splitlines())


@pytest.mark.skipif(os.name == "nt", reason="Workflow routing runs in POSIX Bash")
@pytest.mark.parametrize("default", ["false", "true"])
@pytest.mark.parametrize("changed,levels", [
    ("l0/compiler/shared/runtime/dea_rt.h", (True, True, True)),
    ("l0/compiler/stage2_l0/src/analysis.l0", (True, True, True)),
    ("l0/compiler/stage1_py/l0_types.py", (True, True, True)),
    ("l0/compiler/stage2_l0/scripts/check_trace_log.py", (True, True, True)),
    ("l0/compiler/stage1_py/tests/backend/test_header.py", (True, False, False)),
    ("l0/docs/reference/grammar.md", (True, False, False)),
    ("l0/scripts/gen_docs.py", (True, False, False)),
    ("l1/compiler/src/analysis.l0", (False, True, True)),
    ("l1/compiler/shared/runtime/include/dea_rt.h", (False, True, True)),
    ("l1/compiler/shared/l1/stdlib/std/time.l1", (False, True, True)),
    ("l1/tests/test_predecessor_compatibility.py", (False, True, False)),
    ("l1/docs/reference/grammar.md", (False, True, False)),
    ("l1/scripts/docs/templates/file.html.j2", (False, True, False)),
    (".github/actions/l1-ci/action.yml", (False, True, False)),
    (".github/workflows/l1-ci.yml", (False, True, False)),
    (".github/actions/l0-ci/action.yml", (True, False, False)),
    (".github/workflows/l0-ci.yml", (True, False, False)),
    ("l2/compiler/src/analysis.l1", (False, False, True)),
    (".github/actions/l2-ci/action.yml", (False, False, True)),
    (".github/actions/setup-doxygen/action.yml", (True, True, True)),
    ("scripts/tests/test_shuffle_sources.py", (True, True, True)),
])
def test_validation_follows_level_dependencies(tmp_path, default, changed, levels):
    """Successor changes stay downstream; predecessor input changes reach consumers."""
    result = route(tmp_path, default=default, event="push", changed=changed)
    for level, selected in zip(("l0", "l1", "l2"), levels):
        assert result[f"run_{level}"] == str(selected and (level != "l2" or default == "true")).lower()


@pytest.mark.skipif(os.name == "nt", reason="Workflow routing runs in POSIX Bash")
def test_recovered_push_base_preserves_l1_only_selection(tmp_path):
    """Recover the exact event base before selecting workloads after a rewrite."""
    result = route(tmp_path, default="false", event="push", missing="recoverable",
                   changed="l1/compiler/shared/runtime/include/dea_rt.h")
    assert result["run_l0"] == "false"
    assert result["run_l1"] == "true"
    calls = (tmp_path / "git-calls").read_text().splitlines()
    assert "fetch --no-tags --no-recurse-submodules origin base" in calls
    assert "diff --name-only base head" in calls


@pytest.mark.skipif(os.name == "nt", reason="Workflow routing runs in POSIX Bash")
def test_pull_request_uses_merge_base_for_selection(tmp_path):
    """Unrelated target-branch changes must not expand a pull request's scope."""
    result = route(tmp_path, default="false", event="pull_request", changed="l1/docs/roadmap.md")
    assert result["run_l0"] == "false"
    assert result["run_l1"] == "true"
    calls = (tmp_path / "git-calls").read_text().splitlines()
    assert "merge-base base head" in calls
    assert "diff --name-only ancestor head" in calls
    assert not any(line.startswith("fetch ") for line in calls)


@pytest.mark.skipif(os.name == "nt", reason="Workflow routing runs in POSIX Bash")
def test_missing_merge_base_selects_conservative_workloads(tmp_path):
    """Keep validation when a pull request has no resolvable common ancestor."""
    result = route(tmp_path, default="false", event="pull_request", merge_missing=True)
    assert result["run_l0"] == result["run_l1"] == "true"
    assert result["run_l2"] == "false"


@pytest.mark.skipif(os.name == "nt", reason="Workflow routing runs in POSIX Bash")
def test_rewrite_routing_recovers_unadvertised_commit_from_local_remote(tmp_path):
    """Exercise real Git recovery of a force-push base missing from a fresh clone."""
    origin = tmp_path / "origin.git"
    writer = tmp_path / "writer"
    checkout = tmp_path / "checkout"
    git_env = {**os.environ, "GIT_AUTHOR_NAME": "Routing Test", "GIT_COMMITTER_NAME": "Routing Test",
               "GIT_AUTHOR_EMAIL": "routing@example.invalid", "GIT_COMMITTER_EMAIL": "routing@example.invalid"}

    def git(*args, cwd=tmp_path):
        return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=cwd,
                              env=git_env, capture_output=True, text=True, check=True).stdout.strip()

    git("init", "--bare", str(origin))
    git("init", "-b", "main", str(writer))
    (writer / "l0").mkdir()
    (writer / "l1").mkdir()
    (writer / "l0/baseline").write_text("unchanged")
    (writer / "l1/source").write_text("original")
    git("add", ".", cwd=writer)
    git("commit", "-m", "Original fixture.", cwd=writer)
    before = git("rev-parse", "HEAD", cwd=writer)
    git("remote", "add", "origin", str(origin), cwd=writer)
    git("push", "origin", "main", cwd=writer)
    (writer / "l1/source").write_text("rewritten")
    git("add", ".", cwd=writer)
    git("commit", "--amend", "-m", "Rewritten fixture.", cwd=writer)
    head = git("rev-parse", "HEAD", cwd=writer)
    git("push", "--force", "origin", "main", cwd=writer)
    git("clone", "--no-local", "--branch", "main", str(origin), str(checkout))
    missing = subprocess.run(["git", "cat-file", "-e", before], cwd=checkout, capture_output=True)
    assert missing.returncode != 0
    output = tmp_path / "route-output"
    env = {**git_env, "EVENT_NAME": "push", "BEFORE_SHA": before, "PUSH_SHA": head,
           "PR_BASE_SHA": "", "PR_HEAD_SHA": "", "L2_CI_DEFAULT_ENABLED": "false",
           "INPUT_RUN_L2_CI": "default", "GITHUB_OUTPUT": str(output)}
    document = workflow(".github/workflows/ci.yml")
    script = step(document["jobs"]["route-levels"]["steps"], "Decide level routing")["run"]
    result = subprocess.run(["bash", "-eu", "-o", "pipefail", "-c", script], cwd=checkout,
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Recovering the push comparison base" in result.stdout
    selection = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert selection["run_l0"] == "false"
    assert selection["run_l1"] == "true"
    assert selection["run_l2"] == "false"
    assert git("rev-parse", before, cwd=checkout) == before


def test_repository_checks_have_a_separate_native_step():
    """Run shared checks on every native platform outside the L0 delegate."""
    steps = workflow(".github/workflows/ci.yml")["jobs"]["unified"]["steps"]
    for name, python in (("Run repository checks", ".venv/bin/python"),
                         ("Run repository checks (Windows)", ".venv/Scripts/python.exe")):
        selected = step(steps, name)
        assert f"{python} -m pytest -q -n 0 scripts/tests" in selected["run"]
    assert "scripts/tests" not in (ROOT / "l0/Makefile").read_text()
    assert "test_shuffle_sources.py" not in (ROOT / "l0/Makefile").read_text()


def test_ubuntu_utilities_use_pinned_ci_baseline():
    """Keep every direct Ubuntu job on the CI baseline and reject moving aliases."""
    selected = []
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        assert "ubuntu-latest" not in path.read_text(), path.name
        document = workflow(path.relative_to(ROOT))
        for name, job in document["jobs"].items():
            runner = job.get("runs-on", "")
            if isinstance(runner, str) and runner.startswith("ubuntu-"):
                assert runner == "ubuntu-26.04", (path.name, name)
                selected.append((path.name, name))
    assert selected


@pytest.mark.parametrize("filename,jobs", [
    ("l0-release.yml", ["build-dist"]),
    ("l0-snapshot.yml", ["build-dist"]),
    ("l1-release.yml", ["build-dist", "verify-dist"]),
    ("l1-snapshot.yml", ["build-dist", "verify-dist"]),
    ("l1-productization-acceptance.yml", ["build", "verify"]),
])
def test_linux_artifact_builders_and_verifiers_share_ubuntu24_baseline(filename, jobs):
    """Preserve the native artifact baseline independently of compiler CI and docs."""
    document = workflow(f".github/workflows/{filename}")
    for name in jobs:
        job = document["jobs"][name]
        linux = [entry for entry in job["strategy"]["matrix"]["include"]
                 if entry.get("os") == "linux" or entry.get("platform") == "linux-x86_64"]
        assert len(linux) == 1, (filename, name)
        assert linux[0]["runner"] == "ubuntu-24.04", (filename, name)
        assert job["runs-on"] == "${{ matrix.runner }}"


@pytest.mark.parametrize("filename", ["ci.yml", "l0-ci.yml", "l1-ci.yml", "l2-ci.yml"])
@pytest.mark.parametrize("event,platform", [
    ("push", "all"), ("workflow_dispatch", "all"), ("workflow_dispatch", "linux"),
])
def test_generated_linux_ci_selections_use_ubuntu26(tmp_path, filename, event, platform):
    """Exercise real matrix selection for automatic and manual Linux CI routes."""
    document = workflow(f".github/workflows/{filename}")
    shell = step(document["jobs"]["select-matrix"]["steps"], "Select matrix")["run"]
    script = shell.split("python3 - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    output = tmp_path / "matrix output"
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                            env={**os.environ, "EVENT_NAME": event, "INPUT_PLATFORM": platform,
                                 "GITHUB_OUTPUT": str(output)}, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    matrix = json.loads(output.read_text().removeprefix("matrix="))["include"]
    linux = [entry for entry in matrix if entry["os"] == "linux"]
    assert len(linux) == 1
    assert linux[0]["runner"] == "ubuntu-26.04"
    if platform == "linux":
        assert matrix == linux


@pytest.mark.parametrize("filename,job_name", [
    ("ci.yml", "unified"), ("l0-ci.yml", "test-extended"),
    ("l1-ci.yml", "bootstrap"), ("l2-ci.yml", "bootstrap"),
])
def test_linux_temp_storage_precedes_compiler_ci_consumers(filename, job_name):
    """Set job-wide temporary storage before tools and delegates can use /tmp."""
    steps = workflow(f".github/workflows/{filename}")["jobs"][job_name]["steps"]
    setup = [item for item in steps if item.get("uses") == "./.github/actions/setup-linux-temp"]
    assert len(setup) == 1
    assert setup[0]["if"] == "runner.os == 'Linux'"
    checkout = next(item for item in steps if item.get("uses", "").startswith("actions/checkout@"))
    python = next(item for item in steps if item.get("uses", "").startswith("actions/setup-python@"))
    assert steps.index(checkout) < steps.index(setup[0]) < steps.index(python)
    consumers = [item for item in steps if item.get("uses", "").startswith("./.github/actions/l")]
    assert consumers and all(steps.index(setup[0]) < steps.index(item) for item in consumers)


@pytest.mark.skipif(os.name == "nt", reason="Linux-only action exercised on native POSIX hosts")
def test_linux_temp_action_redirects_real_subprocess_temporary_files(tmp_path):
    """Exercise the actual action and Python's temporary-directory selection."""
    action = workflow(".github/actions/setup-linux-temp/action.yml")
    assert action["runs"]["using"] == "composite"
    setup, = action["runs"]["steps"]
    assert setup["shell"] == "bash"
    runner_temp = tmp_path / "runner temp with spaces and 'apostrophe'"
    runner_temp.mkdir()
    output = tmp_path / "github environment"
    source = {**os.environ, "RUNNER_TEMP": str(runner_temp), "GITHUB_ENV": str(output),
              "TMPDIR": "/old-tmp", "TMP": "/old-tmp", "TEMP": "/old-tmp"}
    result = subprocess.run(["bash", "-eu", "-o", "pipefail", "-c", setup["run"]],
                            env=source, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    selected = dict(line.split("=", 1) for line in output.read_text().splitlines())
    directory = runner_temp / "dea-tmp"
    assert set(selected) == {"TMPDIR", "TMP", "TEMP"}
    assert all(Path(value) == directory for value in selected.values())
    assert directory.is_dir()
    assert "Linux temporary directory:" in result.stdout
    probe = subprocess.run(
        [sys.executable, "-c", "import json, pathlib, tempfile; "
         "p = pathlib.Path(tempfile.mkdtemp(prefix='trace-probe.')); "
         "(p / 'trace.log').write_bytes(b'trace probe\\n'); print(json.dumps(str(p)))"],
        env={**source, **selected}, capture_output=True, text=True, timeout=10)
    assert probe.returncode == 0, probe.stdout + probe.stderr
    artifact = Path(json.loads(probe.stdout))
    assert artifact.parent == directory
    assert (artifact / "trace.log").read_bytes() == b"trace probe\n"


@pytest.mark.skipif(os.name == "nt", reason="Linux-only action exercised on native POSIX hosts")
@pytest.mark.parametrize("runner_temp", [None, ""])
def test_linux_temp_action_requires_runner_storage(tmp_path, runner_temp):
    """Fail before exporting an unusable fallback when runner storage is absent."""
    action = workflow(".github/actions/setup-linux-temp/action.yml")
    setup, = action["runs"]["steps"]
    output = tmp_path / "github environment"
    env = {**os.environ, "GITHUB_ENV": str(output)}
    env.pop("RUNNER_TEMP", None)
    if runner_temp is not None:
        env["RUNNER_TEMP"] = runner_temp
    result = subprocess.run(["bash", "-eu", "-o", "pipefail", "-c", setup["run"]],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert "RUNNER_TEMP is required" in result.stderr
    assert not output.exists()


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


@pytest.mark.parametrize("target,expected", [
    ("test", ["test"]), ("test-extended", ["test-extended"]),
    ("test-stage1", ["test-stage1"]), ("test-docgen", ["test-docgen", "test-stage1"]),
    ("test-stage2 TESTS=parser_test", ["test-stage2", "test-stage1"]),
])
def test_windows_focused_l0_targets_still_validate_native_stage1(checkout, target, expected):
    root, calls = checkout
    ci.run_delegate("l0", {"RUNNER_OS": "Windows", "CI_MAKE_TARGET": target}, root=root)
    assert [command[3] for command, _ in make_calls(calls)] == expected


@pytest.mark.parametrize("family,os_name,platform,temporary,valid", [
    ("native", "nt", "win-amd64", True, True),
    ("native", "nt", "mingw_x86_64_ucrt", True, False),
    ("native", "posix", "linux-x86_64", True, False),
    ("msys2", "nt", "mingw_x86_64_ucrt", True, True),
    ("msys2", "nt", "win-amd64", True, False),
    ("msys2", "nt", "mingw_x86_64", True, False),
    ("msys2", "nt", "mingw_x86_64_ucrt", False, False),
])
def test_windows_interpreter_family_boundary(tmp_path, family, os_name, platform, temporary, valid):
    from check_windows_python import validate_family
    root = tmp_path / "checkout with spaces"
    prefix = tmp_path / "runner temporary/venv" if temporary else root / ".venv"
    arguments = dict(os_name=os_name, platform=platform, prefix=prefix,
                     base_prefix=tmp_path / "base Python", root=root)
    if valid:
        validate_family(family, **arguments)
    else:
        with pytest.raises(ValueError):
            validate_family(family, **arguments)
    if family == "msys2" and valid:
        with pytest.raises(ValueError, match="separate virtual environment"):
            validate_family(family, **{**arguments, "base_prefix": prefix})


@pytest.mark.skipif(os.name == "nt", reason="POSIX stubs simulate Windows Make selection without installing Python")
@pytest.mark.parametrize("windows", [False, True])
def test_make_forwards_selected_python_only_on_windows(tmp_path, windows):
    selected = tmp_path / "native Python"
    selected.write_text('#!/bin/sh\ncase "$*" in\n'
                        '  *sys.executable*) printf "%s\\n" "$EXPECTED_PYTHON";;\nesac\n')
    selected.chmod(0o755)
    uv = tmp_path / "uv"
    uv.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$UV_ARGUMENTS"\n'
                  'printf "%s\\n" "$UV_PROJECT_ENVIRONMENT" > "$UV_ENVIRONMENT"\n')
    uv.chmod(0o755)
    arguments = tmp_path / "uv arguments"
    environment = tmp_path / "uv environment"
    venv = tmp_path / "checkout with spaces/.venv"
    env = {**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
           "EXPECTED_PYTHON": r"C:\Native Python\python.exe", "UV_ARGUMENTS": str(arguments),
           "UV_ENVIRONMENT": str(environment)}
    command = ["make", "-f", str(ROOT / "Makefile"), "venv", f"PYTHON={selected}",
               f"VENV_DIR={venv}", f"OS={'Windows_NT' if windows else 'POSIX'}"]
    result = subprocess.run(command, cwd=tmp_path, env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = ["sync", "--quiet", "--all-groups"]
    if windows:
        expected += ["--python", env["EXPECTED_PYTHON"]]
    assert arguments.read_text().splitlines() == expected
    assert environment.read_text().strip() == str(venv)
    if windows:
        # An old MSYS2 checkout environment must fail before uv can replace it.
        (venv / "bin").mkdir(parents=True)
        (venv / "bin/python").touch()
        arguments.unlink()
        result = subprocess.run(command, cwd=tmp_path, env=env, text=True, capture_output=True)
        assert result.returncode != 0
        assert "recreate it with native Windows CPython" in result.stderr
        assert not arguments.exists()


def test_windows_provisioning_and_stage1_pass_share_canonical_suite():
    action = workflow(".github/actions/setup-windows-python/action.yml")
    steps = action["runs"]["steps"]
    assert step(steps, "Set up native CPython")["uses"].startswith("actions/setup-python@")
    native = step(steps, "Provision native shared environment")["run"]
    assert 'make venv PYTHON="$native_python"' in native
    assert "UV_PROJECT_ENVIRONMENT=" in native and "UV_PYTHON=" in native
    setup = step(steps, "Provision temporary MSYS2 Stage 1 environment")
    assert setup["if"] == "inputs.msys2_stage1 == 'true'"
    assert setup["env"]["MSYSTEM"] == "UCRT64"
    script = setup["run"]
    assert 'mktemp -d "$(cygpath -u "$RUNNER_TEMP")/' in script
    assert '/ucrt64/bin/python.exe -m venv' in script
    assert "uv export --frozen --all-groups --no-emit-workspace" in script
    assert '"$test_python" -m pip install' in script
    assert "--python" not in script and "pytest" not in script
    assert "DEA_MSYS2_TEST_PYTHON=" in script
    makefile = (ROOT / "l0/Makefile").read_text()
    for name, interpreter in (("test-stage1", "VENV_PYTHON"), ("test-stage1-msys2", "DEA_MSYS2_TEST_PYTHON")):
        recipe = makefile.split(f"\n{name}:", 1)[1].split("\n\n", 1)[0]
        assert f'"$({interpreter})" -m pytest $(STAGE1_PYTEST_ARGS)' in recipe
        if name.endswith("msys2"):
            assert "| venv" not in recipe and "pip" not in recipe and "uv " not in recipe
            assert "check_windows_python.py msys2" in recipe
    assert "STAGE1_PYTEST_ARGS := -n auto -q --quiet-progress" in makefile
    delegate = workflow(".github/actions/l0-ci/action.yml")["runs"]["steps"]
    msys2 = step(delegate, "Run full L0 Stage 1 suite (MSYS2 UCRT64)")
    assert msys2["if"] == "runner.os == 'Windows'"
    assert msys2["env"]["MSYSTEM"] == "UCRT64"
    assert "make -C l0 test-stage1-msys2" in msys2["run"]
    assert "Stage 1 pytest: %s seconds" in msys2["run"]


@pytest.mark.parametrize("filename", [
    "ci.yml", "l0-ci.yml", "l1-ci.yml", "l2-ci.yml", "l0-release.yml", "l0-snapshot.yml",
    "l1-release.yml", "l1-snapshot.yml", "l1-productization-acceptance.yml",
])
def test_windows_consumers_select_native_tooling(filename):
    document = workflow(f".github/workflows/{filename}")
    for job in document["jobs"].values():
        steps = job.get("steps", [])
        msys = [i for i, item in enumerate(steps) if item.get("uses", "").startswith("msys2/setup-msys2@")]
        if not msys:
            continue
        provision = [i for i, item in enumerate(steps)
                     if item.get("uses") == "./.github/actions/setup-windows-python"]
        has_checkout = any(item.get("uses", "").startswith("actions/checkout@") for item in steps)
        if has_checkout:
            assert len(provision) == 1 and provision[0] > max(msys)
            options = steps[provision[0]].get("with", {})
            expected = "${{ needs.route-levels.outputs.run_l0 }}" if filename == "ci.yml" else str(filename == "l0-ci.yml").lower()
            assert options.get("msys2_stage1", "false") == expected
        else:
            assert not provision
            setup = step(steps, "Set up Python")
            assert "if" not in setup
            verify = step(steps, "Verify without source checkout or bootstrap compilers (Windows)")
            assert '"$(cygpath -u "$pythonLocation/python.exe")" -I' in verify["run"]
        for index in msys:
            assert "-uv" not in steps[index]["with"]["install"]
            if filename not in {"ci.yml", "l0-ci.yml"}:
                assert "-python" not in steps[index]["with"]["install"]
        for item in steps:
            if item.get("shell") == "msys2 {0}":
                assert item.get("env", {}).get("PYTHON") != "python"
                assert not any(line.strip().startswith(("python ", "python3 ")) for line in item.get("run", "").splitlines())


@pytest.mark.skipif(os.name == "nt", reason="POSIX filesystem fixtures simulate both Make host branches")
@pytest.mark.parametrize("level", ["", "l0", "l1", "l2"])
@pytest.mark.parametrize("windows", [False, True])
@pytest.mark.parametrize("recursive", [False, True], ids=["direct", "recursive"])
def test_make_shared_environment_selection_cannot_pick_msys2_on_windows(
    tmp_path, monkeypatch, level, windows, recursive,
):
    if recursive:
        monkeypatch.setenv("MAKELEVEL", "1")
        monkeypatch.setenv("MAKEFLAGS", "w")
    venv = tmp_path / "shared environment"
    for name in ("bin/python", "Scripts/python.exe"):
        path = venv / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        path.chmod(0o755)
    probe = tmp_path / "probe.mk"
    probe.write_text('print-selected:\n\t@printf "%s\\n" "$(VENV_PYTHON)" "$(PYTHON)"\n')
    result = subprocess.run([
        "make", "--no-print-directory", "-f", str(ROOT / level / "Makefile"), "-f", str(probe),
        "print-selected", f"VENV_DIR={venv}", f"OS={'Windows_NT' if windows else 'POSIX'}",
    ], cwd=ROOT / level, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = str(venv / ("Scripts/python.exe" if windows else "bin/python"))
    assert result.stdout.splitlines() == [expected, expected]


@pytest.mark.parametrize("prefix,root,valid", [
    (r"C:\runner temp\test-env", "C:/Dea checkout", True),
    (r"C:\Dea checkout/.venv", "C:/Dea checkout", False),
    (r"C:\Dea checkout different/.venv", "C:/Dea checkout", True),
    (r"\\server\share\runner temp/test-env", r"\\server/share/Dea checkout", True),
    (r"\\server\share\Dea checkout/.venv", r"\\server/share/Dea checkout", False),
])
def test_temporary_interpreter_boundary_handles_windows_path_spellings(prefix, root, valid):
    from pathlib import PureWindowsPath
    from check_windows_python import validate_family
    arguments = dict(os_name="nt", platform="mingw_x86_64_ucrt", prefix=PureWindowsPath(prefix),
                     base_prefix=PureWindowsPath("C:/msys64/ucrt64"), root=PureWindowsPath(root))
    if valid:
        validate_family("msys2", **arguments)
    else:
        with pytest.raises(ValueError, match="outside the checkout"):
            validate_family("msys2", **arguments)


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable stubs verify the external MSYS2 test command")
def test_msys2_stage1_execution_never_installs_or_uses_native_environment(tmp_path):
    interpreter = tmp_path / "MSYS2 environment/python.exe"
    interpreter.parent.mkdir()
    interpreter.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$INTERPRETER_CALLS"\n')
    interpreter.chmod(0o755)
    calls = tmp_path / "calls"
    env = {**os.environ, "INTERPRETER_CALLS": str(calls)}
    command = ["make", "-C", str(ROOT / "l0"), "test-stage1-msys2"]
    result = subprocess.run([*command, f"DEA_MSYS2_TEST_PYTHON={interpreter}"],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert calls.read_text().splitlines() == [
        "../scripts/check_windows_python.py msys2", "-m pytest -n auto -q --quiet-progress",
    ]
    calls.unlink()
    result = subprocess.run([*command, "DEA_MSYS2_TEST_PYTHON="], env=env, capture_output=True, text=True)
    assert result.returncode != 0 and "provision DEA_MSYS2_TEST_PYTHON first" in result.stderr
    assert not calls.exists()


@pytest.mark.parametrize("event,platform,expected", [
    ("push", "all", ["linux", "macos-intel", "macos-arm64", "windows-ucrt64-python"]),
    ("workflow_call", "all", ["linux", "macos-intel", "macos-arm64", "windows-ucrt64-python", "windows-mingw64-python"]),
    ("workflow_dispatch", "windows-native-python", ["windows-mingw64-python"]),
    ("workflow_dispatch", "windows-ucrt64-python", ["windows-ucrt64-python"]),
    ("workflow_call", "linux", ["linux"]),
    ("workflow_dispatch", "macos-intel", ["macos-intel"]),
    ("workflow_dispatch", "macos-arm64", ["macos-arm64"]),
])
def test_l0_manual_python_selector_alias_preserves_platform_routes(tmp_path, event, platform, expected):
    import json
    document = workflow(".github/workflows/l0-ci.yml")
    shell = step(document["jobs"]["select-matrix"]["steps"], "Select matrix")["run"]
    script = shell.split("python3 - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    output = tmp_path / "matrix output"
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                            env={**os.environ, "EVENT_NAME": event, "INPUT_PLATFORM": platform,
                                 "GITHUB_OUTPUT": str(output)})
    assert result.returncode == 0, result.stdout + result.stderr
    matrix = json.loads(output.read_text().removeprefix("matrix="))["include"]
    assert [entry["platform"] for entry in matrix] == expected
    for entry in matrix:
        if entry["os"] == "windows":
            assert entry["msystem"] == ("MINGW64" if entry["platform"] == "windows-mingw64-python" else "UCRT64")
        else:
            assert entry["c_compiler"] == ("gcc" if entry["os"] == "linux" else "clang")
