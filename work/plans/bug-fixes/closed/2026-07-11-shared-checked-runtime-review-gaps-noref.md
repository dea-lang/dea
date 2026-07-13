# Bug Fix Plan

## Close checked-runtime pointer validation review gaps

- Date: 2026-07-11
- Status: Completed
- Title: Close allocation provenance, foreign pointer, trace, build, and benchmark gaps in checked runtimes
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Stage 1, Stage 2, and shared header runtime
  - L1 Stage 1 and shared archive runtime
  - Shared runtime build, benchmark, and documentation surfaces
- Origin: L0 shared header runtime and Python Stage 1 backend
- Porting rule: Establish runtime semantics and generated-C shape in L0 Stage 1, then port mechanically to L0 Stage 2
  and L1 except for L1 archive symbols and Make rebuild tracking.
- Target status:
  - L0 Stage 1, Stage 2, and shared header runtime: Implemented
  - L1 Stage 1 and shared archive runtime: Implemented
  - Shared runtime build, benchmark, and documentation surfaces: Implemented
- Subsystem: Runtime pointer validation, generated drop cleanup, raw-memory FFI, tracing, runtime archives, and
  benchmarks
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage1_py/l0_c_emitter.py`
  - `l0/compiler/stage2_l0/src/backend.l0`
  - `l0/compiler/stage2_l0/src/c_emitter.l0`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l1/compiler/shared/runtime/src/dea_rt_string.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l0/compiler/shared/l0/stdlib/sys/memory.l0`
  - `l1/compiler/shared/l1/stdlib/sys/memory.l1`
  - `l1/Makefile`
  - `l0/scripts/bench_runtime_harness.c`
  - `l0/scripts/bench_runtime.py`
  - `l1/scripts/bench_runtime_harness.c`
  - `l1/scripts/bench_runtime.py`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_runtime_pointer_validation.py`
  - `l0/compiler/stage1_py/tests/backend/test_trace_memory.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l0/compiler/stage2_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/runtime_pointer_validation_test.py`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/runtime_symbol_manifest_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_build_config_test.py`
- Related:
  - `work/plans/features/closed/2026-06-30-shared-runtime-pointer-access-validation-noref.md`
  - `work/plans/features/closed/2026-07-04-shared-runtime-alloc-benchmark-noref.md`
  - `work/plans/features/closed/2026-07-08-shared-runtime-check-basic-mode-noref.md`
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
  - `work/proposals/static-pointer-check-elision.md`
- Repro: raw `rt_alloc(1)` accepted by generated `drop` cleanup, heap-string write accepted under `--check-basic`, and
  valid unregistered pointer returned by an external C function rejected in full checked mode

## Summary

The checked-runtime implementation collapses raw and `new` allocations into one releasable memory kind, registers ARC
string headers while exposing interior byte pointers, and provides no supported lifetime registration surface for valid
foreign memory. The same branch also drops invalid-drop panic trace events, leaves one L0 trace path observing a pointer
after possible eviction, fails to rebuild L1 archives when baked tuning flags change, and records optimized-away
CPU-time loops as wall-time benchmark evidence.

This fix restores allocation-family ownership, makes generated drop cleanup extent-aware, protects heap strings in basic
mode, adds explicit foreign-memory registration, restores trace compatibility, makes archive configuration changes
rebuild-sensitive, and replaces the invalid benchmark evidence.

## Runtime Contract

1. Split tracked memory into raw, `new`, ARC, static, and foreign kinds. `drop` accepts only `new`; `rt_free` and
   `rt_realloc` accept only raw allocations.
2. Change `_rt_drop_begin_impl` directly to take expected size and alignment. Remove the obsolete `_rt_drop` and
   `_rt_drop_impl` helpers so every generated drop cleanup uses the sized begin/finish protocol.
3. Register heap-string byte storage at the exposed byte pointer, making exact-base basic-mode writes read-only.
4. Add `rt_register_foreign(ptr, bytes, read_only)` and `rt_unregister_foreign(ptr)`. Identical live registrations are
   idempotent; conflicting registrations panic; unregistration invalidates tracking without freeing foreign storage.
5. Keep unchecked mode as an explicit validation opt-out. Registration validates basic arguments but stores no tracker
   state there.

The L1 runtime ABI is unreleased. Compiler, header, archives, tcc objects, manifests, and generated-C tests change
atomically; no compatibility wrapper or unsized drop entry point remains.

## Tooling And Documentation

1. Restore the existing invalid-drop `panic-not-found` memory trace and make L0 trace ordering safe across immediate
   quarantine eviction and realloc.
2. Add content-sensitive per-variant runtime flag stamps so L1 archives rebuild when compiler, flags, tuning values, or
   mode defines change without penalizing identical incremental builds.
3. Measure monotonic wall time and add observable pointer escapes to allocation/string benchmark loops. Rerun the full
   L0 and L1 matrix with tcc, clang, and gcc-16 at scale 5, best of 3.
4. Refresh ADR-0010, ownership, standard-library, design-decision, trace, roadmap, proposal, and benchmark evidence.
   Audit and refresh affected `Version:` metadata. No new compiler diagnostic codes are required.

## Verification Criteria

- Raw allocations cannot reach generated drop cleanup; `new` allocations cannot reach raw free/realloc.
- Drop begin rejects an undersized pointee before dereferencing owned fields.
- Heap and static string bytes reject checked writes in full and basic modes.
- Registered writable/read-only foreign storage validates correctly; after unregister, fully checked access fails as
  unregistered while basic mode retains its documented hash-miss-as-untracked contract.
- Invalid drops emit one compatible panic trace; successful L0 trace paths do not observe released pointer values.
- Changing an L1 baked runtime setting rebuilds affected archives, while repeating the same configuration is a no-op.
- Optimized unchecked benchmark scenarios retain observable allocation/string work and report monotonic wall time.
- Focused tests, ASan probes, both clean full suites, both complete benchmark matrices, docs audit, `git diff --check`,
  and pre-commit all pass.

## Outcome

- Split allocation provenance into raw, `new`, ARC, static, and foreign families in both runtimes. Checked `drop`
  accepts only `new`; `rt_free` and `rt_realloc` accept only raw allocations.
- Broke the unreleased L1 runtime ABI atomically: `_rt_drop_begin_impl` now requires pointee size/alignment, obsolete
  `_rt_drop`/`_rt_drop_impl` symbols and emitter paths are gone, and every backend emits sized begin/finish cleanup.
- Registered heap-string bytes at the exposed byte base, closing the exact-base `--check-basic` write gap.
- Added checked foreign-memory lifetime registration with idempotent identical registration, conflict detection,
  read-only enforcement, unregister-without-free, full-mode post-unregister rejection, and argument-only unchecked
  behavior.
- Restored one compatible invalid-drop `panic-not-found` trace, made L0 realloc tracing retain only an address snapshot
  across immediate quarantine eviction, and preserved trace-before-release ordering.
- Added content-sensitive L1 runtime configuration stamps for every archive and tcc object variant; changed settings
  rebuild affected objects, while identical invocations are no-ops.
- Replaced CPU-time/optimizable benchmark loops with monotonic wall timing and observable pointer escapes. Marked three
  archived timing tables as invalid performance evidence while retaining their deterministic memory observations.
- Refreshed the shared ADR, ownership, standard-library, backend/design/status/trace/roadmap docs, the static-elision
  proposal, and all reviewed `Version:` markers. No compiler diagnostic codes were added.

## Corrected Benchmark Evidence

Both levels completed all 24 rows (`unchecked`, `check_basic`, and retention counts `0`, `256`, `1024`, `4096`, `16384`,
`65536`) on the macOS x86_64 development host with tcc, Apple clang 17, and GCC 16.1 at scale 5, best of 3. Values below
are monotonic wall milliseconds; `ramp` is the sum of grow/free/settle phases.

### L0 header runtime

| Compiler | Setting     | tight | window | ramp | cached | strings |
| -------- | ----------- | ----: | -----: | ---: | -----: | ------: |
| tcc      | unchecked   |   787 |   1817 |  766 |    201 |     741 |
| tcc      | check_basic |  2264 |   4533 | 2047 |    455 |     687 |
| tcc      | 0           |  1374 |   4431 | 1597 |    449 |     619 |
| tcc      | 256         |  3393 |   4317 | 2351 |    538 |     652 |
| tcc      | 1024        |  4170 |   4851 | 2887 |    644 |     726 |
| tcc      | 4096        |  5232 |   8339 | 3299 |    605 |     731 |
| tcc      | 16384       |  6062 |  10728 | 4350 |    717 |    1115 |
| tcc      | 65536       |  8745 |   7314 | 3791 |    614 |     713 |
| clang    | unchecked   |   415 |    910 |  659 |      9 |     425 |
| clang    | check_basic |  1182 |   3000 | 1542 |    234 |     406 |
| clang    | 0           |   647 |   3197 | 1323 |    235 |     404 |
| clang    | 256         |  1699 |   2559 | 1720 |    227 |     393 |
| clang    | 1024        |  2242 |   2575 | 1747 |    235 |     395 |
| clang    | 4096        |  2394 |   3705 | 2307 |    252 |     451 |
| clang    | 16384       |  3522 |   4822 | 2680 |    239 |     451 |
| clang    | 65536       |  4164 |   4585 | 2608 |    227 |     435 |
| gcc-16   | unchecked   |   442 |    966 |  654 |     11 |     429 |
| gcc-16   | check_basic |  1282 |   3363 | 1395 |    235 |     480 |
| gcc-16   | 0           |   712 |   3045 | 1338 |    220 |     443 |
| gcc-16   | 256         |  1779 |   2696 | 1552 |    145 |     380 |
| gcc-16   | 1024        |  1927 |   1848 | 1249 |    141 |     314 |
| gcc-16   | 4096        |  1796 |   2937 | 1593 |    175 |     327 |
| gcc-16   | 16384       |  2119 |   2577 | 1605 |    118 |     308 |
| gcc-16   | 65536       |  2127 |   1616 | 1330 |    103 |     252 |

### L1 archive runtime

| Compiler | Setting     | tight | window | ramp | cached | strings |
| -------- | ----------- | ----: | -----: | ---: | -----: | ------: |
| tcc      | unchecked   |   244 |    393 |  350 |     78 |     334 |
| tcc      | check_basic |  1016 |    964 |  870 |    280 |     343 |
| tcc      | 0           |   727 |   1774 |  979 |    272 |     341 |
| tcc      | 256         |  1793 |   1599 | 1244 |    271 |     353 |
| tcc      | 1024        |  2263 |   1700 | 1373 |    277 |     341 |
| tcc      | 4096        |  2296 |   1945 | 1429 |    272 |     357 |
| tcc      | 16384       |  2624 |   1985 | 1557 |    273 |     371 |
| tcc      | 65536       |  3007 |   1976 | 1638 |    273 |     373 |
| clang    | unchecked   |   212 |    336 |  331 |      4 |     268 |
| clang    | check_basic |   547 |    766 |  667 |    100 |     262 |
| clang    | 0           |   341 |   1087 |  699 |    101 |     259 |
| clang    | 256         |   799 |   1002 |  893 |    101 |     262 |
| clang    | 1024        |  1147 |   1059 |  928 |    102 |     259 |
| clang    | 4096        |  1162 |   1240 | 1004 |    100 |     262 |
| clang    | 16384       |  1300 |   1236 | 1102 |    101 |     253 |
| clang    | 65536       |  1540 |   1247 | 1186 |     99 |     261 |
| gcc-16   | unchecked   |   197 |    316 |  325 |      5 |     231 |
| gcc-16   | check_basic |   508 |    645 |  664 |    105 |     241 |
| gcc-16   | 0           |   335 |   1066 |  702 |    103 |     244 |
| gcc-16   | 256         |   832 |    980 |  878 |    102 |     244 |
| gcc-16   | 1024        |  1122 |   1032 |  924 |    103 |     238 |
| gcc-16   | 4096        |  1145 |   1158 |  997 |    101 |     244 |
| gcc-16   | 16384       |  1253 |   1163 | 1080 |    102 |     237 |
| gcc-16   | 65536       |  1516 |   1174 | 1157 |    103 |     237 |

The corrected data removes the impossible optimized-away zeroes. Smaller retention generally helps allocation-heavy
paths, but the magnitude and the value of intermediate settings vary by compiler and workload; the live docs now
recommend measuring deployment-specific tradeoffs instead of treating 1024 as universally equivalent to 4096.

## Verification

- Focused L0 Stage 1: `103 passed`; focused L0 Stage 2 backend/emitter: `2 passed`.
- Focused L1 compiler/runtime: `7 passed`, including manifests, configuration stamps, pointer behavior, traces, and
  tracker invariants.
- ASan sized-drop probe: rejected the undersized ARC-bearing pointee before cleanup with no sanitizer finding.
- Immediate-eviction traced realloc probe: compiled with GCC 16 `-Werror=use-after-free` and ran under ASan with no
  finding.
- `make clean test-all`: passed from clean artifacts. L0: `1326` Stage 1 tests, `54` Stage 2 suites, `33` trace suites,
  `8` examples, and all distribution/workflow tests. L1: `50` normal suites, `36` trace suites, env stackability, and
  `4` examples.
- L0 and L1 `bench_runtime.py --cc "tcc clang gcc-16" --scale 5 --runs 3`: all 48 combined rows passed with positive
  wall times and observable pointer sinks.
- `make -C l1 runtime` followed by the identical command: first build produced all variants; the second produced no
  rebuild output. The isolated setting-change regression also passed.
- `make -C l0 docs`: strict documentation generation passed after documenting the affected emitter parameter.
- ADR index parity was audited across root, L0, and L1; every ADR file has exactly one index row.
- Copyright and `mdformat` pre-commit hooks passed; `git diff --check` passed.
