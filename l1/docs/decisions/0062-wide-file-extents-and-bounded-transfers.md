# ADR-0062: Wide File Extents and Bounded Transfers

- Decision date: 2026-11-10
- Last edited: 2026-11-10
- Status: Accepted

## Context

L1's wide filesystem metadata and opaque byte buffers already distinguish persistent sizes from in-memory lengths.
Incremental and random-access file I/O must preserve that distinction: processing a large file must not require one
equally large allocation or narrow its position through a buffer index.

## Decision

Use signed 64-bit `long` for persistent file extents, positions, positional offsets, and timestamp seconds.
`std.file::FileOffset` aliases `long`, including relative seek offsets. Preserve these widths across `sys.fs` and the
native runtime boundary; validate arithmetic and host representability instead of silently narrowing values. Negative
absolute positions and extents are invalid, while relative seek offsets may be negative when the resulting position is
valid. Nullable metadata retains the existing unavailable-field contract.

Retain `int` for buffer sizes, capacities, indexes, transfer start/count ranges, individual transferred counts, and
normalized timestamp nanoseconds. Exact/all helpers process one bounded buffer range, while applications loop over such
ranges to process files whose extent exceeds the container limit. Whole-file string helpers remain bounded by the string
length contract.

## Rationale

Persistent storage and timestamps have independent ranges from in-memory allocations. Wide positions support sparse and
large files with bounded reusable storage. Keeping container and transfer counts unchanged avoids introducing a second
container-width migration or implying that every file can be materialized in one value.

## Consequences

Large-file consumers must distinguish file offsets from buffer indexes and check any deliberate conversion. The wide
language type does not override native filesystem limits; unsupported values remain observable through the relevant
operation's result. This extends the metadata policy in
[l1/docs/decisions/0037-wide-filesystem-metadata.md][metadata-width] to stateful file operations and retains the buffer
width contract in [l1/docs/decisions/0052-owned-dynamic-byte-buffers.md][buffer-width].

## Related Plans

- [l1/work/initiatives/closed/0005-filesystem-and-stream-io.md][filesystem-io]
- [l1/work/plans/features/closed/2026-08-30-file-handles-and-random-access-noref.md][file-plan]

## Current Docs

- [l1/docs/reference/filesystem.md][filesystem]
- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/design-decisions.md][design]

[buffer-width]: 0052-owned-dynamic-byte-buffers.md
[design]: ../reference/design-decisions.md
[file-plan]: ../../work/plans/features/closed/2026-08-30-file-handles-and-random-access-noref.md
[filesystem]: ../reference/filesystem.md
[filesystem-io]: ../../work/initiatives/closed/0005-filesystem-and-stream-io.md
[metadata-width]: 0037-wide-filesystem-metadata.md
[stdlib]: ../reference/standard-library.md
