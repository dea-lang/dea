# ADR-0007: Function Pointer Types

- Decision date: 2026-04-18
- Last edited: 2026-07-05
- Status: Accepted

## Context

L1 programs need to store, pass, and call functions as first-class values, for callbacks, dispatch tables, and
higher-order patterns. The question was how to spell function pointer types and what their semantics should be.

## Decision

Function pointer types are spelled `func(T1, T2) -> U` and `unsafe func(T1, T2) -> U`:

- Bare references to top-level functions have the function pointer type matching their signature; they can be stored,
  passed, returned, and called indirectly.
- Generated C represents each distinct signature with a `dea_func_*` typedef over a plain C function pointer.
- Two function pointer types are compatible only when parameter arity, parameter types, result type, and the `unsafe`
  marker all match exactly.
- Nullable function pointers use the `T?` model: `(func(...) -> U)?`. The parentheses are needed because
  `func(...) -> U?` means a non-null function returning nullable `U`.
- Lambdas, closures, method pointers, and C variadic function pointers are explicitly out of scope for the current
  bootstrap.

The `unsafe` marker is a function-level contract marker, not a call-site gate; safe code may still call an `unsafe func`
value today. The marker exists to distinguish source-unsafe raw-memory contracts in signatures.

## Rationale

- Spelling the type as `func(...)` rather than a C-style pointer syntax keeps the L1 type system consistent: function
  types are just types, not a special pointer category.
- The strict compatibility rule (arity + types + unsafe marker) prevents silent ABI mismatches when calling through
  function pointer values.
- Nullable function pointers via the standard `(T)?` pattern reuse the existing nullable machinery rather than inventing
  a new null-function-pointer primitive.

## Consequences

- Each distinct function pointer signature generates one `dea_func_*` typedef; programs that use many distinct
  signatures produce more typedefs but no runtime overhead.
- The `unsafe` marker on a function pointer type signals to the reader (and future tooling) that the function operates
  under an unchecked memory contract.

## Related Plans

- [l1/work/plans/features/closed/2026-04-18-l1-function-pointer-types-noref.md][fp-types]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §8 (function pointer types)

[design-decisions]: ../reference/design-decisions.md
[fp-types]: ../../work/plans/features/closed/2026-04-18-l1-function-pointer-types-noref.md
