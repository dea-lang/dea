# Static Pointer-Check Elision Proposal

Version: 2026-07-11

Status: Proposed

## Summary

Dea validates pointer accesses at runtime by default
([docs/decisions/0010-checked-runtime-pointer-access-validation.md](../../docs/decisions/0010-checked-runtime-pointer-access-validation.md)).
This proposal records the long-term direction for reducing that overhead: a static analysis that proves individual
checked access sites safe and elides their runtime checks, growing over time toward ownership/borrow-style flow
analysis. The prover is an optimizer, not a gatekeeper: code it cannot prove safe keeps its runtime check and still
compiles.

This document is a direction record, not an implementation plan. Each stage below should open its own shared feature
plan when work starts.

## Model

The runtime check remains the semantic definition of a pointer error. A checked access site either executes its runtime
check or has been statically proven to satisfy the same contract; the observable behavior of a correct program is
identical either way. Consequences of this framing:

- **Elision, not rejection.** A site the prover cannot discharge keeps its runtime check. The prover never turns an
  unprovable program into a compile error, and no lifetime or borrow annotations are added to the surface syntax.
  Performance improves monotonically as the analysis gets smarter, and existing programs are never held hostage to the
  prover's precision.
- **Per-site granularity.** Every checked access site already owns a static pointer-site cache, so codegen has a
  per-site identity for each check. Elision means the backend does not lower a proven site through the check helper; no
  new runtime machinery is needed.
- **The checked runtime is the oracle.** Any program whose checks the prover elides must also run clean under the fully
  checked runtime. Differential runs (checked versus elided) over the test suites and the bootstrap are the soundness
  gate for the prover itself: a proven-safe site that trips a check in the checked build is a prover bug.
- **A residue always remains.** Pointers that cross the C FFI boundary and raw `sys.memory` storage have invalidation
  events the analysis cannot see, so those sites keep runtime checks indefinitely. Foreign pointers make the external
  lifetime explicit with `rt_register_foreign`/`rt_unregister_foreign`, but that dynamic lifetime still cannot be
  statically elided in general. The checked runtime, quarantine, and the lighter checked modes remain the permanent
  backstop for that residue and for unproven sites.

## Staging

In expected value order:

1. **Local redundant-check elimination.** Flow-sensitive, within a function: a pointer already checked on every path,
   with no intervening call, `drop`, or store that can invalidate it, does not need a second check at the same size and
   access mode. No alias analysis beyond local facts.
2. **Loop-invariant check hoisting.** A check of a loop-invariant pointer moves out of the loop body; the per-iteration
   fast path disappears entirely instead of hitting the site cache.
3. **Ownership/borrow-style flow analysis.** Interprocedural facts (parameter validity contracts, escape information,
   drop placement) discharge whole classes of sites. This is the stage that approaches a borrow checker in power while
   keeping the elision posture: what it cannot prove, the runtime still checks.

## Non-Goals

- Rejecting programs the prover cannot verify.
- Lifetime, borrow, or ownership annotations in the surface language.
- Removing the checked runtime, the quarantine, or the per-site cache machinery; elided builds still link the same
  runtime for the residual checked sites.
- Any commitment to a specific analysis representation before stage 1 opens its feature plan.

## Relationship to Current Work

- [docs/decisions/0010-checked-runtime-pointer-access-validation.md](../../docs/decisions/0010-checked-runtime-pointer-access-validation.md)
  defines the checked-access contract and the per-site cache shape this proposal builds on.
- The runtime perf tranches (quarantine tuning, allocation-record cache locality, the basic checked mode) reduce the
  cost of checks that remain; this proposal reduces how many checks remain. The two lines are complementary, and the
  residual-check cost keeps mattering after elision lands.
