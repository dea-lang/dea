# Bug Fix Plan

## Shared drop precheck before generated cleanup

- Date: 2026-07-03
- Status: Completed
- Title: Validate stale `drop` pointers before generated ARC cleanup dereferences pointees
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L0 runtime repro where `zap(p); zap(p);` on a struct with a `string` field can segfault before `_rt_drop`
  reports the stale pointer
- Porting rule: Settle the runtime helper and lowering order in L0 Stage 1, port mechanically to L0 Stage 2, and mirror
  the same behavior in L1 Stage 1 including fixed-array cleanup.
- Target status:
  - L0 Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Runtime allocation tracking and backend `drop` cleanup lowering
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage2_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage1_py/tests/backend/test_trace_memory.py`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
- Related:
  - `l0/docs/reference/ownership.md`
  - `l1/docs/reference/ownership.md`
- Repro: `l0c --run --trace-memory` on a program that calls a helper with `drop p` twice for the same `Box*`

## Summary

Generated `drop` lowering currently cleans ARC-managed fields before calling the runtime `_rt_drop` helper. If a stale
alias reaches `drop`, the cleanup path can dereference freed pointee storage before the allocation tracker has a chance
to report `drop: pointer not allocated by 'new'`. Depending on allocator state, the same invalid program may therefore
produce either the intended software failure or a segmentation fault.

## Root Cause

The allocation tracker validation is tied to `_rt_drop`, but `_rt_drop` is emitted after generated cleanup for structs,
enums, direct ARC pointees, and L1 heap fixed arrays. That ordering assumes the pointer is safe to dereference before
the runtime check proves it is still registered.

## Scope of This Fix

1. Add an internal runtime precheck helper that validates `new` allocation membership without unregistering or freeing
   the pointer.
2. Emit the precheck immediately before any generated `drop` cleanup that dereferences the pointee.
3. Keep final `_rt_drop` as the only unregister/free step.
4. Preserve valid-drop memory traces by keeping the precheck silent on success and on `null`.
5. Update L0 and L1 ownership docs to document the validation order.

## Non-Goals

- New user-facing syntax, diagnostics, or ownership annotations.
- Interprocedural ownership/liveness analysis for callees that drop borrowed pointer parameters.
- Full temporal safety for arbitrary stale pointer dereferences outside `drop`.

## Verification Criteria

- L0 Stage 1 generated C contains precheck before ARC cleanup and final `_rt_drop` after cleanup.
- L0 Stage 2 and L1 Stage 1 runtime regressions abort deterministically with `drop: pointer not allocated by 'new'` for
  the double-drop-through-helper repro.
- The invalid-drop repro emits only one ARC cleanup for the owned heap string field.
- Valid drop trace tests continue to see unchanged `new_alloc` and `drop free` events.

## Outcome

- Added silent success-path drop precheck helpers to the L0 header runtime and the L1 split runtime.
- Updated L0 Stage 1, L0 Stage 2, and L1 Stage 1 drop lowering so cleanup-bearing drops validate the pointer before
  generated cleanup dereferences it.
- Covered the stale helper-mediated double-drop repro in L0 Stage 1, L0 Stage 2, and L1 Stage 1.
- Updated L0 and L1 ownership docs to document validation before generated cleanup.

## Verification

```bash
cd l0 && ../.venv/bin/python -m pytest compiler/stage1_py/tests/backend/test_codegen_semantics.py::test_codegen_drop_precheck_precedes_struct_cleanup compiler/stage1_py/tests/backend/test_trace_memory.py::test_trace_memory_double_drop_precheck_precedes_arc_cleanup -q
cd l0 && make test-stage2 TESTS="c_emitter_test backend_test l0c_stage2_arc_trace_regression_test.py"
cd l1 && make test-stage1 TESTS="c_emitter_test backend_test l1c_stage1_arc_trace_regression_test.py"
cd l0 && ../.venv/bin/python -m pytest compiler/stage1_py/tests/backend/test_trace_memory.py -q
make clean test-all
```
