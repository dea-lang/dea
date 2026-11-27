# Bug Fix Plan

## Align match wildcard reachability and dispatch

- Date: 2026-11-27
- Status: Completed
- Title: Align match wildcard reachability and dispatch
- Kind: Bug Fix
- Severity: Medium
- Stage: Shared
- Subsystem: Enum match checking, return-flow analysis, and C switch lowering
- Modules:
  - `l0/compiler/stage1_py/l0_parser.py`
  - `l0/compiler/stage2_l0/src/parser/stmt.l0`
  - `l0/compiler/stage1_py/l0_check_patterns.py`
  - `l0/compiler/stage1_py/l0_check_flow.py`
  - `l0/compiler/stage1_py/l0_backend_lowering.py`
  - `l0/compiler/stage2_l0/src/expr_types/flow.l0`
  - `l0/compiler/stage2_l0/src/expr_types/patterns.l0`
  - `l0/compiler/stage2_l0/src/backend/lowering.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/parser/test_parser_recovery.py`
  - `l0/compiler/stage1_py/tests/integration/test_case_statement.py`
  - `l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`
  - `l0/compiler/stage1_py/tests/type_checker/test_control_flow.py`
  - `l0/compiler/stage2_l0/tests/parser_test.l0`
  - `l0/compiler/stage1_py/tests/type_checker/test_match_exhaustiveness.py`
  - `l0/compiler/stage1_py/tests/name_resolver/test_qualified_names.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l0/compiler/stage2_l0/tests/fixtures/typing/typing_match_validation_err.l0`
- Repro: Match a two-variant enum with a leading empty wildcard and returning arms for both variants.
- Related:
  [work/plans/bug-fixes/closed/2026-11-27-shared-wildcard-fallbacks-noref.md](../../../../../work/plans/bug-fixes/closed/2026-11-27-shared-wildcard-fallbacks-noref.md)

## Finding and fix

The checker treated the wildcard as reachable when a later arm covered the last missing variant. A function with an
empty wildcard followed by returning Red and Blue arms consequently reported `TYP-0010` even though dispatch selected
the named arms. The checker now computes coverage from all validated named patterns. It checks ordinary source errors in
a redundant body and excludes that body from return and ownership analysis. The emitter omits the redundant arm.

Scalar `case` accepts explicit arms on either side of the fallback. Duplicate defaults, repeated values, and unmatched
`else` retain their diagnostics. String dispatch emits an unconditional block for a lone fallback.

Stage 1 may list missing variants in Python hash order. Stage 2 retains its declaration-order diagnostic.

## Verification

Both L0 stages passed the focused parser, checker, backend, diagnostic and execution regressions on macOS Intel. The
shared plan records the commands, warning counts, runtime expectations and deferred L2 verification.

## ADR Impact

- Decision: Apply the shared position-independent fallback rule to enum match and scalar case in both L0 stages.
  - Scope: Dea-wide
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0007-case-default-arm-wildcard.md`
  - Rationale: The shared plan owns the ADR amendment. This plan retains L0-specific reproduction and validation
    evidence.
