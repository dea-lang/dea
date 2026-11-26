# Bug Fix Plan

## Group the full pointer operand in generated C dereferences

- Date: 2026-11-26
- Status: Draft
- Title: Group the full pointer operand in generated C dereferences
- Kind: Bug Fix
- Scope: Shared
- Severity: Low
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 canonical compiler
- Origin: Establish the helper contract and C99 regression in L0 Stage 1.
- Porting rule: Apply the same operand grouping and two-branch write test in L0 Stage 2, then in L1.
- Target status:
  - L0 Stage 1: Pending
  - L0 Stage 2: Pending
  - L1 canonical compiler: Pending
- Subsystem: C expression emission for pointer lvalues
- Modules:
  - `l0/compiler/stage1_py/l0_c_values.py`
  - `l0/compiler/stage2_l0/src/c_emitter/values.l0`
  - `l1/compiler/src/c_emitter/expr.l0`
  - `l1/compiler/src/backend/expr.l0`
  - `l1/compiler/src/backend/lower.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/c_emitter/test_c_emitter_runtime_contracts.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage2_l0/tests/c_emitter_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_codegen_test.py`
  - `l1/compiler/tests/c_emitter_test.l0`
  - `l1/compiler/tests/backend_test.l0`
- Related:
  - [l0/docs/reference/c-backend-design.md](../../../l0/docs/reference/c-backend-design.md)
  - [l1/docs/reference/c-backend-design.md](../../../l1/docs/reference/c-backend-design.md)
- Repro: Call `cem_emit_deref_lvalue("take_a ? a : b")` and use its result with an integer condition and two `int *`
  operands in a C99 function.

## Summary

L0 Stage 1 uses `CValues.emit_deref_lvalue`. L0 Stage 2 and L1 use `cem_emit_deref_lvalue`. All three produce the same C
expression for this input.

The helper returns `(*take_a ? a : b)`. C applies unary `*` to the integer condition. Clang rejected the translation
unit, while `(*(take_a ? a : b))` compiled and selected the right integer in both branches. Existing checked-pointer
callers supply a grouped operand. The reproduced failure is at the helper interface.

## ADR Impact

- Decision: Preserve C expression precedence for a pointer operand passed to the dereference emitter.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: Parenthesizing the operand fulfills the existing lvalue contract using ordinary C syntax.

## Fix and regression criteria

1. Group the complete operand before applying unary dereference in the helper. Keep pointer checking, access mode and
   single evaluation at their existing lowering sites.
2. Extend `c_emitter_test` to assert how the actual helper renders a conditional pointer operand. Feed that output to a
   small host C fixture. Assign through the resulting lvalue with each condition, checking both integers after each
   write. This exercises precedence and writability.
3. Exercise the same two writes using the Stage 1 Python helper's actual output. Compile and execute an ordinary checked
   pointer read and write through both L0 stages and L1 as a production-path control. Inspect the existing pointer-index
   and dereference callers for grouping assumptions.

## Verification by target

From `l0/`, run the two listed Stage 1 pytest modules with `../.venv/bin/python -m pytest -q`. Run
`make test-stage2 TESTS="c_emitter_test l0c_codegen_test"` and compile and execute the host C fixture using each L0
stage's output. Record both integer values after each write.

From `l1/`, run `make test-compiler TESTS="c_emitter_test backend_test"` and compile and run the host C fixture with the
selected C99 compiler. Record the compiler and both branch results.
