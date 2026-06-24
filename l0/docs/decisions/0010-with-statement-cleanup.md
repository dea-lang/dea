# ADR-0010: `with` Statement and Deterministic Cleanup

- Decision date: 2025-12-29
- Last edited: 2026-06-24
- Status: Accepted

## Context

L0 programs acquire resources (ARC-managed strings, handles, allocated memory) that need deterministic release at block
exit, including on early exit paths (`return`, `break`, `continue`, `?`). A structured cleanup facility was needed that
works correctly with ARC and with the null-propagation operator.

The alternatives considered were: `defer` (Go-style deferred statements), try/finally (Java/Python style),
destructor-based RAII (C++ style), and an explicit cleanup statement attached to each `with` binding.

## Decision

L0 provides a `with` statement with two forms:

```
WithStmt ::= "with" "(" WithItemList ")" Block
           | "with" "(" WithItemList ")" Block "cleanup" Block

WithItem ::= SimpleStmt "=>" SimpleStmt   (* inline cleanup *)
           | SimpleStmt                   (* cleanup-block form *)
```

Semantics:

- The inline form (`A => B`): each header item has its own cleanup statement. Cleanup runs in LIFO order at block exit.
- The `cleanup` block form: a single cleanup block runs at block exit for all successfully initialized header items.
- The two forms are mutually exclusive within a single `with` statement; mixing is a parse error.
- Cleanup runs on every exit from the body: normal fall-through, `return`, `break`, and `continue`.
- Cleanup also runs on early exit from `with` headers caused by `?` (null propagation), but only for items that
  completed initialization before the short-circuit.
- Cleanup fallthrough resumes the pending exit. An abrupt cleanup (`return`, valid `break`, or valid `continue`)
  replaces that exit; inline cleanup statements execute in LIFO order until one transfers control.
- ARC drop sequencing inside `with` bodies follows the same slot-replacement rules as ordinary assignment.

## Rationale

- Attaching cleanup to the binding site (rather than deferring to a separate defer/finally block) keeps resource
  acquisition and release co-located, which makes the code easier to audit.
- Inline `=>` is concise for single-resource patterns; the `cleanup` block handles multi-step cleanup that must run as
  an atomic sequence.
- `defer` was not chosen because deferred statements execute in registration-reverse order across an entire function,
  which interacts poorly with ARC temporaries and makes cleanup reasoning harder when control flow is complex.
- RAII was not chosen because L0 does not have destructors; the `with` statement is the explicit deterministic cleanup
  mechanism.

## Consequences

- The backend must insert ARC cleanup correctly before every early exit from a `with` body, including `?`-triggered
  exits from header expressions.
- The parser enforces the mutual-exclusivity constraint (inline form vs. cleanup block) at parse time.
- `drop` remains available for early deallocation of `new`-allocated heap objects outside `with`, for cases where
  block-scoped cleanup is not the right structure. It operates on raw pointers, not ARC-managed values.

## Related Plans

- `work/plans/bug-fixes/closed/2026-06-22-shared-for-header-and-statement-flow-safety-noref.md`: defines cleanup exit
  precedence when an abrupt cleanup replaces a pending `with` exit.
- Pre-plan ARC cleanup history is summarized from
  [l0/docs/decisions/0008-arc-ownership-model.md](0008-arc-ownership-model.md).

## Current Docs

- [l0/docs/reference/ownership.md](../reference/ownership.md): normative `with` cleanup semantics, ARC interaction, LIFO
  ordering rules
- [l0/docs/reference/grammar.md](../reference/grammar.md): §5.6 (`with` statement grammar and constraints)
