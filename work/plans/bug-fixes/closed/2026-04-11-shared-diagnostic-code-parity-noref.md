# Bug Fix Plan

## Restore native diagnostic-code parity for release

- Date: 2026-04-11
- Status: Closed
- Title: Restore native L0 Stage 2 and L1 Stage 1 diagnostic-code parity for Dea/L0 v1.0.0
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Stage 2
  - L1 Stage 1
- Origin: L0 Stage 2, using Python L0 Stage 1 as the canonical diagnostic-code oracle
- Porting rule: Fix the L0 Stage 2 native path first, then keep the homologous L1 Stage 1 path mechanically aligned
  except for intentional L1 front-end differences such as the `LEX-0060` exclusion
- Target status:
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Diagnostics / Lexer / Driver / Type checking / Test runners
- Modules: `scripts/diagnostic_parity.py`, `l0/compiler/stage2_l0/src/{driver,expr_types,lexer,type_resolve}.l0`,
  `l0/compiler/stage2_l0/src/util/strings.l0`, `l0/compiler/stage2_l0/tests/diagnostic_code_parity_test.py`,
  `l1/compiler/stage1_l0/src/{driver,expr_types,lexer,type_resolve}.l0`, `l1/compiler/stage1_l0/src/util/strings.l0`,
  `l1/compiler/stage1_l0/scripts/test_runner_common.py`, `l1/compiler/stage1_l0/tests/diagnostic_code_parity_test.py`
- Test modules: `l0/compiler/stage2_l0/tests/diagnostic_code_parity_test.py`,
  `l1/compiler/stage1_l0/tests/diagnostic_code_parity_test.py`
- Repro: compare every reachable Python L0 diagnostic trigger against native L0 Stage 2 and L1 Stage 1, excluding
  `LEX-0060` for L1 Stage 1

## Summary

A prior diagnostic-code parity pass closed many native implementation gaps against the Python L0 oracle, but the release
audit still found diagnostic-code drift in L0 Stage 2 and L1 Stage 1.

The remaining native gaps covered by this plan are:

- invalid UTF-8 should surface as `DRV-0040`
- oversized Unicode escapes should report `LEX-0054` instead of crashing
- local duplicate and shadowing diagnostics should report the `TYP-0020` through `TYP-0025` family
- expression name-resolution failures should preserve canonical `TYP-0151`, `TYP-0152`, `TYP-0154`, `TYP-0155`,
  `TYP-0158`, `TYP-0159`, `TYP-0180`, `TYP-0181`, and `TYP-0189`
- unary and binary operator mismatches should use `TYP-0160`, `TYP-0161`, `TYP-0162`, `TYP-0170`, `TYP-0171`, and
  `TYP-0172`
- L0 constructor diagnostics should use the canonical `TYP-0191`, `TYP-0313`, `TYP-0201`, and `TYP-0314` codes
- type-position failures in expression contexts should surface the canonical `TYP-0270`, `TYP-0271`, `TYP-0278`,
  `TYP-0279`, `TYP-0280`, and `TYP-0290` codes
- parity coverage should be executable from the normal L0 Stage 2 and L1 Stage 1 test runners

## Scope of This Fix

1. Add a shared diagnostic parity harness that imports the Python L0 Stage 1 oracle triggers.
2. Add L0 Stage 2 and L1 Stage 1 test entrypoints for the harness.
3. Extend the L1 Stage 1 normal test runner to discover Python tests.
4. Fix native diagnostic-code gaps where the error condition already exists but emits the wrong code.
5. Add narrow contextual diagnostics where native code previously emitted only lower-level signature diagnostics.
6. Preserve the intentional L1 Stage 1 exclusion for `LEX-0060`.

## Non-Goals

- Do not change the Python L0 Stage 1 oracle.
- Do not make local duplicate declaration diagnostics build-fatal across existing native compiler sources in this
  tranche.
- Do not refactor the parser or resolver beyond what is needed to surface the canonical codes.

## Approach

- Reuse Python Stage 1 diagnostic triggers as the single oracle input set.
- Run the native compiler for each reachable trigger and assert the expected code appears in diagnostics.
- Keep the harness stage-aware so L1 adds L1-only lexical/intrinsic checks and skips `LEX-0060`.
- Add native UTF-8 validation before parsing source text.
- Guard Unicode escape accumulation against integer overflow.
- Restore canonical expression/type diagnostic codes in the shared self-hosted checker paths.

## Tests

Verification checks passing:

```bash
make -C l0 install-dev-stage2
make -C l1 build-stage1
.venv/bin/python scripts/diagnostic_parity.py --stage l0 --compiler l0/build/dea/bin/l0c-stage2
.venv/bin/python scripts/diagnostic_parity.py --stage l1 --compiler l1/build/dea/bin/l1c-stage1
make -C l0 test-stage2 TESTS=diagnostic_code_parity_test.py
make -C l1 test-stage1 TESTS=diagnostic_code_parity_test.py
make -C l0 test-stage2 TESTS=expr_types_test
make -C l1 test-stage1 TESTS=expr_types_test
make -C l0 test-stage2-trace TESTS=expr_types_test
make -C l0 test-stage2
make -C l1 test-stage1
make -C l0 test-stage2-trace
make -C l0 triple-test
git diff --check
```

## Open Questions

- Whether `TYP-0020` should remain a native warning for compatibility with existing compiler sources or whether the
  sources should be cleaned up so the code can become fatal like the Python oracle.
- Whether contextual `TYP-027x` emissions should eventually replace the lower-level `SIG-*` diagnostics in expression
  contexts rather than being emitted alongside them.

## Current Outcome

- L0 Stage 2 diagnostic parity harness passes.
- L1 Stage 1 diagnostic parity harness passes with `LEX-0060` excluded.
- The normal L0 and L1 targeted parity test entrypoints pass.
- The focused L0 Stage 2 trace check for `expr_types_test` passes after fixing the `Type` ownership leak on map
  overwrite in expression/type tracking.
- Full L0 Stage 2, L1 Stage 1, L0 Stage 2 trace, and L0 triple-bootstrap gates pass.

## Related Work

- `work/plans/bug-fixes/closed/2026-04-10-shared-self-hosted-stage1-statement-parity-audit-noref.md`
- `work/plans/bug-fixes/closed/2026-04-10-shared-let-initializer-parity-noref.md`
- `work/plans/bug-fixes/closed/2026-04-10-shared-condition-diagnostic-code-parity-noref.md`
