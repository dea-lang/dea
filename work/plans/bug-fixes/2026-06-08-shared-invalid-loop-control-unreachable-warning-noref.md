# Bug Fix Plan

## Shared invalid loop-control unreachable warning

- Date: 2026-06-08
- Status: Draft
- Title: Stop invalid loop-control statements from poisoning unreachable-state analysis
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L0 Stage 1 statement analysis, then parity ports to self-hosted checkers
- Porting rule: Fix the L0 Stage 1 behavior first, then port the same loop-depth guard mechanically to L0 Stage 2 and L1
  Stage 1
- Target status:
  - L0 Stage 1: Pending
  - L0 Stage 2: Pending
  - L1 Stage 1: Pending
- Subsystem: Statement analysis / Control flow / Warnings
- Modules: `l0/compiler/stage1_py/l0_expr_types.py`, `l0/compiler/stage2_l0/src/expr_types.l0`,
  `l1/compiler/stage1_l0/src/expr_types.l0`
- Test modules: `l0/compiler/stage1_py/tests/type_checker/`, `l0/compiler/stage2_l0/tests/expr_types_test.l0`,
  `l1/compiler/stage1_l0/tests/expr_types_test.l0`
- Related:
  - `work/plans/bug-fixes/closed/2026-04-10-shared-loop-control-statement-parity-noref.md`
  - `work/plans/bug-fixes/closed/2026-04-10-shared-unreachable-warning-parity-noref.md`
- Repro: `l0c --check` / `l1c --check` on a function containing top-level `break;` or `continue;` followed by another
  statement

## Summary

Invalid `break` and `continue` placement should report the placement error without marking later code unreachable.
Today, both invalid statements poison the same reachability state used for valid loop exits, so the next statement gets
a false `TYP-0030` unreachable-code warning.

This affects the shared statement checkers:

- top-level `break;` emits `TYP-0110`, then incorrectly causes `TYP-0030` on the following statement,
- top-level `continue;` emits `TYP-0120`, then incorrectly causes `TYP-0030` on the following statement.

## Current Behavior

This program should report only `TYP-0120`:

```dea
module hello;
import std.io;
func main() {
    continue;
    printl_s("hello");
}
```

Current output also warns that `printl_s("hello")` is unreachable:

```text
error: [TYP-0120] 'continue' statement not within a loop
warning: [TYP-0030] unreachable code
```

The same false warning occurs after invalid top-level `break;` with `TYP-0110`.

## Root Cause

The statement checkers validate loop-control placement and reachability as two separate steps, but the reachability step
does not depend on successful placement validation.

Current shape:

- emit `TYP-0110` when `break` appears with loop depth zero,
- emit `TYP-0120` when `continue` appears with loop depth zero,
- unconditionally mark the next statement unreachable after either statement.

That unconditional final step is correct only when the loop-control statement is inside a valid loop body.

## Scope of This Fix

1. Preserve the existing placement diagnostics:
   - `TYP-0110` for `break` outside a loop,
   - `TYP-0120` for `continue` outside a loop.
2. Mark the next statement unreachable only for valid `break` / `continue` statements.
3. Keep valid loop-body behavior unchanged: code after an unconditional valid `break` or `continue` should still report
   `TYP-0030`.
4. Cover invalid loop-control statements in ordinary blocks and in `with` headers or inline cleanup clauses outside
   loops.

## Approach

### L0 Stage 1

Update `BreakStmt` and `ContinueStmt` checking in `l0_expr_types.py`:

- if loop depth is zero, emit the existing error and do not set `_next_stmt_unreachable`,
- otherwise set `_next_stmt_unreachable = True`.

### L0 Stage 2 and L1 Stage 1

Mirror the same guard in the `ST_BREAK` and `ST_CONTINUE` branches:

- if `loop_depth < 1`, emit the existing diagnostic and leave `next_stmt_unreachable` unchanged,
- otherwise set `next_stmt_unreachable = true`.

No diagnostic-code changes are needed.

## Tests

Add focused coverage in all three target checkers:

1. Invalid top-level `break;` followed by another statement reports `TYP-0110` and does not report `TYP-0030` for the
   following statement.
2. Invalid top-level `continue;` followed by another statement reports `TYP-0120` and does not report `TYP-0030` for the
   following statement.
3. Valid unconditional `break;` inside a loop still reports `TYP-0030` on the next statement in the same loop body.
4. Valid unconditional `continue;` inside a loop still reports `TYP-0030` on the next statement in the same loop body.
5. Invalid `with (... => break)` and `with (... => continue)` outside loops report only the placement diagnostics, not
   false unreachable warnings on following statements.

## Verification

Suggested focused checks:

```bash
make -C l0 test-stage1
make -C l0 test-stage2 TESTS="expr_types_test"
make -C l1 test-stage1 TESTS="expr_types_test"
```

Manual repro checks should confirm that `--check` reports `TYP-0110` / `TYP-0120` without a following false `TYP-0030`
for invalid loop-control statements.

## Non-Goals

1. Suppressing warnings after arbitrary type errors.
2. Changing the meanings or severities of `TYP-0110`, `TYP-0120`, or `TYP-0030`.
3. Broadening unreachable-code analysis beyond the current statement-checker model.
4. Changing parser behavior or loop grammar.
