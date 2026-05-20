# ADR-0011: Fixed-Size Array Policy

- Decision date: 2026-05-10
- Last edited: 2026-05-20
- Status: Accepted

## Context

L0 deferred array types entirely. L1 needed a concrete array model for systems-level programs. The question was what
kind of arrays to support first: heap-allocated dynamic slices, stack-allocated fixed-size arrays, or something else?

## Decision

Fixed-size arrays are first-class value types spelled `T[N]`, where `N` is a positive `int` literal:

- Suffix order is source-significant across pointer, nullable, and array suffixes: `T*[N]` is an array of pointers;
  `T[N]*` is a pointer to an array.
- Adjacent dimensions preserve C-like source order: `int[2][3]` is two rows of three `int` values.
- Array literals `[a, b]` are contextual: accepted when the target type is a known fixed-size array; reject overlong
  lists; zero-pad omitted trailing elements.
- Array fill constructor: `T[N](value)` fills all elements with `value`.
- Array indexing is **safe**: generated code evaluates base and index once, checks `index < 0 || index >= N`, and calls
  `_rt_panic_oob(index, N)` on failure.
- Raw pointer indexing (`ptr[i]` where `ptr: T*`) remains the unsafe, unchecked operation and requires an `unsafe func`
  body (see [ADR-0010][adr-unsafe]).

## Rationale

- Fixed-size arrays as value types are the simplest starting point: no allocator, no length field, no fat pointer, just
  a block of values with a statically-known layout.
- Bounds-checked indexing by default is consistent with the UB-free language contract; raw pointer indexing is gated on
  `unsafe` because it requires the caller to prove safety manually.
- Source-significant suffix order (`T*[N]` vs `T[N]*`) matches the intuition that suffixes compose left-to-right from
  the base type outward.

## Consequences

- `T[N]` arrays participate in ARC: slot-replacement semantics apply when `T` transitively contains ARC-managed data;
  `ptr[index] = value` follows the same ownership discipline as ordinary assignment.
- Array literals and fill constructors are contextual-only: they require a known destination type and do not have a
  standalone type.

## Related Plans

- [l1/work/plans/features/closed/2026-05-10-fixed-size-array-primitive-noref.md][arrays]
- [l1/work/initiatives/closed/0004-array-primitives-and-unsafe-marker.md][initiative]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §7.1 (fixed-size array policy)

[adr-unsafe]: 0010-unsafe-marker-and-raw-pointer-indexing.md
[arrays]: ../../work/plans/features/closed/2026-05-10-fixed-size-array-primitive-noref.md
[design-decisions]: ../reference/design-decisions.md
[initiative]: ../../initiatives/closed/0004-array-primitives-and-unsafe-marker.md
