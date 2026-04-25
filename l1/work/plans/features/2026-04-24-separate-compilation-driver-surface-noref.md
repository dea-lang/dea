# Feature Plan

## Add the separate-compilation driver surface

- Date: 2026-04-24
- Status: Draft
- Title: Add the separate-compilation driver surface
- Kind: Feature
- Severity: High
- Stage: L1
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
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/0001-separate-compilation-and-linking.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 TESTS="cli_args_test build_driver_test driver_test l0c_lib_test"`

## Summary

Initiative `0001` now commits L1 to a real separate-compilation workflow built around per-module `.l1m`, generated C,
and object files. This plan is the driver/CLI tranche that introduces the user-facing entry points for that flow:

- `-c`
- `-I`
- the orchestration needed for `--build` and `--run` to fan out per-module compilation

Link-option expansion for external libraries is tracked separately so this driver plan can stay focused on module
compilation orchestration.

## Current State

1. Stage 1 still treats one requested entry module plus its import closure as one generated C program build.
2. The current CLI mode matrix is centered on `--build`, `--run`, and inspection modes, not compile-only output.
3. The driver does not search an interface-path list for `.l1m` files.
4. Current runtime short-option plumbing still occupies `-I` / `-L` in a pre-separate-compilation way.

## Defaults Chosen

1. `-c <module>` (long alias `--compile <module>`) is the stable compile-only user surface.
2. `-I <dir>` (long alias `--interface-path <dir>`) becomes the interface-search path used during compile-involving
   flows.
3. The old runtime-specific `-I` / `-L` short aliases are withdrawn. The long forms `--runtime-include` and
   `--runtime-lib` keep working unchanged, and this plan introduces fresh two-letter short aliases `-Ri` and `-Rl` for
   them respectively (bikeshed-friendly; finalize during CLI implementation if a different convention is chosen).
4. Whole-program `--build` and `--run` remain convenience orchestrators, but internally they fan out per-module compile
   work.
5. The driver continues to own import-closure computation rather than pushing build-graph logic into ad hoc scripts.
6. External-library linker flags are not part of this plan beyond the short-alias reclamation above.

## Goal

1. Add compile-only and interface-path options to the L1 CLI/driver.
2. Teach build/run orchestration to compile modules individually.
3. Preserve current bootstrap ergonomics for ordinary `--build` and `--run` users.
4. Establish the command surface that later link and external-library plans can build on.

## Implementation Phases

### Phase 1: CLI option and mode design

Extend CLI parsing and validation for:

- `-c` / `--compile`,
- `-I` / `--interface-path`,
- `-Ri` (new short alias for the existing `--runtime-include`),
- `-Rl` (new short alias for the existing `--runtime-lib`),
- any internal/testing-only long-form interface-emission mode needed to support Stage 1 development.

This phase should also retire the old runtime-specific meaning of `-I` and `-L` so the option surface stops conflicting
with the new separate-compilation model. The long forms `--runtime-include` / `--runtime-lib` keep working unchanged.

### Phase 2: Compile-only driver flow

Teach the driver/library entry points to compile a single module into generated C, object output, and `.l1m`, with
imported modules loaded through interface discovery rather than always rebuilding the whole closure as one generated C
unit.

### Phase 3: Build/run fan-out orchestration

Update `--build` and `--run` to compute the import closure, compile modules individually, and prepare the later link
stage inputs deterministically.

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

## Verification Criteria

1. `-c` / `--compile` and `-I` / `--interface-path` parse, validate, and participate in the driver as specified.
2. `-Ri` and `-Rl` resolve to `--runtime-include` and `--runtime-lib` respectively, and the old `-I` / `-L` runtime
   short aliases are no longer accepted.
3. `--build` and `--run` preserve current user-facing behavior while compiling module inputs individually internally.
4. Driver tests cover invalid mode combinations, missing interface paths, and successful compile-only flows.
5. Any newly assigned diagnostic codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md`.
