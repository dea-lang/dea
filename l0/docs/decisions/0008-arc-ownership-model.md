# ADR-0008: ARC Ownership Model

- Decision date: 2025-12-29
- Last edited: 2026-05-20
- Status: Accepted

## Context

L0 strings are immutable heap-allocated values that can be passed around, returned from functions, stored in structs,
and used in temporaries. Without a memory management strategy, strings would either leak or require manual
`retain`/`release` calls everywhere.

The broader question was: what ownership discipline governs all ARC-managed types, not just strings?

## Decision

Strings (and any future ARC-managed types) use automatic reference counting (ARC) with compiler-inserted
`retain`/`release` calls.

The ARC model:

- Every assignment to an ARC-managed slot retains the incoming value and releases the previous occupant
  (slot-replacement semantics).
- Temporaries produced during expression evaluation are retained on materialization and released after the statement
  that consumes them.
- Parameters of ARC-managed type are borrowed (not retained on entry) unless they are reassigned inside the function
  body, in which case an entry retain is inserted defensively.
- The `with` statement provides deterministic cleanup at block exit.
- `drop` frees `new`-allocated heap objects early; it operates on raw pointers, not on ARC-managed values.

The C kernel owns `rt_string_retain` and `rt_string_release`. The Stage 1 Python backend and Stage 2 L0 backend handle
ARC insertion logic.

## Rationale

- ARC is simpler to implement than a tracing garbage collector and requires no runtime scanning.
- Compiler-inserted calls mean user code stays ARC-clean without manual retain/release discipline.
- The kernel boundary keeps reference-count manipulation in auditable C code, not scattered through generated output.

## Consequences

- The backend must correctly handle ARC cleanup in all control-flow paths: `if`, `while`, `for`, `with`, `match`,
  `break`, `continue`, `return`, and the null-propagation operator `?`.
- Several early bug-fix plans addressed ARC correctness in edge cases (see Related Plans below).
- The slot-replacement rule is normative: reassignment of an ARC-managed variable always releases the old value before
  retaining the new one.
- Borrowed parameter reassignment requires an entry retain; the rule is documented in `l0/docs/reference/ownership.md`.

## Related Plans

- [l0/work/plans/bug-fixes/closed/2026-02-15-arc-bug-fixes-noref.md](../../work/plans/bug-fixes/closed/2026-02-15-arc-bug-fixes-noref.md):
  ARC leaks for temporaries and discarded results
- [l0/work/plans/bug-fixes/closed/2026-02-17-arc-return-expression-temp-cleanup-noref.md](../../work/plans/bug-fixes/closed/2026-02-17-arc-return-expression-temp-cleanup-noref.md):
  leaked ARC temporaries in return expressions
- [l0/work/plans/bug-fixes/closed/2026-02-17-missing-cleanup-when-try-fails-in-with-noref.md](../../work/plans/bug-fixes/closed/2026-02-17-missing-cleanup-when-try-fails-in-with-noref.md):
  missing cleanup when `?` fails in `with` headers
- [l0/work/plans/bug-fixes/closed/2026-02-25-arc-opt-as-string-unwrap-ownership-noref.md](../../work/plans/bug-fixes/closed/2026-02-25-arc-opt-as-string-unwrap-ownership-noref.md):
  ownership lowering for `string?` unwrap
- [l0/work/plans/bug-fixes/closed/2026-03-11-general-logical-short-circuit-arc-temp-lowering-noref.md](../../work/plans/bug-fixes/closed/2026-03-11-general-logical-short-circuit-arc-temp-lowering-noref.md):
  ARC temps and `&&`/`||` short-circuit lowering
- [l0/work/plans/bug-fixes/closed/2026-03-11-stage1-backend-condition-arc-temp-control-flow-noref.md](../../work/plans/bug-fixes/closed/2026-03-11-stage1-backend-condition-arc-temp-control-flow-noref.md):
  ARC temps hoisted out of `if`/`while`/`for` headers
- [work/plans/bug-fixes/closed/2026-04-21-shared-arc-borrowed-param-reassignment-noref.md](../../../work/plans/bug-fixes/closed/2026-04-21-shared-arc-borrowed-param-reassignment-noref.md):
  defensive entry retain for borrowed param reassignment
- [work/plans/bug-fixes/closed/2026-04-30-shared-arc-owned-local-reassignment-semantics-noref.md](../../../work/plans/bug-fixes/closed/2026-04-30-shared-arc-owned-local-reassignment-semantics-noref.md):
  slot-replacement semantics correctness

## Current Docs

- [l0/docs/reference/ownership.md](../reference/ownership.md): normative ownership rules, ARC contract, and normative
  rules matrix
- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §11 (string value semantics)
