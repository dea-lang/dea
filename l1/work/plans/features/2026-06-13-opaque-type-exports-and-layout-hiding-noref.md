# Feature Plan

## Add opaque type exports and layout-hiding visibility

- Date: 2026-06-13
- Status: Draft
- Title: Add opaque type exports and layout-hiding visibility
- Kind: Feature
- Severity: High
- Stage: L1
- Subsystem: Analysis / signature resolution / interface emission / parser / docs
- Parent Initiative: [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative]
- Modules:
  - `l1/compiler/stage1_l0/src/signatures.l0`
  - `l1/compiler/stage1_l0/src/parser/decl.l0`
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/docs/specs/compiler/module-visibility-and-imports.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
- Related:
  - [`l1/docs/decisions/0013-opaque-type-exports-and-layout-hiding-visibility.md`][adr-0013]
  - [`l1/docs/specs/compiler/module-visibility-and-imports.md`][visibility-spec]
  - [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative]
  - [`docs/specs/compiler/diagnostic-code-catalog.md`][diag-catalog]
- Repro: None

## Summary

[ADR-0013] adopts layout-hiding field visibility for L1, with opacity derived from it and `export opaque T` as sugar for
"export the name, hide all fields." This plan implements the two endpoints of that model (transparent and fully opaque)
plus the exported-surface typing rule that makes the `.l1m` interface self-contained. It closes the latent soundness gap
where an exported signature can reference an unexported type, which resolves under whole-source compilation but produces
an interface that names a type defined nowhere in it under separate compilation ([initiative 0001][initiative]).

## Current State

- `sig_resolve_func` in `signatures.l0` resolves parameter and return types within the defining module's scope, against
  no export set, so an exported signature mentioning an unexported type resolves cleanly today.
- The export manifest (`signatures.l0` / `decl.l0`) supports `export *;` and `export a, b;` with no per-type modifier.
- Interface projection emits every exported struct/enum with full structural layout; there is no forward-declaration
  form.
- There is no test covering a private type appearing in a public signature.

## Goal

- Parse `export opaque T` (the `opaque` qualifier on an exported type name) and record per-type visibility state
  (transparent vs opaque) in the export set.
- Enforce the exported-surface typing rule in `sig_resolve_func` and the analogous aggregate layout-closure check, one
  level deep:
  - by pointer (`U*`): the pointee name must be exported (opaque or transparent);
  - by value: the type must be transparent;
  - unexported in either position is an error.
- Project opaque types into `.l1m` as explicit name-only declarations and transparent types with full layout. The
  transparent-only Step 2 interface artifact tranche does not emit or parse opaque declarations yet.
- Reject mixed/partial field visibility with a not-yet-implemented diagnostic.

## Implementation Phases

### Phase 1: Parse and represent opacity

Extend the export-manifest parser (`decl.l0`) for the `opaque` qualifier and carry a per-type visibility state on the
export set (`signatures.l0` / `analysis.l0`). Reject `opaque` on non-type symbols and under `export *;`.

### Phase 2: Exported-surface typing rule

In `sig_resolve_func` and the aggregate-export path, check each referenced type against the module export set with the
by-value/by-pointer split, and add the one-level layout-closure check for transparent aggregates (by-value field edges
must be transparent; pointer fields place the pointee at the frontier and stop the walk). Report at the exporting
definition in the defining module.

### Phase 3: Interface projection

Update the `.l1m` emitter so opaque types project as explicit name-only declarations:

```dea
opaque struct T == "";
opaque enum E == "";
```

Transparent types continue to project with full layout (the rule collapses to "project the exported fields"). Round-trip
the explicit opaque declarations through the interface parser, reject bodyless non-opaque declarations such as
`struct T == "";`, and reject `opaque` before non-nominal interface declarations.

## Diagnostics

New diagnostics are provisional and must be re-checked against the live [diagnostic-code catalog][diag-catalog] at
implementation time before final numbers are assigned. These are export-surface visibility rules, nearest to the
existing `RES-0030`..`RES-0036` export/visibility block; the alternative home is the `SIG` family, since the checks run
in `signatures.l0`. Confirm the family against the live catalog before assigning:

- `RES-0037` (provisional): unexported type referenced in an exported function signature or exported aggregate field.
- `RES-0038` (provisional): opaque type used by value where a transparent type is required.
- `RES-0039` (provisional): mixed or partial field visibility is not yet implemented.

## Non-Goals

- Mixed/partial per-field visibility and its declaration syntax (`export T hiding { ... }` vs a positive list); rejected
  with `RES-0039` for now.
- A "sized-opaque" rung exporting size and alignment while hiding fields.
- Per-variant enum visibility; enums stay all-or-none.
- Checked-opacity drift-guard annotation; read-only-but-visible fields; submodule/friend visibility.

## Verification Criteria

- `make test-stage1` and `make test-stage1-trace` pass.
- New tests: private-type-in-public-signature is now diagnosed; opaque-pointer round trip across two modules compiles
  and runs; by-value use of an opaque type is rejected; nested-struct closure cases (by-value chain, pointer frontier,
  unexported intermediary) behave per the rule; `.l1m` emits explicit `opaque struct` / `opaque enum` declarations and
  the interface parser reads them back.
- The visibility spec and ADR-0013 match the implemented behavior.

[adr-0013]: ../../../docs/decisions/0013-opaque-type-exports-and-layout-hiding-visibility.md
[diag-catalog]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[initiative]: ../../initiatives/0001-separate-compilation-and-linking.md
[visibility-spec]: ../../../docs/specs/compiler/module-visibility-and-imports.md
