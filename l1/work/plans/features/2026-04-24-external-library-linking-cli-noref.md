# Feature Plan

## Add external-library linking flags to the L1 CLI

- Date: 2026-04-24
- Status: Draft
- Title: Add external-library linking flags to the L1 CLI
- Kind: Feature
- Severity: Medium
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0001-separate-compilation-and-linking.md`
- Subsystem: CLI / build driver / linker integration / docs
- Modules:
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/l1c.l0`
  - `l1/docs/roadmap.md`
  - `l1/docs/reference/design-decisions.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/0001-separate-compilation-and-linking.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 TESTS="cli_args_test build_driver_test driver_test"`

## Summary

Once separate compilation lands, L1 needs a normal external-library linking surface so FFI binding modules can link
against host libraries without bespoke runtime-only flags. This plan adds the conventional linker-facing flags committed
by Initiative `0001`:

- `-l<name>` or `-l <name>`
- `-L<dir>` or `-L <dir>`
- `--rpath=<dir>`
- `--link-arg=<flag>`

It also completes the cleanup that frees `-I` for interface-path lookup rather than raw linker/include-path behavior.

## Current State

1. Current Stage 1 linking is centered on compiling one generated C program plus runtime-path forwarding.
2. Runtime-specific short aliases have moved to `-Ri` / `-Rl`; `-I` is the interface path and `-L` / `-l` are recognized
   as reserved canonical syntax that currently reports the shared `L1C-2032` capability diagnostic.
3. There is no implemented CLI forwarding surface for user-requested external link libraries or runtime search paths.
4. Manual C binding modules cannot yet express their host-library link requirements through the L1 compiler.

## Defaults Chosen

1. `-l`, `-L`, `--rpath`, and `--link-arg` follow host-compiler conventions directly; `-l` / `-L` accept attached and
   following values.
2. `-I` is reserved for interface-file discovery and is not repurposed as a C-header include-path flag in core L1.
3. The compiler forwards external-linking options to the host toolchain rather than abstracting static vs dynamic
   linkage.
4. Manual `extern "C"` binding modules remain the intended workflow; package manifests and automatic dependency metadata
   remain undecided and stay out of scope unless and until Dea adopts a package-management direction.

## Goal

1. Add external-library and rpath flags to the L1 CLI.
2. Forward them through build/link flows deterministically.
3. Replace the reserved `-L` / `-l` capability diagnostic with implemented link-option validation.
4. Document the intended FFI binding plus linker-flags workflow.

## Implementation Phases

### Phase 1: CLI and validation surface

Teach CLI parsing and validation for:

- `-l`,
- `-L`,
- `--rpath`,
- `--link-arg`.

The coordinated CLI-surface tranche has already removed the old runtime meanings and assigned `-Ri` / `-Rl`. This phase
turns the reserved `-L` / `-l` grammar into usable link inputs without changing the runtime-path aliases.

### Phase 2: Link-driver forwarding

Thread the accepted flags through `--link`, `--build`, and `--run` so the final host link invocation receives them in a
deterministic order.

### Phase 3: Docs and smoke coverage

Add user-facing documentation that explains the expected pattern: manual binding module plus explicit library flags,
with platform notes for `.a`, `.so`, `.dylib`, `.lib`, and `.dll` expectations.

## Diagnostics

1. This plan is expected to need diagnostics for invalid linker-option combinations, missing linker-option values, and
   host-link failures attributable to explicit external-library options.
2. Provisionally reserve `L1C-2070` to `L1C-2089` for external-linking CLI and linker-forwarding diagnostics.
3. Re-check the live catalog at implementation time before assigning final numbers. If any proposed slot has been used
   in the meantime, choose a different free block then.

## Non-Goals

1. Package manifests or dependency resolution.
2. Automatic bindgen or C-header parsing.
3. Separate compilation of modules; that is tracked by other plans under the same initiative.
4. Runtime static-library refactoring except where option cleanup overlaps.

## Verification Criteria

1. `-l`, `-L`, `--rpath`, and `--link-arg` parse and validate as specified.
2. Link-involving flows forward the requested flags to the host toolchain deterministically.
3. The roadmap and user docs clearly describe the intended external-linking workflow for FFI modules.
4. Any newly assigned diagnostic codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md`.
