# ADR-0024: L1 Named-Call Syntax, Completeness, and Evaluation Order

- Decision date: 2026-04-22
- Last edited: 2026-07-27
- Status: Accepted

## Context

Positional calls couple source order to declaration order. L1 needed labels for function and constructor arguments
without simultaneously introducing default arguments, partial naming, or unspecified side-effect order.

Named arguments create two independent orders: the order in which expressions appear and must be evaluated, and the
declaration order in which values must reach the callee or constructed object. A durable rule is required so backend
reordering cannot silently change program behavior.

## Decision

Top-level function calls, struct constructors, and enum-variant constructors accept named arguments with the syntax
`label: expression`.

Each argument list is entirely positional or entirely named. A named list must supply every required parameter, field,
or payload label exactly once. Unknown labels, duplicate labels, and omissions are static errors. Named arguments may
appear in any written order and resolve to the corresponding declaration-order slots.

Argument expressions evaluate from left to right in written source order. Lowering must stabilize those results before
placing them into declaration order for the call or constructor.

Compiler intrinsics do not accept labels. Function-pointer calls do not accept labels because function-pointer types do
not retain source parameter names. Named variadic calls are outside the named-call surface.

## Rationale

An all-positional or all-named rule makes call interpretation deterministic without adding defaults or partial naming.
Exact completeness catches misspellings and omissions at the call site. Preserving written evaluation order keeps
visible side effects independent of parameter order and backend implementation details.

The rejected alternatives were allowing a positional prefix followed by named arguments, evaluating named expressions in
declaration order, and treating omitted labels as an implicit default-argument mechanism.

## Consequences

- The AST preserves labels and written argument order until semantic resolution and lowering are complete.
- Type checking maps labels to declaration slots and diagnoses unknown, duplicate, and missing labels.
- Backends may need temporaries when written order differs from declaration order.
- Positional calls retain their existing behavior.
- Adding labels to function-pointer calls would require a separate type-identity and metadata decision.

## Related Plans

- [l1/work/plans/features/closed/2026-04-22-named-arguments-noref.md][named-arguments]
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md][publication-plan]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: named-call completeness, exclusions, and evaluation order
- [l1/docs/reference/grammar.md][grammar]: named argument syntax and accepted call surfaces

[design-decisions]: ../reference/design-decisions.md
[grammar]: ../reference/grammar.md
[named-arguments]: ../../work/plans/features/closed/2026-04-22-named-arguments-noref.md
[publication-plan]: ../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md
