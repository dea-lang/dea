# Bug Fix Plan

## Stage 2 for-loop variable scope leaks, causing false TYP-0021 shadow warnings

- Date: 2026-06-05
- Status: Closed (fixed)
- Title: Scope L0 Stage 2 for-loop variables to their loop so sibling loops do not trigger false `TYP-0021` shadow
  warnings
- Kind: Bug Fix
- Severity: Medium
- Stage: Stage 2
- Subsystem: Name resolution / locals scope building / type checker
- Modules:
  - `compiler/stage2_l0/src/locals.l0`
- Test modules:
  - `compiler/stage2_l0/tests/expr_types_test.l0`
  - `compiler/stage2_l0/tests/fixtures/typing/typing_for_loop_scope.l0`
  - `compiler/stage1_py/tests/type_checker/test_control_flow.py`
- Related:
  - `l0/work/plans/bug-fixes/closed/2026-06-05-stage2-surface-warnings-in-build-run-gen-noref.md`
- Repro:
  ```l0
  module m;
  func f() -> int {
      let t = 0;
      for (let i = 0; i < 3; i = i + 1) { t = t + i; }
      while (0 < 1) { for (let i = 0; i < 3; i = i + 1) { t = t + i; } break; }
      return t;
  }
  ```
  `l0c-stage2 --check m` warned `[TYP-0021] ... 'i' shadows an outer local`; Stage 1 did not.

## Summary

After warnings began surfacing during builds, the L1 bootstrap build (compiled by `l0c-stage2`) emitted several
`TYP-0021` "shadows an outer local" warnings for sibling for-loops that reuse `i`. Stage 1 (the oracle) did not. The
cause was a Stage 2 scope-building bug: a for-loop variable was declared into the enclosing block scope instead of a
per-loop scope, so it lingered and a later, deeper sibling `for (let i ...)` appeared to shadow it.

## Root Cause

In `lc_visit_stmt` (`compiler/stage2_l0/src/locals.l0`), the `ST_FOR` arm visited the init statement (`let i`) and the
step with the enclosing `scope` and only created a child scope for the loop body. The loop variable therefore lived in
the enclosing block and was never popped, so the type checker's `TYP-0021` shadow check (`expr_types.l0`, via the
alive-scope stack) still saw it when a deeper sibling loop redeclared `i`. Stage 1's checker pushes/pops a dedicated
scope per `ForStmt`, so it never leaked. The `block_scopes` metadata is consumed only by `locals.l0` and `expr_types.l0`
(type checking); codegen does not use it, so the fix has no effect on generated C.

## Fix

Give the for-loop its own header scope, mirroring `lc_visit_with`: create a `header_scope` (child of the enclosing
scope), register it for the for-statement id so the type checker enters and exits it, declare the init and step into the
header scope, and create the body scope as a child of the header. The loop variable is then popped with the header scope
when the loop ends.

## Non-Goals

- No change to genuine nested shadowing, which still warns once.
- No change to loop-variable visibility (the variable remains unusable after the loop, `TYP-0159`).
- No change to Stage 1, which was already correct.

## Verification Criteria

- Sibling and deeper-but-disjoint reuse of a loop variable produces no `TYP-0021` in Stage 2, matching Stage 1.
- A genuinely nested loop variable still warns exactly once in both stages.
- A loop variable referenced after its loop still errors (`TYP-0159`) in both stages.

## Outcome

Implemented as described. Validation:

- New Stage 2 `test_typing_for_loop_scope` with fixture `typing_for_loop_scope.l0` asserting exactly one `TYP-0021` (the
  genuine nested shadow only) and no errors.
- New Stage 1 oracle pins `test_for_loop_variable_scope_does_not_leak_to_siblings` and
  `test_for_loop_genuine_nested_shadow_warns` in `test_control_flow.py`.
- Both stages agree on the repro (clean), on a genuine nested shadow (one `TYP-0021`), and on loop-variable escape
  (`TYP-0159`).
- Full `make -C l0 clean test-all` (Stage 1 + Stage 2 incl. triple-bootstrap, trace suites, examples) green; `l0c`
  self-check emits zero `TYP-0021`.
