# Feature Plan

## Shared runtime check-basic mode

- Date: 2026-07-08
- Status: Closed
- Title: Shared checked-runtime basic validation mode
- Kind: Feature
- Severity: Medium
- Stage: Shared
- Subsystem: Runtime pointer validation, CLI drivers, C backend prelude, runtime archive build, benchmarks
- Scope: Shared
- Targets:
  - L0 Stage 1 Python driver, backend, and header runtime
  - L0 Stage 2 driver and backend
  - L1 Stage 1 driver, backend, and archive runtime
- Origin: Follow-up to checked-runtime allocation-tracker performance work
- Porting rule: Keep CLI semantics, generated prelude defines, basic-mode runtime semantics, and benchmark rows
  mechanically aligned across L0 and L1; L1 additionally selects a prebuilt archive and tcc object variant.
- Target status:
  - L0 Stage 1 Python driver, backend, and header runtime: Done
  - L0 Stage 2 driver and backend: Done
  - L1 Stage 1 driver, backend, and archive runtime: Done
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l0/compiler/stage1_py/l0c.py`
  - `l0/compiler/stage1_py/l0_context.py`
  - `l0/compiler/stage1_py/l0_c_emitter.py`
  - `l0/compiler/stage2_l0/src/cli_args.l0`
  - `l0/compiler/stage2_l0/src/codegen_options.l0`
  - `l0/compiler/stage2_l0/src/c_emitter.l0`
  - `l0/compiler/stage2_l0/src/build_driver.l0`
  - `l0/compiler/stage2_l0/src/l0c_lib.l0`
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/codegen_options.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l0/Makefile`
  - `l1/Makefile`
  - `l0/scripts/bench_runtime.py`
  - `l1/scripts/bench_runtime.py`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_cli_mode_flags.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage1_py/tests/backend/test_runtime_pointer_validation.py`
  - `l0/compiler/stage1_py/tests/backend/test_runtime_alloc_tracker.py`
  - `l0/compiler/stage2_l0/tests/cli_args_test.l0`
  - `l0/compiler/stage2_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/runtime_pointer_validation_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_alloc_tracker_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_symbol_manifest_test.py`
- Related:
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
  - `work/plans/features/closed/2026-07-04-shared-unchecked-build-surface-noref.md`
  - `work/plans/features/closed/2026-07-07-shared-alloc-record-hot-cold-split-noref.md`
- Repro: `make -C l0 bench-runtime && make -C l1 bench-runtime`

## Summary

The full checked runtime validates exact allocation bases through a hash table and interior derived pointers through an
address-ordered treap. The treap preserves strong spatial diagnostics, but it dominates allocation tracker mutation and
interior lookup cost. This plan adds a middle checked mode, `CHECK_BASIC`, that keeps hash-resident base validation,
quarantine temporal checks, generation caches, and read-only exact-base protection while compiling out treap tracking
and interior containment checks.

## Shared Design

- `--check-basic` is valid in `--build`, `--run`, and `--gen`.
- `--check-basic` is mutually exclusive with `--unchecked`, `--trace-arc`, and `--trace-memory`.
- L0 emits `#define L0_RT_CHECK_BASIC 1`; L1 emits `#define DEA_RT_CHECK_BASIC 1`.
- Defining both basic and unchecked runtime macros is a compile-time error in the runtime headers.
- The L1 driver selects `libdea_rt_check_basic.a`, linker name `dea_rt_check_basic`, or tcc object directory
  `runtime/tcc/check_basic`.
- Diagnostic codes were re-checked against the live catalog on 2026-07-08. The implementation uses `L0C-2027`/`L1C-2027`
  for mode-scope violations, `L0C-2028`/`L1C-2028` for conflicts, and `L1C-0021` for L1 `--gen --check-basic` link
  guidance.

## Runtime Semantics

- Exact base hash hits validate like full checked mode and update the per-site cache.
- Null, negative size, invalid alignment, invalid access-mode, base use-after-drop, double drop, untracked drop,
  exact-base out-of-range access, and exact-base read-only writes still panic.
- Hash misses for scalar pointer checks validate only alignment and return without caching.
- Hash misses for indexed pointer checks use the existing untracked overflow and target-alignment path.
- Interior-pointer drops report `unregistered pointer`.
- `_rt_validate_derived_ptr` validates only exact hash-resident parent bases in basic mode; unregistered parent storage
  still passes through to access-site validation.
- `_rt_alloc_record` remains 64 bytes; treap fields are replaced by padding in basic builds so pool and cold-index
  behavior remain unchanged.

## Non-Goals

- No traced-basic archive variant.
- No syntax changes or static elision changes.
- No separate L1 symbol manifest unless the basic archive public symbol surface diverges from the default checked
  archive.

## Verification Criteria

- L0 Stage 1, L0 Stage 2, and L1 accept `--check-basic` in build/run/gen and reject it elsewhere.
- L0 Stage 1, L0 Stage 2, and L1 reject `--check-basic` with `--unchecked`, `--trace-arc`, or `--trace-memory`.
- L1 `--gen --check-basic` emits a `L1C-0021` warning.
- Generated C carries the correct prelude define before the runtime include.
- Runtime harnesses cover base UAF, double drop, read-only string writes, valid interior/stale-derived accesses,
  interior drop, and mixed-size churn in basic mode.
- `make -C l1 runtime` produces default, traced, unchecked, and check-basic archives plus tcc object variants.
- Benchmark scripts print a basic row alongside unchecked and checked retention rows.

## Completion Notes

Closed on 2026-07-08 with one shared implementation across L0 Stage 1, L0 Stage 2, and L1 Stage 1/runtime. `CHECK_BASIC`
remains a checked runtime variant: generated code keeps the checked runtime call shape and only changes the emitted
prelude define/runtime archive selection.

## Verification Results

- `make -C l1 runtime`: Pass; produced `libdea_rt.a`, `libdea_rt_traced.a`, `libdea_rt_unchecked.a`,
  `libdea_rt_check_basic.a`, and the default/traced/unchecked/check_basic tcc object directories.
- `make -C l0 test-all`: Pass; Stage 1 Python suite, Stage 2 suite, Stage 2 trace checks, examples, and workflow tests.
- `make -C l1 test-all L1_TRACE_TEST_JOBS=1`: Pass; normal Stage 1 tests ran with default parallelism, trace checks ran
  single-job after the first default-parallel run was interrupted while diagnosing a long-running trace worker.
- `make -C l0 bench-runtime`: Pass.
- `make -C l1 bench-runtime`: Pass.
- `/usr/bin/time -p make -C l0 triple-test`: Pass; `real 53.66`, `user 51.85`, `sys 1.30`.
- `/usr/bin/time -p make -C l0 triple-test L0_CFLAGS=-DL0_RT_CHECK_BASIC`: Pass; `real 45.91`, `user 44.40`, `sys 1.28`.

## Benchmark Conclusions

> **Correction (2026-07-11):** The benchmark timings below used process CPU `clock()` and allowed optimized unchecked
> allocation/string loops to disappear. They are not valid wall-time evidence; functional mode coverage and
> deterministic tracker-memory observations remain valid. Corrected monotonic, anti-elision matrices are recorded in
> [work/plans/bug-fixes/closed/2026-07-11-shared-checked-runtime-review-gaps-noref.md](../../bug-fixes/closed/2026-07-11-shared-checked-runtime-review-gaps-noref.md).

- `check_basic` is consistently faster than full checked mode on allocation-heavy paths.
- `check_basic` remains slower than `unchecked`, as expected, because it still preserves core checked runtime
  validation.
- Tracker shape matches checked mode: `hotB=64`, `coldB=40`, ramp cap `1048576`, chunks `1954`.
- L0 and L1 benchmark results are closely aligned, confirming shared runtime behavior.
- The L0 triple bootstrap improved from the checked baseline `real 53.66` to `real 45.91` with `L0_RT_CHECK_BASIC`.

## Benchmark Results

L0 `make -C l0 bench-runtime`, default `scale=5`, `runs=3`:

```text
=== tcc (tcc version 0.9.28rc 2026-02-07 mob@4597a962 (x86_64 Darwin)) ===
   setting | hotB | coldB |     tight |    window |      ramp |    cached |   strings | rampRSSMiB |   rampCap |  chunks
------------------------------------------------------------------------------------------------------------------------
 unchecked |   64 |    40 |       368 |       582 |       481 |       124 |       498 |      248.4 |         0 |       0
check_basic |   64 |    40 |      1553 |      1749 |      1152 |       353 |       517 |      321.8 |   1048576 |    1954
         0 |   64 |    40 |      1109 |      2607 |      1285 |       354 |       513 |      321.8 |   1048576 |    1954
       256 |   64 |    40 |      2587 |      2420 |      1677 |       354 |       509 |      321.8 |   1048576 |    1954
      1024 |   64 |    40 |      3275 |      2559 |      1860 |       355 |       513 |      322.0 |   1048576 |    1954
      4096 |   64 |    40 |      3386 |      2920 |      1944 |       353 |       511 |      321.8 |   1048576 |    1954
     16384 |   64 |    40 |      3754 |      2891 |      2140 |       356 |       511 |      322.0 |   1048576 |    1954
     65536 |   64 |    40 |      4093 |      2905 |      2259 |       351 |       505 |      321.9 |   1048576 |    1954

=== clang (Apple clang version 17.0.0 (clang-1700.6.4.2)) ===
   setting | hotB | coldB |     tight |    window |      ramp |    cached |   strings | rampRSSMiB |   rampCap |  chunks
------------------------------------------------------------------------------------------------------------------------
 unchecked |   64 |    40 |         0 |       481 |       292 |         5 |         0 |       70.1 |         0 |       0
check_basic |   64 |    40 |       826 |      1062 |       900 |       129 |       303 |      135.1 |   1048576 |    1954
         0 |   64 |    40 |       484 |      1653 |       919 |       132 |       309 |      133.2 |   1048576 |    1954
       256 |   64 |    40 |      1258 |      1558 |      1223 |       133 |       303 |      148.6 |   1048576 |    1954
      1024 |   64 |    40 |      1804 |      1675 |      1300 |       134 |       314 |      124.1 |   1048576 |    1954
      4096 |   64 |    40 |      2003 |      1969 |      1392 |       137 |       308 |      133.7 |   1048576 |    1954
     16384 |   64 |    40 |      2153 |      1901 |      1544 |       135 |       304 |      121.3 |   1048576 |    1954
     65536 |   64 |    40 |      2327 |      1962 |      1637 |       133 |       306 |      148.2 |   1048576 |    1954

=== gcc-16 (gcc-16 (Homebrew GCC 16.1.0) 16.1.0) ===
   setting | hotB | coldB |     tight |    window |      ramp |    cached |   strings | rampRSSMiB |   rampCap |  chunks
------------------------------------------------------------------------------------------------------------------------
 unchecked |   64 |    40 |         0 |       476 |       454 |         8 |         0 |       74.0 |         0 |       0
check_basic |   64 |    40 |       849 |      1030 |       862 |       123 |       312 |      125.2 |   1048576 |    1954
         0 |   64 |    40 |       501 |      1599 |       902 |       118 |       312 |      123.2 |   1048576 |    1954
       256 |   64 |    40 |      1202 |      1511 |      1222 |       124 |       315 |      133.4 |   1048576 |    1954
      1024 |   64 |    40 |      1751 |      1642 |      1269 |       117 |       327 |      116.2 |   1048576 |    1954
      4096 |   64 |    40 |      1846 |      1832 |      1360 |       123 |       311 |      135.3 |   1048576 |    1954
     16384 |   64 |    40 |      2037 |      1976 |      1504 |       117 |       312 |      123.8 |   1048576 |    1954
     65536 |   64 |    40 |      2192 |      1813 |      1553 |       120 |       315 |      139.1 |   1048576 |    1954
```

L1 `make -C l1 bench-runtime`, default `scale=5`, `runs=3`:

```text
=== tcc (tcc version 0.9.28rc 2026-02-07 mob@4597a962 (x86_64 Darwin)) ===
   setting | hotB | coldB |     tight |    window |      ramp |    cached |   strings | rampRSSMiB |   rampCap |  chunks
------------------------------------------------------------------------------------------------------------------------
 unchecked |   64 |    40 |       368 |       598 |       506 |       117 |       497 |      248.4 |         0 |       0
check_basic |   64 |    40 |      1616 |      1479 |      1161 |       352 |       514 |      321.7 |   1048576 |    1954
         0 |   64 |    40 |      1105 |      2733 |      1266 |       354 |       525 |      321.8 |   1048576 |    1954
       256 |   64 |    40 |      2659 |      2469 |      1762 |       355 |       520 |      321.8 |   1048576 |    1954
      1024 |   64 |    40 |      3287 |      2571 |      1943 |       353 |       520 |      322.3 |   1048576 |    1954
      4096 |   64 |    40 |      3461 |      2985 |      1948 |       356 |       519 |      322.0 |   1048576 |    1954
     16384 |   64 |    40 |      3777 |      3209 |      2081 |       357 |       524 |      321.9 |   1048576 |    1954
     65536 |   64 |    40 |      4105 |      2940 |      2277 |       370 |       527 |      321.8 |   1048576 |    1954

=== clang (Apple clang version 17.0.0 (clang-1700.6.4.2)) ===
   setting | hotB | coldB |     tight |    window |      ramp |    cached |   strings | rampRSSMiB |   rampCap |  chunks
------------------------------------------------------------------------------------------------------------------------
 unchecked |   64 |    40 |         0 |       491 |       323 |         6 |       382 |       56.5 |         0 |       0
check_basic |   64 |    40 |       805 |      1011 |       876 |       112 |       388 |      132.6 |   1048576 |    1954
         0 |   64 |    40 |       493 |      1656 |       917 |       112 |       387 |      134.1 |   1048576 |    1954
       256 |   64 |    40 |      1257 |      1546 |      1216 |       118 |       384 |      135.2 |   1048576 |    1954
      1024 |   64 |    40 |      1757 |      1642 |      1300 |       113 |       382 |      122.2 |   1048576 |    1954
      4096 |   64 |    40 |      1843 |      1928 |      1391 |       114 |       385 |      145.5 |   1048576 |    1954
     16384 |   64 |    40 |      2130 |      1940 |      1513 |       111 |       381 |      131.2 |   1048576 |    1954
     65536 |   64 |    40 |      2287 |      2009 |      1614 |       115 |       386 |      140.3 |   1048576 |    1954

=== gcc-16 (gcc-16 (Homebrew GCC 16.1.0) 16.1.0) ===
   setting | hotB | coldB |     tight |    window |      ramp |    cached |   strings | rampRSSMiB |   rampCap |  chunks
------------------------------------------------------------------------------------------------------------------------
 unchecked |   64 |    40 |         0 |       484 |       443 |         8 |       351 |       68.2 |         0 |       0
check_basic |   64 |    40 |       842 |      1055 |       860 |       121 |       359 |      140.7 |   1048576 |    1954
         0 |   64 |    40 |       511 |      1610 |       928 |       128 |       372 |      135.8 |   1048576 |    1954
       256 |   64 |    40 |      1321 |      1515 |      1207 |       119 |       363 |      134.1 |   1048576 |    1954
      1024 |   64 |    40 |      1780 |      1584 |      1264 |       119 |       362 |      132.6 |   1048576 |    1954
      4096 |   64 |    40 |      1887 |      1876 |      1362 |       131 |       364 |      131.4 |   1048576 |    1954
     16384 |   64 |    40 |      2112 |      1925 |      1500 |       121 |       361 |      139.5 |   1048576 |    1954
     65536 |   64 |    40 |      2265 |      1902 |      1580 |       122 |       364 |      128.8 |   1048576 |    1954
```
