# Feature Plan

## Add process spawning and anonymous pipes

- Date: 2026-08-30
- Last reviewed: 2026-10-29
- Status: Draft
- Title: Add shell-free process spawning, waiting, and anonymous pipe endpoints
- Kind: Feature
- Priority: Medium
- Stdlib Tier: 2
- Parent Initiative: `l1/work/initiatives/0006-process-and-host-services.md`
- Subsystem: Stdlib / runtime / process control / I/O
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/process.l1`
  - `l1/compiler/shared/l1/stdlib/std/pipe.l1`
  - `l1/compiler/shared/l1/stdlib/std/file.l1`
  - `l1/compiler/shared/l1/stdlib/sys/process.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_process.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l1/compiler/tests/process_runtime_test.l0`
  - `l1/compiler/tests/pipe_runtime_test.l0`
  - `l1/compiler/tests/analysis_trace_test.l0`
- Related:
  - `l1/work/initiatives/0006-process-and-host-services.md`
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/work/plans/features/closed/2026-08-30-os-error-and-io-results-noref.md`
  - `l1/work/plans/features/closed/2026-08-30-time-width-sleep-and-deadlines-noref.md`
- Repro: `make -C l1 test-compiler TESTS="process_runtime_test pipe_runtime_test analysis_trace_test"`

## Summary

Replace `std.system::system` as the only child-execution option with a typed, shell-free process API and first-class
anonymous pipe endpoints. The existing shell helper remains available as an explicitly shell-oriented convenience.

## Stdlib-First Direction and Reference Material

Use direct argv execution, executable lookup, and quoting in [l1/compiler/support/compiler_support.c][compiler-support],
plus capture and current-executable discovery in [l1/compiler/support/preparation/platform.h][platform-support], as
implementation references and sources of regression cases. Public process/pipe ownership, errors, inheritance, and
timeout behavior define the new implementation. Private JSON argument carriers, compiler diagnostics, process-group
policy, and fixed capture limits are not public defaults.

L2 adoption of L1 stdlib and removal of superseded private helpers are separate follow-up work. This plan does not
require compiler migration, bootstrap changes, or extraction of a common private C implementation.

## Public Surface

- Process types: `Process`, `ProcessId`, `ExitStatus`, `SpawnOptions`, and `Stdio`.
- Process operations: `spawn`, `wait`, `try_wait`, `terminate`, `kill`, `pid`, `stdin`, `stdout`, and `stderr`.
- Executable discovery: `find_executable` and `current_executable`.
- Pipe types: `PipeReader`, `PipeWriter`.
- Pipe operations: `create`, `read_some`, `read_exact`, `write_some`, `write_all`, and `close`.

`SpawnOptions` carries an argument vector, environment replacement or overrides, working directory, and standard-stream
routing as inherit, null, file, or pipe.

Concurrent in-memory capture and `run_capture` are deferred to later L2 work. Their separate limits, concurrent
draining, timeout, partial-output, and cleanup contracts require a separate plan. L1 callers route output to explicitly
selected files or pipes; the acceptance build driver captures to temporary files. Generic stream adapters are not
required.

## Required Semantics

1. The primary API never invokes a shell and never concatenates arguments into a command string.
2. Pipe ends have separate ownership and close behavior.
3. On POSIX, writes to a closed pipe return `BrokenPipe` rather than terminating the process through `SIGPIPE`.
4. Child inheritance is opt-in and limited to explicitly selected endpoints.
5. `wait` is idempotence-defined, and `try_wait` distinguishes running, exited, and failure.
6. `ExitStatus` distinguishes normal exit from signal or host termination where available.
7. `terminate` and `kill` state their platform-strength guarantees without pretending they are equivalent.
8. `find_executable` defines ordered `PATH` search, empty/relative components, Windows executable-suffix policy, and
   missing versus failed lookup. Anchor a selected relative candidate before a later working-directory change while
   preserving executable aliases whose spelling affects invocation behavior.
9. `current_executable` uses actual-host discovery rather than assuming `argv[0]` is a usable path. Document host alias
   spelling and unavailable-path behavior; neither discovery API guarantees the file cannot change before launch.

## Implementation Phases

1. Implement owned anonymous pipe endpoints and broken-pipe behavior.
2. Define process handles, argument/environment transport, standard-stream routing, and executable discovery.
3. Add spawn and wait/try-wait on POSIX and Windows without a shell.
4. Add termination, kill, and exit-status normalization.
5. Add explicit file/pipe routing, failure injection, handle-leak checks, and hostile-argument fixtures.

## Non-Goals

- shell grammar, quoting helpers, or replacing explicit `std.system::system`
- pseudo-terminals, interactive terminal control, or Unix job control
- named pipes, Unix-domain sockets, or shared-memory IPC
- process groups, daemonization, privilege changes, or sandbox policy in v1
- asynchronous wait or event-loop integration
- L2 compiler migration or removal of compiler-private support

## ADR Impact

- Decision: Define shell-free argument transport, process and pipe ownership, explicit handle inheritance, exit-status
  normalization, and termination semantics.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: These choices form the portable security, lifetime, and behavior contract for compiler drivers and build
    tools that launch child processes.
- Decision: Define executable search and current-executable discovery independently of shell interpretation and
  invocation-time working-directory changes.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Search order, Windows suffix selection, alias preservation, and host-discovered identity are durable
    process API behavior.
- Decision: Defer concurrent in-memory output capture and use explicit file/pipe routing in L1.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Compiler drivers can capture output through temporary files without adding concurrent draining, timeout,
    and buffering policy to the L1 stabilization boundary.

## Verification Criteria

1. Arguments containing spaces, quotes, empty strings, and non-ASCII data arrive unchanged on supported hosts.
2. Environment replacement and override behavior is deterministic.
3. Unselected file and socket handles are not inherited.
4. Pipe EOF and broken-pipe behavior is consistent and cannot terminate the parent process.
5. Wait, try-wait, terminate, and kill produce the documented state transitions.
6. Trace and host-level leak checks cover success and every spawn-failure stage.
7. Executable lookup covers root order, empty/relative components, aliases, spaces, Unicode, and native Windows suffix
   behavior. A later cwd change does not reinterpret a returned path; current-executable lookup works independently of
   the original command spelling.
8. The acceptance build driver captures stdout and stderr to temporary files and inspects exact binary output after
   waiting. No generic stream or concurrent capture helper is required.

[compiler-support]: ../../../compiler/support/compiler_support.c
[platform-support]: ../../../compiler/support/preparation/platform.h
