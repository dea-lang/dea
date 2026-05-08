# Bug Fix Plan

## Align L1 Stage 1 indexing diagnostics with the shared catalog

- Date: 2026-05-08
- Status: Implemented
- Title: Align L1 Stage 1 indexing and array-type diagnostic wording with the shared catalog
- Kind: Bug Fix
- Severity: Medium
- Stage: 1
- Subsystem: Parser / Type checker / diagnostic wording parity
- Modules:
  - `compiler/stage1_l0/src/parser/shared.l0`
  - `compiler/stage1_l0/src/expr_types.l0`
  - `compiler/stage1_l0/tests/parser_test.l0`
  - `compiler/stage1_l0/tests/expr_types_test.l0`
  - `compiler/stage1_l0/tests/diagnostic_message_parity_test.py`
  - `docs/roadmap.md`
- Test modules:
  - `compiler/stage1_l0/tests/parser_test.l0`
  - `compiler/stage1_l0/tests/expr_types_test.l0`
  - `compiler/stage1_l0/tests/diagnostic_message_parity_test.py`
- Related:
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/roadmap.md`
- Repro:
  `rg -n "PAR-9401|TYP-0211|TYP-0212" l1/compiler/stage1_l0/src/parser/shared.l0 l1/compiler/stage1_l0/src/expr_types.l0`

## Summary

L1 Stage 1 still emits stale wording for unsupported array-type syntax and indexing diagnostics:

- `PAR-9401` still suggests pointers and `[]` indexing as a substitute for arrays.
- `TYP-0211` still says `cannot index nullable type ...`.
- `TYP-0212` still says `cannot index into expression of type ...` without the shared `not yet supported` wording.

The shared diagnostic catalog now defines the intended wording for these codes, and L1 Stage 1 should match it for the
conditions it emits today.

## Scope

1. Update L1 Stage 1 parser wording for `PAR-9401` to `array types not yet supported`.
2. Update L1 Stage 1 type-checker wording for:
   - `TYP-0211`: `cannot index into a nullable expression; indexing is not yet supported`
   - `TYP-0212`: `cannot index into an expression; indexing is not yet supported`
3. Add or tighten Stage 1 tests so message text is asserted directly for reachable parser and typing cases.
4. Keep L1 pointer-indexing semantics unchanged in this plan. That separate parity bug remains out of scope here.

## Approach

### 1. Update emitted strings

Change the parser and type-checker emitters in `compiler/stage1_l0/src/parser/shared.l0` and
`compiler/stage1_l0/src/expr_types.l0` so the emitted diagnostic wording matches the shared catalog rather than the
older L1-local phrasing.

### 2. Lock the wording with tests

Add direct message assertions in:

- `compiler/stage1_l0/tests/parser_test.l0` for `PAR-9401`
- `compiler/stage1_l0/tests/expr_types_test.l0` for `TYP-0211` and `TYP-0212`

Update the L1 diagnostic-message parity harness if needed so it exercises the reachable L1 Stage 1 cases for these codes
without changing the separate pointer-indexing semantics.

## Non-Goals

1. Changing which expressions are indexable in L1.
2. Aligning L1 pointer-indexing semantics with L0.
3. Introducing new diagnostic codes.

## Verification Criteria

1. `parser_test.l0` asserts the exact `PAR-9401` message.
2. `expr_types_test.l0` asserts the exact `TYP-0211` and `TYP-0212` messages.
3. `compiler/stage1_l0/tests/diagnostic_message_parity_test.py` passes with reachable L1 cases.
4. `make test-stage1 TESTS="parser_test expr_types_test"` passes.

## Resolution

Implemented the wording alignment in the reachable L1 Stage 1 parser and type-checker paths:

- `compiler/stage1_l0/src/parser/shared.l0` now emits `PAR-9401` as `array types not yet supported`.
- `compiler/stage1_l0/src/expr_types.l0` now emits:
  - `TYP-0211`: `cannot index into a nullable expression; indexing is not yet supported`
  - `TYP-0212`: `cannot index into an expression; indexing is not yet supported`
- `compiler/stage1_l0/tests/parser_test.l0` now asserts the exact `PAR-9401` message text.
- `compiler/stage1_l0/tests/expr_types_test.l0` now asserts the exact `TYP-0211` and `TYP-0212` message text.
- `scripts/diagnostic_message_parity.py` now supports stage-specific expectations for these codes so the L1 parity test
  checks the reachable L1 wording rather than the L0-specific pointer-indexing case.

This plan intentionally did not change the separate L1 pointer-indexing semantic drift. L1 still accepts raw-pointer
indexing on non-null pointer bases, so the `TYP-0212` parity case in the shared message harness remains exercised
through the reachable non-pointer invalid-base path.

## Verification

```bash
make test-stage1 TESTS="parser_test expr_types_test"
../.venv/bin/python compiler/stage1_l0/tests/diagnostic_message_parity_test.py
```

Results:

- `make test-stage1 TESTS="parser_test expr_types_test"` passed.
- `../.venv/bin/python compiler/stage1_l0/tests/diagnostic_message_parity_test.py` passed.
