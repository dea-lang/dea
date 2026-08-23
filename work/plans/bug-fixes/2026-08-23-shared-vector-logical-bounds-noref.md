# Bug Fix Plan

## Enforce logical bounds for shared vectors and compiler token access

- Date: 2026-08-23
- Status: Draft
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
  - L0 shared stdlib and L0 Stage 2 token vectors: Pending
  - L1 shared stdlib and L1 Stage 1 token vectors: Pending
- Subsystem: Standard library containers / Compiler token storage / Runtime safety
- Modules:
  - `l0/compiler/shared/l0/stdlib/std/vector.l0`
  - `l0/compiler/shared/l0/stdlib/std/array.l0`
  - `l0/compiler/stage2_l0/src/tokens.l0`
  - `l1/compiler/shared/l1/stdlib/std/vector.l1`
  - `l1/compiler/shared/l1/stdlib/std/array.l1`
  - `l1/compiler/stage1_l0/src/tokens.l0`
- Test modules:
  - `l0/compiler/stage2_l0/tests/vector_test.l0`
  - `l0/compiler/stage2_l0/tests/lexer_test.l0`
  - `l1/compiler/stage1_l0/tests/vector_test.l0`
  - `l1/compiler/stage1_l0/tests/lexer_test.l0`
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
