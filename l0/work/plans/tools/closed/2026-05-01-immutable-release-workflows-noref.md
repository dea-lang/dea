# Tool Plan

## Immutable-Compatible L0 Release Workflows

- Date: 2026-05-01
- Status: Implemented
- Title: Immutable-compatible L0 release workflows
- Kind: Tooling
- Severity: High
- Stage: Shared
- Subsystem: GitHub workflows
- Modules:
  - `.github/workflows/l0-release.yml`
  - `.github/workflows/l0-snapshot.yml`
  - `.github/workflows/l0-docs-publish.yml`
- Test modules:
  - `l0/tests/test_release_tag_policy.py`

## Summary

Convert the L0 release-bearing workflows to a draft-first publish model so release assets are fully assembled before
publication and no workflow mutates a published release. This covers stable `l0-v*` releases, snapshot prereleases, and
manual draft-asset preparation for docs/blog artifacts.

## Implementation Notes

- Stable and snapshot releases assemble dist archives, the versioned API PDF, `blog-export.tar.gz`, and `SHA256SUMS`
  before publication.
- `SHA256SUMS` must cover every staged release asset and record bare filenames with no `./` prefix.
- Snapshot manual dispatch keeps a draft-only mode through `publish_release=false`.
- `l0-docs-publish.yml` stays manual-only and may attach assets only to existing draft releases.

## Validation

- Run `make test-workflows`.
- Completed: `make test-workflows`.
