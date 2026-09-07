# Refactor Plan

## Decompose L0 compiler sources by architectural responsibility

- Date: 2026-09-07
- Status: Completed
- Title: Decompose L0 Stage 1 and Stage 2 compiler sources by architectural responsibility
- Kind: Refactor
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1 Python compiler
  - L0 Stage 2 self-hosted compiler
- Origin: L0 Stage 2 module-boundary design constrained by open imports, with L0 Stage 1 as the behavioral oracle
- Porting rule: Share responsibility boundaries and observable behavior across both stages, but use idiomatic Python
  composition in Stage 1 and acyclic canonical state/model ownership in Stage 2; identical file layouts are not
  required.
- Target status:
  - L0 Stage 1 Python compiler: Completed
  - L0 Stage 2 self-hosted compiler: Completed
- Subsystem: Compiler source organization / CLI / semantic analysis / C backend
- Modules:
  - `l0/compiler/stage1_py/l0c.py`
  - `l0/compiler/stage1_py/l0_c_emitter.py`
  - `l0/compiler/stage1_py/l0_expr_types.py`
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage2_l0/src/cli_args.l0`
  - `l0/compiler/stage2_l0/src/build_driver.l0`
  - `l0/compiler/stage2_l0/src/l0c_lib.l0`
  - `l0/compiler/stage2_l0/src/c_emitter.l0`
  - `l0/compiler/stage2_l0/src/expr_types.l0`
  - `l0/compiler/stage2_l0/src/backend.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_cli_mode_flags.py`
  - `l0/compiler/stage1_py/tests/cli/test_l0c_assumptions.py`
  - `l0/compiler/stage1_py/tests/diagnostics/test_diagnostics_reporting.py`
  - `l0/compiler/stage1_py/tests/c_emitter/`
  - `l0/compiler/stage1_py/tests/type_checker/`
  - `l0/compiler/stage1_py/tests/backend/`
  - `l0/compiler/stage2_l0/tests/cli_args_test.l0`
  - `l0/compiler/stage2_l0/tests/build_driver_test.l0`
  - `l0/compiler/stage2_l0/tests/c_emitter_test.l0`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_lib_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_codegen_test.py`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py`
- Related:
  - `l0/docs/reference/architecture.md`
  - `l0/docs/reference/c-backend-design.md`
  - `l0/docs/specs/compiler/stage1-contract.md`
  - `l0/docs/specs/compiler/stage2-contract.md`
  - `l1/work/plans/refactors/closed/2026-07-08-stage1-source-decomposition-noref.md`
- Repro: `make -C l0 test`

## Summary

L0 Stage 1 and Stage 2 contained matching source-concentration problems in their command, type-checking, and
code-generation layers. At baseline, the Python Stage 1 production tree contained 24 modules and 15,413 physical lines;
four modules over 1500 lines accounted for 62.5 percent of that tree. The L0 Stage 2 production tree contained 38
modules and 25,154 physical lines; its three modules over 2000 lines accounted for 38.3 percent of that tree.

The problem is not file length by itself. The oversized modules combine independent invariants and reasons to change:
CLI grammar, diagnostic presentation, host build transactions, target-C spelling, optional-wrapper planning, semantic
lookup, flow-sensitive liveness, type compatibility, static initialization, ownership lowering, and translation-unit
orchestration. At the same time, some of the largest statement/expression lowering regions form genuine mutually
recursive kernels that must not be fragmented merely to satisfy a line target.

This refactor applies the architectural-smell rules established by the L1 Stage 1 source-decomposition plan to both L0
compiler stages. Stage 1 remains the behavioral oracle, while the shared boundary design accounts for the stricter L0
module system used by Stage 2.

## Baseline State

The Stage 1 production modules over 1000 lines are:

| Module             | Lines |
| ------------------ | ----: |
| `l0_backend.py`    |  3439 |
| `l0_expr_types.py` |  2373 |
| `l0_c_emitter.py`  |  1962 |
| `l0c.py`           |  1861 |
| `l0_parser.py`     |  1174 |

The Stage 2 production modules over 1000 lines are:

| Module            | Lines |
| ----------------- | ----: |
| `backend.l0`      |  3557 |
| `expr_types.l0`   |  3475 |
| `c_emitter.l0`    |  2595 |
| `build_driver.l0` |  1172 |
| `cli_args.l0`     |  1126 |

The internal structure reinforces the architectural concern:

- Stage 1 `l0c.py` defines 51 functions covering CLI parsing, diagnostic rendering, path/context construction,
  temporary-source safety, toolchain invocation, build/run commands, analysis modes, dump modes, and dispatch.
- The C emitters expose approximately 146 Stage 1 methods and 160 Stage 2 functions. Their name, type, declaration,
  value, control-flow, and cleanup emitters have little recursive coupling and therefore provide strong extraction
  seams.
- Stage 1 expression typing contains a roughly 605-line statement checker; the corresponding Stage 2 checker is roughly
  694 lines. Expression inference and statement/liveness analysis form distinct recursive groups around shared checker
  state.
- Each backend contains about 100 implementation entrypoints. Expression lowering, statement lowering, structured
  control flow, and cleanup participate in one large recursive group, while type ordering, static initialization, and
  translation-unit orchestration sit outside that knot.

Stage 2 also inherits the L0 module-system constraints:

- `import` opens only the provider module's locally declared top-level names; imported names are not re-exported.
- Import cycles are rejected by the compiler driver.
- Imports are open rather than selective, so every extracted module enlarges the importer's unqualified namespace.
- Qualified names resolve ambiguity but do not create a re-export or private implementation boundary.

## General Decomposition Rules

01. Split by independent invariants and reasons to change, not by length alone. Distinct semantic phases, artifact
    contracts, state subsets, transaction lifecycles, or output formats are strong split signals.
02. Treat more than 1500 lines as a mandatory architectural review and more than 2000 lines as a presumptive split. A
    larger module may remain only when it owns one cohesive lifecycle or mutually recursive algorithm and the closure
    notes record that conclusion.
03. Require a real seam before extracting a module. Each child must own a describable responsibility and communicate
    through a stable state/model or narrow functional interface.
04. Keep the Stage 2 import graph acyclic. Shared structs, enums, and lifecycle operations belong in the lowest
    canonical `*.state` or `*.model` module needed by participating implementation modules.
05. Let Stage 2 root modules act only as coarse facades or orchestrators. A facade may import implementation children;
    no implementation child may import its facade.
06. Do not preserve the old Stage 2 helper surface through forwarding wrappers. Production code and tests that need an
    implementation helper or shared type must import its canonical owner explicitly.
07. Keep Stage 1's established coarse Python APIs where they are useful to callers, but do not simulate decomposition
    with a large mixin hierarchy or one forwarding method per extracted operation. Prefer explicit collaborators, state
    objects, and module-level algorithms with narrow contracts.
08. Align Stage 1 and Stage 2 responsibility boundaries where that improves parity navigation, but do not require
    identical filenames, object models, or helper granularity. Python and L0 should each use their natural module
    mechanics.
09. Keep mutually recursive functions together unless there is an independently justified algorithmic redesign. Do not
    introduce callback frameworks, duplicate mutable state, or inverted dependency layers solely to reduce file size.
10. Keep data definitions with their ownership lifecycle unless separating them creates a lower-level canonical state or
    model owner used consistently by all consumers.
11. Preserve compiler phase ordering, language behavior, diagnostic codes and messages, public CLI behavior, ABI,
    generated target-C, runtime behavior, ownership behavior, and bootstrap contracts.
12. Treat Stage 1 output as the behavioral oracle. Every Stage 2 move must preserve exact parity for equivalent paths,
    and every phase must retain the Stage 2 triple-bootstrap fixed point.

## Goal

Make the two L0 compiler implementations navigable by owned state, compiler phase, and artifact contract:

- CLI grammar, presentation, analysis commands, and host build transactions have explicit owners.
- Target-C names, type spelling, declaration layout, value syntax, control syntax, and cleanup emission have visible
  boundaries.
- Expression typing distinguishes shared checker state, lookup/compatibility rules, pattern analysis, expression
  inference, and statement/liveness flow.
- Backend type ordering, static initialization, module orchestration, and recursive lowering are separate concerns.
- Root modules expose only coarse pass or command entrypoints.
- Every production module over 1500 lines receives an explicit architectural review outcome.
- Every production module over 2000 lines is split or receives a documented cohesion exception.

## ADR Impact

- Decision: Organize the L0 compiler sources around architectural responsibility under the existing module and import
  semantics.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The refactor applies accepted L0 module/import semantics and preserves the compiler pipeline and all
    external contracts. The resulting current layout belongs in the existing architecture references rather than a new
    architectural decision record.

## Non-Goals

- Do not change L0 language semantics, diagnostics, public CLI behavior, ABI, generated target-C, runtime behavior,
  ownership behavior, or bootstrap strategy.
- Do not require Stage 1 and Stage 2 to use identical file or object layouts.
- Do not retain internal helpers through broad compatibility facades merely to avoid updating production callers or
  tests.
- Do not split tests solely to mirror production modules; update imports and add focused boundary coverage where needed.
- Do not split `l0_parser.py`, the Stage 2 parser modules, AST modules, lexer modules, or another cohesive state machine
  solely because of size or cross-stage symmetry.
- Do not introduce new diagnostic codes. Existing diagnostics retain their exact code, phase, wording, and source
  location behavior.

## Implementation Phases

### Phase 1: CLI, build orchestration, and C emission

1. Record the current top-level declaration inventory, direct callers, shared types, mutable fields, recursive call
   groups, and import direction for every Phase 1 module. Capture representative diagnostic, generated-C, build, run,
   and trace baselines for temporary before/after comparison.
2. Decompose Stage 1 `l0c.py` into explicit owners for CLI argument construction/normalization, diagnostic presentation,
   source/context preparation, native build transactions, analysis/dump commands, and top-level dispatch. Keep `l0c.py`
   as the executable entrypoint and coarse dispatcher; update tests to target internal owners rather than preserving
   every helper in the root module.
3. Decompose Stage 2 `cli_args.l0` into canonical CLI model, help/presentation, validation, and parsing
   responsibilities. `CliMode`, `CliOptions`, `CliParseResult`, and their lifecycle operations must have one canonical
   owner that `l0c_lib` and build orchestration import directly.
4. Decompose Stage 2 `build_driver.l0` into prepared-input state, C-option handling, host/platform spelling, toolchain
   discovery and command construction, build workspace transaction, and build/run orchestration. Keep only
   `bd_cmd_build` and `bd_cmd_run` as coarse root entrypoints where a root facade remains useful.
5. Decompose both C emitters around builder/state, C names, type spelling and optional wrappers, translation-unit and
   declaration emission, value/lvalue/constructor syntax, statement/control syntax, and cleanup/runtime emission.
6. In Stage 2, use canonical `c_emitter.state` and `c_emitter.builder` owners beneath semantic child modules. Backend
   implementation modules and tests must import the emitter children they actually use; `c_emitter` must not attempt to
   re-export their helper surfaces.
7. In Stage 1, retain a coherent `CEmitter` session API only where it represents real shared state. Extract behavior
   through explicit collaborators or narrow functions, not mixins whose only contract is unrestricted access to all
   emitter internals and not one-for-one forwarding methods.
8. Complete focused Stage 1 and Stage 2 CLI/emitter validation before beginning Phase 2. Generated C must remain byte
   identical for existing golden inputs except for an explicitly reviewed source-location-only difference.

### Phase 2: Expression typing and semantic flow

1. Map the exact dependency direction among checker state, diagnostics, name/type lookup, compatibility, pattern
   analysis, expression inference, statement traversal, and flow-sensitive liveness in both stages.
2. Give Stage 2 shared checker structs, enums, and their ownership operations a canonical `expr_types.state` owner.
   Lower-level lookup and compatibility helpers may depend on this state; they must not depend on the root `expr_types`
   facade.
3. Separate name/type lookup and assignment/cast compatibility from AST traversal where their interfaces are stable and
   do not require duplicating checker state.
4. Separate match-pattern validation and exhaustiveness analysis from general statement dispatch while keeping its
   diagnostic and resolved-type dependencies explicit.
5. Keep the mutually recursive expression-inference functions together. Keep statement traversal and loop liveness
   fixed-point functions together unless a new one-way flow interface is proven independently; the current call graph
   makes them one recursive algorithm.
6. Arrange the Stage 2 direction as canonical state/model at the bottom, lookup/compatibility and expression-only
   liveness helpers above it, expression inference above those helpers, statement/flow analysis depending on expression
   inference, and the root `expr_types_check` orchestrator at the top.
7. Use analogous responsibilities in Stage 1 while preserving the useful `ExpressionTypeChecker.check()` entrypoint.
   Python collaborators must receive explicit state/contracts rather than reaching through an unrestricted parent
   object.
8. Preserve diagnostic accumulation order, suppression/replay rules, inferred-type storage, liveness fixed points,
   pattern coverage, and all Stage 1/Stage 2 parity cases.

### Phase 3: Backend orchestration and recursive lowering

01. Map backend state-field ownership and the full mutually recursive call group before moving code. Record which
    functions participate in expression/statement/control/cleanup recursion and reject any split that would require an
    import cycle or callback framework.
02. Extract type-key handling, value-type dependency collection, stable type ordering, and type-definition emission into
    an acyclic type-ordering responsibility.
03. Extract top-level constant classification and initializer construction into a static-initialization responsibility,
    keeping its small constructor recursion together.
04. Extract module-level generation order, top-level declaration traversal, function setup/teardown, and `main` wrapper
    coordination from node-level lowering.
05. Extract stable state/query and ownership-conversion helpers only when their dependencies are lower than the lowering
    kernel and their ownership contracts are explicit.
06. Keep expression lowering, statement lowering, structured control flow, and cleanup scheduling in one
    `backend.lowering`-style recursive kernel unless a later dependency proof identifies a genuinely one-way seam. This
    kernel may remain above the normal line target with a documented cohesion exception.
07. In Stage 2, place shared backend structs and lifecycle operations in a canonical `backend.state` owner. The root
    `backend` module retains only the coarse generation entrypoint, and no implementation child imports it.
08. In Stage 1, preserve `Backend(...).generate()` as the coarse entrypoint while using explicit collaborators rather
    than a compatibility layer that forwards the former method surface wholesale.
09. Preserve ARC retain/release placement, cleanup ordering on normal and early exits, temporary materialization, lvalue
    evaluation count, source-line directives, declaration order, and exact generated target-C.
10. Update `l0/docs/reference/architecture.md`, `l0/docs/reference/c-backend-design.md`, and the Stage 1/Stage 2
    compiler contracts to describe the settled ownership and navigation layout. Record every remaining size exception in
    the plan closure notes.

## Verification Criteria

Run from the repository root unless noted:

```bash
wc -l l0/compiler/stage1_py/*.py | sort -nr
wc -l $(rg --files l0/compiler/stage2_l0/src -g '*.l0') | sort -nr
./.venv/bin/python -m pytest -q l0/compiler/stage1_py/tests/cli/test_l0c_assumptions.py l0/compiler/stage1_py/tests/cli/test_cli_mode_flags.py l0/compiler/stage1_py/tests/diagnostics/test_diagnostics_reporting.py l0/compiler/stage1_py/tests/c_emitter l0/compiler/stage1_py/tests/type_checker l0/compiler/stage1_py/tests/backend
make -C l0 test-stage1
make -C l0 test-stage2 TESTS="cli_args_test build_driver_test c_emitter_test expr_types_test backend_test l0c_lib_test"
make -C l0 test-stage2
make -C l0 test-stage2-trace
make -C l0 check-examples
make -C l0 triple-test
make -C l0 test-all
```

Acceptance requires:

- Every module has one describable owned responsibility, invariant, or cohesive recursive algorithm.
- Shared Stage 2 state/model types have one canonical owner, and consumers import that owner explicitly.
- Stage 2 root facades locally expose only coarse entrypoints and are never imported by their implementation children.
- No split introduces an import cycle, depends on transitive re-export, floods a facade with forwarding helpers, or
  replaces direct dependencies with an unrestricted callback/mixin layer.
- Every production module over 1500 lines has a recorded architectural review outcome.
- Every production module over 2000 lines is split unless the closure notes document a cohesive ownership domain or
  recursive algorithm that is safer to keep together.
- Stage 1 and Stage 2 retain exact diagnostic codes, messages, ordering, and source spans.
- Generated target-C remains byte identical for the existing parity/golden corpus except for explicitly reviewed
  source-location-only differences.
- Focused and full Stage 1/Stage 2 tests pass, the trace suites report no leaks or ownership regressions, examples pass,
  and triple bootstrap reaches the existing fixed point.

## Execution Steps

Implementation proceeds through nine independently reviewed steps:

1. Stage 1 CLI: argument grammar, diagnostic presentation, context/source preparation, native build transactions, and
   analysis commands.
2. Stage 2 CLI: canonical options/result model, presentation, validation, and parsing.
3. Stage 2 build driver: prepared input, C options, host/toolchain policy, workspace transaction, and build/run
   commands.
4. Stage 1 C emitter: explicit builder and syntax collaborators.
5. Stage 2 C emitter: canonical state and acyclic syntax responsibilities.
6. Stage 1 expression typing: checker state, lookup/compatibility, patterns, expression inference, and statement/flow
   recursion.
7. Stage 2 expression typing: corresponding canonical state and semantic responsibilities.
8. Stage 1 backend: state, types, static initialization, module orchestration, and the recursive lowering kernel.
9. Stage 2 backend: corresponding canonical owners, final architecture documentation, and size review.

Each step receives focused validation followed by a fresh independent read-only review. Valid findings are fixed before
the next step. The complete change receives another independent review before finalization.

### Baseline and dependency inventory

Temporary snapshots preserve all original production sources, top-level declarations, direct calls, mutable fields, and
imports. The existing CLI/diagnostic baseline passed 181 tests; the six selected Stage 2 CLI, build, emitter, typing,
backend, and library suites passed. Fourteen temporary behavior snapshots cover help, a diagnostic with source span,
native execution, trace-enabled generated C, and all ten Stage 1 backend golden inputs. Snapshots preserve source paths
to permit byte comparisons.

### Step 1

The Stage 1 executable retains only `main` and coarse command imports. `l0_cli_args` owns
grammar/normalization/validation; `l0_cli_diagnostics` owns diagnostic rendering; `l0_cli_context` owns source/context
preparation; `l0_cli_build` owns the native build and temporary-source lifecycle; `l0_cli_commands` owns
analysis/dump/codegen commands. Internal tests import and patch the owning module. No implementation module imports
`l0c`.

Step 1 independent review reported no findings. All 50 moved declarations are AST-identical; 181 focused tests, 1507
full Stage 1 tests, and all fourteen behavior snapshots passed.

### Step 2

`cli_args.model` owns CLI types and their lifecycle. `cli_args.presentation` owns identity, mode spelling, help, and
version output. `cli_args.validate` owns mode/option compatibility and CLI diagnostics; `cli_args.tokens` owns scanning
and value boundaries. The root `cli_args` declares only the coarse `cli_parse` algorithm. Library, build, and test
consumers import canonical owners directly; the import graph remains acyclic.

Step 2 independent review reported no findings. All 28 original declarations remain byte-identical and the four selected
CLI/build/library suites passed. The corrected temporary harness validates successful compilation/execution and
maintains separate before/after snapshots for each stage. A pre-existing return-type diagnostic wording/span difference
between stages is preserved, outside this source-only refactor.

### Step 3

`build_driver.state` owns prepared input and lifecycle; `input` owns source preparation and entry validation; `options`
owns C-option policy; `platform` owns actual-host spelling and shell tokens; `toolchain` owns compiler discovery and
command construction. `workspace` compiles generated C inside its caller-owned workspace. The root declares only
`bd_cmd_build` and `bd_cmd_run`, retaining their complete workspace lifetime and cleanup epilogues. All implementation
imports point downward; `compiler_filesystem` remains the canonical workspace-policy owner.

Step 3 independent review reported no findings. All 40 declarations are byte-identical and all four
build/workspace/library integration suites passed.

### Step 4

Stage 1 `CEmitter` assembles explicit `CNames`, `CTypes`, `CValues`, `CStatements`, `CCleanup`, and `CDeclarations`
collaborators around canonical `CEmitterState` and `CCodeBuilder`. Name sequencing belongs to `CNames`; optional-wrapper
state belongs to `CTypes`; shared output, analysis, and active source location belong to `CEmitterState`. Collaborators
declare only their actual lower-level dependencies. Callers use these owners directly; no per-helper forwarding surface
or mixin hierarchy remains. Focused session regressions cover mixed pointer/statement temporary numbering and
independent optional-wrapper registries.

Step 4 independent review reported no findings. All 151 emitter/builder method ASTs are unchanged after normalizing
collaborator access, 374 existing emitter/backend tests and two session tests passed, and all fourteen Stage 1 snapshots
match.

### Step 5

Stage 2 C emission uses `c_emitter.builder`, `state`, `names`, `types`, `wrappers`, `values`, `statements`, `lifetime`,
and `declarations`. Builder and emitter structs retain one canonical owner with their original lifecycle. State owns
active source-location restoration below pointer syntax; type spelling sits below wrapper emission. The empty
`c_emitter` facade is removed, and backend, unit-test, and embedded Python harness consumers import their actual owners.
All moved declarations retain their original bodies and comments.

The Stage 2 cleanup owner is named `lifetime` because `cleanup` is an L0 keyword and cannot be used as a module-name
component.

Step 5 independent review reported no findings. All 162 Stage 2 emitter declarations are unchanged; the five selected
emitter/backend/codegen/cleanup-ICE/ARC suites passed. Both stages' fourteen snapshots matched. Phase 1 triple bootstrap
passed, including identical second/third generated C and a final smoke run; the existing TCC policy skips native-binary
identity.

### Step 6

Stage 1 `ExpressionTypeChecker.check()` coordinates `CheckerState`, `SemanticLookup`, `TypeCompatibility`,
`PatternAnalysis`, `ExpressionLiveness`, `ExpressionInference`, and `StatementFlow`. State owns lexical/liveness stacks,
cached analysis tables, and diagnostic suppression/replay. Expression inference's 14-function recursive group stays
together; statement/block traversal and loop fixed points retain their six-function recursive group. Match pattern
validation/coverage preparation runs before arm traversal, and exhaustiveness diagnostics run afterward through a narrow
`MatchCoverage` result. A focused regression locks that diagnostic ordering. The driver reads diagnostics from their
existing `AnalysisResult` owner.

Step 6 independent review reported no findings. All original methods retain their AST after collaborator routing except
the two reviewed match-coverage extractions. The original/current diagnostic-order probe is byte-identical, four pattern
tests passed, and full Stage 1 validation passed 1510 tests.

### Step 7

Stage 2 expression typing uses canonical `expr_types.state` models and stack ownership, with `lookup`, `compat`,
`patterns`, `liveness`, `expr`, `flow`, and `initializers` above it. Root `expr_types_check` retains module ordering and
error gating. Construction and the existing destruction epilogue move into `etc_create`/`etc_free` in the state owner.
The eight-function inference recursion and five-function statement/loop recursion remain intact. Compatibility never
imports inference; the initializer helper that invokes inference belongs to `expr`. Module-scope initializer traversal
remains an independent phase above it.

Step 7 independent review reported no findings. All 95 moved declarations are byte-identical; the root lifecycle
extraction preserves constructor arguments and destruction order. All five focused semantic/backend/library/codegen/ARC
suites passed. Original/current Stage 1 comparisons across all 54 typing fixtures preserve exact status, output,
diagnostics, order, and spans.

Phase 2 triple bootstrap passed with the existing generated-C fixed point and final smoke run. The same exact diagnostic
comparison also passed all 54 Stage 2 typing fixtures, and both stages' fourteen behavior snapshots still match their
originals.

### Step 8

Stage 1 `Backend` assembles explicit `BackendState`, `OwnershipConversion`, `ValueLifetime`, `StaticInitializers`,
`TypeOrdering`, `Lowering`, and `ModuleGeneration` collaborators. State owns emitter access, semantic queries, scopes,
labels, and the current function/module. Type ordering owns both dependency sorting and its contiguous
definition-emission phase. Static constructors remain a separate recursive group. Module generation controls
translation-unit order and function lifecycle; it invokes the lowering owner without callbacks or reverse imports.

The 32-function recursive lowering group remains together in the 1864-line `l0_backend_lowering.py`. Scheduled cleanup
can lower statements, and expression lowering can emit control flow, so separating these operations would create cycles
or require an artificial dispatcher. This is the reviewed size exception for this subsystem.

All 376 focused backend/emitter tests and fourteen Stage 1 behavior snapshots passed.

Step 8 independent review reported no findings. All 97 original methods are preserved after routing and inlining the
type-definition extraction. Independent construction probes confirmed shared state, custom-emitter preservation, and
isolation between backend sessions.

### Step 9

Stage 2 `backend.state` owns backend/loop models, construction/destruction, scopes, and semantic queries. `convert`,
`lifetime`, `ordering`, `initializers`, and `output` separate pointer/value operations, type ordering, static
initialization, and module/function lifecycle. Root `backend_generate` retains its complete generation algorithm and
session lifetime. Static initializers retain their existing fallback into expression lowering through an explicit
dependency. The 24-function recursive lowering group stays together in `backend.lowering`, along with its tightly
related pattern and cleanup-header helpers. All 103 original declarations retain their bodies and comments. The complete
production import graph is acyclic across 71 modules.

The architecture, C backend design, Stage 1/Stage 2 compiler contracts, and ownership source references now describe the
settled source owners. No language, CLI, diagnostic-code, ABI, runtime, or bootstrap contract is changed.

### Final source inventory and size review

| Tree                      | Before modules | Before lines | After modules | After lines |
| ------------------------- | -------------: | -----------: | ------------: | ----------: |
| Stage 1 production Python |             24 |        15413 |            51 |       15747 |
| Stage 2 production L0     |             38 |        25154 |            71 |       25712 |

The inventory counts physical lines in Stage 1 top-level production `.py` files and recursively in Stage 2 production
`.l0` files, excluding tests. Added lines are module headers/imports, explicit collaborator wiring, and documentation
for ownership boundaries.

Every remaining production module over 1500 lines has this architectural outcome:

| Module                                          | Lines | Review outcome                                                                                                                                                                                                                                                                                       |
| ----------------------------------------------- | ----: | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `l0/compiler/stage1_py/l0_backend_lowering.py`  |  1864 | Retain the 32-function recursive expression/statement/control-flow/scheduled-cleanup group. Its leaf lifetime and conversion operations, type ordering, static constructors, and module generation are extracted. Further separation would cut recursion or require an unrelated algorithm redesign. |
| `l0/compiler/stage2_l0/src/backend/lowering.l0` |  1676 | Retain the corresponding 24-function recursive group with tightly coupled pattern and cleanup-header helpers. Canonical state and independent value operations sit below it; module generation and static initializers depend on it without reverse imports.                                         |

No production module remains over 2000 lines. The largest remaining non-lowering module is the unchanged 1174-line Stage
1 parser; Stage 2's largest other module is the unchanged 997-line AST owner. Their coherent grammar/state ownership
does not require a split.

Step 9 independent review reported no findings. It verified declaration preservation, canonical imports, recursive
groups, documentation, and the final inventory.

### Final validation

- `make -C l0 clean test-all`: passed 1510 Stage 1 tests, all 58 Stage 2 suites, eight examples, all workflow checks,
  and all 34 broad ARC/memory trace checks. Every broad trace check reported zero leaked object and string pointers.
- Phase 3 triple bootstrap passed as `l0c_triple_bootstrap_test.py` within the full Stage 2 suite. The second/third
  generated-C fixed point and final smoke execution passed; the existing TCC policy skips native-binary identity.
- Temporary before/after comparisons passed fourteen behavior snapshots per stage, including all ten existing Stage 1
  backend golden inputs, help, diagnostic output/spans, deterministic native execution, and trace-enabled generated C.
- Exact before/after `--check` comparisons passed all 54 Stage 2 typing fixtures using each stage, preserving status,
  stdout, stderr, diagnostic order, text, and spans. Existing cross-stage diagnostic differences remain unchanged.
- Production dependency audits confirmed an acyclic 71-module Stage 2 graph and acyclic top-level runtime imports across
  all 51 Stage 1 modules. Original type-checking-only imports remain unchanged.
- Edited live-document links resolve, and `python3 scripts/check_adr_impact.py --all-active` passed.

Full validation uses the `test-all` tier because the moved backend/emitter and self-hosted compiler code includes
allocation, ownership, and cleanup paths. The staged whitespace gate subsequently removed inherited trailing spaces from
ten blank lines in `expr_types/expr.l0`, `expr_types/flow.l0`, and `expr_types/patterns.l0`. Lexer comparisons confirmed
identical tokens and source spans; physical line counts are unchanged. An independent follow-up review confirmed that
this final source delta contains only end-of-line whitespace and does not change the full-review result. All other
production/test inputs, build configuration, dependencies, and toolchain selection remain unchanged.

Post-cleanup validation passed:

- `make -C l0 test-stage2 TESTS="expr_types_test l0c_triple_bootstrap_test"`: both suites passed, including the final
  bootstrap fixed point.
- `make -C l0 test-stage2-trace TESTS=expr_types_test`: passed with zero leaked object and string pointers.
- Exact Stage 2 diagnostics across all 54 typing fixtures still match the original compiler.
- `git diff --cached --check` and `python3 scripts/check_adr_impact.py --staged`: passed.

The earlier successful `make -C l0 clean test-all` result remains the full validation evidence for unchanged paths; the
focused reruns cover the three whitespace-cleaned files. No semantic input or external modification invalidated the
remaining tests, examples, workflows, or trace results.

### Final review and completion

The independent full-change read-only review reported no actionable findings. It covered tracked and new files, all
non-mechanical extractions, state wiring, resolved Python globals, canonical Stage 2 imports, caller migrations,
documentation, and the validation evidence. No review finding remains unresolved. All nine implementation steps and both
target implementations are complete; the plan is closed with its existing final `ADR not warranted` disposition.

Validation is local to the available host/toolchain. Native-binary bootstrap identity remains subject to the existing
TCC exclusion; no new bootstrap exception was introduced. No remote push, release, or publication is part of this plan.
