# ADR-0029: Lifted Implicit Nullable Numeric Widening

- Decision date: 2026-11-25
- Last edited: 2026-11-25
- Status: Accepted

## Context

L0 Stage 1 accepts a `byte?` where an `int?` is expected but can emit invalid C. L0 Stage 2, L1 and L2 reject the same
source during checking. L1 and L2 also have wider integer and floating types and distinguish multiple nullable layers. A
level-local list of optional conversion pairs would leave the same source-level question open for each additional type
or level.

## Decision

Lift each level's existing type-based implicit numeric widenings through matching nullable layers. Evaluate the source
once, preserve absence at each existing layer, and widen the numeric payload only when present. If the destination has
more layers, apply ordinary nullable injection around the converted value until the destination depth is reached. Every
added layer is present. This order also preserves existing `T` to `T?` injection when `T` is nullable.

The rule governs implicit assignment contexts and their corresponding explicit casts across Dea levels. General
assignment compatibility is too broad to serve as the payload predicate. Contextual literal conversions, casts that
require narrowing, and conversions of pointer or aggregate types cannot establish a numeric widening.

## Rationale

An existing safe numeric widening preserves every payload value. Preserving the nullable tags extends that guarantee to
absence. Applying injection last gives a unique result even for an absent source. Converting an absent `byte?` to
`int??` produces a present outer value holding an absent `int?`. Code can observe that distinction.

## Consequences

Each compiler must implement the same value semantics using its own destination representations. Reordering a checker
branch alone cannot make generated code correct. An implicit conversion may never remove a nullable layer. Numeric
operators, nullable equality, and the range of other explicit casts continue to follow each level's existing rules. The
linked implementation plan tracks conformance separately from acceptance of this decision.

## Related Plans

- [work/plans/features/2026-11-25-shared-nullable-numeric-widening-noref.md][implementation] owns compiler conformance.
- [l0/work/plans/bug-fixes/2026-11-21-stage1-nullable-conversions-and-ownership-noref.md][l0-plan] identified the
  original stage discrepancy.
- [l1/work/plans/features/closed/2026-05-11-ordered-type-suffix-constructors-noref.md][suffixes] established the
  significance of successive type constructors.

## Current Docs

- [docs/specs/language/nullable-numeric-widening.md][spec]
- [l0/docs/decisions/0007-nullability-and-casts.md][l0-nullability]

[implementation]: ../../work/plans/features/2026-11-25-shared-nullable-numeric-widening-noref.md
[l0-nullability]: ../../l0/docs/decisions/0007-nullability-and-casts.md
[l0-plan]: ../../l0/work/plans/bug-fixes/2026-11-21-stage1-nullable-conversions-and-ownership-noref.md
[spec]: ../specs/language/nullable-numeric-widening.md
[suffixes]: ../../l1/work/plans/features/closed/2026-05-11-ordered-type-suffix-constructors-noref.md
