# Bug Fix Plan

## Preserve qualified type identity in L0 C name mangling

- Date: 2026-11-26
- Status: Completed
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
  - `l0/compiler/stage2_l0/src/c_emitter/wrappers.l0`
  - `l0/compiler/stage2_l0/src/c_emitter/declarations.l0`
  - `l0/compiler/stage2_l0/src/c_emitter/values.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_driver_cross_module_runtime.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_from_files.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_type_ordering.py`
  - `l0/compiler/stage1_py/tests/backend/test_runtime_public_header.py`
  - `l0/compiler/stage2_l0/tests/c_emitter_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_codegen_test.py`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l0/compiler/stage2_l0/tests/l0c_lib_test.l0`
- Related:
  - [l0/docs/reference/c-backend-design.md](../../../../../l0/docs/reference/c-backend-design.md)
  - [l0/docs/decisions/0027-public-c-runtime-header.md](../../../../../l0/docs/decisions/0027-public-c-runtime-header.md)
- Repro: Import `aaa.bbb` and `aaa_bbb`, each declaring `struct V` with a different field. Construct and read both
  values in one program, then compile the generated C99.

## Summary

Both stages lost the distinction between the two module names. In Stage 1 a shared definition guard suppressed one
struct definition. Stage 2 emitted the same tag, `l0_aaa_bbb_V`, for both structs. Analysis succeeded, but Clang
rejected the initializer and access for the missing `right` field. Importing both types is valid L0.

## Fixes and regression tests

Use `l0_` followed by the dot-separated module components and the local struct or enum name, joined by single
underscores. Prefix each component containing an underscore with its decimal ASCII byte length, then copy the component
verbatim. Copy other components verbatim. A digit at a component boundary always starts a length because L0 identifiers
cannot begin with digits. This gives `l0_aaa_bbb_V` for `aaa.bbb::V` and `l0_7aaa_bbb_V` for `aaa_bbb::V`. Preserve case
in nominal wrapper guards and retain the existing runtime builtin guard spellings.

Both stages now use the encoded name for forward declarations, definitions, guards, type references, constructors, enum
tags and optional wrappers. The public runtime record tags and extern function names keep their established spellings.
Handwritten C that refers directly to an affected generated type must use the revised tag.

The shared fixture constructs both `V` types and reads their different fields through same-named enums. It also
exercises `V?` and `v?` in one module. Reversing the imports exposed the opposite missing field before the fix.

## Verification

Local validation used Apple Clang from `l0/`.

- Stage 1 passed 52 tests across the four backend pytest modules listed above, including strict C compilation in both
  import orders and foreign C linking against the public runtime header.
- `make test-stage2 TESTS="c_emitter_test l0c_lib_test l0c_build_run_test l0c_codegen_test"` passed all four Stage 2
  cases, including both import orders and existing C goldens.
- Both stages emitted identical struct and enum declaration lines and guard directives for each fixture entry.
  `c_emitter_test` also covers multi-digit lengths and leading, trailing and repeated underscores.
- `make test-stage2-trace TESTS=c_emitter_test` reported zero leaked objects and zero leaked strings.

## ADR Impact

- Decision: Preserve the distinct identities of L0 declarations when naming C types.
  - Scope: L0
  - Disposition: Amend ADR
  - ADR: `l0/docs/decisions/0011-c-emission-strategy.md`
  - Rationale: The repair changes a documented generated-name convention. Record its identity and compatibility
    guarantees alongside the emitter's C99 contract.
