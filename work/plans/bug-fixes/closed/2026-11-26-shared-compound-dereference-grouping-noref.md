# Bug Fix Plan

## Group the full pointer operand in generated C dereferences

- Date: 2026-11-26
- Status: Completed
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
  - L0 Stage 1: Verified locally
  - L0 Stage 2: Verified locally
  - L1 canonical compiler: Verified locally
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
  - `l0/compiler/stage1_py/tests/backend/test_codegen_lvalue_caching.py`
  - `l0/compiler/stage2_l0/tests/c_emitter_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_codegen_test.py`
  - `l1/compiler/tests/c_emitter_test.l0`
  - `l1/compiler/tests/backend_test.l0`
  - `l1/compiler/tests/deref_lvalue_test.py`
- Related:
  - [l0/docs/reference/c-backend-design.md](../../../../l0/docs/reference/c-backend-design.md)
  - [l1/docs/reference/c-backend-design.md](../../../../l1/docs/reference/c-backend-design.md)
- Repro: Call `cem_emit_deref_lvalue("take_a ? a : b")` and use its result with an integer condition and two `int *`
  operands in a C99 function.

## Summary

L0 Stage 1 uses `CValues.emit_deref_lvalue`. L0 Stage 2 and L1 use `cem_emit_deref_lvalue`. All three previously emitted
`(*take_a ? a : b)` for a conditional pointer. C applied unary `*` to the integer condition and Clang rejected the
assignments.

All three helpers now emit `(*(take_a ? a : b))`. Grouping both the operand and the resulting lvalue lets the caller
assign through the selected pointer. Checked dereference and index callers already pass a grouped runtime-check
expression. Lowering still selects the access mode and evaluates side-effectful operands once.

## ADR Impact

- Decision: Preserve C expression precedence for a pointer operand passed to the dereference emitter.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: Parenthesizing the operand fulfills the existing lvalue contract using ordinary C syntax.

## Verification by target

Apple Clang 17 compiled all three targets' fixtures on macOS. The shared C99 fixture takes the actual expression
returned by each emitter. Starting from `(left, right) = (1, 2)`, the true branch writes `11` and checks `(11, 2)`. The
false branch writes `22` and checks `(11, 22)`. A second shared program reads `3` through an allocated pointer, writes
`7`, reads it back and drops the allocation.

- L0 Stage 1 passed all 70 tests in the three pytest modules listed above, including the C99 fixture, checked native
  control and existing single-evaluation tests.
- L0 Stage 2 passed `c_emitter_test` and `l0c_codegen_test`, including both native fixtures and all eight generated-C
  goldens.
- L1 passed `make test-compiler TESTS="c_emitter_test backend_test deref_lvalue_test"`, including checked pointer
  indexing, field stores and both native fixtures.
