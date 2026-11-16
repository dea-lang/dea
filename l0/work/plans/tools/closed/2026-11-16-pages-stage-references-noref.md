# Tool Plan

## Restore both L0 stage references on Pages

- Date: 2026-11-16
- Status: Completed
- Completed: 2026-11-16
- Title: Restore both L0 stage references on Pages
- Kind: Tooling
- Priority: Medium
- Stage: Shared
- Subsystem: Documentation publication
- Modules:
  - `l0/scripts/stage_docs_pages.py`
  - `l0/compiler/docgen/l0_docgen_blog.py`
  - `.github/workflows/l0-docs-build.yml`
  - `.github/workflows/l0-release.yml`
  - `.github/workflows/l0-docs-publish.yml`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_docgen_stage_artifacts.py`
  - `l0/tests/test_release_tag_policy.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_blog.py`

## Summary

Restore public browsing of Stage 1 alongside Stage 2. Keep Stage 2 at the existing Pages root and Stage 1 under
`stage1/`, each with independent navigation, search data, and PDFs. Add a stage selector only to staged Pages HTML;
compiler bundles and blog exports continue to contain Stage 2 alone. This restores developer reference access without
changing compiler semantics or the immutable release asset set.

## Implementation

- Aggregate independently built HTML/PDF artifacts after both stage builds succeed, then upload one Pages artifact.
- Preserve existing Stage 2 URLs and the legacy PDF alias; route retired Stage 1 URLs to the matching new page where
  available, otherwise to the Stage 1 home. Retain an informative missing-page fallback.
- Validate selectors, nested links, search separation, missing inputs, workflow dependencies, and Stage 2-only
  packaging.
- Identify the Stage 2 blog reference and link to both HTML references and their separate PDFs; keep Stage 2 content and
  release asset selection unchanged.
- Update current documentation and the release/publication decision record. Preserve historical release notes.

## Verification

- Documentation regression suite: 187 tests passed before the final workflow-input coverage addition. The final
  artifact/Pages suite passed 45 tests, including HTML-only and HTML/PDF workflow staging, isolated search payloads,
  nested selectors, historical redirects, incomplete-input preservation, and Stage 2-only archives on four host
  fixtures.
- Release-tag/workflow policy checks passed, including the two-stage Pages dependency and unchanged Stage 2-only
  compiler, release, and blog consumers. Actionlint passed with the established `ubuntu-26.04` runner label supplied
  through a temporary configuration because the installed linter's label inventory predates that runner.
- Reused generated HTML was assembled into 989 Pages HTML files. Checked 19,072 local links; all non-PDF targets
  resolved; both search payloads remained byte-identical to their inputs. The existing local outputs had no PDFs: PDF
  placement and the legacy alias were verified with fixtures, without rerunning the unchanged TeX pipeline.
- Blog exporter checks passed 15 tests, covering stage-specific introductory text, both PDF labels, site-root URL
  joining, absent optional URLs, and historical mixed-input handling. The generated Stage 2 tab introduction matches the
  local blog page exactly; its PDF links distinguish the current Pages Stage 1 PDF from the versioned Stage 2 asset.
- Local browser verification passed for the selector in both directions and a Stage 1 search result opening inside its
  own reference. Searching `l0_ast` returned four Stage 1 results and no Stage 2 results.
- Formatting, whitespace, copyright, pre-commit, and ADR closure/backlink checks passed. Closure was checked against the
  working tree without changing the Git index.

This is trace-independent documentation tooling work; compiler/runtime validation beyond the focused packaging
regressions is unnecessary. Hosted Actions and public deployment remain unexecuted.

## Publication Boundary

Local implementation, validation, and local commits are in scope. No push, tag, workflow dispatch, deployment, release
asset replacement, or downstream notification is authorized. The public site remains unchanged until a separately
authorized Pages publication from the updated source.

## ADR Impact

- Decision: Serve both L0 references on Pages while retaining Stage 2-only compiler and release assets.
  - Scope: L0
  - Disposition: Amend ADR
  - ADR: `l0/docs/decisions/0017-release-identity-integrity-and-immutable-publication.md`
  - Rationale: Clarify the distinction between the public Pages reference and immutable release assets.
