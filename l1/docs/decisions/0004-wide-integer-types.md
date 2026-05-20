# ADR-0004: Wide Integer Types

- Decision date: 2026-04-04
- Last edited: 2026-05-20
- Status: Accepted

## Context

L0 defines only `int` (32-bit signed) and `byte` (8-bit unsigned). L1 programs (particularly those targeting systems
programming tasks) need additional fixed-width integer types. The question was which types to add and how to extend the
stdlib consistently.

## Decision

L1 implements the following builtin integer types beyond L0's `int` and `byte`:

- `tiny`: 8-bit signed.
- `short`: 16-bit signed.
- `ushort`: 16-bit unsigned.
- `uint`: 32-bit unsigned.
- `long`: 64-bit signed.
- `ulong`: 64-bit unsigned.

All types follow the same UB-free semantic contract as L0's `int`: overflow and narrowing go through checked runtime
helpers; integer division by zero is a defined runtime error.

Integer literals outside the native `int` range are carried as opaque bigint payloads inside the compiler until a
contextual target type is known. Generated C reconstructs equivalent literal spellings with appropriate C suffixes.

At the stdlib layer, L1-only wide-integer helpers use explicit `_ui`, `_l`, and `_ul` suffixes in `std.integer` to avoid
shadowing the shared `int` surface.

## Rationale

- A complete fixed-width integer set is required for systems programming (bit manipulation, protocol parsing, memory
  arithmetic).
- Bigint payload representation avoids implementing arbitrary-precision arithmetic in the bootstrap compiler: range
  checking is textual, and C codegen delegates literal value/base to the downstream C compiler.
- Explicit suffixes in `std.integer` prevent ambiguity between `int` and wider helpers without requiring namespace
  prefixes.

## Consequences

- Compile-time constant folding for non-native numeric types is unavailable in the current bootstrap compiler; code
  generation must preserve literal value and base faithfully.
- `tiny` and `byte` share 8-bit width but differ in signedness; they are not interchangeable.
- The integer type lattice applies to bitwise operators (`&`, `|`, `^`, `<<`, `>>`) with the same common-integer-type
  promotion rules as arithmetic.

## Related Plans

- [l1/work/plans/features/closed/2026-04-04-l1-small-int-builtins-on-dea-abi-noref.md][small-ints]
- [l1/work/plans/features/closed/2026-04-13-l1-uint-long-ulong-bigint-builtins-noref.md][wide-ints]
- [l1/work/plans/features/closed/2026-04-14-l1-std-math-wide-integer-followup-noref.md][wide-stdlib]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §11 (integer and failure semantics), §15 (numeric literal
  representation)

[design-decisions]: ../reference/design-decisions.md
[small-ints]: ../../work/plans/features/closed/2026-04-04-l1-small-int-builtins-on-dea-abi-noref.md
[wide-ints]: ../../work/plans/features/closed/2026-04-13-l1-uint-long-ulong-bigint-builtins-noref.md
[wide-stdlib]: ../../work/plans/features/closed/2026-04-14-l1-std-math-wide-integer-followup-noref.md
