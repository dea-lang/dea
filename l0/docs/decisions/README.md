# L0 Design Decision Records

This directory holds ADR-style records that link L0 design decisions to the closed plans that shaped them and the
current docs where they are normatively recorded.

ADRs complement [l0/docs/reference/design-decisions.md](../reference/design-decisions.md) (stable aggregate) and closed
plans in `l0/work/plans/*/closed/` (execution history). They do not replace either.

## Lifecycle

Valid `Status` values: `Accepted`, `Deprecated`, `Superseded by [ADR-NNNN](NNNN-slug.md) (YYYY-MM-DD)`.

ADR numbers are never reused. Superseded entries remain in place with their original number retired; the superseding ADR
takes the next available number.

Plans declare ADR work through the `## ADR Impact` contract in root `CLAUDE.md`. A `New ADR`, `Amend ADR`, or
`Covered by ADR` disposition is completed in the same change that closes its source plan. The ADR's `Related Plans`
section must contain a resolvable link to every newly closed source plan, and `INDEX.md` must contain every ADR in this
directory.

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
