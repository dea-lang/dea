# Refactor Plan

## Rename `sys.unsafe` to `sys.memory`

- Date: 2026-05-08
- Status: Implemented
- Title: Rename `sys.unsafe` to `sys.memory`
- Kind: Refactor
- Severity: Medium
- Stage: Shared
- Scope: Shared
- Targets:
  - `l0` stdlib / docs / tests
  - `l1` stdlib / docs / tests
- Porting rule: Mechanical parity across L0 and L1
- Target status:
  - `l0`: Implemented
  - `l1`: Implemented
- Subsystem: Stdlib / imports / docs / tests
- Modules:
  - `l0/compiler/shared/l0/stdlib/sys/memory.l0`
  - `l1/compiler/shared/l1/stdlib/sys/memory.l1`
  - `l0/compiler/shared/l0/stdlib/std/array.l0`
  - `l0/compiler/shared/l0/stdlib/std/vector.l0`
  - `l0/compiler/shared/l0/stdlib/std/hashmap.l0`
  - `l0/compiler/shared/l0/stdlib/std/hashset.l0`
  - `l0/compiler/shared/l0/stdlib/std/linear_map.l0`
  - `l0/compiler/shared/l0/stdlib/std/text.l0`
  - `l0/compiler/shared/l0/stdlib/std/io.l0`
  - `l1/compiler/shared/l1/stdlib/std/array.l1`
  - `l1/compiler/shared/l1/stdlib/std/vector.l1`
  - `l1/compiler/shared/l1/stdlib/std/hashmap.l1`
  - `l1/compiler/shared/l1/stdlib/std/hashset.l1`
  - `l1/compiler/shared/l1/stdlib/std/linear_map.l1`
  - `l1/compiler/shared/l1/stdlib/std/text.l1`
  - `l1/compiler/shared/l1/stdlib/std/io.l1`
  - `l0/docs/reference/standard-library.md`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_codegen_lvalue_caching.py`
  - `l0/compiler/stage1_py/tests/backend/test_hash_runtime.py`
  - `l0/compiler/stage1_py/tests/backend/test_stdlib_fs_path_raw_io.py`
  - `l0/compiler/stage1_py/tests/backend/test_string_runtime.py`
  - `l0/compiler/stage1_py/tests/backend/test_trace_location.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_markdown_renderer.py`
  - `l0/compiler/stage1_py/tests/integration/test_implicit_conversions.py`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l0/docs/reference/standard-library.md`
  - `l1/docs/reference/standard-library.md`
- Repro: `make -C l0 test-stage1 && make -C l1 test-stage1`

## Summary

An upcoming L1 initiative will reserve `unsafe` as a function modifier. The existing `sys.unsafe` stdlib module blocks
that in L1 because module path components are identifiers and reserved words cannot remain valid identifiers.

This refactor renames the shared L0 and L1 stdlib module path from `sys.unsafe` to `sys.memory`. It deliberately does
not change the runtime C ABI, the `rt_*` function names, or any pointer semantics.

## Implementation Result

1. `compiler/shared/l0/stdlib/sys/memory.l0` and `compiler/shared/l1/stdlib/sys/memory.l1` now declare
   `module sys.memory;`.
2. The L0 and L1 stdlib consumers that previously imported `sys.unsafe` now import `sys.memory`.
3. `l0/docs/reference/standard-library.md` and `l1/docs/reference/standard-library.md` now document the module as
   `sys.memory`.

## Goal

1. Rename the shared stdlib module to `sys.memory`.
2. Update all source imports and qualified references from `sys.unsafe` to `sys.memory`.
3. Update user-facing and reference docs to use `sys.memory`.
4. Keep the refactor behavior-preserving so the upcoming `unsafe` keyword plan starts from a clean import surface.

## Defaults Chosen

1. Module name is `sys.memory`.
2. Function names remain unchanged: `rt_alloc`, `rt_free`, `rt_memcpy`, and the rest of the `rt_*` surface are stable.
3. Runtime C symbols remain unchanged.
4. No compatibility shim module named `sys.unsafe` is retained. The purpose of this plan is to free `unsafe` as a
   keyword.

## Implementation Phases

### Phase 1: Rename module source

1. Keep the moved file names `compiler/shared/l0/stdlib/sys/memory.l0` and `compiler/shared/l1/stdlib/sys/memory.l1`.
2. Change each file's module declaration to `module sys.memory;`.
3. Keep function declarations and comments semantically unchanged except for module naming.

### Phase 2: Update consumers

1. Replace every `import sys.unsafe;` with `import sys.memory;`.
2. Replace any selective imports or qualified references using `sys.unsafe`.
3. Search the stdlib, examples, fixtures, tests, and docs for `sys.unsafe` and update active references.

### Phase 3: Documentation and validation

1. Update the L0 and L1 standard-library references.
2. Run the focused search `rg "sys\\.unsafe"` and document any intentionally preserved historical references.

## Diagnostics

No new diagnostics. This refactor changes module naming only.

## Non-Goals

1. No `unsafe` keyword or parser changes.
2. No `unsafe extern func` annotations.
3. No pointer dereference, pointer indexing, or raw-memory semantic changes.
4. No runtime ABI changes and no rename of any `rt_*` function.

## Verification Criteria

1. `rg "sys\\.unsafe"` reports only intentional historical references, if any.
2. `make -C l0 test-stage1` passes.
3. `make -C l1 test-stage1` passes.
4. Existing stdlib users of `std.array`, `std.vector`, `std.io`, maps, and sets still compile through the relevant
   stage1 test suites.

## Validation Snapshot

1. `make -C l0 test-stage1`
2. `make -C l1 test-stage1`
