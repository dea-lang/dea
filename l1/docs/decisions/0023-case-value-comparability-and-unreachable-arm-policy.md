# ADR-0023: L1 Case Value Comparability and Unreachable-Arm Policy

- Decision date: 2026-06-08
- Last edited: 2026-07-27
- Status: Accepted

## Context

L1 originally required a `case` arm literal to have exactly the scrutinee type, apart from a special bigint path. That
made `case (value: long) { 1 => ... }` invalid even though `value == 1` was valid, and it excluded `float` and `double`
scrutinees despite their equality support.

An integer arm may also be well formed but outside the scrutinee's value domain, such as `-1` for an unsigned type or a
large value for a narrow type. Rejecting such arms hides the distinction between type incompatibility and static
unreachability. Emitting them directly as C `case` labels can overflow, invoke undefined behavior, or require runtime
checked arithmetic for a value that can never match.

## Decision

L1 `case` value dispatch follows the same type-comparability model as `==` rather than requiring exact
arm-value/scrutinee type equality.

The supported scrutinee families are the builtin integer types, `float`, `double`, `bool`, and `string`. After an arm's
compile-time value is resolved, the compiler classifies it as one of:

- possible: the value can compare equal to the scrutinee under the ordinary equality rules;
- always false: a well-formed integer value is outside the scrutinee's value domain; or
- error: the value's type family is not comparable with the scrutinee.

An always-false arm is accepted with warning `TYP-0111`. It is not a viable runtime branch and does not contribute to
definite-return analysis, but its body is still type-checked. Lowering must omit the arm or emit an explicitly false
condition; it must not materialize an overflowing C label, unsafe cast, or checked arithmetic operation.

Real-valued arms use ordinary real equality. This decision introduces no special NaN matching behavior.

## Rationale

Reusing equality comparability gives `case` and `==` one coherent numeric conversion model. Treating out-of-domain
integer values as warnings preserves useful reachability feedback without turning a type-correct program into an error.
Continuing to type-check an unreachable arm prevents reachability classification from hiding independent source errors.

The rejected alternatives were exact arm/scrutinee type matching, treating out-of-domain integer values as errors, and
skipping semantic analysis of statically impossible arm bodies.

## Consequences

- Changes to equality compatibility must account for `case` dispatch compatibility.
- Reachability classification remains distinct from ordinary type checking.
- Duplicate checking and backend lowering operate only on values that can participate in dispatch.
- Integer cases may require equality-chain lowering when C `switch` cannot preserve L1 semantics safely.
- `TYP-0107` reports incomparable arm values, while `TYP-0111` reports well-formed values that can never match.

## Related Plans

- [l1/work/plans/bug-fixes/closed/2026-06-08-stage1-case-builtin-literal-support-noref.md][case-plan]
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md][publication-plan]

## Current Docs

- [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]: `case` comparability, duplicate, and always-false
  diagnostics
- [l1/docs/reference/design-decisions.md][design-decisions]: equality and comparison policy
- [l1/docs/reference/grammar.md][grammar]: accepted `case` arm value forms

[case-plan]: ../../work/plans/bug-fixes/closed/2026-06-08-stage1-case-builtin-literal-support-noref.md
[design-decisions]: ../reference/design-decisions.md
[diagnostics]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[grammar]: ../reference/grammar.md
[publication-plan]: ../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md
