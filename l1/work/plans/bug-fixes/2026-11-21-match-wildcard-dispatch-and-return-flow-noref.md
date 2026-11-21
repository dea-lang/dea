# Bug Fix Plan

## Make enum match flow and execution agree on wildcard precedence

- Date: 2026-11-21
- Status: Draft
- Title: Make enum match flow and execution agree on wildcard precedence
- Kind: Bug Fix
- Severity: Medium
- Subsystem: Enum pattern coverage, control flow, and switch generation
- Modules:
  - `l1/compiler/src/expr_types/stmt.l0`
  - `l1/compiler/src/expr_types/patterns.l0`
  - `l1/compiler/src/backend/lower.l0`
- Test modules:
  - `l1/compiler/tests/expr_types_test.l0`
  - `l1/compiler/tests/backend_test.l0`
  - `l1/compiler/tests/l1c_build_run_multi_cu_test.py`
- Related:
  - [l1/docs/reference/grammar.md][grammar]
  - [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]
  - [work/plans/bug-fixes/closed/2026-08-23-shared-match-validation-regressions-noref.md][coverage]
  - [l0/work/plans/bug-fixes/2026-11-21-match-wildcard-precedence-and-return-flow-noref.md][l0-match]
- Repro: Check the function below, then add `return 9;` after the match and run calls with both variants.

## Summary

```l1
enum Color { Red; Blue; }
func choose(c: Color) -> int {
    match (c) {
        _ => { }
        Red => { return 7; }
        Blue => { return 8; }
    }
}
```

The checker reports `TYP-0010` because it counts the wildcard body as reachable. With the trailing return, the
executable returns 7 for Red and 8 for Blue because the C switch sends only unmatched tags to its default. Placing the
wildcard last works around this disagreement. The choice applies to enum `match`; scalar `case` has its own rules.

## ADR Impact

- Decision: Which arms can an L1 enum match select when a wildcard precedes a named variant?
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: The alternatives change observable results or the validity of existing L1 programs. The language rule
    must be chosen before either the checker or the backend can serve as the reference.

## Decision and regression criteria

| Candidate rule        | Function as written                                              | With the trailing return                                                   |
| --------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Fallback anywhere     | Both named arms return. Accept, and flag the redundant wildcard. | Red returns 7 and Blue returns 8.                                          |
| First matching arm    | The wildcard wins for both values. Report `TYP-0010`.            | Both calls return 9.                                                       |
| Require wildcard last | Reject a non-final wildcard at its source location.              | Adding a return leaves the placement error. Moving `_` last gives 7 and 8. |

1. Settle the L1 rule and record it alongside the enum match grammar. Coordinate the decision with the open L0 question.
   Keep existing diagnostic meanings for missing variants (`TYP-0104`), a redundant wildcard (`TYP-0105`) and a missing
   return (`TYP-0010`). If the final-only grammar is chosen, provisionally use the nearby unused `PAR-0178` for wildcard
   placement. Recheck the live catalog and active reservations before assignment.
2. Apply the chosen rule to arm reachability, liveness joins, return checking, coverage diagnostics, and generated
   dispatch. Validate patterns before they contribute to coverage. The existing wildcard-first warning test encodes the
   earlier before-wildcard calculation and must be reconciled with the decision.
3. Pair a diagnostic test with an executable test that checks each variant independently. Exercise first, middle and
   last wildcard positions, full and partial named coverage, a returning and a falling-through wildcard, and an
   exhaustive named-only match. Check the warning location and preserve declaration order for missing variants. Under a
   final-only rule, include rejected placements and execute their legal reordered versions.

From `l1/`, run `make test-compiler TESTS="expr_types_test backend_test l1c_build_run_multi_cu_test"`. Include
`parser_test` for a grammar change. Require analysis and execution to predict the same result for each accepted input.

[coverage]: ../../../../work/plans/bug-fixes/closed/2026-08-23-shared-match-validation-regressions-noref.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[grammar]: ../../../docs/reference/grammar.md
[l0-match]: ../../../../l0/work/plans/bug-fixes/2026-11-21-match-wildcard-precedence-and-return-flow-noref.md
