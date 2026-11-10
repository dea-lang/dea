# ADR-0060: Opened-Object File Metadata

- Decision date: 2026-11-10
- Last edited: 2026-11-10
- Status: Accepted

## Context

A pathname can be renamed or replaced after a file is opened. Repeating a path lookup would then describe a different
object or fail even though the original file remains open. Consumers need metadata for the object used by their file
operations without introducing a second metadata representation.

## Decision

`std.file::metadata` queries the opened native object directly and never resolves its original path again. Renaming or
replacing that path cannot redirect the query to another object. Return the shared `std.fs::MetadataResult`, including
the object type, nullable signed `long` byte size and modification seconds, and nullable normalized `int` nanoseconds.
Preserve unavailable or unrepresentable fields as absent, separately from a captured query failure.

`size` derives the opened object's extent from this metadata contract without moving the sequential cursor. It returns
`Unsupported` when no usable size is available. Metadata queries on a closed live wrapper return `InvalidHandle`.

Native sharing and filesystem rules still govern whether rename or replacement can occur. The Windows implementation
permits native read/write/delete sharing, without promising that every host operation will be allowed.

## Rationale

The native handle binds a query to the resource that was actually opened. Reusing the filesystem metadata record keeps
field widths, absence, and error interpretation consistent between path and file APIs while preserving their different
object-selection contracts.

## Consequences

Handle metadata and path metadata may correctly describe different objects after path replacement. A stable object
association does not freeze its contents or metadata; other operations can still change the same object. The API does
not promise a historical snapshot, extra locking, or success where the native host rejects the query.

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
