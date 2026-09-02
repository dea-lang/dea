# Bug Fix Plan

## Make bulk byte-vector pushes safe for backing-store aliases

- Date: 2026-09-02
- Status: Completed
- Title: Make shared L0 and L1 bulk byte-vector pushes safe for backing-store aliases
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 shared standard library and header runtime
  - L1 shared standard library and archive runtime
- Origin: The L1 shared standard-library implementation has a confirmed unchecked-mode AddressSanitizer
  heap-use-after-free; the L0 standard-library copy has the same reserve-before-copy sequence.
- Porting rule: Settle the alias-offset and logical-source-range contract against the confirmed L1 failure, then port
  the runtime helper, vector change, and regression shape mechanically to L0.
- Target status:
  - L0 shared standard library and header runtime: Completed
  - L1 shared standard library and archive runtime: Completed
- Subsystem: Standard-library vectors / raw-memory runtime / allocation lifetime
- Modules:
  - `l0/compiler/shared/l0/stdlib/std/vector.l0`
  - `l0/compiler/shared/l0/stdlib/sys/memory.l0`
  - `l0/compiler/shared/runtime/dea_rt.h`
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l1/compiler/shared/l1/stdlib/std/vector.l1`
  - `l1/compiler/shared/l1/stdlib/sys/memory.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_runtime_pointer_validation.py`
  - `l0/compiler/stage1_py/tests/backend/test_runtime_public_header.py`
  - `l0/compiler/stage2_l0/tests/vector_test.l0`
  - `l0/compiler/stage2_l0/tests/vector_aliasing_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_pointer_validation_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_symbol_manifest_test.py`
  - `l1/compiler/stage1_l0/tests/vector_aliasing_test.py`
- Related:
  - `work/plans/bug-fixes/closed/2026-08-23-shared-vector-logical-bounds-noref.md`
  - `work/plans/bug-fixes/closed/2026-09-01-shared-builtin-and-runtime-contract-observability-noref.md`
  - `work/plans/features/closed/2026-06-30-shared-runtime-pointer-access-validation-noref.md`
  - `l1/work/plans/features/2026-06-21-cheap-string-slices-noref.md`
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
  - `l0/docs/reference/standard-library.md`
  - `l1/docs/reference/standard-library.md`
- Repro: Compile and run the minimized growth-triggering self-append in Current State through L1 Stage 1 with the
  unchecked runtime and AddressSanitizer.

## Summary

`vec_push_bytes` accepts a raw `src` pointer, computes the required capacity, calls `vec_reserve`, and only then copies
from `src`. When `src` points into the vector's own backing allocation and reserve grows that allocation, `rt_realloc`
may move and release the old storage. The later `rt_memcpy` reads through the stale interior pointer.

An L1 probe reliably reports an AddressSanitizer heap-use-after-free in unchecked mode. At investigation time, ordinary
checked execution could appear to pass because quarantine kept the released allocation readable. The rebased runtimes
now poison retained payloads when built with AddressSanitizer, so checked-plus-ASan execution should expose the stale
read as `use-after-poison`; this observability improvement does not repair the invalid source lifetime. The L0 and L1
standard-library copies have the same vulnerable operation order, so one shared plan must restore the same alias-safe
contract in both.

## ADR Impact

- Decision: Rebase a valid logical self-alias across vector growth while preserving the existing append and raw-memory
  contracts.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The fix restores defined behavior for an already accepted low-level vector operation. It does not change
    language semantics, container layout, ownership rules, or the public runtime ABI; the planned offset helper is
    implementation-private.

## Current State and Reproduction Evidence

The minimized L1 failure shape is:

```l1
let vec = vec_create(sizeof(byte), 2);
vec_push_byte(vec, 'A');
vec_push_byte(vec, 'B');

let aliased_source = vec.arr.data as byte*;
vec_push_bytes(vec, aliased_source, 2);

assert(*(vec_get(vec, 2) as byte*) == 'A', "first appended byte mismatch");
assert(*(vec_get(vec, 3) as byte*) == 'B', "second appended byte mismatch");
vec_free(vec);
```

Observed evidence:

1. The vector is full before `vec_push_bytes`, so appending two bytes forces `vec_reserve` through `arr_resize` and
   `rt_realloc`.
2. An unchecked build under AddressSanitizer reports a heap-use-after-free when `rt_memcpy` reads `aliased_source`.
3. Ordinary checked execution may appear to pass because the old allocation remains in quarantine; this is not evidence
   that the pointer is valid. When the rebased checked runtime is itself built with AddressSanitizer, its quarantine
   poisoning should expose the same stale read as `use-after-poison`.
4. `l0/compiler/shared/l0/stdlib/std/vector.l0` and `l1/compiler/shared/l1/stdlib/std/vector.l1` contain the same
   reserve-before-copy implementation.
5. Existing vector coverage exercises growth and logical bounds but does not retain an interior source pointer across a
   bulk push.

## Root Cause

1. `vec_push_bytes` does not classify `src` before any operation that can change `self.arr.data`.
2. `vec_reserve` delegates growth to `arr_resize`, whose `rt_realloc` is allowed to return a different base and release
   the old allocation.
3. The destination is derived from the post-reserve base, but the source remains derived from the pre-reserve base.
4. `rt_memcpy` receives the stale source without pointer-lifetime validation and performs the invalid read.
5. Quarantine changes when the defect becomes observable but does not preserve the source pointer's lifetime.

## Contract for the Fix

1. A positive-count `vec_push_bytes` accepts `src` from an unrelated valid allocation exactly as before.
2. It also accepts `src` at the backing base or at an interior byte when the complete source range is within the
   vector's current logical bytes `[0, length)`.
3. When `src` starts in the backing allocation but the requested range reaches outside the current logical bytes, the
   operation fails its runtime contract before reserve, copy, or length mutation.
4. When a positive source range starts below the backing allocation but crosses into its physical span, the operation
   rejects that unsupported overlap before reserve, copy, or length mutation.
5. `count <= 0` remains a no-op and does not inspect or classify `src`.
6. A successful append preserves source-byte order and updates `length` only after the copy completes.
7. Non-aliasing inputs retain the existing single reserve decision and single bulk copy. The fix must not copy every
   input through temporary storage.
8. Under the supported self-alias contract, the source range ends at or before the old logical length and the append
   destination begins at that length. The rebased ranges therefore do not overlap, so `rt_memcpy` remains valid and a
   new public `rt_memmove` operation is unnecessary.

## Scope of This Fix

1. Add implementation-private shared runtime operations that classify a candidate pointer against a byte span and test
   two byte spans for overlap without dereferencing either pointer or computing potentially wrapping end addresses.
2. Use the operations before reserve to distinguish an unrelated source from a source derived from or crossing into the
   vector backing.
3. Validate a backing-derived source against the old logical length, retain its offset, and reconstruct it from the
   post-reserve base.
4. Apply the same runtime and standard-library behavior to L0 and L1.
5. Add durable growth, no-growth, base-alias, interior-alias, rejection, external-source, checked, unchecked, and
   sanitizer regressions.
6. Document the supported `vec_push_bytes` alias contract in both standard-library references and source comments.

## Implementation Sequence

### Phase 1: Pin the failure and boundary cases

1. Add L1 and L0 subprocess regressions that self-append an entire byte vector while growth is required and verify the
   appended contents and final length.
2. Add interior-source cases, such as appending the middle two bytes of a four-byte vector, with and without growth.
3. Retain an unrelated source allocation as a control so alias handling cannot perturb ordinary bulk appends.
4. Add a contract-failure case for a source that begins in the backing allocation but extends beyond the current logical
   length; verify failure occurs before any copy or successful length update.
5. Add a defensive contract-failure case for a positive source range that begins below the backing span and crosses into
   it, using a valid containing allocation so the range can be represented without invalid pointer arithmetic.
6. Run each semantic case through the default checked and unchecked runtime modes. Reuse the ASan capability-selection
   pattern from the existing L0 and L1 quarantine observability tests. On supported GCC or Clang hosts, require the
   pre-fix checked growth case to report `use-after-poison` and the pre-fix unchecked case to report
   `heap-use-after-free`; both sanitizer variants must exit cleanly after the fix.

### Phase 2: Add the private byte-span primitives

1. Introduce the same private runtime helpers in the L0 header runtime and L1 archive runtime. Give them private `_rt_`
   symbols and narrow contracts: return the candidate's offset within one half-open byte span, and report whether two
   positive half-open byte spans overlap.
2. Implement classification with checked `uintptr_t` differences. Do not form C pointers outside an allocation, compute
   wrapping end addresses, or read through either candidate.
3. Define null, negative-extent, zero-extent, exact-base, interior, exact-end, left-overlap, and disjoint behavior
   explicitly and test it identically in checked, basic, traced, and unchecked runtime builds. Exact-end ranges do not
   overlap, so adjacent unrelated allocations remain external.
4. Add the L1 archive symbols to both manifests and keep the L0 declaration-only header and implementation header
   signatures synchronized where applicable.
5. Keep the helper implementation-private. Do not expose it as a new documented `sys.memory` capability beyond the
   declaration required by the shared standard-library implementation.

### Phase 3: Rebase aliased vector sources

1. In each `vec_push_bytes`, retain the old length and classify `src` against the pre-reserve physical backing span
   before computing a post-growth source pointer. Account for the one-byte physical allocation used when logical
   capacity is zero so an invalid base-derived positive source is rejected before reserve.
2. For a backing-derived source, require `offset < old_length` and `count <= old_length - offset`. Use subtraction-based
   bounds checks so the validation itself cannot overflow.
3. For a source starting outside the backing span, reject a positive source range that overlaps the backing span.
4. Call `vec_reserve` only after alias classification and validation.
5. Reconstruct an aliased source from the new backing base plus the saved offset; leave unrelated sources unchanged.
6. Derive the append destination from the post-reserve base and old logical length, perform one `rt_memcpy`, and publish
   the new length only after the copy.
7. Keep the L0 and L1 implementations mechanically aligned, including assertions, comments, and no-op behavior.

### Phase 4: Document and validate the repaired contract

1. Add `vec_push_bytes` to the L0 and L1 standard-library tables and state that complete logical self-ranges are
   supported across growth while backing-derived non-logical ranges are rejected.
2. Confirm runtime symbol/header checks cover the private helpers without accidentally promoting them as stable public
   API.
3. Run focused normal, trace, unchecked, and sanitizer regressions for both levels.
4. Run the repository-wide trace-inclusive validation because the change affects shared containers, allocation lifetime,
   and all runtime variants.

## Diagnostics

No compiler diagnostic code is added or reassigned. Invalid backing-derived and backing-overlapping ranges remain
runtime contract failures, and valid programs continue to compile with unchanged compiler diagnostics.

## Non-Goals

1. Redesigning `VectorBase`, `ArrayBase`, their layouts, or their allocation-growth policy.
2. Adding generics, borrow checking, or a general lifetime type for raw interior pointers.
3. Supporting copies from unused reserved capacity or otherwise treating non-logical vector storage as initialized
   source data.
4. Adding a public `rt_memmove` API while the supported source and destination ranges are provably non-overlapping.
5. Changing quarantine retention, checked-runtime pointer validation, or `rt_realloc` semantics.
6. Auditing every unrelated `rt_memcpy` caller without separate evidence of an aliasing defect.

## Outcome

- Added the private `_rt_byte_span_offset` and `_rt_byte_spans_overlap` runtime helpers to the L0 header runtime and L1
  archive runtime. They classify exact-base, interior, left-overlap, exact-end, and disjoint ranges with overflow-safe
  `uintptr_t` differences, reject null and non-positive spans, and remain outside the documented public runtime API.
- Updated both shared `vec_push_bytes` implementations to classify and validate aliases before reserve, preserve the
  original byte offset, rebase valid logical sources after growth, copy once, and publish the new length only after the
  copy. Non-positive counts remain no-ops, including for stale source pointers.
- Added matching L0 and L1 coverage for base and interior aliases with and without growth, unrelated sources, zero-count
  calls, non-logical backing ranges, left-overlapping ranges, zero-capacity backing, all runtime modes, and
  checked/unchecked AddressSanitizer builds.
- Updated both standard-library references with the supported logical self-alias contract and its rejection boundary. No
  compiler diagnostics, container layouts, ownership rules, or public runtime APIs changed.

## Verification

- The minimized pre-fix fixture reproduced checked-runtime `use-after-poison` and unchecked-runtime
  `heap-use-after-free` failures under AddressSanitizer. The final checked and unchecked sanitizer fixtures pass for
  both L0 and L1.
- Focused L0 runtime signature and pointer-classification tests passed (`49 passed`); the focused native vector and
  trace suites passed with zero leaks.
- Focused L1 aliasing, pointer-classification, symbol-manifest, native vector, and trace suites passed with zero leaks.
- The defensive left-overlap follow-up passed its checked and unchecked L0/L1 fixtures, the expanded private-helper
  contract tests in all runtime modes, both symbol-manifest variants, and focused native vector traces with zero leaks.
- Root `make clean test-all` passed: L0 passed `1507` Stage 1 tests, `58` Stage 2 suites, all example and workflow
  checks, and `34` trace suites; L1 passed `73` normal suites, environment and example checks, and `45` trace suites.
  The complete gate passed again after the defensive left-overlap follow-up, and every trace suite reported zero leaked
  object and string pointers.
- `python3 scripts/check_adr_impact.py --all-active` and `git diff --check` passed before plan closure.
- Independent read-only review reported no actionable findings after checking the alias contract, pre-reserve logical
  bounds, post-reserve rebasing, zero-capacity handling, L0/L1 parity, private symbol coverage, documentation, and
  tests.
