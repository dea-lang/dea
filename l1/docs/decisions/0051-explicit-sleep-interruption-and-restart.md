# ADR-0051: Explicit Sleep Interruption and Restart

- Decision date: 2026-10-28
- Last edited: 2026-10-28
- Status: Accepted

## Context

Host sleeps can wake early, report interruptions, round timer intervals, or account for suspension differently from a
monotonic clock. Implicitly restarting a relative duration changes the caller's budget and hides retry policy.

## Decision

`sleep(Duration(0, 0))` completes without allocation, clock reads, or waits. Invalid delays fail before host operations.
A positive sleep computes one monotonic deadline and delegates to `sleep_until`. Successful wakes recheck the same
deadline; completion requires reaching it. A past or equal deadline completes immediately after its clock sample.

`SleepResult` distinguishes `Completed`, `Interrupted(deadline, error: OsError)`, and `SleepFailed(error: TimeError)`.
Host interruption returns immediately with the original absolute deadline and captured native error, even when the
deadline crosses simultaneously. No signal handlers, automatic restart, or portable cancellation event are introduced.
Callers resume explicitly with `sleep_until` and the returned deadline, and may query `remaining` independently.

Linux prefers absolute `clock_nanosleep(CLOCK_MONOTONIC)` and captures its returned error code. Relative POSIX fallback
waits are bounded at one second when suspend-accounting agreement is not established. Windows uses integer QPC
conversion and a private non-inheritable one-shot relative waitable timer with a non-alertable wait. Every Windows wait
is capped at one second and rounded up to native resolution before rechecking QPC. Timer handles close on every path;
cleanup failure after success is `Host`, while a primary failure retains its original captured error.

Sleep expiry is success. Process and networking consumers report their own timeout result separately from OS failure,
interruption, and successful partial progress. Retries preserve the original deadline.

Concrete failure constructors use `DeadlineFailed`, `RemainingFailed`, and `SleepFailed` because L1 enum constructors
share module scope. Private compile-time clock/wait seams permit deterministic tests without production configuration
switches.

## Rationale

One absolute deadline avoids accumulated rounding and retry drift. Returning interruption preserves application policy.
QPC includes suspension while Windows 8+ relative timers exclude it; the one-second cap bounds extra countdown after a
resumed deadline to one second plus timer and scheduler latency. The same conservative cap covers uncertain POSIX
suspend accounting.

## Consequences

Long Windows waits wake and recheck once per second. Scheduler latency can delay return without a hard upper bound. The
API requests no process-wide timer-resolution change or wake from suspension, and never substitutes wall time. Native
Windows timer/wait failures are host failures; this path does not manufacture POSIX interruptions.

## Related Plans

- [l1/work/plans/features/closed/2026-08-30-time-width-sleep-and-deadlines-noref.md][time-plan]
- [l1/work/initiatives/0006-process-and-host-services.md][host-services]

## Current Docs

- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/design-decisions.md][design]
- [l1/docs/project-status.md][status]

[design]: ../reference/design-decisions.md
[host-services]: ../../work/initiatives/0006-process-and-host-services.md
[status]: ../project-status.md
[stdlib]: ../reference/standard-library.md
[time-plan]: ../../work/plans/features/closed/2026-08-30-time-width-sleep-and-deadlines-noref.md
