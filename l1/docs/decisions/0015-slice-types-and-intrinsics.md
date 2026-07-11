# ADR-0015: Slice Types and `len`/`slice` Intrinsics

- Decision date: 2026-06-16
- Last edited: 2026-07-11
- Status: Accepted

## Context

L1 had owning fixed-size value arrays `T[N]` (see [ADR-0011][adr-arrays]) but no variable-length contiguous view. APIs
needing variable-length spans had to fall back to library containers or raw pointers. L1 also has no borrow checker or
lifetime inference, so a general escape-capable reference type was out of reach. The question was how to introduce a
first slice surface that is useful for parameters and local spans without committing to ownership or lifetime analysis.

## Decision

Slices are first-class non-owning views spelled `T[]`, layered on top of fixed arrays:

- A slice uses the explicitly selected single-letter LBI component `W<elem>` and lowers to a descriptor
  `typedef struct __deaW<elem> { dea_int len; T *data; }`, copied by value with no retain, release, cleanup, or
  ownership transfer; the underlying fixed array remains the sole owner of the storage.
- The initial surface supports `T[]`, `T*[]`, and `T?[]`. `T[]?` and `T[]*` are rejected so the non-owning escape
  restrictions are not weakened. The inferred-length form `T[_]` is reserved and rejected by the parser, never `T[]`.
- Because there is no lifetime analysis, slices are accepted only as local variables, parameters, and call arguments.
  They are rejected as function return types, returned expressions, struct fields, top-level `let` bindings, and enum
  (heap) payload fields.
- A fixed array `T[N]` converts to `T[]` only in known slice target contexts: function arguments, annotated local
  initialization, and assignment to an existing slice variable. There is no unconstrained C-style array decay.
- Two compiler-owned `dea` prelude intrinsics are added (see [ADR-0002][adr-prelude]): `len(x)` returns the `int` length
  of a fixed array or slice, and `slice(x)`, `slice(x, start)`, `slice(x, start, count)` build a `T[]` over a fixed
  array or slice. The third argument is `count`, not an end index. Index, `start`, and `count` operands must be `int`.
- Slice indexing and slice-range construction are bounds-checked with `_rt_panic_oob` before any pointer arithmetic or
  dereference; a zero-length result uses `len = 0` and `data = NULL`.

## Rationale

- A non-owning, escape-restricted descriptor is the smallest slice surface that is useful for parameters and spans
  without requiring borrow or lifetime analysis that L1 does not yet have.
- Conservatively rejecting returns and long-lived storage keeps the "underlying array owns the storage" invariant
  explicit, so slice descriptor copies stay plain value copies. If the compiler materializes a fixed-array rvalue to
  back a slice, that temporary still follows normal array cleanup rules.
- Restricting `T[N] -> T[]` to known target contexts keeps ownership explicit and avoids C-style array decay.
- The `W` slice component follows the LBI single-letter rule and denotes a non-owning window over contiguous storage. It
  remains distinct from the `S` nominal struct leaf.
- Reusing the `dea` prelude for `len`/`slice` keeps intrinsics in the normal symbol/module system with the same
  shadowing behavior as `sizeof`, `ord`, and `is`.

## Consequences

- Slice descriptor copies do not retain or release elements. When a slice is backed by a compiler-materialized
  fixed-array rvalue, that backing array remains scope-owned and is cleaned up when it transitively contains ARC-managed
  data.
- The escape restrictions are enforced at signature-resolution time (return types, struct fields, top-level lets, enum
  payloads), so a function can never declare a slice return type.
- Dynamic buffers, shared buffers, address-of (`&`), broader pointer arithmetic, and slice-of-slice ergonomics remain
  future work. L1-defined variadic functions now use a slice-typed callee parameter and caller-owned packs as recorded
  by [ADR-0017][adr-variadics]; C variadic FFI remains separate.

## Related Plans

- [l1/work/plans/features/closed/2026-05-19-stage1-slices-len-slice-intrinsics-noref.md][slices]
- [l1/work/plans/features/closed/2026-05-10-fixed-size-array-primitive-noref.md][arrays-plan]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §7.2 (slice policy) and §10 (`dea` prelude)
- [l1/docs/reference/grammar.md][grammar]: slice suffix and `len`/`slice` notes
- [l1/docs/reference/ownership.md][ownership]: non-owning slice semantics
- [l1/docs/reference/c-backend-design.md][backend]: slice descriptor lowering and checked access
- [l1/docs/specs/compiler/abi.md][abi]: `W` slice type-component encoding and ABI decision rule

[abi]: ../specs/compiler/abi.md
[adr-arrays]: 0011-fixed-size-array-policy.md
[adr-prelude]: 0002-dea-virtual-prelude-module.md
[adr-variadics]: 0017-l1-variadic-functions.md
[arrays-plan]: ../../work/plans/features/closed/2026-05-10-fixed-size-array-primitive-noref.md
[backend]: ../reference/c-backend-design.md
[design-decisions]: ../reference/design-decisions.md
[grammar]: ../reference/grammar.md
[ownership]: ../reference/ownership.md
[slices]: ../../work/plans/features/closed/2026-05-19-stage1-slices-len-slice-intrinsics-noref.md
