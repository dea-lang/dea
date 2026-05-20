# ADR-0012: Ordered Type Suffix Constructors

- Decision date: 2026-05-11
- Last edited: 2026-05-20
- Status: Accepted

## Context

With the addition of fixed-size arrays, L1 type expressions can now combine multiple suffix constructors: pointer (`*`),
nullable (`?`), and array (`[N]`). The question was what the precedence and order of these suffixes should be, and
whether the order should be semantically significant.

## Decision

Type suffix constructors are applied left-to-right in source order and each application is semantically distinct:

- `T*`: pointer to `T`.
- `T?`: nullable `T`.
- `T[N]`: fixed-size array of `N` elements of type `T`.
- `T*[N]`: array of `N` pointers to `T` (not a pointer to an array).
- `T[N]*`: pointer to an array of `N` elements of `T`.
- `T*?`: optional pointer to `T` (uses pointer-null niche).
- `T?*`: pointer to an optional `T` (separate from optional pointer).
- Adjacent dimensions: `T[M][N]` is `M` rows of `N` elements.

Nullable function pointers follow the same rule: `(func(...) -> U)?` because `func(...) -> U?` means a non-null function
returning nullable `U`.

## Rationale

- Left-to-right application is the most predictable reading model: each suffix applies to what is on its left.
- Semantic significance of order (rather than normalized forms) prevents silent aliasing between `T*?` and `T?*`, which
  have different generated representations and different ownership semantics.
- Consistency with the existing `T*?` / `T?*` distinction established in L0/L1 nullability (see
  [l0/docs/decisions/0007-nullability-and-casts.md][l0-nullable]).

## Consequences

- The type parser must enforce left-to-right application and reject forms that would be ambiguous.
- Documentation and diagnostic messages describe types in source-order suffix form.

## Related Plans

- [l1/work/plans/features/closed/2026-05-11-ordered-type-suffix-constructors-noref.md][suffix]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §7 (pointer and ownership policy), §7.1 (fixed-size array
  policy)

[design-decisions]: ../reference/design-decisions.md
[l0-nullable]: ../../../l0/docs/decisions/0007-nullability-and-casts.md
[suffix]: ../../work/plans/features/closed/2026-05-11-ordered-type-suffix-constructors-noref.md
