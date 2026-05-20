# ADR-0005: Floating-Point Semantics

- Decision date: 2026-04-13
- Last edited: 2026-05-20
- Status: Accepted

## Context

L1 needed `float` and `double` types for numeric programs. C's floating-point behavior is notoriously underspecified:
the standard allows implementations to use excess precision, flush denormals, or define behavior differently. Simply
lowering to C `float`/`double` without an explicit contract would make L1 floating-point semantics undefined by
accident.

## Decision

L1 defines a narrow, explicit contract for floating-point:

- `float` and `double` are builtin non-integer numeric types; `float` lowers to C `float`, `double` to C `double`.
- Unsuffixed real literals denote `double`; a trailing `f`/`F` denotes `float`.
- Floating arithmetic is non-panicking; division by zero is a defined language-level non-panicking operation on
  supported targets.
- The target must provide IEEE-style behavior with signed zero, infinities, NaNs, and non-trapping arithmetic.
- If these requirements are not met by the host C compiler and target, the backend must reject programs that use `float`
  or `double`.
- Implicit `float → double` widening is allowed; the reverse is not.
- Integer-to-float conversion requires an explicit `as` cast except for integer literals used in a typed float/double
  context.

## Rationale

- Plain C lowering is acceptable only when the target contract making it sound is stated explicitly; leaving it implicit
  would make L1 semantics implementation-defined.
- Rejecting unsupported FP targets is cleaner than silently producing programs that misbehave on those targets.
- The narrow conversion lattice avoids accidental promotion creep; explicit casts make conversions visible.

## Consequences

- `float / 0.0` is a language-defined non-panicking operation on supported targets (not a runtime abort).
- Backend or optimization changes must preserve the stated FP contract; they cannot silently weaken it.
- `std.real` provides `float` and `double` stdlib helpers; it is linked only when the compilation unit uses `sys.real`,
  not unconditionally.

## Related Plans

- [l1/work/plans/features/closed/2026-04-04-l1-float-double-literals-noref.md][fp-literals]
- [l1/work/plans/features/closed/2026-04-13-l1-float-backend-contract-followup-noref.md][fp-contract]
- [l1/work/plans/features/closed/2026-04-14-l1-std-real-module-noref.md][std-real]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §12 (floating-point semantics and backend contract)

[design-decisions]: ../reference/design-decisions.md
[fp-contract]: ../../work/plans/features/closed/2026-04-13-l1-float-backend-contract-followup-noref.md
[fp-literals]: ../../work/plans/features/closed/2026-04-04-l1-float-double-literals-noref.md
[std-real]: ../../work/plans/features/closed/2026-04-14-l1-std-real-module-noref.md
