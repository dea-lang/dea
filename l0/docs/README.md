# Documentation Layout

This directory is organized by document intent first, then subsystem.

## Folders

- `project-status.md`: current implementation status and known limitations.
- `reference/`: stable current-state documentation for language and compiler.
- `user/`: standalone end-user guides used as the source for shipped distribution docs.
- `releases/`: curated stable-release notes used unchanged as GitHub release descriptions.
- `specs/`: normative contracts and behavioral specifications.
- `implementation/`: implementation-oriented specs and design notes.
- `attic/`: superseded or obsolete documents when archival storage is needed.
- `decisions/`: ADR-style records linking design decisions to the closed plans that shaped them and the current docs
  where they are normatively recorded.

Lifecycle artifacts do not live in `docs/`. Use the sibling `../work/` tree for:

- `../work/proposals/`: planned or in-discussion changes and new features.
- `../work/plans/`: execution plans and operational work tracking.

Create subdirectories only when they are needed for real documents. Do not keep empty placeholders or `.gitkeep` entries
in `docs/`; recreate directories on demand.

Generated API documentation is not stored in this tree. `make docs` and `make docs-pdf` generate independent Stage 1 and
Stage 2 references, with `DOC_STAGE=stage1|stage2|all` (default `all`). `--output-dir` selects their common parent. Each
stage has its own source manifest, XML database, search index, Markdown, LaTeX, report, and successful preview. Shared
stdlib and the runtime headers `dea_rt.h`, `dea_siphash.h`, and `l0_runtime.h` appear in both references.

The wrapper and distribution bundle verifier use only the Python standard library. Source inventories and fingerprints
remain independent of rendering imports. Prepare dependencies with `make venv`; the wrapper launches rendering through
the shared virtual environment, where Jinja2 and the other documentation dependencies are installed.

For `S=1` or `S=2`, outputs live under `build/docs/stageS/{html,markdown,doxygen,pdf}/`, with
`pdf/dea_l0_stageS_api_reference.pdf` and `undocumented-functions.txt`. Preview copies live under
`build/preview/stageS/{html,markdown,pdf}/`. A selected-stage build replaces only that stage's successful outputs;
failures retain the previous preview, invalidate its bundle, and save diagnostics under `build/docs/stageS-failure/`.
`--pdf-fast` makes a preview PDF with one TeX pass and cannot create a distribution manifest.

From `l0/`, prepare an offline reference explicitly before packaging:

```bash
make docs-artifacts DOC_STAGE=stage2 DEA_DIST_VERSION=dev
DOCS_ARTIFACT="$PWD/build/docs/artifacts/dea_l0_stage2_autodocs.tar.gz" DEA_DIST_VERSION=dev make dist
```

The tarball has one `dea-l0-stage2-autodocs/` root with HTML/assets, a complete PDF, and `manifest.json`. Its schema
version 1 records level, stage, package version, source revision/tree state, selected-source and generator input digest,
tool versions, strict/full-PDF success, and relative file digests. Distribution consumes an absolute `DOCS_ARTIFACT`
path, rejects unsafe, partial, wrong-stage, stale-source, or wrong-version bundles, and verifies digests after copying.
It embeds the reference under `share/doc/dea/l0/autodocs/stage2/`. Compiler-only `make install` does not invoke TeX.

New release and snapshot sets contain four compiler archives, `dea_l0_stage2_api_reference-<TAG>.pdf`,
`dea_l0_stage2_autodocs-<TAG>.tar.gz`, `dea_l0_stage2_api_reference-<TAG>.tar.gz`, and `SHA256SUMS`. The last tarball is
an opt-in Chirpy Markdown export, distinct from the offline HTML/PDF bundle. Export consumers must select the new
stage-qualified filename; `compiler.docgen.l0_docgen_blog --stage stage2` filters Stage 1 pages even from historical
mixed input. Its default `--stage all` retains historical mixed-input compatibility.

Pages keeps its existing unversioned HTML entrypoint for Stage 2. The old `pdf/dea_l0_api_reference.pdf` URL is a
compatibility copy of the Stage 2 PDF; new links use `pdf/dea_l0_stage2_api_reference.pdf`. Retired Stage 1 URLs show a
migration notice pointing to local generation and developer validation artifacts, with the same notice as the Pages 404
fallback for unrecognized historical URLs. Historical published mixed-reference assets remain immutable and keep their
original names and URLs. Destination repositories own export import and deployment. Local generation and validation do
not authorize publication or downstream messages.

## Placement Guide

- Use `project-status.md` for the current L0 status snapshot.
- Use `reference/` when documenting how the system currently works.
- Use `user/` for standalone end-user docs meant to ship in release archives.
- Use `releases/` for versioned stable-release descriptions and their index.
- Use `specs/` when defining canonical behavior/contracts.
- Use `implementation/` for build strategy details (for example Stage 2 parser internals).
- Move a document to `attic/` only when it is superseded or obsolete.

## Naming Conventions

- Use lowercase kebab-case file names.
- Avoid duplicating type in file names when path already encodes it.
- Keep names concise and domain-focused.

## Document Metadata & Templates

All documentation should follow these metadata standards to ensure consistency and discoverability.

### Reference and Specifications (`reference/`, `specs/`)

Stable or normative documents must include a version line immediately following the main header.

**Template:**

```markdown
# [Title]

Version: YYYY-MM-DD

[Introduction or summary of the document intent.]

## Related Docs

- [Link to related architecture/spec/reference doc]
```

### Work Items (`../work/`)

Plans and proposals follow the metadata and lifecycle rules in [`../work/README.md`](../work/README.md).

## Core Docs

- [project-status.md](project-status.md): current implementation status and known limitations.
- [releases/README.md](releases/README.md): index of curated stable-release descriptions.
- [reference/architecture.md](reference/architecture.md): compiler pipeline and pass structure.
- [reference/c-backend-design.md](reference/c-backend-design.md): Stage 1 lowering/runtime interaction details.
- [reference/standard-library.md](reference/standard-library.md): `std.*` and `sys.*` API surface.
- [reference/ownership.md](reference/ownership.md): canonical ownership rules for `new`/`drop`, ARC strings, and
  container patterns.

### Bug-Fix Plans

Use:

`YYYY-MM-DD-<area>-<slug>-<tracker>.md`

Examples:

- `2026-02-15-arc-retain-cycle-leak-noref.md`
- `2026-03-02-arc-double-release-on-error-path-ref-gh-128.md`

Tracker values:

- `noref` when no tracking system item exists yet.
- `ref-gh-<number>`, `ref-jira-<key>`, or equivalent when available.

## Archived Documents

Use `docs/attic/` only for superseded or obsolete documents.

- Do not use `docs/attic/` as per-change version history; git already provides history.
- Archive only retired docs; routine edits stay in the live tree.
- When `docs/attic/` exists, keep any subdirectories aligned with the live docs tree (`reference/`, `specs/`,
  `implementation/`, `user/`).

Archived file naming pattern:

`<original-name>-archived-YYYY-MM-DD-ref-<replacement-or-none>.md`

Archived document header should include:

- `Status: Archived`
- `Archived on: YYYY-MM-DD`
- `Reason: superseded | obsolete`
- `Replaced by: <path | none>`
- `Scope note: <short context>`
