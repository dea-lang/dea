# Feature Plan

## Add mutable dynamic byte buffers

- Date: 2026-08-30
- Status: Draft
- Title: Add a public mutable dynamic byte-buffer module
- Kind: Feature
- Severity: High
- Priority: 1
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Subsystem: Stdlib / containers / binary I/O
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/bytes.l1`
  - `l1/compiler/shared/l1/stdlib/std/array.l1`
  - `l1/compiler/shared/l1/stdlib/std/vector.l1`
  - `l1/compiler/shared/l1/stdlib/sys/memory.l1`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/byte_array_test.l0`
  - `l1/compiler/stage1_l0/tests/bytes_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_trace_test.l0`
- Related:
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/work/initiatives/closed/0004-array-primitives-and-unsafe-marker.md`
- Repro: `make -C l1 test-stage1 TESTS="byte_array_test bytes_test analysis_trace_test"`

## Summary

Add `std.bytes` as the public growable binary-buffer layer required by file I/O, networking, and streaming parsers.
Binary data remains distinct from text, and all lengths and indexes remain `int` to match arrays and slices.

## Defaults Chosen

1. Introduce a module-owned `ByteBuffer` type with `create`, `with_capacity`, `len`, `capacity`, `reserve`, `resize`,
   and `clear`.
2. Add checked `get` and `set`, plus `append_byte`, `append_range`, and `append_buffer`.
3. Expose temporary `byte[]` views through `as_slice` under the existing slice escape restrictions.
4. Make `to_string` and `from_string` explicit copying conversions.
5. Keep fixed-sized `ByteArray` available for callers that need a stable-size allocation.
6. Reuse safe container/runtime primitives where possible without exposing raw `VectorBase` storage as the public
   contract.
7. Define growth overflow and allocation failure behavior instead of relying on wrapped `int` arithmetic.

## Implementation Phases

1. Establish representation, ownership, cleanup, checked indexing, capacity growth, and overflow tests.
2. Add bulk append and slice interoperation.
3. Add explicit string conversions, including embedded NUL and non-UTF-8 byte coverage.
4. Add ARC/memory trace coverage and current-reference documentation.

## Non-Goals

- implicit conversion between strings and binary buffers
- 64-bit in-memory lengths or indexes
- shared mutable buffers or cross-thread synchronization
- memory mapping or zero-copy file ownership
- replacing fixed `ByteArray` in the first tranche

## ADR Impact

- Decision: Add a distinct owned growable byte buffer with `int` lengths, explicit text conversion, and escape-
  restricted slice views.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Binary I/O needs amortized growth without conflating arbitrary bytes with immutable strings or exposing
    the untyped `VectorBase` representation as public API.

## Verification Criteria

1. Growth preserves data and rejects arithmetic overflow before allocation.
2. Indexed access and resize behavior are bounds checked.
3. Slice views cannot outlive or escape their owner under existing L1 rules.
4. String conversions preserve all bytes, including embedded NUL, and are visibly explicit.
5. Normal and trace suites report balanced ownership for create, grow, clear, and drop paths.
