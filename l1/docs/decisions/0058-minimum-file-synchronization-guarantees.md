# ADR-0058: Minimum File Synchronization Guarantees

- Decision date: 2026-11-10
- Last edited: 2026-11-10
- Status: Accepted

## Context

File consumers need to distinguish data synchronization from synchronization that also includes associated metadata.
Supported hosts do not all expose separate operations for these requests, and successful native synchronization has
filesystem and storage limitations that a portable library cannot remove.

## Decision

Define `std.file::sync_data` as a request for data synchronization at minimum. Define `sync_all` as a request for data
and associated metadata synchronization. A host implementation may satisfy either request with a stronger operation; it
must return `Unsupported` when the required minimum is unavailable. Other host failures retain their captured
`std.os::OsError`. Both operations reject a closed live wrapper with `InvalidHandle`.

The current macOS implementation uses `fsync` for both requests. Other supported POSIX hosts use `fdatasync` for data
and `fsync` for all. Windows uses `FlushFileBuffers` for both and requires writable access. These are host mappings of
the minimum-guarantee contract, not a requirement that the two requests always have different cost or behavior.

Successful synchronization retains the host and filesystem guarantees. It does not promise parent-directory
synchronization, hardware compliance with cache-flush requests, or survival of every power failure. `flush` remains a
separate live-handle check and requests no durability.

## Rationale

Minimum guarantees permit portable callers to state the required outcome while allowing a stronger host fallback.
Explicit unsupported and failure results prevent an unavailable synchronization request from appearing successful.
Keeping host limitations visible avoids giving native completion a stronger durability meaning than it supports.

## Consequences

Callers inspect synchronization results separately from transfer and close results. A data-only request can have the
same cost as full synchronization. Applications needing durable directory-entry changes or stronger storage guarantees
must establish those requirements separately; this API introduces neither automatic synchronization on close nor a
transactional persistence protocol.

## Related Plans

- [l1/work/plans/features/closed/2026-08-30-file-handles-and-random-access-noref.md][file-plan]
- [l1/work/initiatives/closed/0005-filesystem-and-stream-io.md][filesystem-io]

## Current Docs

- [l1/docs/reference/filesystem.md][filesystem]
- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/design-decisions.md][design]

[design]: ../reference/design-decisions.md
[file-plan]: ../../work/plans/features/closed/2026-08-30-file-handles-and-random-access-noref.md
[filesystem]: ../reference/filesystem.md
[filesystem-io]: ../../work/initiatives/closed/0005-filesystem-and-stream-io.md
[stdlib]: ../reference/standard-library.md
