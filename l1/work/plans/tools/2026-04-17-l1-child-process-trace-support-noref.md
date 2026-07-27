# Tool Plan

## Add child-process trace support for L1 Stage 1 runtime fixtures

- Date: 2026-04-17
- Status: Draft
- Title: Add child-process trace support for L1 Stage 1 runtime fixtures
- Kind: Tooling
- Severity: Medium
- Stage: L1
- Subsystem: Test runner / trace analysis / compiler driver tests
- Modules:
  - `compiler/stage1_l0/scripts/run_trace_tests.py`
  - `compiler/stage1_l0/scripts/test_runner_common.py`
  - `compiler/stage1_l0/scripts/check_trace_log.py`
  - `compiler/stage1_l0/tests/math_runtime_compile_test.l0`
  - `compiler/stage1_l0/tests/fixtures/math_runtime/`
- Test modules:
  - `compiler/stage1_l0/tests/math_test.l0`
  - `compiler/stage1_l0/tests/math_runtime_compile_test.l0`
- Related:
  - `l1/work/plans/features/closed/2026-04-14-l1-std-math-wide-integer-followup-noref.md`
- Repro: `make test-stage1-trace TESTS="math_runtime_compile_test"`

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
3. Make slow fixture trace coverage explicit and opt-in.
4. Preserve the fast default trace suite for ordinary development and `make test-all`.

## Proposed Shape

1. Add fixture metadata for tests that need child executable tracing.
2. Extend the trace runner so it can:
   - build or run the fixture with trace flags enabled,
   - capture child stdout/stderr into per-fixture artifact files,
   - run `check_trace_log.py` against each child trace independently,
   - report parent and child trace failures separately.
3. Keep `math_runtime_compile_test` as an integration test for nested compiler-driver behavior.
4. Add direct child-trace coverage for representative math runtime fixtures rather than relying on nested stderr mixing.
5. Keep child-process trace fixtures behind `make test-stage1-trace-all` or another explicit opt-in target until runtime
   cost is known.

## ADR Impact

- Decision: Keep child-process tracing as an opt-in test-runner facility with isolated parent and child trace streams.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This is a narrow verification-tool arrangement that does not alter language, compiler, runtime, CLI, or
    distribution architecture.

## Non-Goals

- changing `std.integer` behavior
- changing normal `make test-stage1` fixture semantics
- making slow child trace fixtures part of `make test-all`
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
6. The default `make -C l1 test-all` workflow remains free of intentionally slow child trace coverage.
