# Bug Fix Plan

## Shared `for`-header and statement-flow safety

- Date: 2026-06-22
- Status: Completed
- Title: Restore shared `for`-header control flow, cleanup, drop-liveness, and trace ownership safety
- Kind: Bug Fix
- Scope: Shared
- Severity: Critical
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
  - Shared reference docs
- Origin: Cross-compiler audit of abrupt statements and destructive `drop` flow
- Porting rule: Settle semantics in L0 Stage 1, then port the homologous analyzer and backend rules mechanically to L0
  Stage 2 and L1 Stage 1 while preserving L1-only `const` diagnostics
- Target status:
  - L0 Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
  - Shared reference docs: Implemented
- Subsystem: Parser / Statement flow / Drop liveness / Backend cleanup / Trace ownership
- Modules: `l0/compiler/stage1_py/l0_expr_types.py`, `l0/compiler/stage1_py/l0_backend.py`,
  `l0/compiler/stage2_l0/src/expr_types.l0`, `l0/compiler/stage2_l0/src/backend.l0`,
  `l1/compiler/stage1_l0/src/expr_types.l0`, `l1/compiler/stage1_l0/src/backend.l0`
- Test modules: `l0/compiler/stage1_py/tests/type_checker/test_control_flow.py`,
  `l0/compiler/stage1_py/tests/integration/test_with_statement.py`, `l0/compiler/stage2_l0/tests/expr_types_test.l0`,
  `l1/compiler/stage1_l0/tests/expr_types_test.l0`, and the L0/L1 ARC trace regression suites
- Related:
  - `l0/docs/decisions/0010-with-statement-cleanup.md`
  - `work/plans/bug-fixes/closed/2026-04-10-shared-loop-control-statement-parity-noref.md`
  - `work/plans/bug-fixes/closed/2026-06-08-shared-with-inline-abrupt-header-cleanup-noref.md`
- Repro: run the focused nested-loop, dropped-pointer, and traced cleanup cases documented below through all three
  compilers

## Summary

The final grammar rejects only `let` declarations in a `for` update clause with `PAR-0145`. Other simple statements
remain valid in both header positions, but their analysis and lowering were inconsistent:

- header `break` and `continue` validated against an enclosing loop but targeted the inner `for` during lowering,
- update `continue` could jump to itself indefinitely,
- mismatched loop-label and cleanup stacks could release an outer ARC value and then continue using it,
- normal condition-false exit skipped cleanup of ARC values declared by the initialization clause,
- update-before-body analysis produced incorrect reachability and drop-liveness state,
- loop-body assignment could unsafely revive a dropped value on a zero-iteration path,
- assignment revived a bare target before evaluating its RHS,
- `with` header and inline-cleanup returns did not participate consistently in definite-return analysis,
- self-hosted loop-liveness fixed-point helpers leaked the final empty iteration wrapper after transferring the captured
  liveness state.

## Semantics

- `for` initialization and update clauses execute in the enclosing loop context. Header `break` and `continue` target
  that enclosing loop and report `TYP-0110` / `TYP-0120` when none exists.
- Initialization executes once before the inner loop becomes active. Update executes after body fallthrough or an
  inner-body `continue`, before the next condition check.
- `return` and `drop` retain their ordinary statement behavior at either header execution point.
- `PAR-0145` remains specific to an update-clause `let`; L1 local `const` continues to use `PAR-0263`.
- A loop may execute zero times for definite-liveness purposes. A variable is usable only when alive on every path
  reaching the use.
- Inline `with` cleanup remains LIFO. Cleanup fallthrough resumes a pending exit, while cleanup `return`, `break`, or
  `continue` replaces it. A failing header `?` does not register the current inline cleanup.

## Implementation

1. Analyze `for` in runtime order and merge pre-loop and post-iteration liveness conservatively.
2. Delay bare-target revival until after RHS validation so a dead value cannot revive itself.
3. Expose inner loop labels and cleanup boundaries only while lowering the condition/body region; init/update control
   continues to see the enclosing loop.
4. Route condition-false and inner-body `break` through one initialization-scope cleanup point, while body `continue`
   cleans only the iteration scope before update.
5. Propagate definite returns from `for` initialization and all established `with` return forms without treating a
   zero-iteration loop body/update return as guaranteed.
6. Drop self-hosted `LoopIterationFlow` wrappers after moving fixed-point capture and backedge-state ownership into the
   returned flow result.
7. Reuse existing diagnostic codes; no new diagnostic reservation is required.

## Verification

- Header `break` / `continue` without an outer loop report placement diagnostics; nested cases target the outer loop.
- Header `return` works in init/update and preserves cleanup/value ordering.
- Header `drop` respects loop order and definite liveness, including zero-iteration and reassignment paths.
- `p = p` after `drop p` reports `TYP-0150`; assignment of a fresh value may revive the binding.
- Normal condition-false exit releases initialization-scope ARC values once.
- Nested-header double-free and update-continue self-loop reproducers complete safely.
- `with` header, inline-cleanup, cleanup-block, and body returns agree across all three analyzers.
- Focused parser, analyzer, backend, and trace tests pass before the full L0 and L1 suites.
- Focused L0 Stage 2 and L1 Stage 1 `expr_types_test` trace runs report zero leaked object and string pointers.

Completed verification:

- `env L0_TEST_JOBS=2 L1_TEST_JOBS=2 make test-all`
- L0 focused `expr_types_test` trace with `DEA_BUILD_DIR=build/dea`: `leaked_object_ptrs=0` and `leaked_string_ptrs=0`.
- L1 focused `expr_types_test` trace: `leaked_object_ptrs=0` and `leaked_string_ptrs=0`.

## Non-Goals

1. Rejecting `return`, `break`, `continue`, or `drop` from `for` headers.
2. Labeled loop control or constant-condition/infinite-loop proofs.
3. Changing AST shape or `with` syntax.
