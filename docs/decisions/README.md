# Dea-Wide Design Decision Records

This directory holds ADR-style records for architectural decisions that span both language levels or belong to the Dea
project as a whole.

ADRs complement the level-local `reference/design-decisions.md` files (stable aggregates of what is currently true) and
the closed plans in `work/plans/` (execution history). They do not replace either.

## Lifecycle

Valid `Status` values: `Accepted`, `Deprecated`, `Superseded by [ADR-NNNN](NNNN-slug.md) (YYYY-MM-DD)`.

ADR numbers are never reused. Superseded entries remain in place with their original number retired; the superseding ADR
takes the next available number.

Plans and initiatives declare ADR work through the `## ADR Impact` contract in `CLAUDE.md`. A `New ADR`, `Amend ADR`, or
`Covered by ADR` disposition is completed in the same change that closes its source document. The ADR's `Related Plans`
section must contain a resolvable link to every newly closed source document, and `INDEX.md` must contain every ADR in
this directory.

## Template

```markdown
# ADR-NNNN: Title

- Decision date: YYYY-MM-DD
- Last edited: YYYY-MM-DD
- Status: Accepted

## Context

## Decision

## Rationale

## Consequences

## Related Plans

## Current Docs
```

See [INDEX.md](INDEX.md) for the current list.
