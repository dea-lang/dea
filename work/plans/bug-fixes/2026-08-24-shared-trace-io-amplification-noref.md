# Bug Fix Plan

## Eliminate shared trace I/O amplification without weakening ordering

- Date: 2026-08-24
- Status: In Progress (implementation complete; hosted verification pending)
- Title: Eliminate ARC and memory trace I/O amplification across runtimes and test runners
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 runtime and Stage 2 trace tooling
  - L1 runtime and Stage 1 trace tooling
- Origin: Settle the trace-output policy in the L0 header runtime and Stage 2 trace tooling, because the L1 Stage 1
  `.l0` trace sweep executes through that runtime, then adapt the same policy to L1's compiled runtime boundary.
- Porting rule: Keep event text, flush boundaries, failure behavior, and streaming-capture semantics aligned. Preserve
  the intentional implementation difference between L0's header-only runtime and L1's compiled runtime archives.
- Target status:
  - L0 runtime and Stage 2 trace tooling: Implemented
  - L1 runtime and Stage 1 trace tooling: Implemented
- Subsystem: Runtime tracing / Test capture / Trace analysis / Cross-platform CI
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l0/compiler/stage2_l0/scripts/test_runner_common.py`
  - `l0/compiler/stage2_l0/scripts/run_trace_tests.py`
  - `l0/compiler/stage2_l0/scripts/run_test_trace.py`
  - `l0/compiler/stage2_l0/scripts/check_trace_log.py`
  - `l0/docs/specs/runtime/trace.md`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_trace.c`
  - `l1/compiler/shared/runtime/src/dea_rt_panic.c`
  - `l1/compiler/shared/runtime/src/dea_rt_sys.c`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l1/compiler/stage1_l0/scripts/test_runner_common.py`
  - `l1/compiler/stage1_l0/scripts/run_trace_tests.py`
  - `l1/compiler/stage1_l0/scripts/run_test_trace.py`
  - `l1/compiler/stage1_l0/scripts/check_trace_log.py`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/Makefile`
  - `.github/workflows/ci.yml`
  - `.github/workflows/l1-ci.yml`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_trace_runtime.py`
  - `l0/compiler/stage1_py/tests/cli/test_stage2_trace_log_checker.py`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_trace_runner_common_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_trace_runner_common_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/runtime_build_config_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_trace_policy_test.py`
- Related:
  - `l0/work/plans/bug-fixes/closed/2026-04-01-stage2-windows-trace-runner-pipe-capture-noref.md`
  - `l0/docs/decisions/0025-runtime-trace-source-provenance.md`
  - `l1/docs/decisions/0027-runtime-archive-and-trace-selection-boundary.md`
  - `l1/work/plans/tools/2026-04-17-l1-child-process-trace-support-noref.md`
  - `l1/docs/project-status.md`
- Repro: On hosted Windows with four workers, run `make -C l1 test-stage1-trace TESTS="l1c_lib_test"`; the traced
  integration test takes roughly 74 minutes in the observed CI run, versus roughly 4 minutes on hosted Linux.

## Summary

The full L1 Stage 1 ARC/memory trace sweep is pathologically slow on hosted Windows. The observed 44-test trace phase
took 85 minutes 37 seconds on Windows and 5 minutes 59 seconds on Linux. The ordered-output interval ending at
`l1c_lib_test` accounts for 74 minutes 24 seconds on Windows and 4 minutes 1 second on Linux. Normal-suite execution is
much closer at 6 minutes 15 seconds and 4 minutes 13 seconds, respectively. Trace work therefore explains about 96% of
the total Windows/Linux job difference.

The current hosted-CI mitigation is sound but incomplete: Windows runs every normal L1 check plus a focused six-test
trace smoke set, while POSIX hosts retain the full trace sweep. This plan fixes the underlying output path so full
Windows trace coverage can be restored after measured hosted-runner verification. It does not use fewer tests or fewer
workers as the performance mechanism.

## ADR Impact

- Decision: Batch trace output and stream trace artifacts while preserving the existing stream, event format, source
  provenance, and parent/child ordering contracts.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The work removes implementation-level I/O and memory amplification under the existing trace and runtime
    boundaries. It does not change language semantics, trace event meaning, public runtime signatures, archive
    selection, or the source-provenance contract.

## Evidence and Corrected Ownership

| Phase                                            | Hosted Windows | Hosted Linux | Windows/Linux |
| ------------------------------------------------ | -------------: | -----------: | ------------: |
| Whole job                                        |        94m 54s |      12m 14s |          7.8x |
| Toolchain setup                                  |         1m 30s |          17s |          5.3x |
| Normal 67-test suite                             |         6m 15s |       4m 13s |          1.5x |
| 44-test trace suite                              |        85m 37s |       5m 59s |         14.3x |
| Ordered-output interval ending at `l1c_lib_test` |        74m 24s |       4m 01s |         18.5x |

The supplied hosted-CI comparison reports four parallel test workers on both Windows and Linux, so worker count does not
explain the difference.

The hot runtime is easy to misidentify from the L1 tree. `l1/compiler/stage1_l0/scripts/run_trace_tests.py` asks the L0
Stage 2 compiler to compile and run each L1 compiler test, because those tests are `.l0` programs. The dominant
`l1c_lib_test` trace therefore comes from `l0/compiler/shared/runtime/l0_runtime.h`. The equivalent macros in
`l1/compiler/shared/runtime/include/dea_rt.h` have the same per-event flush behavior and need the same policy for traced
L1 programs, but changing only the L1 archive would not fix this CI regression.

## Current State and Root Cause

1. Each ARC or memory event makes three or four `fprintf(stderr, ...)` calls and then calls `fflush(stderr)`.
2. The explicit per-event flush is intentional. It preserves parent trace ordering before a nested child inherits and
   writes to stderr. Removing it without a replacement would regress the existing recursive-output invariant.
3. `l1c_lib_test.l0` is a 1,654-line compiler integration test that runs about 60 compiler, build, link, and execution
   scenarios. Tracing the outer compiler-test process produces a much larger event stream than ordinary unit tests.
4. The L1 capture helper writes the child output to temporary files, reads both files completely into Python bytes,
   writes the bytes to the named artifacts, and deletes the temporary files. The trace runner then reads the entire
   trace again even on success before launching the analyzer, which scans it once more.
5. The L0 capture helper retains the entire stdout and stderr streams in `subprocess.PIPE` buffers, writes the complete
   byte strings to artifacts, and then follows the same unconditional trace-text load. Its analyzer also materializes
   the complete trace text and parsed event list, unlike the already-streaming L1 analyzer.
6. Every successful worker retains `trace_text` in its `TraceResult` until ordered emission reaches that case. Large
   completed results can therefore remain resident behind an earlier straggler.
7. The trace runner publishes results in test-name order. Once later tests finish, no further output appears until
   `l1c_lib_test` completes, which makes the long-running test look like a general hang and hides useful per-test
   timing.
8. MinGW CRT flushes, NTFS writes, and host filesystem filtering magnify the event-level I/O pattern. The available CI
   evidence isolates the trace path but does not justify attributing exact shares to those Windows components.

## Required Invariants

1. The trace stream remains `stderr`; prefixes, key/value fields, source locations, and one-complete-event-per-line
   formatting remain byte-compatible.
2. Default interactive or explicitly durable tracing retains event-level visibility. Bulk trace runners may select a
   documented block-buffered policy for throughput.
3. Buffered parent trace bytes are flushed before `rt_system()` launches a child, before panic/abort diagnostics, on an
   explicit stderr flush, and during normal process termination.
4. A direct C trace-macro use that has not passed through generated-program runtime initialization falls back to the
   current event-flush behavior.
5. Capture completion remains an EOF boundary, not merely immediate-child exit. A delayed descendant that inherited
   stdout or stderr must finish writing before analysis begins.
6. Successful trace validation must not require Python memory proportional to raw trace size. Analyzer lifecycle maps
   may remain proportional to the number of live pointer identities required for correctness.
7. A failed test retains a complete on-disk trace artifact when artifacts are requested and prints only a bounded
   excerpt in the runner log.
8. Normal non-trace builds and runtime archives remain free of trace buffers, policy checks, and new hot-path work.

## Scope of This Fix

### 1. Establish a measured trace-throughput baseline

1. Record per-test execution time, analyzer time, trace bytes, and parsed event count in the trace runner report.
2. Add a bounded synthetic probe that emits enough trace events to distinguish event-flush and block-buffered behavior
   without making normal validation slow.
3. Measure the probe and `l1c_lib_test` with event and block policies on at least Linux and hosted Windows. Treat event
   formatting, capture, and analysis as separate intervals.
4. Keep the supplied CI timing table as the regression baseline; do not infer unrecorded disk, Defender, or CRT shares.

### 2. Replace unconditional event flushes with an explicit runtime policy

1. Add one startup-selected trace flush policy shared in meaning by L0 and L1. Preserve event flushing as the durable
   default and allow bulk trace runners to select block buffering through a documented environment setting such as
   `DEA_TRACE_FLUSH=block`.
2. Initialize the policy and a fixed-size stderr buffer from `_rt_init_args()` before user module initialization. If
   initialization or `setvbuf()` fails, retain event flushing.
3. Make trace macros flush each event only when the selected policy requires it. Keep the current pre-initialization
   fallback so direct runtime probes and generated-code contract tests remain deterministic.
4. Flush buffered stderr before `rt_system()`, panic and abort output, `rt_flush_stderr()`, and other process-exit paths
   that bypass normal C stream finalization. Preserve the existing parent-before-child regression with the flush moved
   to the process boundary rather than every trace event.
5. Keep L0 trace state header-local for its single-translation-unit runtime. Give L1 one compiled-runtime-owned state
   rather than one buffer per runtime C translation unit; update archive source lists and symbol manifests if an
   internal cross-object helper is required.
6. Document the bulk-capture policy, durability tradeoff, and explicit event-flush rerun path in
   [l0/docs/specs/runtime/trace.md][trace-spec].

### 3. Stream capture directly into final artifacts

1. Replace whole-stream `subprocess.run(..., PIPE)` materialization and the L1 temporary-file copy with a shared
   semantic model: `Popen` pipes drained concurrently in fixed-size chunks into the final stdout and stderr artifact
   files.
2. Join both drainers through EOF after the immediate process exits. This preserves the delayed-descendant guarantee
   established by the earlier Windows pipe-capture fix while bounding Python memory.
3. Return process status and artifact paths rather than duplicate stdout/stderr byte strings. Do not read a successful
   trace into `TraceResult`.
4. On process failure, read a bounded leading or trailing excerpt for console output and leave the full artifact on disk
   according to the runner's artifact-retention policy.
5. Add parallel delayed-descendant regression cases to both L0 and L1 helpers so neither implementation regresses to a
   file-visibility race or an unbounded pipe buffer.

### 4. Make analysis and progress streaming

1. Port the L1 line-iterator analyzer shape to L0, preserving exact error, warning, operation-count, and leak-triage
   semantics.
2. Keep one analyzer pass over each successful trace. Do not pre-read the trace merely to decide whether analysis can
   run.
3. Keep analyzer reports small and bounded by `--max-details`; parse only the report summary needed for the runner's
   one-line success output.
4. Emit completion progress and elapsed time when each future completes rather than withholding every later result
   behind the next test-name slot. Preserve deterministic final counts and a selection-ordered failed-test summary.
5. Include the trace artifact path and byte count for failures so a long run is diagnosable without verbose mode.

### 5. Restore full hosted-Windows coverage only after verification

1. Keep `test-stage1-trace-smoke` and the current Windows `test-ci` selection while implementing and measuring the
   runtime and runner changes.
2. Require at least two comparable hosted-Windows `test-all` runs with four workers and the final implementation before
   changing the Windows default back to the full trace sweep.
3. Restore full Windows tracing only if event counts and analyzer results match Linux and the performance criteria below
   are met. Retain the smoke target as a focused developer command.
4. Update `l1/CLAUDE.md` and `l1/docs/project-status.md` when the hosted-CI default changes; do not describe full
   Windows coverage as restored before the measured gate passes.
5. This plan does not authorize a push or workflow dispatch. Any agent-triggered remote verification requires fresh user
   confirmation immediately before the exact remote, branch, and workflow operation.

## Performance and Correctness Criteria

1. The synthetic captured-trace probe uses bounded runner memory and shows a material block-policy improvement on
   Windows; target at least 5x event-generation throughput over event flushing.
2. A successful trace artifact is written once by the capture drain and scanned once by the analyzer. No successful path
   copies or materializes the complete trace in Python.
3. Parent trace events emitted before a synchronous child launch precede that child's stderr; parent events emitted
   after child completion follow it.
4. Panic, abort, explicit stderr flush, normal return, and `rt_exit()` leave complete line-terminated trace events in
   the artifact. Event-flush mode remains available for native-crash archaeology.
5. Delayed inherited grandchild writers remain complete under one and four parallel capture calls on Windows and POSIX.
6. L0 and L1 analyzers report identical counts and outcomes for the same fixture logs, including malformed input,
   negative balances, leaks, pointer reuse, and source locations.
7. On hosted Windows with four workers, the full L1 trace phase is no more than 3x the same-revision hosted-Linux trace
   phase and `l1c_lib_test` no more than 3x its Linux duration. Record absolute times as evidence, but use the ratio for
   the coverage-restoration gate.
8. The focused trace suites, full L0 and L1 trace-inclusive validation, runtime symbol manifests, documentation checks,
   and workflow tests pass.

## Diagnostics

No compiler diagnostic code is introduced. Invalid optional trace-policy environment values should fall back to the
durable event policy and may produce a runner warning; they must not alter generated-program language semantics.

## Non-Goals

1. Changing the textual trace schema, prefixes, source-provenance fields, or analyzer correctness rules.
2. Adding JSON or binary traces, event filtering, sampling, compression, or a general profiling framework.
3. Treating lower worker counts, smaller test selection, Defender exclusions, or runner-local filesystem tuning as the
   durable fix.
4. Splitting nested child executable traces into independent analyzer inputs; that remains owned by
   `l1/work/plans/tools/2026-04-17-l1-child-process-trace-support-noref.md`.
5. Changing normal runtime buffering or stderr behavior when trace instrumentation is disabled.
6. Removing the Windows trace smoke target after full coverage is restored.

## Verification

1. Run direct runtime probes for default event flushing, selected block buffering, pre-initialization fallback, explicit
   flush, panic, normal exit, and parent/child ordering.
2. Run the L0 and L1 trace-runner helper regressions with ordinary, large, delayed-grandchild, and four-way parallel
   streams.
3. Run both trace analyzers against the shared balanced and failing fixture corpus and compare reports.
4. Run focused `l0c_lib_test` and `l1c_lib_test` normal and trace checks, followed by root `make test-all`.
5. Record Linux and hosted-Windows phase, test, byte, and event metrics from the same implementation before applying the
   hosted-Windows coverage-restoration gate.
6. Run `python3 scripts/check_adr_impact.py --all-active`, Markdown formatting, staged whitespace checks, and the
   repository pre-commit gate before closure.

## Implementation Progress

- On 2026-08-27, both runtime targets gained the startup-selected `event`/`block` policy, pre-initialization fallback,
  and explicit process-boundary flushing. The L1 normal archives do not compile or link the trace-policy object.
- Both trace capture helpers now drain stdout and stderr concurrently in 64 KiB chunks directly into final artifacts,
  wait for inherited writers to close the pipes, and return only process status, paths, and byte counts.
- Both full trace runners select block mode by default, analyze successful traces once without pre-reading them, emit
  completion-order timing/size/event progress, bound failure excerpts, and retain selection-order failure summaries.
- The 4,096-event compiled-runtime probe produced byte-identical event/block traces on macOS and measured 0.032435
  seconds in event mode versus 0.014912 seconds in block mode (2.18x). This is local correctness and directional
  throughput evidence, not the hosted-Windows coverage-restoration gate.
- Focused macOS runs passed for L0 `analysis_trace_test` (3.326 seconds run, 0.205 seconds analysis, 815,042 trace
  bytes, 4,969 events) and L1 `analysis_trace_test` (45.474 seconds run, 0.290 seconds analysis, 1,585,946 trace bytes,
  8,735 events).
- The large macOS regressions passed for L0 `l0c_lib_test` (10.842 seconds run, 15.680 seconds analysis, 180,760,923
  trace bytes, 1,074,049 events) and L1 `l1c_lib_test` (192.292 seconds run, 634.432 seconds analysis, 3,635,124,307
  trace bytes, 19,512,089 events). The latter completed through the bounded live-identity analyzer state and its
  temporary artifact was removed after success.
- An independent read-only review found and prompted fixes for missing L1 runtime-header dependencies, a missing traced
  runtime object in the TinyCC direct-object link path, retained balanced-pointer analyzer metadata, and unbounded
  analyzer report sections. Focused regressions cover each correction, and the reviewer found no remaining actionable
  issue after re-review.
- Root `make test-all` passed on macOS after the review fixes, including 56 L0 Stage 2 tests, 33 L0 broad trace tests,
  69 L1 Stage 1 tests, and 44 L1 broad trace tests. The final L1 `l1c_lib_test` trace contained 3,627,828,427 bytes and
  19,511,529 events and completed with zero reported leaks.
- Hosted-Windows `test-all` comparison has not been dispatched because this plan does not authorize remote workflow
  writes. Windows CI therefore intentionally retains the trace smoke selection until two qualifying hosted runs satisfy
  the existing ratio gate.

[trace-spec]: ../../../l0/docs/specs/runtime/trace.md
