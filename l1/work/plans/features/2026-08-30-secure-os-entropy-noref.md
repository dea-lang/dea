# Feature Plan

## Add secure operating-system entropy

- Date: 2026-08-30
- Status: Draft
- Title: Add a secure operating-system entropy module distinct from pseudorandom generation
- Kind: Feature
- Severity: Medium
- Priority: 2
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0006-process-and-host-services.md`
- Subsystem: Stdlib / runtime / host services
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/entropy.l1`
  - `l1/compiler/shared/l1/stdlib/sys/os.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_entropy.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/entropy_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_trace_test.l0`
- Related:
  - `l1/work/initiatives/0006-process-and-host-services.md`
  - `l1/work/plans/features/2026-08-30-os-error-and-io-results-noref.md`
- Repro: `make -C l1 test-stage1 TESTS="entropy_runtime_test analysis_trace_test"`

## Summary

Add `std.entropy` for bytes supplied by the operating system. It is separate from deterministic `std.rand`, reports host
failure directly, and never substitutes a predictable generator when secure entropy is unavailable.

## Public Surface

- `fill(buf: ByteBuffer*, start: int, count: int) -> EntropyResult`
- `random_bytes(count: int) -> RandomBytesResult`

The runtime uses the supported non-blocking secure host primitive where available and retries only according to the
documented interrupted-operation contract.

## Implementation Phases

1. Select supported POSIX, Apple, BSD, and Windows entropy calls without opening user-controlled paths.
2. Add direct error transport and chunking for host APIs with narrower request limits.
3. Add buffer-range, zero-length, failure-injection, and runtime-symbol tests.
4. Document the security boundary and distinction from `std.rand`.

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
    operating system cannot provide entropy.

## Verification Criteria

1. All supported hosts use an OS-provided secure source.
2. Failure is explicit and never replaced by deterministic bytes.
3. Zero-length requests succeed without probing the host.
4. Large requests are completed safely through bounded chunks.
5. Tests validate buffer bounds and symbol-manifest parity without asserting probabilistic uniqueness.
