# Bug Fix Plan

## Keep invalid match patterns out of validated coverage

- Date: 2026-08-24
- Status: Completed
- Title: Reject nested qualified patterns and compute exhaustiveness from validated enum variants
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Stage 2
  - L1 Stage 1
- Origin: L0 Python Stage 1 remains the diagnostic oracle; settle one validated-pattern result in L0 Stage 2 and port it
  mechanically to L1 Stage 1.
- Porting rule: Keep pattern-path validation, canonical variant identity, exhaustiveness membership, and diagnostic
  codes identical across the self-hosted analyzers.
- Target status:
  - L0 Stage 2: Completed
  - L1 Stage 1: Completed
- Subsystem: Match typing / Qualified-name validation / Exhaustiveness analysis
- Modules:
  - `l0/compiler/stage1_py/l0_expr_types.py`
  - `l0/compiler/stage2_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/name_resolver/test_qualified_names.py`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
- Related:
  - `work/plans/bug-fixes/closed/2026-04-10-shared-match-pattern-parity-noref.md`
  - `work/plans/bug-fixes/closed/2026-04-10-shared-match-qualified-pattern-parity-noref.md`
  - `work/plans/bug-fixes/closed/2026-04-10-shared-match-exhaustiveness-return-path-parity-noref.md`
  - `work/plans/bug-fixes/closed/2026-04-10-shared-match-diagnostic-tail-parity-noref.md`
- Repro: Check a match containing `module::Enum::Variant` and a separate match whose arms are one valid variant plus one
  unknown name; the native analyzers accept the nested path and can count the invalid name toward exhaustiveness.

## Summary

The self-hosted match validator and exhaustiveness checker do not share one authoritative validated variant result.
Nested paths such as `module::Enum::Variant` can pass the module-qualified lookup even though Dea permits only
`module::symbol`. Separately, exhaustiveness collects every syntactic variant-pattern name, including patterns already
rejected as unknown, and considers coverage complete when the set size equals the enum's variant count.

This is a regression follow-up to the completed shared match-parity plans. Those plans remain closed; this plan restores
the stricter path-shape and validated-coverage invariants their outcomes intended to establish.

## ADR Impact

- Decision: Base match exhaustiveness only on canonical variants produced by successful pattern validation.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The fix enforces existing qualified-name grammar and exhaustiveness semantics without introducing a new
    matching construct or diagnostic policy.

## Current State and Root Cause

1. `etc_check_match_pattern()` validates `pattern.module_path` but can pass `pattern.name_qualifier` into symbol lookup
   without first applying the single `module::symbol` path rule.
2. The validator returns only `bool`; it does not return the canonical enum-variant identity that was validated.
3. `etc_check_match_exhaustiveness()` walks the syntax again and adds each `PT_VARIANT` name to `covered`, regardless of
   the validator result.
4. Coverage succeeds on set cardinality instead of proving every covered item is a defined variant of the scrutinee
   enum.
5. Python Stage 1 already rejects nested symbol paths with `TYP-0158` and uses defined-set equality for the demonstrated
   invalid-name case.

## Scope of This Fix

1. Apply the existing nested-symbol-path rejection to match patterns before module/variant lookup.
2. Make successful pattern validation yield or record a canonical variant identity owned by the scrutinee enum.
3. Bind payload variables and compute exhaustiveness only from successfully validated variants.
4. Determine explicit coverage through membership/equality with the enum definition, never cardinality alone.
5. Preserve wildcard behavior while ensuring invalid explicit patterns do not make a wildcard appear unreachable.
6. Add wrong-module, wrong-enum, nested-path, unknown-name, duplicate-name, and invalid-plus-missing regressions in both
   native suites.

## Diagnostics

No new codes are needed:

1. Reuse `TYP-0158` for nested symbol paths.
2. Reuse `TYP-0102` for unknown or wrong-owner variants.
3. Reuse `TYP-0104` for the variants still missing after invalid arms are excluded.
4. Preserve `TYP-0105` only when every defined variant is validly covered before `_`.

## Non-Goals

1. Reopening or rewriting the completed shared match plans.
2. Changing legal `module::Variant` syntax or enum ownership rules.
3. Adding new pattern forms.

## Verification

1. Add fixtures that require both the primary pattern error and the remaining non-exhaustive diagnostic.
2. Assert `module::Enum::Variant` reports `TYP-0158` in both native compilers.
3. Assert invalid patterns never suppress `TYP-0104` or trigger an incorrect `TYP-0105`.
4. Run focused expression-type and diagnostic-parity suites for L0 Stage 2 and L1 Stage 1, then root `make test`.

## Verification Criteria

1. Every covered variant is known to belong to the scrutinee enum.
2. Invalid arms remain type-checked enough for useful diagnostics but contribute no coverage or payload bindings.
3. Both native compilers match Python Stage 1 codes and source spans for the focused cases.

## Implementation Outcome

1. Python Stage 1 and both native expression checkers now validate each enum pattern once and retain its canonical
   scrutinee-variant identity for coverage and payload-binding decisions.
2. Nested `module::Enum::Variant` patterns report the shared `TYP-0158` wording before lookup, while unknown,
   wrong-module, and wrong-enum patterns remain `TYP-0102` errors.
3. Exhaustiveness and wildcard reachability are derived only from successfully validated variants and prove membership
   against the enum definition; invalid names and arity-invalid patterns cannot satisfy coverage.
4. `TYP-0105` is emitted only when a wildcard is present after every declared variant has already been validly covered.
   Explicit exhaustive matches without `_`, wildcard-first matches, and invalid arms before `_` do not warn.

## Verification Outcome

1. The Python qualified-name suite passed with 22 tests. L0 Stage 2 and L1 Stage 1 expression-type suites passed in
   normal and ARC/memory trace modes.
2. Native regressions cover nested paths, unknown names, wrong modules, wrong enums, duplicates, invalid-plus-missing
   coverage, wildcard ordering, wildcard-free exhaustive matches, arity-invalid coverage, payload-binding exclusion,
   exact nested-path wording, and representative diagnostic spans.
3. Repository-root `make test` passed: 1,472 L0 Python tests, all 55 L0 Stage 2 tests, workflows and examples, and all
   67 L1 Stage 1 tests and examples completed successfully.
4. The independent read-only review found missing no-wildcard, arity/binding, and diagnostic-detail regressions. All
   findings were accepted and fixed; follow-up review reported no remaining actionable issue.
