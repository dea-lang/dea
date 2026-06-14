# Feature Plan

## Add the separate-compilation driver surface

- Date: 2026-06-13
- Status: Draft
- Title: Add the separate-compilation driver surface
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0001-separate-compilation-and-linking.md`
- Subsystem: CLI / driver / build workflow / docs
- Modules:
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/l1c.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/0001-separate-compilation-and-linking.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 TESTS="cli_args_test build_driver_test driver_test l1c_lib_test"`

## Summary

Initiative `0001` now commits L1 to a real separate-compilation workflow built around per-module `.l1m`, generated C,
and object files. This plan owns the driver/CLI side of that workflow, but it is split into implementation tranches so
the repo does not land a half-wired user surface:

1. direct `.l1m` import replay and codegen plumbing,
2. CLI option parsing and validation for the future surface,
3. correct compile-only output for one implementation module,
4. build/run fan-out and link orchestration.

Link-option expansion for external libraries is tracked separately so this driver plan can stay focused on module
compilation orchestration.

## Current State

1. Stage 1 still treats one requested entry module plus its import closure as one generated C program build.
2. The current CLI mode matrix is centered on `--build`, `--run`, and inspection modes, not compile-only output.
3. The driver does not search an interface-path list for `.l1m` files.
4. Current runtime short-option plumbing still occupies `-I` / `-L` in a pre-separate-compilation way.
5. The abandoned local `module-interface-implementation` branch proved that direct `.l1m` imports are useful, but also
   showed that exposing `-I` to `--build`/`--run` before provider objects are linked leaves unresolved externs, and that
   compile-only must not emit a whole source closure into one object.
6. The same branch did not complete transitive `.l1m` dependency loading, and any parsed implementation-tier `link`
   entries were not yet populated into the project graph that later provider-object linking depends on.

## Defaults Chosen

1. `-c <module>` (long alias `--compile <module>`) is the stable compile-only user surface.
2. `-I <dir>` (long alias `--interface-path <dir>`) becomes the interface-search path used during compile-involving
   flows.
3. The old runtime-specific `-I` / `-L` short aliases are withdrawn. The long forms `--runtime-include` and
   `--runtime-lib` keep working unchanged, and this plan introduces fresh two-letter short aliases `-Ri` and `-Rl` for
   them respectively (bikeshed-friendly; finalize during CLI implementation if a different convention is chosen).
4. Whole-program `--build` and `--run` remain convenience orchestrators. They do not accept interface-backed imports as
   a complete user-facing workflow until the fan-out/link tranche can provide every required provider object.
5. The driver continues to own import-closure computation rather than pushing build-graph logic into ad hoc scripts.
6. External-library linker flags are not part of this plan beyond the short-alias reclamation above.

## Goal

1. Add interface-backed semantic and codegen plumbing for direct imports.
2. Add compile-only and interface-path options to the L1 CLI/driver when their behavior is coherent.
3. Teach build/run orchestration to compile modules individually in a later fan-out tranche.
4. Preserve current bootstrap ergonomics for ordinary `--build` and `--run` users.
5. Establish the command surface that later link and external-library plans can build on.

## Implementation Phases

### Phase 1: Direct `.l1m` import plumbing

Teach the driver, name resolver, signature resolver, and backend to consume a direct imported `.l1m` for:

- exported symbols,
- transparent struct/enum layouts and opaque name-visible nominal declarations,
- function and top-level binding signatures,
- external declarations in generated C.

Direct interface replay must preserve imported nominal visibility state. Transparent imported nominal types carry full
layout for ordinary by-value and field operations; opaque imported nominal types are name-visible but layout-hidden and
must support pointer-only use without requiring a full definition in the consumer CU.

This phase should not expose `-I` to `--build` or `--run` as a complete workflow. Its verification should compile a
consumer against a pre-existing direct provider interface and check generated C shape, while keeping provider-object
linking out of scope.

This phase may start with direct provider interfaces only, but it must not silently treat missing transitive interface
dependencies as success. Until transitive `.l1m` closure loading exists, nested interface dependencies should either be
rejected with a clear diagnostic or documented as unsupported in the specific driver entry point being tested.

### Phase 2: CLI option and mode design

Extend CLI parsing and validation for:

- `-c` / `--compile`,
- `-I` / `--interface-path`,
- `-Ri` (new short alias for the existing `--runtime-include`),
- `-Rl` (new short alias for the existing `--runtime-lib`),
- any internal/testing-only long-form interface-emission mode needed to support Stage 1 development.

This phase should also retire the old runtime-specific meaning of `-I` and `-L` so the option surface stops conflicting
with the new separate-compilation model. The long forms `--runtime-include` / `--runtime-lib` keep working unchanged.

CLI parsing may land before all orchestration is complete only if mode validation prevents users from entering
half-supported workflows. In particular, `--build` and `--run` must not accept interface-backed imports until their
provider objects are linked.

### Phase 3: Compile-only driver flow

Teach the driver/library entry points to compile a single module into generated C, object output, and `.l1m`, with
imported modules loaded through interface discovery rather than always rebuilding the whole closure as one generated C
unit.

The compile-only artifact writer must treat `.l1m` as part of a successful output set, not as an early side effect. If C
compilation or object writing fails, the command must not leave a newly written interface file that can be mistaken for
a valid provider artifact on a later build.

### Phase 4: Build/run fan-out orchestration

Update `--build` and `--run` to compute the import closure, compile modules individually, and prepare the later link
stage inputs deterministically. This phase owns passing every provider object needed by an interface-backed consumer to
the linker.

This phase also owns walking the transitive `.l1m` dependency graph for interface-backed builds and ensuring any
implementation-tier dependency records that feed linking, including populated `link` entries, correspond to concrete
provider objects or explicit external-link inputs.

## Diagnostics

1. This plan is expected to need new driver diagnostics for interface-path handling, compile-only target resolution, and
   new mode-validation failures.
2. Provisionally reserve `DRV-0070` to `DRV-0089` for separate-compilation target and interface-search-path discovery
   diagnostics.
3. Provisionally reserve `L1C-2030` to `L1C-2049` for new CLI mode validation and compile-only/build orchestration
   failures.
4. Re-check the live catalog at implementation time before assigning final numbers. If any proposed slot has been used
   in the meantime, choose a different free block then.

## Non-Goals

1. Fingerprint hashing and link-time provider verification.
2. External-library linking flags.
3. Runtime static-library extraction.
4. Full C FFI support.
5. Landing `--build`/`--run` interface search without provider-object link orchestration.
6. Emitting one compile-only object that contains multiple source modules from the import closure.
7. Treating direct-interface replay as proof that transitive interface closure, dependency graph population, or
   provider-object discovery is complete.
8. Defining the source-language `export opaque { T }` semantic diagnostics; the opaque-export plan owns by-value opaque
   rejection and exported-surface visibility checks.

## Verification Criteria

01. Direct `.l1m` imports replay into analysis and codegen without requiring the provider source.
02. `-c` / `--compile` and `-I` / `--interface-path` parse, validate, and participate in the driver only for supported
    modes.
03. `-Ri` and `-Rl` resolve to `--runtime-include` and `--runtime-lib` respectively, and the old `-I` / `-L` runtime
    short aliases are no longer accepted.
04. `--compile` emits exactly one implementation module's object and does not smuggle source-import definitions into
    that object.
05. A failed object compilation does not leave a fresh `.l1m` interface artifact behind.
06. `--build` and `--run` preserve current user-facing behavior until the fan-out tranche links all provider objects.
07. Interfaces with transitive `require` / `link` dependencies are either resolved through the interface closure or
    rejected with a clear diagnostic until closure loading is implemented.
08. Implementation-tier `link` dependency records are populated before any build/run or link-verification path relies on
    them to select provider objects.
09. Direct interface replay tests cover pointer-only use of imported opaque nominal types without requiring imported
    layout, while by-value opaque rejection remains covered by the opaque-export semantic tests.
10. Driver tests cover invalid mode combinations, missing interface paths, direct interface imports, and successful
    compile-only flows.
11. Any newly assigned diagnostic codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md`.
