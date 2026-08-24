# Bug Fix Plan

## Recover ADR impact push bases after rewritten history

- Date: 2026-08-24
- Status: Completed
- Title: Fetch unadvertised ADR impact push bases after force pushes
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - Unified CI ADR impact push validation
- Origin: `.github/workflows/ci.yml`
- Porting rule: Keep one monorepo-owned push-base recovery path; no level-local port is required.
- Target status:
  - Unified CI ADR impact push validation: Implemented
- Subsystem: Lifecycle policy / ADR governance / Unified CI
- Modules:
  - `.github/workflows/ci.yml`
- Test modules:
  - `scripts/tests/test_check_adr_impact.py`
- Related:
  - `docs/decisions/0011-plan-adr-impact-and-closure-gate.md`
  - `work/plans/bug-fixes/closed/2026-08-21-shared-adr-impact-push-range-chronology-noref.md`
- Repro: Force-push a rebased `ci-probe` history so `github.event.before` is no longer advertised, then observe the ADR
  impact job reject the missing base before invoking chronological validation.

## Summary

Unified CI checks out every advertised branch and tag, but a force push can leave the event's `before` commit
unadvertised. The ADR impact job rejects that missing object even though GitHub can still serve it by exact object ID,
so a valid rebased push fails before the chronological checker runs.

## ADR Impact

- Decision: Recover an unadvertised push base by its event-provided object ID before applying chronological ADR impact
  validation.
  - Scope: Repository/tooling
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0011-plan-adr-impact-and-closure-gate.md`
  - Rationale: ADR-0011 already requires CI to enforce same-change closure evidence; recovering the original push base
    preserves that contract across rewritten history without weakening validation.

## Root Cause

`actions/checkout` with full history fetches objects reachable from current refs. After a force push, the prior branch
tip supplied as `github.event.before` may no longer be reachable from any public ref, so it is absent locally and fails
the workflow's endpoint precondition.

## Scope of This Fix

1. Detect a missing nonzero push base after the event endpoints are selected.
2. Fetch the exact `before` object from `origin` before validating both endpoints.
3. Preserve `--push-base` chronological validation and its per-commit closure semantics.
4. Verify the recovery against the reported force-push event and retain a hard failure if the exact object cannot be
   recovered.

## Non-Goals

- Falling back to active-plan-only validation when closure evidence cannot be reconstructed.
- Changing pull-request merge-base handling or manual active-inventory validation.
- Changing the ADR Impact schema or closure policy.
- Pushing the resulting commit or rerunning public CI without fresh user authorization.

## Verification Criteria

1. A checkout containing current advertised refs does not initially resolve the reported pre-force-push object.
2. An exact-object fetch recovers that base and makes the reported `--push-base` range pass.
3. Focused ADR checker tests, active and staged ADR validation, workflow YAML checks, pre-commit, and whitespace checks
   pass.

## Outcome

- Unified CI now detects when a push event's nonzero `before` commit is absent from the advertised checkout and fetches
  that exact object from `origin` before checking the comparison endpoints.
- The job retains chronological `--push-base` validation after recovery and still fails closed when the required object
  cannot be fetched.

## Verification

- An isolated fetch of all current public refs reproduced the missing pre-force-push base; fetching its exact object ID
  recovered it, and the reported chronological push range passed ADR impact validation.
- All 37 focused ADR impact checker tests passed, and active-inventory validation passed.
- Root `make clean test` passed across L0 and L1. The workflow-only change is trace-independent, so the dedicated broad
  trace sweeps were not required.
- Workflow YAML parsing and `git diff --check` passed before closure.
- Staged whitespace, ADR impact, copyright-header, and Markdown-formatting gates passed before commit.
