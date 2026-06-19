# ADR-0017: L1 Variadic Functions

- Decision date: 2026-06-19
- Last edited: 2026-06-19
- Status: Accepted

## Context

L1 function declarations, calls, and function pointer types originally required fixed arity. The earlier variadic plan
was deferred until slices existed so the language would not ship a one-off pack representation or C varargs dependency.
With non-owning `T[]` descriptors implemented, L1 can define variadics as language sugar over the existing slice ABI.

## Decision

- A single trailing variadic parameter is spelled `name: T...`; function pointer types use `func(Prefix, T...) -> U`.
- Inside the callee the parameter has effective type `T[]` and uses ordinary slice operations.
- Calls supply the fixed prefix plus zero or more positional `T` arguments. Named variadic calls are rejected.
- Ordinary trailing arguments are copied into a caller-owned fixed-array pack whose slice descriptor is passed to the
  callee. A zero-element pack uses `{ len = 0, data = NULL }`.
- A final `pack...` forwards one compatible slice or contextually converted fixed array as the complete variadic tail.
- Variadic and fixed-slice function types remain distinct in semantic and LBI identity. The LBI uses `V<T>` for the
  variadic final parameter, while both forms use the same slice-descriptor C parameter ABI.
- Variadic `extern func` declarations remain rejected; this decision does not define C variadic FFI.

## Rationale

- Reusing slices gives the callee count, checked indexing, mutation, and a bootstrap-safe ABI without new runtime data
  structures.
- Owning the ordinary argument pack in the caller preserves ARC balance for copied aggregate and string values.
- Explicit spread syntax distinguishes forwarding from passing one element and avoids ambiguity when element types are
  themselves aggregate types.
- Distinct function-type identity prevents fixed-slice functions from silently acquiring variadic call behavior.

## Consequences

- Mutating an ordinary variadic pack changes only its caller-created copies. Mutating a spread-forwarded pack follows
  normal slice aliasing and can change the supplied backing storage.
- Direct and indirect variadic calls share one lowering path and one C ABI shape.
- Individual variadic values cannot be combined with a spread pack in the same call.
- C variadic calling conventions, promotions, and `va_list` remain owned by the C FFI initiative.

## Related Plans

- [l1/work/plans/features/closed/2026-04-22-variadic-functions-noref.md][variadic-plan]
- [l1/work/plans/features/closed/2026-05-19-stage1-slices-len-slice-intrinsics-noref.md][slices-plan]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §8.1 (L1 variadic functions)
- [l1/docs/reference/grammar.md][grammar]: variadic parameter and spread-call syntax
- [l1/docs/reference/ownership.md][ownership]: pack ownership and spread aliasing
- [l1/docs/reference/c-backend-design.md][backend]: slice ABI and pack lowering
- [l1/docs/specs/compiler/abi.md][abi]: `V` type-component encoding

[abi]: ../specs/compiler/abi.md
[backend]: ../reference/c-backend-design.md
[design-decisions]: ../reference/design-decisions.md
[grammar]: ../reference/grammar.md
[ownership]: ../reference/ownership.md
[slices-plan]: ../../work/plans/features/closed/2026-05-19-stage1-slices-len-slice-intrinsics-noref.md
[variadic-plan]: ../../work/plans/features/closed/2026-04-22-variadic-functions-noref.md
