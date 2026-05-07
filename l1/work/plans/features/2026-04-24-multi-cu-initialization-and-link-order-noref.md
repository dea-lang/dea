# Feature Plan

## Extend module initialization to the multi-CU model

- Date: 2026-04-24
- Status: Draft
- Title: Extend module initialization to the multi-CU model
- Kind: Feature
- Severity: Medium
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0001-separate-compilation-and-linking.md`
- Subsystem: Backend / driver / initialization ordering / docs
- Modules:
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/0001-separate-compilation-and-linking.md`
  - `l1/work/plans/features/closed/2026-04-17-l1-let-non-constant-initializers-noref.md`
- Repro: `make -C l1 test-stage1 TESTS="backend_test build_driver_test driver_test l0c_lib_test"`

## Summary

The completed top-level `let` initializer work already established `_dea_init_<module>()` helpers and dependency-ordered
init chaining inside the old single generated C model. Separate compilation changes the execution model: those init
helpers now live in different CUs and objects, so the executable wrapper and driver need a new cross-object ordering
story.

This plan adapts that existing groundwork to the multi-CU build shape without reopening the semantics of top-level `let`
initialization itself.

## Current State

1. Stage 1 already lowers deferred top-level `let` initialization through hidden `_dea_init_<module>()` helpers.
2. The current generated C `main` wrapper calls a global init chain assembled in one generated C program.
3. That chain assumes all module definitions are emitted into one generated C file.
4. Separate compilation will split those definitions across independently compiled objects.

## Defaults Chosen

1. Per-module `_dea_init` helpers remain the initialization unit.
2. The executable wrapper calls module init helpers in dependency order before user `main`.
3. The dependency order follows the driver's topological module graph, preserving deterministic import-order behavior.
4. Modules with no deferred initialization may still participate through a trivial helper or an omitted call, as long as
   the generated wrapper contract remains deterministic.
5. `_dea_init` orchestration is an executable-target concern only. L1 does not produce static or dynamic library outputs
   today, and Phase 3 external linking only consumes external libraries rather than producing them. If a future tranche
   introduces L1-as-library output, that tranche owns defining the consumer-side init entrypoint contract; this plan
   does not pre-commit one.

## Goal

1. Preserve the current top-level initialization semantics across multiple compiled objects.
2. Move init ordering responsibility from the old single-CU global chain to the new executable wrapper/driver flow.
3. Keep initialization deterministic and testable at module granularity.

## Implementation Phases

### Phase 1: Per-module init emission contract

Make the backend/C emitter explicit about how each compiled module exposes its `_dea_init` entrypoint and when such an
entrypoint is emitted.

### Phase 2: Driver-assembled init order

Teach the driver/build path to compute the dependency-ordered `_dea_init` call sequence for the final executable wrapper
once modules are compiled separately.

### Phase 3: Regression fixtures

Expand initialization fixtures so they prove imported module state is initialized correctly across multiple compiled
modules and not just the old single-CU build shape.

## Diagnostics

1. No dedicated new diagnostic-code block is expected from this tranche.
2. Existing import-cycle and entry-wrapper diagnostics should be reused first if the implementation exposes new failure
   paths while building the ordered init chain.

## Non-Goals

1. Non-constant top-level `let` semantics; those are already established.
2. Fingerprint hashing and object metadata.
3. External-library linker flags.
4. FFI syntax or runtime boundary types.

## Verification Criteria

1. Existing top-level initializer behavior remains unchanged when modules are built separately.
2. The executable wrapper calls `_dea_init` helpers in deterministic dependency order across multiple objects.
3. Driver/backend tests cover modules with and without deferred initialization and imported-state dependencies.
