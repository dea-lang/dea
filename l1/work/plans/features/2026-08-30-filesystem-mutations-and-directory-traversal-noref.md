# Feature Plan

## Add filesystem mutations and directory traversal

- Date: 2026-08-30
- Last reviewed: 2026-10-24
- Status: Draft
- Title: Add path-level filesystem mutations and streaming directory traversal
- Kind: Feature
- Priority: High
- Stdlib Tier: 1
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
  - `l1/compiler/tests/filesystem_runtime_test.l0`
  - `l1/compiler/tests/directory_runtime_test.l0`
  - `l1/compiler/tests/compiler_filesystem_support_test.py`
- Related:
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/work/plans/features/closed/2026-08-30-wide-filesystem-metadata-noref.md`
  - `l1/work/plans/features/closed/2026-08-30-os-error-and-io-results-noref.md`
- Repro: `make -C l1 test-compiler TESTS="filesystem_runtime_test directory_runtime_test"`

## Summary

Complete the path-level `std.fs` surface needed by compilers and build tools, and add `std.dir` for incremental
directory iteration. Directory entry order remains host-defined unless a caller chooses an explicit sorted helper.

## Stdlib-First Direction and Reference Material

Define public `std.fs` / `std.dir` contracts over `sys.fs` and the runtime. Use
[l1/compiler/support/compiler_support.c][compiler-support] and
[l1/compiler/support/preparation/platform.h][platform-support] as references for path classification, identity,
canonicalization, directory creation/removal, and enumeration. Inventory their relevant regression cases before
implementation; their private ABIs, coarse errors, narrow Windows APIs, and compiler-specific assumptions do not define
the public contract. The eager sorted JSON result of `pc_list` is reference material for the host iteration, not the
representation of `Dir`.

L2 adoption of L1 stdlib and removal of superseded compiler-private helpers belong to separate follow-up work. Neither
compiler migration nor extraction of shared private C code is required to complete this plan.

## Public Surface

- Metadata and identity: `metadata`, `symlink_metadata`, and `same_file`.
- Path resolution: `absolute` and `canonicalize`.
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
7. `same_file` compares the followed native identities of two existing objects, not lexical spellings. Missing or
   inaccessible inputs return structured failure rather than being classified as distinct objects.
8. `absolute` anchors a path to the process's current directory at call time without resolving filesystem aliases.
   `canonicalize` resolves an existing path through aliases and fails for missing inputs. Specify Windows
   drive-relative, rooted, and UNC behavior independently of POSIX behavior; neither operation proves containment
   against later changes.
9. Define destination-exists, alias, and cross-filesystem behavior separately for `rename` and `replace`. Decide whether
   a separate atomic no-replace operation is supportable and document any capability limit or deferral. The private
   `l1c_fs_rename_absent` POSIX check-then-rename sequence relies on a single writer and does not establish that public
   atomic guarantee.

## Implementation Phases

1. Establish `sys.fs` path conversion and shared error handling.
2. Add metadata variants, identity and path-resolution operations, and single-object mutations with explicit replacement
   policies.
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
- L2 compiler migration, bootstrap changes, or removal of compiler-private support

## ADR Impact

- Decision: Define the cross-platform path-encoding, embedded-NUL, symbolic-link, recursive-mutation, and directory-
  iteration contract.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Path representation and link traversal affect correctness and safety on every supported host, while
    streaming iteration and explicit sorting are durable API behavior.
- Decision: Compare existing filesystem objects by followed native identity independently of path spelling.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Lexical equality cannot establish object identity, and missing or inaccessible objects require explicit
    failure rather than a false identity result.
- Decision: Distinguish call-time absolute-path anchoring from existing-path canonicalization through aliases.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The operations answer different questions and need distinct existence, alias, and host-root contracts.
- Decision: Select overwrite/replacement policies and an atomic no-replace capability or explicit deferral.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: General callers cannot inherit the private compiler's single-writer assumption; supported atomicity and
    cross-filesystem behavior must be settled before the public mutation contract is final.

## Verification Criteria

1. Iteration distinguishes entry, clean end, and failure and closes handles on every path.
2. Sorted helpers are deterministic without changing host-order iteration.
3. Unicode Windows paths and byte-oriented POSIX paths follow the documented contract.
4. Recursive create/remove tests cover partial failure and symbolic links without escaping the requested tree.
5. Rename, replace, and copy tests document same-filesystem and cross-filesystem behavior.
6. Identity tests distinguish aliases of the same existing object from genuinely different objects and report missing or
   inaccessible inputs. Resolution tests distinguish absolute spelling from canonical spelling, including POSIX literal
   backslashes and Windows drive, UNC, mixed-separator, space, and Unicode cases.
7. Replacement tests cover existing destinations, links, and failure without making an unsupported atomic no-replace
   claim. Exercise competing destination creation if an atomic no-replace API is selected.

[compiler-support]: ../../../compiler/support/compiler_support.c
[platform-support]: ../../../compiler/support/preparation/platform.h
