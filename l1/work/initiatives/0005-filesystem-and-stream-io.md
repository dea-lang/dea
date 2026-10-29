# L1 Initiative 0005 - Filesystem and Stream I/O

- Version: 2026-10-29
- Status: Active
- Kind: Initiative
- Open plans:
  - `l1/work/plans/features/2026-08-30-dynamic-byte-buffers-noref.md`
  - `l1/work/plans/features/2026-08-30-file-handles-and-random-access-noref.md`
- Closed plans:
  - `l1/work/plans/features/closed/2026-08-30-filesystem-mutations-and-directory-traversal-noref.md`
  - `l1/work/plans/features/closed/2026-08-30-os-error-and-io-results-noref.md`
  - `l1/work/plans/features/closed/2026-08-30-wide-filesystem-metadata-noref.md`

## Summary

This initiative establishes the portable I/O foundation needed by compiler tooling and ordinary L1 programs. It adds a
shared OS error model, corrects inherited 32-bit filesystem metadata, introduces mutable dynamic byte buffers, adds
stateful file handles and path operations, and provides streaming directory traversal. Generic streams and file-watch
design are now L2-owned and do not gate this initiative.

The target is portable systems capability with typed Dea APIs and platform-specific behavior contained behind the
runtime boundary. It is not a literal mirror of C99 or of any one host API. This initiative executes under the
[L1 roadmap].

## Stdlib-first delivery and compiler follow-up

Complete public L1 contracts through `std.*`, `sys.*`, and the runtime. Existing compiler-private C helpers and their
tests are reference material for host behavior and regression cases, not a required shared implementation or the public
ABI. Each affected plan inventories useful references and adapts the behavior to its own error, encoding, and ownership
contract.

Once the APIs meet compiler needs, separate follow-up work can migrate L2's L1 implementation to L1 stdlib and remove
superseded private helpers. Canonical L1's L0 bootstrap boundary remains unchanged. Compiler migration, removal, and
shared-private-code extraction are not completion requirements for this initiative or its stdlib plans.

## Current baseline

- `std.fs` exposes structured metadata, native identity, path resolution, mutations, and legacy whole-file helpers.
- `std.dir` provides streaming owned cursors, result-level cleanup, and explicit materialization with composable
  comparator/default sorting through `sys.fs`.
- `std.io` exposes standard-stream byte transfers whose buffer indexes and counts are `int`. Additive result helpers use
  shared `std.os` errors and distinguish EOF, timeout, failure, and successful partial transfer.
- L1 has no general file-handle API, so there is no legacy 32-bit offset contract to preserve.
- `std.fs::FileInfo` and `sys.rt::RtFileInfo` use `long?` for file size and modification seconds; normalized nanoseconds
  remain `int?`.
- Whole-file helpers are necessarily bounded by the `int` length of a Dea string.
- `ByteArray` is fixed-sized, and general mutable growth is exposed only through lower-level `VectorBase` operations.
- New filesystem APIs return captured `std.os` errors directly; legacy convenience helpers retain nullable results.

## Decisions and invariants

01. `std.fs` remains the path-level module; stateful file handles live in `std.file`, directory iteration in `std.dir`,
    and dynamic binary buffers in `std.bytes`.
02. Low-level filesystem services move toward `sys.fs`; normalized native errors live in `sys.os` and are wrapped by
    `std.os`.
03. Persistent file extents, positions, positional offsets, and timestamp seconds use `long`.
04. In-memory lengths, buffer indexes, individual transfer request sizes, and individual transfer counts remain `int`.
05. Whole-file string helpers remain bounded convenience operations. Large files are processed incrementally.
06. EOF is not an error. Zero-length reads do not probe for EOF, and partial transfers are successful results.
07. Runtime calls return an error with the failed operation. `std.system::errno()` is not the primary error channel.
08. File handles are opaque and module-owned. Public APIs do not expose `FILE*`, POSIX descriptors, or Win32 handles.
09. Append uses host append semantics, positional I/O does not mutate the shared cursor, and close failures are visible.
10. Directory traversal is incremental. Sorting and full materialization are explicit helpers.
11. Path-taking runtime operations reject embedded NUL, use wide Win32 APIs after UTF-8 conversion on Windows, preserve
    filesystem bytes on POSIX, and document symbolic-link following per operation.
12. Dynamic buffers expose checked operations, borrowed inputs, copying conversions, and explicit cleanup. Returning
    buffer views is outside L1.

## Phases and stdlib tiers

### Phase 0 - Error and width foundation (Stdlib Tier 1)

- Define `ErrorKind`, `OsError`, direct native-code preservation, and operation-specific result enums.
- Widen file size and modification seconds to `long?` without changing whole-file helper bounds.
- Wide metadata and the direct-error foundation are complete, with standard streams as the first error consumer. Opening
  results and file-handle ownership remain in Phase 2.

Spawned plans: [OS errors and I/O results] and [wide filesystem metadata].

### Phase 1 - Dynamic binary buffers (Stdlib Tier 1)

- Add a public growable byte buffer with reserve, resize, indexed access, copying append from borrowed slices, and
  explicit string conversion.

Spawned plan: [dynamic byte buffers].

### Phase 2 - File handles and complete file I/O (Stdlib Tier 1)

- Add open/close, sequential reads and writes, seek and position, positional I/O, append, truncate, flush, and durable
  synchronization.
- Query metadata through the opened file rather than looking up its original path again.
- Define closed-handle behavior, close-error reporting, and non-inheritance by child processes.

Spawned plan: [file handles and random access].

### Phase 3 - Path mutations and directory traversal (Stdlib Tier 1, complete)

- Add metadata variants, directory creation/removal, rename/replace/copy, current-directory operations, and streaming
  directory iteration.
- Add `same_file`, absolute-path conversion, and existing-path canonicalization with distinct identity/resolution
  contracts; settle replacement policies and any atomic no-replace capability or deferral.

Completed public `std.fs` / `std.dir` contracts preserve native identity separately from spelling, wide Windows paths,
POSIX bytes, non-following recursive removal, and result-level cursor/collection cleanup. Sorting composes with
materialization through in-place iterative heapsort with custom or default name comparison. Rename and replacement have
explicit native policies; atomic no-replace rename is deferred rather than emulated by check-then-rename. Compiler
adoption is separate.

Closed plan: [filesystem mutations and directory traversal].

## Dependencies

- Initiative 0006 consumes the error, buffer, file, and handle-inheritance contracts for processes, pipes, and temporary
  objects.
- The L1 borrowed-slice correction precedes new buffer delivery.

## Non-goals

- literal C99 API parity
- unbounded whole-file strings or 64-bit in-memory container indexes
- exposing native handles through safe `std.*` APIs
- memory mapping or file locking in this initiative
- a portable event loop, local IPC, or asynchronous I/O
- changing L0 APIs or treating the L0 Stage 1 implementation language as an L1 type-surface constraint

## ADR Impact

- Decision: Deliver general I/O capabilities through L1 stdlib before separately migrating compiler consumers and
  removing superseded private helpers.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Public error, encoding, identity, and ownership contracts must govern the library implementation; private
    compiler ABIs are reference material, and compiler adoption must not gate stdlib completion.
- Decision: Use `long` for persistent filesystem extents, positions, offsets, and timestamp seconds while retaining
  `int` for in-memory lengths, indexes, and individual transfer counts.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: L1 has native 64-bit integers, file extents are independent of container length, and no prior L0
    file-handle ABI requires 32-bit compatibility.
- Decision: Use direct operation-specific results with normalized OS errors, explicit EOF, and successful partial
  transfers as the common I/O contract.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0045-direct-os-errors-and-io-results.md`
  - Rationale: Files, processes, and sockets need portable branching without discarding native diagnostic codes or
    consulting ambient `errno` after the operation.
- Decision: Finalize file-handle ownership, close behavior, append atomicity, buffering, and synchronization semantics.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: The initiative fixes the required distinctions, while the file-handle plan must settle exact lifetime and
    durability behavior against the supported host implementations.

## References

[dynamic byte buffers]: ../plans/features/2026-08-30-dynamic-byte-buffers-noref.md
[file handles and random access]: ../plans/features/2026-08-30-file-handles-and-random-access-noref.md
[filesystem mutations and directory traversal]: ../plans/features/closed/2026-08-30-filesystem-mutations-and-directory-traversal-noref.md
[l1 roadmap]: ../../docs/roadmap.md
[os errors and i/o results]: ../plans/features/closed/2026-08-30-os-error-and-io-results-noref.md
[wide filesystem metadata]: ../plans/features/closed/2026-08-30-wide-filesystem-metadata-noref.md
