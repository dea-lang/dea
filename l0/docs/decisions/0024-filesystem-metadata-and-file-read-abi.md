# ADR-0024: Filesystem Metadata and File-Read ABI

- Decision date: 2026-03-09
- Last edited: 2026-07-27
- Status: Accepted

## Context

Compiler drivers and standard-library code need file existence, kind, size, and modification-time information across
supported hosts. They also encounter ordinary filesystem uncertainty: an empty file, a short read, end-of-file, a
non-regular path, an unavailable metadata field, or a file too large for L0's current integer model.

Turning these environmental outcomes into runtime panics would make routine compiler input handling indistinguishable
from an internal invariant failure. Several independent metadata calls would also permit callers to observe an
incoherent view of one path.

## Decision

The filesystem runtime boundary is:

1. `rt_file_info(path)` returns one stable `RtFileInfo` record containing `exists`, `is_file`, `is_dir`, optional
   `size`, and optional modification seconds and nanoseconds.
2. Absence or host-unavailable metadata is represented in the record rather than by a runtime panic. Callers decide
   whether their operation requires a regular file or a particular field.
3. An empty regular file is a valid readable input.
4. End-of-file and short reads remain ordinary outcomes handled by file-reading logic. A full-file helper retries or
   reports recoverable failure according to its public contract rather than asserting that every transfer is complete.
5. Non-regular paths, oversized files, metadata races, and host read failures surface as recoverable read failure, not
   an internal runtime abort.

## Rationale

- One metadata snapshot provides a compact, portable boundary and keeps platform-specific `stat` details inside the C
  runtime.
- Optional fields distinguish an existing path from metadata the host cannot represent through the current ABI.
- Empty files, EOF, and partial transfers are expected filesystem behavior and belong in caller-visible control flow.
- Recoverable failure lets compiler and library code produce contextual diagnostics rather than terminating in a
  low-level helper.

## Consequences

- Callers inspect `exists` and kind fields before relying on optional size or timestamp data.
- Runtime ports normalize host metadata into `RtFileInfo` without exposing platform-specific structs.
- Full-file readers must handle zero length, partial progress, and EOF explicitly.
- L0's current `int` width can make an otherwise valid host file unrepresentable; that case remains a recoverable
  failure until the ABI evolves.
- Unexpected runtime invariants may still abort, but ordinary filesystem conditions may not be reclassified as internal
  failures.

## Related Plans

- [l0/work/plans/features/closed/2026-03-09-stdlib-runtime-fs-path-raw-io-bootstrap-noref.md](../../work/plans/features/closed/2026-03-09-stdlib-runtime-fs-path-raw-io-bootstrap-noref.md):
  introduced `RtFileInfo` and recoverable filesystem APIs
- [l0/work/plans/bug-fixes/closed/2026-03-13-linux-c99-compatibility-noref.md](../../work/plans/bug-fixes/closed/2026-03-13-linux-c99-compatibility-noref.md):
  made non-regular and oversized file reads recoverable on strict Linux hosts
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the filesystem metadata and read-failure boundary into this ADR

## Current Docs

- [l0/docs/reference/standard-library.md](../reference/standard-library.md): current `std.fs`, `RtFileInfo`, and runtime
  file API
