# Feature Plan

## Add external-library linking flags to the L1 CLI

- Date: 2026-08-30
- Status: Completed
- Title: Add external-library linking flags to the L1 CLI
- Kind: Feature
- Severity: Medium
- Stage: L1
- Parent Initiative: `l1/work/initiatives/closed/0001-separate-compilation-and-linking.md`
- Subsystem: CLI / build driver / linker integration / docs
- Modules:
  - `README.md`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/link_driver.l0`
  - `docs/specs/compiler/cli-contract.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - `docs/decisions/0003-shared-cli-contract.md`
  - `docs/project-status.md`
  - `l1/README.md`
  - `l1/compiler/stage1_l0/README.md`
  - `l1/docs/README.md`
  - `l1/docs/roadmap.md`
  - `l1/docs/decisions/0033-multi-compilation-unit-build-and-run-pipeline.md`
  - `l1/docs/decisions/0036-ordered-external-link-inputs-and-cli-only-dependency-ownership.md` (new)
  - `l1/docs/decisions/INDEX.md`
  - `l1/docs/project-status.md`
  - `l1/docs/reference/architecture.md`
  - `l1/docs/reference/c-backend-design.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/reference/separate-compilation.md`
  - `l1/docs/specs/compiler/module-interface-format.md`
  - `l1/docs/user/linking.md`
  - `l1/work/initiatives/closed/0001-separate-compilation-and-linking.md`
  - `l1/work/initiatives/0003-c-ffi.md`
  - `l1/work/plans/bug-fixes/closed/2026-07-27-stage1-standalone-link-hardening-noref.md`
  - `l1/work/plans/features/closed/2026-04-24-c-ffi-extern-c-and-cstr-noref.md`
  - `l1/work/plans/features/closed/2026-07-17-build-run-multi-cu-orchestration-noref.md`
  - `l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md`
  - `l1/work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md`
  - `work/plans/features/closed/2026-07-28-shared-compiler-short-option-aliases-noref.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_build_run_multi_cu_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_help_output_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_link_set_test.py`
  - `l1/compiler/stage1_l0/tests/link_driver_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/closed/0001-separate-compilation-and-linking.md`
  - `l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md`
  - `l1/work/plans/features/closed/2026-07-17-build-run-multi-cu-orchestration-noref.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro:
  `make -C l1 test-stage1 TESTS="build_driver_test cli_args_test link_driver_test l1c_stage1_build_run_multi_cu_test l1c_stage1_help_output_test l1c_stage1_link_set_test"`

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
   relocatable. Object-suffixed `-l` values and raw linker payload segments are rejected as the same role violation.
   Opaque response, file-list, and driver-config indirection remains outside the supported contract. Archive and
   shared-library operands remain valid external-library inputs.
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
operands retain their typed CLI role and opaque option-file indirection remains outside the supported contract.

### Phase 3: Docs and smoke coverage

Add user-facing documentation that first describes today's legacy `extern func` binding module plus explicit foreign
objects/libraries, then points to Initiative `0003` for the future typed `extern "C"` surface. Include platform notes
for `.o`, `.obj`, `.a`, `.so`, `.dylib`, `.lib`, and `.dll` expectations.

## Diagnostics

1. `L1C-2070` reports external-link options used outside `--build`, `--link`, and `--run`.
2. `L1C-2071` reports a library/raw link input that attempts to supply a relocatable object or opaque option-file
   indirection.
3. `L1C-2072` reports an external-link control unsupported or not losslessly representable by the selected host
   platform, compiler family, or value, including canonical `-l` / `-L` under MSVC.
4. Missing values continue to use shared `L1C-2003`; captured host-link failures retain the existing common-link
   diagnostic path.

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
  - ADR: `l1/docs/decisions/0036-ordered-external-link-inputs-and-cli-only-dependency-ownership.md`
  - Rationale: Input ordering and dependency ownership constrain `--link`, `--build`, `--run`, FFI bindings, and any
    future package-metadata design.
- Decision: Extend the multi-compilation-unit build/run pipeline with the common ordered external-link input stream.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0033-multi-compilation-unit-build-and-run-pipeline.md`
  - Rationale: ADR-0033 owns build/run delegation to the common link planner and previously excluded external libraries
    and raw host-driver arguments.

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
4. An object-suffixed library/raw input fails with typed-operand guidance, and response, file-list, and driver-config
   indirection remains outside the supported contract. Archives and shared libraries remain valid external inputs.
5. Native object bytes are never inspected for linker-control carriers; explicitly typed options remain the supported
   way to request libraries and raw host arguments, and hidden controls are left to host-tool behavior.
6. The roadmap and user docs distinguish the currently usable `extern func` workflow from future `extern "C"` support.
7. Any newly assigned diagnostic codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md`.

## Completion Notes

- Added the canonical library, library-search, rpath, and raw host-driver options to the L1 parser and help surface with
  link-mode validation and typed raw-argument rejection.
- Extended the common link plan used by standalone link and build/run so external controls retain encounter order, use
  compiler-family rpath lowering, and precede exact driver-selected runtime inputs.
- Kept external dependencies CLI-owned, preserved opaque native-input handling, and recorded the durable boundary in
  ADR-0036 while amending the shared CLI and multi-CU build/run decisions.
- Added focused parser, help-output, ordering, rpath-family, build/run propagation, Windows preflight, compiler-family,
  typed-object-boundary, and opaque option-file regressions.
- Validation:
  - `make -C l1 test-stage1 TESTS="build_driver_test cli_args_test link_driver_test l1c_stage1_build_run_multi_cu_test l1c_stage1_help_output_test l1c_stage1_link_set_test"`:
    passed 6/6.
  - `make -C l1 clean test-all`: passed 69/69 normal Stage 1 tests, environment stackability, all four examples, and
    44/44 ownership trace tests.
  - `python3 scripts/check_adr_impact.py --all-active`: passed before closure.
