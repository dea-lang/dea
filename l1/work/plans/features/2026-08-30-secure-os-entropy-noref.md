# Feature Plan

## Add secure operating-system entropy

- Date: 2026-08-30
- Status: Draft
- Title: Add a secure operating-system entropy module distinct from pseudorandom generation
- Kind: Feature
- Priority: Medium
- Stdlib Tier: 2
- Parent Initiative: `l1/work/initiatives/0006-process-and-host-services.md`
- Subsystem: Stdlib / runtime / host services
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/entropy.l1`
  - `l1/compiler/shared/l1/stdlib/std/os.l1`
  - `l1/compiler/shared/l1/stdlib/sys/os.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_entropy.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l1/compiler/tests/entropy_runtime_test.py` (pending integration)
  - `l1/compiler/tests/entropy_native_simulation.py` (pending integration)
  - `l1/compiler/tests/fixtures/entropy_runtime/` (pending integration)
- Related:
  - `l1/work/initiatives/0006-process-and-host-services.md`
  - `l1/work/plans/features/closed/2026-08-30-os-error-and-io-results-noref.md`
  - [l1/work/plans/refactors/closed/2026-11-10-byte-buffer-range-actions-noref.md][range-actions]
- Repro: After integration, from `l1/`, `make test-compiler TESTS="entropy_runtime_test.py"`; focused child traces and
  allocation checks follow the validation requirements below.

## Summary

Add `std.entropy` for bytes supplied by the operating system. It is separate from deterministic `std.rand`, reports host
failure directly, and never substitutes a predictable generator when secure entropy is unavailable.

The range protocol and file migration are implemented, validated, and closed in
[l1/work/plans/refactors/closed/2026-11-10-byte-buffer-range-actions-noref.md][range-actions]. Bring that foundation
into entropy's integration base before resuming this feature. Adapt the entropy provider to the synchronous range API:
`std.bytes` checks logical bounds and dispatches the callback, while `std.entropy` owns the native call and result
conversion. No entropy-specific bridge or native OS operation belongs in `std.bytes`.

The dependency is one-way: this feature consumes the range protocol, and its implementation, validation, and closure
must not become prerequisites of the protocol refactor.

Use a by-value context with null state and a zero argument. Preserve completed-prefix failures and native OS error
domains, including distinct NTSTATUS and Win32 sources; do not reuse file decoding that requires zero terminal progress.
Valid empty requests still invoke the range callback once, but the entropy runtime must make no host call. Keep buffer
allocation explicit in `random_bytes`, with no new context/result allocation on `fill`.

## Public Surface

- `fill(buf: ByteBuffer*, start: int, count: int) -> EntropyResult`
- `random_bytes(count: int) -> RandomBytesResult`
- `free_random_bytes_result(result: RandomBytesResult)`

The runtime uses the supported non-blocking secure host primitive where available and continues only successful short
transfers. Interruption or unavailable entropy returns immediately without implicit retry. Successful random-byte
results carry one shared cleanup obligation; failed `random_bytes` calls release their partial buffers before returning
failure. `fill` preserves caller ownership and reports the completed prefix.

## Range-Action Adapter

Use a private unsafe callback in `std.entropy` and construct `ByteBufferRangeActionContext(null, 0)` by value. The
callback calls `rt_entropy_fill(data as void*, count)` exactly once and explicitly encodes its result. It needs no file
handle or allocated context. Keep native chunking and staging in the entropy runtime; do not duplicate its loop in the
callback or reuse file-specific result conversion.

| Native entropy outcome               | Range result                          | Public entropy result        |
| ------------------------------------ | ------------------------------------- | ---------------------------- |
| Complete success, state 0            | `RangeActionApplied(count, null)`     | `EntropyFilled`              |
| Failure, state 2, after `done` bytes | `RangeActionFailed(done, diagnostic)` | `EntropyFailed(done, error)` |

The entropy schema uses `tag = native state`, `code = error.kind`, `detail = error.domain`, and
`value = error.native_code`. Its decoder requires success progress equal to the requested count and a null success
value. A failure may have nonzero progress; retain the exact completed prefix. Reject `RangeActionStopped` and invalid
entropy outcome/tag combinations. The file decoder's zero-terminal-progress requirement must not become a restriction of
the generic protocol or entropy decoder.

Preserve captured native domains, including the preliminary entropy implementation's distinct `NtStatus` domain for
BCrypt provider failures and `Win32` domain for loader failures. Preserve NTSTATUS as an unsigned 32-bit value widened
to positive `long`; never replace it with ambient last-error state or assume the earlier domain inventory is exhaustive.
`std.bytes` forwards these integer fields without assigning any OS meaning.

The generic helper still invokes the callback once for a valid empty range. `rt_entropy_fill` then succeeds without
calling the host, preserving the entropy contract. Invalid ranges fail before callback entry. Preserve the runtime's
bounded 256-byte stack staging, successful-short continuation, no implicit interruption/unavailable retry, exact failure
prefix, and unchanged failed suffix and surrounding bytes. Retain the secure OS source and no predictable fallback.

`fill` must add no Dea heap allocation around a pre-sized buffer. `random_bytes` intentionally allocates its result
buffer; retain that ownership behavior and release partial buffers before returning failure without exposing them.
Measure range/context/result transport separately from this explicit creation API and from native loader resources.

The initial entropy ADR records this adapter and references the range protocol ADR created by the preceding refactor.
Select the exact indexed protocol ADR after that work is finalized; add a `Covered by ADR` record and the required
closed-plan backlink if applicable. Assign the entropy ADR number from the live index at entropy closure.

## Implementation Phases

1. After the range protocol and file migration are implemented and validated, resume this feature against that
   foundation. Adapt the preliminary entropy work to the completed API and keep `std.bytes` independent of I/O.
2. Verify supported POSIX, Apple, BSD, and Windows entropy calls without opening user-controlled paths.
3. Add direct error transport and chunking for host APIs with narrower request limits.
4. Add buffer-range, zero-length, failure-injection, runtime-symbol, adapter, and allocation checks described below.
   Preserve partial progress and failed-suffix contents.
5. Document the security boundary and distinction from `std.rand`.

## Adapter Tests and Allocation Evidence

- Extend the pending entropy suite in checked, basic, unchecked, and traced modes. Verify logical-range validation,
  exactly one callback for valid empty requests, and zero host calls for empty requests. Test source and
  emitted-interface consumers of the migrated public API.

- Verify complete success, partial failure after a successful chunk, exact progress, and unchanged failed suffix even
  when a failing host call dirties its staging buffer. Preserve bounded chunking, successful short fills, interruption,
  unavailable/unsupported sources, and no predictable fallback. Use deterministic injection, never probabilistic
  uniqueness assertions.

- Reject malformed success counts, non-null success values, stopped variants, and mismatched entropy tags. Accept
  nonzero failure progress within the requested range. Preserve error kind, `NtStatus` versus `Win32`/errno, wide native
  codes, and independence from ambient errors or cleanup failures. Retain loader/export failure fixtures and adapter
  simulations; report simulated coverage separately from native execution.

- Preserve `random_bytes` success ownership, alias expiry, and partial-allocation cleanup without publishing a failed
  buffer. Keep rendering of error messages outside allocation measurement windows.

- With preallocated buffers, measure first and repeated `fill` calls, including partial failure, using
  `--trace-arc --trace-memory` and nonallocating measurement markers. Reject added allocation events rather than
  checking only balanced cleanup; include a positive-control allocation outside the window. Verify complete-log
  ownership separately. Exclude intentional `random_bytes` buffer construction and native loader resources from the
  transport-allocation claim.

After implementation, run focused `entropy_runtime_test.py` coverage and the registered `entropy_main` child trace from
`l1/`, plus the affected byte-buffer, OS-error, interface, and runtime-symbol regressions. Keep exhaustive native
platform checks in CI. Earlier prototype results do not validate the adapted implementation.

## Non-Goals

- seeded or repeatable pseudorandom generation
- cryptographic algorithms, key storage, or protocol design
- entropy-quality estimation
- falling back to timestamps, process IDs, `rand`, or `std.rand`
- returning secret bytes through immutable text strings

## ADR Impact

- Decision: Expose host entropy as a fallible binary service distinct from deterministic pseudorandom generation, with
  no insecure fallback.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Temporary-name and security-sensitive consumers must not accidentally receive predictable output when the
    operating system cannot provide entropy. Record the provider-owned callback adapter and native error preservation
    while referencing the generic range protocol's ADR; `std.bytes` remains independent of OS operations.
- Decision: Preserve BCrypt provider failures in a distinct native OS error namespace.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0045-direct-os-errors-and-io-results.md`
  - Rationale: The planned NTSTATUS error domain must preserve the provider's original status independently of Win32
    loader errors and ambient last-error state, including through the range-action diagnostic payload.

## Verification Criteria

1. All supported hosts use an OS-provided secure source.
2. Failure is explicit and never replaced by deterministic bytes.
3. Zero-length requests succeed without probing the host.
4. Large requests are completed safely through bounded chunks.
5. Tests validate buffer bounds and symbol-manifest parity without asserting probabilistic uniqueness.
6. `fill` uses the generic range protocol without per-transfer context/result allocations or OS calls in `std.bytes`;
   `random_bytes` retains its intentional result-buffer allocation and failure cleanup.

[range-actions]: ../refactors/closed/2026-11-10-byte-buffer-range-actions-noref.md
