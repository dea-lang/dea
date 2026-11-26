# Bug Fix Plan

## Investigate C comment emission for discarded Stage 1 string literals

- Date: 2026-11-26
- Status: Draft
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
  - [l0/docs/reference/c-backend-design.md](../../../../l0/docs/reference/c-backend-design.md)

## Evidence and open question

In the string-literal statement branch, `Lowering._emit_expr` passes the literal's value to `CStatements.emit_comment`.
Static inspection identified this path. Whether it affects the structure or behavior of a generated C translation unit
remains unverified. The original Stage 2 control emitted a discarded `L0_STRING_CONST` expression for `"plain marker";`
and ran successfully.

## Investigation and disposition

1. Trace a discarded string literal through the normal Stage 1 entry point and inspect the generated C. Compare the
   surrounding statements and the program's output with a control in which the discarded literal is omitted.
2. Record the source-level evidence and C99 compilation and execution results. If the renderer preserves the discarded
   statement's semantics, document the reason and close the investigation. If evidence remains inconclusive, record the
   open question.
3. If a defect is confirmed, omit the unnecessary comment or use fixed compiler-authored text. Cover the confirmed case
   in `test_codegen_semantics.py` and verify that the compiled program preserves the expected output. Run
   `../.venv/bin/python -m pytest -q compiler/stage1_py/tests/backend/test_codegen_semantics.py` from `l0/`.

## ADR Impact

- Decision: Determine whether discarded string statements preserve their semantics in generated C.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The investigation checks an implementation detail against the existing C99 emission contract.
