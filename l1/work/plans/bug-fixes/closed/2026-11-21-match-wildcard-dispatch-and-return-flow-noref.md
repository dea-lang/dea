# Bug Fix Plan

## Make enum match flow and execution agree on wildcard precedence

- Date: 2026-11-27
- Status: Completed
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

## Verification

The canonical L1 compiler passed the focused parser, checker, backend, diagnostic and execution regressions on macOS
Intel. The shared plan records the commands, warning counts, runtime expectations and deferred L2 verification.

## ADR Impact

- Decision: Apply the shared position-independent fallback rule to enum match and scalar case in canonical L1.
  - Scope: Dea-wide
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0007-case-default-arm-wildcard.md`
  - Rationale: The shared plan owns the ADR amendment. This plan retains L1-specific reproduction and validation
    evidence.
