# Bug Fix Plan

## Honor module qualifiers

- Date: 2026-11-21
- Status: Draft
- Title: Honor module qualifiers
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: Name resolution, enum patterns, and intrinsic dispatch
- Modules:
  - `l0/compiler/stage1_py/l0_resolve.py`
  - `l0/compiler/stage1_py/l0_check_expr.py`
  - `l0/compiler/stage1_py/l0_check_patterns.py`
  - `l0/compiler/stage1_py/l0_analysis.py`
  - `l0/compiler/stage1_py/l0_backend_lowering.py`
  - `l0/compiler/stage2_l0/src/type_resolve.l0`
  - `l0/compiler/stage2_l0/src/expr_types/expr.l0`
  - `l0/compiler/stage2_l0/src/expr_types/patterns.l0`
  - `l0/compiler/stage2_l0/src/backend/initializers.l0`
  - `l0/compiler/stage2_l0/src/backend/lowering.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/name_resolver/test_qualified_names.py`
  - `l0/compiler/stage1_py/tests/integration/test_ord_intrinsic.py`
  - `l0/compiler/stage1_py/tests/type_checker/test_sizeof_type_alias.py`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
- Related:
  - [l0/docs/decisions/0012-name-disambiguation.md](../../../../l0/docs/decisions/0012-name-disambiguation.md)
  - [docs/specs/compiler/diagnostic-code-catalog.md](../../../../docs/specs/compiler/diagnostic-code-catalog.md)
  - [l0/docs/reference/grammar.md](../../../../l0/docs/reference/grammar.md)
- Repro: Import a module defining `sizeof(x: int) -> int` with body `return 37;`. Call `dep::sizeof(1)` and observe the
  generated C intrinsic and the wrong return value.

## Summary

Both stages dispatch qualified intrinsic names by spelling. Native Stage 2 returned 4 from `dep::sizeof(1)` and 1 from
`dep::ord(dep::B)` although both functions were defined to return 37. Stage 1 also accepts an imported enum variant
under the wrong owner. Stage 2 already diagnoses that pattern.

## Fixes and regression tests

1. **Current-module qualification.** Preserve an explicit qualifier when selecting the symbol table in `resolve_symbol`.
   Qualified lookup uses declarations owned by the named module. Unqualified lookup retains open imports, local
   shadowing, and ambiguity handling. Define `Red` only in `remote`, import it in `main`, and match a `remote::Color`
   using `main::Red`. Assert `TYP-0102` and that the rejected arm contributes no coverage. Exercise valid `remote::Red`,
   a genuine local `main::Red`, and an unqualified imported variant as controls. Retain the Stage 2 results as controls:
   the wrong owner gives `TYP-0102` and leaves the match non-exhaustive, and `remote::Red` checks.

2. **Qualified intrinsic spellings.** Resolve qualified calls to `sizeof` and `ord` as ordinary qualified names. Have
   lowering consume the intrinsic identity established by analysis so it cannot reinterpret a resolved function by its
   spelling. Declare `dep::sizeof` and `dep::ord` to return 37. Compile and execute `dep::sizeof(1)` and
   `dep::ord(dep::B)` with `B` the second enum variant. Both results must be 37, independent of host C sizes. Require
   the existing callee-lookup diagnostic (`TYP-0189`) for `missing_module::sizeof(1)` and `missing_module::ord(B)`.
   These operands are valid for the bare intrinsics. Keep bare `sizeof` on a type alias and bare enum `ord` as controls.
   Cover an existing but unimported module as well. Exercise both stages' check and run paths. Audit the Stage 2
   initializer emitter for the same name-only dispatch.

## Verification

Run the listed pytest modules from `l0/` with `../.venv/bin/python -m pytest -q` and their level-relative paths. Run
`make test-stage2 TESTS="expr_types_test l0c_build_run_test"` there. Compare the executable results from
`./scripts/l0c --run` and `./build/dea/bin/l0c-stage2 --run` on the same fixtures. Recheck the registered diagnostic
meanings against the live catalog and cover both qualified lookup and intrinsic dispatch.

## ADR Impact

- Decision: An explicit module qualifier identifies the owner of a declaration, including a callable whose name also
  spells an intrinsic.
  - Scope: L0
  - Disposition: Covered by ADR
  - ADR: `l0/docs/decisions/0012-name-disambiguation.md`
  - Rationale: Both lookup fixes enforce the accepted meaning of a qualified reference.
