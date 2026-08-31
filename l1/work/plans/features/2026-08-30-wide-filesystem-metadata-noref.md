# Feature Plan

## Widen L1 filesystem metadata

- Date: 2026-08-30
- Status: Draft
- Title: Widen L1 filesystem metadata to 64-bit extents and timestamp seconds
- Kind: Feature
- Severity: High
- Priority: 1
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Subsystem: Stdlib / runtime / filesystem
- Modules:
  - `l1/compiler/shared/l1/stdlib/sys/rt.l1`
  - `l1/compiler/shared/l1/stdlib/std/fs.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l1/docs/reference/standard-library.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/project-status.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_test.l0`
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_support_test.py`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Repro: `make -C l1 test-stage1 TESTS="compiler_filesystem_test l0c_lib_test"`

## Summary

Correct the inherited L0-era width leak in L1 file metadata before the API hardens. File sizes and modification seconds
become `long?`; normalized modification nanoseconds remain `int?`. Whole-file string helpers and individual buffer
transfer counts remain intentionally `int`-bounded.

## Current State

`sys.rt::RtFileInfo` and `std.fs::FileInfo` use `int?` for `size` and `mtime_sec`. The runtime already receives wider
host values through `off_t` or `_stat64`, then discards values that do not round-trip through `dea_int`. L1 itself has
native `long`, and no L0 file-handle ABI constrains the L1 surface.

## Scope

1. Change `RtFileInfo.size` and `RtFileInfo.mtime_sec` to `long?`.
2. Mirror those types in `std.fs::FileInfo`, `file_size`, and `mtime_sec`.
3. Preserve `mtime_nsec: int?` because its normalized range fits `int`.
4. Return representable host 64-bit values without narrowing through `dea_int`.
5. Add fixtures for sparse files larger than `INT32_MAX` where the host supports them.
6. Update stable current-state docs only when the implementation lands.

## Non-Goals

- changing string, array, slice, or buffer lengths to `long`
- adding 64-bit whole-file string helpers
- implementing open, seek, or incremental file I/O
- widening general wall, monotonic, and duration seconds in this plan
- preserving the current L1 `int?` metadata signature as a compatibility overload

## ADR Impact

- Decision: Use `long?` for L1 file size and modification seconds while keeping normalized nanoseconds and in-memory
  transfer quantities `int`-sized.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: L1 has native 64-bit integers, host files commonly exceed 2 GiB, and the current narrowing is an
    inherited bootstrap limitation rather than a compatibility contract.

## Verification Criteria

1. `FileInfo` and `RtFileInfo` expose `long?` size and modification seconds.
2. Sparse files beyond 2 GiB report their exact size on supported test hosts.
3. Pre-epoch or post-2038 host timestamps survive when the platform can represent them.
4. Nanoseconds remain normalized and `int?`.
5. Whole-file reads still reject files that cannot fit in one Dea string through a structured error path once that
   consumer adopts the shared error model.
