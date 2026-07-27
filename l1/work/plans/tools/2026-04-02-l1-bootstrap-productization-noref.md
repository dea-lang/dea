# Tool Plan

## Define the first L1 install/dist/bootstrap-product workflow

- Date: 2026-04-02
- Status: Draft
- Title: Define the first L1 install/dist/bootstrap-product workflow
- Kind: Tooling
- Severity: Medium
- Stage: L1
- Subsystem: Build workflow / install layout / distribution packaging / bootstrap docs
- Modules:
  - `l1/Makefile`
  - `l1/scripts/`
  - `l1/compiler/shared/`
  - `l1/docs/`
  - `scripts/dea_tooling/`
- Test modules:
  - `l1/compiler/stage1_l0/scripts/run_tests.py`
  - install-prefix smoke checks
  - dist archive smoke checks
- Related:
  - `work/plans/refactors/closed/2026-04-02-l1-bootstrap-scaffold-noref.md`

## Summary

The `l1/` subtree currently supports repo-local bootstrap development through `make build-stage1`, shell activation via
`build/l1/bin/l1-env.sh`, and `make test-stage1`. It does not yet define an install-prefix workflow, distribution
archive format, or the first stable bootstrap-oriented artifact layout for L1.

This plan defines that missing productization layer without changing the current scope claim: L1 remains a bootstrap
toolchain seed, not a release-bearing product. The goal is to make the Stage 1 compiler installable, runnable from an
installed prefix, and packageable as a curated bootstrap archive with explicit upstream-compiler provenance.

## Current State

1. `l1/` is bootstrap-only.
2. `make build-stage1` builds a repo-local `l1c-stage1` wrapper and native binary under `build/l1/bin/`.
3. `make test-stage1` validates the copied Stage 1 implementation tests using the upstream L0 compiler.
4. There is no `make install`, `make list-installed`, `make dist`, or release-artifact layout for L1.
5. Bootstrap correctness depends on the explicit upstream compiler contract:
   - local development defaults to `../l0/build/dea/bin/l0c-stage2`
   - reproducible overrides must use `L1_BOOTSTRAP_L0C`
   - the workflow must not rely on whichever `l0c` happens to be on `PATH`

## Defaults Chosen

1. L1 remains bootstrap-only after this work; productization here does not imply stable-release readiness.
2. The default local upstream compiler remains repo-local `../l0/build/dea/bin/l0c-stage2`.
3. Installed and dist-oriented validation must support an explicit `L1_BOOTSTRAP_L0C` override.
4. The first install/dist layout should stay minimal and bootstrap-oriented rather than mirroring the full L0 release
   payload.
5. Shared launcher/env/bootstrap helpers should be reused only where L0 and L1 already share the same behavior.

## Goal

1. Define the first install-prefix layout for the L1 Stage 1 compiler.
2. Add install workflows that make the built compiler usable outside the repo-local build tree.
3. Add a minimal distribution archive workflow for the bootstrap-stage L1 toolchain.
4. Update L1-local docs so the install/dist/bootstrap workflow is documented consistently.

## Implementation Phases

### Phase 1: Define the install-prefix layout

Define the installed L1 layout and discovery rules for:

- `bin/` launchers and env activation files
- runtime include path resolution
- stdlib/module root resolution
- any metadata file needed for smoke-testable bootstrap artifacts

The installed layout must preserve the existing bootstrap contract and must not weaken `L1_BOOTSTRAP_L0C` semantics.

### Phase 2: Add install workflows

Add the first L1 install-target surface, including:

- `make install PREFIX=...`
- `make list-installed PREFIX=...`
- installed launcher generation
- installed env activation scripts for the same shells already supported by the repo-local workflow

Install behavior should mirror the L0 developer experience where that improves usability, but only for the bootstrap
subset L1 actually owns today.

### Phase 3: Add distribution packaging

Add `make dist` for a bootstrap-stage L1 archive with a curated payload containing only what is needed to run the
installed Stage 1 toolchain and validate it with a smoke test. The archive shape must be intentionally smaller than the
L0 release archive and must not claim end-user completeness.

The plan must define:

- archive root name
- expected installed files inside the archive
- which docs are included
- which development-only or monorepo-only files are excluded

### Phase 4: Update documentation and contributor guidance

Update the L1-local docs and contributor guidance so they describe:

- repo-local bootstrap workflow
- install-prefix workflow
- dist archive workflow
- explicit upstream compiler override behavior via `L1_BOOTSTRAP_L0C`

## ADR Impact

- Decision: Define a minimal install-prefix and distribution-artifact contract for the bootstrap-stage L1 compiler.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The installed layout, archive contents, launcher behavior, and provenance contract become public
    toolchain interfaces that future release work must preserve.
- Decision: Choose the L1 bootstrap compiler from repo-local L0 Stage 2 or `L1_BOOTSTRAP_L0C`, never ambient `PATH`.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0001-bootstrap-adaptation-strategy.md`
  - Rationale: ADR-0001 owns bootstrap adaptation and should record the compiler-selection rule for installed and
    distribution workflows.

## Non-Goals

- GitHub Release publishing for L1
- docs publishing or Pages deployment for L1
- any L1 Stage 2 / self-hosted compiler work
- a broad rewrite of the root `README.md`
- automatic inference of the upstream compiler from whichever `l0c` is active on `PATH`

## Verification Criteria

1. `make -C l1 build-stage1` succeeds.
2. `make -C l1 test-stage1` succeeds.
3. `make -C l1 install PREFIX=...` produces a usable install tree.
4. The installed `l1c` reports `--version` correctly and can run a basic smoke command after env activation.
5. `make -C l1 list-installed PREFIX=...` reports the installed payload deterministically.
6. `make -C l1 dist` produces a curated archive that unpacks into the expected layout.
7. The dist archive smoke test can run the packaged `l1c` successfully.
8. The installed and/or packaged workflow honors an explicit `L1_BOOTSTRAP_L0C` override.

## Open Design Constraints

1. The first artifact layout must be stable enough for later CI consumption.
2. The install/dist workflow must stay narrow and bootstrap-oriented until a later plan explicitly expands L1 into a
   release-bearing product.
3. Any reuse of `scripts/dea_tooling/` should follow the existing narrow shared-tooling policy rather than pulling
   unrelated L0 release/docs behavior into L1.
