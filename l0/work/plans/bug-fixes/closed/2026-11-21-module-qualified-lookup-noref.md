# Bug Fix Plan

## Honor module qualifiers and reserve the L0 intrinsic names at module scope

- Date: 2026-11-27
- Status: Completed
- Title: Honor module qualifiers and reserve the L0 intrinsic names at module scope
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: Name resolution, enum patterns, and intrinsic dispatch
- Modules:
  - `l0/compiler/stage1_py/l0_name_resolver.py`, `l0/compiler/stage1_py/l0_resolve.py`,
    `l0/compiler/stage1_py/l0_check_expr.py`, `l0/compiler/stage1_py/l0_expr_types.py`,
    `l0/compiler/stage1_py/l0_backend_lowering.py`
  - `l0/compiler/stage2_l0/src/name_resolver.l0`, `l0/compiler/stage2_l0/src/signatures.l0`,
    `l0/compiler/stage2_l0/src/expr_types/expr.l0`, `l0/compiler/stage2_l0/src/backend/initializers.l0`,
    `l0/compiler/stage2_l0/src/backend/lowering.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/name_resolver/test_qualified_names.py`
  - `l0/compiler/stage1_py/tests/backend/test_driver_cross_module_runtime.py`
  - `l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`
  - `l0/compiler/stage2_l0/tests/name_resolver_test.l0`, `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
- Related:
  - [l0/docs/decisions/0012-name-disambiguation.md](../../../../docs/decisions/0012-name-disambiguation.md)
  - [l0/docs/decisions/0028-module-scope-intrinsic-names.md](../../../../docs/decisions/0028-module-scope-intrinsic-names.md)
  - [work/plans/bug-fixes/closed/2026-11-26-shared-c-field-name-emission-noref.md](../../../../../work/plans/bug-fixes/closed/2026-11-26-shared-c-field-name-emission-noref.md)

## Summary

Both stages previously selected intrinsics by the final identifier alone. For example, Stage 2 returned 4 from
`dep::sizeof(1)` even though the declared function returned 37. Stage 1 also searched open imports for an enum pattern
explicitly qualified with the current module, allowing a wrong-owner arm to count toward match coverage.

Both stages now issue `RES-0011` at a module declaration of `sizeof` or `ord`, including an unused declaration in an
imported module. Enum variants carry their own source spans. Parameters, locals, pattern variables, fields and module
path components keep their ordinary spellings. A scan of the L0 standard library, Stage 2 compiler, L0 examples and L0
sources of the L1 compiler found no affected module declarations.

Only a bare callee selects intrinsic checking and lowering. An explicit module qualifier selects that owner's own
declarations. A missing qualified callee receives `TYP-0189`. Stage 1 uses the same expression checker for resolved
module initializers and function bodies. Stage 2 also applies the bare-name test when classifying and emitting static
initializers. Both stages preserve the existing signature inference rules for unannotated top-level bindings.

## Verification

The shared programs in `l0/tests/fixtures/intrinsic_names/` exercise both spellings across seven kinds of module
declaration, both intrinsics alongside local bindings, and qualified calls with current, imported, transitively loaded
and unknown module owners. Both compilers run the positive program to exit 0. They accept the field declarations during
checking. Both report `TYP-0102` for the wrong-owner pattern and `TYP-0104` for the missing variant.

Local validation with Clang on macOS passed:

- Stage 1 passed 368 tests across the qualified-name, resolver-environment, cross-module execution, `ord`, `sizeof`
  alias, top-level binding, control-flow and diagnostic-code pytest modules.
- Stage 2 passed `name_resolver_test`, `signatures_test`, `expr_types_test`, `c_emitter_test`, `l0c_build_run_test` and
  `l0c_stage2_toplet_test`. The first four also passed the trace runner with zero leaked objects or strings.
- Direct `--gen` probes in both stages rejected the invalid imports and qualified calls before emitting C.

## ADR Impact

- Decision: An explicit module qualifier identifies the owner of a declaration.

  - Scope: L0
  - Disposition: Covered by ADR
  - ADR: `l0/docs/decisions/0012-name-disambiguation.md`
  - Rationale: Qualified calls and enum patterns follow the accepted owner lookup rule.

- Decision: Reserve `sizeof` and `ord` at L0 module scope and expose both intrinsics through bare calls.

  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/0028-module-scope-intrinsic-names.md`
  - Rationale: This changes which module declarations stable L0 accepts and defines the compatibility boundary with L1's
    shadowable intrinsics.
