# Bug Fix Plan

## Make repeated expression analysis idempotent and ownership-safe

- Date: 2026-08-24
- Status: Completed
- Title: Prevent metadata leaks and duplicate semantic effects during native liveness replay
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Python Stage 1 diagnostic replay audit
  - L0 Stage 2 expression analysis
  - L1 Stage 1 expression analysis
- Origin: Settle replace/free and semantic-once invariants in L0 Stage 2 using L1's local-callee cleanup as an existing
  ownership model, then port common native fixes and audit Python diagnostic multiplicity.
- Porting rule: Keep semantic diagnostics and result metadata idempotent across targets; apply manual type cleanup only
  to native owned `Type*` values and retain Python's managed-memory implementation.
- Target status:
  - L0 Python Stage 1 diagnostic replay audit: Implemented
  - L0 Stage 2 expression analysis: Implemented
  - L1 Stage 1 expression analysis: Implemented
- Subsystem: Expression typing / Liveness fixed points / Analyzer memory ownership
- Modules:
  - `l0/compiler/stage1_py/l0_expr_types.py`
  - `l0/compiler/stage2_l0/src/expr_types.l0`
  - `l0/compiler/stage2_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/analysis.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_trace_memory.py`
  - `l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
- Related:
  - `l0/work/plans/features/closed/2026-03-01-stage2-expression-type-checking-milestone.md`
  - `l1/work/plans/bug-fixes/closed/2026-06-18-stage1-toplet-initializer-typing-noref.md`
  - `work/plans/bug-fixes/closed/2026-06-22-shared-for-header-and-statement-flow-safety-noref.md`
- Repro: Analyze a loop whose condition records an intrinsic target and a function containing a local function-value
  call under memory tracing; repeated condition inference overwrites owned metadata, while L0 Stage 2 also leaks the
  cloned local-callee type used only for an existence check.

## Summary

Native expression analysis owns cloned `Type*` values stored in result maps. Replacing an existing intrinsic target
without freeing the old value leaks memory. Loop liveness convergence infers the same condition multiple times, which
turns that replacement gap into a repeatable leak and can also duplicate semantic diagnostics. L0 Stage 2 has an
additional one-shot leak: `etc_infer_call()` invokes `etc_lookup_local()` in a boolean predicate and drops the returned
owned clone. L1 Stage 1 already wraps the homologous lookup in scoped cleanup.

Python Stage 1 does not share the manual-memory defects, but its loop algorithm also re-infers conditions during
liveness work. It is included for a focused diagnostic-multiplicity audit and semantic-once parity.

## ADR Impact

- Decision: Make analysis result replacement ownership-safe and keep liveness replay free of repeated semantic side
  effects.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The plan corrects analyzer resource management and diagnostic multiplicity within the existing analysis
    architecture; it does not alter language semantics or establish a new compiler phase boundary.

## Current State and Root Cause

1. `etc_set_expr_type()` frees an old mapped type before replacement, but `etc_set_intrinsic_target()` inserts a clone
   without freeing an existing value in both native analyzers.
2. Native loop fixed-point checking calls `etc_infer_expr()` for the condition during the initial pass, convergence
   iterations, and final liveness-only pass.
3. Suppressing diagnostics during part of convergence does not suppress metadata writes or free overwritten values.
4. L0 Stage 2 calls `etc_lookup_local()` solely to compare the result with `null`; the function returns an owned clone.
5. L1 Stage 1 already uses `with (let local_callee_ty = ... => etc_type_free_opt(...))` for that lookup.

## Scope of This Fix

1. Give every owned analysis map an explicit replace-or-insert helper that frees the previous value exactly once.
2. Port L1's scoped local-callee cleanup to L0 Stage 2 and audit nearby existence-only lookups for the same ownership
   error.
3. Separate semantic condition typing from liveness replay, or make replay consume cached semantic results without
   repeating diagnostics and metadata mutation.
4. Preserve liveness-sensitive variable-use checks during the settled pass without re-running unrelated semantic work.
5. Assert exact diagnostic counts for invalid loop conditions and intrinsic operands.
6. Run native analyzer memory tracing on valid and invalid loop fixtures until no owned analysis value leaks.
7. Audit Python Stage 1 for duplicate diagnostics and change it only where the same observable multiplicity is
   reproduced.

## Target-Specific Work

1. L0 Stage 2: fix intrinsic replacement, the local-call clone leak, and repeated condition effects.
2. L1 Stage 1: fix intrinsic replacement and repeated condition effects; retain the existing local-callee cleanup.
3. L0 Python Stage 1: enforce one semantic diagnostic per source condition and retain managed-memory behavior.

## Diagnostics

No new codes are needed. Existing condition and intrinsic diagnostics must retain their meanings and appear exactly once
per offending source expression.

## Non-Goals

1. Removing the liveness fixed-point algorithm.
2. Caching every inferred expression globally without regard to contextual typing.
3. Converting native analysis maps to borrowed `Type*` storage.

## Verification

1. Add a result-map replacement unit test that proves old intrinsic targets are freed.
2. Trace repeated `sizeof` or equivalent intrinsic conditions through zero, one, and multiple convergence iterations.
3. Trace local function-value calls in L0 Stage 2 and retain the L1 control.
4. Assert exact diagnostic counts for invalid conditions across all three frontends.
5. Run focused native expression tests, both native trace suites, L0 triple bootstrap, and root `make test-all`.

## Verification Criteria

1. Replacing analyzer metadata neither leaks nor double-frees.
2. A source condition produces one set of semantic diagnostics independent of convergence count.
3. Liveness replay still diagnoses uses according to the settled ownership state.
4. L0 Stage 2 and L1 Stage 1 finish trace validation with no analyzer-owned `Type` leaks.

## Implementation Outcome

1. Both native analyzers now route owned analysis `Type*` entries through one clone-and-replace helper that frees any
   prior value exactly once; expression types, temporary variable types, and intrinsic targets share that rule.
2. L0 Stage 2 now scopes and frees the cloned local-callee type used by function-call existence checks, matching L1.
3. Loop conditions are semantically inferred once. Convergence and settled passes use cached expression types plus a
   dedicated local-variable liveness walk, preserving next-iteration ownership diagnostics without repeating type
   resolution, semantic diagnostics, or result metadata writes.
4. Python Stage 1 follows the same semantic-once replay boundary while retaining managed-memory metadata storage.
5. Regression fixtures cover repeated valid and invalid `sizeof` conditions, exact diagnostic counts, owned map
   replacement, L0 local function-value calls, and next-iteration condition liveness.

## Verification Outcome

1. Focused Python control-flow tests passed (36 tests), and focused L0 Stage 2 and L1 Stage 1 analysis/expression suites
   passed in both normal and ARC/memory trace modes.
2. Repository-root `make clean test-all` passed: 1,463 L0 Python tests, all 55 L0 Stage 2 tests, triple bootstrap, all
   33 L0 broad trace targets, all 67 L1 Stage 1 tests, and all 44 L1 broad trace targets completed successfully.
3. The required independent read-only review checked the ownership helper, replay call graph, expression traversal,
   local-call regression, and diagnostic tests and reported no actionable findings.
