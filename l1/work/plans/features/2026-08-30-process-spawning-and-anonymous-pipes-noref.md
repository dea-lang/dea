# Feature Plan

## Add process spawning and anonymous pipes

- Date: 2026-08-30
- Status: Draft
- Title: Add shell-free process spawning, waiting, and anonymous pipe endpoints
- Kind: Feature
- Severity: Medium
- Priority: 2
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0006-process-and-host-services.md`
- Subsystem: Stdlib / runtime / process control / I/O
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/process.l1`
  - `l1/compiler/shared/l1/stdlib/std/pipe.l1`
  - `l1/compiler/shared/l1/stdlib/std/file.l1`
  - `l1/compiler/shared/l1/stdlib/std/stream.l1`
  - `l1/compiler/shared/l1/stdlib/sys/process.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_process.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/process_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/pipe_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_trace_test.l0`
- Related:
  - `l1/work/initiatives/0006-process-and-host-services.md`
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/work/plans/features/2026-08-30-os-error-and-io-results-noref.md`
  - `l1/work/plans/features/2026-08-30-streams-and-buffering-noref.md`
- Repro: `make -C l1 test-stage1 TESTS="process_runtime_test pipe_runtime_test analysis_trace_test"`

## Summary

Replace `std.system::system` as the only child-execution option with a typed, shell-free process API and first-class
anonymous pipe endpoints. The existing shell helper remains available as an explicitly shell-oriented convenience.

## Public Surface

- Process types: `Process`, `ProcessId`, `ExitStatus`, `SpawnOptions`, and `Stdio`.
- Process operations: `spawn`, `wait`, `try_wait`, `terminate`, `kill`, `pid`, `stdin`, `stdout`, and `stderr`.
- Pipe types: `PipeReader`, `PipeWriter`.
- Pipe operations: `create`, `read_some`, `read_exact`, `write_some`, `write_all`, and `close`.

`SpawnOptions` carries an argument vector, environment replacement or overrides, working directory, and standard-stream
routing as inherit, null, file, or pipe.

## Required Semantics

1. The primary API never invokes a shell and never concatenates arguments into a command string.
2. Pipe ends have separate ownership and close behavior.
3. On POSIX, writes to a closed pipe return `BrokenPipe` rather than terminating the process through `SIGPIPE`.
4. Child inheritance is opt-in and limited to explicitly selected endpoints.
5. `wait` is idempotence-defined, and `try_wait` distinguishes running, exited, and failure.
6. `ExitStatus` distinguishes normal exit from signal or host termination where available.
7. `terminate` and `kill` state their platform-strength guarantees without pretending they are equivalent.

## Implementation Phases

1. Implement owned anonymous pipe endpoints and broken-pipe behavior.
2. Define process handles, argument/environment transport, and standard-stream routing.
3. Add spawn and wait/try-wait on POSIX and Windows without a shell.
4. Add termination, kill, and exit-status normalization.
5. Add stream adapters, failure injection, handle-leak checks, and hostile-argument fixtures.

## Non-Goals

- shell grammar, quoting helpers, or replacing explicit `std.system::system`
- pseudo-terminals, interactive terminal control, or Unix job control
- named pipes, Unix-domain sockets, or shared-memory IPC
- process groups, daemonization, privilege changes, or sandbox policy in v1
- asynchronous wait or event-loop integration

## ADR Impact

- Decision: Define shell-free argument transport, process and pipe ownership, explicit handle inheritance, exit-status
  normalization, and termination semantics.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: These choices form the portable security, lifetime, and behavior contract for compiler drivers and build
    tools that launch child processes.

## Verification Criteria

1. Arguments containing spaces, quotes, empty strings, and non-ASCII data arrive unchanged on supported hosts.
2. Environment replacement and override behavior is deterministic.
3. Unselected file and socket handles are not inherited.
4. Pipe EOF and broken-pipe behavior is consistent and cannot terminate the parent process.
5. Wait, try-wait, terminate, and kill produce the documented state transitions.
6. Trace and host-level leak checks cover success and every spawn-failure stage.
