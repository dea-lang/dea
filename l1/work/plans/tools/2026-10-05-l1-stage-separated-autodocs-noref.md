# Tool Plan

## Generate separate L1 Stage 1 and Stage 2 autodocs

- Date: 2026-10-05
- Status: Draft
- Title: Generate separate L1 Stage 1 and Stage 2 autodocs
- Kind: Tooling
- Severity: Medium
- Stage: L1
- Subsystem: Doxygen / HTML and PDF generation / distribution documentation
- Targets:
  - Stage 1 developer HTML/PDF reference: Pending
  - Stage 2 HTML/PDF reference and distribution artifact: Pending
- Modules:
  - `l1/scripts/gen_docs.py` (new)
  - `l1/compiler/docgen/` (new L1 filters and generation adapters)
  - `l1/scripts/docs/templates/` (new)
  - `l1/Makefile`
  - `l1/docs/README.md`
  - `l1/docs/project-status.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/tests/test_docgen_source_scope.py` (new)
  - `l1/tests/test_docgen_filters.py` (new)
  - `l1/tests/test_docgen_outputs.py` (new)
  - `l1/tests/test_docgen_artifacts.py` (new)
- Related:
  - [l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][productization]
  - [work/plans/tools/2026-05-12-l1-gha-release-snapshot-workflows-noref.md][release-workflows]
  - [l0/work/plans/tools/2026-10-05-l0-stage-separated-autodocs-noref.md][l0-split]
  - [docs/decisions/0017-documentation-publication-ownership-and-cross-repository-boundary.md][publication-adr]

## Summary

Add L1 source-derived documentation using L0's Doxygen XML, m.css HTML, Markdown, and Doxygen LaTeX/PDF approach.
Generate Stage 1 and Stage 2 as independent documents. Ship only Stage 2 autodocs with the self-hosted Stage 2
distribution. This plan defines the artifact contract; productization consumes it and the root release-workflow plan
owns hosted builds and release attachment. Generation can be implemented before install/dist and does not require a
release tag.

## Current State

Reviewed on 2026-10-05:

- L1 has hand-authored reference documentation and both compiler source trees, but no `scripts/gen_docs.py`, docgen
  package, or HTML/PDF artifact pipeline.
- L0's `scripts/gen_docs.py`, `compiler/docgen/`, and `scripts/docs/templates/` produce one combined source manifest,
  XML/HTML/Markdown/LaTeX tree, and `dea_l0_api_reference.pdf`. Stage sections in that output do not separate documents.
- L1 Stage 1 is written in L0; Stage 2 and the bundled stdlib are written in L1. L0's Python filter cannot document L1
  Stage 1, and its L0 filter cannot be assumed to cover every L1 construct.
- L1's Stage 2 native build uses shared C support currently located under `compiler/stage1_l0/support/`. Physical
  directory ownership alone is insufficient to classify shared support for documentation.
- L1 install/dist and release workflows are unimplemented. The workflow plan's readiness-policy phase is complete;
  workflow implementation awaits productization and Stage 2 documentation generation.

## Source and Document Boundaries

Select the stage before building a source manifest or running Doxygen. `--stage all` runs two independent pipelines;
never generate a combined XML database and hide the other stage only in rendering.

| Document | Compiler sources                 | Shared material included in this document                          |
| -------- | -------------------------------- | ------------------------------------------------------------------ |
| Stage 1  | `compiler/stage1_l0/src/**/*.l0` | Bundled L1 stdlib, runtime API, and native support used by Stage 1 |
| Stage 2  | `compiler/stage2_l1/src/**/*.l1` | Bundled L1 stdlib, runtime API, and native support used by Stage 2 |

Build explicit shared-input allowlists from the actual build contracts. Include Stage 2's `compiler_support.c`,
`preparation_support.c`, and required support headers as shared implementation support even though their paths contain
`stage1_l0`; exclude the Stage 1 compiler and Stage 1-only fingerprint bridge from the Stage 2 document. Label shared
chapters accordingly. Repeat required shared reference material in each output so either document works independently.
Exclude tests, fixtures, build trees, generated compiler C, and lifecycle documents.

HTML navigation, search indexes, XML, Markdown, LaTeX, PDF contents/indexes, and undocumented-function reports are all
stage-specific. Titles identify `Dea/L1 Stage 1` or `Dea/L1 Stage 2`. Resolve duplicate module/symbol names only within
the selected stage plus its shared inputs. The Stage 2 package must have no link or asset dependency on Stage 1 output.
References to the other implementation may remain prose or explicit optional repository links, never required offline
links to an absent sibling document.

## Generation Interface

From `l1/`, add:

- `python scripts/gen_docs.py --stage stage1 --strict --pdf`
- `python scripts/gen_docs.py --stage stage2 --strict --pdf`
- `python scripts/gen_docs.py --stage all --strict --pdf` (two separate documents)
- `make docs DOC_STAGE=all` and `make docs-pdf DOC_STAGE=all`; an omitted `DOC_STAGE` means `all`.
- `make docs-artifacts DOC_STAGE=stage2 DEA_DIST_VERSION=<version>` for the complete distribution handoff.

The wrapper accepts `--stage {stage1,stage2,all}`, defaulting to `all`, and `--output-dir` as the parent of stage
subdirectories. Preserve L0-style strict warnings and synthetic-symbol checks; add L1 fixtures for wide integers,
function pointers, slices, unsafe declarations, and interfaces so unsupported syntax cannot silently disappear.
`--pdf-fast` may be retained for previews but cannot produce a distributable artifact. A normal HTML-only build needs no
TeX; `docs-artifacts` requires a complete PDF and fails when its tools are unavailable.

Reuse Doxygen, Graphviz, the shared Python dependency group, and vendored m.css. Start with narrow L1-owned adapters to
L0's approach; do not import a module that silently binds generation to the L0 root or labels. Shared helper extraction,
if needed, must preserve L0 behavior and include its relevant regression tests. The separate L0 split is not a
dependency.

## HTML/PDF Artifact Contract

For `S=1` or `S=2`, define:

| Output                             | Path relative to `l1/`                                               |
| ---------------------------------- | -------------------------------------------------------------------- |
| Offline HTML entrypoint and assets | `build/docs/stageS/html/index.html` and its tree                     |
| Generated Markdown                 | `build/docs/stageS/markdown/`                                        |
| Doxygen XML / LaTeX intermediates  | `build/docs/stageS/doxygen/xml/`, `build/docs/stageS/doxygen/latex/` |
| Complete PDF                       | `build/docs/stageS/pdf/dea_l1_stageS_api_reference.pdf`              |
| Warning/coverage reports           | `build/docs/stageS/undocumented-functions.txt` and stage-local logs  |
| Preview                            | `build/preview/stageS/{html,markdown,pdf}/`                          |
| Consumer bundle                    | `build/docs/artifacts/dea_l1_stageS_autodocs.tar.gz`                 |

Each bundle has one `dea-l1-stageS-autodocs/` root containing `html/`, `pdf/dea_l1_stageS_api_reference.pdf`, and
`manifest.json`. Exclude XML, LaTeX scratch, logs, and generated Markdown from this distribution bundle. HTML must work
from a local filesystem without a web server or remote asset fetch. Bundled PDF links use the relative `../pdf/` path.

The manifest has schema version 1, level `l1`, numeric stage, package version, source revision and dirty-state evidence,
a digest of the selected source-input inventory, Doxygen/renderer/TeX tool versions, full-PDF and strict-validation
success flags, and a complete relative file inventory with content digests. The manifest excludes its own digest. Reject
malformed paths, duplicate entries, escaping links, mismatched level/stage/version/source, and partial output. Use
`DEA_DIST_VERSION` for package version, defaulting to `dev` locally. Optional `L1_DOCS_RELEASE_TAG` labels hosted
output; it must agree with the selected package version. Source identifiers are generated artifact provenance, not
literal identifiers recorded in this plan.

Create the manifest and archive only after strict HTML and full PDF verification succeeds. A failed invocation cannot
leave an old bundle represented as its new result. Use separate staging directories for both stages and replace only the
selected stage's outputs after success. Building Stage 1 must not remove or overwrite Stage 2 output, or vice versa.

## Packaging and Release Handoff

- Productization adds `DOCS_ARTIFACT=<absolute-stage2-bundle-path>` to `make dist` and copies verified HTML, PDF, and
  the docs manifest under `share/doc/dea/l1/autodocs/stage2/` in every platform archive. All copied files also enter the
  install inventory. A complete dist requires Stage 2 docs; missing or invalid docs fail with the generation command.
- `make install` may omit autodocs for a compiler-only prefix, or consume the same explicit Stage 2 bundle. It never
  invokes Doxygen/TeX implicitly. Ordinary installed compiler operation never requires documentation build tools.
- Doc generation needs source files and documentation tools, not an installed compiler. This avoids a dependency cycle.
  Packaging validates version, source revision, and the source-input inventory against its checkout, including dirty
  local builds. Documentation and binaries must describe the same source state.
- The root workflow plan builds complete Stage 2 docs once on Linux at the selected immutable source revision, then
  supplies that exact bundle to all four platform builds. It publishes the same bundle and PDF as stage-qualified
  release assets and includes them in asset completeness/checksum checks. Stage 1 docs are generated/validated as
  separate developer outputs and never attached to Stage 2 releases or included in compiler archives.
- Public HTML hosting, blog export, and Pages deployment are outside this L1 plan. Distribution of offline HTML/PDF
  artifacts is sufficient for the initial delivery contract.

## Implementation Phases

1. Add explicit stage source manifests and L0/L1/C filters, with source-scope and language-syntax regression fixtures.
   Inventory shared native support from actual builders instead of broad recursive inclusion.
2. Implement separate XML/HTML/Markdown/LaTeX/PDF runs, titles, cross-reference resolution, and preview paths. Build
   both real source inventories strictly and review representative rendered pages and PDF chapters in each document.
3. Implement the manifest and bundle contract, corruption/stale-output checks, and the documented Make/wrapper surface.
   Exercise Stage 1 then Stage 2, the reverse order, and `all`, proving output independence.
4. Document local tooling requirements and artifact consumption in `l1/docs/README.md`. Update project status and
   roadmap with the implemented scope. Hand off verified Stage 2 artifacts to productization and workflow integration.
   Close this generation plan after local generation/artifact acceptance; remote publication is not its closure gate.

## ADR Impact

- Decision: Generate independent stage-specific L1 references and distribute only Stage 2 autodocs with Stage 2 tooling.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Source ownership, independent documents, artifact identity, and distribution selection are durable L1
    documentation contracts. The existing root publication ADR continues to govern remote effects.

## Non-Goals

- Combining Stage 1 and Stage 2 in one PDF, HTML index, or documentation bundle.
- Shipping Stage 1 documentation in Stage 2 compiler archives or release assets.
- Implementing the L1 installer, compiler, or release workflow within this plan.
- L1 Pages/blog publication, external synchronization, or changes to L0's existing pipeline.
- Generating compiler diagnostics or reserving diagnostic codes; docgen errors are tooling failures.

## Verification Criteria

1. Each stage's source manifest contains its compiler and intentional shared inputs only. Stage 2 cannot resolve a
   symbol through the Stage 1 compiler manifest. Tests cover duplicate names and native-support ownership exceptions.
2. Strict builds produce two independently navigable HTML trees and two complete PDFs with correct stage titles, source
   signatures, shared chapters, and resolved local references. Inspect representative PDF pages, contents, and index;
   source/XML tests alone do not establish rendering correctness.
3. Stage 2 HTML/PDF work after extraction without Stage 1 output, checkout access, or network access for assets.
4. Sequential/all builds cannot contaminate each other's previews, PDF, search data, reports, or success manifests.
   Preview-only PDFs and stale bundles are rejected by artifact verification.
5. Bundle corruption, wrong stage/level/version/source, unsafe members, or missing HTML/PDF cause clear failures before
   packaging. Productization's archive smoke verifies the exact documentation files it embeds on every host.
6. Lightweight docgen tests and real strict Stage 1/2 HTML/PDF builds pass. Record commands, tool versions, and
   outcomes; do not infer publication success from local generation. Create/index the ADR and repair links at closure.

[l0-split]: ../../../../l0/work/plans/tools/2026-10-05-l0-stage-separated-autodocs-noref.md
[productization]: 2026-04-02-l1-bootstrap-productization-noref.md
[publication-adr]: ../../../../docs/decisions/0017-documentation-publication-ownership-and-cross-repository-boundary.md
[release-workflows]: ../../../../work/plans/tools/2026-05-12-l1-gha-release-snapshot-workflows-noref.md
