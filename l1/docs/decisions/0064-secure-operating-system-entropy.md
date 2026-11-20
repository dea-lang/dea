# ADR-0064: Secure Operating-System Entropy

- Decision date: 2026-11-20
- Last edited: 2026-11-20
- Status: Accepted

## Context

Temporary-object creation and other security-sensitive consumers need bytes supplied by the operating system.
Deterministic `std.rand` cannot satisfy that contract. A provider must report unavailable entropy and native failures
without substituting predictable output, while preserving opaque buffer ownership and completed progress.

## Decision

Expose `std.entropy::fill` for initialized logical ranges of caller-owned `std.bytes::ByteBuffer` storage, plus
`random_bytes` and `free_random_bytes_result` for an explicitly allocated result buffer. `fill` returns complete success
or a captured `OsError` with the exact completed prefix. It preserves buffer ownership, logical size, capacity,
surrounding bytes, and the unfilled suffix on failure.

Use the synchronous unsafe range protocol recorded in
[l1/docs/decisions/0063-synchronous-byte-buffer-range-actions.md][range-actions]. A private entropy callback passes
`ByteBufferRangeActionContext(null, 0)` by value, invokes the native entropy operation once, and owns its result
conversion. `std.bytes` validates generic bounds and progress without interpreting OS data. Valid empty ranges invoke
the callback once, but the native operation makes no host call. Invalid logical ranges fail before callback entry.

The entropy decoder requires complete success with a null success payload. It rejects stopped outcomes and malformed
schema fields while permitting failure after nonzero progress. Captured native domains and codes survive conversion;
BCrypt provider failures use unsigned 32-bit NTSTATUS widened to positive `long`, separately from Win32 loader errors,
as recorded in [l1/docs/decisions/0045-direct-os-errors-and-io-results.md][os-errors].

Select secure host sources explicitly:

- Linux, FreeBSD, and NetBSD use `getrandom` with `GRND_NONBLOCK`.
- Apple and OpenBSD use `getentropy`.
- Windows resolves `BCryptGenRandom` through System32-only loading and uses the system-preferred RNG.
- Unsupported hosts fail explicitly without a device-path or predictable fallback.

Stage at most 256 bytes on the stack per host operation and copy only successfully generated chunks to the destination.
Continue successful short fills; return interruption, unavailable entropy, and other failures immediately without an
implicit retry. Capture native errors before cleanup so loader cleanup or ambient state cannot replace the cause.

Range dispatch and entropy context/result transport add no Dea heap allocation to `fill` on a pre-sized buffer.
`random_bytes` intentionally allocates its buffer, returns one shared cleanup obligation on success, and frees any
partial buffer before returning failure. Extracted buffer pointers borrow that result owner. Neither API promises secure
erasure.

## Rationale

Separate deterministic and secure APIs make the source requirement explicit. Structured partial failures let callers
decide whether and how to retry without losing native diagnostics. Bounded staging protects the destination suffix even
when a failed host call modifies its output buffer. Provider-owned conversion preserves the generic range protocol and
keeps native operations out of the buffer module.

## Consequences

- Security-sensitive consumers must handle explicit failure and cannot assume entropy is always available.
- Buffer lifetime and synchronous no-escape rules remain unchanged; `fill` does not expose or retain a storage view.
- The Dea allocation guarantee excludes explicit result-buffer creation and native loader resource costs.
- Tests use deterministic failure injection and native execution, without probabilistic uniqueness assertions.
- Native acceptance covers Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64. BSD source branches have no native
  CI acceptance claim.
- Cryptographic algorithms, key storage, entropy-quality estimation, and secure erasure remain outside this API.

## Related Plans

- [l1/work/plans/features/closed/2026-08-30-secure-os-entropy-noref.md][entropy-plan]

## Current Docs

- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/ownership.md][ownership]
- [l1/docs/reference/design-decisions.md][design]

[design]: ../reference/design-decisions.md#secure-operating-system-entropy
[entropy-plan]: ../../work/plans/features/closed/2026-08-30-secure-os-entropy-noref.md
[os-errors]: 0045-direct-os-errors-and-io-results.md
[ownership]: ../reference/ownership.md#stdentropy-randombytesresult
[range-actions]: 0063-synchronous-byte-buffer-range-actions.md
[stdlib]: ../reference/standard-library.md#stdentropy
