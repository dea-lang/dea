# Bug Fix Plan

## Shared ARC owned-local reassignment semantics and trace repro reduction

- Date: 2026-04-30
- Status: In Progress
- Title: Fix shared ARC owned-local reassignment lowering to match the documented slot-replacement semantics and settle
  the remaining shared root-cause question
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Python Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L0 ownership semantics as documented in the shared ownership references, with the current L1 harness failures
  used as the active seeded repro surface
- Porting rule: Settle the semantic rule and minimal regression in the current oracle/backend pair first, then port the
  fix mechanically to the homologous seeded backends while keeping trace and normal repro coverage aligned
- Target status:
  - L0 Python Stage 1: Pending reproducer
  - L0 Stage 2: No active failing repro
  - L1 Stage 1: Mitigated in current tree
- Subsystem: Backend ARC lowering, owned-local reassignment cleanup ordering, and L1 trace/harness reproduction
- Modules:
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage2_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l0/docs/reference/ownership.md`
  - `l1/docs/reference/ownership.md`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_trace_arc.py`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/mul_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `work/plans/refactors/closed/2026-04-30-prefer-native-string-concat-operator-noref.md`
  - `work/plans/bug-fixes/closed/2026-04-21-shared-arc-borrowed-param-reassignment-noref.md`
  - `l0/docs/reference/ownership.md`
  - `l1/docs/reference/ownership.md`
- Repro: No active failing tree-level repro remains. Historical L1 repros were
  `cd l1 && make test-stage1 TESTS='mul_runtime_test l0c_lib_test'`,
  `cd l1 && make test-stage1-trace TESTS='mul_runtime_test'`, and later
  `cd l1 && make test-stage1 TESTS='expr_types_test'` before the current mitigations landed

## Summary

The ownership references define ordinary ARC assignment as compiler-balanced slot replacement. That contract implies
that owned-local replacement and self-referential ARC assignments such as `name = name + "." + suffix;` are valid
ordinary code and must work without clone-like helper functions.

Recent concat-refactor work exposed a gap between that intended contract and at least part of the current
implementation. The observed failures were evidence of an ownership-lowering or cleanup-ordering bug, not evidence that
the language requires builder-only source patterns or clone-like helpers.

This plan moves the current workaround guidance out of the ownership docs, treats the documented semantics as the
oracle, and drives the implementation work from a narrowed repro sequence.

## Current State

The current ownership docs now state the intended semantic rule:

- the right-hand side of an ARC assignment is evaluated and stabilized before the destination slot is replaced
- the old destination value is released exactly once
- the new stabilized result moves into the destination slot without a clone-like copy

The implementation contract remains stricter than what has been proven by minimized repros across all seeded compilers.

Current known facts:

- `make -C l0 test-all` currently passes
- `make -C l1 test-all` currently passes
- the original L1 repros in `mul_runtime_test` and `l0c_lib_test` are fixed in the current tree
- the later `expr_types_test` regression is also fixed in the current tree
- the ownership docs remain normative and now explicitly state that ARC slot replacement and self-referential
  reassignment are intended-valid semantics

Confirmed L1 hot spots and relative failure classes:

- `l1/compiler/stage1_l0/src/build_driver.l0`
  - long-lived optional owned strings plus repeated `as string` unwraps
  - reuse of one mutable local across distinct ownership origins
  - this manifested as `mul_runtime_test` / `l0c_lib_test` failures
- `l1/compiler/stage1_l0/src/expr_types.l0`
  - delayed unwrap of optional string diagnostics
  - self-referential string replacement in one diagnostic path (`msg = msg + ...`)
  - this manifested as `expr_types_test` failure

Those failures are mitigated by source reshaping in the current tree. What remains open is whether they were only local
L1 bootstrap bugs or symptoms of a deeper shared lowering defect that still deserves a reduced cross-target regression.

## Root Cause Hypothesis

The likely underlying failure class remains one or more backend lowering bugs around ARC slot replacement, including:

- cleanup ordering when an owned local appears on both sides of a reassignment
- ownership stabilization of temporary ARC values created during nested string expressions
- move-versus-retain decisions when replacing one owned local with another ARC source
- scope cleanup of locals whose slot contents have changed across multiple assignments

The earlier suite-wrapper versus direct-trace discrepancy no longer reproduces after the current L1 fixes, so it is no
longer considered a primary active root-cause candidate.

The goal is still not to prove that one current workaround shape is universally required. The goal is to determine
whether a backend-level fix is still needed once the concrete L1 hot spots are accounted for.

## Current Temporary Workarounds

These patterns are allowed as temporary implementation accommodations in compiler code today, but they are not language
rules and must not appear in the ownership references as normative guidance:

- builder-based string extension instead of self-referential `x = x + ...`
- one-shot construction helpers instead of `let s = ""; s = ...`
- separate lexical bindings for distinct ownership origins instead of reusing one mutable owned local

Those patterns should remain documented only here, as temporary source-level mitigations while the compiler bug is being
fixed.

## Scope of This Fix

In scope:

- prove or disprove the slot-replacement rule against the current L0 and L1 backends with a minimal repro
- reduce the historical L1 failure to the smallest useful backend-facing reproducer
- add a focused regression if a backend-level failing shape still exists after the current L1 mitigations
- fix the responsible lowering/cleanup path in the shared backend family if that reduced repro exists
- keep the ownership references normative and free of workaround instructions

Not in scope:

- reintroducing clone-like helper functions
- weakening the documented semantics to match the current bug
- source-level rewrites whose only purpose is to preserve current bootstrap quirks once the backend fix exists

## Reproducer Reduction Plan

Continue investigation in this order:

1. reduce the historical L1 failures to a minimal `.l0` or `.l1` source reproducer for owned-local replacement, delayed
   optional-string unwrap, or self-referential ARC assignment
2. if no direct source repro fails in the current tree, decide whether the plan should narrow from “shared backend fix”
   to “documented L1 mitigations plus follow-up watch item”
3. if a direct source repro does fail, capture:
   - the source program
   - the generated C excerpt for the failing assignment/replacement path
   - the trace log and triage result

The final regression, if still needed, should target the smallest discovered repro, not the broad original
concat-refactor workload.

## Implementation Approach

1. audit the ARC reassignment lowering in the current oracle/backend pair against the documented slot-replacement rule
2. compare the mitigated L1 source fixes against homologous patterns in L0 Stage 2 and L0 Python Stage 1
3. determine whether the remaining issue is:
   - a true shared backend/codegen bug
   - an L1-only source/bootstrap ownership hazard now already mitigated
4. if a backend/codegen bug remains, fix it in the responsible implementation and port it mechanically across aligned
   targets
5. if no backend/codegen bug remains reproducible, update this plan to record the findings and close or narrow it

## Verification

Minimum investigation and fix validation:

```bash
cd l1 && make test-stage1 TESTS='mul_runtime_test l0c_lib_test expr_types_test'
cd l1 && make test-stage1-trace TESTS='mul_runtime_test expr_types_test'
cd l1 && ../.venv/bin/python compiler/stage1_l0/scripts/run_test_trace.py mul_runtime_test
cd l1 && ../.venv/bin/python compiler/stage1_l0/scripts/run_test_trace.py l0c_lib_test
cd l1 && ../.venv/bin/python compiler/stage1_l0/scripts/run_test_trace.py expr_types_test
cd l1 && ../.venv/bin/python compiler/stage1_l0/scripts/check_trace_log.py <stderr.log> --triage
cd l0 && ../.venv/bin/python -m pytest compiler/stage1_py/tests/backend/test_trace_arc.py
cd l0 && make test-stage2
cd l0 && make test-stage2-trace
cd l1 && make test-stage1
cd l1 && make test-stage1-trace
```

## Verification Criteria

- the smallest discovered repro, if any still exists, demonstrates a backend/codegen ownership failure rather than only
  a broad suite symptom
- after any further fix, the same repro passes without clone-like helpers
- normal and traced runner paths agree on pass/fail behavior for the same focused repro
- the ownership docs remain accurate without documenting workaround coding styles
- the normal and trace regressions for the touched targets pass
