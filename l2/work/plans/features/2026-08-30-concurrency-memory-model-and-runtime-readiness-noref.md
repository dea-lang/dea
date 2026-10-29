# Feature Plan

## Define the concurrency memory model and runtime readiness

- Date: 2026-08-30
- Last reviewed: 2026-10-29
- Status: Draft
- Title: Define safe concurrency semantics and audit runtime thread readiness
- Kind: Feature
- Priority: Low
- Stdlib Tier: 4
- Parent Initiative: `l2/work/initiatives/0003-safe-concurrency.md`
- Subsystem: Language semantics / runtime / ARC / concurrency stdlib
- Modules:
  - `l2/docs/specs/language/concurrency-memory-model.md`
  - `l2/compiler/shared/l2/stdlib/std/thread.l2`
  - `l2/compiler/shared/l2/stdlib/std/sync.l2`
  - `l2/compiler/shared/l2/stdlib/std/atomic.l2`
  - `l2/compiler/shared/l2/stdlib/std/channel.l2`
  - `l2/compiler/shared/l2/stdlib/sys/thread.l2`
  - `l2/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l2/compiler/shared/runtime/src/dea_rt_trace.c`
  - `l2/compiler/shared/runtime/src/dea_rt_thread.c`
- Test modules:
  - `l2/compiler/tests/concurrency_runtime_test.l1`
  - `l2/compiler/tests/analysis_trace_test.l1`
- Related:
  - `l2/work/initiatives/0003-safe-concurrency.md`
  - `l1/work/plans/features/closed/2026-06-30-runtime-pointer-access-validation-noref.md`
  - `l2/docs/roadmap.md`
- Repro: `rg -n "thread|atomic|data race|channel|concurr" l2/compiler l2/docs l2/work`

## Summary

This work is deferred until stable-L1 catch-up and explicit activation of sustained L2 development. It does not gate L1
stabilization.

Define what safe concurrency can mean in an UB-free language before implementing public threads. The plan produces the
memory-model decision, cross-worker value rules, runtime thread-safety audit, and an ordered set of follow-up plans. It
does not ship a thin safe wrapper over host thread APIs.

## Questions to Resolve

1. What constitutes a data race and whether it is rejected, trapped, serialized, or otherwise defined.
2. Which values are movable, shareable, or forbidden across worker boundaries.
3. Whether isolated workers and channels can precede shared-memory threads.
4. String ARC, allocation tracker, quarantine, and runtime trace synchronization.
5. Module initialization/finalization and process exit while workers exist.
6. Panic propagation, join results, cancellation, mutex poisoning, and detached execution.
7. Atomic types and ordering semantics, including interaction with the generated C contract.

## Approach

1. Audit every runtime global and ownership primitive for concurrent access.
2. Define the minimum memory model consistent with Dea's no-UB goal and C backend.
3. Prototype isolated worker/channel transfer rules and falsify unsafe ownership cases.
4. Decide whether low-level `sys.thread` must be explicitly unsafe and non-portable.
5. Write `l2/docs/specs/language/concurrency-memory-model.md` and enumerate implementation gates.
6. Spawn separate plans for runtime hardening, workers/channels, and any later atomics/synchronization.

## Non-Goals

- implementing safe public threads in this design plan
- exposing unrestricted shared mutable pointers
- copying C's data-race UB into the L2 contract
- async I/O, event loops, green-thread scheduling, or local IPC
- promising shared synchronization before runtime and ownership invariants are enforceable

## ADR Impact

- Decision: Define L2 data races, cross-worker ownership, atomic ordering, runtime thread safety, and the safe boundary
  between isolated workers/channels and shared-memory synchronization.
  - Scope: L2
  - Disposition: Pending
  - ADR: None
  - Rationale: The safe API shape depends on language and runtime guarantees that do not exist today and cannot be
    delegated to host thread conventions without violating the UB-free goal.

## Verification Criteria

1. The runtime audit identifies every mutable global and ownership operation requiring synchronization or isolation.
2. The memory model defines outcomes for representative conflicting and ordered accesses.
3. Cross-worker movement and sharing rules cover strings, arrays, structs, raw pointers, files, sockets, and callbacks.
4. The generated C strategy does not introduce C data-race UB for behavior declared safe by L2.
5. Follow-up implementation plans have explicit prerequisites and no unresolved safe-API claims.
