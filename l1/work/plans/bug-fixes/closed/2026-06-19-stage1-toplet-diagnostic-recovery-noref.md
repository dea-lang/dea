# Bug Fix Plan

## Preserve Stage 1 top-level initializer diagnostics after signature errors

- Date: 2026-06-19
- Status: Completed
- Title: Preserve Stage 1 top-level initializer diagnostics after signature errors
- Kind: Bug Fix
- Severity: Medium
- Stage: 1
- Subsystem: Analysis orchestration / expression typing / diagnostic recovery
- Modules:
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
- Test modules:
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/fixtures/typing/typing_toplet_diagnostic_recovery_err.l1`
- Related:
  - `l1/work/plans/features/closed/2026-06-17-stage1-const-value-grammar-contexts-noref.md`
  - `l1/work/plans/bug-fixes/closed/2026-06-18-stage1-toplet-initializer-typing-noref.md`
- Repro: `make -C l1 test-stage1 TESTS="expr_types_test"`

## Summary

Stage 1 stops before expression typing when signature resolution reports an error. A wrong-type named constant used as
an array length therefore prevents an independent initializer mismatch on that constant from being reported. The
compiler should report both the invalid initializer and the invalid array-bound use.

## Root Cause

`analysis_analyze_entry` returns after signature and local-scope resolution whenever the diagnostic collector contains
an error. Top-level initializer checking is implemented inside `expr_types_check`, so it is skipped together with
function-body checking even when the affected top-level binding has a resolved type and can be checked safely.

## Scope of This Fix

1. Enter expression typing after semantic setup even when an earlier semantic phase reported errors.
2. Always check initializers for top-level bindings whose declaration type resolved successfully.
3. Preserve the existing safety barrier by checking function bodies only when expression typing began without errors.
4. Reuse `TYP-0310` and `TYP-0816`; no diagnostic codes or meanings change.

## Non-Goals

- Recovering function-body diagnostics after name, signature, or local-scope errors.
- Checking top-level bindings whose destination type did not resolve.
- Changing constant evaluation, array-bound rules, or diagnostic ordering.

## Verification Criteria

1. The reported reproduction emits exactly one `TYP-0310` and one `TYP-0816`.
2. Existing top-level initializer failures remain single diagnostics rather than being checked twice.
3. The focused Stage 1 expression-type test passes.
4. The complete L1 test suite passes.

## Resolution

`analysis_analyze_entry` now enters expression typing after semantic setup regardless of earlier semantic errors.
`expr_types_check` snapshots the incoming error state, checks every resolved top-level initializer, and only checks
function bodies when the snapshot was clean. Modules without a resolved name environment and bindings without a resolved
destination type remain skipped.

The regression fixture reproduces the named-constant array-bound case and requires exactly one `TYP-0310` plus one
`TYP-0816`. Existing top-level initializer coverage now also requires exactly one `TYP-0310`, guarding against a
duplicate recovery pass.

## ADR Note

No ADR is required. The fix completes existing diagnostic behavior without changing language semantics, public
interfaces, diagnostic meanings, ABI, or compiler architecture.

## Verification

```bash
make -C l1 test-stage1 TESTS="expr_types_test"
make -C l1 test-all
```

Results:

- The focused expression-type test passed.
- All 47 Stage 1 tests passed.
- All 36 default trace tests passed.
- Environment stackability and all four L1 example checks passed.
