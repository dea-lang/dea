# ADR-0022: Time Model and Runtime Boundary

- Decision date: 2026-02-27
- Last edited: 2026-07-27
- Status: Accepted

## Context

Time APIs combine several domains that cannot safely substitute for one another. Wall time can be converted to a
calendar value but can jump. Monotonic time measures elapsed intervals but has no civil-calendar meaning and is not
available on every host. Local calendar conversion also depends on host timezone rules that are inappropriate to
reimplement in a bootstrap standard library.

Reading seconds and nanoseconds separately could produce a torn snapshot. Panics or magic sentinel values would also
make ordinary clock or conversion unavailability indistinguishable from valid time data.

## Decision

L0's time model and host boundary are:

1. `std.time` exposes distinct `WallTime`, `MonotonicTime`, `Duration`, and `DateTime` value types. APIs do not silently
   interchange wall and monotonic values.
2. A clock reading crosses the runtime boundary as one coherent `RtTimeParts { sec, nsec }` snapshot written by one
   runtime call.
3. Public fallible operations return optionals. Clock capture or conversion failure returns `null`; it does not panic or
   use an in-band timestamp sentinel.
4. `monotonic_supported()` reports availability. `monotonic_now()` returns `null` when unavailable and never falls back
   to wall time.
5. Nanosecond components are normalized to `0 <= nsec < 1_000_000_000`. Duration and conversion operations reject
   invalid or reversed inputs through their optional result.
6. UTC calendar conversion is portable integer arithmetic in L0 code.
7. Local calendar conversion asks the runtime for the UTC offset and daylight-saving fact at the source Unix second.
   Host timezone rules stay behind the runtime boundary.
8. `DateTime.second` remains in `0..59`; the model does not represent leap seconds.

## Rationale

- Separate value types prevent accidental arithmetic between clock domains with different guarantees.
- One runtime call keeps the seconds and fractional component internally coherent.
- Optional results make environmental limitations and range failures explicit at call sites.
- Refusing a monotonic-to-wall fallback preserves elapsed-time correctness during wall-clock adjustments.
- Integer UTC conversion is deterministic and portable, while local timezone policy remains with the host facilities
  that maintain it.
- A normalized nanosecond invariant keeps arithmetic and runtime adapters consistent.

## Consequences

- Callers must handle `null` from time capture, difference, and calendar conversion.
- Runtime ports provide coherent wall and monotonic snapshots plus local offset/DST queries; they do not own portable
  UTC civil-date arithmetic.
- Monotonic values can be used for durations but not as timestamps.
- New public time APIs must state their clock domain and preserve normalization.
- Supporting 64-bit timestamps, leap seconds, parsing, formatting, or sleeping requires separate evolution of this
  contract.

## Related Plans

- [l0/work/plans/features/closed/2026-02-27-stdlib-time-interface-noref.md](../../work/plans/features/closed/2026-02-27-stdlib-time-interface-noref.md):
  introduced the time value model, optional results, coherent runtime snapshots, and calendar boundary
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the public time and runtime contract into this ADR

## Current Docs

- [l0/docs/reference/standard-library.md](../reference/standard-library.md): current `std.time` and `sys.rt` APIs
- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): runtime and integer-model context
- [l1/docs/reference/standard-library.md](../../../l1/docs/reference/standard-library.md): downstream shared-library
  surface
