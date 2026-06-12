#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for monorepo release-tag policy wiring."""

from __future__ import annotations

from pathlib import Path


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


def check_release_workflow() -> None:
    # Pin the durable wiring concepts (triggers, version derivation, the
    # immutable draft-then-publish lifecycle, release-line tag gating), not the
    # exact shell/quoting of each step, which is reworded freely.
    text = read_text(".github/workflows/l0-release.yml")
    # Triggered by level-prefixed release tags.
    assert_contains(text, '"l0-v*"', context="l0-release.yml")
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
    # Release-line gating: prefer the previous l0-v tag, fall back to a
    # pre-monorepo bare vX.Y.Z tag for release notes.
    assert_contains(text, "grep '^l0-v'", context="l0-release.yml")
    assert_contains(text, "grep -E '^v[0-9]+\\.[0-9]+\\.[0-9]+$'", context="l0-release.yml")
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
