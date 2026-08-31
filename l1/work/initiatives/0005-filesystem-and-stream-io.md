# L1 Initiative 0005 - Filesystem and Stream I/O

- Version: 2026-08-30
- Status: Active
- Kind: Initiative
- Open plans:
  - `l1/work/plans/features/2026-08-30-os-error-and-io-results-noref.md`
  - `l1/work/plans/features/2026-08-30-wide-filesystem-metadata-noref.md`
  - `l1/work/plans/features/2026-08-30-dynamic-byte-buffers-noref.md`
  - `l1/work/plans/features/2026-08-30-file-handles-and-random-access-noref.md`
  - `l1/work/plans/features/2026-08-30-filesystem-mutations-and-directory-traversal-noref.md`
  - `l1/work/plans/features/2026-08-30-streams-and-buffering-noref.md`
  - `l1/work/plans/features/2026-08-30-file-watch-api-design-noref.md`
- Closed plans: (none)

## Summary

This initiative establishes the portable I/O foundation needed by compiler tooling and ordinary L1 programs. It adds a
shared OS error model, corrects inherited 32-bit filesystem metadata, introduces mutable dynamic byte buffers, adds
stateful file handles and path operations, provides streaming directory traversal, and builds explicit stream adapters
over the concrete endpoint contracts. A later Priority 4 design tranche defines whether file watching can have a useful
portable surface.

The target is portable systems capability with typed Dea APIs and platform-specific behavior contained behind the
runtime boundary. It is not a literal mirror of C99 or of any one host API. This initiative executes under the
[L1 roadmap].

## Current baseline

- `std.fs` exposes metadata, whole-file string reads and writes, and file deletion.
- `std.io` exposes standard-stream byte transfers whose buffer indexes and counts are `int`.
- L1 has no general file-handle API, so there is no legacy 32-bit offset contract to preserve.
- `std.fs::FileInfo` and `sys.rt::RtFileInfo` still use `int?` for file size and modification seconds.
- Whole-file helpers are necessarily bounded by the `int` length of a Dea string.
- `ByteArray` is fixed-sized, and general mutable growth is exposed only through lower-level `VectorBase` operations.
- Filesystem failures currently collapse into `null`, `false`, or `-1`, losing operation-specific error information.

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
12. Stream adapters have explicit endpoint ownership; freely escaping borrowed views are not part of the v1 surface.

## Phases and priorities

### Phase 0 - Error and width foundation (Priority 1)

- Define `ErrorKind`, `OsError`, direct native-code preservation, and operation-specific result enums.
- Widen file size and modification seconds to `long?` without changing whole-file helper bounds.

Spawned plans: [OS errors and I/O results] and [wide filesystem metadata].

### Phase 1 - Dynamic binary buffers (Priority 1)

- Add a public growable byte buffer with reserve, resize, indexed access, append, slicing, and explicit string
  conversion.

Spawned plan: [dynamic byte buffers].

### Phase 2 - File handles and complete file I/O (Priority 1)

- Add open/close, sequential reads and writes, seek and position, positional I/O, append, truncate, flush, and durable
  synchronization.
- Define closed-handle behavior, close-error reporting, and non-inheritance by child processes.

Spawned plan: [file handles and random access].

### Phase 3 - Path mutations and directory traversal (Priority 1)

- Add metadata variants, directory creation/removal, rename/replace/copy, current-directory operations, and streaming
  directory iteration.

Spawned plan: [filesystem mutations and directory traversal].

### Phase 4 - Streams and buffering (Priority 2)

- Add reader, writer, seeker, and buffered adapters only after the concrete file contracts are stable.

Spawned plan: [streams and buffering].

### Phase 5 - File-watch contract discovery (Priority 4)

- Select a portable event, overflow, rename, lifetime, and path contract before any implementation plan is opened.

Spawned plan: [file-watch API design].

## Dependencies

- Initiative 0006 consumes the error, file, stream, and handle-inheritance contracts for processes, pipes, and temporary
  objects.
- Initiative 0007 consumes the error, byte-buffer, stream, and timeout contracts for networking.
- Initiative 0008 consumes byte buffers and streams for incremental format processing.
- File watching does not block Phases 0 through 4.

## Non-goals

- literal C99 API parity
- unbounded whole-file strings or 64-bit in-memory container indexes
- exposing native handles through safe `std.*` APIs
- memory mapping or file locking in this initiative
- a portable event loop, local IPC, or asynchronous I/O
- changing L0 APIs or treating the L0 Stage 1 implementation language as an L1 type-surface constraint

## ADR Impact

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
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Files, processes, and sockets need portable branching without discarding native diagnostic codes or
    consulting ambient `errno` after the operation.
- Decision: Finalize file-handle ownership, close behavior, append atomicity, buffering, and synchronization semantics.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: The initiative fixes the required distinctions, while the file-handle plan must settle exact lifetime and
    durability behavior against the supported host implementations.
- Decision: Finalize stream-adapter ownership and endpoint-lifetime semantics.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: Function-pointer dispatch is available, but L1 has no general lifetime system that would make an escaping
    borrowed endpoint safe.
- Decision: Define a portable file-watch event and overflow model.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: Host watcher APIs disagree on event coalescing, rename pairing, recursive watches, overflow, and path
    identity; the Priority 4 design plan must determine whether a useful common contract exists.

## References

[dynamic byte buffers]: ../plans/features/2026-08-30-dynamic-byte-buffers-noref.md
[file handles and random access]: ../plans/features/2026-08-30-file-handles-and-random-access-noref.md
[file-watch api design]: ../plans/features/2026-08-30-file-watch-api-design-noref.md
[filesystem mutations and directory traversal]: ../plans/features/2026-08-30-filesystem-mutations-and-directory-traversal-noref.md
[l1 roadmap]: ../../docs/roadmap.md
[os errors and i/o results]: ../plans/features/2026-08-30-os-error-and-io-results-noref.md
[streams and buffering]: ../plans/features/2026-08-30-streams-and-buffering-noref.md
[wide filesystem metadata]: ../plans/features/2026-08-30-wide-filesystem-metadata-noref.md
