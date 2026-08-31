# L1 Initiative 0009 - Safe Concurrency

- Version: 2026-08-30
- Status: Active
- Kind: Initiative
- Open plans:
  - `l1/work/plans/features/2026-08-30-concurrency-memory-model-and-runtime-readiness-noref.md`
- Closed plans: (none)

## Summary

This Priority 4 initiative promotes the roadmap's concurrency direction into explicit design work without pretending
that a thin wrapper over `pthread_create` or `CreateThread` would be a safe L1 concurrency model. Dea's UB-free goal
requires a data-race policy, rules for values crossing worker boundaries, and a thread-safe runtime before safe threads,
atomics, synchronization, or channels can ship.

The preferred direction is isolated workers and message passing. Shared mutable synchronization remains contingent on
semantics the language and runtime can enforce.

## Required decisions

1. Define a data race and the language response to unsynchronized shared mutation.
2. Define which values can be moved or shared across worker boundaries.
3. Audit string ARC, allocation tracking, module initialization/finalization, panic propagation, and process exit for
   concurrent execution.
4. Define join, cancellation, poisoning, and atomic ordering semantics.
5. Decide whether safe channels and isolated workers can land before general shared-memory threads.

## Phases and priority

### Phase 0 - Memory model and runtime readiness (Priority 4)

Produce the concurrency memory-model decision, runtime thread-safety audit, implementation prerequisites, and ordered
follow-up plan set.

Spawned plan: [concurrency memory model and runtime readiness].

### Later phases - Not yet opened

1. Unsafe low-level `sys.thread` primitives, if required for implementation.
2. Runtime thread-safety work.
3. Safe isolated workers and channels.
4. Shared synchronization and atomics only if their semantics can preserve Dea's UB-free contract.

## Non-goals

- exposing unrestricted shared mutable pointers through safe APIs
- selecting POSIX or Win32 behavior as the language memory model
- shared memory or local IPC in the initial design plan
- scheduling policy, green threads, or async networking
- opening implementation plans before the memory-model and runtime-readiness gates are settled

## ADR Impact

- Decision: Define the L1 concurrency memory model, cross-thread value rules, and the boundary between safe workers,
  channels, atomics, and shared synchronization.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: Safe concurrency cannot be exposed until the language response to data races and the runtime ownership
    invariants are defined together.

## References

[concurrency memory model and runtime readiness]: ../plans/features/2026-08-30-concurrency-memory-model-and-runtime-readiness-noref.md
