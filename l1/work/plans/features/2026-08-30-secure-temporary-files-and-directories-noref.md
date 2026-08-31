# Feature Plan

## Add secure temporary files and directories

- Date: 2026-08-30
- Status: Draft
- Title: Add exclusive temporary-file and temporary-directory creation
- Kind: Feature
- Severity: Medium
- Priority: 2
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0006-process-and-host-services.md`
- Subsystem: Stdlib / runtime / filesystem / tooling
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/temp.l1`
  - `l1/compiler/shared/l1/stdlib/std/file.l1`
  - `l1/compiler/shared/l1/stdlib/std/fs.l1`
  - `l1/compiler/shared/l1/stdlib/std/entropy.l1`
  - `l1/compiler/shared/l1/stdlib/sys/fs.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/temp_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_trace_test.l0`
- Related:
  - `l1/work/initiatives/0006-process-and-host-services.md`
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/work/plans/features/2026-08-30-secure-os-entropy-noref.md`
- Repro: `make -C l1 test-stage1 TESTS="temp_runtime_test analysis_trace_test"`

## Summary

Add race-free temporary-file and temporary-directory creation for compiler and linker transactions. Creation is
exclusive, returns ownership of the created object, and provides explicit cleanup helpers.

## Public Surface

- `system_temp_dir`
- `create_file`
- `create_dir`
- `close_and_remove`
- `remove_tree`

Returned temporary files use the ordinary `std.file::File` contract. Names are never created through a separate
existence check followed by a non-exclusive open.

## Defaults Chosen

1. Prefer host primitives that atomically choose and create an exclusive object.
2. When a host requires candidate generation, combine secure entropy with create-exclusive semantics and bounded retry.
3. Create files with private permissions subject to the documented host contract.
4. Keep automatic cleanup explicit; process termination is not promised to run destructors.
5. Make cleanup failure observable.

## Implementation Phases

1. Define temporary root discovery and error behavior.
2. Implement exclusive file and directory creation on supported hosts.
3. Add explicit close/remove and recursive cleanup helpers.
4. Add collision injection, permission, symlink, trace, and cleanup-failure tests.

## Non-Goals

- predictable names or caller-visible name templates as a security primitive
- check-then-create workflows
- guaranteed cleanup after crash or forced process termination
- shelling out to host utilities
- a general transaction or package-cache abstraction

## ADR Impact

- Decision: Require atomic exclusive creation, private defaults, bounded collision retry, and observable cleanup for
  temporary files and directories.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Compiler and linker temporary paths are security and correctness boundaries where name-first creation is
    vulnerable to races and substitution.

## Verification Criteria

1. Collision tests cannot replace or open an existing object.
2. Symlink attacks cannot redirect creation outside the selected temporary root.
3. Returned file handles obey ordinary ownership and close-error rules.
4. Cleanup reports partial failure and does not traverse unexpected links.
5. Created paths and permissions follow the documented POSIX and Windows contracts.
