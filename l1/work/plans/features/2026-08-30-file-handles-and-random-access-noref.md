# Feature Plan

## Add file handles and complete file I/O

- Date: 2026-08-30
- Status: Draft
- Title: Add opaque file handles, incremental transfers, random access, and synchronization
- Kind: Feature
- Severity: High
- Priority: 1
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Subsystem: Stdlib / runtime / filesystem I/O
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/file.l1`
  - `l1/compiler/shared/l1/stdlib/std/os.l1`
  - `l1/compiler/shared/l1/stdlib/std/bytes.l1`
  - `l1/compiler/shared/l1/stdlib/sys/fs.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l1/docs/reference/standard-library.md`
  - `l1/docs/reference/design-decisions.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/file_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_trace_test.l0`
- Related:
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/work/plans/features/2026-08-30-os-error-and-io-results-noref.md`
  - `l1/work/plans/features/2026-08-30-dynamic-byte-buffers-noref.md`
- Repro: `make -C l1 test-stage1 TESTS="file_runtime_test l0c_lib_test analysis_trace_test"`

## Summary

Add the first stateful file API to L1. `std.file` owns opaque file handles and exposes incremental sequential I/O,
64-bit positioning, positional I/O, append, truncate, flush, and durability requests through structured results.

## Public Surface

- Types: `File`, `OpenOptions`, `AccessMode`, `CreateMode`, `SeekOrigin`, and `FileOffset` as a `long` alias.
- Lifetime: `open`, `close`.
- Transfers: `read_some`, `read_exact`, `write_some`, `write_all`.
- Positioning: `seek`, `position`, `read_at`, `write_at`.
- Extent: `size`, `truncate`.
- Completion: `flush`, `sync_data`, `sync_all`.

Buffer starts, lengths, and per-call counts are `int`; file sizes, positions, and positional offsets are `long`.

## Required Semantics

1. `read_at` and `write_at` do not mutate the shared cursor.
2. Append requests real host append behavior rather than `seek(end)` followed by write.
3. Non-seekable handles return `NotSeekable`.
4. Child-process inheritance is disabled by default.
5. Close failures are observable and repeated or post-close operations have defined results.
6. Partial transfers remain successful; exact/all helpers loop or return the terminal failure with documented progress.
7. `flush` concerns runtime/language buffering, while `sync_data` and `sync_all` request distinct host durability
   levels.
8. No public operation exposes the native handle representation.

## Implementation Phases

1. Settle ownership, explicit close, cleanup integration, and runtime handle representation.
2. Implement open/close and sequential partial/exact/all transfers.
3. Add `long` seek, position, size, and truncate.
4. Add positional reads/writes and true append tests.
5. Add flush/data-sync/full-sync behavior and cross-platform capability reporting.
6. Add trace, failure-injection, large sparse-file, and stable-doc coverage.

## Non-Goals

- memory mapping, locking, or file watching
- asynchronous or evented I/O
- changing container lengths to `long`
- exposing `FILE*`, file descriptors, or Win32 handles
- silently closing an independently owned endpoint through an adapter

## ADR Impact

- Decision: Finalize file-handle ownership, explicit close, cleanup integration, and post-close behavior.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: The API must make close failures visible without permitting use-after-close or double-close ownership
    ambiguity.
- Decision: Define true append, cursor-independent positional I/O, and distinct flush/data-sync/full-sync operations.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: These distinctions materially affect concurrent append behavior, shared cursors, and durability
    guarantees across supported hosts.

## Verification Criteria

1. Large sparse files can be traversed and modified through `long` offsets with `int`-sized buffers.
2. EOF, short transfer, interrupted operation, invalid handle, and non-seekable results remain distinct.
3. Positional I/O leaves the shared cursor unchanged.
4. Append behavior is atomic to the degree promised by the selected host contract.
5. Close and synchronization failures are observable in deterministic tests.
6. Normal and traced runtime symbol manifests remain complete.
