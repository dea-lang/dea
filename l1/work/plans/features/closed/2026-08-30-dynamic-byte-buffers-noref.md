# Feature Plan

## Add mutable dynamic byte buffers

- Date: 2026-11-05
- Last reviewed: 2026-11-05
- Status: Completed
- Title: Add a public mutable dynamic byte-buffer module
- Kind: Feature
- Priority: High
- Stdlib Tier: 1
- Parent Initiative: `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Subsystem: Stdlib / containers / binary I/O
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/bytes.l1`
- Test modules:
  - `l1/compiler/tests/bytes_test.py`
  - `l1/compiler/tests/fixtures/bytes/bytes_main.l1`
  - `l1/compiler/scripts/test_runner_common.py`
- Related:
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/work/initiatives/closed/0004-array-primitives-and-unsafe-marker.md`
  - `l1/work/plans/bug-fixes/closed/2026-10-29-borrowed-slice-escape-noref.md`

## Scope and Outcome

Implemented `std.bytes` as the public growable binary-buffer layer. `ByteBuffer` is exported opaquely, with checked
`int` lengths, capacities, indexes, and counts. Fixed `ByteArray` and existing stream helpers remain available.

The public surface is `create`, `with_capacity`, `free`, `len`, `capacity`, `reserve`, `resize`, `clear`, `get`, `set`,
`append_byte`, `append_range`, `append_buffer`, `to_string`, and `from_string`. No operation exposes storage or returns
a slice. Constructors establish one explicit cleanup obligation compatible with `with`; aliases borrow that obligation.

The decision is recorded in [l1/docs/decisions/0052-owned-dynamic-byte-buffers.md][buffer-decision].

## Implementation Decisions

- Keep one private raw byte allocation using existing checked runtime primitives. Avoid exporting or relying on the raw
  `VectorBase` layout and its unchecked length-growth arithmetic.
- Reserve total capacity with geometric growth and saturation at `int_max`. Check append additions and source ranges
  with subtraction before allocation. Invalid sizes/ranges, overflow, and allocation failure terminate execution in both
  checked and unchecked modes.
- Shrink and clear retain capacity. Resize zeroes all newly visible bytes, including previously discarded bytes. Clear
  is not secure erasure.
- Copy borrowed slice subranges synchronously; no safe public operation can form a slice of buffer storage. L1 has no
  address-of operation, so slice copying uses indexed byte reads. Buffer-to-buffer append uses bulk copying, reloading
  source storage after reserve to support self-append across relocation.
- Copy string conversions preserve embedded NUL and non-UTF-8 bytes. Converted strings and buffers have independent
  lifetimes and mutation behavior.
- Use qualified `bytes::len` alongside the existing `dea::len` intrinsic. The current compiler's prelude-shadow warning
  remains documented; no new compiler diagnostic or language rule is introduced.

## Verification

Native validation ran on macOS Intel with `/usr/bin/clang`, Apple Clang 17.0.0, after verifying support for
`--no-default-config`. The explicit upstream L0 Stage 2 toolchain built canonical L1. No native Linux, macOS ARM, or
Windows execution is claimed.

Passed from `l1/`, with `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC` explicitly selecting that compiler:

- `make test-compiler TESTS="bytes_test.py byte_array_test analysis_trace_test l1c_trace_runner_common_test.py"`: four
  focused cases passed. The final byte-buffer fixture additionally exercises resize across reallocation, and
  `../.venv/bin/python compiler/tests/bytes_test.py` passed again after that addition.
- `make test-compiler-trace TESTS="byte_array_test analysis_trace_test"`: both ownership regressions passed with no
  object or string leaks.
- `../.venv/bin/python compiler/scripts/run_trace_tests.py --children bytes_main`: the final actual L1 consumer passed
  with 125 memory events, 18 ARC events, and no object or string leaks. The fixture is registered for routine child
  trace discovery.
- The normal bundled-interface and managed-native workflow,
  `build/dea/bin/l1c --project-root compiler/tests/fixtures/bytes --run bytes_main`, prepared the stdlib/runtime and
  passed.
- `make test-docgen docs`: 114 documentation tests and strict reference generation passed.

Behavioral coverage includes zero capacity, amortized repeated growth, retained capacity, shrink/regrow initialization,
checked indexing and source ranges, independent source copies, self-append with and without relocation, every byte
value, embedded NUL, non-UTF-8 bytes, string lifetime, and early-return cleanup. Source and generated-interface
consumers reject hidden field access, size, construction, dereference, and direct drop with `RES-0038`.

A same-module harness runs the unchanged production definitions with test-only allocation shims and synthetic lengths.
It verifies exact-limit addition, saturation, overflow rejection before allocation, and allocation/reallocation failure
without allocating or accessing gigabyte ranges. Checked and unchecked runtime modes pass the same contracts. Later
documentation-only edits reuse the completed code validation.

## ADR Impact

- Decision: Add a distinct owned growable byte buffer with `int` lengths, explicit copying text conversion, and borrowed
  inputs without returning views.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0052-owned-dynamic-byte-buffers.md`
  - Rationale: Binary I/O needs amortized growth without conflating arbitrary bytes with immutable strings or exposing
    untyped storage. The ADR records ownership, failure, range, and conversion contracts.

## Non-Goals

- implicit conversion between strings and binary buffers
- 64-bit in-memory lengths or indexes
- shared mutable buffers or cross-thread synchronization
- owned slices, returning `byte[]`, escaping views, or implicit lifetime extension
- memory mapping, zero-copy ownership, secure erasure, or recoverable allocation results
- replacing fixed `ByteArray`, implementing file/entropy APIs, or changing the compiler bootstrap

[buffer-decision]: ../../../../docs/decisions/0052-owned-dynamic-byte-buffers.md
