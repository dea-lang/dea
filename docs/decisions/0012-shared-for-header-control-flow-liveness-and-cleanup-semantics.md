# ADR-0012: Shared For-Header Control Flow, Liveness, and Cleanup Semantics

- Decision date: 2026-06-22
- Last edited: 2026-07-27
- Status: Accepted

## Context

Dea permits simple statements in the initialization and update clauses of a `for` loop. Declarations are valid in
initialization, while update-clause `let` declarations are rejected. The remaining statement surface includes abrupt
statements such as `return`, `break`, `continue`, and `drop`.

That expressive grammar exposed disagreements among parsing, semantic flow analysis, backend control-flow lowering, and
cleanup ownership. Header `break` and `continue` could be accepted because an outer loop existed but lowered to the
inner `for`; an update `continue` could jump back to itself; condition-false and abrupt exits could bypass or duplicate
cleanup; and analysis performed out of runtime order could produce unsound definite-liveness or definite-return facts.
The same flow model also has to compose with assignment after `drop` and with `with` cleanup, where cleanup may replace
a pending exit.

Because L0 Stage 1, L0 Stage 2, and L1 Stage 1 share these semantics, independently fixing individual lowering sites
would leave the language contract vulnerable to stage drift.

## Decision

`for` header clauses retain ordinary simple statements. A `let` declaration is allowed only in initialization, not in
update. L1's local `const` restriction remains separate.

Initialization and update execute in the context that encloses the `for`; the new loop is not an available target while
either header clause executes. Consequently, a header `break` or `continue` targets an already-enclosing loop and is a
placement error when no such loop exists. `return` and `drop` retain their ordinary statement meanings in either header
position.

Runtime order is:

1. execute initialization once;
2. test the condition;
3. execute the body;
4. after body fallthrough or a body `continue`, clean the iteration scope and execute update;
5. test the condition again.

Condition-false exit and body `break` leave through the initialization-scope cleanup point. A body `continue` cleans
only the iteration scope before update. A `continue` executed by the update itself targets an enclosing loop rather than
the `for` whose update is running.

Flow analysis follows that runtime order and treats the loop as possibly executing zero times. A binding is live at a
use only if it is live on every path reaching that use. Returns in initialization are definite, but returns in a body or
update that may execute zero times do not prove that the enclosing function returns. Assignment validates the right-hand
side before reviving a dropped bare target.

`with` cleanup remains LIFO. Cleanup fallthrough resumes a pending exit, while cleanup `return`, `break`, or `continue`
replaces that exit. A failing header `?` does not register the current inline cleanup. These cleanup rules participate
in the same definite-flow model as the loop rules.

L0 Stage 1 is the semantic oracle for this shared behavior. The self-hosted analyzers and backends preserve the same
observable control-flow, liveness, and cleanup contract.

## Rationale

- Keeping abrupt header statements preserves the existing expressive grammar and avoids inventing a reduced `BasicStmt`
  subgrammar solely for `for`.
- Targeting only an already-enclosing loop matches the scope in which a header executes. The inner loop cannot be a
  control target before its condition/body region is active.
- An explicit runtime order gives the parser, analyzer, backend, and cleanup lowering one model instead of a collection
  of local exceptions.
- Zero-iteration analysis is required for sound liveness and definite-return conclusions.
- Delaying revival until after right-hand-side validation prevents a dropped value from making itself appear live.
- Exit replacement during cleanup preserves deterministic cleanup while allowing cleanup code to terminate or redirect
  control deliberately.

## Consequences

- Parser diagnostics keep update-clause declaration restrictions separate from abrupt-statement placement checks.
- Analyzer loop fixed points must conservatively merge the pre-loop path with post-iteration paths.
- Backend loop labels and cleanup boundaries are visible only in the condition/body region; header lowering retains the
  enclosing context.
- Body `continue`, body `break`, condition-false exit, and header abrupt control take deliberately different cleanup
  paths.
- A loop body or update return cannot by itself satisfy definite-return checking because the condition may initially be
  false.
- Invalid exits and impossible paths must not mutate later reachability or ownership state.
- All compiler stages need parity tests for nested header control, zero-iteration drop liveness, assignment revival,
  initialization-scope ARC cleanup, and `with` exit replacement.

## Related Plans

- [work/plans/bug-fixes/closed/2026-06-22-shared-for-header-and-statement-flow-safety-noref.md](../../work/plans/bug-fixes/closed/2026-06-22-shared-for-header-and-statement-flow-safety-noref.md):
  settled and implemented the shared parser, flow-analysis, lowering, and cleanup rules
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the historical decision into the ADR catalog

## Current Docs

- [docs/specs/compiler/diagnostic-code-catalog.md](../specs/compiler/diagnostic-code-catalog.md): shared placement and
  `for`-header diagnostic meanings
- [l0/docs/decisions/0010-with-statement-cleanup.md](../../l0/docs/decisions/0010-with-statement-cleanup.md): L0 `with`
  cleanup and exit-replacement contract
- [l0/docs/reference/grammar.md](../../l0/docs/reference/grammar.md): L0 `for` header grammar
- [l1/docs/reference/grammar.md](../../l1/docs/reference/grammar.md): L1 `for` header grammar
