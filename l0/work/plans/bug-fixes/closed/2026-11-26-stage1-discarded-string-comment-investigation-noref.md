# Bug Fix Plan

## Investigate C comment emission for discarded Stage 1 string literals

- Date: 2026-11-27
- Status: Completed
- Title: Investigate C comment emission for discarded Stage 1 string literals
- Kind: Bug Fix
- Severity: Low
- Stage: 1
- Subsystem: Statement-context expression lowering and C comment rendering
- Modules:
  - `l0/compiler/stage1_py/l0_backend_lowering.py`
  - `l0/compiler/stage1_py/l0_c_statements.py`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
- Related:
  - [l0/docs/reference/c-backend-design.md](../../../../../l0/docs/reference/c-backend-design.md)

## Findings and fix

Stage 1 copied the text of a standalone string literal into a C block comment. A discarded filename pattern,
`"examples/*.l0";`, caused Clang to diagnose a nested comment opener and reject the generated C with
`-std=c99 -Werror=comment`. Removing the literal produced a successful build. The string statement has no observable
effect in Dea.

Stage 1 now returns an empty C expression for a string literal used directly as a statement. String literals used as
values still go through the existing encoder.

## Verification

- The regression places the discarded literal between two print calls. With source-line directives disabled, the
  generated translation unit must equal the one for the same program with the statement removed. The test failed before
  the fix and passed afterward.
- Generated both programs with `l0/scripts/l0c --gen` and compiled them with Apple Clang 17 in C99 mode with
  `-Werror=comment`. After the fix, both compiled, printed `before` and `after` on separate lines, and exited 0.
- From `l0/`, `L0_CC=clang ../.venv/bin/python -m pytest -q compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  passed all 49 tests.

## ADR Impact

- Decision: Omit the text of a discarded string literal during Stage 1 statement lowering.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This restores the existing no-op semantics of a literal statement within the C99 emission contract.
