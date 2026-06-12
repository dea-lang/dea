# Bug Fix Plan

## L1 Stage 1 cast and diagnostic parity

- Date: 2026-04-03
- Status: Implemented
- Title: Restore L1 Stage 1 cast validation and mismatch diagnostic parity
- Kind: Bug Fix
- Severity: High
- Stage: 1
- Subsystem: Type Checker
- Modules: `compiler/stage1_l0/src/expr_types.l0`, `compiler/stage1_l0/tests/expr_types_test.l0`,
  `compiler/stage1_l0/tests/fixtures/typing/typing_err.l1`,
  `compiler/stage1_l0/tests/fixtures/typing/typing_cast_ok.l1`,
  `compiler/stage1_l0/tests/fixtures/typing/typing_cast_err.l1`,
  `compiler/stage1_l0/tests/fixtures/typing/typing_cast_int_to_byte_overflow.l1`,
  `compiler/stage1_l0/tests/fixtures/typing/typing_cast_null_unwrap_err.l1`,
  `compiler/stage1_l0/tests/fixtures/typing/typing_nullable_assignment.l1`
- Test modules: `compiler/stage1_l0/tests/expr_types_test.l0`
- Repro: `make test-stage1 TESTS="expr_types_test"`

## Summary

This work applied the same two upstream Stage 2 parity fixes from the L0 Stage 2 explicit-cast legality fix and the L0
Stage 2 mismatch-diagnostic split to the L1 Stage 1 checker.

- `EX_CAST` now validates explicit cast legality instead of blindly returning the resolved target type
- invalid explicit casts now report `TYP-0230`
- compile-time `int -> byte` overflow now reports `TYP-0700`
- compile-time-null `T*? -> T*` unwrap now reports `TYP-0701`
- annotated `let` initializer mismatches now report `TYP-0310`
- assignment-statement mismatches now report `TYP-0311`
- the Stage 1 fixture suite now covers cast success, cast failure, overflow, nullable-pointer null unwrap, and
  assignment-vs-cast nullability behavior

## Root Cause

The L1 Stage 1 checker had been seeded from the earlier L0 Stage 2 implementation and retained the old checker behavior:

- `EX_CAST` resolves the target type, infers the operand type, and returns the target without legality checks
- `ST_LET` and `ST_ASSIGN` still emit the old Stage 2-local mismatch codes

That structure predated both the cast-specific validation added in the L0 Stage 2 explicit-cast legality fix and the
mismatch-code remap added in the L0 Stage 2 mismatch-diagnostic split, so the L1 Stage 1 port was mostly mechanical.

## Scope of This Fix

1. Port the L0 Stage 2 explicit cast validation logic from the L0 Stage 2 explicit-cast legality fix into
   `l1/compiler/stage1_l0/src/expr_types.l0`.
2. Reuse the Stage 1-oracle diagnostic codes:
   - `TYP-0230` for invalid explicit casts
   - `TYP-0310` for annotated `let` initializer mismatches
   - `TYP-0311` for assignment-statement mismatches
   - `TYP-0700` for compile-time `int -> byte` overflow
   - `TYP-0701` for compile-time-null nullable-pointer unwrap
3. Port the L0 Stage 2 mismatch-diagnostic split into the same Stage 1 statement checker.
4. Add L1 Stage 1 fixture coverage for valid casts, invalid casts, overflow, null unwrap, nullable assignment-vs-cast
   behavior, and the `let` initializer versus assignment-statement code split.
5. Keep this plan limited to the upstream parity fixes above; do not fold in unrelated diagnostic-code cleanup.

## Approach

In `compiler/stage1_l0/src/expr_types.l0`:

- port the cast-specific helper logic already proven in L0 Stage 2 rather than inventing an L1-only rule set
- add an explicit cast legality helper that layers cast-only allowances on top of normal assignment rules
- preserve the compile-time constant `int -> byte` overflow check (`TYP-0700`)
- preserve the explicit null optional-pointer unwrap rejection (`TYP-0701`)
- update annotated `let` initializer mismatches to `TYP-0310`
- update assignment-statement mismatches to `TYP-0311`
- otherwise reject invalid explicit casts with `TYP-0230`

In `compiler/stage1_l0/tests/expr_types_test.l0` and new typing fixtures:

- mirror the L0 Stage 2 cast-parity fixtures under the L1 Stage 1 typing fixture tree
- mirror the L0 Stage 2 `typing_err` and `typing_nullable_assignment` parity cases that distinguish `TYP-0310` from
  `TYP-0311`
- add success coverage for `10 as byte`, `int* as void*`, and `int? as int`
- add failure coverage for invalid pointer casts, byte overflow, and compile-time-null pointer unwrap
- add nullable assignment coverage that proves plain initialization still rejects `T? -> T` while explicit cast allows
  it

## Tests

Implemented fixture-backed checks for:

01. `1 as int*` -> `TYP-0230`
02. `1 as void*` -> `TYP-0230`
03. `null as int*` -> `TYP-0230`
04. `null as void*` -> `TYP-0230`
05. `300 as byte` and `(-1) as byte` -> `TYP-0700`
06. `(null as int*?) as int*` -> `TYP-0701`
07. `let y: int? = x` where `x: int` remains accepted
08. `let y: int = x` where `x: int?` remains rejected as a plain initialization mismatch
09. `return x as int` where `x: int?` remains accepted
10. annotated `let` initializer mismatch reports `TYP-0310`
11. assignment statement mismatch reports `TYP-0311`

## Verification

```bash
make test-stage1 TESTS="expr_types_test"
make test-stage1
```

Results:

- `make test-stage1 TESTS="expr_types_test"` passed
- `make test-stage1` passed

## Related Work

- L0 reference fix: `l0/work/plans/bug-fixes/closed/2026-04-03-stage2-pointer-cast-parity-noref.md`
- L0 follow-up diagnostic split fix:
  `l0/work/plans/bug-fixes/closed/2026-04-03-stage2-0310-0311-diagnostic-parity-noref.md`

## Assumptions

- L0 Stage 2 is now the most relevant implementation template because it already carries both desired fixes.
- Python Stage 1 remains the behavioral oracle for cast legality and diagnostic-code meaning.
- L1 Stage 1 should stay structurally close to L0 Stage 2 where the code paths are still homologous.
