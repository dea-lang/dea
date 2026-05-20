# ADR-0005: Shared Diagnostic Code Catalog

- Decision date: 2026-04-03
- Last edited: 2026-05-20
- Status: Accepted

## Context

As both L0 Stage 2 and the L1 compiler were ported from L0 Stage 1, diagnostic codes were at risk of drifting: Stage 2
might emit a different code for the same condition, L1 might invent new codes that conflict with existing L0 ones, and
the meaning of codes would be undocumented and hard to audit.

## Decision

A single normative diagnostic-code registry is maintained in `docs/specs/compiler/diagnostic-code-catalog.md`. Every
code that any compiler stage or level produces must be registered there with a stable meaning.

Rules:

- Stage 2 conditions that have a Stage 1 equivalent must reuse the Stage 1 code exactly, including `ICE-xxxx` codes.
- New codes are allowed only for Stage 2-only conditions with no Stage 1 equivalent.
- When a new diagnostic area is needed, one block of 20 unused codes is provisionally reserved per family; when only a
  few new codes are needed in an established area, nearby unused codes are preferred.
- Code reservations in plans are provisional; the live catalog is re-checked at implementation time.

## Rationale

- Stable codes allow users and tooling to pattern-match on specific diagnostics reliably.
- A shared catalog prevents accidental reuse of the same numeric code for different meanings across stages or levels.
- Treating Stage 1 as the oracle eliminates the ambiguity of which stage defines the "correct" behavior.

## Consequences

- Every new diagnostic must be verified as unused before being assigned (search `rg 'XXX-NNNN'` in all compiler source
  trees and docs).
- Plans that introduce diagnostics must carry explicit code-planning sections.
- L1 inherits the L0 code assignment for any condition that is semantically equivalent; it cannot reuse a code with a
  different meaning.

## Related Plans

- [work/plans/features/closed/2026-04-03-shared-diagnostic-code-catalog-noref.md](../plans/features/closed/2026-04-03-shared-diagnostic-code-catalog-noref.md):
  introduced the catalog
- [work/plans/features/closed/2026-04-03-diagnostic-code-catalog-meanings-noref.md](../plans/features/closed/2026-04-03-diagnostic-code-catalog-meanings-noref.md):
  expanded with semantic meanings

## Current Docs

- [docs/specs/compiler/diagnostic-code-catalog.md](../specs/compiler/diagnostic-code-catalog.md): normative code
  registry
- [l0/docs/specs/compiler/diagnostic-code-policy.md](../../l0/docs/specs/compiler/diagnostic-code-policy.md): L0-level
  assignment rules
