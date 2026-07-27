# ADR-0025: L1 Pointer Equality and Ordering Semantics

- Decision date: 2026-04-19
- Last edited: 2026-07-27
- Status: Accepted

## Context

L1 pointer values need a useful equality operation without inheriting every comparison permitted by host C. Before this
decision, the grammar admitted equality expressions but the type checker rejected two `T*` operands even when they had
the same type.

Reference identity is meaningful for heap pointers. Implicitly converting unrelated pointer types through `void*`,
however, would weaken nominal type checking, and ordering raw addresses would expose host-specific behavior with no
stable L1 interpretation.

## Decision

`==` and `!=` are defined on two operands of the same non-nullable pointer type `T*`, including `void*`. They return
`bool` and compare reference identity: equality means that both values refer to the same runtime object.

Different pointer types are not implicitly made comparable. Pairs such as `int*` and `long*`, unrelated object-pointer
types, or a non-`void` pointer and `void*` are rejected unless the program first applies an explicit cast that produces
the same static type.

Pointer comparisons with `null` retain the existing null-check rules. The relational operators `<`, `<=`, `>`, and `>=`
are rejected for pointer operands because L1 does not define address ordering.

The C backend lowers accepted pointer equality directly to C `==` or `!=`; it adds no runtime helper, representation
widening, or string-equality behavior.

## Rationale

Identity equality provides the pointer operation programs need while remaining compatible with the underlying C
representation. Requiring the same static pointer type keeps heterogeneous comparisons explicit. Rejecting address
ordering prevents allocator layout and host-C assumptions from becoming language semantics.

The rejected alternatives were coercing every pointer through `void*`, defining relational order over host addresses,
and rejecting all pointer comparison.

## Consequences

- Pointer equality remains nominally type-strict.
- Heterogeneous identity checks require an explicit cast chosen by the programmer.
- Pointer values cannot be sorted or range-compared by address as an L1 language operation.
- String equality remains content equality and does not inherit this identity rule.
- General nullable equality remains governed by the nullable-value contract rather than changing this `T*` rule.

## Related Plans

- [l1/work/plans/features/closed/2026-04-19-pointer-identity-equality-noref.md][pointer-identity]
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md][publication-plan]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: pointer identity, nullability, and comparison restrictions

[design-decisions]: ../reference/design-decisions.md
[pointer-identity]: ../../work/plans/features/closed/2026-04-19-pointer-identity-equality-noref.md
[publication-plan]: ../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md
