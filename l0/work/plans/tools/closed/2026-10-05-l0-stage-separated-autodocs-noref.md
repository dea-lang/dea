# Tool Plan

## Split L0 Stage 1 and Stage 2 autodocs and distribute the Stage 2 reference

- Date: 2026-10-05
- Status: Completed
- Completed: 2026-10-05
- Title: Split L0 Stage 1 and Stage 2 autodocs and distribute the Stage 2 reference
- Kind: Tooling
- Severity: Medium
- Stage: L0
- Subsystem: Doxygen / HTML and PDF generation / distribution and release documentation
- Targets:
  - Independent Stage 1 and Stage 2 HTML/PDF: Complete
  - Stage 2 documentation in compiler archives and release assets: Complete
  - Existing Pages/blog/export consumer migration: Complete
- Modules:
  - `l0/scripts/gen_docs.py`
  - `l0/scripts/docs_artifacts.py`
  - `l0/scripts/stage_docs_pages.py`
  - `l0/compiler/docgen/`
  - `l0/scripts/docs/templates/`
  - `l0/scripts/gen_dist_tools.py`
  - `l0/scripts/dist_tools_lib.py`
  - `l0/Makefile`
  - `l0/docs/README.md`
  - `l0/docs/project-status.md`
  - `.github/workflows/ci.yml`
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
  - `l0/compiler/stage1_py/tests/cli/test_docgen_stage_artifacts.py`
  - `l0/tests/docs_fixture.py`
  - `l0/tests/test_make_dist_workflow.py`
  - `l0/tests/test_release_tag_policy.py`
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

## Implementation and Findings

Implemented on 2026-10-05:

- Stage selection precedes Doxygen. Each stage has its own source shadow tree, XML, navigation/search, Markdown, LaTeX,
  HTML, PDF, reports, and preview. Renderer fallback maps remain valid against isolated XML.
- Shared inputs are the stdlib plus `dea_rt.h`, `dea_siphash.h`, and `l0_runtime.h`. Stage 2 explicitly includes
  `compiler/stage2_l0/scripts/check_trace_log.py`. A comment in that checker was reworded to prevent Doxygen from
  linking an ordinary reference to a missing parser page; execution behavior is unchanged.
- Successful outputs replace only their selected stage. Failed attempts preserve prior references and failure logs while
  invalidating the selected consumer bundle. Fast PDF generation cannot create a success manifest.
- Bundle verification rejects unsafe members, identity mismatches, missing strict/full-PDF success, partial payloads,
  and digest changes before compiler building or archive creation. Distribution installation remains compiler-only.
- Release/snapshot distributions wait for one shared Stage 2 bundle and verify extracted contents. Windows disables
  checkout newline conversion before source extraction to preserve the exact input fingerprint across platforms.
- Stage-qualified workflow artifacts, future eight-asset release sets, checksums, manual draft attachment, and Stage 2
  Chirpy export are wired. Unified CI routes changes to the new helpers into complete docs validation.
- Pages serves Stage 2, preserves the old PDF URL as an identical copy, and provides migration notices for retired Stage
  1 source/symbol URLs plus a fallback 404 page. Historical mixed exports remain accepted and published assets remain
  untouched.

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

## Verification Outcomes

- Repo-root `make clean test`: passed both levels' normal suites, examples, tooling, bootstrap, distribution, workflow,
  and release-policy checks. Reused normal compiler/build validation after unchanged runtime/compiler inputs; later
  documentation bundle and workflow changes received focused validation. This work is trace-independent: it changes
  generation, packaging, and CI routing, with no lifetime, ownership, trace invocation, or checker behavior changes.
- `.venv/bin/python -m pytest l0/compiler/stage1_py/tests/cli/test_docgen* -q`: 126 passed, including isolated
  inventories/outputs, failures and stale-bundle invalidation, schema/type checks, unsafe tar members, version/source
  mismatches, historical export compatibility, Pages migration, and all four host archive layouts.
- `.venv/bin/python l0/tests/test_release_tag_policy.py`: passed. Tests execute checksum fragments and mock immutable
  publication rejection and CI routing. Missing documentation or platform assets fail; docs precede distributions;
  generation remains read-only and Windows checkout preserves source bytes.
- From `l0/`, `make docs-artifacts DOC_STAGE=all DEA_DIST_VERSION=dev`: strict HTML/Markdown/LaTeX and complete PDFs
  passed with Doxygen 1.18.0. The final Stage 2 comment correction was verified with the same command selecting
  `DOC_STAGE=stage2`. Stage 1 has 74 selected sources and 719 PDF pages; Stage 2 has 95 sources and 863 PDF pages. XML
  source locations stay within their selected inventories. All generated HTML local links resolve, and neither reference
  needs remote assets. Both PDFs' title, index, and representative symbol pages and Stage 2 HTML were visually
  inspected.
- From `l0/`, `make dist DOCS_ARTIFACT=<absolute-stage2-bundle-path> DEA_DIST_VERSION=dev`: passed on macOS x86_64 with
  TCC 0.9.28rc. The extracted real archive's 325 documentation payload files match the manifest; its relocated compiler
  reports the expected version and runs a standalone Hello World project successfully.
- `stage_docs_pages.py` and `l0_docgen_blog.py --stage stage2` passed against real outputs. The legacy PDF alias is
  byte-identical, retired Stage 1 URLs show the migration notice, and the 96-file Markdown export contains no Stage 1
  compiler pages.
- ADR Impact checks, staged whitespace, and root pre-commit checks passed. The amended indexed L0 ADRs and existing
  publication-ownership ADR link back to this closed plan; the related L1 plan points to its new location.

Native Linux, macOS arm64, and Windows hosted execution was not performed locally. Their archive layouts were tested
with host fixtures; the workflows retain native extraction/compiler smoke checks. No push, tag, workflow dispatch,
release edit, deployment, downstream message, or external repository write was performed. Local implementation and
artifact verification complete this plan; hosted publication remains subject to the separate repository authorization
boundary.

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

[distribution-adr]: ../../../../docs/decisions/0023-toolchain-installation-and-distribution-layout.md
[l1-docs]: ../../../../../l1/work/plans/tools/2026-10-05-l1-stage-separated-autodocs-noref.md
[publication-adr]: ../../../../../docs/decisions/0017-documentation-publication-ownership-and-cross-repository-boundary.md
[release-adr]: ../../../../docs/decisions/0017-release-identity-integrity-and-immutable-publication.md
