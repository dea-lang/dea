# Feature Plan

## Add export manifests and aliased/selective imports

- Date: 2026-04-24
- Status: Completed
- Title: Add export manifests and aliased/selective imports
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: `l1/work/initiatives/closed/0001-separate-compilation-and-linking.md`
- Subsystem: Parser / name resolution / import analysis / docs
- Modules:
  - `l1/compiler/stage1_l0/src/ast.l0`
  - `l1/compiler/stage1_l0/src/parser.l0`
  - `l1/compiler/stage1_l0/src/parser/decl.l0`
  - `l1/compiler/stage1_l0/src/name_resolver.l0`
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/symbols.l0`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/name_resolver_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/closed/0001-separate-compilation-and-linking.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 TESTS="parser_test name_resolver_test analysis_test"`
- Final validation:
  - `make -C l1 test-stage1 TESTS="name_resolver_test analysis_test"`
  - `make -C l1 test-stage1 TESTS="build_driver_test name_resolver_test"`
  - `make -C l1 test-stage1`
  - `make -C l1 test-stage1-trace`
  - `make clean test-all`

## Summary

Initiative `0001-separate-compilation-and-linking` now fixes visibility at the module level and moves L1 away from the
current flat import surface. Before interface files, mangling, or separate compilation can land, Stage 1 needs to parse,
represent, and resolve:

- `export *;`
- `export foo, bar;`
- `import math as m;`
- `import abs, pi from math;`

This plan is the language-front-end tranche for that change. It settles syntax, AST shape, and resolver behavior for the
new surface while leaving backend linkage and `.l1m` emission to follow-on plans.

## Current State

1. Imports remain flat: modules contribute symbols into the current resolution environment without an alias/object
   namespace.
2. Top-level symbols are implicitly available to importers, so there is no explicit exported-vs-internal surface.
3. Qualified-name support exists for module paths and enum variants, but not for alias-backed module namespaces.
4. The current parser and resolver do not model an export manifest at all.

## Defaults Chosen

1. Visibility is module-level only in this tranche; there is no per-declaration `pub` or `priv`.
2. `export *;` exports every top-level symbol, including `_`-prefixed names.
3. If no `export` statement is present, the default export set is every top-level symbol except names starting with `_`.
4. `export foo, bar;` is an allowlist over top-level symbol names only; it does not rename exports.
5. `import math as m;` introduces a module alias used through `m::name`.
6. `import abs, pi from math;` introduces unqualified bindings for the named exported symbols only.
7. Mixed import forms in one statement stay out of scope. Use one import statement per form.

## Goal

1. Parse export manifests and the two new import forms.
2. Represent the explicit export surface in the AST and semantic model.
3. Resolve alias-qualified references and selective imports deterministically.
4. Preserve current Dea/L1 bootstrap semantics outside the new surface.

## Implementation Phases

### Phase 1: Parser and AST surface

Extend top-level declaration parsing so a module may begin with at most one `export` manifest. Record:

- `export *;`
- `export` name lists in source order
- `import <module> as <alias>;`
- `import <name-list> from <module>;`

The AST should retain enough structure for deterministic re-emission into `.l1m` later without reparsing ad hoc token
spans.

### Phase 2: Export-surface analysis

Teach semantic analysis to compute the module's public export set under the initiative defaults:

- explicit star export,
- explicit allowlist export,
- implicit default export of all non-`_` names.

This phase should also settle resolver-time validation for unknown exported names and duplicate names inside an explicit
export list.

### Phase 3: Import binding and qualified-name resolution

Teach name resolution to:

- bind alias imports as module namespaces addressable through `alias::name`,
- bind selective imports as ordinary imported values/types in the current scope,
- reject unqualified access to symbols that were imported only through an alias,
- keep ambiguity behavior deterministic when selective imports collide with existing local or imported names.

The implementation should reuse the existing qualified-name path where possible instead of creating a second resolution
mechanism for `::`.

### Phase 4: Grammar, docs, and regression coverage

Update the grammar/reference text and add fixtures covering:

- implicit default exports,
- explicit `export *;`,
- explicit export lists,
- alias-qualified access,
- selective import success and failure,
- collisions between alias names, local names, and imported symbols.

## Diagnostics

1. This plan is expected to need new parse-time diagnostics for malformed `export` and `import ... as` /
   `import ... from` syntax.
2. Provisionally reserve `PAR-0540` to `PAR-0559` for export/import syntax and placement diagnostics.
3. Provisionally reserve `RES-0030` to `RES-0049` for export-surface and import-binding resolution diagnostics such as
   unknown exported names, duplicate explicit exports, and invalid alias/selective import bindings.
4. Re-check the live catalog at implementation time before assigning final numbers. If any proposed slot has been used
   in the meantime, choose a different free block then.

## ADR Impact

- Decision: Define L1 module visibility through one export manifest and provide open, aliased, and selective import
  forms.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0009-module-visibility-exports-imports.md`
  - Rationale: ADR-0009 records the explicit and implicit export rules, import spellings, and public-surface enforcement
    implemented by this plan.

## Non-Goals

1. `.l1m` interface emission.
2. Linkage changes in generated C.
3. Object-name mangling.
4. Package management or manifest files.
5. C FFI syntax.

## Verification Criteria

1. `export *;`, `export foo, bar;`, `import mod as alias;`, and `import foo, bar from mod;` parse successfully.
2. The resolver computes the correct public surface under explicit and implicit export rules.
3. Alias-qualified access works through `alias::name` and does not leak unqualified bindings accidentally.
4. Selective import resolution and ambiguity behavior are covered by parser and semantic tests.
5. Any newly assigned diagnostic codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md`.

## Completion Notes

Implemented in L1 Stage 1. The parser now accepts export manifests, aliased imports, and selective imports; the resolver
computes explicit and implicit export surfaces, resolves alias-qualified references, and keeps redundant same-module
imports idempotent while warning for redundant selective imports and duplicate open imports. The CLI build/run path now
prints non-fatal analysis diagnostics before executing generated programs.
