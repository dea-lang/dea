# Tool Plan

## Establish explicit validation tiers and reduce local test cost

- Date: 2026-10-01
- Status: Completed
- Title: Establish repo-wide development, extended, and CI validation tiers and reduce local L1 test cost
- Kind: Tooling
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - Root test orchestration and target naming
  - L0 test target naming
  - L1 local and CI test composition
  - Unified CI target routing
  - Agent and contributor validation guidance
- Origin: Root monorepo test and CI policy, prompted by L1 validation cost observed in Unified CI and local development.
- Porting rule: The tier names and intent are shared repository policy. Each language level may compose those tiers
  differently according to its own test costs and architecture. L1 receives the substantive cost reclassification in
  this plan; L0 changes target naming without requiring an equivalent suite restructuring.
- Target status:
  - Root test orchestration and target naming: Implemented
  - L0 test target naming: Implemented
  - L1 local and CI test composition: Implemented
  - Unified CI target routing: Implemented
  - Agent and contributor validation guidance: Implemented
- Subsystem: Make test orchestration / test runners / GitHub Actions / developer and agent workflow
- Modules:
  - `Makefile`
  - `l0/Makefile`
  - `l1/Makefile`
  - `.github/workflows/ci.yml`
  - `.github/workflows/l0-ci.yml`
  - `AGENTS.md`
  - `.github/copilot-instructions.md`
  - `l0/AGENTS.md`
  - `l1/AGENTS.md`
  - `MONOREPO.md`
  - `l0/README.md`
  - `l1/README.md`
  - `CLAUDE.md`
  - `CONTRIBUTING.md`
  - `docs/project-status.md`
  - `l1/docs/project-status.md`
  - `l1/docs/reference/architecture.md`
  - `.agents/skills/finalize-dea-work/SKILL.md`
  - `l1/compiler/stage1_l0/scripts/run_tests.py`
  - `l1/compiler/stage1_l0/scripts/run_trace_tests.py`
  - `l1/compiler/stage1_l0/scripts/test_runner_common.py`
  - `l1/compiler/stage2_l1/scripts/run_tests.py`
  - `l1/compiler/stage2_l1/scripts/run_trace_tests.py`
  - `l1/compiler/stage2_l1/scripts/test_runner_common.py`
- Test modules:
  - `l1/tests/test_env_stackability.py`
  - `l1/tests/test_docker_wine.py`
  - `l1/tests/test_stage2_tooling.py`
  - `l1/tests/test_bootstrap_identity.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_trace_runner_common_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_reuse_report_test.py`
  - `l1/compiler/stage1_l0/tests/mul_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/mul_runtime_compile_test.l0`
  - `l1/compiler/stage1_l0/tests/mul_runtime_overflow_test.py`
  - `l1/compiler/stage2_l1/tests/mul_runtime_test.l1`
  - `l1/compiler/stage2_l1/tests/mul_runtime_compile_test.l1`
  - `l0/tests/test_make_dea_build_workflow.py`
  - `l0/tests/test_dist_tools_lib_fallback.py`
- Related:
  - `l1/work/plans/tools/closed/2026-09-13-preparation-test-cost-noref.md`
  - `work/plans/bug-fixes/closed/2026-08-24-shared-trace-io-amplification-noref.md`
  - `l1/work/plans/features/closed/2026-09-13-warm-preparation-validation-reuse-noref.md`
  - `docs/decisions/0004-monorepo-directory-structure.md`
- Repro: `L1_TEST_JOBS=4 L1_TRACE_TEST_JOBS=4 make -C l1 test-extended`

## Summary

Completed on October 1, 2026. Repository-wide validation now uses `test` for development, `test-extended` for broader
local confidence, and level-specific `test-ci` for exhaustive hosted coverage. The removed `test-all` target has no
compatibility alias. L0 preserves its extended suite composition; L1 separates costly integration from routine checks.

L1's fast tier measured 4m07s on Linux. The final Linux extended tier measured 16m31s, approximately 17 minutes, which
satisfies the accepted scope despite the initial directional 10-to-15-minute goal. Exhaustive coverage is preserved;
there is no established exhaustive-tier speedup.

## Final Validation Contracts

Root `test` and `test-extended` delegate to the corresponding target in each registered level. L0 `test-extended`
retains `test` plus its dedicated Stage 2 trace sweep. Standalone L0 CI and Unified CI use `test-extended` for L0;
Unified CI uses `test-ci` for L1. No root `test-ci` aggregate was added.

| L1 tier         | Composition                                                                                                                                                                                                       |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test`          | Eight Stage 1 smoke tests, two Stage 2 smoke tests, parity, examples, Stage 2 tooling, and Docker/Wine runner regressions.                                                                                        |
| `test-extended` | Both local-normal stage suites, parity, examples, tooling, and Docker/Wine runner regressions; excludes CI-only normal cases, environment reconstruction, dedicated traces, child fixtures, and triple bootstrap. |
| `test-ci`       | Extended validation with CI-only normal cases included, environment/bootstrap integration, both default trace sweeps, both child-fixture suites, and triple bootstrap.                                            |

Stage 1 smoke membership is `array_test`, `parser_test`, `analysis_test`, `expr_types_test`, `interface_test`,
`backend_test`, `c_emitter_test`, and `driver_test`. Stage 2 uses `array_test` and `parser_test`. Parity ignores only
cache-dependent stdlib preparation progress while preserving diagnostic output.

### Cost classification and direct selection

Normal runners use explicit `CI_ONLY_NORMAL_STAGE1_TESTS` and `CI_ONLY_NORMAL_STAGE2_TESTS` metadata. Default discovery
excludes classified cases; `--include-ci-only` includes them. Explicit names or file selectors bypass cost exclusion,
remain limiting even with CI inclusion enabled, and reject unknown or ambiguous selectors. Logs identify excluded or
included cases, and Make output marks each exhaustive category without duplicating normal-suite execution.

Both stages classify these normal cases as CI-only:

- `math_runtime_compile_test`, `mul_runtime_compile_test`, and `slice_trace_test`.
- `l1c_stage1_arc_trace_regression_test.py`.
- `l1c_stage1_installed_preparation_test.py` and `l1c_stage1_preparation_test.py`.

Stage 1 additionally classifies `preparation_identity_test.py` and `preparation_ownership_test.py` as CI-only. These
cases exercise tracing, embedded compiler construction, installed inputs, identity matrices, recovery, or concurrency;
core semantic and backend suites remain local regardless of their duration.

Multiplication arithmetic and boundaries remain in `mul_runtime_test`. Shared `mul_runtime_overflow_test.py` runs all
six original overflow fixtures through the already-built subject and requires the multiplication-overflow panic message,
not merely a nonzero exit. The stage fixture copies are identical, and Stage 2/triple-bootstrap use the shared Python
subject-selection contract. CI-only `mul_runtime_compile_test` retains all six embedded-driver compilations and their
ownership coverage.

Local `l1c_stage1_managed_preparation_test.py` retains representative cold/warm preparation, interface selection,
opt-outs, native configuration, and standalone linking. The full installed-input and recovery/concurrency matrices
remain complete and directly selectable. `link_driver_test`, including its 10,000-module chain, `l1c_lib_test`,
including its four traced executions, `preparation_test`, and `compile_driver_test` remain local: their direct
correctness coverage is valuable, and splitting them would add compiler-containing harnesses without enough execution
savings.

### Independent trace policy and validation guidance

Dedicated trace discovery includes trace-eligible CI-only normal cases, including `slice_trace_test` and
`mul_runtime_compile_test`. Normal cost classification never removes trace coverage. Slow trace cases such as
`math_runtime_compile_test` remain opt-in through `*-trace-all` or explicit `TESTS` selection. Default discovery has 47
parent cases per stage; slow-inclusive discovery has 48. CI runs both declared child fixtures per stage independently of
parent selectors.

Current contributor/agent guidance, Make help, README files, workflows, and active plans use the new names. Historical
validation records retain the target names actually used. Development defaults to `test`; substantial refactors use
`test-extended`. Trace-, bootstrap-, preparation-, and environment-sensitive changes use relevant focused targets;
exhaustive hosted equivalence uses L1 `test-ci`. Passing higher-tier results can satisfy included lower tiers only for
unchanged code, build, dependencies, generated sources, test inputs, and toolchain selection.

## Measurement Methods and Findings

### Hosted baseline and tier measurements

Hosted times are the nested L1 `Run L1 Make target` action durations: complete Make targets and prerequisites are
included; queue time, workflow setup, and preparation-report upload are excluded. The
[September 27 baseline](https://github.com/dea-lang/dea/actions/runs/36348673934) measured exhaustive L1 validation:

| Platform       | Baseline `test-ci` |
| -------------- | -----------------: |
| Linux x86_64   |             39m35s |
| macOS ARM64    |             51m28s |
| macOS Intel    |             90m51s |
| Windows UCRT64 |             76m24s |

On Linux, normal Stage 1/2 suites took approximately 6m01s/8m08s, Stage 2 construction 1m07s, environment stackability
2m26s, trace sweeps 3m30s/6m49s, and triple bootstrap 10m53s. Traces plus triple bootstrap consumed approximately 21
minutes, over half the lane. Separate preparation-cost evidence recorded a 54m22s local Intel Mac extended run and
multi-gigabyte trace workloads, supporting a tier-composition change.

Linux hosted measurements used `ubuntu-latest` x86_64 and GCC. The post-profiling jobs used `/usr/bin/gcc` (Ubuntu GCC
13.3.0) for `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`, with four normal and trace workers.

| Measurement                                        |       Time |
| -------------------------------------------------- | ---------: |
| Fast `test`                                        |  4m07.327s |
| Extended before harness split, two-sample mean     | 18m12.223s |
| CI before harness split and trace-selection repair | 34m30.881s |
| Extended after harness split                       | 16m11.379s |
| CI after harness split and trace-selection repair  | 51m19.294s |

All listed jobs passed. The post-split extended sample is approximately 11.1% faster than the earlier mean. CI includes
the restored slice trace and separate embedded-overflow harness; its increased time cannot be attributed between extra
coverage and runner variance from these samples. The earlier CI run had 45 parent trace cases per stage and does not
prove the final trace union. No exhaustive-tier speedup is claimed.

### Separate harness construction from execution

Local profiling used an isolated Linux x86_64 Docker container with four CPUs, Python 3.14.7, and `/usr/bin/gcc` (Debian
GCC 12.2.0) selected for all three compiler roles. Compiler/runtime artifacts were built there with default basic
runtime checks and quarantine settings; network access was disabled. These timings are not directly comparable with
hosted samples.

The probe used each runner's normal command and sanitized environment, replaced `--run` with `--build` to a private
output path, and executed the resulting harness separately. The six original harnesses were measured serially; shared
Stage 2 C support preparation preceded the timed build. All builds and executions passed.

| Stage | Original test      | Harness build | Harness execution |
| ----: | ------------------ | ------------: | ----------------: |
|     1 | `mul_runtime_test` |       52.029s |            0.665s |
|     2 | `mul_runtime_test` |      193.737s |            0.762s |
|     1 | `link_driver_test` |       50.864s |            1.520s |
|     2 | `link_driver_test` |      162.262s |            1.517s |
|     1 | `l1c_lib_test`     |       55.161s |           11.689s |
|     2 | `l1c_lib_test`     |      204.286s |           11.621s |

With the same probe and compiler artifacts, split multiplication coverage measured:

| Stage | Arithmetic build | Arithmetic execution | Six CLI overflow cases | Combined local coverage |
| ----: | ---------------: | -------------------: | ---------------------: | ----------------------: |
|     1 |           1.054s |               0.001s |                 0.794s |                  1.849s |
|     2 |           0.611s |               0.002s |                 0.764s |                  1.376s |

The split removes approximately 244 seconds of serial harness work across both stages. It does not imply the same
aggregate saving: normal suites use four workers and include prerequisites and other tests. The container aggregate used
`L1_TEST_JOBS=4 L1_TRACE_TEST_JOBS=4 make -C l1 test-extended`, with artifacts prepared and normal Make prerequisites
included.

### Diagnostic findings

The container extended aggregate failed after 32m15.697s in unchanged Stage 2 `vector_aliasing_test.py` ASan startup:
Stage 1 passed 78/78 and Stage 2 passed 63/64. An isolated execution reproduced the timeout. An empty C executable built
with `/usr/bin/gcc -fsanitize=address` timed out in 13/40 default PIE executions with repeated
`AddressSanitizer:DEADLYSIGNAL`; all 40 non-PIE executions passed. The vector test's checked/unchecked matrix passed in
39.837s with a temporary `L1_ASAN_CC` wrapper adding `-fno-pie -no-pie`. These controls indicate container ASan startup
trouble; they do not turn the failed aggregate into a passing timing. Repository compiler/sanitizer policy is unchanged,
and hosted Linux validation passed with default sanitizer settings.

The [Windows reporter failure](https://github.com/dea-lang/dea/actions/runs/36770085187/job/110074016488) came from
fixture isolation. Patching `reporter.subprocess.run` changes the shared subprocess module; uncached
`platform.machine()` can invoke `ver` through `subprocess.check_output`. The compiler-only callback received the string
`"ver"`, interpreted its first character as an executable, and failed before preparation scenarios began. Forcing that
lookup reproduced the defect; deterministic platform metadata was the passing control. Real Windows preparation
reporting passed, distinguishing the fixture failure from a production preparation regression.

`ReporterTest.exercise()` now mocks `Windows`/`AMD64` metadata and clears inherited `MSYSTEM`, preserving compiler-argv
assertions and preparation scenarios. `test_platform_discovery_is_isolated` makes real OS/architecture lookup raise,
requires controlled report metadata, and fails if either mock is removed. This prevents platform caches or non-Windows
hosts from masking the defect. All 14 reporter methods passed on macOS x86_64/Python 3.14.7, as did the focused Stage 1
normal-runner selector; the final Windows aggregate validates the repair on Windows. Production reporter behavior is
unchanged.

## Validation Results and Conclusions

Runner regressions cover actual default discovery, every explicit CI-only selector, complete CI inclusion, retained
local overflow/preparation checks, native support dependencies, and default/explicit-slow/slow-inclusive trace selection
and logging through both runner entrypoints. Local-normal discovery has 78 Stage 1 and 64 Stage 2 cases; CI-inclusive
discovery has 86 and 70.

Focused Linux validation used four workers and the prepared profiling artifacts. For both stages, `run_tests.py`
selected
`--include-ci-only mul_runtime_compile_test l1c_stage1_installed_preparation_test.py l1c_stage1_preparation_test.py`:
all three cases passed. `run_trace_tests.py` selected `mul_runtime_test mul_runtime_compile_test slice_trace_test`: all
three passed with zero object/string leaks. All six local CLI overflow cases passed in both stages on Linux GCC and
macOS x86_64 Apple Clang 17.0.0 (clang-1700.6.4.2), with all three compiler roles explicitly selected and
`--no-default-config` verified. Parity, examples, Docker/Wine, and final runner/tooling regressions also passed locally.

The post-split Linux `make -C l1 test-ci` result validates all 86/70 normal cases, environment stackability, both
47-case default parent trace sweeps, two child fixtures per stage, and triple bootstrap with 137 identical retained C
translation units. Final cross-platform `make -C l1 test-extended` results, including the repaired reporter fixture,
are:

| Platform              | GCC version | Extended time | Result |
| --------------------- | ----------- | ------------: | ------ |
| Linux x86_64          | 13.3.0      |    16m30.603s | Passed |
| Windows UCRT64 x86_64 | 16.2.0      |    25m44.443s | Passed |
| macOS ARM64           | 15.3.0      |    23m41.175s | Passed |
| macOS Intel           | 15.3.0      |    31m02.219s | Passed |

All three compiler roles selected each lane's listed GCC version. Each lane passed 78/64 local-normal cases, parity,
four examples, six Docker/Wine regressions, and 18 tooling/bootstrap regressions. Documentation validation and ADR
Impact checks also passed. The earlier exhaustive evidence remains applicable to unchanged CI-only, environment, trace,
child-fixture, and fixed-point inputs; the repaired reporter is covered by the final matrix.

The fast tier meets the directional five-minute goal. Approximately 17 minutes for Linux extended validation is accepted
as sufficient for this effort; the initial 10-to-15-minute range is not a hard threshold. Expensive correctness coverage
remains accessible directly and in CI. No further classification or timing work is required for closure, and there is no
remaining in-scope implementation or validation work.

## ADR Impact

- Decision: Introduce repository-wide `test`, `test-extended`, and level-specific `test-ci` validation semantics and
  classify costly L1 tests by workflow role.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This changes internal repository test orchestration, naming, CI composition, and developer guidance
    without changing the language, compiler architecture, runtime contract, artifact format, or public Dea behavior. The
    tier policy remains maintainable repository tooling rather than a product architecture decision.
