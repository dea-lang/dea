# Tool Plan

## Separate preparation coverage from compiler and runtime checks

- Date: 2026-09-13
- Status: Completed
- Title: Separate preparation coverage from compiler and runtime checks
- Kind: Tooling
- Severity: Medium
- Stage: 1
- Subsystem: Stage 1 test inputs, native support composition and trace workload
- Modules:
  - `l1/compiler/stage1_l0/scripts/test_runner_common.py`
  - `l1/compiler/stage1_l0/scripts/run_trace_tests.py`
  - `l1/compiler/stage1_l0/scripts/run_test_trace.py`
  - `l1/scripts/build_stage1_l1c.py`
- Test modules:
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/mul_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/slice_trace_test.l0`
  - `l1/compiler/stage1_l0/tests/math_runtime_compile_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_build_run_multi_cu_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_link_set_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_toplet_test.py`
  - `l1/compiler/stage1_l0/tests/compiler_runtime_build_env_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_trace_runner_common_test.py`
  - `l1/compiler/stage1_l0/tests/support/driver_inputs.l0`
  - `l1/compiler/stage1_l0/tests/support/driver_inputs.py`
- Related:
  - [l1/work/plans/features/closed/2026-09-13-warm-preparation-validation-reuse-noref.md][warm-validation]
- Repro: `make test-stage1-trace TESTS="l1c_lib_test mul_runtime_test slice_trace_test"`

## Summary

Completed points 1 through 5 of the preparation-cost investigation without changing production preparation semantics.
Unrelated driver/runtime tests explicitly select their source and runtime inputs. Dedicated tests retain automatic
preparation coverage. Measurements after that separation did not justify retaining a split of the driver trace harness.
Test support composition omits preparation C for tests that do not require it.

## ADR Impact

- Decision: Keep automatic preparation coverage explicit while eliminating redundant work in unrelated tests.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This changes test input selection and support compilation only. Existing compiler, runtime, cache,
    semantic-validation and trace-health contracts remain unchanged.

## Baseline

The earlier Intel Mac CI job spent 6m10s in normal tests and 7m40s in trace tests. The preparation-focused Intel Mac CI
job spent 16m05s and 31m38s respectively, using the same runner image, Clang version and four workers. The latter
`l1c_lib_test` produced 10,561,650,858 trace bytes and 76,912,462 events, with 441.925 seconds executing the test and
1,265.963 seconds analyzing its trace. Normal coverage increased from 73 to 81 cases and trace coverage from 45 to 46.

Existing driver test executables embed the compiler. Their distinct executable identities prevent native-profile sharing
between harnesses, and every preparation invocation validates the full bundled graph even on a native cache hit. The
runners also append all compiler-private C support sources to every `.l0` build.

## Implementation Steps

1. Add explicit source/runtime input selection to unrelated driver, multiplication, slice and math tests. Respect custom
   build directories and keep the helper local to tests. Do not inject native-only options into semantic-only modes.
2. Retain and strengthen dedicated cold/warm automatic-preparation and integration coverage, including a consumer
   without bundled imports. Verify prepared outputs execute and warm consumers compile no managed modules.
3. Measure the affected trace cases after input separation, recording execution, analyzer time, bytes and event counts.
   Use identical local toolchain/configuration for comparisons where possible and distinguish local timing from CI.
4. Prototype a split only if the remaining driver harness still dominates tracing, and retain it only if measurements
   show a net benefit. Preserve every assertion, independent output ownership, test discovery and trace coverage. Avoid
   splitting before eliminating repeated automatic preparation.
5. Avoid repeated preparation C compilation in tests that do not need it, while preserving upstream compiler flags,
   support ABI and ordinary compiler builds. Validate support selection for both normal and trace runners.

## Implementation And Measurement Checkpoint

The `.l0` and Python `support/driver_inputs` helpers select the repo's bundled source tree, public runtime headers and
Make-built archives for unrelated native consumers. This covers multiplication, slices, slow math, all native driver
cases, top-level-let and ARC integrations, multi-CU orchestration and ordinary link-set operations. Native-only options
are added only to native modes. Dedicated preparation suites and the deliberate default-host linking and stdin cold/warm
integration cases keep automatic discovery exercised. TinyCC retains automatic raw-object selection.

The automatic-preparation integration suite additionally runs a no-import application against a warm profile with
`--no-auto-prepare`, asserting its program status, one native resolution, zero managed module compiles, zero preparation
build commands, and one complete bundled analysis. This deliberately retains the current warm semantic contract.

After explicit inputs, the three previously expensive traces passed with no leaks:

| Test               | Preparation CI bytes | Explicit-input bytes | Explicit-input events | Local run (s) | Local analyzer (s) |
| ------------------ | -------------------: | -------------------: | --------------------: | ------------: | -----------------: |
| `l1c_lib_test`     |       10,561,650,858 |        2,916,801,097 |            19,686,538 |       146.591 |            234.658 |
| `mul_runtime_test` |        2,423,340,257 |           38,593,241 |               242,890 |        99.520 |              2.987 |
| `slice_trace_test` |        1,631,667,427 |          177,715,908 |             1,201,712 |        99.044 |             12.770 |

These local measurements use Intel Mac and Clang with four allowed workers (three selected cases). They are not hosted
CI wall-time predictions. The remaining driver trace still dominated analysis, so a four-group split was prototyped. It
reduced per-log size but required compiling four embedded compilers instead of one. The unchanged numeric group alone
took 248.693 seconds to build/run plus 144.822 seconds to analyze, exceeding the unsplit case's combined 381.249
seconds. The CLI group's build/run also took 223.724 seconds. This is not proof that splitting loses on every host, but
it does not establish the benefit needed to justify additional test-build work.

**Point 4 decision: retain the unsplit harness.** The trace size after explicit inputs is close to the earlier CI
baseline, and the local split trial did not demonstrate a wall-time improvement. The final change preserves every test
body and all 60 existing calls, with only native argument construction changed. No cases, exclusions, checks or trace
parallelism settings were changed. A later split would need an execution/build strategy that demonstrates a net gain.

`stage1_support_args` retains its default complete compiler ABI. Test runners use an explicit dependency declaration for
`preparation_support.c`, shared by normal, aggregate trace and single-case trace entrypoints. Other implementation tests
and two auxiliary token/emitter harnesses omit that unit. This preserves upstream flags and avoids a new object cache or
cache-invalidation policy. An initial local array-test probe took 5.41/5.02 seconds with preparation C versus 3.22/2.66
seconds with the two required support units; these are illustrative, not timing assertions.

Six of the 47 native implementation tests require preparation support. The other 41 omit its C compilation in both the
normal run and the default trace sweep, avoiding 82 compilations per `test-all` invocation.

## Final Validation

The clean full L1 run passed with 81 normal tests, environment stackability, all four examples, and all 46 default trace
cases. Every trace case reported zero leaked objects and strings. The default sweep emitted 4,776,160,249 bytes and
32,182,668 events. The three affected cases measured:

| Test               |   Trace bytes |     Events | Build/run (s) | Analyzer (s) |
| ------------------ | ------------: | ---------: | ------------: | -----------: |
| `mul_runtime_test` |    38,610,141 |    242,990 |       274.345 |       25.942 |
| `slice_trace_test` |   177,715,908 |  1,201,712 |       194.627 |      102.393 |
| `l1c_lib_test`     | 2,916,765,425 | 19,686,327 |       500.920 |     1366.960 |

Command from `l1/`:

```bash
UV_CACHE_DIR=/private/tmp/dea-ci-uv-cache L0_CC=clang L1_CC=clang L1_TEST_JOBS=4 L1_TRACE_TEST_JOBS=4 make clean test-all
```

The local compiler was Apple Clang 17.0.0 (`clang-1700.6.4.2`). This full validation took 54m22s. Local wall times
varied substantially: the same driver case took about 381 seconds in the earlier focused run versus 1,868 seconds here,
while trace bytes and event counts stayed effectively unchanged. The analyzer remained active during the long tail.
These measurements establish removed test work and successful validation; they do not establish a post-change hosted-CI
wall-time improvement. No hosted workflow was dispatched.

The modified slow math trace additionally passed with zero leaked objects and strings. It emitted 3,675,893,063 bytes
and 25,073,581 events, with 841.295 seconds to build/run and 2,224.272 seconds to analyze. It started after only three
default cases remained, keeping at most four test cases active. The default sweep excludes this case, so it was run
explicitly from `l1/`:

```bash
L0_CC=clang L1_CC=clang L1_TRACE_TEST_JOBS=1 ../.venv/bin/python compiler/stage1_l0/scripts/run_trace_tests.py math_runtime_compile_test
```

The finalization reused these passing results: all 19 changed code/test files retained their recorded hashes, with only
documentation changed after validation. Active and staged ADR Impact checks, staged whitespace checks and root
pre-commit passed. No production compiler or runtime source, trace exclusion, dependency or toolchain selection changed
during finalization.

## Non-Goals

- Changing native cache keys, full semantic graph validation, invalidation, diagnostics or compiler behavior.
- Reducing coverage by adding trace exclusions or disabling checks.
- Investigating failures on other CI platforms.
- Dispatching workflows or pushing commits.

The separate [l1/work/plans/features/closed/2026-09-13-warm-preparation-validation-reuse-noref.md][warm-validation]
tracks the future production design question (point 6).

## Verification Criteria

- All existing functional assertions remain covered and ordinary archive-based runtime tests do not invoke automatic
  preparation. TinyCC retains its automatic raw-object selection because platform archives cannot substitute for its
  distinct Darwin object format.
- Dedicated automatic consumers cover cold generation, warm reuse and runtime-only consumption.
- Support selection preserves required symbols and avoids preparation C compilation for unrelated implementation tests.
- The default L1 `test-all` tier passes, including the full default trace sweep; explicitly run the modified slow math
  trace case because the default sweep omits it.
- Record the measurement checkpoint and the resulting split/no-split decision.
- Staged whitespace, ADR Impact and root pre-commit checks pass before the local commit.

[warm-validation]: ../../features/2026-09-13-warm-preparation-validation-reuse-noref.md
