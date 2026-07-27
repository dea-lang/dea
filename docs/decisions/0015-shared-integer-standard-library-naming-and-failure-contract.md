# ADR-0015: Shared Integer Standard-Library Naming and Failure Contract

- Decision date: 2026-04-14
- Last edited: 2026-07-27
- Status: Accepted

## Context

L0 and L1 share a signed 32-bit `int` helper surface. L1 additionally provides `uint`, `long`, and `ulong`. Without a
fixed naming policy, the common family could acquire redundant type suffixes, wider L1 families could depend on
overloading that the language does not provide, or `uint` callers could be forced to widen to `ulong`.

Integer helpers also have different kinds of failure. A zero divisor, invalid clamp bounds, or invalid alignment is a
caller contract violation. A mathematically meaningful operation may instead have no result in the target type, such as
the absolute value of the minimum signed integer, multiplication overflow, an out-of-range greatest common divisor, or
alignment round-up overflow. Treating every case as nullable hides precondition errors; treating every case as a panic
hides recoverable representability failure.

The API was introduced under `std.math` and now lives under `std.integer`; the module rename did not change this naming
or failure contract.

## Decision

The shared `int` helper family uses unsuffixed public names. Dea does not add `_i` aliases and does not use overloads to
distinguish integer widths.

L1-only wide families use explicit suffixes:

- `_ui` for `uint`;
- `_l` for `long`;
- `_ul` for `ulong`.

`uint` has a direct 32-bit family rather than requiring callers to widen to `ulong`. Signed `long` mirrors the shared
signed surface where the operation remains meaningful. `ulong` remains selective and omits signed-only concepts.
Unsigned quotient and remainder helpers use `div_*` and `mod_*`, because ordinary and Euclidean unsigned division
coincide.

Invalid caller preconditions use `assert`. This includes zero or otherwise invalid divisors, invalid clamp bounds, and
invalid alignment values.

Functions return plain values when they are total after their preconditions, or when their contract requires the
mathematical result to be representable. Functions return nullable values only when a valid input can produce a domain
or representability failure. In particular, checked signed absolute value, multiplicative helpers, square-root domain
checks, and alignment operations use nullable results where their target width requires it. Unsigned operations remain
plain when their result is always representable and nullable when overflow can occur.

Saturating arithmetic is not part of this contract.

## Rationale

- Unsuffixed names keep the shared and most common `int` surface concise.
- Explicit wide suffixes make width visible without requiring overload resolution or implicit widening.
- A direct `uint` family preserves the intended width and avoids turning `ulong` into an accidental universal unsigned
  API.
- Assertions distinguish programmer violations of a documented precondition from valid calculations whose results do not
  fit the target type.
- Nullable checked results let callers handle mathematical failure without converting every arithmetic helper into a
  fallible operation.
- Keeping signed-only operations out of unsigned families prevents a mechanically complete but semantically incoherent
  API.

## Consequences

- L0 and L1 keep the shared unsuffixed `int` signatures and edge cases aligned.
- L1 documentation and code use `_ui`, `_l`, and `_ul` consistently; `_i` is not a compatibility spelling.
- Callers handle `null` for checked domain or representability cases but may rely on ordinary return values for total
  operations.
- Invalid preconditions terminate through the standard assertion contract rather than returning `null`.
- Signed minimum values require explicit coverage because several mathematically non-negative results cannot fit their
  signed type.
- Adding another fixed-width integer family requires a deliberate suffix and the same precondition-versus-failure
  analysis.
- The integer/floating-point module boundary and later module renames do not alter helper suffix or failure semantics.

## Related Plans

- [work/plans/features/closed/2026-04-14-shared-std-math-int-surface-noref.md](../../work/plans/features/closed/2026-04-14-shared-std-math-int-surface-noref.md):
  established the common unsuffixed `int` surface and failure policy
- [l1/work/plans/features/closed/2026-04-14-l1-std-math-wide-integer-followup-noref.md](../../l1/work/plans/features/closed/2026-04-14-l1-std-math-wide-integer-followup-noref.md):
  extended the policy to L1's `uint`, `long`, and `ulong` families
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the historical decision into the ADR catalog

## Current Docs

- [l0/docs/reference/standard-library.md](../../l0/docs/reference/standard-library.md): shared `std.integer` helper
  signatures and contracts
- [l1/docs/reference/standard-library.md](../../l1/docs/reference/standard-library.md): shared and wide `std.integer`
  helper families
- [l0/docs/decisions/0003-integer-model.md](../../l0/docs/decisions/0003-integer-model.md): L0 fixed-width integer
  semantics
- [l1/docs/decisions/0004-wide-integer-types.md](../../l1/docs/decisions/0004-wide-integer-types.md): L1 `uint`, `long`,
  and `ulong` semantics
