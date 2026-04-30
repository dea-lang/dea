# Feature Plan

## Backport string concatenation operator from L1

- Date: 2026-04-30
- Status: Completed
- Title: Backport string concatenation operator from L1
- Kind: Feature
- Severity: Medium
- Stage: L0 (Stage 1 Python + Stage 2 self-hosted)
- Subsystem: Typing / backend / C emission / tests / docs
- Modules:
  - `l0/compiler/stage1_py/l0_expr_types.py`
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage1_py/l0_c_emitter.py`
  - `l0/compiler/stage2_l0/src/expr_types.l0`
  - `l0/compiler/stage2_l0/src/backend.l0`
  - `l0/compiler/stage2_l0/src/c_emitter.l0`
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l0/compiler/stage2_l0/tests/c_emitter_test.l0`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_lib_test.l0`
  - `l0/compiler/stage2_l0/tests/fixtures/driver/string_concat_main.l0`
  - `l0/compiler/stage2_l0/tests/fixtures/typing/typing_string_concat_ok.l0`
  - `l0/compiler/stage2_l0/tests/fixtures/typing/typing_string_concat_err.l0`
  - `l0/compiler/stage1_py/tests/integration/test_string_operators.py`
  - `l0/docs/reference/design-decisions.md`
- Test modules:
  - `l0/compiler/stage1_py/tests/integration/test_string_operators.py`
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l0/compiler/stage2_l0/tests/c_emitter_test.l0`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/work/plans/features/closed/2026-04-22-string-concatenation-operator-noref.md`
  - `l0/work/plans/features/closed/2026-04-20-string-equality-and-relational-operators-noref.md`
- Repro: `make -C l0 test-stage1 && make -C l0 test-stage2`

## Summary

L0 already shipped the shared runtime helper `rt_string_concat`, including traced caller-location reporting through the
macro wrapper, but neither compiler accepted top-level `string + string`. This change ports the L1 operator surface into
both L0 stages so typing, C lowering, runtime behavior, and docs all agree on one narrow rule:
`string + string -> string`.

## Completion Notes

1. Stage 1 Python `_infer_binary` now accepts `string + string` before the integer arithmetic branch and returns
   `string`.
2. Stage 1 Python `_emit_binary_op` now routes string `+` through `emit_string_concat_call`, reusing the existing ARC
   temp materialization logic used by other string operators.
3. Stage 2 `etc_infer_binary` now accepts `string + string` before the integer arithmetic branch and returns a builtin
   `string`.
4. Stage 2 `be_emit_binary_op` now dispatches string `+` through `cem_emit_string_concat_call`, preserving the current
   `rt_string_concat(...)` call shape so traced code generation still picks up the runtime macro wrapper automatically.
5. Regression coverage now includes Stage 1 codegen/runtime/type-error cases, Stage 2 typing fixtures, backend/emitter
   assertions, and a `--run --keep-c` concat fixture.
6. `l0/docs/reference/design-decisions.md` now records concatenation as shipped string-operator behavior with a fresh
   owned result and no operand consumption.

## Defaults Chosen

1. Only `string + string` is supported.
2. Mixed operands still use the existing arithmetic mismatch diagnostic path (`TYP-0170`); no new diagnostic code was
   introduced.
3. The result is a fresh owned `string` with ordinary ARC cleanup behavior.
4. Neither operand is mutated or consumed.
5. No runtime/header change is part of this feature because the helper already existed in shared L0 runtime code.

## Non-Goals

1. String coercions from non-string operands.
2. Augmented assignment such as `+=`.
3. Any change to `case`-over-string, equality, or relational operator behavior.
4. Any broader string builder or performance redesign.

## Verification

1. `make -C l0 test-stage1`
2. `make -C l0 test-stage2`
3. `make -C l0 test-all`
