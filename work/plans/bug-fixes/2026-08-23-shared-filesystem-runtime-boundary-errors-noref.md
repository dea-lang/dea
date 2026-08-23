# Bug Fix Plan

## Harden shared filesystem runtime boundary errors

- Date: 2026-08-23
- Status: Draft
- Title: Reject canonical empty paths safely and preserve empty-write close failures in L0 and L1 runtimes
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 shared runtime and `std.fs`
  - L1 shared runtime and `std.fs`
- Origin: Settle the boundary contract in the L0 shared runtime, then port the same checks mechanically to the cloned L1
  runtime and stdlib surface.
- Porting rule: Keep path validation and write/close success semantics identical across L0 and L1 while preserving each
  runtime's type and symbol names.
- Target status:
  - L0 shared runtime and `std.fs`: Pending
  - L1 shared runtime and `std.fs`: Pending
- Subsystem: Filesystem runtime / Standard library I/O / C boundary safety
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l0/compiler/shared/l0/stdlib/std/fs.l0`
  - `l0/compiler/shared/l0/stdlib/sys/rt.l0`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/l1/stdlib/std/fs.l1`
  - `l1/compiler/shared/l1/stdlib/sys/rt.l1`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_stdlib_fs_path_raw_io.py`
  - `l0/compiler/stage1_py/tests/backend/test_string_runtime.py`
  - `l0/compiler/stage2_l0/tests/fs_path_test.l0`
  - `l0/compiler/stage2_l0/tests/io_errno_test.l0`
  - `l1/compiler/stage1_l0/tests/fs_path_test.l0`
  - `l1/compiler/stage1_l0/tests/io_errno_test.l0`
  - `l1/compiler/stage1_l0/tests/io_runtime_test.py`
- Related:
  - `l0/work/plans/refactors/closed/2026-03-13-stdlib-fs-io-boundary-cleanup-noref.md`
  - `l0/work/plans/bug-fixes/closed/2026-02-25-stdio-stale-errno-io-wrappers-noref.md`
  - `l0/docs/reference/standard-library.md`
  - `l1/docs/reference/standard-library.md`
- Repro: Call filesystem metadata and deletion with the canonical empty string, then exercise an empty file write under
  an injected `fclose()` failure; the current runtime can pass a null C pointer to path APIs and ignores the close
  failure for empty data.

## Summary

The canonical empty Dea string may expose a null byte pointer at the C runtime boundary. `rt_file_info()` and
`rt_delete_file()` forward that pointer to `stat`/`_stat64` and `remove` without first rejecting an empty path. This is
outside the C APIs' valid input contract and can crash or otherwise behave unpredictably.

`rt_write_file_all()` rejects an empty path but has a second correctness gap: it checks `fclose()` only after a
non-empty `fwrite()`. An empty payload always returns success once `fopen()` succeeds, even if finalization fails. Both
defects exist in the L0 runtime header and the corresponding L1 runtime implementation.

## ADR Impact

- Decision: Validate empty filesystem paths before C API calls and include stream finalization in whole-file write
  success.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The fix enforces the existing fallible filesystem API contract and removes invalid C boundary calls; it
    does not change public signatures or introduce a new I/O policy.

## Current State and Root Cause

1. `rt_file_info()` and `rt_delete_file()` obtain `_rt_string_bytes(path)` before checking path length.
2. The canonical empty-string representation can return `NULL`, which is not a valid path for `stat` or `remove`.
3. `rt_write_file_all()` stores `close_result` only in the `data_len > 0` branch.
4. The empty-data branch calls `fclose(file)` and discards its result.
5. The L1 C runtime is a direct semantic clone of these paths, so fixing only the L0 header would leave generated L1
   programs inconsistent.

## Scope of This Fix

1. Reject empty paths before converting them to C strings in every affected filesystem primitive.
2. Return the existing neutral metadata result or failure value without calling a host path API.
3. Make `rt_write_file_all()` combine write completion and close completion for both empty and non-empty payloads.
4. Add direct runtime-boundary tests that distinguish empty strings from non-empty valid paths.
5. Add an injectable or wrapped close-failure test that does not depend on an unreliable host filesystem condition.
6. Audit sibling whole-file operations for the same empty-path and ignored-finalization shape, expanding scope only when
   the identical defect is confirmed.

## Diagnostics

No compiler diagnostic code is introduced. The existing `bool`/optional runtime and `std.fs` error contracts carry these
failures.

## Non-Goals

1. Adding richer filesystem error objects or exposing host `errno` values.
2. Changing valid empty-file write behavior when close succeeds.
3. Redesigning Dea string storage or requiring every empty string to own a non-null byte buffer.

## Verification

1. Run direct C boundary probes under address/undefined-behavior sanitizers for empty metadata and delete paths.
2. Verify `std.fs` wrappers surface failure without crashing for empty paths in L0 Stage 1, L0 Stage 2, and L1 output.
3. Inject successful and failing close outcomes for empty and non-empty writes.
4. Run the focused filesystem/runtime suites and the repository-root `make test-all` tier.

## Verification Criteria

1. No host filesystem function receives a null path pointer.
2. Empty paths return deterministic existing failure values in both runtimes.
3. A close failure makes `rt_write_file_all()` fail regardless of payload length.
4. L0 and L1 stdlib behavior stays aligned and trace-clean.
