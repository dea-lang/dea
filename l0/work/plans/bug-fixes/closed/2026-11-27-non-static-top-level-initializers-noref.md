# Bug Fix Plan

## Diagnose non-static L0 top-level let initializers

- Date: 2026-11-27
- Status: Completed
- Title: Diagnose non-static L0 top-level let initializers
- Kind: Bug Fix
- Severity: Medium
- Stage: Shared
- Subsystem: Module-scope initializer checking and diagnostics
- Modules:
  - `l0/compiler/stage1_py/l0_expr_types.py`
  - `l0/compiler/stage1_py/l0_check_compat.py`
  - `l0/compiler/stage1_py/l0_check_expr.py`
  - `l0/compiler/stage1_py/l0_backend_initializers.py`
  - `l0/compiler/stage1_py/l0_c_types.py`
  - `l0/compiler/stage1_py/l0_diagnostics.py`
  - `l0/compiler/stage2_l0/src/expr_types/initializers.l0`
  - `l0/compiler/stage2_l0/src/backend/initializers.l0`
  - `l0/compiler/stage2_l0/src/c_emitter/wrappers.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/integration/test_toplet.py`
  - `l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_toplet_test.py`
  - `l0/tests/fixtures/static_initializers/`
- Related:
  - [l0/docs/reference/c-backend-design.md](../../../../../l0/docs/reference/c-backend-design.md)
  - [docs/specs/compiler/diagnostic-code-catalog.md](../../../../../docs/specs/compiler/diagnostic-code-catalog.md)
- Repro: In a module with `func make_ptr() -> int* { return new int(1); }`, check `let p: int* = make_ptr();`.

## Findings and fix

Both stages previously accepted the call during source checking. Stage 1 then failed with `ICE-1034` during C
generation, and Stage 2 aborted with `ICE-1181`. A direct allocation reached the same Stage 2 failure and produced
`ICE-1180` in Stage 1.

Both source checkers now report `[TYP-0054] A top-level let initializer must be static.` at the first non-static operand
of each successfully typed binding. This covers ordinary calls, allocations, reads of module bindings and other
expressions outside the supported static subset. Signature and type errors retain their own diagnostics. The Stage 2
classifier moved from emission to source checking.

Static value constructors can nest. The checker inspects their evaluated arguments, including payloads of variants
passed to `ord`. Both emitters use the variant's C tag constant for static `ord` and the resolved operand type for
`sizeof`. An ordinary call or allocation inside `sizeof` is type-checked and remains unevaluated. Both emitters collect
nullable types used only as `sizeof` targets so their C definitions are available at file scope.

## Verification

From `l0/` with Clang on macOS:

- `../.venv/bin/python -m pytest -q -n 0 compiler/stage1_py/tests/integration/test_toplet.py compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`
  passed all 284 Stage 1 tests.
- `make test-stage2 TESTS=l0c_stage2_toplet_test` passed.
- Both launchers returned exit 1 with the same nine source diagnostics during `--check`, `--gen`, `--build`, and
  `--run`. Both executed the static cases, including an unevaluated allocating helper, parenthesized enum variants,
  nested constructors and nullable values.

## ADR Impact

- Decision: Report an unsupported L0 initializer through the diagnostic collector during source checking.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0013-compiler-diagnostic-collection-parser-recovery-and-phase-barriers.md`
  - Rationale: The existing phase barrier prevents code generation after a source error. This fix applies it to the
    existing L0 restriction on top-level initialization.
