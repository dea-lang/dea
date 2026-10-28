# Feature Plan

## Widen time seconds and add sleep and deadlines

- Date: 2026-08-30
- Last reviewed: 2026-10-28
- Status: Completed
- Title: Widen L1 time seconds and add monotonic sleep, deadline, and timeout helpers
- Kind: Feature
- Priority: Medium
- Stdlib Tier: 3
- Parent Initiative: `l1/work/initiatives/0006-process-and-host-services.md`
- Subsystem: Stdlib / runtime / time
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/time.l1`
  - `l1/compiler/shared/l1/stdlib/std/os.l1` (from the OS-error prerequisite)
  - `l1/compiler/shared/l1/stdlib/sys/rt.l1`
  - `l1/compiler/shared/l1/stdlib/sys/time.l1` (new scheduling transport)
  - `l1/compiler/shared/l1/stdlib/sys/os.l1` (from the OS-error prerequisite)
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_time.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l1/docs/reference/standard-library.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/specs/compiler/abi.md`
- Test modules:
  - `l1/compiler/tests/time_runtime_test.py` (new L1 runtime/fixture harness)
  - `l1/compiler/tests/fixtures/time_runtime/` (new `.l1` fixtures)
  - `l1/compiler/tests/time_test.l0` (existing L0-seed compatibility coverage)
  - `l1/compiler/tests/io_runtime_test.py`
  - `l1/compiler/tests/runtime_symbol_manifest_test.py`
- Related:
  - `l1/work/initiatives/0006-process-and-host-services.md`
  - `l1/work/initiatives/0007-blocking-networking.md`
  - `l1/work/plans/features/closed/2026-08-30-wide-filesystem-metadata-noref.md`
  - [l1/work/plans/features/closed/2026-08-30-os-error-and-io-results-noref.md][os-errors]
- Repro: `make -C l1 test-compiler TESTS="time_runtime_test time_test io_runtime_test runtime_symbol_manifest_test"`

## Summary

Widened the general L0-era second fields separately from filesystem metadata and added the scheduling helpers needed by
process control and networking. Wall, monotonic, and duration seconds use `long`; normalized nanoseconds remain `int`.

## Implementation Baseline and Dependencies

The implementation baseline declared all four second fields as `int`. Runtime conversion helpers rejected seconds
outside the signed 32-bit range, and local-offset/DST entrypoints accepted `dea_int`. Previously widened filesystem
metadata remains unchanged.

`time_test.l0` is compiled by the upstream L0 compiler and imports the L0 seed's `std.time`. It remains bootstrap
compatibility coverage. The new Python runtime harness and `.l1` fixtures validate actual L1 widths and scheduling APIs.

The width/arithmetic phase was independent. Structured scheduling errors reuse
[l1/work/plans/features/closed/2026-08-30-os-error-and-io-results-noref.md][os-errors] and its `OsError` / runtime error
transport. Process and networking plans consume this contract later; neither was a prerequisite. Deterministic consumer
simulations verify timeout behavior without those modules.

## Stdlib-First Direction and Reference Material

Host clock handling and regression cases draw on `l1c_timing_monotonic` in
[l1/compiler/support/compiler_support.c][compiler-support] and timing/probe behavior in
[l1/compiler/support/preparation/platform.h][platform-support]. The review covered clock-read failures, timer/wait
failures, native conversion widths, and cleanup precedence. The public `long`-second, checked arithmetic,
structured-error, and interruption contracts below govern the implementation; the private two-`int32` transport and
floating-point millisecond deadlines are not its representation.

L2 adoption of L1 stdlib and removal of superseded private timing/probe helpers are separate follow-up work. This plan
requires neither compiler migration nor extraction of shared private C code.

## Defaults Chosen

### Width, representation, and compatibility

1. Change `RtTimeParts.sec`, `WallTime.sec`, `MonotonicTime.sec`, and `Duration.sec` to signed `long`; update the
   matching generated-name C struct and native prototypes with `dea_long`, never host C `long`.
2. Keep nanoseconds normalized to `0 <= nsec < 1000000000`. Wall seconds may be negative. Durations and monotonic values
   used by the new helpers require nonnegative seconds. Invalid public struct values produce an explicit failure rather
   than silently normalizing arbitrary input.
3. Perform second arithmetic in checked `long` operations and carry/borrow normalized nanoseconds explicitly. Do not
   flatten a full-range time or duration into one signed 64-bit nanosecond count.
4. Widen Unix-second parameters, `civil_from_unix_days`, and intermediate civil-date arithmetic. Keep `CivilDate.year`,
   `DateTime.year`, calendar components, and UTC offset seconds as `int`. Make `civil_from_unix_days(long)` return
   `CivilDate?`; check intermediate arithmetic and year range before narrowing. Extreme timestamps fail with `null` when
   the calendar representation or host local-time conversion cannot represent them.
5. Replace the seconds-specific 32-bit runtime conversion helper with checked `time_t`/`dea_long` conversion in both
   directions, accounting for signedness and width before any narrowing cast. Preserve the nanosecond helper's `int`
   contract. Widen local-offset/DST inputs while retaining their existing optional result types.
6. Keep the nullable forms of existing `wall_now`, `monotonic_now`, `monotonic_diff`, and calendar helpers. New
   scheduling APIs use the structured results below; wholesale legacy-error migration is outside this plan.
7. The L1 runtime/stdlib layout and function signatures change incompatibly. Rebuild runtime archives, interfaces, and
   dependent native objects together. L0 time remains unchanged. Managed cache identities include the affected inputs
   and invalidate prior support.

### Public scheduling surface

Use concrete result enums rather than generics. The implemented concrete results are:

| API                                                     | Result variants                                                                                      |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `deadline_after(delay: Duration) -> DeadlineResult`     | `Ready(deadline: MonotonicTime)`, `DeadlineFailed(error: TimeError)`                                 |
| `remaining(deadline: MonotonicTime) -> RemainingResult` | `Remaining(duration: Duration)`, `Expired`, `RemainingFailed(error: TimeError)`                      |
| `sleep(delay: Duration) -> SleepResult`                 | `Completed`, `Interrupted(deadline: MonotonicTime, error: OsError)`, `SleepFailed(error: TimeError)` |
| `sleep_until(deadline: MonotonicTime) -> SleepResult`   | The same `SleepResult`                                                                               |

L1 enum constructors share module scope, so result-specific failure names preserve the concrete result types without
introducing a compiler extension.

`TimeError` has `InvalidValue`, `Overflow`, `UnsupportedClock`, and `Host(error: OsError)` variants. Validation or
arithmetic failures do not invent native error codes. Runtime host failures preserve the shared normalized category and
native code before cleanup. The unsupported-clock case means no usable monotonic source exists; other clock-read and
wait failures return `Host`.

`deadline_after` validates the delay, samples the monotonic clock once, and adds the delay with checked arithmetic. A
zero delay still requires a clock reading to return a usable deadline. `remaining` validates and samples once; it
returns `Expired` when the deadline is at or before that sample and a strictly positive normalized duration otherwise.
Deadlines belong to the current host clock epoch and must not be persisted or transferred between unrelated hosts or
boots. No new wall-to-monotonic conversion is introduced.

### Completion, interruption, and restart

1. `sleep(Duration(0, 0))` returns `Completed` without a clock read, allocation, or host wait. Invalid delays fail
   before any host call. A positive delay computes one deadline and delegates to the `sleep_until` machinery.
2. `sleep_until` samples the selected monotonic clock and completes immediately if the deadline has passed. Otherwise it
   waits and rechecks the same deadline. Rounded or early successful host wakeups and bounded wait chunks do not count
   as completion until the clock reaches the deadline.
3. A host-reported interruption returns `Interrupted` immediately with the original absolute deadline and captured
   `OsError`. Do not silently restart, install signal handlers, or infer a portable cancellation event. An interruption
   wins over a simultaneous deadline crossing; an explicit retry can then complete immediately.
4. Callers choose whether to resume by calling `sleep_until` with the returned deadline. Do not restart the original
   relative duration or trust a stale host-provided remaining interval. The caller can query `remaining` separately.
5. Reaching a sleep deadline is success. A process or socket operation that exhausts its deadline returns its own
   `TimedOut` result, distinct from `OsError`, interruption, and a successful partial transfer. Retries reuse the same
   deadline. This plan specifies and tests that integration contract without adding process/socket APIs.
6. Scheduler latency and timer resolution may delay return. There is no hard real-time upper bound, busy-wait loop,
   process-wide timer-resolution change, or wake-from-suspend promise. Elapsed time follows the selected host monotonic
   source; inclusion of suspended time is host-specific and must be documented.

### Runtime and host mapping

Keep the existing time ABI declarations in `sys.rt`. Add scheduling/result transport in `sys.time`, reusing the common
`sys.os` error transport. Native out-parameters must be initialized consistently and filled only with validated results.
New runtime symbols belong in both normal and traced manifests.

- On Linux, prefer `clock_gettime(CLOCK_MONOTONIC)` with absolute `clock_nanosleep` when available. Its positive
  returned error code is the native error; do not read unrelated `errno` for that API. A missing absolute-wait facility
  may use bounded relative waits while keeping the same monotonic deadline. See the
  [GNU C Library sleeping contract][glibc-sleep].
- On macOS and other supported POSIX paths, use the available monotonic source plus `nanosleep` where an absolute
  monotonic wait is unavailable. Capture `errno` immediately on failure; `EINTR` maps to `Interrupted`. Apple's
  [nanosleep contract][apple-sleep] explicitly allows early signal interruption. Verify that the clock and relative wait
  agree on suspend accounting; if they differ or their agreement cannot be established, use the one-second chunk cap
  specified for Windows and recheck the same deadline between chunks.
- On Windows, use `QueryPerformanceCounter`/`QueryPerformanceFrequency` for monotonic measurements and a private,
  non-inheritable relative waitable timer with a non-alertable wait. Use integer quotient/remainder conversion with
  checked scaling. Cap every positive relative wait at `min(remaining, Duration(1, 0))` before native conversion and
  round up to native resolution; this cap applies independently of overflow. Reuse a one-shot timer and recheck QPC
  between chunks. QPC includes suspended time, while Windows 8+ relative timers exclude it: the cap limits extra native
  timer countdown after resuming past a deadline to one second, plus timer-resolution and scheduler latency. Normal long
  waits therefore recheck once per second. Do not reinterpret a QPC deadline as UTC timer time or request wake from
  suspend. Close the timer on every path and preserve the primary operation error if cleanup also fails. A cleanup
  failure after an otherwise successful wait returns `Host`. This route does not manufacture POSIX interruption events;
  observable timer or wait failures use `Host`. See Microsoft's [clock guidance][windows-clock] and
  [waitable-timer contract][windows-timer].

Clock and wait adapters expose private test seams for deterministic injected reads, errors, interruptions, and wakeups.
They are not public runtime configuration or production environment switches. No supported platform may substitute wall
time when monotonic time is unavailable.

## Implementation Findings

- Widened the four time-second fields, runtime ABI, local-time inputs, and checked civil/day arithmetic. Calendar years
  remain `int`; exact minimum/maximum year boundaries and extreme timestamps have explicit rejection coverage.
- Added concrete scheduling results through `sys.time`, reusing `sys.os::RtOsError`. L1 enum constructors share module
  scope, so failure variants are `DeadlineFailed`, `RemainingFailed`, and `SleepFailed`. Generated validation imports
  now use unique aliases to avoid the public `std.os` / `std.time` `Interrupted` collision during preparation, semantic
  bootstrap, and captured package-input validation.
- Implemented Linux absolute monotonic waits, bounded POSIX fallback, and Windows integer QPC/private-timer adapters.
  Clock-read `EINTR` remains a host failure; wait interruption returns immediately with the original deadline. Timer
  cleanup preserves a primary error, and cleanup-only failure is observable.
- Added actual generated L1 width/calendar/scheduling fixtures in checked, unchecked, and traced modes. Deterministic
  injected clock/wait/cleanup fixtures cover early wakes, suspension, expired and future-deadline resumption, error
  precedence, and consumer timeout/partial-progress distinctions. Native adapter probes and synthetic signed/unsigned
  32/64-bit `time_t` probes cover ABI conversions and error capture.
- Existing managed content identities include the changed stdlib/runtime sources, header, and semantic interfaces;
  mutation regressions now explicitly include those time inputs. Rebuild matching runtime/interfaces/native objects and
  recreate caller-owned profiles; no cache schema change is needed.

## Diagnostic Planning

No compiler diagnostic codes are introduced or reassigned. Invalid durations, overflow, clock support, and host failures
are runtime/library results, not compiler diagnostics. Reuse the shared `OsError` definitions; do not reserve a second
OS-error or compiler-diagnostic area. If implementation exposes an independent compiler defect, track it separately and
check the live shared diagnostic catalog before assigning any code.

## Non-Goals

- timezone database management or locale formatting
- calendaring beyond current conversion helpers
- event-loop timers or asynchronous tasks
- conflating wall time with elapsed-time deadlines
- widening nanoseconds or in-memory collection lengths to `long`
- changing L0 time semantics or treating `.l0` harness tests as L1 ABI validation
- adding process/network APIs, signal handlers, cancellation tokens, or automatic interruption restart
- requiring every host to support every `long` calendar timestamp or identical suspend accounting
- L2 compiler migration, bootstrap changes, or removal of compiler-private support

## ADR Impact

- Decision: Use `long` for wall, monotonic, and duration seconds, retain normalized `int` nanoseconds, and base
  deadlines on monotonic time.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0050-wide-time-and-monotonic-deadlines.md`
  - Rationale: The existing second fields are inherited 32-bit limitations, and wall-clock adjustment must not change
    elapsed timeout behavior.
- Decision: Return explicit sleep interruptions with the original deadline and distinguish scheduling completion from
  consumer timeout and structured host failure.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0051-explicit-sleep-interruption-and-restart.md`
  - Rationale: Retry policy and result distinctions are durable public contracts used by later process and networking
    APIs; host-specific signal and timer behavior must not choose those semantics implicitly.

## Verification Criteria

1. Generated `.l1` fixtures and native layout probes verify `long` seconds and `int` nanoseconds on all supported hosts.
   Runtime archives and both symbol manifests agree with the declarations.
2. UTC conversion handles timestamps outside the 32-bit range, including negative seconds. Civil-year overflow,
   unsupported local-time ranges, and `time_t` conversion failures produce explicit failure without truncation.
3. Invalid nanoseconds and negative durations fail before host calls. Carry, borrow, deadline addition, and extreme
   second/day calculations reject overflow before it occurs; no whole-duration nanosecond multiplication is used.
4. Zero sleep avoids the host; zero `deadline_after` still samples the clock. Past/equal deadlines complete or expire,
   and future deadlines produce positive normalized remaining time.
5. Injected wall-clock changes do not alter deadline behavior. Unsupported monotonic clocks and native read/wait
   failures remain distinct, and native error codes survive timer cleanup.
6. Injected interruption returns exactly once with the original deadline and native error, without an automatic retry.
   Explicit resumption uses that deadline, including the case where it expires before retry.
7. Early successful wakeups, repeated wait chunks, native-unit rounding, and large durations preserve the deadline and
   cannot overflow, busy-spin, or return success early. Inject a suspension that advances QPC beyond the deadline while
   the native relative countdown stays unchanged: every requested wait is at most one second and completion follows the
   first resumed chunk without rearming. Apply the same probe to POSIX fallbacks with mismatched suspend accounting.
8. Consumer simulations distinguish timeout, interruption, failure, and partial success without requiring the future
   process/network modules to exist.
9. Timer handles and fixture allocations are released on success and failure. Short real waits use a generous harness
   timeout and avoid fragile upper-latency assertions.

## Verification Results

Selected the exhaustive L1 `test-ci` tier because this change alters runtime ABI, native wait-resource handling, stdlib
preparation, and traced generated programs. L0 time remains unchanged. Commands below ran from `l1/`.

- Rebuilt fresh native runtime artifacts with `make clean-runtime`, followed by `make build runtime` with
  `L0_CC=/usr/bin/clang L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang`. The actual compiler was Apple Clang 17.0.0
  on macOS Intel; the bootstrap was the repo-local `../l0/build/dea/bin/l0c-stage2`.
- `make test-ci L0_CC=/usr/bin/clang L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang L1_TEST_JOBS=8 L1_TRACE_TEST_JOBS=8`:
  passed 99 normal compiler cases, 50 canonical trace cases, 5 child trace fixtures, 244 docgen checks, 183 tooling
  checks (1 skip), and 289 productization fixture checks (14 skips), plus examples, Wine-runner unit checks, and the
  environment/bootstrap integration check. All traced cases reported zero leaked object/string pointers.
- `make docker CMD=test-ci DOCKER_CC=gcc L1_TEST_JOBS=8 L1_TRACE_TEST_JOBS=8` exposed existing image omissions:
  `.github` and `tools` are absent, so documentation tests stop before compiler validation. Reused the built image with
  those two directories mounted read-only and ran the same `make test-ci` target with all three C compiler roles set to
  `gcc`. The actual compiler was `/usr/bin/gcc`, Debian GCC 12.2.0, on Linux x86_64. The complete-input run passed 99
  normal cases, 50 trace cases, 5 child fixtures, 202 docgen checks (42 skips), 153 tooling checks (31 skips), 287
  productization fixture checks (16 skips), examples, Wine-runner checks, and environment integration.
- Both complete normal suites ran `time_runtime_test`, `io_runtime_test`, `runtime_symbol_manifest_test`,
  `preparation_identity_test`, and the L0-seed `time_test`. The time harness independently checks ARC/memory traces for
  real-host and injected generated L1 fixtures. The three final boundary/restart fixtures were byte-identical between
  hosts before execution. Default canonical trace discovery retains its documented slow math-compile exclusion; normal
  CI-only math coverage passed.
- Synthetic signed/unsigned 32/64-bit `time_t` conversions, native POSIX absolute/fallback error probes, and portable
  QPC fraction / Windows tick conversions passed. Temporary C ABI probes on both hosts confirmed supported 1900/2100
  local offset/DST results exactly match native data and extreme `long` timestamps fail cleanly. Simulated Win32
  clock/timer failures and suspend handling also passed; this is separate from native Windows execution.
- `python3 scripts/check_c_docs.py` and targeted checks for all three new C/header fixtures passed. ADR Impact, staged
  whitespace, Markdown formatting, and root pre-commit checks complete the local closure gate.

Native Windows and macOS ARM execution remain unverified locally. No path-text comparison changed. No release,
publication, remote push, or hosted workflow dispatch is part of this implementation.

[apple-sleep]: https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/nanosleep.2.html
[compiler-support]: ../../../../compiler/support/compiler_support.c
[glibc-sleep]: https://sourceware.org/glibc/manual/2.42/html_node/Sleeping.html
[os-errors]: 2026-08-30-os-error-and-io-results-noref.md
[platform-support]: ../../../../compiler/support/preparation/platform.h
[windows-clock]: https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps
[windows-timer]: https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-setwaitabletimer
