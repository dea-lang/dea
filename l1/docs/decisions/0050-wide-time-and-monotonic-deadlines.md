# ADR-0050: Wide Time and Monotonic Deadlines

- Decision date: 2026-10-28
- Last edited: 2026-10-28
- Status: Accepted

## Context

Inherited 32-bit seconds restrict timestamps, durations, and elapsed-time calculations. Filesystem metadata already uses
wide seconds. Process and networking consumers need checked deadlines that wall-clock corrections cannot change.

## Decision

L1 `WallTime`, `MonotonicTime`, `Duration`, and `sys.rt::RtTimeParts` use signed `long` seconds and normalized `int`
nanoseconds. Wall seconds may be negative; durations and monotonic values require nonnegative seconds. Public helpers
validate supplied values and perform checked second arithmetic with explicit nanosecond carry/borrow, without reducing
the full value to a signed nanosecond count.

Unix-second and civil-day inputs use `long`. Calendar years/components and UTC offsets remain `int`.
`civil_from_unix_days(long)` returns `CivilDate?`; extreme calendar values and unsupported native local-time ranges
return `null` rather than narrowing. Runtime conversions check native `time_t` signedness and width in both directions.
The C ABI uses `dea_long`, independent of host C `long`.

`deadline_after` validates, samples monotonic time once, and adds with checked arithmetic. A zero delay still samples.
`remaining` validates and samples once, returning `Expired` at or after the deadline and a strictly positive normalized
duration otherwise. Deadlines belong to the current host clock epoch and cannot be persisted or transferred between
unrelated hosts or boots. No wall-to-monotonic conversion or wall-clock fallback is supplied.

`TimeError` distinguishes `InvalidValue`, `Overflow`, `UnsupportedClock`, and `Host(OsError)`. Existing nullable clock
and calendar APIs remain available. New scheduling transport belongs in `sys.time`, reusing `sys.os::RtOsError`.

## Rationale

Wide seconds preserve useful timestamp range while the existing nanosecond representation remains normalized and easy to
carry or borrow. Monotonic deadlines preserve a single elapsed budget across retries. Explicit library failures do not
invent native error codes or duplicate the shared OS-error model.

## Consequences

The L1 time layout and signatures are incompatible with prior native objects. Rebuild semantic interfaces, runtime
archives, and dependent native objects together; recreate explicit profiles. Managed preparation's content identity
already covers the affected sources, headers, and interfaces. L0 time and L2 adoption remain separate.

The representable timestamp range exceeds the calendar and host local-time range. Suspend inclusion follows the selected
monotonic source. Scheduling has no hard real-time upper-latency guarantee.

## Related Plans

- [l1/work/plans/features/closed/2026-08-30-time-width-sleep-and-deadlines-noref.md][time-plan]
- [l1/work/initiatives/0006-process-and-host-services.md][host-services]

## Current Docs

- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/design-decisions.md][design]
- [l1/docs/specs/compiler/abi.md][abi]

[abi]: ../specs/compiler/abi.md
[design]: ../reference/design-decisions.md
[host-services]: ../../work/initiatives/0006-process-and-host-services.md
[stdlib]: ../reference/standard-library.md
[time-plan]: ../../work/plans/features/closed/2026-08-30-time-width-sleep-and-deadlines-noref.md
