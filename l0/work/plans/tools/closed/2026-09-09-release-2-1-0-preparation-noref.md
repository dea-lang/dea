# Tool Plan

## Dea/L0 2.1.0 Release Preparation

- Date: 2026-09-10
- Status: Completed
- Title: Prepare and locally validate the L0 2.1.0 release
- Kind: Tooling
- Severity: Medium
- Stage: Shared
- Subsystem: Release documentation, version metadata, and local artifact verification
- Modules:
  - `l0/docs/releases/`
  - `l0/pyproject.toml`
  - `uv.lock`
  - Root and L0 entry points and project-status documents
- Test modules:
  - `l0/tests/test_release_tag_policy.py`
  - `l0/tests/test_make_dist_workflow.py`
  - `l0/tests/test_make_dea_build_workflow.py`
- Related:
  - [l0/docs/decisions/0017-release-identity-integrity-and-immutable-publication.md](../../../../docs/decisions/0017-release-identity-integrity-and-immutable-publication.md)
  - [l0/docs/decisions/0027-public-c-runtime-header.md](../../../../docs/decisions/0027-public-c-runtime-header.md)
  - [docs/decisions/0021-runtime-hash-semantic-domains-and-stability.md](../../../../../docs/decisions/0021-runtime-hash-semantic-domains-and-stability.md)
- Repro: `cd l0 && make test-release-tags`

## Summary

Prepare one consolidated local release commit for L0 2.1.0 using `l0-v2.0.0` as the exclusive change-history baseline.
The commit contains canonical release notes, package metadata, and final release-facing documentation suitable for the
stable tag. Local preparation is complete; public CI, snapshot rehearsal, tagging, and publication remain separate
follow-up work. Release-facing wording is not evidence that publication has occurred.

## ADR Impact

- Decision: Apply the established L0 release and compatibility contracts to 2.1.0 preparation.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This operational preparation applies existing release identity, public C header, and runtime hash
    decisions without changing architecture, compatibility policy, or publication behavior.

## Final Commit Contents

- Canonical notes in [l0/docs/releases/2.1.0.md](../../../../docs/releases/2.1.0.md) cover public C interoperability,
  vector alias safety, optional hashes, sanitizer visibility, compiler decomposition, Python modernization, editor
  fixes, and delivery improvements. They distinguish the new header from the existing `--c-source` option and exclude
  L1-only features.
- L0 package and workspace lock metadata use `2.1.0.dev0`. Dependency versions remain unchanged.
- Root/L0 entry points, contributor guidance, project-status pages, the release index, and the release ADR's current-doc
  link identify 2.1.0 as the current release. Historical descriptions of the 2.0.0 language and CLI changes remain
  intact.
- This completed preparation record retains validation evidence and publication boundaries. The temporary two-commit
  preparation sequence is consolidated into one local commit before any push.
- No compiler, runtime, language, public API, diagnostic code, build behavior, or workflow is changed by this
  preparation. Generated artifacts remain outside Git.

## Validation Evidence

Validation completed on September 9 on the local Intel macOS host before the documentation-only consolidation:

- From `l0/`, `make test-release-tags`: passed separately and within the normal workflow suite.
- From the root, `PYTEST_XDIST_AUTO_NUM_WORKERS=4 make clean test`: passed, using the default TCC selection. L0 passed
  1,525 Stage 1 tests, all 58 Stage 2 groups including triple bootstrap, eight examples, 13 runtime build-flag tests,
  and all installation/distribution, provenance-fallback, release-policy, and source-selection checks. L1 passed all 73
  normal test groups, environment stackability, and four examples.
- A parsed before/after lockfile comparison confirmed that only the L0 package-version record changed; no dependency
  versions or other lock records changed.
- From `l0/`, `L0_DOCS_RELEASE_TAG=l0-v2.1.0 ../.venv/bin/python scripts/gen_docs.py --strict --pdf`: passed on the
  clean pre-consolidation revision. HTML and Markdown include the public runtime declarations. The 1,260-page PDF
  contains the release label and clean source identity; its cover and public runtime header section passed visual
  inspection.
- From `l0/`, `DEA_DIST_VERSION=2.1.0 make dist`: passed on the same clean revision. The macOS Intel archive was
  extracted into a fresh temporary directory and tested outside the checkout with source-tree environment overrides
  removed. Version and clean-tree provenance matched, and all 22 packaged stdlib/header files matched the checkout.
  Hello, the two-file C interoperability example, and a direct foreign-C `rt_strlen` call produced their expected
  output.
- Release heading, local links, active/staged ADR policy, whitespace, and root pre-commit checks passed during
  preparation.

The September 8 [public Unified CI run](https://github.com/dea-lang/dea/actions/runs/34249219862) passed L0 `test-all`
on Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64, plus strict documentation validation. This is retained as
trace-inclusive evidence for unchanged compiler/runtime inputs, not as CI for the consolidated release commit.

## Consolidation Validation

Compare the replacement tree with the pre-consolidation tree. Reuse the normal suite, runtime trace evidence, and
artifact behavior checks only while compiler, runtime, tests, build configuration, package metadata, dependencies,
generated-source inputs, and toolchain selection remain unchanged. The final release-wording edits are Markdown-only and
do not require repeating the compiler suites or broad trace sweep.

Run strict documentation generation without LaTeX, release-tag policy, edited-link checks, active/staged ADR validation,
staged whitespace checks, and root pre-commit for the consolidated change. Verify that exactly one commit replaces the
two local preparation commits and that the committed tree matches the reviewed staged tree.

On September 10, strict documentation generation with `--no-latex`, release-tag policy, edited-link checks, and
active/staged ADR validation passed. The comparison with the pre-consolidation tree confirmed that only Markdown
changed; the successful compiler suites remain applicable.

The earlier archive and PDF embed the pre-consolidation source revision. They remain historical validation evidence, not
distributable artifacts for the replacement commit. Subsequent snapshot and stable-release workflows must rebuild
artifacts from their exact target revision.

## Handoff and Publication Boundary

Local preparation is completed. Report the consolidated commit, reused and fresh validation, clean worktree status, and
the original local revision as a reflog recovery point. Publication has not been performed or verified by this work.

The user will push to `ci-probe` manually. Public CI for the consolidated revision, an optional draft snapshot
rehearsal, promotion to `main`, stable tag creation and push, release publication, Pages deployment, and downstream blog
dispatch remain separately authorized follow-up actions. No remote operation, upstream change, tag, or announcement copy
is part of this consolidation. The final release-facing documentation is already in the candidate; no later
release-status commit is required before tagging that candidate.
