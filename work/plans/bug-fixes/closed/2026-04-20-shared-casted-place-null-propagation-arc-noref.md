# Bug Fix Plan

## Shared casted-place null-propagation ARC cleanup

- Date: 2026-04-20
- Status: Closed
- Title: Restore shared casted-place null-propagation ARC cleanup classification across L0 and L1 backends
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Python Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L0 Stage 2, using the minimized traced repro to settle the ownership rule before porting aligned fixes
- Porting rule: Fix the shared cast-from-place ownership classification first in the L0 backends, then port the
  source-level `?` cleanup mechanically into the homologous L1 Stage 1 paths where the code remains aligned
- Target status:
  - L0 Python Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Backend ARC ownership / nullable expression lowering
- Modules: `l0/compiler/stage1_py/l0_backend.py`, `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`,
  `l0/compiler/stage2_l0/src/backend.l0`, `l0/compiler/stage2_l0/src/build_driver.l0`,
  `l0/compiler/stage2_l0/src/l0c_lib.l0`, `l0/compiler/stage2_l0/tests/backend_test.l0`,
  `l1/compiler/stage1_l0/src/backend.l0`, `l1/compiler/stage1_l0/src/build_driver.l0`,
  `l1/compiler/stage1_l0/src/expr_types.l0`, `l1/compiler/stage1_l0/src/l1c_lib.l0`
- Test modules: `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`,
  `l0/compiler/stage2_l0/tests/backend_test.l0`, `l0/compiler/stage2_l0/tests/build_driver_test.l0`,
  `l0/compiler/stage2_l0/tests/l0c_lib_test.l0`, `l0/compiler/stage2_l0/tests/driver_test.l0`,
  `l1/compiler/stage1_l0/tests/backend_test.l0`, `l1/compiler/stage1_l0/tests/build_driver_test.l0`,
  `l1/compiler/stage1_l0/tests/expr_types_test.l0`, `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`,
  `l1/compiler/stage1_l0/tests/driver_test.l0`
- Related:
  - `l0/docs/reference/ownership.md`
  - `l1/docs/reference/ownership.md`
- Repro: `make -C l1 test-stage1-trace TESTS="l0c_lib_test"` after rewriting the constant-constructor initializer loops
  to use `let value = helper(...)?;` in the previously casted string path

## Summary

Rewriting the L1 constant-constructor loops from an explicit nullable guard to direct `?` propagation exposed an ARC
ownership bug in the L0 backends when a nullable string place was immediately cast and passed through an owner-sensitive
call path.

The failing shape was not bare `...?`; it was `...?` followed by an identity-style cast such as `field_init as string`
before insertion into a vector or another owner-taking call.

## Root Cause

Both L0 backends misclassified cast expressions whose operand was already a place. In ownership-sensitive lowering, the
compiler treated `x as string` as though it were a fresh ARC rvalue rather than a casted view of the existing place.

That let the compiler materialize and later release a synthetic ARC alias temp for the casted local. Once a container
stored the original pointer, later retains and releases could touch freed memory. L0 Stage 2 exposed the bug reliably
under trace, while L0 Python Stage 1 carried the same bad ownership shape in generated code.

## Scope of This Fix

1. Keep cast expressions from existing places place-like for ARC ownership classification in both L0 backends.
2. Add focused Stage 1 and Stage 2 regressions that lock the generated-code invariant for identity casts on string
   places.
3. Remove the original L1 source workaround shape by using direct `?` propagation where the expression type is already
   narrowed.
4. Clean up the other direct manual null-propagation candidates identified during the follow-up audit of the affected
   compiler sources.

## Approach

- Update the shared cast-from-place helper in `l0/compiler/stage1_py/l0_backend.py` and
  `l0/compiler/stage2_l0/src/backend.l0` so casts whose operand is already a place remain place-like for ARC decisions.
- Add one focused codegen regression per L0 backend to assert that `sink(first as string)` does not materialize a
  synthetic ARC alias temp.
- Keep the user-facing L1 constructor code in direct `?` form and drop the redundant `as string` casts after
  propagation.
- Rewrite the audited direct null-propagation candidates in the L0 Stage 2 and L1 Stage 1 driver/library and helper
  paths to the simpler `?` form once the backend bug is fixed.

## Tests

Minimum coverage for the landed fix:

1. the focused L0 Python backend regression for identity-cast string-place ownership stays green,
2. the focused L0 Stage 2 backend regression for the same codegen invariant stays green,
3. the original L1 trace failure in `l0c_lib_test` no longer reproduces,
4. the touched driver, backend, and expression-typing suites continue to pass after the direct `?` rewrites.

## Verification

```bash
cd l0 && ../.venv/bin/python -m pytest compiler/stage1_py/tests/backend/test_codegen_semantics.py -k identity_cast_place_copy_retains
cd l0 && make test-stage2 TESTS="backend_test build_driver_test l0c_lib_test driver_test"
cd l1 && make test-stage1 TESTS="backend_test expr_types_test build_driver_test l0c_lib_test driver_test"
cd l1 && make test-stage1-trace TESTS="l0c_lib_test"
```

## Outcome

- Fixed cast-from-place ARC ownership classification in both L0 backends so identity-style casts on existing string
  places no longer fabricate and release synthetic owner aliases.
- Added focused Stage 1 and Stage 2 backend regressions that pin the no-alias-temp codegen invariant.
- Updated the L1 constant-constructor loops and the other direct manual null-propagation candidates in both compilers to
  the simpler `?` form with redundant casts removed.

## Assumptions

- The ownership rule remains shared: a cast whose operand is already a place must stay place-like for ARC decisions
  unless the cast itself introduces a real ownership boundary.

## Follow-up

The L1 Stage 1 hunk of this fix was incomplete at original closing time: only the source-level `?` rewrites in
`l1/compiler/stage1_l0/src/{backend,build_driver,expr_types,l1c_lib}.l0` were ported in the initial implementation. The
actual widening of `be_is_unwrap_cast_from_place` from "T? as T from place" to "any cast from place" was missed in
`l1/compiler/stage1_l0/src/backend.l0` and remained in the narrow shape until the
[2026-04-30 closed bug-fix plan][followup-plan] discovered the divergence as the root cause of the concat-refactor
failure footprint and landed the L1 backend port plus the matching L1 backend regression. This closed plan's "L1 Stage
1: Implemented" status should be read as covering the source-level `?` rewrites only; the backend helper port belongs to
the follow-up.

[followup-plan]: 2026-04-30-shared-arc-owned-local-reassignment-semantics-noref.md
