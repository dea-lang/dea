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
  - `docs/specs/compiler/cli-contract.md`
  - `l1/docs/roadmap.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/user/linking.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/0001-separate-compilation-and-linking.md`
  - `l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md`
  - `l1/work/plans/features/2026-07-17-build-run-multi-cu-orchestration-noref.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 TESTS="cli_args_test build_driver_test driver_test"`

## Summary

Once the standalone link-set and build/run fan-out plans land, L1 needs a normal external-library surface so binding
modules can link against host libraries without bespoke runtime-only flags. This final Initiative `0001` tranche adds:

- `-l<name>` or `-l <name>`
- `-L<dir>` or `-L <dir>`
- `-Rr=<dir>` / `--rpath=<dir>`
- `-Cl=<flag>` / `--link-arg=<flag>`

It extends the typed ordered input stream already established for verified-interface/opaque-object Dea pairs and
explicit caller-asserted `--foreign-object` C relocatables. It also completes the cleanup that frees `-I` for
interface-path lookup rather than raw linker/include-path behavior.

## Current State

1. Current Stage 1 linking is centered on compiling one generated C program plus runtime-path forwarding.
2. Runtime-specific short aliases have moved to `-Ri` / `-Rl`; `-I` is the interface path and `-L` / `-l` are recognized
   as reserved canonical syntax that currently reports the shared `L1C-2032` capability diagnostic.
3. There is no implemented CLI forwarding surface for user-requested external link libraries or runtime search paths.
4. Manual C binding modules cannot yet express their host-library link requirements through the L1 compiler.
5. Standalone `--link`, ordered object inputs, and repeatable `--foreign-object` are prerequisites owned by the link-set
   plan; build/run propagation is owned by the following fan-out plan.

## Defaults Chosen

1. `-l`, `-L`, `-Rr` / `--rpath`, and `-Cl` / `--link-arg` follow the shared CLI contract; `-l` / `-L` accept attached
   and following values, while the namespaced aliases accept following or `=VALUE` forms.
2. `-I` is reserved for interface-file discovery and is not repurposed as a C-header include-path flag in core L1.
3. The driver preserves declaration order for order-sensitive objects, libraries, and raw arguments rather than sorting
   inputs by category. `--link-arg` contributes one host compiler-driver argument; it is not implicitly rewritten as a
   native-linker argument.
4. `--rpath` is translated for each supported compiler family; unsupported host/platform combinations receive a driver
   diagnostic rather than an invented spelling.
5. The already selected runtime link inputs are passed by exact path so user `-L` entries cannot shadow them: one
   selected archive for normal families, or the complete variant-matched TinyCC raw-object set when available with
   archive fallback.
6. Existing legacy `extern func` binding modules are the workflow available when this plan lands. Initiative `0003`
   later adds `extern "C"`; package manifests and automatic dependency metadata stay out of scope.
7. `--link-arg` cannot substitute for the typed object surfaces. A direct relocatable-object operand is rejected with
   guidance to use a positional Dea `.o` with its sibling `.l1m`, or `--foreign-object` for one caller-asserted foreign
   relocatable. Opaque response-file indirection remains outside the supported contract. Archive and shared-library
   operands remain valid external-library inputs.
8. Dea does not inspect native object bytes for embedded linker controls. Libraries, search paths, rpaths, and raw
   arguments must enter through this plan's explicit typed CLI surface for supported use, while any controls hidden in
   caller-supplied native bytes are outside Dea validation and may be accepted or rejected by the host toolchain.

## Goal

1. Add external-library and rpath flags to the L1 CLI.
2. Add them to the common ordered link-input model used by `--link`, `--build`, and `--run`.
3. Replace the reserved `-L` / `-l` capability diagnostic with implemented link-option validation.
4. Document the intended FFI binding plus linker-flags workflow.

## Implementation Phases

### Phase 1: CLI and validation surface

Teach CLI parsing and validation for:

- `-l`,
- `-L`,
- `-Rr` / `--rpath`,
- `-Cl` / `--link-arg`.

The coordinated CLI-surface tranche has already removed the old runtime meanings and assigned `-Ri` / `-Rl`. This phase
turns the reserved `-L` / `-l` grammar into usable link inputs without changing the runtime-path aliases.

### Phase 2: Link-driver forwarding

Thread the accepted flags through `--link`, `--build`, and `--run` using the common typed input stream. Preserve the
user's order across Dea objects, `--foreign-object` operands, libraries, and raw host-driver arguments wherever order is
semantically observable. Translate rpath values per supported compiler family and pass the validated runtime link inputs
by exact path: one selected archive for normal families, or the complete variant-matched TinyCC raw-object set when
available with archive fallback. Validate raw host-driver arguments before invocation so direct relocatable-object
operands retain their typed CLI role and response-file indirection remains outside the supported contract.

### Phase 3: Docs and smoke coverage

Add user-facing documentation that first describes today's legacy `extern func` binding module plus explicit foreign
objects/libraries, then points to Initiative `0003` for the future typed `extern "C"` surface. Include platform notes
for `.o`, `.obj`, `.a`, `.so`, `.dylib`, `.lib`, and `.dll` expectations.

## Diagnostics

1. This plan is expected to need diagnostics for invalid linker-option combinations, missing linker-option values, and
   host-link failures attributable to explicit external-library options.
2. Provisionally reserve `L1C-2070` to `L1C-2089` for external-linking CLI and linker-forwarding diagnostics.
3. Re-check the live catalog at implementation time before assigning final numbers. If any proposed slot has been used
   in the meantime, choose a different free block then.

## ADR Impact

- Decision: Expose external-library inputs through the shared `-l`, `-L`, `-Rr` / `--rpath`, and `-Cl` / `--link-arg`
  CLI spellings.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: The shared CLI ADR owns option naming, repeatability, validation, and level-extension rules.
- Decision: Treat external libraries, C objects, and raw linker arguments as ordered CLI-only link inputs outside Dea
  module identity, without package or per-module dependency manifests.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Input ordering and dependency ownership constrain `--link`, `--build`, `--run`, FFI bindings, and any
    future package-metadata design.

## Non-Goals

1. Package manifests or dependency resolution.
2. Automatic bindgen or C-header parsing.
3. Separate compilation of modules; that is tracked by other plans under the same initiative.
4. Runtime static-library refactoring except where option cleanup overlaps.

## Verification Criteria

1. `-l`, `-L`, `-Rr` / `--rpath`, and `-Cl` / `--link-arg` parse and validate as specified.
2. Link-involving flows forward the requested flags to the host toolchain deterministically.
3. Mixed Dea objects, explicit foreign objects, libraries, rpaths, and raw host-driver arguments retain the documented
   order, and user search paths cannot shadow the validated runtime link inputs.
4. A direct relocatable object supplied through `--link-arg` fails with typed-operand guidance, and response-file
   indirection remains outside the supported contract. Archives and shared libraries remain valid external inputs.
5. Native object bytes are never inspected for linker-control carriers; explicitly typed options remain the supported
   way to request libraries and raw host arguments, and hidden controls are left to host-tool behavior.
6. The roadmap and user docs distinguish the currently usable `extern func` workflow from future `extern "C"` support.
7. Any newly assigned diagnostic codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md`.
