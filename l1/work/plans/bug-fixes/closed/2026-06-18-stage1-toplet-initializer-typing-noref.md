# Bug Fix Plan

## Type-check L1 Stage 1 top-level `let` initializers before backend lowering

- Date: 2026-06-18
- Status: Completed
- Title: Type-check L1 Stage 1 top-level `let` initializers before backend lowering
- Kind: Bug Fix
- Severity: Medium
- Stage: 1
- Subsystem: Type checker / top-level initialization / C backend metadata
- Modules:
  - `compiler/stage1_l0/src/expr_types.l0`
  - `compiler/stage1_l0/src/backend.l0`
- Test modules:
  - `compiler/stage1_l0/tests/expr_types_test.l0`
  - `compiler/stage1_l0/tests/l1c_stage1_toplet_test.py`
  - `compiler/stage1_l0/tests/fixtures/typing/typing_toplet_initializer_err.l1`
- Related:
  - `l1/work/plans/features/closed/2026-04-17-l1-let-non-constant-initializers-noref.md`
  - `l1/work/plans/features/closed/2026-04-18-l1-const-declarations-noref.md`
  - `l1/work/plans/features/closed/2026-05-19-stage1-slices-len-slice-intrinsics-noref.md`
- Repro: `make -C l1 test-stage1 TESTS="expr_types_test l1c_stage1_toplet_test.py"`

## Summary

L1 Stage 1 supported non-constant top-level `let` initializers, but expression type checking only walked function
bodies. That meant module-scope runtime initializers could reach backend lowering without the same contextual
initializer checks used for local annotated `let` declarations. Invalid top-level initializer expressions could
therefore miss diagnostics, and valid runtime initializers that used intrinsics could miss expression metadata needed by
backend lowering.

The fix makes module-scope `let` initializers part of expression type checking, reuses the local contextual initializer
path, and preserves existing diagnostics for invalid destination types and initializer operands.

## Root Cause

Signature resolution resolved top-level binding types and enforced top-level-only restrictions such as const-only static
initializers and slice escape rejection. It did not perform full expression typing for initializer expressions. The
backend later lowered deferred top-level initializers with `be_emit_owned_expr_with_expected_type`, which assumes that
expression type maps and intrinsic target maps have already been populated.

Local annotated `let` declarations already had the right contextual checking behavior, including array literal context,
bigint range checks, and `TYP-0050` rejection for `void` variables. The top-level path did not share that validation.

## Scope

1. Reuse one contextual initializer helper for local annotated `let` declarations and module-scope `let` declarations.
2. Type-check every resolved top-level `let` initializer before function-body expression checking in each module.
3. Record expression types and intrinsic target metadata for accepted top-level runtime initializers.
4. Preserve local `let` behavior, including declaration liveness and duplicate-name checks.
5. Reject top-level `let` bindings with builtin `void` type through existing `TYP-0050` before initializer inference.
6. Avoid cascade typing after invalid index operands so initializer diagnostics stay focused on the failing operand.

## Diagnostic Plan

No new diagnostic codes are required.

- Reuse `TYP-0310` for top-level initializer type mismatches.
- Reuse intrinsic operand diagnostics such as `TYP-0808` for top-level initializer expressions.
- Reuse `TYP-0050` for top-level `let` bindings whose resolved binding type is `void`.
- Keep the existing index diagnostics and suppress derived result typing after invalid index operands.

## Resolution

The expression checker now has `etc_check_initializer_expr`, shared by local annotated `let` declarations and the new
top-level initializer pass. The pass runs per module after signature and local-scope resolution have succeeded and
before function bodies are checked.

The implementation records contextual array and intrinsic metadata for top-level initializer expressions, reports
top-level initializer mismatches, rejects top-level `void` variables through `TYP-0050`, and avoids result typing after
invalid index operands. Runtime coverage now exercises top-level `len`, `sizeof`, `ord`, and `is` intrinsic initializers
through deferred module initialization.

## ADR Note

No ADR is required for this fix. The change enforces existing `let` typing and diagnostic policy for an implementation
path that previously skipped expression checking; it does not introduce a new language, ABI, ownership, or architecture
decision.

## Verification

```bash
make -C l1 test-stage1 TESTS="expr_types_test l1c_stage1_toplet_test.py"
make -C l1 test-stage1 TESTS="backend_test"
make -C l1 clean test-all
```

Results:

- `make -C l1 test-stage1 TESTS="expr_types_test l1c_stage1_toplet_test.py"` passed.
- `make -C l1 test-stage1 TESTS="backend_test"` passed.
- `make -C l1 clean test-all` passed.
