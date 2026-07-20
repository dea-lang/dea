# Bug Fix Plan

## Harden Stage 1 module-interface resolution

- Date: 2026-07-20
- Status: Completed
- Title: Harden Stage 1 module-interface resolution
- Kind: Bug Fix
- Severity: High
- Stage: 1
- Subsystem: Module graph / interface replay / signature and expression type resolution
- Parent Initiative: [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative-0001]
- Roadmap: [`l1/docs/roadmap.md`][roadmap]
- Modules:
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/compiler/stage1_l0/src/module_graph.l0`
  - `l1/compiler/stage1_l0/src/signatures.l0`
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/compiler/stage1_l0/src/types.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/analysis.l0`
- Test modules:
  - `l1/compiler/stage1_l0/tests/source_paths_test.l0`
  - `l1/compiler/stage1_l0/tests/module_graph_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_replay_test.l0`
  - `l1/compiler/stage1_l0/tests/signatures_test.l0`
  - `l1/compiler/stage1_l0/tests/type_resolve_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
- Related:
  - [`l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md`][artifact-graph]
  - [`l1/docs/specs/compiler/module-interface-format.md`][interface-format]
  - [`docs/specs/compiler/diagnostic-code-catalog.md`][diagnostic-catalog]
- Repro: `make -C l1 test-stage1 TESTS="expr_types_test interface_test interface_replay_test signatures_test"`

## Summary

Stage 1 currently has three interface-resolution gaps: qualified `sizeof` bypasses the shared import-aware symbol
lookup, transparent aliases do not reliably materialize across interface and source-backed providers, and an interface
surface can name a provider reachable only through its implementation-tier `link` closure. These defects can reject
valid programs, accept invalid visibility or qualification, or allow an interface that cannot be type-checked from its
declared semantic dependencies.

## Root Cause

The `sizeof` type-name path performs its own qualified lookup and dependency recording instead of using the semantic
lookup choke point. Interface parser types are materialized before all provider aliases and nominal kinds are known,
while signature resolution does not revisit every semantic type copy after source signatures are available. Finally,
resolution loads both dependency tiers into one graph, but interface-surface validation does not distinguish the
transitive `require` closure from the broader link closure.

## Scope of This Fix

1. Route `sizeof` type-name resolution through the shared import-aware symbol lookup and record only successful semantic
   uses.
2. Finalize materialized semantic types after source signature resolution, including nested wrappers, function types,
   cross-provider nominal kinds, and transparent aliases, while preserving alias-cycle diagnostics.
3. Validate every interface surface against its transitive semantic closure: interface `require` edges and source direct
   imports are traversed, while `link` edges are excluded.
4. Register `RES-0040` for interface surfaces that reference a provider outside that semantic closure.
5. Consolidate adjacent driver recursion and dependency-loop plumbing, centralize interface-root selection, and remove
   unreachable projection fallbacks without changing the `.l1m` wire format.

## Non-Goals

- Projecting source-backed providers into synthetic peer interfaces.
- Building a new nominal-kind index or redesigning parser normalization.
- Replacing pre-node failure caching with graph placeholder nodes.
- Consolidating module-graph pointer vectors, removing object-artifact construction, or changing node-state accessors.
- Changing CLI behavior, artifact syntax, dependency fingerprints, or link orchestration.

## Verification Criteria

1. Alias-qualified exported types work in `sizeof` and emit the canonical provider as a `link` dependency; illegal
   canonical qualification and private qualified types retain their dedicated diagnostics.
2. Interface-backed and source-backed aliases, nested mixed chains, enum payload aliases, and cross-interface cycles
   resolve or fail correctly without changing raw projection spelling.
3. Surface types reachable only through `link` fail with `RES-0040`, while equivalent transitive `require` closures and
   source direct-import closures succeed.
4. Entry-source selection, first-root authority, cycles, missing-provider diagnostic deduplication, and complete graph
   edge retention remain covered.
5. Focused normal and trace suites plus the complete L1 suite pass.

## Resolution

Qualified `sizeof` type names now use the same import-aware lookup target and semantic-use ledger as ordinary symbol
resolution. Exported types resolve through import aliases, canonical names remain unavailable after alias-only or
selective imports, and private qualified types retain their dedicated diagnostics without recording failed uses.

Signature processing now performs a ledger-neutral materialization pass after source signatures are available. It
recursively finalizes wrappers and function types, resolves nominal kinds, expands source- and interface-backed
transparent aliases, detects alias cycles before consulting cached targets, and updates semantic interfaces, name
resolution symbols, and signature tables. Raw graph and projected interface types remain unchanged. Exact source shape
checks retain their declaration-local types, and duplicate declarations skip noncanonical signature insertion so traced
error recovery does not orphan overwritten signature objects.

Each interface surface is validated against the module graph's semantic closure. Interface nodes traverse only `require`
edges, source nodes traverse direct imports, and `link` edges never make a surface provider semantically available.
Violations report the catalogued `RES-0040` diagnostic.

Driver recursion now carries a borrowed resolution context, derives entry-source selection from `state.entry_module`,
and shares one non-short-circuiting dependency loop for registry and filesystem interfaces. Interface-root selection is
centralized in `source_paths`, the pre-node failure cache has a scope-specific name, and source projection retains the
resolved-type fallback only for inferred exported bindings. The CLI and `.l1m` wire format are unchanged.

## ADR Note

No new ADR is expected. The fix enforces the existing semantic distinction between `require` and `link` recorded by the
separate-compilation architecture and [interface-format contract][interface-format]; it does not introduce a new public
or wire-level decision.

## Verification

```bash
./.venv/bin/pytest l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py -q
make -C l1 test-stage1 TESTS="source_paths_test module_graph_test driver_test analysis_test interface_test interface_replay_test signatures_test type_resolve_test expr_types_test backend_test c_emitter_test"
make -C l1 test-stage1-trace TESTS="source_paths_test module_graph_test driver_test analysis_test interface_test interface_replay_test signatures_test type_resolve_test expr_types_test backend_test c_emitter_test"
make -C l1 clean test-all
```

Results:

- The shared diagnostic catalog check passed all 259 tests.
- All 11 focused normal suites passed.
- All 11 focused trace suites passed without ARC or memory leaks.
- The clean full gate passed all 54 Stage 1 suites and all 38 default trace suites.
- Environment stackability and all four L1 example checks passed.

[artifact-graph]: ../../features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[diagnostic-catalog]: ../../../../../docs/specs/compiler/diagnostic-code-catalog.md
[initiative-0001]: ../../../initiatives/0001-separate-compilation-and-linking.md
[interface-format]: ../../../../docs/specs/compiler/module-interface-format.md
[roadmap]: ../../../../docs/roadmap.md
