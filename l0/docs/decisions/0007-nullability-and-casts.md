# ADR-0007: Nullability and Casts

- Decision date: 2025-12-16
- Last edited: 2026-05-20
- Status: Accepted

## Context

L0 needs a way to express optional/nullable values without introducing a general nullable-anything mechanism that
conflates absence of a value with error conditions or with pointer null.

A related question was how explicit type casts should work in a UB-free language.

## Decision

**Nullability:**

- `T?` encodes nullable/optional values; `null` is the only empty value of a nullable type.
- Non-pointer nullable values use wrapper representations in generated C (`l0_opt_*` structs).
- Nullable pointers use the pointer-null niche (`T*?` → C `T *` where `NULL` represents absence).
- The null-propagation operator `?` propagates null out of the current function early and provides nullable
  short-circuiting with explicit type semantics.

**Casts:**

- Casts are explicit and spelled with `as`.
- Narrowing and wrap/unwrap semantics are explicit; implicit widening applies only for `T → T?` (non-nullable to
  nullable promotion).
- Invalid casts are compile-time errors.
- Runtime checks are used for defined-failure cases (panic), not for UB.

## Rationale

- Making `T?` a first-class type rather than a nullable-pointer convention allows the compiler to enforce null-safety
  statically for non-pointer types.
- The pointer-null niche optimization for `T*?` avoids a wrapper struct for the common case of an optional pointer.
- Explicit casts (`as`) prevent silent narrowing and make conversions visible in code review.

## Consequences

- Stage 1 ARC lowering must correctly handle nullable strings (`string?`) unwrapping, which was a source of early bugs.
- Compile-time diagnostics for provably-invalid casts were added as a feature.

## Related Plans

- [l0/work/plans/bug-fixes/closed/2026-02-25-arc-opt-as-string-unwrap-ownership-noref.md](../../work/plans/bug-fixes/closed/2026-02-25-arc-opt-as-string-unwrap-ownership-noref.md):
  ownership lowering for `string?` unwrap
- [l0/work/plans/features/closed/2026-03-06-explicit-cast-constant-safety-diagnostics-noref.md](../../work/plans/features/closed/2026-03-06-explicit-cast-constant-safety-diagnostics-noref.md):
  compile-time diagnostics for invalid casts

## Current Docs

- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §4 (nullability, casts, and introspection)
