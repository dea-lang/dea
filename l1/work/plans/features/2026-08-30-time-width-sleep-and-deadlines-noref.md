# Feature Plan

## Widen time seconds and add sleep and deadlines

- Date: 2026-08-30
- Status: Draft
- Title: Widen L1 time seconds and add monotonic sleep, deadline, and timeout helpers
- Kind: Feature
- Severity: Medium
- Priority: 3
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0006-process-and-host-services.md`
- Subsystem: Stdlib / runtime / time
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/time.l1`
  - `l1/compiler/shared/l1/stdlib/sys/rt.l1`
  - `l1/compiler/shared/l1/stdlib/sys/time.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_time.c`
  - `l1/docs/reference/standard-library.md`
  - `l1/docs/reference/design-decisions.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/time_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/work/initiatives/0006-process-and-host-services.md`
  - `l1/work/initiatives/0007-blocking-networking.md`
  - `l1/work/plans/features/2026-08-30-wide-filesystem-metadata-noref.md`
- Repro: `make -C l1 test-stage1 TESTS="time_runtime_test l0c_lib_test"`

## Summary

Correct the general L0-era 32-bit second fields separately from filesystem metadata, then add the scheduling helpers
needed by process control and networking. Wall, monotonic, and duration seconds become `long`; normalized nanoseconds
remain `int`.

## Scope

1. Change `RtTimeParts.sec`, `WallTime.sec`, `MonotonicTime.sec`, and `Duration.sec` to `long`.
2. Update Unix-second conversion and local-offset/DST runtime calls to accept `long` timestamps.
3. Preserve normalized `nsec: int` and checked arithmetic across second/nanosecond boundaries.
4. Add `sleep`, `sleep_until`, `deadline_after`, and `remaining`.
5. Use monotonic time for deadlines and elapsed waits.
6. Distinguish completed sleep, interruption, unsupported clock, timeout, and host failure.

## Implementation Phases

1. Widen time structs, runtime ABI, conversions, arithmetic, tests, and stable docs.
2. Add duration validation and checked deadline arithmetic.
3. Add relative sleep with documented interruption behavior.
4. Add monotonic deadline and remaining-time helpers.
5. Integrate the timeout contract with process and networking consumers.

## Non-Goals

- timezone database management or locale formatting
- calendaring beyond current conversion helpers
- event-loop timers or asynchronous tasks
- conflating wall time with elapsed-time deadlines
- widening nanoseconds or in-memory collection lengths to `long`

## ADR Impact

- Decision: Use `long` for wall, monotonic, and duration seconds, retain normalized `int` nanoseconds, and base
  deadlines on monotonic time.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The existing second fields are inherited 32-bit limitations, and wall-clock adjustment must not change
    elapsed timeout behavior.

## Verification Criteria

1. Dates outside the 32-bit Unix-second range round-trip where the host supports them.
2. Duration normalization and arithmetic reject overflow before it reaches the runtime.
3. Deadline helpers use monotonic time and remain stable across simulated wall-clock changes.
4. Sleep interruption and restart behavior matches the documented contract.
5. Process and network timeout results remain distinct from general OS failures.
