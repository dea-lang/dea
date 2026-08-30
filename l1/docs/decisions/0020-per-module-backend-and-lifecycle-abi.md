# ADR-0020: Per-Module Backend and Lifecycle ABI

- Decision date: 2026-07-22
- Last edited: 2026-08-30
- Status: Accepted

## Context

The bootstrap backend originally emitted the complete source closure and process-level C `main` in one translation unit.
Separate compilation needs an independently compilable C unit for one source module while build/run composes a complete
source/interface graph through the same module boundary.

The executable wrapper needs stable entry points for module initialization, finalization, and selection of a possibly
non-exported source `main` without giving imported modules permission to orchestrate one another.

## Decision

L1 exposes `backend_generate_module(result, target_module, opts, cfg)` as its only production backend generation
entrypoint. The transitional `backend_generate(result, opts, cfg)` whole-program path, combined initialization walk, and
backend-owned process wrapper are removed now that every CLI producer uses the module boundary.

The module generator selects one canonical source-backed target and applies these rules:

- It emits linkable storage and function definitions only for the target module. Target type definitions and the
  transparent imported layouts required to compile them may be reproduced; imported opaque layouts remain hidden.
- It emits external declarations for source and interface values and functions consumed by the target. Non-extern L1
  declarations use provider-owned LBI names, while C `extern` declarations preserve their declared C spelling.
- Target source exports keep external linkage and target non-exports use `static`. Compiler-generated module symbols are
  always external and are not controlled by the export manifest.
- It never emits the process-level C `main`, the legacy whole-program init chain, or calls to dependency lifecycle
  functions.

Every module translation unit defines an always-present, one-shot lifecycle pair under the LBI `I` terminal and
conditionally defines the following entry bridge:

- `void I4init(void)` initializes only deferred top-level `let` values owned by the module, in established within-module
  order. Its body is empty when no initialization is required.
- `void I4fini(void)` cleans only ARC-managed top-level `let` values owned by the module. Its body is empty when no
  cleanup is required.
- `int I5entry(void)` is present only when the module defines a resolved, zero-parameter, non-extern source `main`. It
  can call a non-exported source definition within the same translation unit and normalizes results to a C status: `int`
  directly, `bool` as `true` to `0` and `false` to `1`, and every other form to `0` after the call.

`I5entry` does not initialize runtime argument state or call lifecycle functions. The common linker used by standalone
link and build/run composes the per-module ABI through a separate process wrapper: it calls `_rt_init_args`, calls each
selected Dea module's `I4init` in deterministic dependency-first order, invokes exactly one selected `I5entry`, and
calls `I4fini` in exact reverse order. Foreign objects do not participate in this lifecycle sequence.

## Rationale

- A separate module API prevents callers from assembling unsupported mixtures of whole-program and per-module output
  flags.
- Provider-owned declarations let one target compile against source-backed and interface-backed imports without
  duplicating provider definitions.
- Always-present init and fini symbols give every Dea object a uniform lifecycle surface.
- Keeping lifecycle operations module-local preserves ownership boundaries; the final executable wrapper has the graph
  context needed to order modules correctly.
- An in-module entry bridge reaches a private source `main` without turning it into a source export or placing a process
  wrapper in every object.
- Removing the transitional generator after migration prevents a second definition, initialization, and process-wrapper
  contract from drifting beside the operational module boundary.

## Consequences

- Ordinary `--gen` emits one selected module; build/run compiles each source-backed graph node through the same module
  operation and links the complete source/interface set.
- The internal module generator produces the lifecycle-bearing staged C used by operational compile-only mode.
  Compile-only always publishes the object and interface, while `--keep-c` also publishes that exact generated C.
- Per-module objects contain no embedded Dea metadata; verified sibling interfaces carry entry and lifecycle manifests.
- The standalone linker selects exactly one `I5entry`, calls `I4init` in dependency order, calls `I4fini` in reverse
  order, and keeps foreign objects outside Dea lifecycle orchestration.
- Future Stage 2 implementation must preserve the same module-output and LBI behavior.
- No backend API emits a complete source closure or owns process-level wrapper orchestration.

## Related Plans

- [l1/work/initiatives/closed/0001-separate-compilation-and-linking.md](../../work/initiatives/closed/0001-separate-compilation-and-linking.md):
  completed separate-compilation and external-linking initiative
- [l1/work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md][interface-authority]
- [l1/work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md][lifecycle]
- [l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md][module-graph]
- [l1/work/plans/features/closed/2026-04-24-multi-cu-initialization-and-link-order-noref.md][superseded-init]
- [l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md][object-metadata]
- [l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md][compile-only]
- [l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md][link-set]
- [l1/work/plans/features/closed/2026-07-17-build-run-multi-cu-orchestration-noref.md][build-run]
- [l1/work/plans/features/closed/2026-07-24-per-module-generated-c-mode-noref.md][generated-c-completion]

## Current Docs

- [l1/docs/specs/compiler/abi.md][abi]: reserved module symbols, signatures, linkage, and normalization
- [l1/docs/reference/c-backend-design.md][backend]: per-module emission and generated-C identity contract
- [l1/docs/reference/architecture.md][architecture]: internal pipeline boundary and CLI separation
- [l1/docs/project-status.md][project-status]: implemented Stage 1 scope and remaining orchestration work

[abi]: ../specs/compiler/abi.md
[architecture]: ../reference/architecture.md
[backend]: ../reference/c-backend-design.md
[build-run]: ../../work/plans/features/closed/2026-07-17-build-run-multi-cu-orchestration-noref.md
[compile-only]: ../../work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md
[generated-c-completion]: ../../work/plans/features/closed/2026-07-24-per-module-generated-c-mode-noref.md
[interface-authority]: ../../work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md
[lifecycle]: ../../work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md
[link-set]: ../../work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md
[module-graph]: ../../work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[object-metadata]: ../../work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md
[project-status]: ../project-status.md
[superseded-init]: ../../work/plans/features/closed/2026-04-24-multi-cu-initialization-and-link-order-noref.md
