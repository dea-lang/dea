# ADR-0020: Per-Module Backend and Lifecycle ABI

- Decision date: 2026-07-22
- Last edited: 2026-07-23
- Status: Accepted

## Context

The bootstrap backend originally emitted the complete source closure and process-level C `main` in one translation unit.
Separate compilation needs an independently compilable C unit for one source module, but the existing `--build` /
`--run` workflow must remain usable until compile-only artifact production, object metadata, standalone linking, and
graph fan-out land.

Later object metadata also needs one always-present symbol that anchors compiler-generated records against dead-strip.
The future executable wrapper needs stable entry points for module initialization, finalization, and selection of a
possibly non-exported source `main` without giving imported modules permission to orchestrate one another.

## Decision

L1 retains `backend_generate(result, opts, cfg)` as the legacy whole-program generator and adds the distinct internal
entry point `backend_generate_module(result, target_module, opts, cfg)`.

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

`I5entry` does not initialize runtime argument state or call lifecycle functions. Exact cross-module init/fini ordering,
runtime argument setup, entry selection, and process-wrapper generation belong to the standalone-link tranche.

## Rationale

- A separate module API prevents callers from assembling unsupported mixtures of whole-program and per-module output
  flags.
- Provider-owned declarations let one target compile against source-backed and interface-backed imports without
  duplicating provider definitions.
- Always-present init and fini symbols give every Dea object a uniform lifecycle surface and give object metadata a
  stable future retention anchor.
- Keeping lifecycle operations module-local preserves ownership boundaries; the final executable wrapper has the graph
  context needed to order modules correctly.
- An in-module entry bridge reaches a private source `main` without turning it into a source export or placing a process
  wrapper in every object.
- Preserving the legacy generator avoids a partially migrated build/run workflow before object metadata and standalone
  linking exist.

## Consequences

- Ordinary `--gen`, `--build`, and `--run` remain legacy whole-program single-CU operations for now.
- The internal module generator can produce final lifecycle-bearing C, but `-c` remains non-operational until the
  compile-only artifact plan publishes generated C, object, and interface artifacts together.
- Object metadata may anchor its portable records from `I4init` without introducing a conditional symbol.
- The standalone linker must select at most one `I5entry`, call `I4init` in dependency order, call `I4fini` in reverse
  order, and keep foreign objects outside Dea lifecycle orchestration.
- Future Stage 2 implementation must preserve the same module-output and LBI behavior.

## Related Plans

- [l1/work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md][lifecycle]
- [l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md][module-graph]
- [l1/work/plans/features/closed/2026-04-24-multi-cu-initialization-and-link-order-noref.md][superseded-init]
- [l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md][object-metadata]
- [l1/work/plans/features/2026-07-17-link-set-driver-and-wrapper-noref.md][link-set]

## Current Docs

- [l1/docs/specs/compiler/abi.md][abi]: reserved module symbols, signatures, linkage, and normalization
- [l1/docs/reference/c-backend-design.md][backend]: legacy and per-module emission contracts
- [l1/docs/reference/architecture.md][architecture]: internal pipeline boundary and CLI separation
- [l1/docs/project-status.md][project-status]: implemented Stage 1 scope and remaining orchestration work

[abi]: ../specs/compiler/abi.md
[architecture]: ../reference/architecture.md
[backend]: ../reference/c-backend-design.md
[lifecycle]: ../../work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md
[link-set]: ../../work/plans/features/2026-07-17-link-set-driver-and-wrapper-noref.md
[module-graph]: ../../work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[object-metadata]: ../../work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md
[project-status]: ../project-status.md
[superseded-init]: ../../work/plans/features/closed/2026-04-24-multi-cu-initialization-and-link-order-noref.md
