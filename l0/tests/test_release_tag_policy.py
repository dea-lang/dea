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
    text = read_text(".github/workflows/l0-release.yml")
    assert_contains(text, '- "l0-v*"', context="l0-release.yml")
    assert_contains(text, 'gh api "repos/$GITHUB_REPOSITORY/pages"', context="l0-release.yml")
    assert_contains(text, "pages_enabled=true", context="l0-release.yml")
    assert_contains(text, "pages_enabled=false", context="l0-release.yml")
    assert_contains(text, "make check-examples", context="l0-release.yml")
    assert_contains(text, 'export DEA_DIST_VERSION="${RELEASE_VERSION#l0-v}"', context="l0-release.yml")
    assert_contains(text, "name: dea-l0-dist-${{ matrix.os }}-${{ matrix.arch }}", context="l0-release.yml")
    assert_contains(text, "pattern: dea-l0-dist-*", context="l0-release.yml")
    assert_contains(text, "name: github-pages", context="l0-release.yml")
    assert_contains(text, "uses: actions/deploy-pages@v4", context="l0-release.yml")
    assert_contains(text, "name: docs-markdown", context="l0-release.yml")
    assert_contains(text, 'pdf_name="dea_l0_api_reference-$CURRENT_TAG.pdf"', context="l0-release.yml")
    assert_contains(text, 'tar -czf build/release-assets/blog-export.tar.gz -C build/docs/blog-export .', context="l0-release.yml")
    assert_contains(text, 'pdf_url="https://github.com/${GITHUB_REPOSITORY}/releases/download/${CURRENT_TAG}/dea_l0_api_reference-${CURRENT_TAG}.pdf"', context="l0-release.yml")
    assert_contains(text, 'if gh api "$release_api" >/dev/null 2>&1; then', context="l0-release.yml")
    assert_contains(text, 'is_draft="$(gh api "$release_api" --jq \'.draft\')"', context="l0-release.yml")
    assert_contains(text, "immutable-release violation", context="l0-release.yml")
    assert_contains(text, '-F draft=true', context="l0-release.yml")
    assert_contains(text, '-F draft=false', context="l0-release.yml")
    assert_contains(text, 'gh release upload "$CURRENT_TAG" build/release-assets/* --clobber --repo "$GITHUB_REPOSITORY"', context="l0-release.yml")
    assert_contains(text, 'path.name != "SHA256SUMS"', context="l0-release.yml")
    assert_contains(text, 'handle.write(f"{digest}  {asset.name}\\n")', context="l0-release.yml")
    assert_contains(text, '"blog-export.tar.gz"', context="l0-release.yml")
    assert_contains(text, 'dea_l0_api_reference-${{ github.ref_name }}.pdf', context="l0-release.yml")
    assert_before(text, "Build blog export archive", "Generate checksums", context="l0-release.yml")
    assert_before(text, "Generate checksums", "Ensure draft GitHub release", context="l0-release.yml")
    assert_before(text, "Upload assets to draft release", "Publish GitHub release", context="l0-release.yml")
    if 'gh release edit "$CURRENT_TAG"' in text:
        fail("unexpected post-draft gh release edit path in l0-release.yml")
    assert_contains(
        text,
        "prev_tag=\"$(git tag --merged HEAD --sort=-v:refname | grep '^l0-v' | grep -Fxv \"$CURRENT_TAG\" | head -n 1 || true)\"",
        context="l0-release.yml",
    )
    assert_contains(
        text,
        "prev_tag=\"$(git tag --merged HEAD --sort=-v:refname | grep -E '^v[0-9]+\\.[0-9]+\\.[0-9]+$' | head -n 1 || true)\"",
        context="l0-release.yml",
    )
    assert_before(text, "make check-examples", "make dist | tee build/dist.log", context="l0-release.yml")


def check_snapshot_workflow() -> None:
    text = read_text(".github/workflows/l0-snapshot.yml")
    assert_contains(text, 'snapshot_version="l0-snapshot-${stamp}-${short_hash}"', context="l0-snapshot.yml")
    assert_contains(text, "publish_release:", context="l0-snapshot.yml")
    assert_contains(text, 'description: "Publish pre-release after attaching assets to the draft release"', context="l0-snapshot.yml")
    assert_contains(text, "default: true", context="l0-snapshot.yml")
    assert_contains(text, "make check-examples", context="l0-snapshot.yml")
    assert_contains(text, 'export DEA_DIST_VERSION="${SNAPSHOT_VERSION#l0-}"', context="l0-snapshot.yml")
    assert_contains(text, "name: dea-l0-dist-${{ matrix.os }}-${{ matrix.arch }}", context="l0-snapshot.yml")
    assert_contains(text, "pattern: dea-l0-dist-*", context="l0-snapshot.yml")
    assert_contains(text, 'release_tag: ${{ needs.prepare-snapshot.outputs.snapshot_tag }}', context="l0-snapshot.yml")
    assert_contains(text, 'pdf_name="dea_l0_api_reference-$CURRENT_TAG.pdf"', context="l0-snapshot.yml")
    assert_contains(text, 'tar -czf build/release-assets/blog-export.tar.gz -C build/docs/blog-export .', context="l0-snapshot.yml")
    assert_contains(text, 'pdf_url="https://github.com/${GITHUB_REPOSITORY}/releases/download/${CURRENT_TAG}/dea_l0_api_reference-${CURRENT_TAG}.pdf"', context="l0-snapshot.yml")
    assert_contains(text, 'if gh api "$release_api" >/dev/null 2>&1; then', context="l0-snapshot.yml")
    assert_contains(text, "immutable-release violation", context="l0-snapshot.yml")
    assert_contains(text, '-F draft=true', context="l0-snapshot.yml")
    assert_contains(text, '-F draft=false', context="l0-snapshot.yml")
    assert_contains(text, "if: inputs.publish_release", context="l0-snapshot.yml")
    assert_contains(text, 'gh release upload "$CURRENT_TAG" build/release-assets/* --clobber --repo "$GITHUB_REPOSITORY"', context="l0-snapshot.yml")
    assert_contains(text, 'path.name != "SHA256SUMS"', context="l0-snapshot.yml")
    assert_contains(text, 'handle.write(f"{digest}  {asset.name}\\n")', context="l0-snapshot.yml")
    assert_contains(text, '"blog-export.tar.gz"', context="l0-snapshot.yml")
    assert_contains(text, 'dea_l0_api_reference-${{ needs.prepare-snapshot.outputs.snapshot_tag }}.pdf', context="l0-snapshot.yml")
    assert_before(text, "Build blog export archive", "Generate checksums", context="l0-snapshot.yml")
    assert_before(text, "Generate checksums", "Ensure draft GitHub pre-release", context="l0-snapshot.yml")
    assert_before(text, "Upload assets to draft pre-release", "Publish GitHub pre-release", context="l0-snapshot.yml")
    if 'gh release edit "$CURRENT_TAG"' in text:
        fail("unexpected post-draft gh release edit path in l0-snapshot.yml")
    assert_contains(
        text,
        "prev_tag=\"$(git tag --merged HEAD --sort=-v:refname | grep -E '^(l0-v|l0-snapshot-)' | grep -Fxv \"$CURRENT_TAG\" | head -n 1 || true)\"",
        context="l0-snapshot.yml",
    )
    assert_contains(
        text,
        "prev_tag=\"$(git tag --merged HEAD --sort=-v:refname | grep -E '^v[0-9]+\\.[0-9]+\\.[0-9]+$' | head -n 1 || true)\"",
        context="l0-snapshot.yml",
    )
    assert_before(text, "make check-examples", "make dist | tee build/dist.log", context="l0-snapshot.yml")


def check_docs_publish_workflow() -> None:
    text = read_text(".github/workflows/l0-docs-publish.yml")
    assert_contains(text, 'gh api "repos/$GITHUB_REPOSITORY/pages"', context="l0-docs-publish.yml")
    assert_contains(text, "pages_enabled=true", context="l0-docs-publish.yml")
    assert_contains(text, "pages_enabled=false", context="l0-docs-publish.yml")
    assert_contains(text, "attach_release_assets_to_draft:", context="l0-docs-publish.yml")
    assert_contains(text, 'description: "Attach release PDF/blog assets to an existing draft release"', context="l0-docs-publish.yml")
    assert_contains(text, "draft_release:", context="l0-docs-publish.yml")
    assert_contains(
        text,
        'description: "Draft release URL or numeric GitHub release ID for draft-release asset attachment"',
        context="l0-docs-publish.yml",
    )
    assert_contains(text, "attach-release-assets:", context="l0-docs-publish.yml")
    assert_contains(text, "always() &&", context="l0-docs-publish.yml")
    assert_contains(text, "needs.build-docs.result == 'success'", context="l0-docs-publish.yml")
    assert_contains(text, "(needs.deploy-pages.result == 'success' || needs.deploy-pages.result == 'skipped')", context="l0-docs-publish.yml")
    assert_contains(text, "inputs.attach_release_assets_to_draft", context="l0-docs-publish.yml")
    assert_contains(text, "Resolve target draft release", context="l0-docs-publish.yml")
    assert_contains(text, 'release_api="repos/$GITHUB_REPOSITORY/releases/$release_id"', context="l0-docs-publish.yml")
    assert_contains(text, 'release_url_prefix="https://github.com/$REPOSITORY_NAME/releases/tag/"', context="l0-docs-publish.yml")
    assert_contains(text, 'release_api="repos/$GITHUB_REPOSITORY/releases/tags/$release_tag"', context="l0-docs-publish.yml")
    assert_contains(text, "draft_release must target https://github.com/$REPOSITORY_NAME/releases/tag/<tag> when provided as a URL", context="l0-docs-publish.yml")
    assert_contains(text, "draft_release must be a numeric release ID or a full GitHub release URL", context="l0-docs-publish.yml")
    assert_contains(text, "draft_release URL must include a release tag after /releases/tag/", context="l0-docs-publish.yml")
    assert_contains(text, 'resolved_target_commitish="$(gh api "$release_api" --jq \'.target_commitish\')"', context="l0-docs-publish.yml")
    assert_contains(text, 'if [ -z "$source_ref" ] && [ "$INPUT_DRAFT_ATTACH" = "true" ]; then', context="l0-docs-publish.yml")
    assert_contains(text, 'source_ref="$RESOLVED_TARGET_COMMITISH"', context="l0-docs-publish.yml")
    assert_contains(text, "Validate target draft release", context="l0-docs-publish.yml")
    assert_contains(text, "draft release $RESOLVED_RELEASE_ID does not exist", context="l0-docs-publish.yml")
    assert_contains(text, "immutable-release violation", context="l0-docs-publish.yml")
    assert_contains(text, 'release_pdf="build/docs/pdf/dea_l0_api_reference-$RESOLVED_RELEASE_TAG.pdf"', context="l0-docs-publish.yml")
    assert_contains(text, 'existing_asset_ids="$(gh api "$release_api/assets" --paginate --jq ".[] | select(.name == \\"$asset_name\\") | .id")"', context="l0-docs-publish.yml")
    assert_contains(text, 'existing_asset_ids="$(gh api "$release_api/assets" --paginate --jq \'.[] | select(.name == "blog-export.tar.gz") | .id\')"', context="l0-docs-publish.yml")
    assert_contains(text, 'upload_url="$(gh api "$release_api" --jq \'.upload_url\' | sed \'s/{?name,label}//\')"', context="l0-docs-publish.yml")
    assert_contains(text, '--input "$release_pdf"', context="l0-docs-publish.yml")
    assert_contains(text, "--input blog-export.tar.gz", context="l0-docs-publish.yml")
    assert_contains(text, 'pdf_url="https://github.com/${GITHUB_REPOSITORY}/releases/download/${TARGET_RELEASE_TAG}/dea_l0_api_reference-${TARGET_RELEASE_TAG}.pdf"', context="l0-docs-publish.yml")
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
    assert_contains(text, "uses: actions/checkout@v6", context="l0-docs-build.yml")


def check_docs() -> None:
    if MONOREPO_ROOT is None:
        return

    monorepo = read_monorepo_text("MONOREPO.md")
    assert_contains(monorepo, "Pre-monorepo history keeps its original bare tags.", context="MONOREPO.md")
    assert_contains(monorepo, "`v0.9.0`, `v0.9.1`, and older", context="MONOREPO.md")
    assert_contains(monorepo, "`l0-vX.Y.Z`", context="MONOREPO.md")
    assert_contains(monorepo, "`l1-vX.Y.Z`", context="MONOREPO.md")

    readme = read_monorepo_text("README.md")
    assert_contains(readme, "Pre-monorepo bare tags such as `v0.9.0` and `v0.9.1` remain historical", context="README.md")
    assert_contains(readme, "current L0 releases use `l0-vX.Y.Z`", context="README.md")


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
