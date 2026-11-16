# Bug Fix Plan

## Run Pages publication when draft release resolution is skipped

- Date: 2026-11-16
- Status: Completed
- Completed: 2026-11-16
- Title: Run Pages publication when draft release resolution is skipped
- Kind: Bug Fix
- Severity: Medium
- Stage: Shared
- Subsystem: Documentation publication workflow
- Modules:
  - `.github/workflows/l0-docs-publish.yml`
- Test modules:
  - `l0/tests/test_release_tag_policy.py`

## Root Cause

Pages-only publication intentionally skips draft release resolution. Target resolution explicitly tolerates this skip,
but documentation building and Pages deployment inherit the default success condition across their dependency chains.
Consequently, the workflow reports success without building or deploying documentation.

## Implementation

Give the build and deploy jobs explicit cancellation-aware status conditions and require their direct prerequisites to
succeed. Retain Pages availability and publication-input gates. Add a regression that evaluates the actual workflow
conditions over fixture job results, including implicit ancestor success, optional draft resolution, failure, skipped
prerequisites, cancellation, and disabled/unavailable Pages. The model is limited to these Boolean job conditions;
GitHub-hosted scheduling and publication still require separate execution.

## Verification

- The new regression failed against the original workflow because Pages-only publication skipped `build-docs`.
- From `l0/`, `../.venv/bin/python tests/test_release_tag_policy.py` passed after the correction. Cases cover Pages-only
  execution, the existing draft-attachment path, failed/cancelled/skipped prerequisites, workflow cancellation, disabled
  Pages, and unavailable Pages. Pages-only execution leaves asset attachment and blog export skipped.
- In-memory mutation probes independently removed the deploy status guard, the build prerequisite guard, and the deploy
  prerequisite guard. The regression rejected all three.
- Actionlint passed with the existing `ubuntu-26.04` label supplied through a temporary compatibility configuration.
- Staged whitespace, ADR closure validation, and root pre-commit are the final commit gates.

This hosted workflow repair is trace-independent and does not change generated documentation, compiler packages, runtime
behavior, or release assets. Prior documentation and packaging validation remains applicable because those inputs are
unchanged. Local checks model conditions only; actual GitHub scheduling and deployment remain to be verified by a
separately authorized workflow run.

## Publication Boundary

Local correction, validation, and commit are authorized. No push, tag, workflow dispatch, release update, or deployment
is in scope. A subsequent authorized publication must verify that build and deploy jobs actually execute.

## ADR Impact

- Decision: Preserve Pages-only publication when the optional draft-resolution job is skipped.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs workflow execution to match its existing inputs and publication contract without changing
    architecture or authorization boundaries.
