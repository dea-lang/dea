# Bug Fix Plan

## Group the full pointer operand in generated C dereferences

- Date: 2026-11-21
- Status: Draft
- Title: Group the full pointer operand in generated C dereferences
- Kind: Bug Fix
- Severity: Low
- Subsystem: C expression emission for pointer lvalues
- Modules:
  - `l1/compiler/src/c_emitter/expr.l0`
  - `l1/compiler/src/backend/expr.l0`
  - `l1/compiler/src/backend/lower.l0`
- Test modules:
  - `l1/compiler/tests/c_emitter_test.l0`
  - `l1/compiler/tests/backend_test.l0`
- Related:
  - [l1/docs/reference/c-backend-design.md][backend]
  - [l0/work/plans/bug-fixes/2026-11-21-stage1-c-type-names-and-dereference-emission-noref.md][l0-emission]
- Repro: Call `cem_emit_deref_lvalue("take_a ? a : b")` and use its result with an integer condition and two `int *`
  operands in a C99 function.

## Summary

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
3. Compile and execute an ordinary L1 checked pointer read and write as a production-path control. Inspect the existing
   pointer-index and dereference callers for grouping assumptions.

From `l1/`, run `make test-compiler TESTS="c_emitter_test backend_test"` and compile and run the host C fixture with the
selected C99 compiler. Record the compiler and both branch results.

[backend]: ../../../docs/reference/c-backend-design.md
[l0-emission]: ../../../../l0/work/plans/bug-fixes/2026-11-21-stage1-c-type-names-and-dereference-emission-noref.md
