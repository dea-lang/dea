#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for monorepo release-tag policy wiring."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import shlex
import sys
import tempfile


def resolve_workflow_root() -> Path | None:
    start = Path(__file__).resolve().parent
    for candidate in (start, *start.parents):
        if (candidate / ".github" / "workflows" / "l0-release.yml").is_file():
            return candidate
    return None


def resolve_monorepo_root(workflow_root: Path | None) -> Path | None:
    if workflow_root is None:
        return None
    for candidate in (workflow_root, *workflow_root.parents):
        if (candidate / "MONOREPO.md").is_file():
            return candidate
    return None


WORKFLOW_ROOT = resolve_workflow_root()
MONOREPO_ROOT = resolve_monorepo_root(WORKFLOW_ROOT)


def fail(message: str) -> None:
    raise SystemExit(f"test_release_tag_policy: FAIL: {message}")


def read_text(path: str) -> str:
    if WORKFLOW_ROOT is None:
        fail(f"workflow root unavailable for {path}")
    return (WORKFLOW_ROOT / path).read_text(encoding="utf-8")


def read_monorepo_text(path: str) -> str:
    if MONOREPO_ROOT is None:
        fail(f"monorepo root unavailable for {path}")
    return (MONOREPO_ROOT / path).read_text(encoding="utf-8")


def assert_contains(text: str, needle: str, *, context: str) -> None:
    if needle not in text:
        fail(f"missing {needle!r} in {context}")


def assert_before(text: str, first: str, second: str, *, context: str) -> None:
    first_index = text.find(first)
    if first_index < 0:
        fail(f"missing {first!r} in {context}")
    second_index = text.find(second)
    if second_index < 0:
        fail(f"missing {second!r} in {context}")
    if first_index >= second_index:
        fail(f"expected {first!r} before {second!r} in {context}")


def extract_named_run_script(text: str, step_name: str) -> str:
    marker = f"      - name: {step_name}\n"
    marker_index = text.find(marker)
    if marker_index < 0:
        fail(f"missing workflow step {step_name!r}")

    run_marker = "        run: |\n"
    run_index = text.find(run_marker, marker_index + len(marker))
    next_step_index = text.find("\n      - name:", marker_index + len(marker))
    if run_index < 0 or (next_step_index >= 0 and run_index >= next_step_index):
        fail(f"missing run script for workflow step {step_name!r}")

    script_lines: list[str] = []
    content = text[run_index + len(run_marker) :]
    for line in content.splitlines(keepends=True):
        if line.strip() == "":
            script_lines.append("\n")
            continue
        if not line.startswith("          "):
            break
        script_lines.append(line[10:])
    if not script_lines:
        fail(f"empty run script for workflow step {step_name!r}")
    return "".join(script_lines)


def run_release_metadata_validation(
    script: str,
    *,
    tag: str,
    notes: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], str]:
    with tempfile.TemporaryDirectory(prefix="l0-release-policy.") as temporary_directory:
        root = Path(temporary_directory)
        for relative_path, content in (notes or {}).items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        output_path = root / "github-output"
        environment = os.environ.copy()
        environment.update({"CURRENT_TAG": tag, "GITHUB_OUTPUT": output_path.name})
        completed = subprocess.run(
            ["bash", "-eu", "-o", "pipefail", "-c", script],
            cwd=root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            check=False,
        )
        output = output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
        return completed, output


def check_release_metadata_validation_script(validation_script: str) -> None:
    """Exercise the Ubuntu release-metadata shell step on POSIX hosts."""
    valid, valid_output = run_release_metadata_validation(
        validation_script,
        tag="l0-v1.2.3",
        notes={"docs/releases/1.2.3.md": "# Dea/L0 1.2.3\n\nRelease body.\n"},
    )
    if valid.returncode != 0:
        fail(f"valid stable release metadata rejected: {valid.stderr.strip()}")
    if valid_output.splitlines() != [
        "release_version=1.2.3",
        "release_notes=docs/releases/1.2.3.md",
    ]:
        fail(f"unexpected stable release metadata outputs: {valid_output!r}")
    for invalid_tag in (
        "l0-v1.2",
        "l0-v1.2.3-rc.1",
        "l0-v1.2.3+build.1",
        "l0-v01.2.3",
        "v1.2.3",
    ):
        invalid, _ = run_release_metadata_validation(validation_script, tag=invalid_tag)
        if invalid.returncode == 0:
            fail(f"non-stable release tag accepted: {invalid_tag}")
    missing, _ = run_release_metadata_validation(validation_script, tag="l0-v1.2.3")
    if missing.returncode == 0 or "missing canonical release notes" not in missing.stderr:
        fail("missing canonical release notes did not fail validation")
    mismatched, _ = run_release_metadata_validation(
        validation_script,
        tag="l0-v1.2.3",
        notes={"docs/releases/1.2.3.md": "# Dea/L0 1.2.4\n"},
    )
    if mismatched.returncode == 0 or "must start with: # Dea/L0 1.2.3" not in mismatched.stderr:
        fail("mismatched release-note heading did not fail validation")


def check_release_workflow() -> None:
    # Pin the durable wiring concepts (triggers, version derivation, the
    # immutable draft-then-publish lifecycle, release-line tag gating), not the
    # exact shell/quoting of each step, which is reworded freely.
    text = read_text(".github/workflows/l0-release.yml")
    # Triggered by level-prefixed release tags.
    assert_contains(text, '"l0-v*"', context="l0-release.yml")
    # The broad event trigger is followed by executable stable-SemVer gating,
    # because GitHub tag filters are globs rather than regular expressions.
    validation_step = "Validate stable release tag and canonical notes"
    validation_script = extract_named_run_script(text, validation_step)
    assert_contains(
        validation_script,
        "^l0-v(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$",
        context=validation_step,
    )
    assert_contains(
        validation_script,
        'release_notes="docs/releases/$release_version.md"',
        context=validation_step,
    )
    assert_contains(
        validation_script,
        'expected_heading="# Dea/L0 $release_version"',
        context=validation_step,
    )
    # The production step runs on ubuntu-latest. Native Windows CI still
    # performs every static wiring assertion below, but does not execute the
    # Ubuntu Bash fragment through an MSYS subprocess boundary.
    if os.name != "nt":
        check_release_metadata_validation_script(validation_script)
    assert_contains(text, "needs: validate-release", context="l0-release.yml")
    assert_contains(
        text,
        "needs: [validate-release, build-dist, build-docs]",
        context="l0-release.yml",
    )
    # Pages availability is probed and gated.
    assert_contains(text, "repos/$GITHUB_REPOSITORY/pages", context="l0-release.yml")
    assert_contains(text, "pages_enabled=true", context="l0-release.yml")
    assert_contains(text, "pages_enabled=false", context="l0-release.yml")
    assert_contains(text, "github-pages", context="l0-release.yml")
    assert_contains(text, "actions/deploy-pages", context="l0-release.yml")
    # Examples are smoke-tested and the dist version is derived from the tag.
    assert_contains(text, "make check-examples", context="l0-release.yml")
    assert_contains(text, "RELEASE_VERSION#l0-v", context="l0-release.yml")
    # Per-platform dist artifacts and the API reference assets are produced.
    assert_contains(text, "dea-l0-dist-", context="l0-release.yml")
    assert_contains(text, "l0-docs-stage2-markdown", context="l0-release.yml")
    assert_contains(text, "dea_l0_stage2_api_reference-", context="l0-release.yml")
    assert_contains(text, "SHA256SUMS", context="l0-release.yml")
    # Immutable draft-then-publish lifecycle: never republish, never edit a
    # published release, create as draft, upload, then flip to published.
    assert_contains(text, "immutable-release violation", context="l0-release.yml")
    assert_contains(text, "draft=true", context="l0-release.yml")
    assert_contains(text, "draft=false", context="l0-release.yml")
    assert_contains(text, "gh release upload", context="l0-release.yml")
    if 'gh release edit "$CURRENT_TAG"' in text:
        fail("unexpected post-draft gh release edit path in l0-release.yml")
    # The canonical checked-in notes are passed unchanged to draft creation
    # and publication; historical tag scanning and generated git-log bodies
    # must not return.
    if text.count('-F "body=@$RELEASE_NOTES"') != 2:
        fail("canonical release notes are not used exactly for draft creation and publication")
    if text.count("RELEASE_NOTES: ${{ needs.validate-release.outputs.release_notes }}") != 2:
        fail("publish steps do not bind canonical release notes from the validation job")
    for stale_release_notes_path in (
        "grep '^l0-v'",
        "git log --pretty",
        "build/release-notes.md",
    ):
        if stale_release_notes_path in text:
            fail(f"stale release-note selector present in l0-release.yml: {stale_release_notes_path}")
    # Lifecycle ordering: build assets, then checksum, then draft, then publish.
    assert_before(text, "make check-examples", "make dist", context="l0-release.yml")
    assert_before(text, "tar -czf", "SHA256SUMS", context="l0-release.yml")
    assert_before(text, "draft=true", "gh release upload", context="l0-release.yml")
    assert_before(text, "gh release upload", "draft=false", context="l0-release.yml")


def check_snapshot_workflow() -> None:
    # Mirrors the release workflow's durable wiring, plus the snapshot-specific
    # tag scheme and the optional publish gate.
    text = read_text(".github/workflows/l0-snapshot.yml")
    # Snapshot tag scheme and optional publish input.
    assert_contains(text, "l0-snapshot-", context="l0-snapshot.yml")
    assert_contains(text, "publish_release:", context="l0-snapshot.yml")
    assert_contains(text, "if: inputs.publish_release", context="l0-snapshot.yml")
    # Examples are smoke-tested and the dist version is derived from the tag.
    assert_contains(text, "make check-examples", context="l0-snapshot.yml")
    assert_contains(text, "SNAPSHOT_VERSION#l0-", context="l0-snapshot.yml")
    # Per-platform dist artifacts and the API reference assets are produced.
    assert_contains(text, "dea-l0-dist-", context="l0-snapshot.yml")
    assert_contains(text, "dea_l0_stage2_api_reference-", context="l0-snapshot.yml")
    assert_contains(text, "SHA256SUMS", context="l0-snapshot.yml")
    # Immutable draft-then-publish lifecycle.
    assert_contains(text, "immutable-release violation", context="l0-snapshot.yml")
    assert_contains(text, "draft=true", context="l0-snapshot.yml")
    assert_contains(text, "draft=false", context="l0-snapshot.yml")
    assert_contains(text, "gh release upload", context="l0-snapshot.yml")
    if 'gh release edit "$CURRENT_TAG"' in text:
        fail("unexpected post-draft gh release edit path in l0-snapshot.yml")
    # Release-line gating spans snapshot, release, and pre-monorepo bare tags.
    assert_contains(text, "grep -E '^(l0-v|l0-snapshot-)'", context="l0-snapshot.yml")
    assert_contains(text, "grep -E '^v[0-9]+\\.[0-9]+\\.[0-9]+$'", context="l0-snapshot.yml")
    # Lifecycle ordering: build assets, then checksum, then draft, then publish.
    assert_before(text, "make check-examples", "make dist", context="l0-snapshot.yml")
    assert_before(text, "tar -czf", "SHA256SUMS", context="l0-snapshot.yml")
    assert_before(text, "draft=true", "gh release upload", context="l0-snapshot.yml")
    assert_before(text, "gh release upload", "draft=false", context="l0-snapshot.yml")


def check_docs_publish_workflow() -> None:
    # Pin the draft-release asset-attachment contract: its inputs, the job
    # gating, draft resolution by ID or tag URL, the immutable-release guard,
    # and asset upload. The exact jq/quoting and prose messages are not pinned.
    text = read_text(".github/workflows/l0-docs-publish.yml")
    # Pages availability is probed and gated.
    assert_contains(text, "repos/$GITHUB_REPOSITORY/pages", context="l0-docs-publish.yml")
    assert_contains(text, "pages_enabled=true", context="l0-docs-publish.yml")
    assert_contains(text, "pages_enabled=false", context="l0-docs-publish.yml")
    # Draft-attachment inputs and job.
    assert_contains(text, "attach_release_assets_to_draft:", context="l0-docs-publish.yml")
    assert_contains(text, "draft_release:", context="l0-docs-publish.yml")
    assert_contains(text, "attach-release-assets:", context="l0-docs-publish.yml")
    # Job gating runs after docs build and pages deploy succeed/skip.
    assert_contains(text, "always() &&", context="l0-docs-publish.yml")
    assert_contains(text, "needs.build-docs.result == 'success'", context="l0-docs-publish.yml")
    assert_contains(text, "(needs.deploy-pages.result == 'success' || needs.deploy-pages.result == 'skipped')", context="l0-docs-publish.yml")
    assert_contains(text, "inputs.attach_release_assets_to_draft", context="l0-docs-publish.yml")
    # Draft release is resolvable by numeric ID or by tag URL.
    assert_contains(text, "releases/$release_id", context="l0-docs-publish.yml")
    assert_contains(text, "releases/tags/$release_tag", context="l0-docs-publish.yml")
    # Immutable-release guard and the API reference asset upload.
    assert_contains(text, "immutable-release violation", context="l0-docs-publish.yml")
    assert_contains(text, "dea_l0_stage2_api_reference-", context="l0-docs-publish.yml")
    assert_contains(text, "upload_url", context="l0-docs-publish.yml")
    # Negative guards against reintroducing superseded behavior.
    if "release_tag is required when attach_release_assets_to_draft=true" in text:
        fail("stale release_tag requirement present in l0-docs-publish.yml")
    if "draft_release must be a numeric release ID or a release URL ending in that ID" in text:
        fail("stale numeric-tail URL requirement present in l0-docs-publish.yml")
    if "\non:\n  release:" in text:
        fail("unexpected release event trigger in l0-docs-publish.yml")
    if "upload_pdf_to_release" in text:
        fail("stale upload_pdf_to_release input present in l0-docs-publish.yml")


def check_docs_build_workflow() -> None:
    text = read_text(".github/workflows/l0-docs-build.yml")
    assert_contains(text, "inputs.release_tag != ''", context="l0-docs-build.yml")
    assert_contains(text, "inputs.source_ref == inputs.release_tag", context="l0-docs-build.yml")
    assert_contains(text, "format('refs/tags/{0}', inputs.release_tag)", context="l0-docs-build.yml")
    assert_contains(text, "actions/checkout", context="l0-docs-build.yml")
    assert_contains(text, "- name: Show Doxygen version", context="l0-docs-build.yml")
    assert_contains(text, "run: doxygen --version", context="l0-docs-build.yml")


def check_docs_validate_workflow() -> None:
    text = read_text(".github/workflows/l0-docs-validate.yml")
    assert_contains(text, "- name: Show Doxygen version", context="l0-docs-validate.yml")
    assert_contains(text, "run: doxygen --version", context="l0-docs-validate.yml")


def check_docs() -> None:
    # The tag-policy docs are prose and get reworded freely; pin only the
    # durable tag identifiers the policy must keep documenting, not sentences.
    if MONOREPO_ROOT is None:
        return

    monorepo = read_monorepo_text("MONOREPO.md")
    for needle in ("`v0.9.0`", "`v0.9.1`", "`l0-vX.Y.Z`", "`l1-vX.Y.Z`"):
        assert_contains(monorepo, needle, context="MONOREPO.md")

    readme = read_monorepo_text("README.md")
    for needle in ("`v0.9.0`", "`v0.9.1`", "`l0-vX.Y.Z`"):
        assert_contains(readme, needle, context="README.md")



def check_stage_docs_contract() -> None:
    """Validate docs-first release DAGs, isolated artifacts, and checksum coverage."""
    import yaml
    for name, prerequisite in (("l0-release.yml", "validate-release"), ("l0-snapshot.yml", "prepare-snapshot")):
        workflow = yaml.safe_load(read_text(f".github/workflows/{name}"))
        jobs = workflow["jobs"]
        if set(jobs["build-dist"]["needs"]) != {prerequisite, "build-docs"}:
            fail(f"{name}: distributions must wait for verified documentation")
        if jobs["build-docs"]["with"].get("stage") != "stage2":
            fail(f"{name}: release docs must select Stage 2")
        steps = jobs["build-dist"]["steps"]
        checkout_index = next(i for i, s in enumerate(steps) if s.get("uses", "").startswith("actions/checkout@"))
        newline_steps = [s for s in steps[:checkout_index] if s.get("run") == "git config --global core.autocrlf false"]
        if len(newline_steps) != 1 or newline_steps[0].get("if") != "matrix.os == 'windows'" or newline_steps[0].get("working-directory") != ".":
            fail(f"{name}: Windows checkout must preserve documentation input bytes")
        downloads = [s for s in steps if s.get("with", {}).get("name") == "l0-docs-stage2-autodocs"]
        if len(downloads) != 1:
            fail(f"{name}: missing shared Stage 2 bundle download")
        build_steps = [s for s in steps if s["name"] == "Build distribution archive"]
        if len(build_steps) != 2 or any("DOCS_ARTIFACT=" not in s["run"] for s in build_steps):
            fail(f"{name}: both POSIX and Windows must consume the same explicit bundle")
        publish = next(job for key, job in jobs.items() if key.startswith("publish-"))
        checksum = next(s["run"] for s in publish["steps"] if s["name"] == "Generate checksums")
        for required in ("dea_l0_stage2_autodocs-", "dea_l0_stage2_api_reference-", "linux-x86_64", "darwin-x86_64", "darwin-arm64", "windows-x86_64"):
            assert_contains(checksum, required, context=f"{name} checksums")
    build = yaml.safe_load(read_text(".github/workflows/l0-docs-build.yml"))
    if build.get("permissions") != {"contents": "read"}:
        fail("documentation generation must remain read-only")
    validate = read_text(".github/workflows/l0-docs-validate.yml")
    assert_contains(validate, "--stage all --strict --pdf --artifacts", context="independent stage validation")
    for stage in ("stage1", "stage2"):
        assert_contains(validate, f"name: l0-docs-validation-{stage}-autodocs", context="stage-qualified validation artifact")
    publish = yaml.safe_load(read_text(".github/workflows/l0-docs-publish.yml"))
    if publish["jobs"]["build-docs"]["with"].get("stage") != "stage2":
        fail("manual publication must select Stage 2")



def check_docs_checksums_and_immutable_guards() -> None:
    """Execute checksum and publication rejection paths without remote operations."""
    if os.name == "nt":
        return  # These production shell fragments run on Ubuntu.
    for name in ("l0-release.yml", "l0-snapshot.yml"):
        text = read_text(f".github/workflows/{name}")
        script = extract_named_run_script(text, "Generate checksums")
        script = script.replace("${{ github.ref_name }}", "l0-v9.9.9")
        script = script.replace("${{ needs.prepare-snapshot.outputs.snapshot_tag }}", "l0-v9.9.9")
        script = script.replace("python -", shlex.quote(sys.executable) + " -")
        with tempfile.TemporaryDirectory(prefix="docs-checksums.") as work:
            root = Path(work)
            assets = root / "build/release-assets"
            assets.mkdir(parents=True)
            filenames = [f"dea-l0-lang_{target}_stamp" + (".zip" if target.startswith("windows") else ".tar.gz")
                         for target in ("linux-x86_64", "darwin-x86_64", "darwin-arm64", "windows-x86_64")]
            filenames += ["dea_l0_stage2_api_reference-l0-v9.9.9.pdf", "dea_l0_stage2_api_reference-l0-v9.9.9.tar.gz", "dea_l0_stage2_autodocs-l0-v9.9.9.tar.gz"]
            for filename in filenames:
                (assets / filename).write_bytes(b"checksum fixture")
            proc = subprocess.run(["bash", "-e", "-c", script], cwd=root, capture_output=True, text=True)
            if proc.returncode or len((assets / "SHA256SUMS").read_text().splitlines()) != 7:
                fail(f"{name}: complete release checksum script failed: {proc.stderr}")
            for filename in (filenames[-1], filenames[0]):
                (assets / filename).unlink()
                proc = subprocess.run(["bash", "-e", "-c", script], cwd=root, capture_output=True, text=True)
                if proc.returncode == 0:
                    fail(f"{name}: incomplete assets accepted: {filename}")
                (assets / filename).write_bytes(b"checksum fixture")

    for name, step in (("l0-release.yml", "Ensure draft GitHub release"),
                       ("l0-snapshot.yml", "Ensure draft GitHub pre-release"),
                       ("l0-docs-publish.yml", "Validate target draft release")):
        text = read_text(f".github/workflows/{name}")
        script = extract_named_run_script(text, step)
        with tempfile.TemporaryDirectory(prefix="immutable-docs.") as work:
            root = Path(work)
            gh = root / "gh"
            gh.write_text("#!/bin/sh\ncase \"$*\" in *POST*|*PATCH*|*DELETE*|*upload*) exit 88;; *.draft*) echo false;; *.id*) echo 123;; esac\n")
            gh.chmod(0o755)
            env = {"PATH": str(root) + os.pathsep + os.environ["PATH"], "CURRENT_TAG": "l0-v9.9.9",
                   "GITHUB_REPOSITORY": "dea-lang/dea", "RESOLVED_RELEASE_ID": "123", "GITHUB_OUTPUT": str(root / "out")}
            proc = subprocess.run(["bash", "-e", "-c", script], cwd=root, env=env, capture_output=True, text=True)
            if proc.returncode == 0 or "immutable-release violation" not in proc.stderr:
                fail(f"{name}: published-release guard failed under mocked gh: {proc.stderr}")



def check_docs_helper_routing() -> None:
    """Execute Unified CI routing with mocked Git diff inputs."""
    if os.name == "nt":
        return
    script = extract_named_run_script(read_text(".github/workflows/ci.yml"), "Decide level routing")
    with tempfile.TemporaryDirectory(prefix="docs-routing.") as work:
        root = Path(work)
        git = root / "git"
        git.write_text('#!/bin/sh\nif [ "$1" = diff ]; then printf "%s\\n" "$MOCK_CHANGED_PATH"; fi\n')
        git.chmod(0o755)
        for helper in ("gen_docs", "docs_artifacts", "stage_docs_pages", "gen_dist_tools", "dist_tools_lib"):
            output = root / "output"
            output.unlink(missing_ok=True)
            env = {"PATH": str(root) + os.pathsep + os.environ["PATH"], "EVENT_NAME": "pull_request",
                   "PR_BASE_SHA": "base", "PR_HEAD_SHA": "head", "GITHUB_OUTPUT": str(output),
                   "MOCK_CHANGED_PATH": f"l0/scripts/{helper}.py"}
            proc = subprocess.run(["bash", "-eu", "-c", script], cwd=root, env=env, capture_output=True, text=True)
            if proc.returncode or "run_docs=true" not in output.read_text():
                fail(f"documentation helper {helper} did not route to full docs validation: {proc.stderr}")


def main() -> int:
    if WORKFLOW_ROOT is None:
        print("test_release_tag_policy: SKIP (workflow files unavailable in this checkout)")
        return 0

    check_release_workflow()
    check_snapshot_workflow()
    check_docs_publish_workflow()
    check_docs_build_workflow()
    check_docs_validate_workflow()
    check_docs()
    check_stage_docs_contract()
    check_docs_checksums_and_immutable_guards()
    check_docs_helper_routing()
    print("test_release_tag_policy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
