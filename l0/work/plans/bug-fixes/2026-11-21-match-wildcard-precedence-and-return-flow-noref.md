# Bug Fix Plan

## Align match wildcard reachability and dispatch

- Date: 2026-11-21
- Status: Draft
- Title: Align match wildcard reachability and dispatch
- Kind: Bug Fix
- Severity: Medium
- Stage: Shared
- Subsystem: Enum match checking, return-flow analysis, and C switch lowering
- Modules:
  - `l0/compiler/stage1_py/l0_check_patterns.py`
  - `l0/compiler/stage1_py/l0_check_flow.py`
  - `l0/compiler/stage1_py/l0_backend_lowering.py`
  - `l0/compiler/stage2_l0/src/expr_types/flow.l0`
  - `l0/compiler/stage2_l0/src/expr_types/patterns.l0`
  - `l0/compiler/stage2_l0/src/backend/lowering.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/type_checker/test_match_exhaustiveness.py`
  - `l0/compiler/stage1_py/tests/name_resolver/test_qualified_names.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l0/compiler/stage2_l0/tests/fixtures/typing/typing_match_validation_err.l0`
- Related:
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

## Open language decision

The project maintainer must settle precedence before either stage changes its diagnostics or execution. Under
**source-order matching**, the example reaches the empty wildcard for both values, so `TYP-0010` is correct and the
version with the trailing return must yield 9 twice. Under **fallback matching**, both explicit arms win, the original
function returns on every path, and the results must be 7 and 8. Record the decision for L0, including whether and when
a redundant wildcard warns. The existing wildcard-first warning test and the C switch each describe only part of the
current behavior.

## Implementation and regression tests

1. Run the same source through each L0 stage, recording analysis diagnostics and the two executable results. Keep a
   fixture without the trailing return and a separately executable control with it. Give the wildcard a distinct
   observable result in the dispatch tests. In the native Stage 2 run, assert Red's result and Blue's result
   independently so swapping the arms cannot pass a summed-result assertion.
2. After the decision, make pattern coverage, fallthrough/liveness joins, return analysis, and emitted dispatch agree on
   reachable arms. Apply equivalent behavior in both L0 stages. Update the grammar/reference and the existing
   wildcard-first expectation with the chosen rule.
3. Cover wildcard-first, middle, and last positions with complete and partial named coverage. Exercise a returning
   wildcard and a falling-through wildcard. Include complete named-only and missing-variant controls. Check exact
   results per variant and the presence or absence of `TYP-0010`, `TYP-0104`, and `TYP-0105` independently. Invalid
   patterns must still be diagnosed and cannot supply coverage.

## Related diagnostic observation

The same non-exhaustive match listed its four missing variants in three different orders under three Python hash seeds.
Each message named the correct set. Stage 2 already iterates the enum declaration: for `A, B, C, D, E0` with only `A`
matched it reported `B, C, D, E0`. Preserve that order in the Stage 2 diagnostic regression. Keep the precedence
assertions independent of display order. If stable Stage 1 wording is adopted, test it separately across hash seeds.

## Verification

Run the listed Stage 1 pytest modules from `l0/`. Run `make test-stage2 TESTS="expr_types_test l0c_build_run_test"`
there and execute the dispatch fixture with each compiler. The proposed precedence rules reuse existing meanings from
[docs/specs/compiler/diagnostic-code-catalog.md](../../../../docs/specs/compiler/diagnostic-code-catalog.md). Resolve
the ADR disposition and document the selected rule before closing this plan.

## ADR Impact

- Decision: Does a wildcard win in source order or act as a fallback after all named enum variants?
  - Scope: L0
  - Disposition: Pending
  - ADR: None
  - Rationale: Both rules explain part of the current implementation. Choosing between them changes observable
    execution, warning reachability, and which functions pass return checking.
