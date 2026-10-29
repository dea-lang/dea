# ADR-0026: Finite L1 Stabilization Boundary

- Decision date: 2026-10-29
- Last edited: 2026-10-29
- Status: Accepted

## Context

L1 needs sufficient expressive power and portable public APIs for compilers and tools while its canonical compiler
remains implemented in L0. Treating every prospective language or library capability as an L1 prerequisite would prevent
a finite stabilization target. Starting L2 early would instead leave its predecessor baseline unsettled.

## Decision

L1 stabilization requires borrowed-slice safety, opaque dynamic byte buffers, file handles and incremental/random-access
I/O, secure entropy and temporary objects, shell-free processes and anonymous pipes, typed string formatting, semantic
dependency discovery, public-API acceptance programs, capability audit, documentation, and fresh artifact acceptance.

Byte buffers accept borrowed inputs and expose checked operations, explicit cleanup, and copying text conversions. They
do not return escaping buffer views. File and entropy operations use buffers plus checked ranges. Process output uses
explicit file/pipe routing; the build-driver acceptance program captures to temporary files.

Typed formatting remains an L1 library capability built on existing `Value` variants, variadics, string builders, and
ordinary ARC strings. Generic writer output, compile-time template checking, arbitrary-type reflection, implicit
heterogeneous conversions, and locale-sensitive formatting are outside this tranche.

Streams and buffering, networking, JSON, file watching, concurrency, owned slices and escaping buffer views, closures,
generics, and broader first-class C interoperability belong to future L2 work. Reassigned active plans move with their
ownership; completed L1 history stays in L1. Owned-slice syntax and mutation policy remain unresolved.

New capabilities require an explicit scope amendment. Correctness defects in the selected contracts remain stabilization
work. L1 has no deadline driven by starting L2. Sustained L2 work follows a selected stable L1 baseline and explicit
activation.

## Rationale

The selected public APIs support bounded-memory binary tools, source processing, deterministic diagnostics, and compiler
drivers without requiring general lifetime types, generic streams, concurrency, or a sophisticated successor language.
String materialization makes typed formatting useful within existing L1 ownership rules. Concrete output routing avoids
adding concurrent pipe draining and capture policy to the completion boundary.

## Consequences

Existing feature plans retain implementation ownership. Initiative 0011 coordinates completion and acceptance without
duplicating membership. Library plans must settle their remaining contracts and deliver real public APIs before the
capability audit can call them implemented. Compiler migration away from private support helpers remains separate work.
Reassignment and planning do not declare L1 stable or deliver the deferred capabilities.

## Related Plans

- [work/plans/features/closed/2026-10-29-l1-stabilization-boundary-noref.md](../../work/plans/features/closed/2026-10-29-l1-stabilization-boundary-noref.md)

## Current Docs

- [l1/docs/roadmap.md](../../l1/docs/roadmap.md)
- [l2/docs/roadmap.md](../../l2/docs/roadmap.md)
- [l1/work/initiatives/0011-l1-stabilization.md](../../l1/work/initiatives/0011-l1-stabilization.md)
