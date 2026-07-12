# Tool Plan

## Dea/L0 1.1.0 Release Preparation

- Date: 2026-07-13
- Status: In Progress
- Title: Prepare, validate, and publish the Dea/L0 1.1.0 release
- Kind: Tooling
- Severity: High
- Stage: Shared
- Subsystem: Release management / documentation / distribution / CI
- Modules:
  - `.github/workflows/l0-release.yml`
  - `l0/docs/releases/`
  - `l0/pyproject.toml`
  - `uv.lock`
  - `l0/work/plans/tools/attachments/release-1.1.0-blog-draft.md`
- Test modules:
  - `l0/tests/test_release_tag_policy.py`
- Related:
  - `l0/work/plans/features/2026-06-08-case-else-removal-l0-phase2-noref.md`
  - `l0/work/plans/tools/closed/2026-05-01-immutable-release-workflows-noref.md`
- Repro: `cd l0 && make test-workflows`

## Summary

Prepare and publish Dea/L0 1.1.0 using `l0-v1.0.0` as the exclusive change-history baseline. This is a minor release
under [Semantic Versioning 2.0.0](https://semver.org/): the canonical `_ =>` `case` default is a backward-compatible
language addition, while the old `else` form remains accepted with a deprecation warning. ASCII identifier enforcement
and rejection of `let` in a `for` update clause are correctness tightenings, which must be called out prominently in the
migration notes.

The release notes are curated by user-facing theme. They exclude L1-only changes, commit-history churn, and raw log
output. The public `googlielmo/dea-lang` repository is the sole release target; the private monorepo does not receive a
duplicate GitHub release.

## Defaults Chosen

1. Release version and tag: `1.1.0` and `l0-v1.1.0`.
2. Release-notes source: `l0/docs/releases/1.1.0.md`, used unchanged as the GitHub release body.
3. Public history boundary: the full comparison from `l0-v1.0.0` through `l0-v1.1.0`.
4. Blog title: "Dea/L0 1.1.0: safer control flow and a frontend that keeps going".
5. Deprecated `case ... else` removal is deferred to Dea/L0 2.0.0 and does not block this release.

## Goals

1. Document the release under five themes: language and source contract, frontend recovery and diagnostics, control-flow
   and ownership safety, Stage 2 and portability, and documentation and examples.
2. Publish explicit migration guidance for `case`, `for`, Unicode source text, diagnostic recovery, and Stage 2 warning
   visibility.
3. Make stable release tags and their curated notes a validated one-to-one mapping in the release workflow.
4. Validate the exact release-preparation revision in both private and public CI before creating the public tag.
5. Publish and verify all release assets, generated documentation, checksums, dispatches, and the announcement post
   before closing this plan.

## Implementation Phases

### 1. Canonical release content

- Add `l0/docs/releases/1.1.0.md` as the exact release body and `l0/docs/releases/README.md` as the release-notes index.
- Add the reviewed blog copy under `l0/work/plans/tools/attachments/` with the same Chirpy front matter used by existing
  Dea/L0 posts.
- State explicitly that no L0 standard-library implementation changed and that no CLI flags, CLI modes, or public L0
  types were added or removed.

### 2. Release policy and version metadata

- Restrict `.github/workflows/l0-release.yml` to stable `l0-vX.Y.Z` tags.
- Derive `l0/docs/releases/X.Y.Z.md` from the tag, reject missing or mismatched notes before publication, and use the
  file unchanged for draft creation and final publication.
- Preserve the immutable draft-first artifact workflow and current four-platform matrix while removing raw `git log`
  notes and previous-tag guessing.
- Extend `l0/tests/test_release_tag_policy.py` for valid tags, invalid tags, required notes, and the snapshot-tag
  namespace.
- Set current release-facing version metadata to `1.1.0` and package-development metadata to `1.1.0.dev0`, while
  preserving historical statements about earlier releases.
- Refresh the open L0 Phase 2 `case` plan so it links to current files, remains Draft, and defers removal of deprecated
  `case ... else` to L0 2.0.0.

### 3. Local validation

- Run root `make test-all`, then run `make docs`, focused release/workflow tests, and pre-commit from the prescribed
  repository directories.
- Build a local distribution with `DEA_DIST_VERSION=1.1.0`; verify its `VERSION`, `l0c --version`, archive layout, and
  checksums.
- Reconfirm both compiler stages for `_ =>`, `PAR-0242`, `PAR-0243`, `PAR-0145`, Unicode strings and comments, ASCII
  identifier rejection, lexer recovery, and warning visibility.

### 4. Public publication

- Mirror the reviewed release-preparation revision to `googlielmo/dea-lang/main` and require green public CI on that
  exact revision before tagging.
- Push the annotated `l0-v1.1.0` tag only to the public repository.
- Verify that the published release body exactly matches `l0/docs/releases/1.1.0.md` and that all seven expected assets
  are present: four platform archives, the API PDF, the API Markdown archive, and `SHA256SUMS`.
- Verify Pages/API documentation publication and the `blog-docs-update` dispatch.
- Copy the reviewed post into `googlielmo/gwz-blog/_drafts/`, preview it, run `bash tools/test.sh`, and publish it
  through that repository's normal Pages workflow.

## Verification Criteria

1. Stable release-tag validation rejects prerelease, snapshot, malformed, missing-notes, and notes-version mismatch
   cases before any release is published.
2. All local tests, documentation validation, release packaging checks, and pre-commit hooks pass.
3. Public CI passes on Linux x86_64, macOS x86_64, macOS arm64, and Windows UCRT64, with documentation and copyright
   validation green.
4. The release body, seven assets, checksums, Pages/API output, downstream dispatch, blog post, and all public links are
   live and mutually consistent.
5. This plan moves to `l0/work/plans/tools/closed/` only after every publication check succeeds.

## Non-Goals

1. Removing deprecated `case ... else` syntax before L0 2.0.0.
2. Publishing a release for the private monorepo or including L1-only changes in the notes.
3. Adding or changing L0 standard-library APIs, compiler modes, CLI flags, or public types as part of release
   preparation.
4. Publishing an unfiltered commit log as user-facing release notes.
