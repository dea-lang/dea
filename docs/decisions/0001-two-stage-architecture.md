# ADR-0001: Two-Stage Compiler Architecture

- Decision date: 2025-12-05
- Last edited: 2026-05-20
- Status: Accepted

## Context

Dea was started in December 2025 as a systems language intended to eventually host its own compiler. For each level, the
question was whether to write the compiler once in an external host language and stop there, or to plan for a
self-hosted implementation from the beginning.

For L0, the external host was Python (chosen for speed of iteration; C, C++, Scheme, and OCaml were also considered).
Python was a pragmatic bootstrap choice, not a permanent commitment: the goal from day one was to produce a self-hosted
Stage 2.

## Decision

Each Dea language level implements its compiler in two distinct stages:

- **Stage 1**: Written in an external host language. Authoritative for language semantics, the normative reference for
  all diagnostic codes, and the bootstrap entrypoint. For L0, the host language is Python; for L1, it is L0 itself.
- **Stage 2**: Written in the level's own language. Built by Stage 1. When mature, replaces Stage 1 as the primary
  development tool.

Both stages must accept the same source programs and produce equivalent behavior. Stage 1 diagnostic codes are the
oracle; Stage 2 must reuse them exactly for equivalent conditions.

## Rationale

- A self-hosted compiler is the practical proof that the language is sufficiently expressive for real work.
- For L0, Python Stage 1 gives a fast, flexible bootstrap path with minimal infrastructure.
- For L1 and beyond, the previous level's Stage 2 provides a known-good baseline to copy and retarget, accelerating the
  bootstrap and providing a regression anchor.
- Keeping Stage 1 as the oracle for diagnostic codes and semantics keeps the system coherent: Stage 2 is a port, not a
  reimplementation with divergent behavior.

## Consequences

- Triple-bootstrap validation (e.g., `make triple-test`in L0) is the definitive regression gate: Stage 1 compiles Stage
  2, Stage 2 compiles itself, and the two outputs agree byte-for-byte.
- Stage 1 code should be maintained in sync with Stage 2: fixes and improvements in Stage 2 should be ported to Stage 1,
  and vice versa. A next-level feature that is backported to the previous level's Stage 2 should also be backported to
  the previous level's Stage 1.
- New diagnostic codes are assigned in Stage 1 first and then ported to Stage 2; Stage 2 must never invent codes for
  conditions that exist in Stage 1.

## Related Plans

- [l0/work/plans/features/closed/2026-02-14-stage2-parser-specification-noref.md](../../l0/work/plans/features/closed/2026-02-14-stage2-parser-specification-noref.md):
  Stage 2 parser specification
- [l0/work/plans/features/closed/2026-02-28-stage2-semantic-foundation-milestone-noref.md](../../l0/work/plans/features/closed/2026-02-28-stage2-semantic-foundation-milestone-noref.md):
  Stage 2 semantic foundation
- [l0/work/plans/features/closed/2026-03-09-stage2-backend-c-emitter-milestone.md](../../l0/work/plans/features/closed/2026-03-09-stage2-backend-c-emitter-milestone.md):
  Stage 2 backend and C emitter
- [l0/work/plans/features/closed/2026-03-11-triple-bootstrap-self-hosting-noref.md](../../l0/work/plans/features/closed/2026-03-11-triple-bootstrap-self-hosting-noref.md):
  triple-bootstrap validation

## Current Docs

- [l0/docs/reference/architecture.md](../../l0/docs/reference/architecture.md): L0 compiler pipeline and stage structure
- [l0/docs/specs/compiler/stage1-contract.md](../../l0/docs/specs/compiler/stage1-contract.md): L0 Stage 1 normative
  contract
- [l1/docs/reference/architecture.md](../../l1/docs/reference/architecture.md): L1 compiler pipeline
