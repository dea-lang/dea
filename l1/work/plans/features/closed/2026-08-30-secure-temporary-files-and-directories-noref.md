# Feature Plan

## Add secure temporary files and directories

- Date: 2026-11-22
- Status: Completed
- Title: Add exclusive temporary-file and temporary-directory creation
- Kind: Feature
- Priority: Medium
- Stdlib Tier: 2
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
  - `l1/compiler/tests/temp_runtime_test.py`
  - `l1/compiler/tests/analysis_trace_test.l0`
- Related:
  - `l1/work/initiatives/0006-process-and-host-services.md`
  - `l1/work/initiatives/closed/0005-filesystem-and-stream-io.md`
  - `l1/work/plans/features/closed/2026-08-30-secure-os-entropy-noref.md`
- Repro:
  `make -C l1 test-compiler TESTS="temp_runtime_test.py file_runtime_test.py entropy_runtime_test.py analysis_trace_test"`

## Summary

L1 tools can create private files and directories under a validated parent and clean them up through a single owner. All
four supported native platforms passed acceptance. The decision is recorded in
[l1/docs/decisions/0065-secure-temporary-files-and-directories.md][adr].

## Stdlib-First Direction and Reference Material

Use temporary-parent inspection in [l1/compiler/support/compiler_support.c][compiler-support] and scratch-directory
creation in [l1/compiler/support/preparation/identity.h][identity-support] as references for platform behavior and
regression cases. The public contract independently defines parent selection, private creation, ownership, and cleanup.
Compiler-specific environment precedence, UID/sticky-bit rules, deterministic workspace names, and the Windows
temporary-file/delete/directory sequence are not sufficient definitions of that contract.

L2 migration to L1 stdlib and removal of superseded private helpers are separate follow-up work, with no dependency on
compiler migration or shared-private-code extraction for this plan's completion.

## Public Surface

- Owned temporary-file and temporary-directory results carrying the created path and cleanup responsibility.
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
6. Support an explicitly selected parent and document default parent discovery, precedence, validation, and error
   behavior. Do not silently inherit the compiler's temporary-parent policy.
7. Create temporary directories with private access under the selected POSIX/Windows contract. Keep directory ownership
   explicit through cleanup; a path string alone does not transfer cleanup responsibility.
8. Cleanup reports the failed operation and partial progress without following substituted links outside the owned tree.
   Define how a primary failure and a later cleanup failure are both preserved.

## Implementation

`std.temp` provides the five public operations. A result owns the pinned parent and original object identity separately
from the borrowed ordinary file. Cleanup consumes the owner once even on failure. The reference records host selection,
trusted alias resolution, permission checks, private creation, publication, error transport and the caller concurrency
boundary in [l1/docs/reference/standard-library.md][stdlib].

The native runtime uses 128-bit OS entropy and at most 32 exclusive attempts. Tests exercise real L1 clients through
source and bundled interfaces, deterministic host faults, release after publication, retained replacements, link leaves
and exact removal counts.

## Verification evidence

Native fixtures cover the public consumer, deterministic failures, ARC and memory traces, and bundled interfaces. The
focused temp, file, entropy and analysis tests passed on macOS Intel. Strict L1 docs, C contract checks and ADR Impact
validation passed with `make -C l1 docs`, `python3 scripts/check_c_docs.py`,
`python3 scripts/check_adr_impact.py --all-active` and `python3 scripts/check_adr_impact.py --staged`.

Unified CI ran `make -C l1 test-ci` on each native host. The normal suite includes `temp_runtime_test.py`. The
`temp_main` child trace reported zero leaked object and string pointers on every host.

| Native host    | Normal tests | Compiler traces | Child traces |
| -------------- | ------------ | --------------- | ------------ |
| Linux x86_64   | 109 passed   | 53 passed       | 11 passed    |
| macOS Intel    | 109 passed   | 53 passed       | 11 passed    |
| macOS ARM64    | 109 passed   | 53 passed       | 11 passed    |
| Windows UCRT64 | 109 passed   | 53 passed       | 11 passed    |

The Windows fixture exercised private creation under a Python-created directory, verified the protected DACL, and
rejected an Everyone delete-child grant on a path through a junction. [CPython's mode 0700 DACL][cpython-mkdir] grants
access to `OWNER RIGHTS`. Parent validation resolves that trustee to the verified owner in the same descriptor.

A separate Wine compatibility probe encountered a filesystem that reports persistent ACLs but discards the protected
DACL. Both file and directory creation returned `Unsupported` and removed the original entries.

## Non-Goals

- predictable names or caller-visible name templates as a security primitive
- check-then-create workflows
- guaranteed cleanup after crash or forced process termination
- shelling out to host utilities
- a general transaction or package-cache abstraction
- L2 compiler migration, bootstrap changes, or removal of compiler-private support

## ADR Impact

- Decision: Require atomic exclusive creation, explicit/default parent selection, owned private temporary objects,
  bounded collision retry, and observable cleanup.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0065-secure-temporary-files-and-directories.md`
  - Rationale: Compiler and linker temporary paths are security and correctness boundaries where name-first creation is
    vulnerable to races and substitution.

## Verification Criteria

1. Collision tests cannot replace or open an existing object.
2. Symlink attacks cannot redirect creation outside the selected temporary root.
3. Returned file handles obey ordinary ownership and close-error rules.
4. Cleanup reports partial failure and does not traverse unexpected links.
5. Created paths and permissions follow the documented POSIX and Windows contracts.
6. Explicit and default parent selection have deterministic precedence and observable inspection failures. Private
   directory access, ownership, primary failure, and cleanup failure follow the selected host contract.

[adr]: ../../../../docs/decisions/0065-secure-temporary-files-and-directories.md
[compiler-support]: ../../../../compiler/support/compiler_support.c
[cpython-mkdir]: https://github.com/python/cpython/blob/v3.14.10/Modules/posixmodule.c#L5387-L5396
[identity-support]: ../../../../compiler/support/preparation/identity.h
[stdlib]: ../../../../docs/reference/standard-library.md#stdtemp
