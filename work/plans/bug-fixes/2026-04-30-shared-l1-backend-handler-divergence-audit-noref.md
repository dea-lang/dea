# Bug Fix Plan

## Shared L1 Stage 1 backend handler divergence audit

- Date: 2026-04-30
- Status: In Progress
- Title: Audit `l1/compiler/stage1_l0/src/backend.l0` against `l0/compiler/stage2_l0/src/backend.l0` for any other
  unported widenings or fixes that arrived through prior shared bug-fix plans
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L1 Stage 1
- Origin: Discovered during the
  [2026-04-30 closed bug-fix plan for ARC owned-local reassignment semantics][parent-plan], where
  `be_is_unwrap_cast_from_place` was found to be the narrow pre-fix shape in L1 Stage 1 while L0 Python and L0 Stage 2
  carried the broad post-fix shape. That divergence had survived since 2026-04-20 and was the root cause of the
  concat-refactor failure footprint. Other shared backend fixes may have similar L1-port gaps.
- Porting rule: Audit only — fix any divergences mechanically once the audit is complete. Do not change semantics.
- Target status:
  - L1 Stage 1: Pending audit
- Subsystem: Backend ARC lowering, scope cleanup ordering, expression emission paths
- Modules:
  - `l1/compiler/stage1_l0/src/backend.l0` (audit subject)
  - `l0/compiler/stage2_l0/src/backend.l0` (oracle)
  - `l0/compiler/stage1_py/l0_backend.py` (oracle for shape rationale)
- Test modules:
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
- Related:
  - `work/plans/bug-fixes/closed/2026-04-20-shared-casted-place-null-propagation-arc-noref.md`
  - `work/plans/bug-fixes/closed/2026-04-21-shared-arc-borrowed-param-reassignment-noref.md`
  - `work/plans/bug-fixes/closed/2026-04-30-shared-arc-owned-local-reassignment-semantics-noref.md`

## Summary

The 2026-04-20 casted-place null-propagation closed plan claimed `L1 Stage 1: Implemented` but in fact only the
source-level `?` rewrites were ported to the L1 tree; the actual widening of `be_is_unwrap_cast_from_place` was missed
in `l1/compiler/stage1_l0/src/backend.l0`. That gap persisted until the
[2026-04-30 ARC owned-local reassignment plan][parent-plan] traced it as the root cause of the concat-refactor failure
footprint and landed the L1 backend port plus the matching regression.

Since this kind of L1-port miss is by construction invisible to the L0 test surface — L0 Stage 2 is the upstream oracle
that compiles the L1 binary, so a stale L1 source-level helper still produces a working L1 binary unless its output
diverges in tests that exercise post-`?` redundant casts or other rare patterns — there may be additional unported fixes
hiding in the L1 backend source surface from earlier shared bug-fix plans. This plan opens the audit.

## Scope

Scope is **audit only**. Any divergence found that has bug-fix semantics (not just stylistic difference) gets fixed and
regression-tested in a follow-up commit, ideally one commit per discovered divergence to keep the diff auditable.

In-scope helper surfaces (compare L1 vs L0 Stage 2 in each pair):

- `be_is_place_expr` and `be_has_side_effects`.
- `be_is_unwrap_cast_from_place` (already ported in the parent plan; included here only as the regression baseline).
- `be_needs_arc_temp`, `be_should_materialize_arc_temp`, `be_materialize_arc_temp`.
- `be_emit_value_cleanup`, `be_emit_retain_for_copied_value`, `be_emit_copy_expr_with_retains`.
- `be_emit_owned_expr_with_expected_type`.
- `ST_LET` and `ST_ASSIGN` handlers (release-before-assign ordering, scope owned-vars registration, lvalue caching).
- `match` and `case` scrutinee retain logic (`be_emit_match` vs L0 Stage 2 sibling).
- `CastExpr` emission paths: `be_emit_unwrap`, `cem_emit_some_value_for_nullable`, the wrap-cast and unwrap-cast
  branches.
- Borrowed-param entry retain (the L0 Python `_collect_reassigned_arc_params` and L0 Stage 2 sibling). Verify the L1
  helper exists and uses the broad classification consistent with the [2026-04-21 closed plan][borrowed-param-plan].
- `be_emit_if_branch` and `be_emit_cleanup_at_scope_exit` (per-branch scope cleanup ordering).
- `be_emit_return` cleanup-for-return ordering and the `ret` temp materialization rule.

## Audit Procedure

For each helper above:

1. Locate the L0 Stage 2 oracle definition in `l0/compiler/stage2_l0/src/backend.l0` and the L1 Stage 1 sibling in
   `l1/compiler/stage1_l0/src/backend.l0`. Quote the function bodies side-by-side.
2. Reduce them to a structural diff — ignore ICE codes and L1-superset arms (such as `EX_BIGINT`, `EX_FLOAT`,
   `EX_DOUBLE` in `be_has_side_effects` — these are legitimate L1 supersets, not divergences).
3. For each remaining difference, decide:
   - Stylistic only (rename, reorder, comment drift): skip; optionally normalize in a separate cleanup commit.
   - Semantic divergence: cross-check against the closed shared bug-fix plans (`work/plans/bug-fixes/closed/`) for ones
     whose shared scope claimed L1 implementation. If a prior plan widened or rewrote the L0 Stage 2 form and the L1
     form does not match, this is a candidate L1-port miss.
4. For each candidate L1-port miss, construct a minimal Dea fixture that exercises the divergent path and demonstrates
   the bug under L1 Stage 1's compilation, ideally the trace runner. Then port the fix and add the regression in
   `backend_test.l0` and (if applicable) `l1c_stage1_arc_trace_regression_test.py`.

## Out of Scope

- Any change to L0 Stage 2 or L0 Python backend behavior. They are the oracle.
- Reformatting or restructuring the L1 backend source for stylistic alignment.
- New language features or new diagnostics.
- Changes to runtime ARC primitives.

## Verification

Per discovered divergence:

```bash
cd l1 && make use-dev-stage1
cd l1 && make test-stage1 TESTS='backend_test'
cd l1 && ../.venv/bin/python -m pytest compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py
cd l1 && make test-stage1
cd l1 && make test-stage1-trace
cd l1 && make check-examples
cd l0 && make -j test-all
```

`make -C l0 -j test-all` includes `triple-test`, which is the strictest gate that the L1 binary, recompiled by L0 Stage
2, still self-bootstraps cleanly.

## Verification Criteria

- For each L1 helper audited, either a confirmation note "structurally aligned with L0 Stage 2" is recorded, or a
  dedicated commit lands the port plus a focused L1 regression that pins the post-fix invariant.
- At plan-close time, every helper in the in-scope list has either a "no divergence" mark or a referenced fixing commit.

[borrowed-param-plan]: closed/2026-04-21-shared-arc-borrowed-param-reassignment-noref.md
[parent-plan]: closed/2026-04-30-shared-arc-owned-local-reassignment-semantics-noref.md
