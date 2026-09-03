# ADR-0006: Docs/Work Taxonomy

- Decision date: 2026-04-04
- Last edited: 2026-09-03
- Status: Accepted

## Context

Early in the project, stable documentation (architecture, specs, reference material) and lifecycle artifacts (plans,
proposals, bug-fix tracking) lived in the same directory trees without a principled separation. As the monorepo grew, it
became unclear where new documents should go and whether a given document described the current state or tracked work in
progress.

## Decision

Two sibling trees are maintained at every scope (root, L0, L1):

- **`docs/`**: stable current-state material only (reference, specs, contracts, rationale). Documents here describe how
  the system currently works and do not have a lifecycle (they are not "opened" or "closed").
- **`work/`**: lifecycle artifacts only (plans, proposals, initiatives). Documents here are opened, worked, and
  eventually closed or moved to `closed/` subdirectories.

Placement rules:

- Level-owned stable docs stay in the owning subtree (`l0/docs/`, `l1/docs/`).
- Dea-wide stable docs live in root `docs/`.
- Level-owned lifecycle artifacts stay in the owning subtree (`l0/work/`, `l1/work/`).
- Dea-wide lifecycle artifacts live in root `work/`.

## Rationale

- The separation makes it immediately clear whether a document records current truth (docs/) or tracks a work item
  (work/).
- Stable docs can be linked from code, READMEs, and commit messages without fear that the link will go stale when a plan
  closes.
- Plans are versioned by closing and archiving, not by overwriting stable docs.

## Consequences

- Every new document must be placed under either `docs/` or `work/`, never in a mixed directory.
- AGENTS.md enforces this taxonomy in the "Documentation And Work Tracking" section.
- Level-local plans that are actually shared work should be promoted to the root `work/` tree, not duplicated.

## Related Plans

- [work/plans/refactors/closed/2026-04-04-docs-work-taxonomy-reorg-noref.md](../../work/plans/refactors/closed/2026-04-04-docs-work-taxonomy-reorg-noref.md):
  implemented the separation across root, L0, and L1

## Current Docs

- [docs/README.md](../README.md): root docs placement rules
- [l0/docs/README.md](../../l0/docs/README.md): L0 docs placement rules
- [l1/docs/README.md](../../l1/docs/README.md): L1 docs placement rules
