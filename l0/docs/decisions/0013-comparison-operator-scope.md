# ADR-0013: Comparison Operator Scope

- Decision date: 2026-02-27
- Last edited: 2026-05-20
- Status: Accepted

## Context

The L0 grammar admits `==`, `!=`, `<`, `<=`, `>`, `>=` between any operand types. The question was which type pairings
should be accepted at the type-checker level and which should be rejected as deliberate design choices rather than
deferred features.

## Decision

The type checker enforces the following restrictions:

- **Ordered comparisons on `bool` are rejected**: `bool < bool`, `bool <= bool`, `bool > bool`, `bool >= bool` are
  rejected with `TYP-0170` (noninteger operands). Booleans are labels, not a scalar ordering; a defined `true > false`
  would be a footgun with no legitimate use case.
- **Equality on `bool` is accepted**: `bool == bool` and `bool != bool` return `bool`, consistent with
  `case (b) { true => ...; }` dispatch.
- **String comparisons**: equality and ordered comparisons on `string` are accepted and compare by value (see
  [ADR-0009](0009-string-value-semantics.md)).
- **Pointer ordered comparisons are rejected**: address ordering is not defined.

The guiding principle is that the compiler prefers a compile-time rejection over a defined-but-misleading or surprising
operation.

## Rationale

- `bool < bool` has no meaningful interpretation that wouldn't confuse readers; rejecting it catches accidental
  integer-style comparisons.
- Accepting `bool ==` but not `bool <` matches the intuition that booleans are tags, not ordered values.
- The rejection is an explicit design choice, not a missing feature; it is documented as such so future implementors do
  not "fix" it.

## Consequences

- Code that wants to route on a boolean should use `if`, `case`, or equality (`b == true`, `b != false`, `b`, `!b`).
- The diagnostic code `TYP-0170` is the canonical rejection for noninteger relational operands and applies consistently
  across both stages.

## Related Plans

None. This decision was established as part of the type-checker implementation and documented in `design-decisions.md`;
no standalone plan covers it.

## Current Docs

- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §10 (comparison operator scope)
