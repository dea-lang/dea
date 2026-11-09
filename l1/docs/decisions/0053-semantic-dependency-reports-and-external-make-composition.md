# ADR-0053: Semantic Dependency Reports and External Make Composition

- Decision date: 2026-11-05
- Last edited: 2026-11-09
- Status: Accepted

## Context

Strict compile-only analysis needs provider interfaces before compiling consumers. A clean external build therefore
needs semantic discovery before those generated interfaces exist. The canonical resolver already knows selected
providers, source imports, interface closure and dependency order. Duplicating that resolver in a build tool would risk
different provider authority and incomplete prerequisites.

## Decision

L1 `--scan-deps MODULE --artifact-root BUILD` exposes P1689R5 version 1, revision 0. Each selected source module
contributes its future object/interface pair and all interface prerequisites in core fields. Prebuilt providers remain
requirements; virtual modules have no filesystem artifacts. Optional vendor annotations carry no essential scheduling
information. Scans do not construct native support, invoke native tools or consult managed native caches.

An optional Python standard-library adapter validates the report and emits explicit GNU Make 4.3 grouped actions. The
invoking project owns recipes, native inputs, configuration stamps, output destinations, freshness and execution. It
runs discovery and adaptation before each inner build under one generated-root lock. Unchanged fragments retain their
timestamps; changed graphs conservatively invalidate all source actions and the final link. Missing output peers rebuild
both members of a compile pair.

Discovery receives project sources and intentional prebuilt interface roots. Compilation appends the generated-interface
root only after checking that it has no canonical candidates for selected prebuilt providers. The adapter rejects such
conflicts, including unusable paths and aliases, instead of deleting artifacts or reproducing resolver precedence.
Interface-first authority remains unchanged.

Standalone `--link` retains `.l1m` authority for fingerprints, provider consistency and lifecycle order. The caller
passes the scanned canonical module explicitly as `--entry`; report order never selects the executable entry.

## Rationale

- A neutral report separates compiler facts from build execution without adding a second source parser.
- Complete core requirements allow consumers to discard annotations safely, including closure through prebuilt and
  link-only providers.
- Fresh scans plus conservative fragment invalidation observe provider additions, removals and older replacement inputs
  without introducing a persistent incremental database or a negative-lookup protocol.
- Separate input sets preserve the established resolver contract and prevent stale generated interfaces from hiding
  source edits during discovery.
- Explicit grouped actions preserve the compiler's two-output publication boundary under parallel Make execution.

## Consequences

P1689 compatibility does not imply automatic CMake integration, ISO standardization, complete native dependency
discovery, or a record of actual consumed compilation inputs. The adapter is optional repository tooling; installed
compiler use adds no Python or Make runtime requirement. Native headers, libraries, foreign inputs and
configuration/profile changes remain caller-owned prerequisites. Timestamp-based rebuilding may conservatively recompile
unchanged public interfaces.

This decision does not change production compiler/stdlib builds, the L0 bootstrap, L2, arbitrary output mappings or
retained-C discovery. Initiative completion still requires its separately recorded platform validation.

## Related Plans

- [l1/work/plans/features/closed/2026-10-21-semantic-dependency-discovery-noref.md][plan]

## Current Docs

- [l1/docs/reference/dependency-discovery.md][discovery]
- [l1/docs/reference/separate-compilation.md][compilation]
- [docs/specs/compiler/cli-contract.md][cli]

[cli]: ../../../docs/specs/compiler/cli-contract.md
[compilation]: ../reference/separate-compilation.md
[discovery]: ../reference/dependency-discovery.md
[plan]: ../../work/plans/features/closed/2026-10-21-semantic-dependency-discovery-noref.md
