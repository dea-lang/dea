# Bug Fix Plan

## Preserve ADR impact chronology across stacked pushes

- Date: 2026-08-21
- Status: Completed
- Title: Validate stacked ADR impact push ranges one commit at a time
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - Unified CI ADR impact push validation
- Origin: `scripts/check_adr_impact.py`
- Porting rule: Keep one monorepo-owned chronological push validator; no level-local port is required.
- Target status:
  - Unified CI ADR impact push validation: Implemented
- Subsystem: Lifecycle policy / ADR governance / Unified CI
- Modules:
  - `scripts/check_adr_impact.py`
  - `.github/workflows/ci.yml`
- Test modules:
  - `scripts/tests/test_check_adr_impact.py`
- Related:
  - `docs/decisions/0011-plan-adr-impact-and-closure-gate.md`
  - `work/plans/tools/closed/2026-07-26-shared-adr-impact-closure-gate-noref.md`
- Repro: `python3 scripts/check_adr_impact.py --base <before-sha> --head <push-sha>` reports closure violations that
  disappear when the same stacked range is validated commit by commit.

## Summary

Unified CI currently collapses an entire push into one base/head comparison. On a stacked push, that aggregate diff can
apply a policy introduced in a later commit to an earlier closure and can treat an ADR added earlier in the push as new
in the same change that later closes a plan covered by it. Both results are false positives that contradict the actual
commit chronology.

## ADR Impact

- Decision: Preserve the existing ADR impact closure contract by evaluating each pushed commit against its own parent
  before validating the active inventory at the pushed head.
  - Scope: Repository/tooling
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0011-plan-adr-impact-and-closure-gate.md`
  - Rationale: ADR-0011 already requires same-change closure evidence and grandfathering of untouched history; this fix
    makes push CI apply those rules to the commits that actually introduced each change.

## Root Cause

The push workflow invokes the checker once with `github.event.before` and `github.sha`. That comparison discards the
intermediate repository states on which policy availability, ADR existence, and closure evidence depend.

## Scope of This Fix

1. Add a push-range checker mode that enumerates `BEFORE_SHA..PUSH_SHA` in chronological topological order.
2. Skip commits whose tree does not contain the ADR checker.
3. Validate each remaining commit against its first parent, then validate the active inventory in the pushed head tree.
4. Route push events through the chronological mode while retaining merge-base comparison for pull requests and
   working-tree inventory validation for manual runs.
5. Add Git-backed regressions for policy introduction during a push and for an ADR added before a later covered-plan
   closure.

## Non-Goals

- Reclassifying historically accurate `Covered by ADR` records as `New ADR`.
- Adding ADR Impact sections to untouched grandfathered closed plans.
- Changing the staged checker, pull-request comparison, or ADR closure policy.
- Pushing the resulting commit or dispatching CI.

## Verification Criteria

1. The reported 14-commit historical stacked range passes chronological push validation.
2. A synthetic push that closes a legacy plan before introducing the checker passes without retroactive validation.
3. A synthetic push that adds an ADR in one commit and uses it for a later `Covered by ADR` closure passes, while the
   equivalent aggregate base/head comparison demonstrates the former false positive.
4. Focused checker tests, active and staged ADR validation, workflow syntax checks, pre-commit, and `git diff --check`
   pass.

## Outcome

- Added `--push-base` as a chronological push-range mode that walks commits in reverse topological order, skips trees
  from before the checker existed, validates each checker-aware commit against its first parent, and finishes with the
  active inventory at the pushed head.
- Routed push events through the chronological mode while preserving merge-base comparison for pull requests and
  working-tree inventory validation for manual runs.
- Added Git-backed regressions that reproduce both aggregate false positives and prove the chronological mode accepts
  the valid histories.

## Verification

- The reported 14-commit stacked range passed `--push-base` validation; the aggregate `--base` comparison reproduced the
  two reported false positives.
- All 37 focused checker tests passed, including both new chronology regressions.
- Root `make clean test` passed across L0 and L1; the change is trace-independent CI policy tooling, so the dedicated
  broad trace sweeps were not required.
- Python compilation, active-inventory validation, workflow YAML parsing, and `git diff --check` passed before closure.
