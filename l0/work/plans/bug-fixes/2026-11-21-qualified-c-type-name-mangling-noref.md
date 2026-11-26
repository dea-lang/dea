# Bug Fix Plan

## Preserve qualified type identity in L0 C name mangling

- Date: 2026-11-26
- Status: Draft
- Title: Preserve qualified type identity in L0 C name mangling
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: C name mangling and type emission
- Modules:
  - `l0/compiler/stage1_py/l0_c_names.py`
  - `l0/compiler/stage1_py/l0_c_types.py`
  - `l0/compiler/stage1_py/l0_c_values.py`
  - `l0/compiler/stage1_py/l0_c_declarations.py`
  - `l0/compiler/stage2_l0/src/c_emitter/names.l0`
  - `l0/compiler/stage2_l0/src/c_emitter/types.l0`
  - `l0/compiler/stage2_l0/src/c_emitter/declarations.l0`
  - `l0/compiler/stage2_l0/src/c_emitter/values.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_driver_cross_module_runtime.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_type_ordering.py`
  - `l0/compiler/stage1_py/tests/backend/test_runtime_public_header.py`
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
rejected the initializer and access for the missing `right` field. Importing both types is valid L0.

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
2. Record the resulting C names for both `struct V` declarations as worked examples in the L0 backend reference. L1's
   length-prefixed module components provide a precedent.
   [l1/docs/specs/compiler/abi.md](../../../../l1/docs/specs/compiler/abi.md)

## Verification

From `l0/`, run the listed Stage 1 pytest modules with `../.venv/bin/python -m pytest -q`. The duplicate-tag regression
must pass semantic analysis and host compilation and must read the correct fields at runtime. Run
`make test-stage2 TESTS="c_emitter_test l0c_codegen_test"` from `l0/`. Verify both import orders in each stage.

## ADR Impact

- Decision: Preserve the distinct identities of L0 declarations when naming C types.
  - Scope: L0
  - Disposition: Amend ADR
  - ADR: `l0/docs/decisions/0011-c-emission-strategy.md`
  - Rationale: The repair changes a documented generated-name convention. Record its identity and compatibility
    guarantees alongside the emitter's C99 contract.
