# Bug Fix Plan

## Shared `with` inline abrupt header cleanup

- Date: 2026-06-08
- Status: Completed
- Title: Run inline `with` cleanup for committed abrupt header exits
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L0 Stage 1 backend lowering, then parity ports to L0 Stage 2 and L1 Stage 1
- Porting rule: Fix L0 Stage 1 first, then mechanically port the same lowering rule to the L0 and L1 self-hosted
  backends
- Target status:
  - L0 Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Backend / `with` lowering / Control-flow cleanup
- Modules:
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage2_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/integration/test_with_statement.py`
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
- Related:
  - `l0/docs/decisions/0010-with-statement-cleanup.md`
  - `l0/docs/reference/grammar.md`
  - `l1/docs/reference/grammar.md`
- Repro: `l0c --run` / `l1c --run` on `with (return 42 => printl_s("leaving")) { }`

## Summary

Inline `with` cleanup currently fails to run when the header init statement itself performs a committed abrupt exit such
as `return 42`.

This violates the live L0 and L1 reference grammars. Both specify that cleanup runs before early exits from header
initializers, with a special `?` carve-out: if the current header item short-circuits via `?`, only prior successfully
completed inline items are cleaned.

## Current Behavior

This cleanup-block form prints `leaving` and exits with `42`:

```dea
with (return 42) {
}
cleanup {
    printl_s("leaving");
}
```

The inline form should be equivalent for this committed `return`, but currently exits with `42` without printing:

```dea
with (return 42 => printl_s("leaving")) {
}
```

L0 Stage 1 and the L0/L1 self-hosted backends all have the same lowering shape.

## Root Cause

Cleanup-block lowering registers the cleanup block on the `with` scope before emitting header statements.

Inline lowering registers each item cleanup only after emitting that item's header init. If the init is `return`,
`break`, or `continue`, backend cleanup emission runs before the paired inline cleanup has been recorded, so the exit
path sees no cleanup for the current item.

Registering inline cleanup unconditionally before the init would be wrong for `?`: a failing `?` in the current item
must not run that item's cleanup.

## Scope of This Fix

1. Preserve grammar and diagnostics; no parser, AST, or diagnostic-code changes.
2. For inline `with` items, run the paired cleanup before committed abrupt exits from that header item:
   - `return`,
   - valid `break`,
   - valid `continue`.
3. Preserve existing `?` behavior:
   - a failing `?` in the current header item does not run that item's inline cleanup,
   - prior successfully completed inline items still clean up.
4. Preserve cleanup return precedence: if cleanup itself returns, it overrides the pending return.
5. Keep cleanup order LIFO for multiple inline items.

## Approach

### L0 Stage 1

Refactor inline-header emission in `l0_backend.py` so paired cleanup can be made visible at the exact committed-exit
point.

Recommended shape:

- Add a helper for emitting one inline `with` header item.
- For ordinary init statements, keep current behavior: emit init, then register cleanup.
- For `ReturnStmt` init:
  - evaluate and stabilize the return expression using the existing return-temp logic,
  - register the current item cleanup,
  - emit normal return cleanup and final return.
- For `BreakStmt` and `ContinueStmt` init:
  - register the current item cleanup,
  - then emit the existing loop-exit cleanup and branch.
- Leave `TryExpr` lowering unchanged so current-item cleanup is not registered before a `?` failure path.

### L0 Stage 2 and L1 Stage 1

Port the same backend rule to `be_emit_with_stmt()` and nearby return / loop-exit helpers:

- keep cleanup-block lowering unchanged,
- add the same inline-item committed-exit handling around `ST_RETURN`, `ST_BREAK`, and `ST_CONTINUE`,
- keep self-hosted helper names and Doxygen style local to each subtree.

## Tests

Add focused coverage in all three targets:

1. `with (return 42 => printl_s("leaving")) { }` prints `leaving` and exits `42`.
2. `with (return value() => cleanup()) { }` evaluates the return value before cleanup and returns the pre-cleanup value.
3. `with (return 42 => return 7) { }` exits `7`.
4. Multiple inline items preserve LIFO cleanup order when the later item returns.
5. A `?` failure in the current header item does not run that item's cleanup, but does run prior successful item
   cleanup.
6. Inside loops, `with (break => cleanup()) { }` and `with (continue => cleanup()) { }` run cleanup before loop exit.

## Verification

Completed focused checks:

```bash
../.venv/bin/python -m pytest compiler/stage1_py/tests/integration/test_with_statement.py
make -C l0 test-stage2 TESTS="backend_test l0c_stage2_arc_trace_regression_test"
make -C l1 test-stage1 TESTS="backend_test l1c_stage1_arc_trace_regression_test"
```

Completed manual repro checks:

```bash
./scripts/l0c -P "$tmpdir/inline" --run hello
./build/dea/bin/l0c-stage2 -P "$tmpdir/inline" --run hello
./build/dea/bin/l1c --run "$tmpdir/hello.l1"
```

All three direct repro checks printed `leaving` and exited with status `42`.

## Non-Goals

1. Changing `with` grammar or making inline cleanup and cleanup-block form identical for all header failure paths.
2. Running current-item inline cleanup on `?` failure inside that same item.
3. Changing cleanup-block nullable predeclaration behavior.
4. Reworking ARC cleanup beyond the control-flow path needed for this bug.
