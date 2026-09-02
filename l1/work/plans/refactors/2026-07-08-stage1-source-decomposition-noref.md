# Refactor Plan

## Decompose Stage 1 source modules

- Date: 2026-07-08
- Last reviewed: 2026-09-02
- Status: Draft
- Title: Decompose Stage 1 source modules into readable architectural units
- Kind: Refactor
- Severity: Medium
- Stage: 1
- Subsystem: Stage 1 compiler source architecture
- Modules:
  - `l1/compiler/stage1_l0/src`
- Test modules:
  - `l1/compiler/stage1_l0/tests/analysis_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/compile_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_fingerprint_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_replay_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/link_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/module_graph_test.l0`
  - `l1/compiler/stage1_l0/tests/name_resolver_test.l0`
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/signatures_test.l0`
  - `l1/compiler/stage1_l0/tests/type_resolve_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_build_run_multi_cu_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_compile_only_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_generated_c_identity_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_link_set_test.py`
- Related:
  - `l1/docs/reference/architecture.md`
  - `l1/docs/roadmap.md`
  - `l1/compiler/stage1_l0/README.md`
  - `work/plans/features/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md`
- Repro: `make -C l1 test-stage1`

## Summary

Stage 1 production sources are hard to navigate because several implementation modules have grown into broad subsystem
catch-alls. At the initial 2026-07-08 draft, the production tree contained 43 `.l0` modules and 36,339 lines, including
22 modules over 500 lines and 11 over 1000 lines. As of the 2026-09-02 review, it contains 53 modules and 48,716 lines,
including 27 modules over 500 lines, 16 over 1000 lines, eight over 1500 lines, and five over 2000 lines.

This refactor splits production modules when they contain multiple independent invariants or reasons to change and when
those responsibilities can be separated through an acyclic dependency seam. Line count is a review trigger, not the
definition of a sound module. A cohesive ownership domain or mutually recursive algorithm may remain larger than the
normal target when its closure notes explain why a further split would damage the dependency structure.

The settled Stage 1 layout is a prerequisite for the first committed Stage 2 source snapshot. The work must therefore
remove the clearest architectural catch-alls without creating a fine-grained module graph that is harder to port or
maintain than the current files.

## Current State

The current production modules over 1000 lines are:

| Module                     | Lines |
| -------------------------- | ----: |
| `backend.l0`               |  5619 |
| `expr_types.l0`            |  5525 |
| `c_emitter.l0`             |  4172 |
| `link_driver.l0`           |  2927 |
| `type_resolve.l0`          |  2121 |
| `signatures.l0`            |  1746 |
| `cli_args.l0`              |  1728 |
| `parser/interface.l0`      |  1665 |
| `name_resolver.l0`         |  1325 |
| `parser/shared.l0`         |  1288 |
| `compile_driver.l0`        |  1185 |
| `lexer.l0`                 |  1171 |
| `ast.l0`                   |  1118 |
| `driver.l0`                |  1114 |
| `interface_fingerprint.l0` |  1097 |
| `analysis.l0`              |  1074 |

Size alone does not determine the candidate list. For example, `analysis.l0` has a clear architectural split between
semantic-pipeline orchestration and its large `mi_*` interface-projection implementation even though the whole file is
only 1074 lines. Conversely, `ast.l0` keeps AST definitions, arenas, and their ownership lifecycle together, while
`lexer.l0` remains one lexer state machine; neither requires a split merely to reduce its line count.

The Stage 1 implementation is written in L0 and is constrained by the L0 module system:

- Imports open only the provider module's locally declared top-level symbols. Imported symbols are not re-exported.
- Import cycles are rejected.
- Qualified names disambiguate imported symbols but do not create re-export or private implementation boundaries.
- Every top-level declaration in an imported implementation module joins the importer's visible symbol set, so existing
  subsystem prefixes remain useful for collision avoidance.

These constraints make a state-at-the-bottom dependency pattern preferable to facades that attempt to hide shared types.
A root module may preserve a small set of coarse entrypoints, but consumers of shared structs or enums must import their
canonical `*.state` or `*.model` owner explicitly.

## General Decomposition Rules

01. Split by independent invariants and reasons to change, not by file length alone. Distinct semantic phases, artifact
    contracts, transaction lifecycles, output formats, or disjoint state subsets are strong split signals.
02. Treat more than 1500 lines as a mandatory architectural review and more than 2000 lines as a presumptive split. A
    larger module may remain only when it is one cohesive ownership domain or mutually recursive algorithm and the
    closure notes document that conclusion.
03. Require a real seam before extracting a module. Each child must own a describable responsibility, and communication
    across the seam must use a stable state/model or a narrow function interface.
04. Keep the import graph acyclic. Shared structs, enums, and lifecycle operations belong in the lowest canonical
    `*.state` or `*.model` module needed by the participating implementation modules.
05. Let root modules act only as coarse facades or orchestrators. A facade imports its implementation modules; no
    implementation module imports the facade. A facade locally defines only the stable entrypoints that callers should
    continue to use.
06. Do not preserve the old internal helper surface through forwarding wrappers. Production code and tests that use
    shared state or implementation helpers may update their imports to name the owning child module explicitly.
07. Keep mutually recursive functions together unless there is an independently justified algorithmic redesign. Do not
    manufacture callback layers or duplicate state merely to meet a size target.
08. Keep data definitions with their ownership lifecycle unless separating them creates a lower-level state/model owner
    used consistently by all consumers.
09. Prefer semantic module names such as `state`, `model`, `lookup`, `liveness`, `provenance`, `transaction`, `types`,
    `expr`, and `stmt`. Do not use positional names such as `part1`.
10. Preserve current language behavior, diagnostics, public CLI behavior, ABI, `.l1m` semantics, generated target-C,
    runtime behavior, and bootstrap contracts. The L0-generated C used to build Stage 1 may change as source modules and
    source locations move; Stage 1 output for equivalent L1 inputs must not change unintentionally.

## Goal

Make Stage 1 navigable by compiler phase, owned state, and output contract while retaining an explicit acyclic module
graph:

- Root modules expose only coarse pass or command entrypoints.
- Shared implementation state has one canonical owner and is imported explicitly.
- Parser, semantic, interface, code-generation, and driver responsibilities have visible boundaries.
- Recursive inference and lowering kernels remain coherent rather than being fragmented to satisfy a number.
- Every module over 1500 lines receives an explicit architectural review outcome.
- Every module over 2000 lines is split or receives a documented cohesion exception.
- The resulting layout is settled before the first committed Stage 2 source snapshot.

## ADR Impact

- Decision: Keep the Stage 1 source decomposition as a behavior-preserving internal module split.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The refactor preserves compiler phase contracts, language behavior, public CLI behavior, ABI, runtime
    behavior, and bootstrap strategy. The module-layout rules guide internal ownership without changing the two-stage
    architecture or a user-visible contract.

## Non-Goals

- Do not split implementation tests solely to mirror production modules; update their imports and add focused coverage
  where the new seams need it.
- Do not rename established helper prefixes such as `be_`, `cem_`, `etc_`, `tr_`, `sig_`, `nr_`, `bd_`, or `ls_` unless
  a local collision or ownership ambiguity requires a reviewed exception.
- Do not introduce a module re-export mechanism, type-alias workaround, callback framework, or generic dependency
  injection layer to simulate module features that L0 does not provide.
- Do not require `ast.l0`, `lexer.l0`, `interface_fingerprint.l0`, or another cohesive module to split solely because of
  its size.
- Do not change L1 language semantics, ABI, diagnostics, runtime behavior, or bootstrap contract.
- Do not update L0 user-facing docs or the root README narrative.

## Implementation Phases

### Phase 0: Boundary map and mechanical guardrails

1. Record a fresh line-count and top-level-declaration inventory for `l1/compiler/stage1_l0/src`.
2. Add a small checker or documented command that reports modules over 1500 and 2000 lines. The checker reports review
   candidates; it does not decide whether a cohesive exception is valid.
3. Before each split, inventory direct callers, callees, shared types, field access, ownership functions, recursive call
   groups, and tests with `rg`.
4. Record the proposed import direction for every child module and reject a boundary that requires a cycle, transitive
   re-export, or wholesale helper forwarding.
5. Capture representative diagnostic, `.l1m`, and generated target-C baselines for temporary before/after comparison.

### Phase 1: Obvious and urgent responsibility splits

These modules have clear independent responsibilities and relatively legible extraction seams. Complete them before the
more entangled type-checking and code-generation kernels.

1. Split `analysis.l0` into semantic-pipeline entrypoints in `analysis` and exported-surface, dependency, and provider
   fingerprint projection in `interface_projection`.
2. Split `link_driver.l0` into `link_driver.model`, `link_driver.plan`, `link_driver.provenance`, `link_driver.inputs`,
   `link_driver.transaction`, `link_driver.toolchain`, `link_driver.build`, and `link_driver.workspace`, with
   `link_driver` retaining the link/build/run command entrypoints.
3. Split `type_resolve.l0` into `type_resolve.lookup`, `type_resolve.const_value`, `type_resolve.const_eval`,
   `type_resolve.materialize`, and `type_resolve.ref`. Consumers of `ConstValue` and other shared data import their
   canonical owner explicitly.
4. Split `signatures.l0` into `signatures.tables`, `signatures.declarations`, `signatures.const_init`,
   `signatures.cycles`, `signatures.visibility`, and `signatures.interface`, with `signatures` retaining `sig_resolve`.
5. Split `cli_args.l0` into `cli_args.model`, `cli_args.help`, `cli_args.link`, and `cli_args.parse`, with `cli_args`
   retaining the coarse parse entrypoint. Build and link drivers import `cli_args.model` directly when they consume CLI
   structs or enums.
6. Split `parser/interface.l0` into `parser.interface.header`, `parser.interface.types`,
   `parser.interface.declarations`, and `parser.interface.normalize`, with `parser.interface` retaining the complete
   interface-parse entrypoints.

### Phase 2: Large stateful and recursive kernels

These modules provide the largest readability payoff but require explicit recursive-group and state-ownership maps
before code moves.

1. Split `expr_types.l0` into `expr_types.state`, `expr_types.liveness`, `expr_types.lookup`, `expr_types.patterns`,
   `expr_types.convert`, `expr_types.expr`, and `expr_types.stmt`, with `expr_types` retaining `expr_types_check`. Keep
   the mutually recursive expression-inference kernel together even if that child remains above 1500 lines.
2. Split `c_emitter.l0` into `c_emitter.state`, `c_emitter.abi`, `c_emitter.type_names`, `c_emitter.types`,
   `c_emitter.declarations`, `c_emitter.wrappers`, `c_emitter.expr`, `c_emitter.stmt`, and `c_emitter.cleanup`.
   `c_emitter.type_names` must remain below both type spelling and wrapper emission so those modules do not depend on
   each other cyclically.
3. Split `backend.l0` into `backend.state`, `backend.coerce`, `backend.types`, `backend.cleanup`, `backend.expr`,
   `backend.stmt`, and `backend.module`, with `backend` retaining `backend_generate_module`. Statement lowering may
   import expression lowering and cleanup; expression lowering must not import statement lowering.

### Phase 3: Conditional second-wave candidates

Review these modules after Phases 1 and 2 settle their consumers. Split only when the stated seam still improves the
resulting dependency graph.

1. Consider splitting `parser/shared.l0` into `parser.state`, `parser.cursor`, `parser.token_value`, and
   `parser.type_ref`. Existing parser leaves would import only the pieces they use.
2. Consider splitting `name_resolver.l0` into `name_resolver.state`, `name_resolver.query`, `name_resolver.collect`,
   `name_resolver.imports`, and `name_resolver.interface`, with `name_resolver` retaining `nr_resolve`. Because
   `ModuleEnv` and `NameResolution` have broad fan-out, all consumers must be updated to import their canonical state
   owner rather than relying on the facade.
3. Review `compile_driver.l0` for a transaction, host-toolchain, artifact-resolution, and command-orchestration split.
4. Review `driver.l0` for a `driver.state`, registry/query, source resolution, interface resolution, and entry-analysis
   split.
5. Leave `ast.l0`, `lexer.l0`, `interface_fingerprint.l0`, and the now narrower `build_driver.l0` intact unless the
   completed dependency map reveals a new independent invariant or lifecycle seam.

### Phase 4: Cleanup, documentation, and closure

1. Review every production module over 1500 lines and record the split or cohesion outcome.
2. Split every production module over 2000 lines or document the cohesive ownership or recursive-knot exception in the
   closure notes.
3. Remove stale and redundant imports introduced during migration and confirm the final import graph is acyclic.
4. Update the canonical architecture reference, Stage 1 README where needed, roadmap, and Stage 2 self-hosting plan to
   describe the settled module layout and current validation baseline.
5. Run focused tests after each subsystem split, then complete Stage 1 validation.
6. Re-run the Stage 2 source-port feasibility check against the settled source layout before taking the committed Stage
   2 snapshot.

## Verification Criteria

Run from the repository root unless noted:

```bash
wc -l $(rg --files l1/compiler/stage1_l0/src -g '*.l0') | sort -nr | sed -n '1,60p'
make -C l1 test-stage1 TESTS="analysis_test parser_test interface_test interface_replay_test type_resolve_test signatures_test name_resolver_test expr_types_test c_emitter_test backend_test cli_args_test build_driver_test compile_driver_test link_driver_test driver_test module_graph_test l1c_lib_test"
make -C l1 test-stage1 TESTS="l1c_stage1_generated_c_identity_test l1c_stage1_compile_only_test l1c_stage1_link_set_test l1c_stage1_build_run_multi_cu_test"
make -C l1 test-all
```

Acceptance requires:

- Every module has one describable owned responsibility or invariant.
- Shared state and model types have one canonical owner, and consumers import that owner explicitly.
- Root facades locally expose only coarse entrypoints and are never imported by their own implementation children.
- No split introduces an import cycle, depends on transitive re-export, or preserves the old helper surface through a
  forwarding layer.
- Every module over 1500 lines has a recorded architectural review outcome.
- Every module over 2000 lines is split unless the closure notes document a cohesive ownership domain or recursive
  algorithm that is safer to keep together.
- Focused Stage 1 unit and integration tests pass after each affected subsystem.
- `make -C l1 test-all` passes.
- Diagnostic codes and messages, `.l1m` text and fingerprints, public CLI behavior, ABI behavior, generated target-C,
  runtime behavior, and bootstrap behavior remain unchanged except for reviewed source-location differences caused by
  moving the Stage 1 implementation itself.
