# Bug Fix Plan

## Make bulk byte-vector pushes safe for backing-store aliases

- Date: 2026-09-01
- Status: Draft
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
  - L0 shared standard library and header runtime: Pending
  - L1 shared standard library and archive runtime: Pending
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
4. `count <= 0` remains a no-op and does not inspect or classify `src`.
5. A successful append preserves source-byte order and updates `length` only after the copy completes.
6. Non-aliasing inputs retain the existing single reserve decision and single bulk copy. The fix must not copy every
   input through temporary storage.
7. Under the supported self-alias contract, the source range ends at or before the old logical length and the append
   destination begins at that length. The rebased ranges therefore do not overlap, so `rt_memcpy` remains valid and a
   new public `rt_memmove` operation is unnecessary.

## Scope of This Fix

1. Add one implementation-private shared runtime operation that classifies a candidate pointer against a byte span and
   returns its byte offset without dereferencing the candidate.
2. Use the operation before reserve to distinguish an unrelated source from a source derived from the vector backing.
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
5. Run each semantic case through the default checked and unchecked runtime modes. Reuse the ASan capability-selection
   pattern from the existing L0 and L1 quarantine observability tests. On supported GCC or Clang hosts, require the
   pre-fix checked growth case to report `use-after-poison` and the pre-fix unchecked case to report
   `heap-use-after-free`; both sanitizer variants must exit cleanly after the fix.

### Phase 2: Add the private byte-offset primitive

1. Introduce the same private runtime helper in the L0 header runtime and L1 archive runtime. Give it a private `_rt_`
   symbol and a narrow contract: return the candidate's offset when it is within a supplied half-open byte span;
   otherwise return the non-alias sentinel.
2. Implement classification with checked `uintptr_t` arithmetic. Do not form C pointers outside an allocation and do not
   read through the candidate.
3. Define null, negative-extent, zero-extent, exact-base, interior, exact-end, and disjoint behavior explicitly and test
   it identically in checked, basic, traced, and unchecked runtime builds. Exact-end pointers are outside the half-open
   span so an adjacent unrelated allocation cannot be misclassified as an alias.
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
3. Call `vec_reserve` only after alias classification and validation.
4. Reconstruct an aliased source from the new backing base plus the saved offset; leave unrelated sources unchanged.
5. Derive the append destination from the post-reserve base and old logical length, perform one `rt_memcpy`, and publish
   the new length only after the copy.
6. Keep the L0 and L1 implementations mechanically aligned, including assertions, comments, and no-op behavior.

### Phase 4: Document and validate the repaired contract

1. Add `vec_push_bytes` to the L0 and L1 standard-library tables and state that complete logical self-ranges are
   supported across growth while backing-derived non-logical ranges are rejected.
2. Confirm runtime symbol/header checks cover the private helper without accidentally promoting it as a stable public
   API.
3. Run focused normal, trace, unchecked, and sanitizer regressions for both levels.
4. Run the repository-wide trace-inclusive validation because the change affects shared containers, allocation lifetime,
   and all runtime variants.

## Diagnostics

No compiler diagnostic code is added or reassigned. Invalid backing-derived ranges remain runtime contract failures, and
valid programs continue to compile with unchanged compiler diagnostics.

## Non-Goals

1. Redesigning `VectorBase`, `ArrayBase`, their layouts, or their allocation-growth policy.
2. Adding generics, borrow checking, or a general lifetime type for raw interior pointers.
3. Supporting copies from unused reserved capacity or otherwise treating non-logical vector storage as initialized
   source data.
4. Adding a public `rt_memmove` API while the supported source and destination ranges are provably non-overlapping.
5. Changing quarantine retention, checked-runtime pointer validation, or `rt_realloc` semantics.
6. Auditing every unrelated `rt_memcpy` caller without separate evidence of an aliasing defect.

## Verification

Focused checks:

```bash
../.venv/bin/python -m pytest -q l0/compiler/stage1_py/tests/backend/test_runtime_pointer_validation.py l0/compiler/stage1_py/tests/backend/test_runtime_public_header.py
make -C l0 test-stage2 TESTS="vector_test vector_aliasing_test.py"
make -C l0 test-stage2-trace TESTS="vector_test"
make -C l1 test-stage1 TESTS="vector_aliasing_test.py runtime_pointer_validation_test.py runtime_symbol_manifest_test.py"
make -C l1 test-stage1-trace TESTS="vector_test"
python3 scripts/check_adr_impact.py --all-active
```

Full gate:

```bash
make test-all
```

The new subprocess regressions must themselves exercise checked, unchecked, checked-plus-AddressSanitizer, and
unchecked-plus-AddressSanitizer program variants. Sanitizer execution may skip only when the host has no compatible GCC
or Clang toolchain, and the skip must report that reason.

## Verification Criteria

1. Growth-triggering base and interior self-appends preserve the exact pre-growth bytes in both L0 and L1.
2. Equivalent no-growth self-appends produce the same result without undefined overlap behavior.
3. A backing-derived range outside the old logical length is rejected before reserve or copy.
4. External-source bulk pushes preserve their one-reserve, one-copy behavior.
5. Default checked and unchecked fixtures plus sanitizer-backed checked and unchecked fixtures all pass;
   AddressSanitizer reports no invalid read, use-after-poison, use-after-free, or overlap violation.
6. L0 and L1 runtime helper semantics, vector assertions, and source comments remain aligned.
7. L1 normal, traced, basic, and unchecked runtime archives export the expected symbol set.
8. The standard-library references describe the repaired alias contract without claiming spare-capacity bytes are
   logical elements.
9. Full L0 and L1 normal and trace validation passes.
