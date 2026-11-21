# Bug Fix Plan

## Preserve C type identity and dereference grouping

- Date: 2026-11-21
- Status: Draft
- Title: Preserve C type identity and dereference grouping
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: C name mangling, type emission, and expression rendering
- Modules:
  - `l0/compiler/stage1_py/l0_c_names.py`
  - `l0/compiler/stage1_py/l0_c_types.py`
  - `l0/compiler/stage1_py/l0_c_values.py`
  - `l0/compiler/stage1_py/l0_c_statements.py`
  - `l0/compiler/stage1_py/l0_backend_lowering.py`
  - `l0/compiler/stage2_l0/src/c_emitter/names.l0`
  - `l0/compiler/stage2_l0/src/c_emitter/types.l0`
  - `l0/compiler/stage2_l0/src/c_emitter/declarations.l0`
  - `l0/compiler/stage2_l0/src/c_emitter/values.l0`
  - `l0/compiler/stage2_l0/src/backend/lowering.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_driver_cross_module_runtime.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_type_ordering.py`
  - `l0/compiler/stage1_py/tests/c_emitter/test_c_emitter_runtime_contracts.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage2_l0/tests/c_emitter_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_codegen_test.py`
- Related:
  - [l0/docs/reference/c-backend-design.md](../../../../l0/docs/reference/c-backend-design.md)
  - [l0/docs/decisions/0027-public-c-runtime-header.md](../../../../l0/docs/decisions/0027-public-c-runtime-header.md)
- Repro: Import `aaa.bbb` and `aaa_bbb`, each declaring `struct V` with a different field. Construct and read both
  values in one program, then compile the generated C99.

## Summary

Both stages lose the distinction between the two module names. In Stage 1 a shared definition guard suppresses one
struct definition. Stage 2 emitted the same tag, `l0_aaa_bbb_V`, for both structs. Analysis succeeded, but Clang
rejected the initializer and access for the missing `right` field. Both stages' dereference helpers also misgroup a
compound pointer operand. Ordinary checked-pointer reads and writes passed in Stage 2.

## Fixes and regression tests

1. **Qualified C type identity.** Encode module components and the local type name unambiguously and deterministically.
   Use the same identity for forward declarations, definitions, guards, type references, and derived wrappers or tags.
   Inspect existing public runtime record spellings and foreign-C declarations before changing the encoder. Preserve the
   explicit runtime/FFI contracts and document the revised internal name convention. Add the two-module fixture above
   with fields `left` and `right`; require distinct C identities, compile under C99, and execute reads that verify both
   values. Reverse import order as a control. Run existing public-header interoperability coverage if shared C-visible
   names are touched. Apply the encoding in Stage 2's `cem_mangle_struct_name` and its consumers. Test the two
   identities directly and compile and run the same two-module program through each native-code path. Where golden C
   changes, compare both generators' output to the agreed spelling before updating it.
2. **Compound dereference.** Parenthesize the complete pointer operand in Stage 1's `CValues.emit_deref_lvalue` and
   Stage 2's `cem_emit_deref_lvalue`. Render a C conditional choosing between two valid integer pointers. Compile a
   small C99 harness and exercise both branches as lvalues; each assignment must update only the selected integer.
   Retain a normal source-level checked dereference as a control. For `take_a ? a : b` the native Stage 2 helper
   currently emits `(*take_a ? a : b)`, which tries to dereference the integer condition. Use each helper's output in
   the C99 fixture and assert both integer values after each write. This is a helper regression in both stages.

## Unverified C comment finding

Static inspection found the string-literal statement branch of `Lowering._emit_expr` passing source text to
`CStatements.emit_comment`. The review did not establish a failing translation unit for this observation. During
implementation, check the renderer's treatment of source-derived text and whether discarded literals need any generated
commentary. If the concern is confirmed, use fixed compiler-authored commentary or omit it. Add a regression asserting
that discarded string values cannot alter generated C structure, compile the fixture as C99, and verify normal
executable output. Record the evidence and disposition separately from the two confirmed defects. The native Stage 2
control emitted `"plain marker";` as a discarded `L0_STRING_CONST` expression and ran successfully. Keep this
investigation scoped to Stage 1.

## Verification

From `l0/`, run the listed Stage 1 pytest modules with `../.venv/bin/python -m pytest -q`. The duplicate-tag regression
must pass semantic analysis and host compilation and must read the correct fields at runtime. The compound-operand test
must verify both selected destinations. Run `make test-stage2 TESTS="c_emitter_test l0c_codegen_test"` from `l0/`. These
emitter repairs require no new compiler diagnostic.

## ADR Impact

- Decision: Preserve the distinct identities of L0 declarations when naming C types.
  - Scope: L0
  - Disposition: Amend ADR
  - ADR: `l0/docs/decisions/0011-c-emission-strategy.md`
  - Rationale: The repair changes a documented generated-name convention. Record its identity and compatibility
    guarantees alongside the emitter's C99 contract.
