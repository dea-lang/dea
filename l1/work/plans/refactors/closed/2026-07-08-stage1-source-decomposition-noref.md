# Refactor Plan

## Decompose Stage 1 source modules

- Date: 2026-09-07
- Last reviewed: 2026-09-07
- Status: Completed
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
  - [l1/work/plans/bug-fixes/2026-09-07-stage2-fingerprint-bridge-declaration-conflict-noref.md][fingerprint-blocker]
- Repro: `make -C l1 test-all`

## Summary

Stage 1 production sources are hard to navigate because several implementation modules have grown into broad subsystem
catch-alls. At the initial 2026-07-08 draft, the production tree contained 43 `.l0` modules and 36,339 lines, including
22 modules over 500 lines and 11 over 1000 lines. At the 2026-09-02 review, it contained 53 modules and 48,716 lines,
including 27 modules over 500 lines, 16 over 1000 lines, eight over 1500 lines, and five over 2000 lines.

This refactor splits production modules when they contain multiple independent invariants or reasons to change and when
those responsibilities can be separated through an acyclic dependency seam. Line count is a review trigger, not the
definition of a sound module. A cohesive ownership domain or mutually recursive algorithm may remain larger than the
normal target when its closure notes explain why a further split would damage the dependency structure.

The settled Stage 1 layout is a prerequisite for the first committed Stage 2 source snapshot. The work must therefore
remove the clearest architectural catch-alls without creating a fine-grained module graph that is harder to port or
maintain than the current files.

## Pre-refactor State

The pre-refactor production modules over 1000 lines were:

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

## Execution Record

The initial 2026-09-07 inventory confirmed 53 production modules, 48,716 lines, eight modules over 1500 lines, and five
over 2000 lines. A temporary declaration inventory and original-source copy support exact declaration-body comparisons.
Temporary before/after baselines cover help, a semantic-error diagnostic, the `linkset.main` interface including
fingerprints, and ordinary plus traced target-C generation.

The implementation used ten independently reviewed steps:

01. Inventory and baselines; separate interface projection from semantic orchestration.
02. Link planning, provenance, inputs, transactions, toolchain, build, and workspace ownership.
03. Type lookup, constant values/evaluation, materialization, and type-reference resolution.
04. Signature tables, declarations, constant initialization, cycles, visibility, and interface replay.
05. CLI model/help/link/parse and interface header/types/declarations/normalization.
06. Expression typing state, liveness, lookup, patterns, conversion, expression inference, and statements.
07. C-emitter state, ABI, type names/types, declarations, wrappers, expressions, statements, and cleanup.
08. Backend state, coercion, types, cleanup, expression/statement lowering, and module orchestration.
09. Conditional second-wave boundary review and final import cleanup.
10. Architecture and lifecycle documentation, full validation, source-port feasibility, and full-work review.

Each implementation step received a separate read-only review before the next step began. Valid findings were fixed and
checked before proceeding. A final independent read-only review then covered the complete unit of work.

The following inventory command reports architectural review candidates without enforcing a line-count limit:

```bash
wc -l $(rg --files l1/compiler/stage1_l0/src -g '*.l0') | awk '$2 != "total" && $1 > 1500 { print ($1 > 2000 ? "presumptive split" : "mandatory review"), $0 }'
```

### Step 1 boundary

`analysis` imports `interface_projection`; projection imports the existing semantic state, type, name, interface, and
driver owners and never imports `analysis`. The entire recursive projection group and provider-fingerprint cache remain
together. `analysis_module_entry_type` belongs to projection alongside the exported entry surface. Direct helper callers
import `interface_projection`; the `analysis_emit_interface` command-level entrypoint stays in `analysis`.

Step 1 review found no correctness or ownership defects. Its two cleanup findings were accepted: remove an unused test
import and inline the two single-caller orchestration helpers so `analysis` locally declares only coarse entrypoints.
The remaining 31 declaration bodies match the original exactly. The four interface/analysis tests passed; the
orchestration-only follow-up passed an additional `analysis_test` run.

### Step 2 boundary

The link command facade imports `inputs`, `transaction`, `toolchain`, and `workspace`. `workspace` orchestrates source
`build` operations, verified inputs, host commands, and retained C. `inputs` imports `plan`; `plan` imports
`provenance`. All of these import the canonical `model` as needed. Transaction paths and their lifecycle belong to
`transaction`; runtime include bundles belong to `toolchain`; reverse-reachability scratch state belongs to
`provenance`. No child imports the command facade. Explicit dependency walks, transaction cleanup, verification order,
and host command words are moved unchanged.

Step 2 independent review reported no findings. The separately compiled provenance benchmark smoke passed all four graph
shapes with five modules and one measured sample; standalone-link and multi-unit integration coverage passed.

### Step 3 boundary

`lookup` owns symbol/type-name lookup. `const_value` owns values, evaluation context/failure state, their lifecycle, and
scalar target conversion. `const_eval` owns non-recursive literal decoding and arithmetic evaluation. `ref` owns the
mutually recursive type/constant resolution kernel. `materialize` applies that kernel across signature/interface tables.
Every consumer imports these owners directly; no empty `type_resolve` forwarding facade remains.

The fresh call graph requires a refinement of the drafted split: array suffixes evaluate constants, constant casts
resolve type references, and aliases finalize materialized nominal types through the same resolver. The ten-function
recursive group therefore stays in `ref`, together with its nominal replacement helpers. Moving those functions into
separate `const_eval`, `materialize`, and `ref` modules would create a cycle. No callback layer or algorithm change is
introduced. The resulting `ref` kernel is below 1500 lines.

Step 3 review reported no findings and independently confirmed the recursive boundary. All four focused tests passed,
and the five captured behavior baselines remained identical.

### Step 4 boundary

`signatures` retains only `sig_resolve`. Its six children independently own table construction/query and pending-shape
state, source declarations, constant initialization, value-layout cycle detection, visibility, and interface replay and
closure validation. Each child imports `tables` as needed; none imports the facade or another higher-level child.
`SignatureTables` and resolved type data remain with their existing canonical ownership lifecycle in `types`. The
constant-initializer recursion remains together in `const_init`.

Step 4 review found two embedded Python-test harness imports that still expected `sig_make_tables` from the facade. Both
now import `signatures.tables`. The five focused suites and corrected cleanup-policy ICE regression passed.

### Step 5 boundary

`cli_args` retains only `cli_parse`, the complete argv-dispatch entrypoint. CLI state, diagnostics, mode spelling, and
ownership live in `model`; output text lives in `help`; ordered operand validation lives in `link`; parsing and
mode-scoped validation helpers live in `parse`. `parse` imports `link` and `model`, and `link` imports `model`. Drivers
consume CLI structs/enums and lifecycle helpers directly from `model`.

`parser.interface` retains the two complete interface-parse entrypoints. `header` owns the strict operational header
protocol and parse-session result cleanup, `types` owns interface type parsing and temporary field/variant cleanup,
`declarations` owns the declaration grammar and its recursive literal parser, and `normalize` owns nominal-kind
normalization against peer interfaces and source modules. Declaration parsing imports `types` and the header recovery
helper; normalization is independent. No child imports the facade.

Step 5 independent review reported no findings. All 90 declarations were preserved, all six focused suites passed, and
all five temporary behavior baselines remained identical.

### Step 6 boundary

`expr_types` retains only `expr_types_check`. `state` owns checker/flow/guard models, diagnostics, recorded typing
state, and guard lifecycle. `lookup` owns name/type queries and structural expression inspection; `liveness` owns
alive-state storage, branch snapshots, and declaration-scope transitions. `convert` owns scalar assignment/cast rules;
`patterns` owns match/case classification and coverage. `expr` owns recursive expression inference; `stmt` owns
statement flow and function/top-level checking. Dependencies descend from `stmt` through `expr`/`patterns`, conversion,
liveness, lookup, and state; no implementation imports the facade.

The 15-function expression-inference group remains in `expr`, which warrants its over-1500-line review exception as one
mutually recursive inference algorithm. The six-function statement/loop fixed-point group remains in `stmt`, including
the loop transfer functions that invoke statement checking. `liveness` contains the reusable state operations below that
group, avoiding a cycle between liveness analysis and statement checking. Allocation, cleanup, and branch-state meet
operations are unchanged.

Step 6 review reported no findings. All 148 declarations match the original, all five focused suites passed, and all
captured behavior baselines remained identical.

### Step 7 boundary

Emitter state and buffer lifecycle live in `state`; ABI mangling lives in `abi`. `type_names` sits below both `types`
(type spelling and initializers) and `wrappers` (recursive wrapper collection/emission). `declarations` owns module,
function, nominal-type, and source-line output; `expr` owns C expression fragments; `stmt` owns statement fragments;
`lifetime` owns value/aggregate ARC cleanup. No empty `c_emitter` facade remains. All callers, including
Python-generated ICE harnesses, import canonical owners. The wrapper dependency-recursion groups remain together in
`wrappers`, and the value/array cleanup recursion remains together in `lifetime`. Every resulting emitter child is below
1500 lines.

The bootstrap parser rejects `cleanup` as a module-name component with `PAR-0300`, so the drafted `c_emitter.cleanup`
name is implemented as `c_emitter.lifetime`. The same reserved-word constraint applies to `backend.cleanup` and
`backend.module`; those responsibilities use `backend.lifetime` and `backend.output`.

Step 7 review reported no findings. All 227 emitter declarations were preserved, all five focused suites passed,
including generated-C identity and cleanup-policy ICE coverage, and the five temporary baselines remained identical.

### Step 8 boundary

`backend` retains only `backend_generate_module`. `state` owns the backend, current-unit/type queries, scopes, and loop
frames. `expr` owns independent expression inspection, static initializers, and C fragments; `lifetime` owns ARC
materialization, copy/retain operations, value cleanup, and drop emission; `coerce` owns conversions and argument
ownership adaptation. `types` owns target type closure, ordering, and wrapper preparation. `stmt` owns function-body
setup and parameter-retain analysis. `output` orchestrates declarations, lifecycle functions, and the final translation
unit. No implementation imports the facade; expression helpers do not import statement lowering.

The fresh function graph reveals an unavoidable joint lowering kernel: `be_emit_expr` lowers `try` through
`be_emit_cleanup_for_return`, which lowers registered `with` cleanup statements and returns to expression lowering.
Condition lowering, calls/constructors, scoped statements, returns, and loop exits participate in the same recursive
group. `lower` keeps that expression/statement/cleanup algorithm together and is the documented over-2000-line cohesion
exception. `stmt` and `output` enter this kernel from above; `lower` imports only independent expression, conversion,
lifetime, and state helpers. A forced expression-versus-statement cut would require a callback framework or algorithm
rewrite, both excluded by this plan. All original declaration bodies and cleanup ordering remain unchanged.

Step 8 review caught a missing canonical `ast` import for the `ExprId` alias in `backend.coerce`; this was fixed before
proceeding. All 152 backend declarations remain unchanged, all six focused suites passed, and all captured behavior
baselines remained identical.

### Step 9 conditional review and boundaries

The settled callers expose useful acyclic seams in all four conditional candidates:

- `parser.shared` becomes `parser.state`, `parser.cursor`, `parser.token_value`, and `parser.type_ref`. Token decoding
  is independent; state diagnostics use token widths; cursor operations consume state and tokens; recursive type-ref
  parsing sits above the cursor. The shared facade disappears, and parser leaves import only the owners they use.
- `name_resolver` retains `nr_resolve`. `state` owns environments, symbols, construction, and lifecycle; `query` owns
  lookup and resolved-reference recording; `collect` owns local/export collection; `imports` owns import binding and
  extern compatibility; `interface` adapts authoritative interfaces through the same local-definition rules. All
  semantic consumers import `state` explicitly when using its structs.
- `driver` retains its three complete entry-analysis APIs. `driver.state` keeps the canonical registry maps, borrowed
  lookup surface, and ownership lifecycle together. `driver.resolve` owns graph construction and activation, retaining
  mutually recursive source/interface resolution as one traversal. Further source-versus-interface or registry-versus-
  model splitting would separate one graph/ownership invariant, so those cuts are deliberately not made.
- `compile_driver` retains `cd_cmd_compile`. `transaction` owns destinations, staging/publication state, rollback, and
  artifact resolution; `toolchain` owns host compiler classification and command words; `compile` owns analyzed-input
  compilation into standalone transactions or an existing workspace. Link/build consumers import the required child.

`ast`, `lexer`, `interface_fingerprint`, and `build_driver` remain intact after review: respectively they own AST arenas
and lifecycle, one lexer state machine, canonical interface serialization/hash verification, and shared host-build
platform policy. No newly discovered independent invariant warrants splitting these cohesive modules.

Step 9 independent review reported no findings. All 213 declarations were preserved, direct and embedded consumers
resolve their canonical owners, and all eight focused suites passed.

### Step 10 source-port and validation guardrails

The filename-only `.l1` check exposed a new cross-module export requirement: `link_driver.inputs` calls the formerly
internal `_ld_prepare_verified_plan` helper, but L1 default exports exclude leading-underscore symbols. The shared
helper is renamed `ld_prepare_verified_plan` in its owner and both callers. This is the sole helper-name exception,
required to make its new ownership boundary available in the mechanical Stage 2 port. Its body is unchanged. The
filename-only `.l1` semantic checks now pass for `l1c`, `util.demangler`, and `util.path`, covering all 116 modules. The
demangler retains its existing local-shadowing warning.

The final temporary declaration audit compares 1077 declarations after normalizing that one helper rename. The only
other non-import code edits inline the two single-caller analysis orchestration helpers; no diagnostics, constants,
conditions, ownership operations, or algorithms are changed.

The native filename-only port was also attempted with Clang and the unchanged compiler-private support object. It
reached per-module C compilation but failed on conflicting declarations of `l1c_interface_fingerprint_sip13_hex`: the
generated extern uses `dea_byte*`, while the existing L1 runtime header uses `const uint8_t*`. Generating and compiling
`interface_fingerprint` from the original pre-refactor source copy reproduced the same diagnostic at the same C
declaration. This existing Stage 2 support-ABI blocker is tracked separately in
[l1/work/plans/bug-fixes/2026-09-07-stage2-fingerprint-bridge-declaration-conflict-noref.md][fingerprint-blocker]. The
required feasibility rerun is complete; this decomposition plan remains completed. Native Stage 2 delivery and runtime
changes remain outside this refactor.

An independent review confirmed the export refinement and the pre-existing native blocker. Its documentation findings
were accepted: the shared Stage 2 plan now describes the current per-module C backend and multi-unit linking, and the
architecture reference names `link_driver/plan.l0` as the lifecycle-traversal owner. Separate checks of the two utility
roots outside the compiler's import closure completed the 116-module semantic-check coverage.

### Settled inventory

| Inventory               | Before |  After |
| ----------------------- | -----: | -----: |
| Production modules      |     53 |    116 |
| Production lines        | 48,716 | 49,757 |
| Modules over 1000 lines |     16 |      7 |
| Modules over 1500 lines |      8 |      2 |
| Modules over 2000 lines |      5 |      1 |

The two reviewed exceptions are `expr_types/expr.l0` (1621 lines) and `backend/lower.l0` (2427 lines), with the
recursive ownership rationale recorded in steps 6 and 8. The final 116-module import graph is acyclic. Root facades
retain only complete coarse entrypoints; empty facades are removed, shared state has one canonical owner, and direct
consumers plus embedded test harnesses use those owners. Module headers, direct imports, and retained declaration
comments account for the added source lines; the refactor does not add compiler behavior.

### Final validation and review

The final independent review reported no actionable findings. Its full-tree token audit accounted for all 1883 original
declarations, including the two inlined helpers and the renamed shared helper. It independently checked direct symbol
imports, aliases, facade boundaries, both recursive exceptions, all five behavior baselines, and the complete
filename-only port graph.

Validation completed on 2026-09-07:

- Every step's focused unit/integration suites passed after valid review findings were fixed. The separate provenance
  benchmark smoke passed four graph shapes with five modules and one sample.
- `make -C l1 clean test-all` passed 73 normal checks, environment stackability, four warning-free examples, and all 45
  default ARC/memory trace cases. Every trace case reported zero leaked objects and strings. The normal suite covered
  `math_runtime_compile_test`; the default trace suite retains its existing exclusion of that unchanged slow case.
- The five before/after snapshots remained byte-identical: help, the selected diagnostic, `.l1m` text/fingerprint,
  ordinary generated C, and generated C with trace flags.
- Filename-only source copies passed `l1/build/dea/bin/l1c-stage1 --check -Rp /tmp/dea-decomposition-port/src l1c` and
  the same command for `util.demangler` and `util.path`. The three roots cover all 116 copied modules, whose contents
  match the settled `.l0` sources exactly. The existing demangler warning is recorded above.
- The native probe used
  `l1/build/dea/bin/l1c-stage1 --build -v --c-compiler clang --c-options=-O0 -Rp /tmp/dea-decomposition-port/src -Cf /tmp/dea-decomposition-port/support.o -o /tmp/dea-decomposition-port/l1c-port l1c`,
  with the unchanged `support/interface_fingerprint.c` compiled by Clang. It reproduced the existing private support-ABI
  blocker described above; generating and compiling the original `interface_fingerprint` module proved that the failure
  predates this refactor.
- `python3 scripts/check_adr_impact.py --all-active` and `git diff --check` passed before closure. The existing
  `ADR not warranted` disposition remains valid because the source split preserves architectural contracts.

The full L1 validation tier covers the moved backend, cleanup, and compiler-owning state. Its successful result is
reused for finalization. Staged whitespace validation required removing trailing spaces from three inherited blank lines
in `backend/lower.l0`; a comparison confirmed unchanged tokens and line numbers. All other source/test/harness hashes
stayed unchanged, and no build, dependency, generated-source, toolchain, or external modifications occurred. The cleanup
passed `make -C l1 test-stage1 TESTS="backend_test l1c_stage1_generated_c_identity_test"`; all five behavior baselines
matched again. Closure links and Markdown formatting require the staged documentation, whitespace, ADR, and pre-commit
gates. All source snapshots, probes, inventories, and generated artifacts remain temporary or ignored; no Stage 2 source
snapshot is committed by this plan.

[fingerprint-blocker]: ../../bug-fixes/2026-09-07-stage2-fingerprint-bridge-declaration-conflict-noref.md
