# Feature Plan

## Add filesystem mutations and directory traversal

- Date: 2026-08-30
- Status: Draft
- Title: Add path-level filesystem mutations and streaming directory traversal
- Kind: Feature
- Severity: High
- Priority: 1
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Subsystem: Stdlib / runtime / filesystem
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/fs.l1`
  - `l1/compiler/shared/l1/stdlib/std/dir.l1`
  - `l1/compiler/shared/l1/stdlib/std/os.l1`
  - `l1/compiler/shared/l1/stdlib/sys/fs.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/filesystem_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/directory_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_support_test.py`
- Related:
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/work/plans/features/2026-08-30-wide-filesystem-metadata-noref.md`
  - `l1/work/plans/features/2026-08-30-os-error-and-io-results-noref.md`
- Repro: `make -C l1 test-stage1 TESTS="filesystem_runtime_test directory_runtime_test"`

## Summary

Complete the path-level `std.fs` surface needed by compilers and build tools, and add `std.dir` for incremental
directory iteration. Directory entry order remains host-defined unless a caller chooses an explicit sorted helper.

## Public Surface

- Metadata: `metadata`, `symlink_metadata`.
- Mutations: `create_dir`, `create_dir_all`, `remove_file`, `remove_dir`, `remove_dir_all`, `rename`, `replace`, and
  `copy_file`.
- Working directory: `current_dir`, `set_current_dir`.
- Directory types: `Dir`, `DirEntry`, and `FileType`.
- Directory operations: `open`, `next`, `close`, `read_all`, and `read_all_sorted`.

`next` distinguishes one entry, clean end, and failure. `DirEntry` carries the entry name and a cheap file-type hint; it
does not perform an implicit full metadata query for every entry.

## Path Contract

1. Reject embedded NUL before entering the host API.
2. Convert UTF-8 to UTF-16 and use wide APIs on Windows.
3. Pass string bytes as filesystem bytes on POSIX.
4. State symbolic-link following for every operation.
5. Never silently truncate paths, file sizes, or timestamps.
6. Make recursive deletion's link traversal and failure behavior explicit.

## Implementation Phases

1. Establish `sys.fs` path conversion and shared error handling.
2. Add metadata variants and single-object mutations.
3. Add recursive create/remove helpers with deterministic failure rules.
4. Add streaming directory handles and entry typing.
5. Add explicit materialized and sorted helpers for deterministic tooling.
6. Add cross-platform fixtures for links, Unicode paths, error cases, and cleanup.

## Non-Goals

- implicit sorting in `next`
- implicit `stat` for every directory entry
- permissions, ownership, ACL, or extended-attribute APIs in v1
- file watching, locking, or memory mapping
- following directory symlinks during recursive removal without an explicit contract

## ADR Impact

- Decision: Define the cross-platform path-encoding, embedded-NUL, symbolic-link, recursive-mutation, and directory-
  iteration contract.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Path representation and link traversal affect correctness and safety on every supported host, while
    streaming iteration and explicit sorting are durable API behavior.

## Verification Criteria

1. Iteration distinguishes entry, clean end, and failure and closes handles on every path.
2. Sorted helpers are deterministic without changing host-order iteration.
3. Unicode Windows paths and byte-oriented POSIX paths follow the documented contract.
4. Recursive create/remove tests cover partial failure and symbolic links without escaping the requested tree.
5. Rename, replace, and copy tests document same-filesystem and cross-filesystem behavior.
