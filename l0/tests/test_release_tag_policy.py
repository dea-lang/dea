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
    assert_contains(text, "docs-markdown", context="l0-release.yml")
    assert_contains(text, "dea_l0_api_reference-", context="l0-release.yml")
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
    assert_contains(text, "dea_l0_api_reference-", context="l0-snapshot.yml")
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
    assert_contains(text, "dea_l0_api_reference-", context="l0-docs-publish.yml")
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


def main() -> int:
    if WORKFLOW_ROOT is None:
        print("test_release_tag_policy: SKIP (workflow files unavailable in this checkout)")
        return 0

    check_release_workflow()
    check_snapshot_workflow()
    check_docs_publish_workflow()
    check_docs_build_workflow()
    check_docs()
    print("test_release_tag_policy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
