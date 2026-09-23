# Tool Plan

## Dea/L0 2.1.1 Release Preparation

- Date: 2026-09-23
- Status: Completed
- Title: Prepare and locally validate the L0 2.1.1 release
- Kind: Tooling
- Severity: Medium
- Stage: Shared
- Subsystem: Release documentation, version metadata, and local validation
- Modules:
  - `l0/docs/releases/`
  - `l0/pyproject.toml`
  - `uv.lock`
  - Root and L0 entry points and project-status documents
- Test modules:
  - `l0/tests/test_release_tag_policy.py`
- Related:
  - [l0/docs/decisions/0017-release-identity-integrity-and-immutable-publication.md](../../../../docs/decisions/0017-release-identity-integrity-and-immutable-publication.md)
  - [l0/work/plans/tools/closed/2026-09-09-release-2-1-0-preparation-noref.md](2026-09-09-release-2-1-0-preparation-noref.md)
- Repro: `cd l0 && make test-release-tags`

## Summary

Prepare one consolidated local release commit for L0 2.1.1 using `l0-v2.1.0` as the change-history baseline. The
canonical release notes cover the L0 ARC comparison cleanup and shared AddressSanitizer test validation changes while
excluding L1-only implementation work. The local commit also updates package metadata and release-facing documents.
Local preparation is complete. The eventual stable tag must target that exact commit. Remote validation, tag creation,
and publication are separate follow-up steps.

## ADR Impact

- Decision: Apply the existing L0 release identity and publication contract to 2.1.1.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This preparation updates release content and metadata without changing the established release contract
    or introducing an architectural decision.

## Preparation

1. Add the curated `l0/docs/releases/2.1.1.md` body and release-index entry.
2. Update the L0 package and workspace lock metadata to `2.1.1.dev0` without changing dependencies.
3. Refresh current-release references while retaining historical 2.1.0 descriptions.
4. Validate the notes, docs, metadata, and exact staged change before making one local commit.

## Validation Evidence

- `make venv` passed after granting access to the shared uv cache.
- From `l0/`, `make test-release-tags`, `make test-dist`, and `make test-dea-build` passed.
- From `l0/`, `L0_DOCS_RELEASE_TAG=l0-v2.1.1 ../.venv/bin/python scripts/gen_docs.py --strict --no-latex` passed.
- From the root, `uv lock --check` and `python3 scripts/check_adr_impact.py --all-active` passed.
- The release heading and local Markdown links in edited documents passed a direct check. Only the L0 workspace package
  version changed in `uv.lock`; dependencies are unchanged.
- Staged whitespace and ADR Impact checks passed. Root pre-commit passed its copyright, ADR Impact, and mdformat hooks.
- The local change is release documentation and package-version metadata only. Compiler and runtime validation for the
  exact release commit remains a required public CI gate before publication.

## Handoff and Publication Boundary

This plan ends at the local consolidated commit. The project maintainer must review the exact committed note before
publication. Public CI, commit promotion, tag creation, and publication follow as separately authorized steps. Public
writes, release tags, workflow dispatches, and publication are outside this preparation. The stable workflow publishes
the checked-in note unchanged, and a tag push can publish release assets, deploy Pages, and dispatch a downstream blog
update.
