# ADR-0014: Module Interface Artifact

- Decision date: 2026-06-13
- Last edited: 2026-08-21
- Status: Accepted

## Context

L1 separate compilation needs an artifact that describes one module's exported public surface without requiring
importers to reparse the provider implementation source. The first shippable tranche needs this artifact to be
deterministic and testable before later driver work makes `.l1m` files normal compile inputs.

## Decision

L1 uses a textual `.l1m` module interface artifact with a constrained source-like grammar:

- The file starts with `module interface <dotted-module-name>;` and a required canonical
  `fingerprint "sip13:<16 lowercase hexadecimal digits>";` line.
- Exported structs, enums, type aliases, function signatures, consts, and top-level lets are emitted in canonical
  declaration-group order.
- Exported declarations carry no per-symbol compatibility suffix.
- Surface-tier dependency lines use `require <module>::<symbol> == "<provider-whole-module-fingerprint>";`.
- Implementation-tier dependency lines use `link <module>::<symbol> == "<provider-whole-module-fingerprint>";`.
- Operational records use `entry;` for entry presence and ordered
  `import module <provider> == "<provider-whole-module-fingerprint>";` lines for direct lifecycle imports.
- Interface projection classifies resolved public-surface provider uses as `require` and remaining implementation uses
  as `link`; a symbol present in both appears only in `require`.
- The source `export` manifest is not emitted; its effect is represented by which declarations appear in the interface.

The Stage 1 compiler can emit the artifact through the internal `--emit-interface` mode and can parse it back through a
dedicated constrained parser. Resolution-aware internal entry points discover interfaces from ordered roots and load
transitive lifecycle-import, `require`, and `link` closure through the canonical module graph. Standalone link requires
and verifies the canonical sibling interface for each positional Dea object. Ordinary `--build`, `--run`, and CLI source
import analysis remain source-based in this tranche.

The emitter fingerprints the canonical effective public surface. Operational consumers validate the tagged module and
dependency values and recompute the module fingerprint before graph registration or semantic replay.

## Rationale

- Textual, source-like interfaces are easy to inspect, diff, and round-trip during bootstrap.
- Canonical declaration order and length-framed semantic records give deterministic artifacts and unambiguous
  whole-module hash inputs.
- One module fingerprint plus repeated provider-module expectations avoids conflicting per-symbol compatibility values.
- Separating `require` from `link` lets later tranches distinguish public-surface typechecking dependencies from
  implementation-only link dependencies.
- Keeping public declarations separate from operational records preserves one inspectable artifact without making
  lifecycle and entry changes part of public compatibility.

## Consequences

- Signature metadata must preserve enum variant field names so interfaces can round-trip named payload fields.
- Interface parsing has its own diagnostics for malformed `.l1m` syntax.
- Graph-backed transitive replay and interface fingerprint verification are available through internal analysis entry
  points. Compile-only publishes the artifact with its caller-trusted opaque object sibling, and standalone linking uses
  verified interfaces as its sole Dea semantic and lifecycle authority.

## Related Plans

- [l1/work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md][interface-authority]
- [l1/work/plans/features/closed/2026-04-24-module-interface-emission-noref.md][interface-plan]
- [l1/work/plans/features/closed/2026-04-24-separate-compilation-driver-surface-noref.md][driver-plan]
- [l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md][graph-plan]
- [l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md][fingerprints-plan]
- [l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md][metadata-plan]

## Related Initiatives

- [l1/work/initiatives/0001-separate-compilation-and-linking.md][initiative]: broader rollout (open)

## Current Docs

- [l1/docs/specs/compiler/module-interface-format.md][format-spec]: textual `.l1m` artifact format
- [l1/docs/specs/compiler/module-visibility-and-imports.md][visibility-spec]: export surface feeding interface emission
- [docs/specs/compiler/diagnostic-code-catalog.md][diagnostic-catalog]: registered `.l1m` parser, fingerprint, and
  discovery diagnostics

[diagnostic-catalog]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[driver-plan]: ../../work/plans/features/closed/2026-04-24-separate-compilation-driver-surface-noref.md
[fingerprints-plan]: ../../work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[format-spec]: ../specs/compiler/module-interface-format.md
[graph-plan]: ../../work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[initiative]: ../../work/initiatives/0001-separate-compilation-and-linking.md
[interface-authority]: ../../work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md
[interface-plan]: ../../work/plans/features/closed/2026-04-24-module-interface-emission-noref.md
[metadata-plan]: ../../work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md
[visibility-spec]: ../specs/compiler/module-visibility-and-imports.md
