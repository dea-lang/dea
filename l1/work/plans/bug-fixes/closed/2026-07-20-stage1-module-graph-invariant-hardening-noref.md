# Bug Fix Plan

## Harden Stage 1 module-graph invariants

- Date: 2026-07-20
- Status: Completed
- Title: Harden Stage 1 module-graph failure and unit-registry invariants
- Kind: Bug Fix
- Severity: Low
- Stage: 1
- Parent Initiative: [l1/work/initiatives/closed/0001-separate-compilation-and-linking.md][initiative]
- Roadmap: [l1/docs/roadmap.md][roadmap]
- Subsystem: Module graph / source-unit registry / interface projection
- Modules:
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/parser/interface.l0`
- Test modules:
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
- Related:
  - [l1/work/plans/bug-fixes/closed/2026-07-20-stage1-module-interface-resolution-hardening-noref.md][hardening]
  - [l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md][graph]
  - [l1/docs/specs/compiler/module-interface-format.md][interface-format]
- Repro:
  `make -C l1 test-stage1 TESTS="driver_test module_graph_test analysis_test interface_test interface_replay_test signatures_test expr_types_test source_paths_test"`

## Summary

The separate-compilation graph is behaviorally correct under current coverage, but a review found three small invariant
gaps: pre-node failures are cached through repeated raw set writes, source units enter name lookup before their declared
identity is validated, and no test isolates an absent link-only provider under strict interface resolution. Interface
projection also lacks the defensive declaration assertion used by its sibling source-symbol branches.

## Scope of This Fix

1. Centralize pre-node failure caching without creating graph placeholders for providers with no selected origin.
2. Retain failed source-unit shells for ordered ownership and diagnostics, but index units by name only after a present,
   matching module header validates their requested identity.
3. Add strict-policy coverage proving an absent link-only provider remains a graph obligation even when the semantic
   `require` surface resolves.
4. Add the defensive source-let declaration assertion and document the parser-normalization boundary that deliberately
   defers transparent aliases to semantic materialization.
5. Refresh affected live docs and successor-plan policy names without changing the `.l1m`, CLI, or diagnostic contract.

## Non-Goals

- Redesigning nominal-kind lookup, the resolved-symbol ledger, interface dependency deduplication, or interface
  emission.
- Replacing graph activation with a worklist or adding graph placeholder nodes for absent providers.
- Removing module-graph pointer helpers, node-state accessors, or the compile-only object-artifact constructor.
- Adding diagnostics, changing dependency tiers, or making compile-only and multi-CU modes operational.

## Verification Criteria

1. Repeated pre-node failures remain diagnostic-deduplicated and absent providers remain absent from the graph.
2. Header-mismatched source units remain owned for diagnostics but cannot be found through `driver_find_unit`.
3. A clean `require` provider plus an absent link-only provider reports one strict missing-interface diagnostic, retains
   both manifest edges, fails the consumer, and creates no node for the absent provider.
4. Focused normal and trace suites plus the complete normal L1 validation pass without ownership leaks or regressions.
5. Documentation links, formatting, and pre-commit checks pass.

## Resolution

The driver now routes every resolution failure that occurs before graph-node construction through
`dr_fail_without_node`. Its private failure ledger remains separate from graph-node state because invalid or absent
providers have no selected origin and therefore must not receive public placeholder nodes.

Parsed source-unit shells remain in ordered ownership for diagnostics and cleanup, but `dr_register_unit` exposes a unit
through `units_by_name` only when its parsed module header exists and matches the canonical identity requested by the
resolver. Header-mismatch and lexer-failure coverage verifies that those owned shells cannot be found under either the
requested or declared name.

The strict-resolution fixture now combines one resolvable `require` provider with one absent link-only provider. It
proves that the consumer retains both dependency edges and fails with one `DRV-0074`, that the semantic provider remains
resolved, that source fallback is not attempted, and that the absent provider remains node-less. Interface projection
also asserts that source `let` symbols retain their declarations, while the parser normalization comment records that
transparent aliases expand during later semantic materialization.

The architecture and project-status references now describe post-signature semantic type materialization and
per-interface semantic `require`-closure validation. ADR-0014 no longer pins a stale interface-format version, and the
open compile-only and build/run plans use the implemented `MRP_REQUIRE_INTERFACE` and `MRP_ALLOW_SOURCE_FALLBACK` policy
names. The `.l1m`, CLI, diagnostic-code, and public semantic contracts are unchanged.

## ADR Impact

- Decision: Keep pre-node failures node-less and expose source units through canonical name lookup only after their
  declared module identity is validated.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0018-canonical-artifact-association-and-module-graph.md`
  - Rationale: ADR-0018 establishes canonical module identity, one selected origin per node, and the rule that failed
    nodes are not committed as resolved; this fix hardens those existing graph invariants.
- Decision: Retain `link` providers as graph obligations without opening them into the semantic `require` surface or
  inventing absent placeholder nodes.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0018-canonical-artifact-association-and-module-graph.md`
  - Rationale: ADR-0018 already separates semantic, link, and lifecycle dependency views; this fix preserves that
    contract under strict interface resolution.

## Verification

```bash
make -C l1 test-stage1 TESTS="driver_test module_graph_test analysis_test interface_test interface_replay_test signatures_test expr_types_test source_paths_test"
make -C l1 test-stage1-trace TESTS="driver_test module_graph_test analysis_test interface_replay_test"
make -C l1 clean test-all
```

Results:

- All eight focused normal suites passed.
- All four focused trace suites passed without ARC or memory leaks.
- The clean full gate passed all 54 Stage 1 suites and all 38 default trace suites.
- Environment stackability and all four L1 example checks passed.
- Changed documentation links, Markdown formatting, staged-diff checks, and pre-commit hooks passed.

[graph]: ../../features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[hardening]: 2026-07-20-stage1-module-interface-resolution-hardening-noref.md
[initiative]: ../../../initiatives/closed/0001-separate-compilation-and-linking.md
[interface-format]: ../../../../docs/specs/compiler/module-interface-format.md
[roadmap]: ../../../../docs/roadmap.md
