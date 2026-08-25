# Bug Fix Plan

## Preserve stray `else` boundaries during L1 Stage 1 `case` recovery

- Date: 2026-08-25
- Status: Completed
- Title: Port the L0 case-arm stray-else recovery-boundary fix to L1 Stage 1
- Kind: Bug Fix
- Severity: Medium
- Stage: 1
- Subsystem: Parser recovery / diagnostic parity
- Modules:
  - `l1/compiler/stage1_l0/src/parser/stmt.l0`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
- Roadmap: [l1/docs/roadmap.md](../../../../docs/roadmap.md)
- Related:
  - [docs/decisions/0013-compiler-diagnostic-collection-parser-recovery-and-phase-barriers.md](../../../../../docs/decisions/0013-compiler-diagnostic-collection-parser-recovery-and-phase-barriers.md)
  - [docs/decisions/0007-case-default-arm-wildcard.md](../../../../../docs/decisions/0007-case-default-arm-wildcard.md)
  - [l0/work/plans/features/closed/2026-06-08-case-else-removal-l0-phase2-noref.md](../../../../../l0/work/plans/features/closed/2026-06-08-case-else-removal-l0-phase2-noref.md)
  - [l1/work/plans/features/closed/2026-06-08-case-else-removal-l1-phase2-noref.md](../../features/closed/2026-06-08-case-else-removal-l1-phase2-noref.md)
- Repro: Parse `case (1) { _ => return 0; 1 => return 1; else return 2; }` and inspect the L1 Stage 1 diagnostics.

## Summary

L1 Stage 1 rejects `else` as a `case` default arm, but its invalid-arm synchronizer does not preserve `TT_ELSE` as a
possible recovery boundary. If an earlier malformed or forbidden arm enters `ps_sync_case_invalid_arm`, recovery can
consume a later stray `else` and then misinterpret tokens from its body as a new arm. The dedicated `PAR-0123`
diagnostic can be lost and replaced by misleading parser or top-level cascades.

L0 Stage 1 and Stage 2 already retain `ELSE` only as a recovery boundary while continuing to reject it as syntax. L1
Stage 1 should mechanically port that settled behavior.

## Current State

`ps_parse_case_stmt` in `l1/compiler/stage1_l0/src/parser/stmt.l0` detects `TT_ELSE`, emits `PAR-0123`, synchronizes the
invalid arm, and continues parsing. However, `ps_at_case_arm_start` recognizes wildcard, literal, real, identifier, and
boolean arm starts but omits `TT_ELSE`.

After an earlier invalid arm sets `boundary_ready`, `ps_sync_case_invalid_arm` therefore continues through a following
`else` instead of returning control to the `case` loop. The loop cannot emit the dedicated unmatched-`else` diagnostic,
and recovery may escape the intended arm or `case` boundary.

The corresponding L0 recovery tests are in
[l0/compiler/stage1_py/tests/parser/test_parser_recovery.py](../../../../../l0/compiler/stage1_py/tests/parser/test_parser_recovery.py)
and [l0/compiler/stage2_l0/tests/parser_test.l0](../../../../../l0/compiler/stage2_l0/tests/parser_test.l0).

## Root Cause

The recovery-boundary helper models only tokens accepted as valid arm starts. It must also include rejected tokens that
the enclosing `case` loop handles with a dedicated diagnostic. Without `TT_ELSE`, the synchronizer consumes the token
before that dedicated branch can observe it.

## Scope of This Fix

1. Add `TT_ELSE` to `ps_at_case_arm_start` in L1 Stage 1.
2. Document in the helper that `else` is retained only as a synchronization boundary so the enclosing loop can emit
   `PAR-0123`.
3. Keep `else` rejected as a `case` default arm; `_ =>` remains the only accepted default spelling.
4. Add L1 parser regression tests for an invalid arm followed by one stray `else` arm and for an invalid arm followed by
   multiple stray `else` arms.
5. Mechanically port the corresponding L0 assertions where the L1 parser-test helpers permit it, adapting only for L1's
   existing parser-test API and expanded case-literal surface.
6. Reuse existing diagnostics. This fix introduces no diagnostic code, severity, or catalog-meaning change, so no code
   reservation is needed.

## Test Scenarios

1. A forbidden value arm after `_ =>` followed by one stray `else` reports the existing invalid-after-default diagnostic
   and exactly one `PAR-0123`.
2. The same setup followed by two stray `else` arms reports exactly two `PAR-0123` diagnostics, one for each token.
3. Both cases remain within the enclosing `case` and do not emit recovery cascades such as `PAR-0235`, `PAR-0100`,
   `PAR-0225`, or `PAR-0020`.
4. A direct stray `else` remains rejected, preserving the wildcard-only default grammar rather than becoming an accepted
   arm.
5. Existing valid `_ =>` defaults and ordinary value-arm parsing remain unchanged.

## Approach

### 1. Port the recovery boundary

Add `ps_check(self, ord(TT_ELSE))` to `ps_at_case_arm_start`, matching the L0 Stage 2 helper. Do not add `TT_ELSE` to
the accepted-arm grammar or bypass the existing `PAR-0123` branch in `ps_parse_case_stmt`.

### 2. Port focused parser regressions

Use the L0 recovery source shape as the oracle: establish a wildcard default, trigger recovery with a later forbidden
value arm, and place one or more stray `else` arms after it. Assert exact diagnostic counts and the absence of generic
or top-level cascades with the existing L1 parser-test helpers.

### 3. Validate normal and traced parsing

Run the focused L1 parser executable normally and through the ARC/memory trace runner. Because
`l1/compiler/stage1_l0/tests/parser_test.l0` is a trace-eligible top-level test, finish with the full L1 aggregate.

## Non-Goals

- Reintroducing `else` as a `case` default arm or changing the wildcard-only grammar.
- Changing L0 Stage 1 or Stage 2; their behavior is the mechanical reference for this port.
- Redesigning general statement or case-arm synchronization beyond the missing `TT_ELSE` boundary.
- Adding, reassigning, or rewording diagnostic codes.
- Changing semantic analysis, backend lowering, or accepted-program behavior.

## Verification Criteria

Run from the repository root:

```bash
make -C l1 test-stage1 TESTS="parser_test"
make -C l1 test-stage1-trace TESTS="parser_test"
make -C l1 test-all
```

The focused normal and trace runs must pass with exact `PAR-0123` counts for the new cases and no `PAR-0235`,
`PAR-0100`, `PAR-0225`, or `PAR-0020` cascades. The full L1 aggregate must remain green.

## ADR Impact

- Decision: Preserve rejected keyword tokens as structural parser-recovery boundaries when the enclosing parser owns a
  dedicated diagnostic for them.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0013-compiler-diagnostic-collection-parser-recovery-and-phase-barriers.md`
  - Rationale: ADR-0013 requires cross-stage recovery-boundary and diagnostic-code parity while permitting different
    internal parser representations.
- Decision: Keep `_ =>` as the sole accepted `case` default arm while treating `else` only as rejected recovery input.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0007-case-default-arm-wildcard.md`
  - Rationale: ADR-0007 records the completed wildcard-only grammar and requires unmatched `else` to remain `PAR-0123`
    rather than accepted syntax.

## Resolution

- Added `TT_ELSE` to the L1 Stage 1 `case` arm synchronization-boundary helper without admitting it to the accepted-arm
  grammar.
- Documented that the rejected token is preserved so the enclosing `case` loop can emit the dedicated `PAR-0123`
  diagnostic.
- Added focused one- and multiple-`else` recovery regressions with exact diagnostic counts and lines plus assertions
  against generic, statement, function-body, and top-level cascades.
- Strengthened the direct stray-`else` regressions for arrowless and arrow spellings while keeping `_ =>` as the only
  accepted default arm.
- Independent read-only review found no parser-logic or regression-test defect; its lifecycle closure finding was
  resolved in the roadmap and covered ADRs.

## Verification

- `make -C l1 test-stage1 TESTS="parser_test"`: passed 1/1.
- `make -C l1 test-stage1-trace TESTS="parser_test"`: passed 1/1.
- `make -C l1 clean test-all`: passed 68/68 normal Stage 1 tests, environment stackability, 4/4 examples, and 44/44
  dedicated trace tests.
- `python3 scripts/check_adr_impact.py --all-active`: passed before closure.
