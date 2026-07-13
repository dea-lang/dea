# Bug Fix Plan

## Shared checked-runtime table contraction and C99 alignment portability

- Date: 2026-07-13
- Status: Completed
- Title: Restore checked allocation-table contraction and strict C99 alignment portability
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 shared header runtime and Stage 2 bootstrap
  - L1 shared archive runtime and public header
- Origin: Unified CI failures after integrating checked-runtime validation and allocation-tracker work
- Porting rule: Keep the table contraction policy and alignment macro selection equivalent across the L0 and L1
  runtimes, with only level-specific names.
- Target status:
  - L0 shared header runtime and Stage 2 bootstrap: Implemented
  - L1 shared archive runtime and public header: Implemented
- Subsystem: Checked runtime allocation tracking and generated C portability
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l0/compiler/stage1_py/tests/conftest.py`
  - `l0/scripts/bench_runtime_harness.c`
  - `l0/docs/reference/design-decisions.md`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l1/scripts/bench_runtime_harness.c`
  - `l1/docs/reference/standard-library.md`
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_runtime_alloc_tracker.py`
  - `l1/compiler/stage1_l0/tests/runtime_alloc_tracker_test.py`
- Related:
  - `work/plans/bug-fixes/closed/2026-07-03-shared-alloc-tracker-churn-rehash-noref.md`
  - `work/plans/features/closed/2026-07-04-shared-runtime-alloc-benchmark-noref.md`
  - `work/plans/bug-fixes/closed/2026-07-11-shared-checked-runtime-review-gaps-noref.md`
  - `work/plans/bug-fixes/closed/2026-07-11-shared-ci-platform-portability-regressions-noref.md`
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
- Repro: Unified CI run 29282843917, the focused ramp memory-invariant tests, and an L0 Stage 2 build with Apple Clang
  17

## Summary

The integrated checked-runtime changes expose two defects across the shared runtime implementations. Allocation-table
rehashing is sized correctly from the live record count, but removal only requests a rebuild after tombstones exceed
half the current capacity. A large live set can therefore fall sharply without reaching that tombstone threshold,
leaving a peak-sized table behind. Generated checked pointer accesses also use `_RT_ALIGNOF`; its C99 fallback defines
an anonymous structure inside `offsetof`, which Apple Clang 17 rejects under the compiler driver's strict
`-pedantic-errors` policy.

## Root Cause

The tracker has a tombstone-pressure rebuild trigger but no independent low-live-count contraction trigger. The ramp
workload grows the table to 262144 slots, then retains too few tombstones to request a rebuild as the live count falls
back near the bounded quarantine.

The shared alignment macro always uses an anonymous `offsetof` probe even on GCC-compatible compilers that provide a
direct type-alignment builtin. Clang classifies the anonymous type in `offsetof` as a C23 extension, so a valid Stage 2
bootstrap fails when warnings are promoted to errors.

## Scope of This Fix

1. Add a hysteretic low-live-count rebuild trigger to both allocation trackers while retaining the existing tombstone
   purge trigger.
2. Select the GCC/Clang type-alignment builtin in both runtime headers and retain the existing override and fallback
   behavior for other compilers.
3. Keep the existing cross-level ramp and churn invariants as regression coverage, and verify strict Stage 2 and L1
   generated-C builds.

## Non-Goals

- Changing quarantine limits or allocation-record pool retention.
- Changing pointer-validation semantics or generated access shapes.
- Introducing new diagnostics or compiler options.

## Verification Criteria

- The L0 and L1 ramp scenarios contract from the peak table capacity to at most 32768 slots.
- Existing churn, quarantine, and checked-runtime tests pass in both levels.
- L0 Stage 2 builds with Apple Clang 17 under strict C99 flags without `offsetof` extension diagnostics.
- L1 runtime and generated checked code build with the same alignment policy.
- Full relevant L0 and L1 validation completes without new failures.

## Outcome

- Both allocation trackers now rebuild when tombstones exceed half the slot array or when a non-minimum table falls
  below one-quarter live occupancy. Rehashing targets approximately one-half occupancy, preserving hysteresis against
  the existing 70 percent growth threshold.
- Both runtime headers use the GCC/Clang type-alignment builtin under those compilers and a strict-C99 size-difference
  probe elsewhere. TinyCC exercises the fallback, while Apple Clang no longer diagnoses an anonymous type inside
  `offsetof`.
- Both ramp harnesses expose table capacity immediately after free-all, and both tracker suites assert contraction
  before allocator-dependent settle churn. L0 also compiles a focused alignment harness with strict C99 diagnostics.
- Live reference docs and ADR-0010 now distinguish peak-driven record-pool retention from live-count-sized table
  capacity.

## Verification

- `env L0_CC=clang ../.venv/bin/pytest -q compiler/stage1_py/tests/backend/test_runtime_alloc_tracker.py` from `l0/`: 7
  passed.
- The same L0 tracker suite with `L0_CC=tcc`: 7 passed.
- `env L1_CC=clang ../.venv/bin/python compiler/stage1_l0/tests/runtime_alloc_tracker_test.py` from `l1/`: passed.
- The same L1 tracker script with `L1_CC=tcc`: passed.
- L0 Stage 2 artifact builds with Apple Clang 17 and TinyCC: passed.
- Root `make test-all`: passed, including 1327 L0 Stage 1 tests, 54 L0 Stage 2 tests, 33 L0 trace checks, 51 L1 Stage 1
  tests, 37 L1 trace checks, workflow tests, and all registered examples.
- Root pre-commit copyright and Markdown formatting hooks: passed.
- `git diff --check`: passed.
