# Bug Fix Plan

## Honor module qualifiers and reserve the L0 intrinsic names at module scope

- Date: 2026-11-21
- Status: Draft
- Title: Honor module qualifiers and reserve the L0 intrinsic names at module scope
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: Name resolution, enum patterns, and intrinsic dispatch
- Modules:
  - `l0/compiler/stage1_py/l0_name_resolver.py`
  - `l0/compiler/stage1_py/l0_resolve.py`
  - `l0/compiler/stage1_py/l0_check_expr.py`
  - `l0/compiler/stage1_py/l0_check_patterns.py`
  - `l0/compiler/stage1_py/l0_analysis.py`
  - `l0/compiler/stage1_py/l0_backend_lowering.py`
  - `l0/compiler/stage2_l0/src/name_resolver.l0`
  - `l0/compiler/stage2_l0/src/type_resolve.l0`
  - `l0/compiler/stage2_l0/src/expr_types/expr.l0`
  - `l0/compiler/stage2_l0/src/expr_types/patterns.l0`
  - `l0/compiler/stage2_l0/src/backend/initializers.l0`
  - `l0/compiler/stage2_l0/src/backend/lowering.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/name_resolver/test_name_resolver_module_envs.py`
  - `l0/compiler/stage1_py/tests/name_resolver/test_qualified_names.py`
  - `l0/compiler/stage1_py/tests/integration/test_ord_intrinsic.py`
  - `l0/compiler/stage1_py/tests/type_checker/test_sizeof_type_alias.py`
  - `l0/compiler/stage2_l0/tests/name_resolver_test.l0`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
- Related:
  - [l0/docs/decisions/0012-name-disambiguation.md](../../../../l0/docs/decisions/0012-name-disambiguation.md)
  - [docs/specs/compiler/diagnostic-code-catalog.md](../../../../docs/specs/compiler/diagnostic-code-catalog.md)
  - [l0/docs/reference/grammar.md](../../../../l0/docs/reference/grammar.md)
  - [l0/docs/reference/design-decisions.md](../../../docs/reference/design-decisions.md)
  - [work/plans/bug-fixes/2026-11-26-shared-c-field-name-emission-noref.md](../../../../work/plans/bug-fixes/2026-11-26-shared-c-field-name-emission-noref.md)
- Repro: Import a module defining `sizeof(x: int) -> int` with body `return 37;`. Call `dep::sizeof(1)` and observe the
  generated C intrinsic and the wrong return value.

## Summary

Both stages dispatch qualified intrinsic names by spelling. Native Stage 2 returned 4 from `dep::sizeof(1)` and 1 from
`dep::ord(dep::B)` although both functions were defined to return 37. Stage 1 also accepts an imported enum variant
under the wrong owner. Stage 2 already diagnoses that pattern.

## L0 decision

Reserve the exact names `sizeof` and `ord` when collecting a module's own declarations. This covers functions (including
externs), structs, enums, enum variants, type aliases and top-level `let` bindings. Diagnose the declaration even if it
is unused. Both spellings remain identifiers in other contexts, including module path components, parameters, local and
pattern bindings, struct fields and enum payload fields.

Only bare calls invoke the L0 intrinsics: `sizeof(T)`, `sizeof(expr)` and `ord(enum_value)`. Every qualified call uses
ordinary module lookup, including a call qualified with the current module. L0 has no intrinsic module. L1 keeps its
existing lookup rules, including module declarations that shadow intrinsics and explicit access through `dea`. The L0
restriction rejects previously accepted declarations whose calls could change meaning when compiled as L1. A scan of the
L0 standard library, Stage 2 sources, L0 examples and L0 sources of the L1 compiler found no such declarations.

## Fixes and regression tests

Apply the following in Stage 1, then Stage 2:

1. **Current-module qualification.** Preserve the explicit qualifier when selecting the symbol table in
   `resolve_symbol`. Define `Red` only in `remote`, import it in `main`, and match a `remote::Color` using `main::Red`.
   Assert `TYP-0102` for the wrong owner and `TYP-0104` because the rejected arm contributes no coverage. Preserve Stage
   2's existing behavior. Exercise valid `remote::Red`, a genuine local `main::Red`, and an unqualified imported variant
   as controls. Preserve unqualified lookup through open imports, local shadowing and ambiguity handling.

2. **Declaration errors.** Test both names across all module binding kinds, including an unused declaration in an
   imported module. Report an error at the offending declaration. Provisionally use `RES-0011` in the existing top-level
   definition range beside `RES-0010` (duplicate definition). Recheck availability in the live catalog at implementation
   time, then register the reserved-name error for L0 only and use the same code in both stages.

3. **Call dispatch.** Require the existing unknown-callee diagnostic (`TYP-0189`) for either spelling qualified with the
   current module, an imported module, an existing unimported module or an unknown module. Use otherwise valid operands
   and modules without reserved declarations so a declaration error cannot mask a dispatch bug. Cover normal calls and
   top-level initializers. Apply the same bare-call condition during checking and lowering, including Stage 2
   initializer emission. Run positive controls for bare `sizeof` on an alias and an expression, bare enum `ord`,
   ordinary qualified functions, and a parameter or local named `sizeof` used alongside `sizeof(7)`. Use `--check` to
   verify fields with either spelling. Native field emission has its own shared plan.

## Verification

Run the listed pytest modules from `l0/` with `../.venv/bin/python -m pytest -q` and their level-relative paths. Run
`make test-stage2 TESTS="name_resolver_test expr_types_test l0c_build_run_test"` there. Compare the executable results
from `./scripts/l0c --run` and `./build/dea/bin/l0c-stage2 --run` on the same fixtures. Recheck the registered
diagnostic meanings against the live catalog. Update the L0 reference with the declaration restriction and bare-call
syntax when both stages implement them.

## ADR Impact

- Decision: An explicit module qualifier identifies the owner of a declaration.

  - Scope: L0
  - Disposition: Covered by ADR
  - ADR: `l0/docs/decisions/0012-name-disambiguation.md`
  - Rationale: Qualified calls and enum patterns follow the accepted owner lookup rule.

- Decision: Reserve `sizeof` and `ord` at L0 module scope and expose both intrinsics through bare calls.

  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/`
  - Rationale: This changes which module declarations stable L0 accepts and defines the compatibility boundary with L1's
    shadowable intrinsics.
