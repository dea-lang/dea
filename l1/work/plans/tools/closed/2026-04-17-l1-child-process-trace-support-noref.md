# Tool Plan

## Add child-process trace support for L1 Stage 1 runtime fixtures

- Date: 2026-09-24
- Status: Completed
- Title: Add child-process trace support for L1 Stage 1 runtime fixtures
- Kind: Tooling
- Severity: Medium
- Stage: L1
- Subsystem: Test runner / trace analysis / compiler driver tests
- Modules:
  - `Makefile`
  - `compiler/stage1_l0/scripts/run_trace_tests.py`
  - `compiler/stage1_l0/scripts/test_runner_common.py`
  - `compiler/stage1_l0/tests/fixtures/math_runtime/`
- Test modules:
  - `compiler/stage1_l0/tests/l1c_stage1_child_trace_runner_test.py`
  - `compiler/stage1_l0/tests/math_test.l0`
  - `compiler/stage1_l0/tests/math_runtime_compile_test.l0`
- Related:
  - `l1/work/plans/features/closed/2026-04-14-l1-std-math-wide-integer-followup-noref.md`
- Repro: `make test-stage1-trace-children`

## Summary

`math_runtime_compile_test` exercises math runtime fixtures by calling `l1c_lib.run_with_argv(...)` from inside the test
process. When the outer test is run through `make test-stage1-trace`, the trace covers the parent test process and the
in-process compiler work performed by those nested `run_with_argv(...)` calls.

That is useful compiler-driver coverage, but it does not provide clean ARC/memory trace coverage for the child fixture
executables themselves. Passing `--trace-memory` and `--trace-arc` into nested `--run` calls directly would mix child
stderr trace events into the parent trace stream, making analysis noisy and potentially ambiguous.

This plan adds first-class runner support for child-process trace fixtures so child executable traces are captured and
analyzed independently.

## Current State

1. `run_trace_tests.py` traces one top-level `.l0` test process at a time.
2. `math_test.l0` contains pure `std.integer` helper checks and is suitable for the default trace suite.
3. `math_runtime_compile_test.l0` contains nested compile/run fixture checks and is intentionally slow under trace.
4. Nested `run_with_argv(...)` calls compile child fixtures in-process, so parent trace logs include compiler pipeline
   allocations and cleanup for those nested compiles.
5. The generated child fixture executables are launched separately by the build driver and are not currently analyzed as
   independent trace subjects.

## Goal

1. Add a trace-runner mode for child runtime fixtures that captures each child executable trace separately.
2. Keep parent and child trace logs isolated so `check_trace_log.py` never has to reason about interleaved trace
   streams.
3. Provide a focused child trace target with explicit fixture selection.
4. Include the inexpensive declared child fixtures in `make test-all`, while keeping slow parent traces opt-in.

## Proposed Shape

1. Add fixture metadata for tests that need child executable tracing.
2. Extend the trace runner so it can:
   - build or run the fixture with trace flags enabled,
   - capture child stdout/stderr into per-fixture artifact files,
   - run `check_trace_log.py` against each child trace independently,
   - report parent and child trace failures separately.
3. Keep `math_runtime_compile_test` as an integration test for nested compiler-driver behavior.
4. Add direct child-trace coverage for representative math runtime fixtures rather than relying on nested stderr mixing.
5. Run both declared child fixtures from `make test-all`, independently of parent `TESTS` selectors; retain
   `make test-stage1-trace-children` for focused fixture selection.

## ADR Impact

- Decision: Isolate parent and child trace streams and include inexpensive declared children in full validation.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This is a narrow verification-tool arrangement that does not alter language, compiler, runtime, CLI, or
    distribution architecture.

## Non-Goals

- changing `std.integer` behavior
- changing normal `make test-stage1` fixture semantics
- making the slow parent `math_runtime_compile_test` trace part of default full validation
- merging parent and child trace logs into one analyzer input
- adding general subprocess tracing outside the Stage 1 trace-test runner

## Verification Criteria

1. `make -C l1 test-stage1-trace TESTS="math_test"` traces only the fast pure helper test and passes.
2. `make -C l1 test-stage1-trace-all TESTS="math_runtime_compile_test"` still covers the parent nested compiler-driver
   path.
3. A new explicit child-trace command or metadata path traces selected math runtime child fixtures as independent
   analyzer inputs.
4. Child runtime trace failures identify the fixture name and child trace artifact path.
5. Parent trace logs and child trace logs remain separate files.
6. `make -C l1 test-all` runs both declared child fixtures even when `TESTS` selects parent tests, and still skips the
   intentionally slow parent trace by default.

## Completion

`run_trace_tests.py --children` builds each declared successful L1 math fixture with both trace flags, executes the
resulting binary directly, and analyzes only its stderr. The metadata requires ARC events from `wide_math_main` and both
memory and ARC events from `math_int_trace_main`; zero-event logs fail even when the trace checker reports no errors.
Build output, child output, trace logs, and analyzer reports remain separate under a unique run directory. Launch,
build, execution, analyzer, and coverage failures identify the fixture and retain their artifacts.

The focused child target is also included in full validation through a child runner invocation after the parent suite.
The parent `math_runtime_compile_test` still tests nested compiler-driver behavior, including expected-panic fixtures,
and the default trace suite continues skipping its slow parent trace. Fast subprocess regressions cover child selection,
host-specific launch paths, native runtime inputs, stream isolation, parallel artifacts, missing event families,
analyzer leaks, failures, and artifact retention.

Focused validation passed with `make test-stage1-trace-children`, individual child selections,
`make test-stage1-trace TESTS="math_test"`, and `make test-stage1-trace-all TESTS="math_runtime_compile_test"`. The
complete local `make -C l1 test-all` gate passed, including 84 normal Stage 1 tests and 46 default trace tests. The
Docker default trace sweep also passed all 46 cases, and the Docker child target passed both fixtures with positive
memory and ARC counts and no leaks. The four-worker Docker normal-test aggregate passed 82 of 84 cases; its two
resource-sensitive failures (`runtime_build_config_test.py` and `runtime_quarantine_asan_test.py`) both passed when
rerun individually in Docker with one worker.

The initial opt-in policy was amended after measuring the real Linux child runs: each fixture built in roughly four to
five seconds, executed in milliseconds, and analyzed in under a second. Full validation now runs both children after the
existing suites; `test-ci` and `test-docker` inherit this coverage through `test-all`. The standalone child target still
accepts fixture selectors, while parent `TESTS` selections do not reach the aggregate child invocation. Existing passing
local and Docker child runs and parent suite results supply execution evidence; Make dry runs verify the new aggregate
wiring without repeating those suites.
