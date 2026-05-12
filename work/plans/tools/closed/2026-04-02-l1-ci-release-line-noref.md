# Tool Plan

## Define the first L1 CI and release-line workflow policy

- Date: 2026-04-02
- Status: Closed
- Closed: 2026-05-12
- Title: Define the first L1 CI and release-line workflow policy
- Kind: Tooling
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - Monorepo release policy
  - L1 bootstrap CI
- Origin: Root monorepo policy, with L1-local artifact shape defined upstream by the L1 productization plan
- Porting rule: Shared policy at root; L1-local implementation details stay in `l1/` but should not fork the shared
  release-line rules
- Target status:
  - Monorepo release policy: Pending
  - L1 bootstrap CI: Pending
- Subsystem: GitHub Actions / release tagging / monorepo release policy
- Modules:
  - `.github/workflows/`
  - `MONOREPO.md`
  - `docs/project-status.md`
  - `l1/`
- Test modules:
  - L1 bootstrap CI smoke checks
  - workflow trigger and tag-policy validation
- Related:
  - `work/plans/refactors/closed/2026-04-02-l1-bootstrap-scaffold-noref.md`
  - `l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md`

## Summary

The monorepo currently ships only L0 automation workflows: `l0-ci.yml`, `l0-release.yml`, `l0-snapshot.yml`, and the L0
docs workflows. Monorepo policy already reserves the `l1-v*` and `l1-snapshot-*` namespaces, but L1 is not yet an
install/dist/release-bearing product and therefore should not inherit a release automation surface prematurely.

This plan defines the first L1 automation policy after productization exists. The first tranche is bootstrap-validation
CI only. Release and snapshot automation come later, and only after the L1 install/dist artifact contract is stable
enough to support smoke-tested publication.

## Current State

1. There is no L1 CI workflow under `.github/workflows/`.
2. The repo currently publishes only L0 release/snapshot workflows.
3. `MONOREPO.md` already reserves:
   - stable tags: `l1-vX.Y.Z`
   - snapshot tags: `l1-snapshot-*`
4. `docs/project-status.md` correctly states that L1 is not yet an install/dist/release-bearing product.
5. L1 bootstrap currently depends on an explicit upstream L0 compiler contract via `L1_BOOTSTRAP_L0C`.

## Dependency Statement

This plan depends on `l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md` landing first. No L1 release
or snapshot workflow should be implemented before the install/dist artifact shape, launcher behavior, and smoke tests
are defined.

The dependency above is implementation-local detail, not a reason to split this shared work into a separate follow-up
root plan and L1 plan pair.

## Defaults Chosen

1. The first automatic L1 workflow should validate bootstrap build/test behavior only.
2. CI must source the upstream L0 compiler explicitly and reproducibly rather than inheriting ambient `PATH` state.
3. The `l1-v*` and `l1-snapshot-*` namespaces remain reserved until L1 artifacts are intentionally releasable.
4. Bare `v*` tags remain invalid for new monorepo releases, and no dual-tagging is introduced.
5. L1 should not copy every L0 workflow; only the workflows justified by current L1 scope should exist.

## Goal

1. Define the first L1 CI entrypoint for bootstrap validation.
2. Define when L1 release and snapshot workflows become valid to add.
3. Lock in release-line naming and trigger policy before any future L1 publication work begins.
4. Keep workflow ownership aligned with monorepo policy rather than burying release-process rules inside `l1/`.

## Implementation Phases

### Phase 1: Add L1 bootstrap CI

Add a new L1 workflow dedicated to:

- repo checkout
- preparing the explicit upstream L0 compiler input
- building the L1 Stage 1 compiler
- running the L1 Stage 1 tests

This workflow should validate bootstrap behavior only and should not publish artifacts.

### Phase 2: Add manual bootstrap-variant controls only if needed

If bootstrap validation needs more than one runner/compiler combination, add `workflow_dispatch` inputs or a narrow
matrix only where it materially improves confidence. Avoid copying the full L0 matrix unless L1 genuinely needs it.

### Phase 3: Define release-line gating policy

Before any release/snapshot workflow is added, define:

- what qualifies L1 as releasable rather than bootstrap-only
- which artifact produced by the productization plan becomes the release payload
- how tag creation is gated
- how release notes and smoke tests are expected to work for the first L1 line

### Phase 4: Add release/snapshot workflows only after readiness

Only after the previous phases and the productization prerequisites are complete, add:

- an `l1-release` workflow keyed to `l1-v*`
- an `l1-snapshot` workflow keyed to `l1-snapshot-*`

These workflows must consume the stabilized install/dist artifact contract rather than inventing one in workflow YAML.

## Non-Goals

- immediate creation of `l1-release.yml` or `l1-snapshot.yml`
- copying the L0 docs-publish pipeline for L1
- broad cross-level generalization of every L0 workflow
- any change to current L0 release ownership
- changing the monorepo rule that bare `v*` tags are historical only

## Closing Note

Closed on 2026-05-12. All four phases of the plan have been addressed:

- **Phase 1 (L1 bootstrap CI):** Created `.github/workflows/l1-ci.yml` with a four-platform Linux/macOS/Windows matrix
  (ubuntu-latest, macos-15-intel, macos-latest, windows-latest) that prepares the upstream L0 Stage 2 compiler, builds
  the L1 Stage 1 compiler, runs implementation tests, default ARC/memory trace checks, and example validation. Windows
  steps run through MSYS2 UCRT64. Uploads workdir artifact on failure.
- **Phase 2 (Manual controls):** The workflow accepts `workflow_dispatch` inputs for `c_compiler` (gcc/clang) and
  `run_slow_traces` (boolean for opt-in slow trace coverage). The matrix stays narrow (Linux/macOS only) and does not
  copy the full L0 matrix.
- **Phase 3 (Release-line gating policy):** Added a `## Release-line Gating Policy` section to `MONOREPO.md` that
  defines four prerequisite conditions for adding L1 release/snapshot workflows. Updated `docs/project-status.md` to
  reference the CI workflow and the gating policy. Updated `l1/docs/project-status.md` to list the CI workflow in the
  validation section.
- **Phase 4 (Release/snapshot workflows deferred):** Explicitly omitted; no `l1-release.yml` or `l1-snapshot.yml` was
  created. The gating policy and existing tag namespace reservation (`l1-v*`, `l1-snapshot-*`) remain the only release
  automation for L1 today.

Verification criteria met: (1) the CI workflow sources the upstream L0 compiler explicitly via `make use-dev-stage2`
with `L0_CC`; (2) workflow triggers align with `push`/`pull_request` for `l1/` and `tools/` paths plus
`workflow_dispatch`; (3) release-line docs (`MONOREPO.md`, `docs/project-status.md`, `l1/docs/project-status.md`) are
consistent and do not claim L1 is release-bearing; (4) `l1-v*` / `l1-snapshot-*` namespaces remain reserved and unused
by any workflow; (5) policy is consistent across all three doc sites.

## Verification Criteria

1. The first L1 CI workflow can bootstrap using an explicit upstream L0 compiler input.
2. Workflow documentation and trigger policy agree with the implemented GitHub Actions entrypoints.
3. Release-line docs do not claim that L1 is already a release-bearing product before the prerequisites exist.
4. Any future `l1-v*` / `l1-snapshot-*` workflow names and triggers do not conflict with the current L0-only release
   surface.
5. The CI/release policy remains consistent across `MONOREPO.md`, `docs/project-status.md`, and L1-local docs.

## Open Design Constraints

1. L1 CI must consume the artifact and launcher behavior defined by the productization plan rather than redefining them.
2. Release automation should appear only after L1 has smoke-testable install/dist outputs.
3. Root workflow files remain monorepo-owned even when they primarily validate `l1/`.
