# Bug Fix Plan

## Restore binding identity and declaration-order visibility in self-hosted analysis

- Date: 2026-08-23
- Status: Draft
- Title: Make native scope, pattern, and cleanup analysis track exact bindings at their declaration points
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Stage 2
  - L1 Stage 1
- Origin: Use L0 Python Stage 1 declaration-order and binding-identity behavior as the oracle, settle the native model
  in L0 Stage 2, then port the common changes to L1 Stage 1.
- Porting rule: Port declaration visibility, pattern-binding identity, and cleanup-guard identity mechanically; retain
  L1's already-correct `lc_visit_scoped_stmt()` behavior and port that helper back to L0 Stage 2.
- Target status:
  - L0 Stage 2: Pending
  - L1 Stage 1: Pending
- Subsystem: Local scopes / Expression typing / Match bindings / Cleanup analysis
- Modules:
  - `l0/compiler/stage1_py/l0_locals.py`
  - `l0/compiler/stage1_py/l0_expr_types.py`
  - `l0/compiler/stage2_l0/src/locals.l0`
  - `l0/compiler/stage2_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/locals.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/locals/test_locals.py`
  - `l0/compiler/stage1_py/tests/integration/test_case_statement.py`
  - `l0/compiler/stage1_py/tests/integration/test_with_statement.py`
  - `l0/compiler/stage2_l0/tests/locals_test.l0`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/locals_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
- Related:
  - `work/plans/bug-fixes/closed/2026-04-10-shared-self-hosted-stage1-statement-parity-audit-noref.md`
  - `l0/work/plans/bug-fixes/closed/2026-06-05-stage2-for-loop-variable-scope-shadow-parity-noref.md`
  - `l1/work/plans/features/closed/2026-04-23-single-statement-loop-and-match-bodies-noref.md`
- Repro: Run the four minimized cases in Current State: a bare `case` arm local, an outer reference before a later
  same-scope shadow, repeated pattern-variable names with different payload types, and a cleanup-local shadow of a
  guarded header name.

## Summary

The self-hosted analyzers build lexical scopes before expression checking, but several later decisions treat every name
present in that completed scope as if it were already visible or uniquely identified. This produces four related
failures: L0 Stage 2 misses the scope mapping for a non-block `case` arm, later declarations can shadow earlier
references retroactively, pattern payload types collide by module and variable name, and cleanup guards confuse a
shadowing local with the guarded header declaration.

L1 Stage 1 already maps every scoped statement body through `lc_visit_scoped_stmt()`, so the bare-arm defect is L0-only.
Its declaration-order, pattern-type, and cleanup-guard representations remain homologous to the affected L0 Stage 2
paths and are in shared scope.

## ADR Impact

- Decision: Restore lexical visibility and guard/type metadata using exact declaration identities rather than bare
  names.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The plan restores established lexical scoping and typing behavior already implemented by the Python
    frontend; it does not introduce a new name-resolution or scope architecture contract.

## Current State and Reproduction Evidence

1. **Bare `case` body mapping:** L0 Stage 2 records an arm scope only when its body is `ST_BLOCK`. A single `let`
   statement is visited in the child scope but its statement ID is not mapped back to that scope during type checking.
2. **Retroactive shadowing:** native local collection pre-populates a block's symbol map. `etc_lookup_local()` searches
   that completed map while typing an earlier initializer, so a later same-block declaration can hide an outer binding
   before its declaration point.
3. **Pattern payload collision:** `etc_set_var_type()` stores pattern types under `<module>::var::<name>`. Reusing the
   same binder name in another arm or function overwrites the prior binding's type.
4. **Cleanup guard collision:** `CleanupHeaderGuard` stores only guarded names. A nested cleanup local with the same
   name is therefore reported as the maybe-uninitialized header binding.
5. Python Stage 1 declares locals sequentially, binds pattern payloads in the current lexical scope, and records the
   exact guarded header scope index.

## Scope of This Fix

1. Port L1's scoped-statement registration helper to L0 Stage 2 and cover non-block `case` arms and `else` bodies.
2. Separate a scope's complete declaration inventory from the set visible at the current statement position, or
   otherwise make native local lookup declaration-order aware.
3. Key pattern payload types by an exact binding identity, such as the owning pattern and binder slot, rather than
   module plus text name.
4. Record cleanup guards against the exact header declaration or scope/binding pair.
5. Preserve duplicate-declaration and shadow-warning behavior by keeping declaration tracking distinct from expression
   visibility.
6. Add cross-function, cross-arm, nested-scope, and repeated-name regressions in both native trees.

## Target-Specific Work

### L0 Stage 2

1. Fix all four confirmed defects.
2. Add explicit scope lookup tests for bare `case` arms and `case else`.
3. Match Python Stage 1 diagnostics for declaration-order and cleanup-shadow cases.

### L1 Stage 1

1. Preserve the current all-body scope mapping as a regression invariant.
2. Fix declaration-order visibility, pattern payload identity, and cleanup-guard identity.
3. Include L1-specific expression forms only where they exercise the same binding model.

## Diagnostics

No new diagnostic family is required. Reuse the existing duplicate, shadowing, type-mismatch, and cleanup-reference
codes with their established meanings. Implementation must check the live diagnostic catalog before changing any code
association, but no reassignment is planned.

## Non-Goals

1. Replacing the complete local-scope pass with a new name resolver.
2. Changing legal shadowing rules or warning policy.
3. Expanding pattern syntax or cleanup semantics.

## Verification

1. Add direct scope-map tests plus analyzer fixtures for each of the four reproduction shapes.
2. Assert the reference before a later shadow resolves to the outer declaration and receives its type.
3. Assert repeated binder names in different arms/functions retain independent payload types.
4. Assert only the exact maybe-uninitialized header declaration is guarded in cleanup.
5. Run focused locals and expression-type suites for both native compilers, then L0 triple bootstrap and root
   `make test-all` because the fix changes ownership-sensitive analysis metadata.

## Verification Criteria

1. Source order, not pre-populated scope contents, determines local visibility.
2. Binding metadata cannot collide solely because two declarations share a text name.
3. L0 Stage 2 maps every scoped single-statement body consistently with L1 Stage 1.
4. Existing duplicate and shadow diagnostics retain their codes and counts.
