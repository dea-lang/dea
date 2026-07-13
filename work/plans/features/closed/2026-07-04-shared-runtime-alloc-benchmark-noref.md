# Feature Plan

## Shared runtime allocation tracker benchmark

- Date: 2026-07-04
- Status: Completed
- Title: Memory-invariant suite tests and a `bench-runtime` tuning benchmark for the checked allocation tracker
- Kind: Feature
- Severity: Medium
- Stage: Shared
- Subsystem: Runtime allocation tracker, test suites, make workflow
- Scope: Shared
- Targets:
  - L0 shared header runtime and Stage 1 test suite
  - L1 shared archive runtime and Stage 1 test suite
- Origin: The `_RT_QUARANTINE_MAX_COUNT` default (4096) was chosen without measurement
- Porting rule: Keep harness scenarios, printed metrics, and invariant bounds identical across the level harnesses; L1
  sweeps retention through the environment overrides while L0 compiles one binary per setting.
- Target status:
  - L0 shared header runtime and Stage 1 test suite: Done
  - L1 shared archive runtime and Stage 1 test suite: Done
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l0/scripts/bench_runtime_harness.c`
  - `l0/scripts/bench_runtime.py`
  - `l1/scripts/bench_runtime_harness.c`
  - `l1/scripts/bench_runtime.py`
  - `l0/Makefile`
  - `l1/Makefile`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_runtime_alloc_tracker.py`
  - `l1/compiler/stage1_l0/tests/runtime_alloc_tracker_test.py`
- Related:
  - `work/plans/bug-fixes/closed/2026-07-03-shared-alloc-tracker-churn-rehash-noref.md`
  - `work/plans/features/closed/2026-07-04-shared-unchecked-build-surface-noref.md`
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`

## Summary

The checked-runtime quarantine retention default is the dominant tunable for allocation-heavy code and the entire
temporal-detection window for small allocations, but it was never measured, and no workload in the suite exercised the
tracker under a large live set. This plan adds a white-box benchmark harness per level with four scenarios (tight churn,
mixed-size window churn with large blocks, a memory-intensive ramp, and string churn), wires deterministic
memory-invariant checks into the official test suites, and adds `make bench-runtime` targets that print a compiler x
retention-setting matrix (tcc, clang, gcc-16) as the data for a follow-up decision on the default.

## Shared Design

- One `static size_t _rt_rec_pool_chunks` counter in each runtime's record-pool refill makes peak record memory exactly
  observable (`chunks * _RT_REC_POOL_CHUNK * sizeof(_rt_alloc_record)`); pool memory is never freed, so the counter is
  monotone and deterministic.
- The harnesses include the runtime white-box (header include for L0; compilation-unit includes for L1) and print
  `scenario.key=value` metrics: wall times, `ru_maxrss` (normalized to KiB), table capacity, live count, quarantine
  bytes/count with in-loop peaks, and record-pool chunks. Scenario and scale come from argv or defines.
- Suite integration asserts only deterministic tracker-internal bounds at scale 1 (about 100k peak live records, seconds
  of runtime): live-count-sized table capacity, both quarantine caps at every post-operation sample point (the window
  scenario's periodic large blocks make the byte cap bind), the record-pool ceiling, and post-free-all contraction.
  Wall-clock is never asserted.
- The ramp settle phase and the window workload use mixed sizes deliberately: uniform sizes let the C allocator return
  the same address each iteration, which reclaims the same tombstone and masks tracker behavior.
- `make bench-runtime` (both levels) drives `scripts/bench_runtime.py`: `BENCH_CC` selects compilers (default: those of
  tcc, clang, gcc-16 on `PATH`), `BENCH_SCALE`/`BENCH_RUNS` control effort, and the checked retention matrix covers
  `{0, 256, 1024, 4096, 16384, 65536}` plus an unchecked baseline. Informational only; not part of `test-all`.

## Non-Goals

- No wall-clock assertions in any suite test.
- No change to the `_RT_QUARANTINE_MAX_COUNT` default in this plan; the decision is a follow-up informed by the recorded
  matrix.
- No cross-machine benchmark result tracking.

## Completion Notes

Completed on 2026-07-04.

> **Correction (2026-07-11):** The performance timings below used process CPU `clock()` and allowed optimized unchecked
> allocation/string loops to disappear, so they are not valid wall-time evidence. The deterministic tracker-memory
> observations remain historical. Corrected monotonic, anti-elision matrices are recorded in
> [work/plans/bug-fixes/closed/2026-07-11-shared-checked-runtime-review-gaps-noref.md](../../bug-fixes/closed/2026-07-11-shared-checked-runtime-review-gaps-noref.md).

Measured matrix on the macOS x86_64 development host (`make bench-runtime`, scale 5, best of 3, wall ms; scenarios: 5M
tight pairs, 2.5M window ops, 500k-live ramp, 5M string pairs). L0 header-runtime table shown; the L1 archive runtime
matched it within run-to-run noise for every cell, as expected for copied runtime code.

| Compiler | Setting   | tight | window | ramp | strings | ramp RSS MiB |
| -------- | --------- | ----- | ------ | ---- | ------- | ------------ |
| tcc      | unchecked | 368   | 591    | 497  | 499     | 248          |
| tcc      | 0         | 1049  | 2813   | 1279 | 524     | 325          |
| tcc      | 256       | 2612  | 2749   | 1863 | 515     | 325          |
| tcc      | 1024      | 3262  | 3034   | 1914 | 515     | 325          |
| tcc      | 4096      | 3324  | 3290   | 2127 | 516     | 325          |
| tcc      | 16384     | 3751  | 3075   | 2212 | 514     | 325          |
| tcc      | 65536     | 4044  | 3162   | 2337 | 510     | 325          |
| clang    | unchecked | ~0    | 490    | 302  | ~0      | 59           |
| clang    | 0         | 473   | 1689   | 920  | 303     | 125          |
| clang    | 256       | 1324  | 1594   | 1257 | 305     | 136          |
| clang    | 1024      | 1819  | 1723   | 1309 | 304     | 145          |
| clang    | 4096      | 1914  | 2137   | 1417 | 310     | 146          |
| clang    | 16384     | 2176  | 1961   | 1570 | 313     | 145          |
| clang    | 65536     | 2350  | 1940   | 1694 | 301     | 137          |
| gcc-16   | unchecked | ~0    | 481    | 315  | ~0      | 82           |
| gcc-16   | 0         | 490   | 1648   | 933  | 311     | 148          |
| gcc-16   | 256       | 1253  | 1543   | 1236 | 314     | 140          |
| gcc-16   | 1024      | 1739  | 1669   | 1300 | 312     | 156          |
| gcc-16   | 4096      | 1894  | 1961   | 1444 | 312     | 147          |
| gcc-16   | 16384     | 2085  | 2688   | 1610 | 314     | 138          |
| gcc-16   | 65536     | 2366  | 1934   | 1652 | 311     | 144          |

Findings for the retention-default follow-up:

- The ordering is identical across tcc, clang, and gcc-16 and across both levels: retention `0` runs tight churn about
  4x faster than the `4096` default; `256` recovers roughly half the overhead; `1024` is nearly indistinguishable from
  `4096`; larger settings degrade further. The meaningful perf step is between `256` and `0`.
- Window churn moves about 20-25 percent between `4096` and `0`/`256`; string churn is flat at every setting because
  lazily registered ARC storage never enters the tracker.
- Checked-mode ramp RSS is retention-independent and sits 50-90 MiB above unchecked at 500k live blocks, dominated by
  the never-freed record pool (1954 chunks of 256 records) plus the 1M-slot table, matching the peak-driven design.
- The tradeoff to decide: `4096` buys a 4096-free temporal-detection window for about 3.8x tight-churn cost over `0`;
  `256` keeps a small window at about 1.4x the cost of `0`. Clang `~0` cells are loop elision of untracked malloc/free
  pairs, not real time.

## Verification Criteria

- The new invariant checks pass in both suites and run in seconds.
- `make -C l0 bench-runtime` and `make -C l1 bench-runtime` print the full matrix for tcc, clang, and gcc-16.
- Full `make -C l0 test-all` and `make -C l1 test-all` pass.
