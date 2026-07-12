# Documentation Layout

This directory is organized by document intent first, then subsystem.

## Folders

- `project-status.md`: current implementation status, known limitations, and near-term direction.
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

Generated API documentation is not stored in this tree. The docs pipeline writes generated HTML, Markdown, Doxygen XML,
and Doxygen LaTeX under `build/docs/`. When `python scripts/gen_docs.py --pdf` is used, the built PDF is copied to
`build/docs/pdf/` (also with `--pdf-fast`). After each successful docs run, generated artifacts are mirrored into a
stable preview tree under `build/preview/{html,markdown,pdf}` and overwritten by the next successful run. CI publishing
also produces a Chirpy-compatible markdown export of the Dea/L0 API reference under `build/docs/api-reference/`,
packaged as a release asset (`dea_l0_api_reference-<TAG>.tar.gz`) for consumption by external blog repositories.

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

- [project-status.md](project-status.md): current implementation status, known limitations, and near-term direction.
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
