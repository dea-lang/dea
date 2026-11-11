# ADR-0059: Pre-Sized Byte-Buffer File Transfers

- Decision date: 2026-11-10
- Last edited: 2026-11-10
- Status: Accepted

## Context

Incremental file I/O needs mutable binary storage and observable partial progress. The opaque dynamic buffer contract
permits an explicit synchronous unsafe borrow but no escaping storage view. File transfers must preserve that boundary
and distinguish a buffer's initialized logical bytes from its reserved capacity.

## Decision

Transfer synchronously through an opaque `std.bytes::ByteBuffer*` and an `int` start/count range within its logical
size. Callers resize read destinations before transferring. Check the complete logical range before native I/O,
including empty ranges; invalid ranges terminate execution in checked, basic, and unchecked runtime modes. Reserved
capacity alone never authorizes a transfer.

Reads and writes leave the logical buffer size unchanged on success, EOF, timeout, and failure. Results identify the
transferred prefix. Private `std.file` callbacks borrow backing storage through `std.bytes::with_raw_range` only for the
synchronous call and neither return nor retain a pointer or view. The buffer module owns logical-range/progress checks
and has no I/O dependency. Native calls and explicit conversion belong to `std.file`; context and results pass by value
without per-transfer heap allocation. Callback dispatch still occurs for valid empty ranges, preserving native
validation. Public file operations do not grow buffers automatically.

Single-attempt operations preserve successful partial counts, explicit EOF, timeout, and captured failure. Valid
zero-length sequential transfers on a live handle succeed without probing EOF; positional operations still enforce their
offset, seekability, and append restrictions. `read_exact` and `write_all` continue only over successful progress and
report accumulated counts on a terminal outcome. Interrupted operations return without implicit retry. A positive-length
zero-progress write becomes `IoError` rather than an unbounded retry loop.

## Rationale

Explicit sizing separates allocation from I/O and preserves the buffer's initialized-range invariant. Synchronous
borrowing permits efficient native transfers without extending storage lifetime or exposing the buffer layout.
Accumulated progress lets callers handle a partially completed request while retaining its terminal error or EOF result.

## Consequences

Callers keep the buffer and its owner alive for the call, manage resizing independently, and inspect the reported count
before using a read result. Exact/all helpers do not provide rollback, automatic retry after interruption, or one atomic
native transfer. Large files use repeated bounded buffers rather than widening in-memory lengths or allocating storage
for the complete file.

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
