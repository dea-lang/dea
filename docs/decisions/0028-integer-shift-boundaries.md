# ADR-0028: Integer Shift Boundaries

- Decision date: 2026-11-11
- Last edited: 2026-11-11
- Status: Accepted

## Context

L1 and L2 require defined integer behavior, but their shifts previously lowered to raw C operators. Negative or
excessive counts, negative signed left operands, and unrepresentable signed left results could invoke undefined
behavior. The common-integer-type lattice and arithmetic signed right shifts were already language contracts; the
remaining boundary policy needed an explicit shared decision.

## Decision

1. Normalize both operands through the existing common-integer-type lattice. The normalized result is `int`, `uint`,
   `long`, or `ulong`, and its width is 32 or 64 bits. Narrow source operands do not independently select a shift width.
2. Both shift directions require a normalized count in `[0, width)`. Other counts produce a controlled arithmetic
   failure; counts are never masked or reduced modulo the width.
3. Signed left shift computes mathematical multiplication by `2^count`. Negative inputs are permitted when the exact
   result fits the normalized signed domain; otherwise the operation fails. For runtime `int` operands, `(-1, 31)`
   yields the minimum value while `(1, 31)` overflows.
4. Unsigned left shift retains fixed-width bit-pattern behavior and discards shifted-out high bits. It does not acquire
   the checked multiplication policy of ordinary unsigned arithmetic.
5. Signed right shift is arithmetic, equivalent to division by `2^count` rounded toward negative infinity. Unsigned
   right shift is logical. Runtime helpers avoid invalid C shifts and implementation-defined negative signed shifts.
6. These arithmetic guarantees apply in default, basic, and unchecked pointer-runtime modes. Both operands are evaluated
   once. Pointer-check selection does not relax integer semantics.
7. The constant evaluator retains its documented conservative subset. Supporting additional runtime operands does not
   make those expressions compile-time evaluable.

## Rationale

Checked signed scaling extends the existing representability policy to the previously undefined signed left-shift cases.
It permits useful negative inputs without adopting accidental host-C behavior. Preserving unsigned bit discard retains
already-defined bit-manipulation behavior. Count rejection catches erroneous inputs instead of silently changing the
requested operation. Explicit helpers make these guarantees independent of host optimizations and pointer-check mode.

## Consequences

Generated L1/L2 C calls typed shift helpers, so native consumers require matching owned runtime headers and archives.
Existing common-type conversions and expression result types remain unchanged. No source diagnostic code, masking rule,
constant-folding expansion, or L0 shift operator is introduced. Native regression tests distinguish controlled Dea
errors from sanitizer failures and cover each owned compiler implementation independently.

## Related Plans

- [work/plans/bug-fixes/closed/2026-11-11-shared-shift-boundary-undefined-behavior-noref.md][shift-plan]

## Current Docs

- [l1/docs/reference/design-decisions.md][l1-decisions]
- [l1/docs/reference/grammar.md][l1-grammar]
- [l2/docs/reference/design-decisions.md][l2-decisions]
- [l2/docs/reference/grammar.md][l2-grammar]

[l1-decisions]: ../../l1/docs/reference/design-decisions.md#11-integer-and-failure-semantics
[l1-grammar]: ../../l1/docs/reference/grammar.md#6-expressions
[l2-decisions]: ../../l2/docs/reference/design-decisions.md#integer-boundaries
[l2-grammar]: ../../l2/docs/reference/grammar.md#6-expressions
[shift-plan]: ../../work/plans/bug-fixes/closed/2026-11-11-shared-shift-boundary-undefined-behavior-noref.md
