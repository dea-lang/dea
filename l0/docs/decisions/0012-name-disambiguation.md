# ADR-0012: Name Disambiguation via Qualified References

- Decision date: 2026-01-31
- Last edited: 2026-05-20
- Status: Accepted

## Context

L0 supports open imports (`import module`) that bring module members into the current scope. When two imported modules
export names that conflict, or when a local binding shadows an import, there needs to be an explicit escape hatch.

## Decision

Qualified names (`module.path::Name`) are the disambiguation mechanism:

- Any name accessible through an import can always be referenced with its full qualified path.
- When an unqualified name is ambiguous (multiple imports expose the same name), using the qualified form resolves the
  ambiguity.
- The current-module qualifier is also accepted to force resolution to the current module's own definitions.

## Rationale

- Open imports stay ergonomic for simple programs: no forced qualification of every name.
- The qualified form provides an explicit, unambiguous escape hatch when needed.
- Introducing aliases or namespace renaming would add complexity before it is clearly needed; the qualified-reference
  approach is the minimal solution.

## Consequences

- The compiler warns (`RES-0021`) when an unqualified name is shadowed by a local binding or import.
- Future disambiguation mechanisms (aliases, renaming imports) would be additive; this decision does not prevent them.

## Related Plans

None (pre-plan era). Implemented as part of the initial module system.

## Current Docs

- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §6 (name disambiguation via qualified
  references)
