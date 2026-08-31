# Feature Plan

## Add a shared OS error and I/O result model

- Date: 2026-08-30
- Status: Draft
- Title: Add a shared OS error and I/O result model
- Kind: Feature
- Severity: High
- Priority: 1
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Subsystem: Stdlib / runtime / filesystem / process / networking
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/os.l1`
  - `l1/compiler/shared/l1/stdlib/sys/os.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l1/compiler/shared/runtime/src/dea_rt_sys.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
- Test modules:
  - `l1/compiler/stage1_l0/tests/os_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/docs/reference/standard-library.md`
- Repro: `make -C l1 test-stage1 TESTS="os_runtime_test l0c_lib_test"`

## Summary

Introduce the common error contract that new file, process, pipe, and socket APIs require. Failed runtime operations
return their error directly, portable code branches on a normalized `ErrorKind`, and diagnostics retain the native host
code. EOF, timeouts, and successful partial transfers remain operation states rather than being collapsed into errors.

## Current State

Existing stdlib wrappers commonly return `null`, `false`, or `-1`. Callers cannot reliably distinguish not-found,
permission, invalid-handle, interrupted, would-block, broken-pipe, and other failures. Consulting `std.system::errno()`
afterward is also unsuitable because it is ambient state and does not model Win32 errors.

## Defaults Chosen

1. Add `std.os::ErrorKind` and `OsError { kind, native_code }` plus `error_message(error)`.
2. Add low-level `sys.os` records that carry normalized and native error data across the runtime boundary.
3. Use concrete operation-specific result enums because L1 has no generics.
4. Model EOF separately from failure; a zero-length read succeeds without probing EOF.
5. Treat partial reads and writes as successful results carrying an `int` count.
6. Capture host error state inside the runtime operation before any cleanup can overwrite it.
7. Preserve current narrow helpers temporarily where needed, but make all newly exposed handle APIs use direct results.

Representative shapes are `OpenResult::Opened/Failed`, `ReadResult::Read/Eof/Failed`, and `WriteResult::Written/Failed`.
Process, DNS, and socket plans may define their own concrete result enums while reusing `OsError`.

## Implementation Phases

1. Define the normalized categories, native-code representation, and platform mapping tests.
2. Add direct runtime result transport and message rendering for POSIX and Windows.
3. Introduce file-oriented result enums needed by the first handle plan.
4. Migrate later process and network APIs onto the same contract without routing failures through ambient `errno`.
5. Update current reference and design-decision docs when the first implemented consumer ships.

## Non-Goals

- a generic `Result<T, E>` language feature
- exception syntax or stack unwinding
- hiding native error codes
- treating EOF, timeout, or partial transfer as one undifferentiated failure
- removing every legacy nullable helper in the first implementation change

## ADR Impact

- Decision: Standardize direct operation-specific results, normalized OS error categories, native diagnostic codes,
  explicit EOF, and successful partial transfers.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: This contract is shared by filesystem, process, pipe, and networking APIs and replaces ambient
    error-state interpretation at the public boundary.

## Verification Criteria

1. POSIX and Windows mappings cover representative not-found, permission, invalid-input, interrupted, broken-pipe,
   timeout, and unsupported cases.
2. Native codes survive normalization and can produce diagnostic messages.
3. Read results distinguish data, EOF, and failure, including the zero-length case.
4. Write results preserve successful short writes.
5. The new runtime symbols are present in both normal and traced symbol manifests.
