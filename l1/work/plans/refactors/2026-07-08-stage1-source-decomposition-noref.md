# Refactor Plan

## Decompose Stage 1 source modules

- Date: 2026-07-08
- Status: Draft
- Title: Decompose Stage 1 source modules into readable architectural units
- Kind: Refactor
- Severity: Medium
- Stage: 1
- Subsystem: Stage 1 compiler source architecture
- Modules:
  - `l1/compiler/stage1_l0/src`
- Test modules:
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
  - `l1/compiler/stage1_l0/tests/lexer_test.l0`
  - `l1/compiler/stage1_l0/tests/name_resolver_test.l0`
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/signatures_test.l0`
  - `l1/compiler/stage1_l0/tests/type_resolve_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/compiler/stage1_l0/README.md`
- Repro: `make -C l1 test-stage1`

## Summary

Stage 1 production sources are now hard to navigate because several implementation modules have grown into broad
subsystem catch-alls. The full L1 `.l0` tree currently has 30 files over 500 lines and 15 over 1000 lines. Production
sources under `l1/compiler/stage1_l0/src` account for 22 files over 500 lines and 11 over 1000 lines.

This refactor should split production Stage 1 source modules along architectural boundaries while preserving current
compiler behavior. The target is a soft 1000-line cap for production modules, with root module imports preserved through
compatibility facades where callers already depend on names such as `backend`, `c_emitter`, `expr_types`, and
`type_resolve`.

## Current State

The largest production modules are:

- `expr_types.l0`: 5211 lines.
- `backend.l0`: 5099 lines.
- `c_emitter.l0`: 3895 lines.
- `type_resolve.l0`: 1687 lines.
- `build_driver.l0`: 1488 lines.
- `parser/shared.l0`: 1288 lines.
- `parser/interface.l0`: 1230 lines.
- `ast.l0`: 1118 lines.
- `lexer.l0`: 1117 lines.
- `signatures.l0`: 1088 lines.
- `name_resolver.l0`: 1011 lines.

The existing parser split establishes the preferred shape: keep a small root module as the public entry point and move
implementation detail into a directory of child modules with dotted module names. L1 name resolution exports only local
top-level symbols, so shared structs and enums that must remain visible to callers cannot simply move behind imported
implementation modules without a facade or explicit state module.

## Defaults Chosen

1. Preserve existing public root imports for production callers and tests.
2. Prefer semantic child-module names such as `state`, `lookup`, `expr`, `stmt`, `wrappers`, `toolchain`, and `runtime`
   instead of positional names such as `part1`.
3. Put cross-cutting state structs and helper enums in `*.state` modules when multiple implementation submodules need
   them.
4. Do not introduce behavior changes, diagnostic wording changes, CLI changes, generated-C changes, runtime changes, or
   test semantic changes.
5. Treat the 1000-line cap as the acceptance target for this refactor, while documenting any unavoidable exception in
   the plan closure notes.

## Goal

Reduce all production Stage 1 source modules below the soft 1000-line cap and make each large subsystem navigable by
compiler phase or responsibility:

- AST shape and ownership helpers are easy to find.
- Lexer state, character predicates, literal readers, and token scanning are separate.
- Parser shared state, token cursor/recovery helpers, and type parsing are separate.
- Semantic analysis phases distinguish name lookup, signature resolution, type resolution, expression typing, and
  statement typing.
- C emission distinguishes state, ABI mangling, type spelling, declarations, wrappers, expressions/statements, and
  cleanup/runtime helper emission.
- Backend lowering distinguishes state, type dependency ordering, coercions, ownership cleanup, expression lowering,
  statement lowering, and top-level emission.
- Build-driver logic distinguishes option parsing, platform helpers, C toolchain command construction, runtime-library
  resolution, and build/run command orchestration.

## ADR Impact

- Decision: Keep the Stage 1 source decomposition as a behavior-preserving internal module split.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The refactor preserves compiler phase contracts, language behavior, public CLI behavior, ABI, runtime
    behavior, and bootstrap strategy.

## Non-Goals

- Do not split implementation tests as part of this plan, except for import updates needed by production module moves.
- Do not rename public helper prefixes such as `be_`, `cem_`, `etc_`, `tr_`, `sig_`, `nr_`, `bd_`, or `ls_`.
- Do not introduce a module re-export mechanism or type-alias workaround.
- Do not change L1 language semantics, ABI, diagnostics, runtime behavior, or bootstrap contract.
- Do not update L0 user-facing docs or the root README narrative.

## Implementation Phases

### Phase 1: Source map and mechanical guardrails

1. Record a fresh line-count inventory for `l1/compiler/stage1_l0/src`.
2. Add a small script or documented command for checking production `.l0` line counts, unless an existing project helper
   already covers this.
3. Identify symbols referenced across module boundaries before each split with `rg`, especially state structs and helper
   functions used directly by tests.

### Phase 2: Low-risk structural splits

1. Split `ast.l0` by moving destructor/free helpers into `ast.free`, while keeping AST type definitions and arena access
   helpers in `ast`.
2. Split `lexer.l0` into character helpers, state/error helpers, literal readers, and token scanning while keeping
   `lexer` as the public import used by the driver and tests.
3. Split `parser/shared.l0` into parser state/cursor helpers, token text helpers, recovery helpers, and type parsing.
4. Split `parser/interface.l0` into interface header parsing, interface type parsing, declaration parsing, and type
   normalization.

### Phase 3: Semantic subsystem splits

1. Split `type_resolve.l0` into symbol lookup, const-value data helpers, const evaluation, and type-reference
   resolution.
2. Split `signatures.l0` into table lookup/free helpers, declaration signature resolution, const initializer support,
   value-type cycle checks, and exported-surface validation.
3. Split `name_resolver.l0` into state/table helpers, local/export collection, import binding, and final resolution.
4. Split `expr_types.l0` into checker state/liveness helpers, lookup and type utilities, assignment/cast checks, pattern
   and case checking, expression inference, statement checking, and top-level/function entry points.

### Phase 4: Code generation and build-driver splits

1. Split `c_emitter.l0` into state/code-builder helpers, ABI mangling, C type spelling, declaration emission, wrapper
   collection/emission, expression/statement emission helpers, and cleanup/runtime helper emission.
2. Split `backend.l0` into backend state, type dependency ordering, coercions, ownership cleanup, expression lowering,
   statement lowering, and top-level/module emission.
3. Split `build_driver.l0` into input preparation, platform/path helpers, C option handling, toolchain command
   construction, runtime-library resolution, and build/run command orchestration.

### Phase 5: Cleanup and validation

1. Confirm every production source module under `l1/compiler/stage1_l0/src` is at or below the soft 1000-line target.
2. Remove stale imports introduced during migration.
3. Update only comments or implementation docs that explicitly reference old monolithic file ownership.
4. Run focused tests after each subsystem split, then full Stage 1 validation.

## Verification Criteria

Run from the repository root unless noted:

```bash
wc -l $(rg --files l1/compiler/stage1_l0/src -g '*.l0') | sort -nr | sed -n '1,40p'
make -C l1 test-stage1 TESTS="lexer_test parser_test interface_test type_resolve_test signatures_test name_resolver_test expr_types_test c_emitter_test backend_test build_driver_test l1c_lib_test"
make -C l1 test-all
```

Acceptance requires:

- No production source module over 1000 lines unless a closure note documents a deliberate exception.
- Existing production imports continue to work.
- The focused Stage 1 tests pass.
- `make -C l1 test-all` passes.
- Generated compiler behavior remains unchanged except for incidental source-location differences that are reviewed and
  accepted as harmless.
