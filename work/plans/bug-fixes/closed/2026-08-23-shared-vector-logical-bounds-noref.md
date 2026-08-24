# Bug Fix Plan

## Enforce logical bounds for shared vectors and compiler token access

- Date: 2026-08-25
- Status: Completed
- Title: Check vector length rather than reserved capacity in shared L0 and L1 containers
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 shared stdlib and L0 Stage 2 token vectors
  - L1 shared stdlib and L1 Stage 1 token vectors
- Origin: Settle the logical-bound contract in `l0/compiler/shared/l0/stdlib/std/vector.l0`, then port it mechanically
  to the seeded L1 stdlib.
- Porting rule: Keep L0 and L1 `VectorBase` bounds behavior identical; compiler token-vector tests must exercise the
  public vector invariant rather than add target-specific capacity checks.
- Target status:
  - L0 shared stdlib and L0 Stage 2 token vectors: Completed
  - L1 shared stdlib and L1 Stage 1 token vectors: Completed
- Subsystem: Standard library containers / Compiler token storage / Runtime safety
- Modules:
  - `l0/compiler/shared/l0/stdlib/std/vector.l0`
  - `l0/compiler/shared/l0/stdlib/std/array.l0`
  - `l0/compiler/shared/l0/stdlib/std/text.l0`
  - `l0/compiler/stage2_l0/src/tokens.l0`
  - `l1/compiler/shared/l1/stdlib/std/vector.l1`
  - `l1/compiler/shared/l1/stdlib/std/array.l1`
  - `l1/compiler/shared/l1/stdlib/std/text.l1`
  - `l1/compiler/stage1_l0/src/tokens.l0`
- Test modules:
  - `l0/compiler/stage2_l0/tests/vector_test.l0`
  - `l0/compiler/stage2_l0/tests/lexer_test.l0`
  - `l0/compiler/stage2_l0/tests/util_text_test.l0`
  - `l0/compiler/stage2_l0/tests/vector_logical_bounds_test.py`
  - `l1/compiler/stage1_l0/tests/vector_test.l0`
  - `l1/compiler/stage1_l0/tests/lexer_test.l0`
  - `l1/compiler/stage1_l0/tests/util_text_test.l0`
  - `l1/compiler/stage1_l0/tests/vector_logical_bounds_test.py`
- Related:
  - `l0/docs/reference/standard-library.md`
  - `l1/docs/reference/standard-library.md`
- Repro: Reserve a vector capacity greater than its logical length, then call `vec_check`, `vec_get`, or `tv_get` at
  `index == length`; the current check accepts the reserved but uninitialized slot.

## Summary

`VectorBase` documents `vec_check()` as a logical-bounds check, but the implementation delegates to `arr_check()`, which
checks the backing array capacity. After a reserve or geometric growth, indices from `length` through `capacity - 1` are
therefore accepted even though they are not vector elements.

Both native compilers inherit the defect through `tv_get()`. The L0 Python compiler does not use `VectorBase`
internally, but L0 programs it compiles still receive the affected L0 stdlib. L1 programs receive an identical L1 stdlib
copy.

## ADR Impact

- Decision: Enforce the already documented distinction between vector length and backing-array capacity.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This is a direct container-contract correction with no change to the public API, memory layout, or
    language semantics.

## Current State and Root Cause

1. `vec_grow()` increments `VectorBase.length` and expands the backing array only when capacity is exhausted.
2. `vec_reserve()` can increase capacity without changing length.
3. `vec_check()` calls `arr_check(self.arr, index)`, whose upper bound is `self.arr.capacity`.
4. `vec_get()` delegates directly to `arr_get()`, so compiler-specific wrappers such as `tv_get()` do not restore the
   missing logical check.
5. Zero-filled reserved storage can make an invalid token access appear superficially valid and defer failure into
   parser or analyzer logic.

## Scope of This Fix

1. Make public vector element access reject every index outside `[0, length)`.
2. Preserve explicit capacity operations for allocation management without exposing reserved slots as elements.
3. Audit internal vector algorithms that write the newly grown slot and confirm they remain within the updated contract.
4. Add compiler token-vector regressions for empty, partially filled, cleared, and over-reserved vectors.
5. Port the settled container and tests to the L1 stdlib and L1 Stage 1 compiler.
6. Refresh standard-library documentation only if it currently describes behavior inconsistent with the corrected
   implementation.

## Diagnostics

No compiler diagnostic code is introduced. Invalid vector access remains an assertion/runtime-contract failure; the fix
makes that failure occur at the correct logical boundary.

## Non-Goals

1. Redesigning `VectorBase`, changing its ABI, or adding generics.
2. Making raw backing-array access available through the public vector API.
3. Auditing unrelated container implementations unless focused tests expose the same length/capacity confusion.

## Verification

1. Extend both `vector_test.l0` suites with reserved-capacity, clear, negative-index, and `index == length` cases.
2. Add direct `TokenVector` coverage proving `tv_get()` rejects a physical reserved slot.
3. Run focused L0 Stage 2 and L1 Stage 1 vector, lexer, parser, and trace tests.
4. Run `make test-all` from the repository root because the affected containers are ownership- and runtime-sensitive.

## Verification Criteria

1. `vec_check()` and `vec_get()` accept exactly the logical element range.
2. `vec_push()` and internal sort/move operations continue to access the newly grown logical slot safely.
3. Both native compilers fail deterministically at the token-vector boundary instead of reading zero-filled capacity.
4. L0 and L1 stdlib implementations remain behaviorally aligned.

## Implementation Outcome

1. `vec_check()` now enforces the exact logical range `[0, length)` in both shared stdlibs, and `vec_get()` plus
   `vec_zap()` route all public element access through that invariant while `ArrayBase` retains capacity bounds.
2. Both compiler `tv_get()` wrappers now inherit the shared public-vector check directly from `vec_get()` instead of
   duplicating target-specific checks.
3. Reserve, grow, push, sort, and linear-map removal callers were audited; newly grown slots become logical before
   access, and removal paths zap their final logical slot before decrementing length.
4. The audit exposed one intentional empty-buffer capacity access in `cb_to_string()`. Empty and cleared char buffers
   now return `""` before requesting element zero, while non-empty conversion continues through logical vector access.

## Verification Outcome

1. Focused L0 Stage 2 and L1 Stage 1 vector, lexer, parser, and text suites passed in normal and ARC/memory trace modes.
2. New auto-discovered subprocess regressions prove deterministic runtime rejection for empty, negative,
   `index == length`, cleared, over-reserved, and zap access, plus direct empty, partially filled, cleared, and
   over-reserved `TokenVector` access in both compiler trees.
3. Repository-root `make test-all` passed: 1,472 L0 Python tests, all 56 L0 Stage 2 tests, triple bootstrap, eight L0
   examples, workflow/distribution checks, all 33 L0 trace tests, all 68 L1 Stage 1 tests, environment stackability,
   four L1 examples, and all 44 default L1 trace tests.
4. The independent read-only review audited the complete diff, relevant callers, test discovery, L0/L1 parity, and the
   empty-buffer compatibility path and reported no actionable findings.
