# Tool Plan

## Versioned Dea/L0 API Reference Export Archive

- Date: 2026-05-07
- Status: Completed (producer landed; consumer redeployed)
- Title: Rename markdown release archive to `dea_l0_api_reference-<TAG>.tar.gz` and align prose
- Kind: Tooling
- Severity: Low
- Stage: Shared
- Subsystem: CI / docs publishing
- Modules:
  - `.github/workflows/l0-release.yml`
  - `.github/workflows/l0-snapshot.yml`
  - `.github/workflows/l0-docs-publish.yml`
  - `.github/workflows/l0-docs-validate.yml`
  - `l0/tests/test_release_tag_policy.py`
  - `l0/docs/README.md`
  - `l0/work/plans/tools/attachments/blog-poll-workflow.yml`

## Summary

On release, the L0 API reference is published with two artifacts:

- A versioned PDF named `dea_l0_api_reference-<TAG>.pdf`.
- A markdown export historically named `blog-export.tar.gz` — unversioned and lacking the `dea_l0_api_reference` prefix.

The asymmetry makes the markdown archive harder to identify in release listings and harder to pin to a specific tag.
This plan renames the markdown archive to mirror the PDF naming and aligns user-facing prose with the artifact's actual
role (the Dea/L0 API reference), while preserving the Chirpy-compatible markdown format and all existing symbol
identifiers (env vars, input names, module names, artifact upload-artifact `name:` fields, repository-dispatch event
types).

## Problem

- The release PDF is versioned (`dea_l0_api_reference-<TAG>.pdf`), but the markdown archive (`blog-export.tar.gz`) is
  not. Both describe the same artifact family — the Dea/L0 API reference — at the same release tag.
- Step names, input descriptions, comments, and README prose talk about a generic "blog export", which obscures the fact
  that the archive is the API reference.
- The output build directory `build/docs/blog-export/` reinforces the same misnomer.

## Solution

### Decisions

- New archive filename: `dea_l0_api_reference-<TAG>.tar.gz` (e.g. `dea_l0_api_reference-l0-v1.0.0-test9.tar.gz`).
- New build output directory: `build/docs/api-reference/`.
- Prose rename `blog` → `Dea/L0 API reference` in user-facing strings (CI step names, `workflow_dispatch` input
  descriptions, comments, README prose). Where "Dea/L0" would immediately follow a `/` (slash-joined compound), use just
  "API reference" for readability.
- Keep "Chirpy-compatible" / "Chirpy-compatible markdown" where it accurately describes the *format* of the export.
- Symbol identifiers remain unchanged to avoid breaking external consumers: `publish_blog` workflow input, `BLOG_REPO`,
  `BLOG_PUSH_TOKEN`, `BLOG_DOCS_PREFIX`, `BLOG_TAB_TITLE`, `BLOG_TAB_ICON`, `BLOG_TAB_ORDER` env/vars, module
  `compiler.docgen.l0_docgen_blog`, artifact `name: blog-export`, job id `upload-blog-export`,
  `event_type=blog-docs-update`.

### Producer side (Dea repo) — landed

- `l0-release.yml`: archive renamed at the templated form
  `"build/release-assets/dea_l0_api_reference-${CURRENT_TAG}.tar.gz"`. Tar source retargeted to
  `build/docs/api-reference`. Checksum `required_assets` set updated. Step renamed to "Build Dea/L0 API reference export
  archive".
- `l0-snapshot.yml`: same shape using `CURRENT_TAG=${{ needs.prepare-snapshot.outputs.snapshot_tag }}`.
- `l0-docs-publish.yml`:
  - Draft-release attach branch (around the "Create blog export archive" step) renamed and templated using
    `RESOLVED_RELEASE_TAG`. Asset-id lookup, `--input`, and `?name=` upload query parameter use a single `archive_name`
    variable.
  - Non-draft `upload-blog-export` job renamed; falls back to `dea_l0_api_reference.tar.gz` when `TARGET_RELEASE_TAG` is
    empty (`dea_l0_api_reference${TARGET_RELEASE_TAG:+-$TARGET_RELEASE_TAG}.tar.gz`), emitted as a step output.
  - Input descriptions for `publish_blog`, `attach_release_assets_to_draft`, and `release_tag` updated.
- `l0-docs-validate.yml`: `--output build/docs/api-reference`.
- `l0/tests/test_release_tag_policy.py`: assertions updated to the new templated forms and new directory.
- `l0/docs/README.md`: prose rephrased; describes the artifact as a Chirpy-compatible markdown export of the Dea/L0 API
  reference at `build/docs/api-reference/`.

### Consumer side (external blog repo) — pending rollout

The reference workflow at `l0/work/plans/tools/attachments/blog-poll-workflow.yml` is updated alongside this plan to
derive the archive filename from the resolved release tag. Concretely:

- `Resolve source` step now emits `archive_name` (and an `archive_name` for the run-id branch too) so subsequent steps
  use a single source of truth.
- Release-asset URL becomes
  `https://github.com/$DEA_SOURCE_REPO/releases/download/$tag/dea_l0_api_reference-$tag.tar.gz`.
- `curl` download writes to `$archive_name`; `tar -xzf` and the cleanup `rm -f` operate on `$archive_name`.
- Run-id download path uses `gh run download` which still pulls the artifact by its workflow-artifact `name:` (unchanged
  symbol `blog-export`); the unpacked filename inside the artifact is the new versioned form.

Operators who have already deployed the previous reference workflow into their blog repo must redeploy the updated
attachment, replacing their `poll-dea-docs.yml`. Until they do, polling will fail with a 404 on the previous fixed-name
URL after the next L0 release.

## Migration / Rollout

1. Land the producer-side changes (this commit). Existing releases keep the old `blog-export.tar.gz` asset name; only
   future releases will publish under the new name.
2. Update the reference attachment in this plan (this commit) so the documented consumer matches.
3. Operators of downstream blog repos (typically the L0 maintainer's Chirpy site) redeploy the updated
   `poll-dea-docs.yml` before the next L0 release/snapshot is cut.
4. After the first release/snapshot under the new naming, validate end-to-end that the consumer fetches the versioned
   archive and commits the synced docs. Then move this plan into `l0/work/plans/tools/closed/`.

## Verification

- `python l0/tests/test_release_tag_policy.py` — passes.
- `uv run --group dev pre-commit run --hook-stage pre-commit -c .pre-commit-config.yaml --files <changed>` — passes.
- `rg 'blog-export\.tar\.gz|build/docs/blog-export' .github/ l0/` returns no matches in producer/test/doc files. The
  attachment under `l0/work/plans/tools/attachments/` is updated in lockstep.
- End-to-end on a test snapshot tag: inspect the draft release assets list and confirm `dea_l0_api_reference-<TAG>.pdf`,
  `dea_l0_api_reference-<TAG>.tar.gz`, and `SHA256SUMS` listing both.
- End-to-end on the consumer side after redeployment: a scheduled poll (or manual `workflow_dispatch`) downloads the
  versioned archive and commits the synced docs with the marker file updated to the new tag.

## Completion

- 2026-05-07: Consumer-side rollout completed. Operators of downstream blog repos have redeployed the updated
  `poll-dea-docs.yml` derived from `l0/work/plans/tools/attachments/blog-poll-workflow.yml`. End-to-end sync against the
  new versioned `dea_l0_api_reference-<TAG>.tar.gz` asset has been validated. Plan moved to
  `l0/work/plans/tools/closed/`.
