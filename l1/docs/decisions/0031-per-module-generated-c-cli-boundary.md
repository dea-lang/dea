# ADR-0031: Per-Module Generated-C CLI Boundary

- Decision date: 2026-08-21
- Last edited: 2026-08-23
- Status: Accepted

## Context

L1 already had a target-aware backend operation for compile-only, but public `--gen` still emitted the legacy complete
source closure with a process wrapper. Build/run fan-out needs a path-independent operation that returns one module's C
bytes without invoking compile-only publication or any host tool. Pure generation also needs to consume verified module
interfaces without treating their native siblings as inputs.

## Decision

L1 `l1c --gen MODULE [-I ROOT]... [-o FILE]` resolves `MODULE` from source and emits exactly one per-module C
translation unit through `backend_generate_module(...)`. The target must have an implementation body; an interface-only
target is invalid.

Imports resolve interface-first under `MRP_ALLOW_SOURCE_FALLBACK`. Ordered interface roots select the first existing
`.l1m`; a selected valid interface is sufficient without a sibling `.o` or `.c`, and a malformed selected interface
fails authoritatively. Source fallback occurs only when no interface is selected.

The output contains target definitions, required imported declarations and transparent types, always-present `I4init`
and `I4fini`, and conditional `I5entry`. It contains no imported definitions, dependency lifecycle calls, process
`main`, executable wrapper, embedded interface text, or native metadata.

Without `-o`, generated C is written to stdout. With `-o`, the value is the exact single output path. Pure generation
creates no companion artifacts and does not discover objects, invoke the host compiler, or invoke the linker.
`cg_options_from_cli(...)` supplies the shared byte-affecting settings used by both `--gen` and compile-only, so `--gen`
output and `-c --keep-c` output are byte-identical for identical resolved inputs and options.

## Rationale

- One backend operation prevents CLI and compile-only generation from drifting.
- Interface-first imports make generated C usable with separately compiled providers without coupling pure generation to
  provider native artifacts.
- An exact one-file/stdout contract keeps `--gen` composable and distinct from build orchestration.
- Keeping process-wrapper ownership in standalone link preserves the per-module lifecycle ABI.

## Consequences

- Existing callers that relied on L1 `--gen` producing a whole source closure must generate or compile modules
  separately and link them through the separate-compilation path.
- Generated utility modules contain lifecycle definitions but no `I5entry`; eligible entry modules additionally contain
  `I5entry`, while neither form contains process `main`.
- `--build` and `--run` use the module generator once per source-backed graph node; their retained trees copy those
  exact bytes, while the downstream completion plan owns legacy-generator removal and the final four-mode proof.
- The downstream generated-C completion plan can remove the legacy generator only after build/run migrates.

## Related Plans

- [l1/work/plans/features/closed/2026-08-21-per-module-generated-c-foundation-noref.md][foundation]
- [l1/work/plans/features/closed/2026-07-17-build-run-multi-cu-orchestration-noref.md][build-run]

## Current Docs

- [docs/specs/compiler/cli-contract.md][cli]: public mode, resolution, and output behavior
- [l1/docs/reference/c-backend-design.md][backend]: shared per-module generation operation and output layout
- [l1/docs/reference/separate-compilation.md][separate-compilation]: generated-C relationship to compile and link
- [l1/docs/reference/architecture.md][architecture]: Stage 1 dispatch and module-graph flow

[architecture]: ../reference/architecture.md
[backend]: ../reference/c-backend-design.md
[build-run]: ../../work/plans/features/closed/2026-07-17-build-run-multi-cu-orchestration-noref.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[foundation]: ../../work/plans/features/closed/2026-08-21-per-module-generated-c-foundation-noref.md
[separate-compilation]: ../reference/separate-compilation.md
