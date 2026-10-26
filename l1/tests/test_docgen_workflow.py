# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Full reference CI builds retain artifacts and print informational reports."""

import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/l1-docs-validate.yml"
REPORT = Path("build/docs/reference/undocumented-functions.txt")


def workflow():
    """Read the reference workflow without interpreting YAML on/off scalars.

    Returns:
        The parsed workflow with scalar values preserved as strings.
    """
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def validation_job():
    """Find the job that builds the full documentation bundle.

    Returns:
        The documentation build job and its ordered workflow steps.
    """
    jobs = workflow()["jobs"].values()
    job = next(job for job in jobs
               if any("make docs-artifacts" in item.get("run", "") for item in job["steps"]))
    return job, job["steps"]


def report_step(steps):
    """Find the informational report step executed by the reference workflow.

    Args:
        steps: Ordered workflow steps from the documentation build job.

    Returns:
        The step printing the generated undocumented-functions report.
    """
    return next(item for item in steps if item.get("name") == "Show undocumented functions report")


def test_unified_ci_routes_l1_docs_as_an_independent_job():
    unified = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
                        Loader=yaml.BaseLoader)
    jobs = unified["jobs"]
    assert jobs["route-levels"]["outputs"]["run_l1_docs"] == "${{ steps.route.outputs.run_l1_docs }}"
    selected = jobs["l1-docs-validation"]
    assert selected["needs"] == "route-levels"
    assert selected["if"] == "needs.route-levels.outputs.run_l1_docs == 'true'"
    assert selected["uses"] == "./.github/workflows/l1-docs-validate.yml"
    assert jobs["docs-validation"]["uses"] == "./.github/workflows/l0-docs-validate.yml"
    assert jobs["docs-validation"]["if"] == "needs.route-levels.outputs.run_docs == 'true'"


def test_full_reference_workflow_is_read_only_and_bootstrap_independent():
    document = workflow()
    assert set(document["on"]) == {"workflow_call", "workflow_dispatch"}
    assert document["permissions"] == {"contents": "read"}
    job, steps = validation_job()
    assert job["runs-on"] == "ubuntu-26.04"
    assert job["defaults"]["run"]["working-directory"] == "l1"
    build = next(item for item in steps if "make docs-artifacts" in item.get("run", ""))
    env = {**document.get("env", {}), **job.get("env", {}), **build.get("env", {})}
    assert env["DEA_DIST_VERSION"] == "dev"
    assert not any("bootstrap" in key.lower() or "release" in key.lower() for key in env)
    setup_python = next(item for item in steps if item.get("uses", "").startswith("actions/setup-python@"))
    assert setup_python["with"]["python-version"] == "3.14"
    assert any(item.get("uses", "").startswith("astral-sh/setup-uv@") for item in steps)
    commands = "\n".join(item.get("run", "") for item in steps)
    setup_doxygen = next(item for item in steps if item.get("uses") == "./.github/actions/setup-doxygen")
    assert steps.index(setup_doxygen) < steps.index(build)
    setup_docs = next(item for item in steps if item.get("uses") == "./.github/actions/setup-docs-toolchain")
    assert steps.index(setup_docs) < steps.index(setup_doxygen)
    assert setup_docs["timeout-minutes"] == "15"
    assert setup_docs.get("with", {}).get("build_pdf", "true") == "true"
    assert "uv sync --group docs" in commands
    for forbidden in ("L1_BOOTSTRAP_L0C", "L1_DOCS_RELEASE_TAG", "gh release", "gh workflow run",
                      "git push", "actions/deploy-pages", "actions/upload-pages-artifact"):
        assert forbidden not in WORKFLOW.read_text(encoding="utf-8")


def test_informational_report_runs_after_build_and_preserves_failure_evidence():
    _, steps = validation_job()
    build = next(item for item in steps if "make docs-artifacts" in item.get("run", ""))
    report = report_step(steps)
    assert steps.index(report) > steps.index(build)
    assert report["if"] == "always()"
    assert 'report_path="build/docs/reference/undocumented-functions.txt"' in report["run"]
    assert 'cat "$report_path"' in report["run"]
    assert "check_undocumented_functions.py" not in WORKFLOW.read_text(encoding="utf-8")
    uploads = [item for item in steps if item.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(uploads) >= 2
    assert all(item.get("if") == "always()" for item in uploads)
    paths = "\n".join(item["with"]["path"] for item in uploads)
    assert "l1/build/docs/reference" in paths
    assert "l1/build/docs/reference/*.log" in paths
    assert "l1/build/docs/reference-failure" in paths
    assert "l1/build/docs/artifacts/dea_l1_autodocs.tar.gz" in paths


@pytest.mark.skipif(os.name == "nt", reason="The Ubuntu workflow uses a POSIX shell")
@pytest.mark.parametrize("content", [
    "# Undocumented Functions\n\nNo undocumented functions found.\n",
    "# Undocumented Functions\n\n## Dea\n\ncompiler/src/parser.l0:17 parse\n",
    "# Undocumented Functions\n\n## Python\n\nscripts/gen_docs.py:23 main\n",
    "# Undocumented Functions\n\n## Other\n\ncompiler/support/compiler_support.c:42 helper\n",
    None,
])
def test_actual_workflow_prints_report_without_rejecting_entries_or_missing_report(tmp_path, content):
    level = tmp_path / "checkout with spaces" / "l1"
    level.mkdir(parents=True)
    if content is not None:
        report = level / REPORT
        report.parent.mkdir(parents=True)
        report.write_text(content, encoding="utf-8")
    _, steps = validation_job()
    result = subprocess.run(["bash", "-eu", "-c", report_step(steps)["run"]],
                            cwd=level, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == (content or "")
    assert result.stderr == ""
