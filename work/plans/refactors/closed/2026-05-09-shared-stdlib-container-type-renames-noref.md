# Refactor Plan

## Rename shared stdlib container outliers to `Type1Type2Container`

- Date: 2026-05-09
- Status: Completed
- Title: Rename shared stdlib container outliers to `Type1Type2Container`
- Kind: Refactor
- Severity: Medium
- Stage: Shared
- Scope: Shared
- Targets:
  - `l0` stdlib / compiler / docs / tests
  - `l1` stdlib / compiler / docs / tests
- Origin: shared stdlib naming policy
- Porting rule: mechanical parity across L0 and L1
- Target status:
  - `l0`: Completed
  - `l1`: Completed
- Subsystem: Stdlib / compiler / docs / tests
- Modules:
  - `l0/compiler/shared/l0/stdlib/std/vector.l0`
  - `l0/compiler/shared/l0/stdlib/std/linear_map.l0`
  - `l0/compiler/shared/l0/stdlib/std/hashmap.l0`
  - `l0/compiler/shared/l0/stdlib/std/hashset.l0`
  - `l0/compiler/shared/l0/stdlib/std/text.l0`
  - `l1/compiler/shared/l1/stdlib/std/vector.l1`
  - `l1/compiler/shared/l1/stdlib/std/linear_map.l1`
  - `l1/compiler/shared/l1/stdlib/std/hashmap.l1`
  - `l1/compiler/shared/l1/stdlib/std/hashset.l1`
  - `l1/compiler/shared/l1/stdlib/std/text.l1`
  - `l0/docs/reference/standard-library.md`
  - `l0/docs/reference/ownership.md`
  - `l1/docs/reference/standard-library.md`
  - `l1/docs/reference/ownership.md`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage1_py/tests/backend/test_string_runtime.py`
  - `l0/compiler/stage1_py/tests/backend/test_trace_arc.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_l0_filter.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_latex.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_markdown_renderer.py`
  - `l0/compiler/stage2_l0/tests/string_vector_test.l0`
  - `l0/compiler/stage2_l0/tests/map_test.l0`
  - `l0/compiler/stage2_l0/tests/hashmap_test.l0`
  - `l0/compiler/stage2_l0/tests/util_text_test.l0`
  - `l1/compiler/stage1_l0/tests/string_vector_test.l0`
  - `l1/compiler/stage1_l0/tests/map_test.l0`
  - `l1/compiler/stage1_l0/tests/hashmap_test.l0`
  - `l1/compiler/stage1_l0/tests/util_text_test.l0`

## Summary

This shared refactor removes the remaining public stdlib container names that still used `ContainerType` or
`ContainerKeyValue` ordering instead of the prevailing `Type1Type2Container` order.

The change is a hard rename across both levels. It updates the public specialized container types, their specialized
entry structs, their specialized helper families, and the directly named string-vector test files. No compatibility
aliases remain in active code.

## Goal

1. Rename `VectorString` to `StringVector`.
2. Rename `LinearMapStringString` to `StringStringLinearMap`.
3. Rename `LinearMapIntString` to `IntStringLinearMap`.
4. Rename `LinearMapStringStringEntry` to `StringStringLinearMapEntry`.
5. Rename `LinearMapIntStringEntry` to `IntStringLinearMapEntry`.
6. Rename the specialized helper families from `vs_*` to `sv_*`, `lmss_*` to `sslm_*`, and `lmis_*` to `islm_*`.
7. Keep the generic `VectorBase`, `LinearMapBase`, `LinearMapEntryBase`, `vec_*`, and `lm_*` APIs unchanged.

## Defaults Chosen

1. This is a naming-only refactor.
2. No runtime ABI changes are introduced.
3. No ownership rules change.
4. No compatibility aliases or mixed old/new transition period are kept.
5. Historical closed plans stay unchanged unless a live doc would otherwise be misleading.

## Implementation Result

1. Shared L0 and L1 stdlib declarations and implementations now use `StringVector`, `StringStringLinearMap`, and
   `IntStringLinearMap`.
2. Specialized entry structs and specialized helper prefixes now follow the new ordering consistently.
3. Compiler sources, tests, fixtures, and user-facing docs in both levels now reference only the new names.
4. The directly named string-vector suites were renamed to `string_vector_test.l0` in both levels.

## Non-Goals

1. No semantic changes to vector or map behavior.
2. No rename of already-conforming types such as `StringIntMap`, `StringPtrMap`, `StringSet`, `ArrayBase`, or
   `ByteArray`.
3. No changes to generic container internals beyond specialized naming references.

## Verification Criteria

1. `rg` finds no unexplained active-tree uses of `VectorString`, `LinearMapStringString`, `LinearMapIntString`,
   `LinearMapStringStringEntry`, `LinearMapIntStringEntry`, `vs_`, `lmss_`, `lmis_`, `_lmss_`, or `_lmis_`.
2. `make -C l0 test-stage1` passes.
3. `make -C l0 test-stage2` passes.
4. `make -C l1 test-stage1` passes.
5. The targeted Stage 1 Python docgen/backend tests that asserted the old names pass with updated expectations.

## Validation Snapshot

1. `make -C l0 test-stage1`
2. `make -C l0 test-stage2`
3. `make -C l1 test-stage1`
4. `./.venv/bin/pytest -q l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py::test_codegen_identity_cast_place_copy_retains l0/compiler/stage1_py/tests/backend/test_string_runtime.py::test_string_text_helpers_runtime l0/compiler/stage1_py/tests/backend/test_trace_arc.py::test_trace_arc_optional_unwrap_into_vector_stabilized l0/compiler/stage1_py/tests/cli/test_docgen_l0_filter.py l0/compiler/stage1_py/tests/cli/test_docgen_latex.py::test_normalize_latex_site_recovers_nullable_l0_struct_fields_from_source l0/compiler/stage1_py/tests/cli/test_docgen_markdown_renderer.py::test_render_markdown_site_recovers_nullable_l0_struct_fields_from_source l0/compiler/stage1_py/tests/cli/test_docgen_markdown_renderer.py::test_render_markdown_site_normalizes_l0_function_signature_spacing`
