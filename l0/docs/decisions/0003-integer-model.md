# ADR-0003: Integer Model

- Decision date: 2025-12-06
- Last edited: 2026-05-20
- Status: Accepted

## Context

L0 compiles to C, and C's integer model is famously vague: `int` width varies by platform, overflow of signed integers
is undefined behavior, and `size_t` leaks platform-specific bit-width assumptions into code.

A decision was needed: should L0 simply inherit C's integer semantics, or define its own?

## Decision

L0 defines its own integer semantics independent of the host C integer model:

- `int` is exactly 32-bit signed two's complement.
- `byte` is 8-bit unsigned.
- The C backend emits `int32_t` and `uint8_t` (from `<stdint.h>`) and never bare `int`/`long` with semantic
  significance.
- Integer arithmetic that could produce undefined behavior in C (division by zero, signed overflow, out-of-range shifts)
  goes through checked runtime helpers (`rt_div`, `rt_mod`, shift guards) in the C kernel.
- `size_t` is a kernel implementation detail and does not appear at the L0 language boundary.

At the stdlib layer, integer helper contracts belong in `std.integer` (formerly `std.math`). The `std.integer` surface
remains integer-focused.

## Rationale

- A bootstrap compiler must not produce programs whose behavior depends on the host C implementation's integer model;
  that would make L0 semantics unportable.
- Quarantining the checked arithmetic in the C kernel means the L0 runtime and compiler code stays UB-free even when
  compiled with a C compiler that exploits signed-overflow UB.
- `size_t` isolation avoids leaking pointer-width assumptions into L0 code that is supposed to be portable across
  LP64/LLP64/ILP32 hosts.

## Consequences

- All L0 programs that use integer arithmetic are portable by construction: the semantics are defined in terms of L0
  types, not C types.
- The `std.integer` module (previously `std.math`) is the normative home for integer utilities.

## Related Plans

- [work/plans/features/closed/2026-04-14-shared-std-math-int-surface-noref.md](../../../work/plans/features/closed/2026-04-14-shared-std-math-int-surface-noref.md):
  expanded shared `int` helper surface
- [work/plans/refactors/closed/2026-05-13-shared-std-math-to-std-integer-rename-noref.md](../../../work/plans/refactors/closed/2026-05-13-shared-std-math-to-std-integer-rename-noref.md):
  renamed `std.math` to `std.integer`

## Current Docs

- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §7 (integer model rationale)
- [l0/docs/reference/c-backend-design.md](../reference/c-backend-design.md): typedef mapping, C99 int layer
- [l0/docs/reference/standard-library.md](../reference/standard-library.md): `std.integer` surface
