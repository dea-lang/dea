# ADR-0057: Native Append and Cursor-Independent File I/O

- Decision date: 2026-11-10
- Last edited: 2026-11-10
- Status: Accepted

## Context

Random access must not disturb a file's sequential cursor. Append needs the host's append behavior rather than a
seek-to-end followed by a separate write. Native append handles do not uniformly honor explicit positional-write offsets
across supported hosts.

## Decision

`std.file::read_at` and `write_at` transfer at an explicit nonnegative file offset without changing the shared
sequential cursor. Non-seekable objects return `NotSeekable`; positional operations retain their offset and seekability
checks even for zero-length transfers. The runtime chooses native mechanisms that preserve these observable guarantees
without resolving the original path to a potentially different object.

Append handles use native host append behavior for ordinary writes. Reject `write_at` on an append handle with
`InvalidInput` before transferring bytes, including a zero-length request. Positional reads remain available when the
handle permits reading and the object is seekable.

The host's append guarantees apply to each underlying native write. `write_all` may perform multiple writes and does not
promise a single atomic append for the entire requested range.

## Rationale

Cursor-independent operations let sequential processing and indexed access share one file owner without implicit seek
state changes. Native append avoids a race between seeking and writing. Rejecting positional append writes preserves
both contracts without claiming a portable offset behavior that native append APIs do not provide.

## Consequences

Programs that need append and arbitrary-position writes must choose an explicit access strategy rather than combining
them on one append handle. Callers still coordinate concurrent operations; cursor preservation does not promise
transactional reads or writes, whole-operation append atomicity, or freedom from native access and filesystem failures.

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
