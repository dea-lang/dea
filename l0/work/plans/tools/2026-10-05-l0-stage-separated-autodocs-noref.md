# Tool Plan

## Split L0 Stage 1 and Stage 2 autodocs and distribute the Stage 2 reference

- Date: 2026-10-05
- Status: Draft
- Title: Split L0 Stage 1 and Stage 2 autodocs and distribute the Stage 2 reference
- Kind: Tooling
- Severity: Medium
- Stage: L0
- Subsystem: Doxygen / HTML and PDF generation / distribution and release documentation
- Targets:
  - Independent Stage 1 and Stage 2 HTML/PDF: Pending
  - Stage 2 documentation in compiler archives and release assets: Pending
  - Existing Pages/blog/export consumer migration: Pending
- Modules:
  - `l0/scripts/gen_docs.py`
  - `l0/compiler/docgen/`
  - `l0/scripts/docs/templates/`
  - `l0/scripts/gen_dist_tools.py`
  - `l0/scripts/dist_tools_lib.py`
  - `l0/Makefile`
  - `l0/docs/README.md`
  - `l0/docs/project-status.md`
  - `.github/workflows/l0-docs-build.yml`
  - `.github/workflows/l0-docs-validate.yml`
  - `.github/workflows/l0-docs-publish.yml`
  - `.github/workflows/l0-release.yml`
  - `.github/workflows/l0-snapshot.yml`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_docgen_source_scope.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_cli.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_python_filter.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_l0_filter.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_markdown_renderer.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_latex.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_blog.py`
  - Existing distribution/workflow regression suites, extended for Stage 2 docs
- Related:
  - [l1/work/plans/tools/2026-10-05-l1-stage-separated-autodocs-noref.md][l1-docs]
  - [l0/docs/decisions/0023-toolchain-installation-and-distribution-layout.md][distribution-adr]
  - [l0/docs/decisions/0017-release-identity-integrity-and-immutable-publication.md][release-adr]
  - [docs/decisions/0017-documentation-publication-ownership-and-cross-repository-boundary.md][publication-adr]

## Summary

Split the current combined L0 source reference into independent Stage 1 and Stage 2 HTML/PDF documents. Keep Stage 1
available for development and oracle inspection; distribute only Stage 2 autodocs with L0's self-hosted Stage 2
compiler. Preserve the current generator's rendering quality, provenance, strict validation, and publication
authorization rules.

## Current State

Reviewed on 2026-10-05:

- `build_source_manifest` includes Stage 1 Python, Stage 2 L0 sources, a Stage 2 trace tool, and shared stdlib/runtime
  inputs in one manifest. HTML/Markdown renderer stage hubs still consume the same XML database.
- The wrapper produces one `build/docs/{html,markdown,doxygen,pdf}` tree, one `dea_l0_api_reference.pdf`, and one
  `build/preview/` tree. Another build replaces the common preview.
- Documentation workflows upload generic `docs-markdown` and `docs-pdf` artifacts and stage one Pages site.
- Stable/snapshot release workflows build docs alongside the four-platform dist matrix. They attach the combined PDF and
  API-reference export separately; the export `.tar.gz` is a Chirpy-oriented Markdown artifact, not an offline HTML/PDF
  bundle. Current distribution extras copy selected hand-authored docs and examples.
- Installed and distributed compilers are already self-built Stage 2. The combined reference is the part that needs
  stage separation, followed by explicit Stage 2 autodoc inclusion in distributions.

## Source and Generation Contract

Add `--stage {stage1,stage2,all}` to the wrapper and generator, defaulting to `all` for local generation. `all` invokes
independent pipelines. Select the manifest before Doxygen and keep XML, rendering, warnings, search, indexes, and
cross-reference databases separate.

| Document | Compiler sources                                                       | Shared inputs                      |
| -------- | ---------------------------------------------------------------------- | ---------------------------------- |
| Stage 1  | `compiler/stage1_py/**/*.py`, excluding tests/cache                    | L0 stdlib and required runtime API |
| Stage 2  | `compiler/stage2_l0/src/**/*.l0` and explicitly selected Stage 2 tools | L0 stdlib and required runtime API |

Inventory runtime headers from the current tree and build contracts rather than retaining an obsolete glob. Include
shared material in both documents so each is complete offline. Stage 2 contains no Stage 1 compiler symbols or Python
oracle pages. Audit renderer fallback maps such as Stage 1 label resolution, generated hubs, templates, and blog
grouping; removing the source files alone does not eliminate cross-stage assumptions.

Preserve strict warning checks, synthetic `__padN__` checks, signature normalization, source ordering, and filtered
Python/L0 semantics. Titles identify `Dea/L0 Stage 1` or `Dea/L0 Stage 2`. Ordinary generation does not publish.

## HTML/PDF Artifact Contract

For `S=1` or `S=2`, use these paths relative to `l0/`:

| Output              | Path                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------- |
| HTML and assets     | `build/docs/stageS/html/` with `index.html`                                                 |
| Markdown            | `build/docs/stageS/markdown/`                                                               |
| XML / LaTeX         | `build/docs/stageS/doxygen/xml/`, `build/docs/stageS/doxygen/latex/`                        |
| Complete PDF        | `build/docs/stageS/pdf/dea_l0_stageS_api_reference.pdf`                                     |
| Reports and preview | `build/docs/stageS/undocumented-functions.txt`, `build/preview/stageS/{html,markdown,pdf}/` |
| Consumer bundle     | `build/docs/artifacts/dea_l0_stageS_autodocs.tar.gz`                                        |

The bundle has one `dea-l0-stageS-autodocs/` root containing `html/`, `pdf/dea_l0_stageS_api_reference.pdf`, and
`manifest.json`. HTML assets and PDF links resolve locally; XML, generated Markdown, logs, and LaTeX scratch stay out.
The manifest records schema version 1, level `l0`, stage, package version, source revision/dirty state and
selected-input digest, tool versions, strict/full-PDF success, and relative file digests excluding itself. Validate safe
members and reject mismatched or stale identities before consumption.

Keep `L0_DOCS_RELEASE_TAG` as the release-label input and `DEA_DIST_VERSION` as package version. Add
`make docs-artifacts DOC_STAGE=stage2 DEA_DIST_VERSION=<version>`, while `make docs` and `make docs-pdf` accept
`DOC_STAGE` and default to independent builds of both stages. `--output-dir` names their common parent. `--pdf-fast`
remains preview-only and cannot generate a distribution success manifest. Replace only the selected stage's successful
outputs; one stage cannot delete the other stage's outputs or reuse its PDF after a failure.

## Distribution and Workflow Integration

1. Add explicit `DOCS_ARTIFACT=<absolute-stage2-bundle-path>` consumption to L0 dist tooling. Embed verified contents
   under `share/doc/dea/l0/autodocs/stage2/` in every `dea-l0/` archive. Keep existing hand-authored user documentation
   and examples. Full distributions require HTML and PDF; missing or invalid docs fail with a generation hint.
   `make install` may remain compiler-only or include the same explicit docs bundle. Do not invoke TeX implicitly.
2. Build complete Stage 2 docs once from the exact release/snapshot source, then feed the same verified artifact into
   all platform dist builds. Reverse the current independent docs/dist scheduling as needed. Match version/source
   provenance, check embedded doc digests after extraction, and keep TeX off platform compiler-build runners.
3. Extend the reusable docs workflow with explicit stage selection and stage-qualified artifact names. Validation builds
   both documents independently; publication and dist consumers explicitly request Stage 2. Retain Stage 1 as a separate
   developer/validation artifact, never part of the compiler release set.
4. Future release sets contain the four compiler archives, `dea_l0_stage2_api_reference-<TAG>.pdf`,
   `dea_l0_stage2_autodocs-<TAG>.tar.gz`, the existing API export now named `dea_l0_stage2_api_reference-<TAG>.tar.gz`,
   and `SHA256SUMS`. The autodocs bundle and Chirpy export are different artifacts. Restrict the export to Stage 2 plus
   shared material; preserve current opt-in downstream notification. Update required asset lists and checksum coverage
   together before enabling the new contract.
5. Update manual docs publication, draft attachment, Pages staging, PDF URLs, and export consumers to select the correct
   stage explicitly. Root workflow files and their publication policy remain monorepo-owned; include their integration
   review in this plan rather than changing the established authorization boundary.

## Existing URL and Artifact Migration

Published releases remain immutable. Never rename, replace, or remove old mixed-reference assets. The stage-qualified
contract starts with newly prepared releases/snapshots, and versioned historical links continue pointing at their
original files.

Keep the current unversioned Pages entrypoint as the Stage 2 reference to preserve the normal documentation destination.
Retain a compatibility copy at the current unversioned PDF URL that now serves the Stage 2 PDF, with a clearly labeled
Stage 2 title. Migrate internal links and new exports to stage-qualified PDFs. For old unversioned HTML paths, redirect
only where an equivalent Stage 2/shared page exists; removed Stage 1 paths should lead to an explicit migration notice
rather than a wrong same-named symbol. Stage 1 remains available through local generation and validation artifacts;
separate public Stage 1 hosting is outside scope. Any optional future hosting must use its own site/search root.

Test the export's legacy input compatibility for historical downloads separately from new stage-qualified output.
Document the filename/URL migration and downstream import requirement before the first new publication. Destination
repositories still own import and deployment; this plan does not authorize edits or messages to those repositories.

## Implementation Phases

1. Parameterize source manifests and all renderer/template assumptions. Add stage boundary tests before changing output
   paths. Preserve the current filters and explicitly inventory shared inputs.
2. Introduce isolated output/preview paths and full HTML/PDF generation. Validate both stages' real source inventories;
   inspect representative pages, PDF contents/indexes, and duplicate-name cross-references.
3. Implement docs manifests/bundles, explicit dist consumption, extraction/digest checks, and stage-qualified workflow
   artifacts. Wire docs before the four dist builds and update release/checksum completeness tests.
4. Migrate Pages/export/draft-attachment paths and document compatibility behavior. Run local workflow and publication
   tests with mocked remote operations. Exercise hosted behavior only under the repository's separate authorization.
5. Update current docs, amend the specified ADRs and indexes/backlinks, and close after implementation and local
   artifact verification. Record any deferred authorized hosted exercise explicitly; published historical assets stay
   untouched.

## ADR Impact

- Decision: Produce separate stage references and include only Stage 2 autodocs in L0 distributions.
  - Scope: L0
  - Disposition: Amend ADR
  - ADR: `l0/docs/decisions/0023-toolchain-installation-and-distribution-layout.md`
  - Rationale: The required distribution payload gains offline Stage 2 HTML/PDF and a versioned documentation manifest.
- Decision: Replace the combined documentation assets with stage-qualified assets in future L0 releases.
  - Scope: L0
  - Disposition: Amend ADR
  - ADR: `l0/docs/decisions/0017-release-identity-integrity-and-immutable-publication.md`
  - Rationale: The complete release set and checksum contract change while already published releases remain immutable.
- Decision: Preserve local generation, opt-in export, and destination-owned publication boundaries during migration.
  - Scope: Repository/tooling
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0017-documentation-publication-ownership-and-cross-repository-boundary.md`
  - Rationale: Splitting artifacts changes their identity and consumers, not ownership or remote-write authorization.

## Non-Goals

- Changes to L0 compiler semantics, bootstrap stage selection, or release tag namespaces.
- Shipping Stage 1 autodocs with Stage 2 distributions, or merging the two references into one output again.
- Rewriting published release assets or directly updating an external blog repository.
- Implementing L1 documentation generation or requiring its plan to land first.

## Verification Criteria

1. Stage manifests, XML, HTML search/navigation, Markdown, LaTeX, PDFs, and reports are isolated; shared material is
   explicitly included in both. Duplicate symbols resolve within the selected document.
2. Real strict builds of both stages pass, with full PDF rendering checked and representative output reviewed. Stage 2
   works offline with no Stage 1 files or network asset dependencies.
3. Dist archives on all four hosts contain the same matching Stage 2 docs bundle contents and no Stage 1 autodocs.
   Wrong-stage, mismatched-source/version, partial, unsafe, or stale bundles fail before archive publication.
4. Workflow tests prove docs precede dist builds, failed docs block releases, and all new assets appear in checksums.
   Generation/validation has no release or deployment permissions or side effects.
5. Pages/PDF compatibility and new stage-qualified export URLs are verified locally. Historical release asset names
   remain unchanged, and attempts to mutate published releases still fail.
6. Existing docgen, relevant dist/workflow tests, new stage-isolation tests, and Markdown/ADR checks pass. Record
   outcomes without specific workflow-run identifiers. Any remote verification follows `AGENTS.md` authorization gates.

[distribution-adr]: ../../../docs/decisions/0023-toolchain-installation-and-distribution-layout.md
[l1-docs]: ../../../../l1/work/plans/tools/2026-10-05-l1-stage-separated-autodocs-noref.md
[publication-adr]: ../../../../docs/decisions/0017-documentation-publication-ownership-and-cross-repository-boundary.md
[release-adr]: ../../../docs/decisions/0017-release-identity-integrity-and-immutable-publication.md
