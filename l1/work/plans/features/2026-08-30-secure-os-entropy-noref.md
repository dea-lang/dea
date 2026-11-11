# Feature Plan

## Add secure operating-system entropy

- Date: 2026-08-30
- Status: In Progress
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
  - `l1/compiler/tests/entropy_runtime_test.py`
  - `l1/compiler/tests/entropy_native_simulation.py`
  - `l1/compiler/tests/fixtures/entropy_runtime/`
- Related:
  - `l1/work/initiatives/0006-process-and-host-services.md`
  - `l1/work/plans/features/closed/2026-08-30-os-error-and-io-results-noref.md`
  - [l1/work/plans/refactors/closed/2026-11-10-byte-buffer-range-actions-noref.md][range-actions]
- Repro: From `l1/`, `make test-compiler TESTS="entropy_runtime_test.py"`; focused child traces and allocation checks
  follow the validation requirements below.

## Summary

Implemented `std.entropy` for bytes supplied by the operating system. It is separate from deterministic `std.rand`,
reports host failure directly, and never substitutes a predictable generator when secure entropy is unavailable.

The range protocol and file migration are implemented, validated, and closed in
[l1/work/plans/refactors/closed/2026-11-10-byte-buffer-range-actions-noref.md][range-actions]. This feature uses that
validated foundation. The entropy provider uses the synchronous range API: `std.bytes` checks logical bounds and
dispatches the callback, while `std.entropy` owns the native call and result conversion. No entropy-specific bridge or
native OS operation belongs in `std.bytes`.

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

Preserve captured native domains, including the distinct `NtStatus` domain for BCrypt provider failures and `Win32`
domain for loader failures. Preserve NTSTATUS as an unsigned 32-bit value widened to positive `long`; never replace it
with ambient last-error state or assume the earlier domain inventory is exhaustive. `std.bytes` forwards these integer
fields without assigning any OS meaning.

The generic helper still invokes the callback once for a valid empty range. `rt_entropy_fill` then succeeds without
calling the host, preserving the entropy contract. Invalid ranges fail before callback entry. Preserve the runtime's
bounded 256-byte stack staging, successful-short continuation, no implicit interruption/unavailable retry, exact failure
prefix, and unchanged failed suffix and surrounding bytes. Retain the secure OS source and no predictable fallback.

`fill` must add no Dea heap allocation around a pre-sized buffer. `random_bytes` intentionally allocates its result
buffer; retain that ownership behavior and release partial buffers before returning failure without exposing them.
Measure range/context/result transport separately from this explicit creation API and from native loader resources.

The initial entropy ADR will record the provider contract and reference
[l1/docs/decisions/0063-synchronous-byte-buffer-range-actions.md][range-adr]. Assign the entropy ADR number from the
live index at feature closure and add the closed-plan backlinks in the same change.

## Implementation Scope

The public provider uses the existing range-action protocol without changing `std.bytes` or `std.file`. Native source
selection uses bounded stack staging and explicit error transport. Build, preparation identity, profile inventory, and
runtime symbol manifests include the new runtime source. Source and emitted-interface consumers share the public API. No
compiler diagnostic or diagnostic-code allocation changes are required.

New coverage checks logical ranges, empty dispatch, partial failures, runtime symbols, private schema rejection,
interface-only use, allocation-free fill, and result cleanup. Stable references describe the delivered API and ownership
contract; CI evidence and feature closure remain in this plan.

## Host Source Decisions

- Linux, FreeBSD, and NetBSD use `getrandom(..., GRND_NONBLOCK)` to return unavailable entropy explicitly. Successful
  short fills continue; interruption and failure return immediately.
- Apple and OpenBSD use `getentropy` with requests bounded to 256 bytes.
- Windows loads BCrypt through `LOAD_LIBRARY_SEARCH_SYSTEM32` and uses the system-preferred RNG. Provider NTSTATUS and
  Win32 loader failures retain separate native domains, captured before cleanup.
- Unsupported hosts report `Unsupported`; no device-path or predictable fallback is introduced.

Primary contracts reviewed: [Linux getrandom][linux-random], [FreeBSD getrandom][freebsd-random],
[NetBSD getrandom][netbsd-random], [Apple getentropy][apple-entropy], [OpenBSD getentropy][openbsd-entropy],
[BCryptGenRandom][bcrypt], and [LoadLibraryExW][system-loader].

## Adapter Coverage

- Exercise the entropy suite in checked, basic, unchecked, and traced modes. Verify logical-range validation, exactly
  one callback for valid empty requests, and zero host calls for empty requests. Test source and emitted-interface
  consumers of the migrated public API.

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

Reproduce focused `entropy_runtime_test.py` coverage and the registered `entropy_main` child trace from `l1/`, plus the
affected byte-buffer, OS-error, interface, and runtime-symbol regressions. Exhaustive native platform checks remain
assigned to CI.

## Implementation Status

- [x] Implemented `std.entropy` using the range protocol, with no changes to `std.bytes` or `std.file`.
- [x] Added bounded native entropy sources, distinct NTSTATUS transport, and runtime/build/preparation inventories.
- [x] Passed the focused local API, schema, allocation, ownership, interface, native-adapter, and supporting
  regressions.
- [x] Updated stable API/ownership references and ADR-0045; independent correctness and portability review found no
  outstanding production issue.
- [ ] Obtain native CI evidence for Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64.
- [ ] Create the entropy ADR and index entry, add closed-plan backlinks to ADR-0045/0063, and close the feature plan
  with its initiative and roadmap links after acceptance.

## Local Verification Evidence

Local execution used macOS Intel and explicitly selected `/usr/bin/clang` for `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`:
Apple Clang 17.0.0 (`clang-1700.6.4.2`), with `--no-default-config` capability verified. An explicit existing L0 Stage 2
compiler supplied the bootstrap. `make build runtime` regenerated 33 bundled interfaces and normal, basic, unchecked,
and traced runtime inputs; supplemental TinyCC objects used TinyCC 0.9.28rc.

- `entropy_runtime_test.py` passed public checked/basic/unchecked/traced behavior, bounds, alias expiry, and result
  cleanup. Private schema, interface-only, native injection/simulation, and allocation checks ran separately against
  unchanged production inputs; together they cover the complete harness. The interface consumer ran with both entropy
  and byte-buffer source absent.
- Allocation windows observed no Dea allocation events across 128 first/repeated success and partial-failure fills,
  including empty requests, with an allocation positive control outside the windows. Complete ownership traces balanced.
  Generated-C review confirmed by-value aggregates without boxing or ARC transport.
- Native Apple probes and deterministic Linux, Windows, and unsupported-host simulations passed. Cases cover successful
  short fills followed by failure, exact prefix preservation, dirty failed staging, unavailable/interrupted sources,
  loader/export failures, zero loader calls on empty requests, unknown NTSTATUS, and error preservation across cleanup.
- The selected compiler regressions passed: `bytes_test.py`, `byte_buffer_range_action_test.py`, `os_runtime_test.py`,
  `io_runtime_test.py`, `runtime_symbol_manifest_test.py`, `l1c_child_trace_runner_test.py`, `build_driver_test.l0`,
  `preparation_profile_test.py`, `preparation_construction_test.py`, `preparation_clang_compatibility_test.py`, and
  `runtime_trace_policy_test.py`.
- Focused preparation probes passed entropy source/API identity invalidation, actual default/traced runtime compilation,
  and dependency coverage for all 11 runtime units and four generated-C configurations.
- The `build_driver_test` canonical trace and `bytes_main`, `range_action_main`, `file_main`, and `entropy_main` child
  traces passed with zero leaked object or string pointers.
- Strict `make docs`, C-contract validation including untracked fixtures, Markdown/link checks, ADR Impact validation,
  and whitespace checks passed.

Reproduce from `l1/` with the explicit compiler/bootstrap selection above:

```sh
make build runtime
make test-compiler TESTS="entropy_runtime_test.py bytes_test.py byte_buffer_range_action_test.py os_runtime_test.py io_runtime_test.py runtime_symbol_manifest_test.py l1c_child_trace_runner_test.py build_driver_test.l0 preparation_profile_test.py preparation_construction_test.py preparation_clang_compatibility_test.py runtime_trace_policy_test.py"
make test-compiler-trace TESTS="build_driver_test"
make test-compiler-trace-children TESTS="bytes_main range_action_main file_main entropy_main"
make docs
```

No native Linux, Windows, macOS ARM, or BSD execution is claimed by these local checks. Simulations and documentation
review do not replace native CI. Broad aggregates, exhaustive compiler validation, and final ADR closure remain pending.

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
  - Rationale: The NTSTATUS error domain preserves the provider's original status independently of Win32 loader errors
    and ambient last-error state, including through the range-action diagnostic payload.

- Decision: Use the established synchronous unsafe range protocol for entropy transport without Dea heap allocation.

  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0063-synchronous-byte-buffer-range-actions.md`
  - Rationale: The provider consumes the existing by-value context/result and no-escape contracts without changing the
    generic protocol; partial failures are already permitted.

## Verification Criteria

1. All supported hosts use an OS-provided secure source.
2. Failure is explicit and never replaced by deterministic bytes.
3. Zero-length requests succeed without probing the host.
4. Large requests are completed safely through bounded chunks.
5. Tests validate buffer bounds and symbol-manifest parity without asserting probabilistic uniqueness.
6. `fill` uses the generic range protocol without per-transfer context/result allocations or OS calls in `std.bytes`;
   `random_bytes` retains its intentional result-buffer allocation and failure cleanup.

[apple-entropy]: https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/man/man2/getentropy.2
[bcrypt]: https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/nf-bcrypt-bcryptgenrandom
[freebsd-random]: https://man.freebsd.org/cgi/man.cgi?query=getrandom&sektion=2
[linux-random]: https://man7.org/linux/man-pages/man2/getrandom.2.html
[netbsd-random]: https://man.netbsd.org/getrandom.2
[openbsd-entropy]: https://man.openbsd.org/getentropy.2
[range-actions]: ../refactors/closed/2026-11-10-byte-buffer-range-actions-noref.md
[range-adr]: ../../../docs/decisions/0063-synchronous-byte-buffer-range-actions.md
[system-loader]: https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-loadlibraryexw
