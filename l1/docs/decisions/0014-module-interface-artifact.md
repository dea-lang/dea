# ADR-0014: Module Interface Artifact

- Decision date: 2026-06-13
- Last edited: 2026-07-20
- Status: Accepted

## Context

L1 separate compilation needs an artifact that describes one module's exported public surface without requiring
importers to reparse the provider implementation source. The first shippable tranche needs this artifact to be
deterministic and testable before later driver work makes `.l1m` files normal compile inputs.

## Decision

L1 uses a textual `.l1m` module interface artifact with a constrained source-like grammar:

- The file starts with `module interface <dotted-module-name>;` and a required `fingerprint "<hash>";` line.
- Exported structs, enums, type aliases, function signatures, consts, and top-level lets are emitted in canonical
  declaration-group order.
- Every exported declaration currently carries a `== "<hash>";` suffix and emits an empty placeholder. The planned
  whole-module fingerprint migration removes these declaration suffixes instead of populating them.
- Surface-tier dependency lines use `require <module>::<symbol> == "<hash>";`.
- Implementation-tier dependency lines use `link <module>::<symbol> == "<hash>";`.
- Interface projection classifies resolved public-surface provider uses as `require` and remaining implementation uses
  as `link`; a symbol present in both appears only in `require`.
- The source `export` manifest is not emitted; its effect is represented by which declarations appear in the interface.

The Stage 1 compiler can emit the artifact through the internal `--emit-interface` mode and can parse it back through a
dedicated constrained parser. Resolution-aware internal entry points can discover interfaces from ordered roots and load
transitive `require` / `link` closure through the canonical module graph. Ordinary `--build`, `--run`, and CLI source
import analysis remain source-based in this tranche.

## Rationale

- Textual, source-like interfaces are easy to inspect, diff, and round-trip during bootstrap.
- Canonical declaration order gives deterministic artifacts before hash verification exists.
- The dedicated module fingerprint and dependency hash slots support the planned whole-module verification contract;
  declaration hash slots are transitional and are retired by that migration.
- Separating `require` from `link` lets later tranches distinguish public-surface typechecking dependencies from
  implementation-only link dependencies.
- Keeping graph-backed interface discovery behind internal APIs prevents a half-complete CLI surface from producing
  artifacts without provider objects, lifecycle records, or fingerprint verification.

## Consequences

- Signature metadata must preserve enum variant field names so interfaces can round-trip named payload fields.
- Interface parsing has its own diagnostics for malformed `.l1m` syntax.
- Graph-backed transitive replay is available through internal analysis entry points. Later tranches must add
  fingerprint verification, compile-only artifact publication, provider-object metadata and linking, and multi-CU
  build/run orchestration before `.l1m` files become a complete user-facing separate-compilation workflow.

## Related Plans

- [l1/work/plans/features/closed/2026-04-24-module-interface-emission-noref.md][interface-plan]
- [l1/work/plans/features/closed/2026-04-24-separate-compilation-driver-surface-noref.md][driver-plan]
- [l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md][graph-plan]
- [l1/work/plans/features/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md][fingerprints-plan]
- [l1/work/plans/features/2026-07-17-object-metadata-emission-and-readers-noref.md][metadata-plan]

## Related Initiatives

- [l1/work/initiatives/0001-separate-compilation-and-linking.md][initiative]: broader rollout (open)

## Current Docs

- [l1/docs/specs/compiler/module-interface-format.md][format-spec]: textual `.l1m` artifact format
- [l1/docs/specs/compiler/module-visibility-and-imports.md][visibility-spec]: export surface feeding interface emission
- [docs/specs/compiler/diagnostic-code-catalog.md][diagnostic-catalog]: registered `.l1m` parser and discovery
  diagnostics

[diagnostic-catalog]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[driver-plan]: ../../work/plans/features/closed/2026-04-24-separate-compilation-driver-surface-noref.md
[fingerprints-plan]: ../../work/plans/features/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[format-spec]: ../specs/compiler/module-interface-format.md
[graph-plan]: ../../work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[initiative]: ../../work/initiatives/0001-separate-compilation-and-linking.md
[interface-plan]: ../../work/plans/features/closed/2026-04-24-module-interface-emission-noref.md
[metadata-plan]: ../../work/plans/features/2026-07-17-object-metadata-emission-and-readers-noref.md
[visibility-spec]: ../specs/compiler/module-visibility-and-imports.md
