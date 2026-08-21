# ADR-0018: Canonical Artifact Association and Module Graph

- Decision date: 2026-07-19
- Last edited: 2026-08-21
- Status: Accepted

## Context

Direct `.l1m` replay originally depended on callers supplying one dependency-free provider interface. That boundary
could not support separate compilation: it had no filesystem discovery policy, transitive interface closure, canonical
association between one module and its artifacts, or representation of ordered source imports alongside interface
dependency manifests.

Later compile-only, standalone-linking, and build/run tranches need one deterministic model for those concerns without
making any of those user-facing modes operational prematurely.

## Decision

L1 uses the canonical dotted module name as the identity of a separate-compilation node and its artifact set:

- Replacing dots with path separators produces the relative artifact stem. `foo.bar` maps to sibling `foo/bar.c`,
  `foo/bar.o`, and `foo/bar.l1m` paths beneath a caller-selected artifact root.
- An explicit compile-only output must be a regular `.o` path; replacing only its final suffix selects the `.c` and
  `.l1m` companions.
- Source paths, import aliases, and search-root spellings do not participate in artifact identity.

The association exposes every possible companion path without requiring every file to exist. The reusable
separate-compilation set is `.o` plus `.l1m`; compile-only publishes the associated `.c` only when `--keep-c` is
selected.

The module graph records one selected origin per canonical module: source, filesystem interface, supplied-interface
registry, or compiler-synthesized virtual module. Canonical graph enumeration is sorted by module name, while each
source node separately preserves its direct imports in declaration order, including duplicates.

Imported modules use interface-first resolution. Ordered interface roots are searched for the dotted relative `.l1m`
path, and the first existing candidate is authoritative. A malformed, unreadable, or header-mismatched selected
interface fails instead of falling back to source. If no interface exists, the caller chooses either
`MRP_REQUIRE_INTERFACE` or `MRP_ALLOW_SOURCE_FALLBACK`; source fallback retains the existing
system-roots-before-project-roots precedence.

The graph closes over every `.l1m` operational provider view. `require` activates provider interfaces for semantic
replay; `link` retains an implementation dependency obligation without opening provider names into the consumer's
semantic environment. Ordered lifecycle imports preserve direct source-import order and side-effect-only providers.
Standalone linking requires each non-virtual semantic provider to be transitively reachable through those lifecycle
imports without deriving lifecycle edges from `require` or `link`.

## Rationale

- Canonical module identity prevents filesystem spelling and import aliases from producing competing artifacts.
- First-root-wins interface selection makes repeated `-I` options deterministic and matches ordinary search-path
  expectations.
- Treating a selected interface as authoritative prevents corrupt or stale artifacts from being hidden by source
  fallback.
- Separate semantic, link, and ordered-import dependency views preserve the information needed by type checking, object
  selection, and future lifecycle ordering.
- A shared internal graph lets compile-only and build/run choose different fallback policies without duplicating module
  discovery.

## Consequences

- The graph and artifact association are shared by internal analysis, compile-only publication, and standalone linking;
  ordinary `--build` and `--run` remain source-based single-CU operations.
- Interface cycles and source cycles share one canonical module-chain policy; cached nodes are not cycles, and failed
  nodes are not committed as resolved.
- Whole-module fingerprints and operational provider expectations are validated before an interface enters the graph.
  The verified sibling interface, rather than native object metadata, is authoritative during standalone linking.

## Related Plans

- [l1/work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md][interface-authority]
- [l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md][graph-plan]
- [l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md][fingerprints]
- [l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md][compile-only]
- [l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md][object-metadata]
- [l1/work/plans/features/2026-07-17-build-run-multi-cu-orchestration-noref.md][build-run]

## Current Docs

- [l1/docs/specs/compiler/module-interface-format.md][module-format]: dependency tiers, discovery, and closure rules
- [l1/docs/reference/architecture.md][architecture]: Stage 1 graph and analysis data flow
- [l1/docs/project-status.md][project-status]: implemented Stage 1 graph and compile-only boundary
- [docs/specs/compiler/diagnostic-code-catalog.md][diagnostic-catalog]: interface discovery diagnostics

[architecture]: ../reference/architecture.md
[build-run]: ../../work/plans/features/2026-07-17-build-run-multi-cu-orchestration-noref.md
[compile-only]: ../../work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md
[diagnostic-catalog]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[fingerprints]: ../../work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[graph-plan]: ../../work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[interface-authority]: ../../work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md
[module-format]: ../specs/compiler/module-interface-format.md
[object-metadata]: ../../work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md
[project-status]: ../project-status.md
