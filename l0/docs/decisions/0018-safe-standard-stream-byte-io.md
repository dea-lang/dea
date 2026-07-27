# ADR-0018: Safe Standard-Stream Byte I/O

- Decision date: 2026-03-09
- Last edited: 2026-07-27
- Status: Accepted

## Context

Bootstrap compiler work required binary reads from stdin and exact byte writes to stdout and stderr. Exposing the
runtime's raw `byte*` transfer functions directly through `std.io` would make ordinary callers responsible for pointer
validity, capacity, range arithmetic, and partial progress. Treating invalid ranges and external I/O failures alike
would also blur the boundary between a programming error and a recoverable host condition.

L0 therefore needs a safe default byte-stream surface while retaining an explicit low-level escape hatch for runtime and
container implementations.

## Decision

The standard-stream byte boundary is:

1. Safe `std.io` operations accept a fixed-capacity `std.array::ByteArray*` and explicit `start` and `count` values.
   `ByteArray` owns its backing storage and does not carry a separate logical used length.
2. Every safe operation assertion-checks `start >= 0`, `count >= 0`, `start <= capacity`, and
   `count <= capacity - start`. An invalid range is a programmer-contract violation, not an optional I/O failure.
3. `read_stdin_some` returns a positive byte count for progress, `0` for EOF, and `null` for I/O failure.
4. `write_stdout_some` and `write_stderr_some` return the observed byte count, including zero when the underlying
   operation reports zero progress, and `null` for I/O failure.
5. `write_stdout_all` and `write_stderr_all` loop over partial writes. They return `null` on I/O failure or zero
   progress before the requested range is complete.
6. Zero-length operations are valid.
7. Raw pointer stream operations remain in the low-level `sys.memory` boundary and are not re-exported by `std.io`.

## Rationale

- A fixed-capacity wrapper provides bounds-checked indexing and ownership without pretending that L0 has complete field
  privacy.
- Explicit subranges make buffer capacity and the meaningful byte count separate and visible.
- Counts preserve partial progress, while distinct EOF and `null` results let callers handle normal stream completion
  separately from host failure.
- Assertions identify invalid caller ranges as contract defects instead of encouraging error-recovery logic around
  memory-safety violations.
- Keeping raw pointers in `sys.memory` makes unsafe operations available to low-level code without turning them into the
  default I/O API.

## Consequences

- Callers allocate and free `ByteArray` storage and track how much of the fixed capacity contains meaningful data.
- Safe I/O implementations must validate the full range before deriving a raw pointer into the backing array.
- Partial read and write behavior remains observable; callers that require complete output use the `*_all` helpers.
- A zero-progress write cannot make an all-write loop spin forever.
- New stream APIs must preserve the safe/unsafe module boundary established by
  [ADR-0015](0015-stdlib-module-boundaries.md).

## Related Plans

- [l0/work/plans/features/closed/2026-03-09-stdlib-runtime-fs-path-raw-io-bootstrap-noref.md](../../work/plans/features/closed/2026-03-09-stdlib-runtime-fs-path-raw-io-bootstrap-noref.md):
  selected `ByteArray`, checked subranges, progress results, and the low-level pointer boundary
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the safe standard-stream contract into this ADR

## Current Docs

- [l0/docs/reference/standard-library.md](../reference/standard-library.md): current `ByteArray`, `std.io`, and
  `sys.memory` APIs
- [l1/docs/reference/standard-library.md](../../../l1/docs/reference/standard-library.md): downstream shared-library
  surface
- [l0/docs/decisions/0015-stdlib-module-boundaries.md](0015-stdlib-module-boundaries.md): standard-library ownership of
  safe I/O and raw memory operations
