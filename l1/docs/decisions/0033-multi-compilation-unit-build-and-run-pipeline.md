# ADR-0033: Multi-Compilation-Unit Build and Run Pipeline

- Decision date: 2026-08-23
- Last edited: 2026-08-23
- Status: Accepted

## Context

L1 generated-C, compile-only, and standalone link already shared a canonical module graph, per-module backend, verified
interface authority, lifecycle ABI, and common link executor. Build and run still dispatched through the legacy
whole-program generator, so they could not combine source fallback with precompiled providers or foreign objects.

## Decision

L1 `--build` and `--run` use one source-rooted multi-compilation-unit pipeline:

- The requested target resolves from source and expands through the canonical graph under `MRP_ALLOW_SOURCE_FALLBACK`.
  The first selected interface is authoritative; source fallback occurs only when no interface is selected.
- Every source-backed node is generated, fingerprinted, and compiled exactly once under canonical module-relative paths
  in the command-owned private workspace. Deterministic dependency-first order follows each node's ordered direct
  imports.
- An interface-backed node contributes its verified `.l1m` and original opaque sibling `.o`. Dea verifies interface
  identity, fingerprints, operational manifests, object regular-file status, and graph consistency but never reads or
  binds the native bytes. The caller keeps the pair stable from selection through link submission.
- The graph-expanded Dea object set is submitted to the common verified link planner at the requested source operand's
  typed-input position. Repeatable foreign objects remain caller-asserted opaque native inputs and preserve their
  relative declaration order.
- Source-backed nodes are re-analyzed dependency-first as one-module entries before generation. Original `-I` interfaces
  retain precedence, while previously source-backed providers must resolve through their staged workspace `.l1m`; source
  fallback is disabled at this per-unit boundary.
- The requested source target is the explicit entry selection and must carry an eligible `I5entry`; another module's
  bridge cannot substitute. Build/run do not accept `--entry`.
- Wrapper emission, dependency-first initialization, reverse finalization, runtime selection, alias checks, and final
  host linking remain owned by the common link path. Build/run supplies explicit wrapper and capture paths from its
  workspace rather than allocating the standalone link transaction.
- Run launches the temporary executable directly, forwards exact argument words after `--`, returns the program status,
  and cleans the executable with the workspace. Launch failure is distinct from a child status.

Any graph, analysis, generation, interface, object-compilation, or common-link validation failure prevents the final
host link and flows through bounded command-workspace cleanup.

## Rationale

- Reusing the graph and link planner keeps provider, fingerprint, entry, lifecycle, runtime, and native-input semantics
  identical across build/run and standalone linking.
- Publication-free compilation prevents convenience commands from overwriting caller compile-only artifacts.
- Explicit source-target entry selection removes ambiguity when multiple linked modules define eligible `main`
  functions.
- Direct process launch preserves argument boundaries and makes launch failure distinguishable without shell quoting.

## Consequences

- Build/run can mix source-backed modules, authoritative `.l1m + .o` providers, and foreign relocatables.
- Compile-only endpoint rollback is not a reader snapshot; callers must externally serialize interface/object pairs
  against publication and replacement.
- Parallel compilation, caching, package manifests, external libraries, and raw host-link arguments remain outside this
  pipeline.
- The generated-C completion work removed the legacy whole-program generator after proving cross-mode module identity.

## Related Plans

- [l1/work/plans/features/closed/2026-07-17-build-run-multi-cu-orchestration-noref.md][build-run]
- [l1/work/plans/features/closed/2026-07-24-per-module-generated-c-mode-noref.md][completion]

## Current Docs

- [docs/specs/compiler/cli-contract.md][cli]: public build/run modes, options, retention, execution, and workspace rules
- [l1/docs/reference/separate-compilation.md][separate-compilation]: graph, provider, lifecycle, and native-input
  contract
- [l1/docs/reference/architecture.md][architecture]: Stage 1 orchestration and ownership flow
- [l1/docs/reference/c-backend-design.md][backend]: per-module generation and common wrapper boundary

[architecture]: ../reference/architecture.md
[backend]: ../reference/c-backend-design.md
[build-run]: ../../work/plans/features/closed/2026-07-17-build-run-multi-cu-orchestration-noref.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[completion]: ../../work/plans/features/closed/2026-07-24-per-module-generated-c-mode-noref.md
[separate-compilation]: ../reference/separate-compilation.md
