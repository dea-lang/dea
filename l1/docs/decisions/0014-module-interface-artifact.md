# ADR-0014: Module Interface Artifact

- Decision date: 2026-06-13
- Last edited: 2026-06-13
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
- Every exported declaration carries a `== "<hash>";` suffix. Empty hashes are valid placeholders until fingerprint
  verification lands.
- Surface-tier dependency lines use `require <module>::<symbol> == "<hash>";`.
- Implementation-tier dependency lines use `link <module>::<symbol> == "<hash>";`, but semantic population of `link`
  entries is deferred to build/run fan-out work.
- The source `export` manifest is not emitted; its effect is represented by which declarations appear in the interface.

The Stage 1 compiler can emit the artifact through the internal `--emit-interface` mode and can parse it back through a
dedicated constrained parser. Ordinary `--build`, `--run`, and source import analysis remain source-based in this
tranche.

## Rationale

- Textual, source-like interfaces are easy to inspect, diff, and round-trip during bootstrap.
- Canonical declaration order gives deterministic artifacts before hash verification exists.
- Reserving fingerprint and per-symbol hash slots avoids changing the file grammar when verification lands.
- Separating `require` from `link` lets later tranches distinguish public-surface typechecking dependencies from
  implementation-only link dependencies.
- Keeping interface discovery out of ordinary imports prevents a half-complete driver surface from producing unresolved
  provider symbols.

## Consequences

- Signature metadata must preserve enum variant field names so interfaces can round-trip named payload fields.
- Interface parsing has its own diagnostics for malformed `.l1m` syntax.
- Later tranches must implement interface-backed import replay, transitive interface closure, fingerprint verification,
  and provider-object linking before `.l1m` files become a complete user-facing separate-compilation workflow.

## Related Plans

- [l1/work/plans/features/closed/2026-04-24-module-interface-emission-noref.md][interface-plan]
- [l1/work/plans/features/2026-04-24-separate-compilation-driver-surface-noref.md][driver-plan]
- [l1/work/plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md][fingerprints-plan]

## Related Initiatives

- [l1/work/initiatives/0001-separate-compilation-and-linking.md][initiative]: broader rollout (open)

## Current Docs

- [l1/docs/specs/compiler/module-interface-format.md][format-spec]: textual `.l1m` artifact format (Version 2026-06-13)
- [l1/docs/specs/compiler/module-visibility-and-imports.md][visibility-spec]: export surface feeding interface emission
- [docs/specs/compiler/diagnostic-code-catalog.md][diagnostic-catalog]: registered `.l1m` parser diagnostics

[diagnostic-catalog]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[driver-plan]: ../../work/plans/features/2026-04-24-separate-compilation-driver-surface-noref.md
[fingerprints-plan]: ../../work/plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md
[format-spec]: ../specs/compiler/module-interface-format.md
[initiative]: ../../work/initiatives/0001-separate-compilation-and-linking.md
[interface-plan]: ../../work/plans/features/closed/2026-04-24-module-interface-emission-noref.md
[visibility-spec]: ../specs/compiler/module-visibility-and-imports.md
