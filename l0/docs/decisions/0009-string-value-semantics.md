# ADR-0009: ARC String Value Contract

- Decision date: 2025-12-29
- Last edited: 2026-05-20
- Status: Accepted

## Context

L0 strings are ARC-managed immutable byte sequences. A key question at the time ARC strings were introduced was how
equality and ordering should work: should two string values compare by identity (same runtime allocation) or by value
(same byte content)?

## Decision

All string comparisons and string-producing operations use **value** semantics, not identity:

- Two strings with the same byte content are equal regardless of which allocations they come from.
- String identity (whether two values refer to the same runtime allocation) is intentionally not exposed through any
  operator, cast, or intrinsic.

The original operator surface for string equality, ordering, and concatenation was stdlib helpers: `std.string::eq_s`,
`cmp_s`, and `concat_s`. These helpers implement value semantics on top of `rt_string_equals`, `rt_string_compare`, and
`rt_string_concat`.

## Rationale

- Identity-based equality would leak backend implementation choices (literal deduplication, static vs. heap, arena
  strategies) into observable language semantics. Value equality keeps the backend free to evolve those strategies.
- Value equality is the only semantic consistent with `case`-over-string dispatch, where two distinct string literals
  with the same content must match the same arm.

## Consequences

- The backend must never emit identity comparisons for string `==`/`!=`.
- `rt_string_concat` is the sole allocation path for string concatenation; it owns the ARC contract for the result.

## Related Plans

None (pre-plan era).

## Current Docs

- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §11 (string equality and ordering)
- [l0/docs/reference/standard-library.md](../reference/standard-library.md): `std.string` module surface
