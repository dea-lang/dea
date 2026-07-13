# Feature Plan

## Shared allocation record hot/cold split

- Date: 2026-07-07
- Status: Completed
- Title: Hot/cold split for checked-runtime allocation records
- Kind: Feature
- Severity: Medium
- Stage: Shared
- Subsystem: Runtime pointer validation, allocation tracker, benchmark harnesses
- Scope: Shared
- Targets:
  - L0 shared header runtime
  - L1 shared archive runtime
- Origin: The 2026-07-03 pointer-validation performance review identified cache-line straddling in `_rt_alloc_record`
- Porting rule: Keep the hot struct layout, cold helper names, compile-time size assert, pool refill behavior,
  moved-field access pattern, and benchmark size metrics mechanically identical across the L0 and L1 runtimes.
- Target status:
  - L0 shared header runtime: Done
  - L1 shared archive runtime: Done
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l0/scripts/bench_runtime_harness.c`
  - `l0/scripts/bench_runtime.py`
  - `l1/scripts/bench_runtime_harness.c`
  - `l1/scripts/bench_runtime.py`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_runtime_pointer_validation.py`
  - `l0/compiler/stage1_py/tests/backend/test_runtime_alloc_tracker.py`
  - `l0/compiler/stage2_l0/tests/l0c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/runtime_alloc_tracker_test.py`
- Related:
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
  - `work/plans/features/closed/2026-07-04-shared-runtime-alloc-benchmark-noref.md`

## Summary

Checked-mode pointer validation stores every allocation in `_rt_alloc_record`. The pointer-check cache-hit path reads
only `base`, `size`, `generation`, `state`, and `read_only`, but allocation tracker churn also repeatedly reads and
writes treap links, free-list links, quarantine links, priorities, and memory kind. The original 112-byte record stride
means most records straddle cache lines when pool chunks come from plain `malloc`. This plan splits the allocation
record into a 64-byte tracker-hot record and a cold companion reached through a stable 32-bit index. Fast-path
declarations and generated-code surfaces stay unchanged.

## Current State

- `_rt_ptr_site`, allocation hash tables, treap roots, free-list heads, and quarantine heads point at
  `_rt_alloc_record`.
- Pointer-check cache hits read only hot validation fields, while allocation, drop, quarantine, and treap mutation paths
  read additional tracker-hot fields.
- The old monolithic struct also carried diagnostic file/line data, type information, and alignment metadata that are
  cold outside panic formatting and `rt_realloc` metadata preservation.
- Runtime pool chunks are never freed, and tests assert deterministic pool chunk bounds rather than a concrete record
  byte size.

## Design

- Keep the hot struct name `_rt_alloc_record`.
- Store `base`, `size`, `generation`, `tree_left`, `tree_right`, `q_next`, `tree_prio`, `cold_index`, `state`,
  `read_only`, and `mem_kind` in the hot struct.
- Explicitly pad and assert `sizeof(_rt_alloc_record) == 64` with a C99-compatible typedef assert.
- Allocate hot chunks with a 64-byte-aligned base using pointer arithmetic over a `malloc` raw pointer.
- Add `_rt_alloc_record_cold` for `align`, `type_id`, `alloc_line`, `drop_line`, `reserved`, `alloc_file`, and
  `drop_file`.
- Add `_rt_cold_chunks` and `_rt_rec_cold(rec)` in each runtime.
- Assign `cold_index` permanently at pool-refill time, preserving free-list recycling and quarantine behavior.
- Keep free-list, quarantine-link, treap, and `mem_kind` access direct on `_rt_alloc_record`; route only diagnostics and
  rare realloc metadata through `_rt_rec_cold(rec)->field`.
- Print `sizeof(_rt_alloc_record)` and `sizeof(_rt_alloc_record_cold)` from both benchmark harnesses, and surface parsed
  values in both benchmark tables.
- Add a cached pointer-check benchmark scenario that warms one `_rt_ptr_site` per live allocation, then times only
  cache-hit validation sweeps.

## Non-Goals

- No generated-code, helper signature, compiler driver, or emitter changes.
- No compiler diagnostic-code changes.
- No ADR-0010 amendment; this is an internal runtime layout change with unchanged pointer-validation semantics.
- No change to quarantine policy, hash-table behavior, treap algorithms, or free-list discipline.

## Baseline Measurements

> **Correction (2026-07-11):** The benchmark timings in this plan used process CPU `clock()` and allowed optimized
> unchecked allocation/string loops to disappear. Timing comparisons in this section are therefore not valid wall-time
> evidence; layout and deterministic tracker-memory observations remain historical. Corrected monotonic, anti-elision
> matrices are recorded in
> [work/plans/bug-fixes/closed/2026-07-11-shared-checked-runtime-review-gaps-noref.md](../../bug-fixes/closed/2026-07-11-shared-checked-runtime-review-gaps-noref.md).

Baseline captured on 2026-07-07 before source edits. Commands:

- `make -C l0 bench-runtime`
- `make -C l1 bench-runtime`
- `/usr/bin/time -p make -C l0 triple-test`

L0 benchmark baseline (`scale=5`, `runs=3`, wall ms, best of 3):

| Compiler | Setting   | tight | window | ramp | strings | ramp RSS MiB | rampCap | chunks |
| -------- | --------- | ----- | ------ | ---- | ------- | ------------ | ------- | ------ |
| tcc      | unchecked | 241   | 388    | 359  | 331     | 248.5        | 0       | 0      |
| tcc      | 0         | 742   | 2248   | 1049 | 335     | 324.7        | 1048576 | 1954   |
| tcc      | 256       | 2111  | 2135   | 1465 | 332     | 324.8        | 1048576 | 1954   |
| tcc      | 1024      | 2189  | 1829   | 1432 | 344     | 324.7        | 1048576 | 1954   |
| tcc      | 4096      | 2630  | 2936   | 1508 | 342     | 324.8        | 1048576 | 1954   |
| tcc      | 16384     | 2484  | 1821   | 1603 | 335     | 324.8        | 1048576 | 1954   |
| tcc      | 65536     | 2775  | 1789   | 1583 | 329     | 324.4        | 1048576 | 1954   |
| clang    | unchecked | 0     | 311    | 221  | 0       | 61.2         | 0       | 0      |
| clang    | 0         | 297   | 1020   | 737  | 194     | 148.4        | 1048576 | 1954   |
| clang    | 256       | 839   | 1010   | 927  | 198     | 132.0        | 1048576 | 1954   |
| clang    | 1024      | 1160  | 1029   | 972  | 193     | 129.8        | 1048576 | 1954   |
| clang    | 4096      | 1207  | 1171   | 1051 | 200     | 128.0        | 1048576 | 1954   |
| clang    | 16384     | 1384  | 1211   | 1117 | 200     | 142.0        | 1048576 | 1954   |
| clang    | 65536     | 1516  | 1230   | 1260 | 200     | 134.3        | 1048576 | 1954   |
| gcc-16   | unchecked | 0     | 308    | 206  | 0       | 75.0         | 0       | 0      |
| gcc-16   | 0         | 315   | 1073   | 731  | 201     | 123.3        | 1048576 | 1954   |
| gcc-16   | 256       | 795   | 1022   | 909  | 206     | 138.7        | 1048576 | 1954   |
| gcc-16   | 1024      | 1138  | 1032   | 959  | 206     | 133.9        | 1048576 | 1954   |
| gcc-16   | 4096      | 1195  | 1177   | 1028 | 202     | 124.1        | 1048576 | 1954   |
| gcc-16   | 16384     | 1328  | 1185   | 1114 | 203     | 123.8        | 1048576 | 1954   |
| gcc-16   | 65536     | 1549  | 1169   | 1192 | 205     | 151.9        | 1048576 | 1954   |

L1 benchmark baseline (`scale=5`, `runs=3`, wall ms, best of 3):

| Compiler | Setting   | tight | window | ramp | strings | ramp RSS MiB | rampCap | chunks |
| -------- | --------- | ----- | ------ | ---- | ------- | ------------ | ------- | ------ |
| tcc      | unchecked | 237   | 372    | 343  | 332     | 248.3        | 0       | 0      |
| tcc      | 0         | 706   | 1711   | 982  | 337     | 324.6        | 1048576 | 1954   |
| tcc      | 256       | 1640  | 1578   | 1223 | 335     | 324.7        | 1048576 | 1954   |
| tcc      | 1024      | 2101  | 1620   | 1326 | 336     | 324.5        | 1048576 | 1954   |
| tcc      | 4096      | 2156  | 1771   | 1442 | 338     | 324.7        | 1048576 | 1954   |
| tcc      | 16384     | 2388  | 1774   | 1521 | 337     | 324.6        | 1048576 | 1954   |
| tcc      | 65536     | 2693  | 1798   | 1692 | 337     | 324.6        | 1048576 | 1954   |
| clang    | unchecked | 0     | 313    | 205  | 248     | 74.0         | 0       | 0      |
| clang    | 0         | 313   | 1046   | 724  | 249     | 148.8        | 1048576 | 1954   |
| clang    | 256       | 766   | 994    | 908  | 246     | 136.7        | 1048576 | 1954   |
| clang    | 1024      | 1091  | 1023   | 957  | 247     | 139.2        | 1048576 | 1954   |
| clang    | 4096      | 1144  | 1179   | 1037 | 247     | 129.9        | 1048576 | 1954   |
| clang    | 16384     | 1318  | 1169   | 1134 | 249     | 133.8        | 1048576 | 1954   |
| clang    | 65536     | 1488  | 1172   | 1201 | 257     | 154.6        | 1048576 | 1954   |
| gcc-16   | unchecked | 0     | 305    | 214  | 225     | 71.3         | 0       | 0      |
| gcc-16   | 0         | 324   | 1041   | 727  | 235     | 131.2        | 1048576 | 1954   |
| gcc-16   | 256       | 819   | 984    | 907  | 232     | 124.2        | 1048576 | 1954   |
| gcc-16   | 1024      | 1136  | 1022   | 956  | 231     | 143.1        | 1048576 | 1954   |
| gcc-16   | 4096      | 1199  | 1156   | 995  | 236     | 151.0        | 1048576 | 1954   |
| gcc-16   | 16384     | 1287  | 1200   | 1120 | 238     | 137.5        | 1048576 | 1954   |
| gcc-16   | 65536     | 1487  | 1176   | 1177 | 236     | 138.2        | 1048576 | 1954   |

L0 triple-test baseline:

- Harness-reported total wall time: 38.98s.
- `/usr/bin/time -p`: real 43.07s, user 41.28s, sys 1.22s.

## Implementation Phases

1. Implement the L0 hot/cold split in `l0/compiler/shared/runtime/l0_runtime.h`, including the 64-byte assert, cold
   chunk directory, aligned hot pool refill, and moved-field accessors.
2. Add L0 benchmark harness size metrics and a cached pointer-check scenario, and surface them in the `bench-runtime`
   table.
3. Validate L0 with `make -C l0 test-stage1`, `make -C l0 -j test-all`, and a generated-C surface spot check.
4. Port the same layout and field relocation to L1's archive runtime and benchmark harness.
5. Rebuild and validate L1 with `make -C l1 runtime` and `make -C l1 test-all`.
6. Repeat the benchmark and triple-test measurements, compare against baseline, and close this plan under
   `work/plans/features/closed/`.

## Current Results

The first implementation pass used a 32-byte pointer-fast-path hot record plus a 72-byte cold companion. It passed
functional tests, but the benchmark criterion failed because allocation-heavy checked rows regressed well beyond the
allowed run-to-run noise. The plan stayed active instead of moving to `work/plans/features/closed/`.

The regression was architectural rather than a functional bug. The first split moved allocation-churn-critical fields
(`q_next`, `tree_left`, `tree_right`, `tree_prio`, and `mem_kind`) behind `_rt_rec_cold`, so every allocation, free,
quarantine, and treap mutation paid cold-directory indirection. The existing benchmark suite mostly measured tracker
churn, not warmed pointer-check cache hits. tcc was hit especially hard; the macro form avoids real calls, but tcc still
appears not to eliminate repeated cold-index and directory computations in these paths.

A second implementation pass now uses a 64-byte tracker-hot `_rt_alloc_record` and a 40-byte cold companion on the LP64
host. Tracker mutation fields are hot again, while diagnostics and rare `rt_realloc` metadata remain cold. The benchmark
harnesses also include a new `cached` scenario that warms one `_rt_ptr_site` per live allocation before timing cache-hit
validation sweeps.

First-pass validation:

- `make -C l0 test-stage1`: 1300 passed.
- `make -C l0 -j test-all`: Stage 1 1300 passed, Stage 2 54 passed, Stage 2 trace 33 passed, examples and workflow tests
  passed.
- `make -C l1 runtime`: rebuilt default, traced, unchecked, and tcc runtime archive variants.
- `make -C l1 test-all`: Stage 1 49 passed, trace 36 passed, environment stackability and examples passed.
- Generated-C surface check: `./scripts/l0c -P examples --gen hello` matched a clean `HEAD` archive after normalizing
  absolute `#line` roots.

First-pass triple-test timing:

- Baseline: harness total 38.98s; `/usr/bin/time -p` real 43.07s, user 41.28s, sys 1.22s.
- After: harness total 49.42s; `/usr/bin/time -p` real 53.23s, user 51.53s, sys 1.31s.

First-pass L0 after vs baseline (`scale=5`, `runs=3`, wall ms, best of 3; timing cells show after value plus percent
delta):

| Compiler | Setting   | hotB | coldB | tight        | window       | ramp        | strings    | ramp RSS MiB  |
| -------- | --------- | ---- | ----- | ------------ | ------------ | ----------- | ---------- | ------------- |
| tcc      | unchecked | 32   | 72    | 249 (+3%)    | 456 (+18%)   | 416 (+16%)  | 328 (-1%)  | 248.4 (-0.1)  |
| tcc      | 0         | 32   | 72    | 825 (+11%)   | 3303 (+47%)  | 1375 (+31%) | 357 (+7%)  | 321.9 (-2.8)  |
| tcc      | 256       | 32   | 72    | 2303 (+9%)   | 3009 (+41%)  | 1823 (+24%) | 349 (+5%)  | 322.1 (-2.7)  |
| tcc      | 1024      | 32   | 72    | 2897 (+32%)  | 3223 (+76%)  | 1894 (+32%) | 355 (+3%)  | 322.1 (-2.6)  |
| tcc      | 4096      | 32   | 72    | 3392 (+29%)  | 4713 (+61%)  | 2238 (+48%) | 347 (+1%)  | 322.1 (-2.7)  |
| tcc      | 16384     | 32   | 72    | 4667 (+88%)  | 4389 (+141%) | 2642 (+65%) | 376 (+12%) | 322.1 (-2.7)  |
| tcc      | 65536     | 32   | 72    | 5912 (+113%) | 4957 (+177%) | 2999 (+89%) | 363 (+10%) | 322.0 (-2.4)  |
| clang    | unchecked | 32   | 72    | 0 (+0%)      | 399 (+28%)   | 271 (+23%)  | 0 (+0%)    | 62.3 (+1.1)   |
| clang    | 0         | 32   | 72    | 424 (+43%)   | 1429 (+40%)  | 824 (+12%)  | 198 (+2%)  | 131.2 (-17.2) |
| clang    | 256       | 32   | 72    | 1071 (+28%)  | 1322 (+31%)  | 1258 (+36%) | 209 (+6%)  | 139.2 (+7.2)  |
| clang    | 1024      | 32   | 72    | 1607 (+39%)  | 1447 (+41%)  | 1165 (+20%) | 198 (+3%)  | 129.8 (+0.0)  |
| clang    | 4096      | 32   | 72    | 1687 (+40%)  | 1951 (+67%)  | 1263 (+20%) | 202 (+1%)  | 133.4 (+5.4)  |
| clang    | 16384     | 32   | 72    | 2008 (+45%)  | 1751 (+45%)  | 1396 (+25%) | 198 (-1%)  | 128.3 (-13.7) |
| clang    | 65536     | 32   | 72    | 2376 (+57%)  | 1696 (+38%)  | 1748 (+39%) | 208 (+4%)  | 137.7 (+3.4)  |
| gcc-16   | unchecked | 32   | 72    | 0 (+0%)      | 322 (+5%)    | 213 (+3%)   | 0 (+0%)    | 51.7 (-23.3)  |
| gcc-16   | 0         | 32   | 72    | 344 (+9%)    | 1546 (+44%)  | 823 (+13%)  | 209 (+4%)  | 146.8 (+23.5) |
| gcc-16   | 256       | 32   | 72    | 1265 (+59%)  | 1702 (+67%)  | 1157 (+27%) | 201 (-2%)  | 134.2 (-4.5)  |
| gcc-16   | 1024      | 32   | 72    | 1528 (+34%)  | 1484 (+44%)  | 1254 (+31%) | 200 (-3%)  | 140.1 (+6.2)  |
| gcc-16   | 4096      | 32   | 72    | 1709 (+43%)  | 2103 (+79%)  | 1413 (+37%) | 272 (+35%) | 141.2 (+17.1) |
| gcc-16   | 16384     | 32   | 72    | 2096 (+58%)  | 2014 (+70%)  | 1534 (+38%) | 204 (+0%)  | 136.1 (+12.3) |
| gcc-16   | 65536     | 32   | 72    | 2291 (+48%)  | 1925 (+65%)  | 1918 (+61%) | 204 (+0%)  | 146.4 (-5.5)  |

First-pass L1 after vs baseline (`scale=5`, `runs=3`, wall ms, best of 3; timing cells show after value plus percent
delta):

| Compiler | Setting   | hotB | coldB | tight       | window      | ramp        | strings    | ramp RSS MiB  |
| -------- | --------- | ---- | ----- | ----------- | ----------- | ----------- | ---------- | ------------- |
| tcc      | unchecked | 32   | 72    | 237 (+0%)   | 372 (+0%)   | 346 (+1%)   | 330 (-1%)  | 248.3 (+0.0)  |
| tcc      | 0         | 32   | 72    | 751 (+6%)   | 2924 (+71%) | 1328 (+35%) | 350 (+4%)  | 322.1 (-2.5)  |
| tcc      | 256       | 32   | 72    | 2272 (+39%) | 2824 (+79%) | 1794 (+47%) | 415 (+24%) | 322.0 (-2.7)  |
| tcc      | 1024      | 32   | 72    | 2724 (+30%) | 2132 (+32%) | 1613 (+22%) | 334 (-1%)  | 322.0 (-2.5)  |
| tcc      | 4096      | 32   | 72    | 2973 (+38%) | 2444 (+38%) | 1725 (+20%) | 337 (+0%)  | 322.2 (-2.5)  |
| tcc      | 16384     | 32   | 72    | 3468 (+45%) | 2353 (+33%) | 1844 (+21%) | 334 (-1%)  | 321.8 (-2.8)  |
| tcc      | 65536     | 32   | 72    | 3754 (+39%) | 2335 (+30%) | 2020 (+19%) | 338 (+0%)  | 321.7 (-2.9)  |
| clang    | unchecked | 32   | 72    | 0 (+0%)     | 309 (-1%)   | 210 (+2%)   | 245 (-1%)  | 81.9 (+7.9)   |
| clang    | 0         | 32   | 72    | 335 (+7%)   | 1310 (+25%) | 774 (+7%)   | 248 (+0%)  | 134.2 (-14.6) |
| clang    | 256       | 32   | 72    | 1044 (+36%) | 1276 (+28%) | 1012 (+11%) | 250 (+2%)  | 124.3 (-12.4) |
| clang    | 1024      | 32   | 72    | 1450 (+33%) | 1322 (+29%) | 1119 (+17%) | 247 (+0%)  | 121.2 (-18.0) |
| clang    | 4096      | 32   | 72    | 1622 (+42%) | 1601 (+36%) | 1218 (+17%) | 244 (-1%)  | 140.4 (+10.5) |
| clang    | 16384     | 32   | 72    | 1854 (+41%) | 1587 (+36%) | 1327 (+17%) | 248 (+0%)  | 134.0 (+0.2)  |
| clang    | 65536     | 32   | 72    | 2092 (+41%) | 1561 (+33%) | 1531 (+27%) | 252 (-2%)  | 140.3 (-14.3) |
| gcc-16   | unchecked | 32   | 72    | 0 (+0%)     | 314 (+3%)   | 213 (+0%)   | 224 (+0%)  | 81.9 (+10.6)  |
| gcc-16   | 0         | 32   | 72    | 345 (+6%)   | 1337 (+28%) | 779 (+7%)   | 234 (+0%)  | 132.9 (+1.7)  |
| gcc-16   | 256       | 32   | 72    | 1022 (+25%) | 1289 (+31%) | 980 (+8%)   | 230 (-1%)  | 117.1 (-7.1)  |
| gcc-16   | 1024      | 32   | 72    | 1440 (+27%) | 1320 (+29%) | 1060 (+11%) | 231 (+0%)  | 122.7 (-20.4) |
| gcc-16   | 4096      | 32   | 72    | 1619 (+35%) | 1572 (+36%) | 1176 (+18%) | 233 (-1%)  | 119.8 (-31.2) |
| gcc-16   | 16384     | 32   | 72    | 1841 (+43%) | 1578 (+32%) | 1404 (+25%) | 230 (-3%)  | 132.9 (-4.6)  |
| gcc-16   | 65536     | 32   | 72    | 2088 (+40%) | 1530 (+30%) | 1405 (+19%) | 229 (-3%)  | 133.4 (-4.8)  |

First-pass interpretation:

- The first-pass hot record size goal was met: `sizeof(_rt_alloc_record) == 32` and
  `sizeof(_rt_alloc_record_cold) == 72` on this host.
- Functional behavior and trace invariants passed in both levels.
- Ramp RSS moved in the expected direction for many checked rows, especially tcc, but the effect is small and noisy.
- Allocation-heavy timings regressed in most checked cells because the benchmark mostly measured allocation tracker
  mutation work, not cached pointer-check dereferences.
- The second pass directly addresses that failure by keeping allocation-churn-critical fields hot and adding a cached
  pointer-check benchmark.

Second-pass validation:

- `git diff --check`: passed.
- L0 benchmark smoke check: `python3 scripts/bench_runtime.py --cc clang --scale 1 --runs 1 --settings 0` compiled and
  reported `hotB=64`, `coldB=40`.
- L1 benchmark smoke check: `python3 scripts/bench_runtime.py --cc clang --scale 1 --runs 1 --settings 0` compiled and
  reported `hotB=64`, `coldB=40`.
- `make -C l0 test-stage1`: 1300 passed.
- `make -C l0 -j test-all`: Stage 1 1300 passed, Stage 2 54 passed, Stage 2 trace 33 passed, examples and workflow tests
  passed.
- `make -C l1 runtime`: rebuilt default, traced, unchecked, and tcc runtime archive variants.
- `make -C l1 test-all`: Stage 1 49 passed, trace 36 passed, environment stackability and examples passed.
- Generated-C surface check: `./scripts/l0c -P examples --gen hello` completed and wrote 4418 lines to
  `/tmp/dea_hotcold_hello.c` without touching tracked generated files.

Second-pass triple-test timing:

- Baseline: harness total 38.98s; `/usr/bin/time -p` real 43.07s, user 41.28s, sys 1.22s.
- First pass: harness total 49.42s; `/usr/bin/time -p` real 53.23s, user 51.53s, sys 1.31s.
- Second pass: harness total 31.74s; `/usr/bin/time -p` real 34.77s, user 33.81s, sys 0.82s.

Second-pass L0 benchmark (`scale=5`, `runs=3`, wall ms, best of 3):

| Compiler | Setting   | hotB | coldB | tight | window | ramp | cached | strings | ramp RSS MiB |
| -------- | --------- | ---- | ----- | ----- | ------ | ---- | ------ | ------- | ------------ |
| tcc      | unchecked | 64   | 40    | 234   | 364    | 311  | 78     | 313     | 248.2        |
| tcc      | 0         | 64   | 40    | 703   | 1618   | 919  | 253    | 325     | 321.5        |
| tcc      | 256       | 64   | 40    | 1654  | 1507   | 1155 | 247    | 329     | 321.8        |
| tcc      | 1024      | 64   | 40    | 2075  | 1562   | 1293 | 242    | 322     | 321.8        |
| tcc      | 4096      | 64   | 40    | 2150  | 1721   | 1332 | 245    | 320     | 321.9        |
| tcc      | 16384     | 64   | 40    | 2428  | 1757   | 1448 | 242    | 325     | 321.7        |
| tcc      | 65536     | 64   | 40    | 2511  | 1740   | 1516 | 244    | 327     | 321.7        |
| clang    | unchecked | 64   | 40    | 0     | 305    | 204  | 4      | 0       | 54.9         |
| clang    | 0         | 64   | 40    | 303   | 1016   | 691  | 113    | 202     | 131.1        |
| clang    | 256       | 64   | 40    | 815   | 980    | 868  | 114    | 191     | 139.8        |
| clang    | 1024      | 64   | 40    | 1165  | 1013   | 910  | 113    | 195     | 148.5        |
| clang    | 4096      | 64   | 40    | 1209  | 1186   | 1001 | 114    | 193     | 124.0        |
| clang    | 16384     | 64   | 40    | 1269  | 1180   | 1117 | 112    | 197     | 146.9        |
| clang    | 65536     | 64   | 40    | 1437  | 1173   | 1136 | 112    | 194     | 137.8        |
| gcc-16   | unchecked | 64   | 40    | 0     | 301    | 297  | 5      | 0       | 60.5         |
| gcc-16   | 0         | 64   | 40    | 321   | 991    | 686  | 102    | 206     | 141.8        |
| gcc-16   | 256       | 64   | 40    | 761   | 946    | 850  | 101    | 203     | 136.9        |
| gcc-16   | 1024      | 64   | 40    | 1106  | 995    | 926  | 101    | 200     | 149.6        |
| gcc-16   | 4096      | 64   | 40    | 1172  | 1151   | 961  | 104    | 202     | 144.8        |
| gcc-16   | 16384     | 64   | 40    | 1220  | 1155   | 1111 | 102    | 204     | 128.1        |
| gcc-16   | 65536     | 64   | 40    | 1406  | 1180   | 1116 | 101    | 209     | 130.6        |

Second-pass L1 benchmark (`scale=5`, `runs=3`, wall ms, best of 3):

| Compiler | Setting   | hotB | coldB | tight | window | ramp | cached | strings | ramp RSS MiB |
| -------- | --------- | ---- | ----- | ----- | ------ | ---- | ------ | ------- | ------------ |
| tcc      | unchecked | 64   | 40    | 232   | 373    | 320  | 73     | 319     | 248.2        |
| tcc      | 0         | 64   | 40    | 696   | 1650   | 932  | 242    | 332     | 321.7        |
| tcc      | 256       | 64   | 40    | 1660  | 1529   | 1179 | 244    | 329     | 321.7        |
| tcc      | 1024      | 64   | 40    | 2124  | 1583   | 1280 | 255    | 329     | 321.7        |
| tcc      | 4096      | 64   | 40    | 2166  | 1753   | 1364 | 243    | 328     | 321.7        |
| tcc      | 16384     | 64   | 40    | 2369  | 1742   | 1461 | 247    | 330     | 321.6        |
| tcc      | 65536     | 64   | 40    | 2552  | 1728   | 1477 | 258    | 337     | 321.7        |
| clang    | unchecked | 64   | 40    | 0     | 308    | 205  | 4      | 243     | 74.1         |
| clang    | 0         | 64   | 40    | 318   | 1041   | 684  | 98     | 242     | 138.1        |
| clang    | 256       | 64   | 40    | 772   | 961    | 860  | 96     | 250     | 136.7        |
| clang    | 1024      | 64   | 40    | 1126  | 1016   | 922  | 98     | 245     | 136.9        |
| clang    | 4096      | 64   | 40    | 1187  | 1177   | 989  | 95     | 246     | 146.0        |
| clang    | 16384     | 64   | 40    | 1300  | 1161   | 1095 | 96     | 251     | 123.4        |
| clang    | 65536     | 64   | 40    | 1436  | 1167   | 1131 | 96     | 243     | 129.8        |
| gcc-16   | unchecked | 64   | 40    | 0     | 305    | 296  | 5      | 223     | 81.9         |
| gcc-16   | 0         | 64   | 40    | 323   | 1023   | 677  | 104    | 229     | 137.9        |
| gcc-16   | 256       | 64   | 40    | 807   | 956    | 835  | 103    | 228     | 148.4        |
| gcc-16   | 1024      | 64   | 40    | 1132  | 1002   | 889  | 104    | 232     | 155.4        |
| gcc-16   | 4096      | 64   | 40    | 1192  | 1126   | 951  | 106    | 230     | 128.1        |
| gcc-16   | 16384     | 64   | 40    | 1296  | 1157   | 1087 | 103    | 241     | 125.3        |
| gcc-16   | 65536     | 64   | 40    | 1484  | 1133   | 1151 | 104    | 229     | 146.6        |

Second-pass interpretation:

- The remediation meets the tracker-hot layout goal: `sizeof(_rt_alloc_record) == 64` and
  `sizeof(_rt_alloc_record_cold) == 40` on this host.
- L0 and L1 churn timings returned to baseline range or better across the checked matrix. The large first-pass
  regressions are gone.
- The explicit `cached` scenario is now recorded for future same-session layout comparisons; no original baseline exists
  for this scenario because the first benchmark harness did not include it.
- L0 triple-test improved beyond both the first pass and the original baseline on this run.

Aggregate delta versus baseline:

- Negative delta means faster than baseline.
- Aggregate rows include checked retention settings only and exclude unchecked rows.
- The `cached` scenario is excluded because it has no pre-change baseline.
- tcc shows the largest aggregate improvement because the remediation removed cold-directory indirection from tracker
  mutation paths that tcc handled especially poorly in the failed 32-byte split.

All baseline scenarios (`tight + window + ramp + strings`):

| Scope    | Compiler | Baseline ms | After ms | Delta ms | Improvement |
| -------- | -------- | ----------- | -------- | -------- | ----------- |
| L0       | tcc      | 36346       | 31037    | -5309    | +14.6%      |
| L0       | clang    | 20323       | 19641    | -682     | +3.4%       |
| L0       | gcc-16   | 20134       | 19278    | -856     | +4.3%       |
| L1       | tcc      | 32142       | 31230    | -912     | +2.8%       |
| L1       | clang    | 20159       | 19820    | -339     | +1.7%       |
| L1       | gcc-16   | 20121       | 19610    | -511     | +2.5%       |
| Combined | tcc      | 68488       | 62267    | -6221    | +9.1%       |
| Combined | clang    | 40482       | 39461    | -1021    | +2.5%       |
| Combined | gcc-16   | 40255       | 38888    | -1367    | +3.4%       |

Tracker churn scenarios (`tight + window + ramp`):

| Scope    | Compiler | Baseline ms | After ms | Delta ms | Improvement |
| -------- | -------- | ----------- | -------- | -------- | ----------- |
| L0       | tcc      | 34329       | 29089    | -5240    | +15.3%      |
| L0       | clang    | 19138       | 18469    | -669     | +3.5%       |
| L0       | gcc-16   | 18911       | 18054    | -857     | +4.5%       |
| L1       | tcc      | 30122       | 29245    | -877     | +2.9%       |
| L1       | clang    | 18664       | 18343    | -321     | +1.7%       |
| L1       | gcc-16   | 18713       | 18221    | -492     | +2.6%       |
| Combined | tcc      | 64451       | 58334    | -6117    | +9.5%       |
| Combined | clang    | 37802       | 36812    | -990     | +2.6%       |
| Combined | gcc-16   | 37624       | 36275    | -1349    | +3.6%       |

## Verification Criteria

- `sizeof(_rt_alloc_record)` is asserted as 64 bytes in both checked runtimes.
- Both benchmark harnesses surface hot and cold record sizes plus the cached pointer-check scenario without breaking
  unchecked builds.
- Full `make -C l0 test-all` and `make -C l1 test-all` pass.
- `make -C l0 bench-runtime`, `make -C l1 bench-runtime`, and `/usr/bin/time -p make -C l0 triple-test` are recorded
  before and after on the same host.
- No churn scenario x compiler x retention cell regresses beyond run-to-run noise unless the completion notes document a
  justified outlier.
- The cached pointer-check scenario is recorded for the current layout and becomes the baseline for future layout
  comparisons.
- L0 generated C for `./scripts/l0c -P examples --gen hello` completes without touching tracked files.
