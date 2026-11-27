# Bug Fix Plan

## Make enum match flow and execution agree on wildcard precedence

- Date: 2026-11-27
- Status: Draft
- Title: Make enum match flow and execution agree on wildcard precedence
- Kind: Bug Fix
- Severity: Medium
- Subsystem: Enum pattern coverage, control flow, and switch generation
- Modules:
  - `l1/compiler/src/parser/stmt.l0`
  - `l1/compiler/src/expr_types/stmt.l0`
  - `l1/compiler/src/expr_types/patterns.l0`
  - `l1/compiler/src/backend/lower.l0`
- Test modules:
  - `l1/compiler/tests/parser_test.l0`
  - `l1/compiler/tests/diagnostic_code_parity_test.py`
  - `l1/compiler/tests/diagnostic_message_parity_test.py`
  - `l1/compiler/tests/expr_types_test.l0`
  - `l1/compiler/tests/backend_test.l0`
  - `l1/compiler/tests/l1c_build_run_multi_cu_test.py`
- Related:
  - [work/plans/bug-fixes/2026-11-27-shared-wildcard-fallbacks-noref.md][shared-fallbacks]
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
executable returns 7 for Red and 8 for Blue because the C switch sends only unmatched tags to its default. Under the
accepted rule the original function must compile and warn once at the redundant wildcard. Red must return 7 and Blue 8
without adding a return after the match.

## Accepted decision and L1 work

One `_ =>` fallback can appear anywhere in enum `match` and scalar `case`. Evaluate the scrutinee once and run the
matching explicit arm, or the fallback when every explicit arm misses. A reachable wildcard in first or middle position
is as warning-free as one written last. The shared plan owns the decision and cross-compiler acceptance matrix.

1. Compute `TYP-0105` from all successfully validated named arms. Keep unknown or wrong-owner variants and invalid
   payload patterns out of coverage. Check ordinary errors in a redundant wildcard while excluding its flow and
   ownership effects. Cover first, middle and last positions with and without Green, an empty fallback, missing return,
   duplicate wildcards and a pointer used after a match.
2. Allow value arms after a scalar wildcard in the L1 parser, including L1's existing scalar constant arm forms. Retire
   `PAR-0234` in the L1 diagnostic fixture inventory. Keep `PAR-0236`, `TYP-0108`, unmatched-`else` diagnostics, and
   source-span and synchronization checks for genuinely malformed arms. Keep statement bodies and current semantics for
   statements without a fallback.
3. Inspect the existing switch and comparison-chain lowering before changing either. Run L1-owned `.l1` programs through
   the canonical `l1c`. Test explicit values after the fallback, misses, and exactly one evaluation and arm effect for
   integer and string cases.

## ADR Impact

- Decision: Apply the shared position-independent fallback rule to enum match and scalar case in canonical L1.
  - Scope: Dea-wide
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0007-case-default-arm-wildcard.md`
  - Rationale: The shared plan owns the ADR amendment. This plan retains L1-specific reproduction and validation
    evidence.

## Verification

From `l1/`, run the focused parser, checker, backend, diagnostic and executable tests listed in the shared plan. Record
the command, host, diagnostic counts, outputs for each input, and outstanding coverage under the L1 target. Verification
is pending. The L2 target has its own bootstrap and execution checks in the shared plan.

[coverage]: ../../../../work/plans/bug-fixes/closed/2026-08-23-shared-match-validation-regressions-noref.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[grammar]: ../../../docs/reference/grammar.md
[l0-match]: ../../../../l0/work/plans/bug-fixes/2026-11-21-match-wildcard-precedence-and-return-flow-noref.md
[shared-fallbacks]: ../../../../work/plans/bug-fixes/2026-11-27-shared-wildcard-fallbacks-noref.md
