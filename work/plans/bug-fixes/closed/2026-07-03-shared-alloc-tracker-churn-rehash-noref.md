# Bug Fix Plan

## Shared allocation tracker churn rehash policy

- Date: 2026-07-03
- Status: Completed
- Title: Size allocation-tracker rehashes from the live record count and expose quarantine tunables
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 shared header runtime
  - L1 shared archive runtime
- Origin: Design review of checked runtime pointer access validation for long-running services
- Porting rule: Keep the rehash sizing policy and tunable guards identical across the L0 header runtime and the L1
  archive runtime; environment-variable overrides are L1-only because the archive runtime is prebuilt.
- Target status:
  - L0 shared header runtime: Implemented
  - L1 shared archive runtime: Implemented
- Subsystem: Runtime allocation tracker
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_runtime_alloc_tracker.py`
  - `l1/compiler/stage1_l0/tests/runtime_alloc_tracker_test.py`
- Related:
  - `work/plans/features/closed/2026-06-30-shared-runtime-pointer-access-validation-noref.md`
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
- Repro: rotating-window mixed-size alloc/free churn; see the churn harness in the test modules

## Summary

The checked-mode allocation tracker rebuilt its base-pointer hash table only through an unconditional capacity doubling,
and that doubling was also the only tombstone-purge mechanism. Under sustained alloc/free churn with a stable live
count, tombstones repeatedly reached the purge threshold and each purge doubled the table, so table capacity grew
roughly linearly with the lifetime number of frees. Long-running services with millions of small allocations and
deallocations saw unbounded slot-array growth and ever-larger rehash pauses.

The fix sizes every rehash from the live record count: the new capacity is the smallest power of two at or above twice
the live count, floored at the initial capacity. A tombstone-triggered rebuild now purges tombstones at a stable or
smaller capacity, and a shrunken live set lets the table contract.

The quarantine limits and pool constants also become tunable: the `_RT_QUARANTINE_MAX_BYTES`,
`_RT_QUARANTINE_MAX_COUNT`, `_RT_ALLOC_INIT_CAP`, and `_RT_REC_POOL_CHUNK` defines gained `#ifndef` guards in both
runtimes, and the L1 archive runtime additionally reads `DEA_RT_QUARANTINE_MAX_BYTES` and `DEA_RT_QUARANTINE_MAX_COUNT`
from the environment once at first tracker use, because the archive cannot be recompiled per application.

## Root Cause

The table rebuild helper computed its new capacity from the old capacity (`old_cap * 2`) instead of from the live record
count. Both rebuild triggers (insert load factor above 0.7 counting tombstones, and tombstones above half the capacity)
therefore always doubled. Uniform-size immediate-free churn masks the problem because the C allocator returns the same
address and each insert reclaims the tombstone its own address left behind; mixed sizes over a rotating live window
diversify addresses and reproduce the ratcheting.

## Scope of This Fix

In scope:

1. Live-count-based rehash sizing in both runtimes.
2. `#ifndef` guards for the tracker and quarantine tunables in both runtimes.
3. One-time environment overrides for the quarantine limits in the L1 archive runtime.
4. White-box churn regression tests for both runtimes.

Not in scope:

1. Reducing the per-operation cost of allocation tracking (treap participation, record layout, lazy ARC string
   registration); those are follow-up performance work.
2. Surfacing the unchecked or tuned modes as first-class driver flags.
3. Thread safety of the tracker.

## Outcome

A rotating-window mixed-size churn workload of one million alloc/free pairs with a 4096-slot live window previously
ratcheted the table to 524288 slots and kept growing; with the fix the table stabilizes at 16384 slots for the same
workload. Both runtimes now behave identically, and the new churn tests fail against the previous doubling policy.

Microbenchmarks with the guards in place show `_RT_QUARANTINE_MAX_COUNT` is the main tunable for tight alloc/free loops:
disabling retention (`0`) cut a five-million-pair tight loop from about 1.34 s to about 0.34 s, and `256` cut it to
about 0.89 s, while steady-window churn stayed near 1.0 s for all retention settings because tracker insert/remove
dominates there. The triple bootstrap is unaffected by this fix (its live set grows mostly monotonically), so the
checked-mode bootstrap slowdown remains follow-up performance work.

## Verification

Completed verification:

1. `../.venv/bin/python -m pytest -q l0/compiler/stage1_py/tests/backend/test_runtime_alloc_tracker.py`
2. `cd l1 && L1_BUILD_DIR=build/dea ../.venv/bin/python compiler/stage1_l0/scripts/run_tests.py`
3. Targeted L0 pointer-validation, trace-memory, and lvalue-caching backend suites.
4. `make -C l0 triple-test` (wall time unchanged against the pre-fix baseline).
5. `make -C l0 test-all` and `make -C l1 test-all`.
