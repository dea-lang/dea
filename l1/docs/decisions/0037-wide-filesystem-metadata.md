# ADR-0037: Wide Filesystem Metadata

- Decision date: 2026-09-07
- Last edited: 2026-09-07
- Status: Accepted

## Context

L1 has native signed 64-bit integers, but its inherited filesystem metadata narrowed host file sizes and modification
seconds through 32-bit `int`. Valid large files and timestamps therefore lost their metadata. No L0 file-handle ABI
constrains this L1 surface.

## Decision

`sys.rt::RtFileInfo` and `std.fs::FileInfo` use `long?` for `size` and `mtime_sec`. The `std.fs` convenience functions
`file_size` and `mtime_sec` also return `long?`. The C runtime ABI uses `dea_opt_long` for these fields and preserves
representable host values without narrowing through `dea_int`.

Normalized modification nanoseconds remain `int?`. String and buffer lengths, indexes, and individual transfer counts
retain their existing `int` bounds. Whole-file reads reject oversized files with `null` until the separate shared I/O
error model is adopted.

## Rationale

Persistent file extents and timestamps are independent of in-memory container lengths. Signed 64-bit values cover common
host file sizes and both pre-epoch and post-2038 timestamps. Normalized nanoseconds fit within `int`.

## Consequences

- Callers requiring the old `int?` metadata signatures must adapt; no compatibility overload is provided.
- Missing or unavailable metadata remains nullable, and host timestamp precision remains platform-dependent.
- Timestamp range also depends on the native API: Windows `_stat64` supports 1970 through 3000, so widening its result
  does not add pre-epoch Windows timestamp support.
- Large-file metadata does not imply that the file can be materialized as one Dea string.
- General clock widths, incremental file I/O, and structured errors remain separate work.

## Related Plans

- [l1/work/plans/features/closed/2026-08-30-wide-filesystem-metadata-noref.md][metadata-plan]

## Current Docs

- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/design-decisions.md][design]
- [l1/docs/project-status.md][status]

[design]: ../reference/design-decisions.md
[metadata-plan]: ../../work/plans/features/closed/2026-08-30-wide-filesystem-metadata-noref.md
[status]: ../project-status.md
[stdlib]: ../reference/standard-library.md
