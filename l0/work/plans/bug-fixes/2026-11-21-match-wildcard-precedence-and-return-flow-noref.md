# Bug Fix Plan

## Align match wildcard reachability and dispatch

- Date: 2026-11-27
- Status: Draft
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
- Related:
  - [work/plans/bug-fixes/2026-11-27-shared-wildcard-fallbacks-noref.md](../../../../work/plans/bug-fixes/2026-11-27-shared-wildcard-fallbacks-noref.md)
  - [l0/docs/reference/grammar.md](../../../../l0/docs/reference/grammar.md)
  - [l0/docs/decisions/0004-enum-tagged-union-model.md](../../../../l0/docs/decisions/0004-enum-tagged-union-model.md)
- Repro: Use the two-variant `choose` below. Check it, then add `return 9;` after the match and run it once for each
  variant.

## Summary

Both stages report `TYP-0010` for the function below. With a trailing `return 9;`, the executable in each stage picks
the named arm for both variants. The native Stage 2 control checked Red and Blue independently and observed 7 and 8. Its
flow checker counts variants before the wildcard, while its generated C switch uses the wildcard as the default. The
existing wildcard-first warning test passes despite this disagreement.

```l0
enum Color { Red; Blue; }

func choose(c: Color) -> int {
    match (c) {
        _ => { }
        Red => { return 7; }
        Blue => { return 8; }
    }
}
```

## Accepted decision and L0 work

A single `_ =>` is a fallback anywhere in enum `match` and scalar `case`. Matching explicit arms win, and the scrutinee
and selected body each execute once. Last is the usual style. In the example, `choose` must compile without a trailing
return, warn once with `TYP-0105`, and return 7 for Red and 8 for Blue. The shared plan owns the acceptance matrix for
both L0 stages, L1, L2 and editors.

1. In Stage 1, replace coverage counted before the wildcard with the complete set of successfully validated variants.
   Port to Stage 2. Check ordinary errors inside a redundant wildcard but exclude the arm from return, fallthrough, and
   ownership/liveness joins. Invalid or wrong-owner variants and malformed payloads cannot supply coverage.
2. In both parsers, accept scalar value arms after the single wildcard. Retire `PAR-0234` and update the Stage 1
   registry, trigger matrix and the Stage 2 parity fixtures. Replace the now-legal recovery example with a malformed arm
   and preserve checks for diagnostic multiplicity, source spans and recovery at the next arm and statement. Preserve
   duplicate-value/default errors and rejection of the old `else` spelling.
3. Inspect both emitters before editing. Test enum switch dispatch and integer and string case dispatch for all three
   positions, a side-effecting scrutinee and one observable arm effect. Preserve L0 block bodies for match arms, literal
   case values, and existing no-fallback behavior.

## Related diagnostic observation

Stage 1 listed the same set of missing variants in different orders under different Python hash seeds. Stage 2 reports
them in declaration order. Keep wildcard precedence assertions independent of Stage 1 display order and retain the Stage
2 declaration-order control.

## Verification

From `l0/`, run the Stage 1 pytest modules above, then the Stage 2 parser, checker, backend, diagnostic parity and
execution suites named in the shared plan. Run L0 fixtures through both launchers. Record results separately for each
stage in the shared plan, including the warning count and Red, Blue and fallback outcomes. Verification is pending.

## ADR Impact

- Decision: Apply the shared position-independent fallback rule to enum match and scalar case in both L0 stages.
  - Scope: Dea-wide
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0007-case-default-arm-wildcard.md`
  - Rationale: The shared plan owns the ADR amendment. This plan retains L0-specific reproduction and validation
    evidence.
