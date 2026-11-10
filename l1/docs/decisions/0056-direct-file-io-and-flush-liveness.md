# ADR-0056: Direct File I/O and Flush Liveness

- Decision date: 2026-11-10
- Last edited: 2026-11-10
- Status: Accepted

## Context

Sequential transfers, positional access, append, and explicit synchronization need a common file abstraction. A library
buffer would introduce another cursor and delayed output state whose interaction with these operations must be managed.
L1 already has separate standard-stream APIs whose C stdio flush behavior remains valid.

## Decision

`std.file` performs synchronous direct native I/O without a library-owned read or write buffer. OS caching still
applies. A successful transfer reports bytes accepted by the native operation, not a durability guarantee.

`flush` checks that the file wrapper is live and open, then succeeds without a native synchronization request. A closed
live wrapper returns `InvalidHandle`. Durability requests belong to `sync_data` and `sync_all`, whose minimum guarantees
are defined separately. File close does not introduce an implicit synchronization request.

This decision applies to stateful `std.file` operations. It does not change the buffering or flush contract of `std.io`
standard streams, and it does not introduce generic stream adapters.

## Rationale

Direct operations expose partial progress promptly and avoid hidden buffer state when mixing sequential and positional
access. A distinct synchronization API lets callers request durability explicitly without overloading a flush operation
that has no library buffer to drain.

## Consequences

Callers choose transfer sizes and any application buffering policy. `flush` cannot make file contents durable, and
successful writes or close do not imply that storage hardware has persisted them. Future buffered abstractions must
specify their own ownership and flush behavior instead of silently changing this file contract.

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
