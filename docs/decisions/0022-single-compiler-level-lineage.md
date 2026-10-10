# ADR-0022: Single-Compiler Level Lineage

- Decision date: 2026-10-10
- Last edited: 2026-10-10
- Status: Accepted
- Supersedes: [ADR-0001](0001-two-stage-architecture.md)

## Context

Dea began in December 2025 as a systems language intended to host its own compiler. Dea/L0 initially used Python for
fast iteration and a practical bootstrap path, with a self-hosted implementation as the goal. The original architecture
extended that approach to every language level: an externally implemented Stage 1 defined semantics and diagnostics,
then built a Stage 2 written in the level's own language. Both implementations were maintained in parity, and
triple-bootstrap validation checked the self-hosted compiler's fixed point.

L0 realized this model with Python Stage 1 and L0 Stage 2. L1 then had an L0-implemented Stage 1 and a self-hosted L1
Stage 2. The completed L1 Stage 2 port demonstrated that L1 could implement a compiler, but treating both
implementations as permanent L1 compilers also required continuing source ports, semantic parity checks, stage
selection, and separate bootstrap machinery within the same level.

The compiler lineage now reuses that proven L1 implementation as the starting point for L2. The architectural question
is whether each subsequent level must repeat the two-stage model or can have one compiler implemented in its
predecessor.

This decision replaces the universal two-stage requirement while preserving the established L0 bootstrap foundation.

## Decision

### L0 bootstrap foundation

L0 retains Python Stage 1 and self-hosted Stage 2. Stage 1 remains the L0 semantic and diagnostic oracle; both stages
accept the same programs and produce equivalent behavior. Equivalent diagnostics reuse the same codes. Fixes and
improvements remain synchronized between the L0 implementations, and L0 retains parity and triple-bootstrap validation.
The initial self-hosting goal and its validation obligations therefore remain in force for L0.

### Levels after L0

For every level after L0, one canonical compiler is implemented in the immediately preceding level and accepts the
target level's programs. The preceding level provides a compatible construction toolchain; a second implementation in
the target language is not required. Each level owns its compiler implementation, target standard library, runtime,
support, and build machinery. Initial copying from a predecessor supplies a tested starting point without creating a
permanent source-parity obligation.

The canonical compiler is the semantic authority for its target level. Shared diagnostic meanings follow the Dea-wide
diagnostic-code catalog; the L0 oracle for shared codes does not make L0 the semantic authority for later levels.

The predecessor toolchain is a construction dependency. Once built, a level's compiler handles its target programs using
its own target inputs, without invoking the predecessor compiler or borrowing sibling target inputs. Generic repository
tooling may remain shared. Bootstrap selection and development workflows are defined in each level's documentation.

### Delivery and feature scope

A toolchain release delivers a compiler together with matching target support and documentation. Acceptance validates
the actual release artifacts on the supported platforms, separately from compiler correctness and publication
authorization. Version numbers, platform coverage, and release procedures belong to the relevant level's delivery plan.

Introducing a successor does not freeze its predecessor or transfer its feature plans. Each level continues to evolve;
cross-level ports require an explicit scope decision.

## Rationale

- Python remains a practical bootstrap and reference implementation for L0, whose established self-hosting checks remain
  useful and are preserved.
- The completed L1 self-hosting port already demonstrated the language's ability to implement a compiler. Retaining two
  compilers for every later level is not necessary to preserve that evidence.
- One canonical implementation makes semantic authority explicit and removes the ongoing cost of intra-level source
  ports, stage selection, and parity maintenance for L1 and later levels.
- Building through a compatible predecessor toolchain preserves a concrete bootstrap path. Physical target-input
  ownership lets each level evolve independently and makes its dependency boundary testable.

## Consequences

- L0 keeps its two-stage lifecycle, including diagnostic synchronization and triple bootstrap. Superseding ADR-0001
  changes its universal scope, not these L0 obligations.
- Every level after L0 uses canonical compiler validation without intra-level stages, parity gates, triple bootstrap, or
  a self-hosting requirement. Independent construction and target-input ownership require separate validation.
- Initial migration comparisons do not require levels to remain semantically identical. Shared contracts and explicitly
  scoped ports determine which behavior must remain aligned.
- Artifact acceptance applies to the compiler and target inputs actually delivered. Evidence for a different
  implementation or artifact does not establish acceptance of its replacement.

## Related Plans

- [l0/work/plans/features/closed/2026-03-11-triple-bootstrap-self-hosting-noref.md](../../l0/work/plans/features/closed/2026-03-11-triple-bootstrap-self-hosting-noref.md):
  established the retained L0 self-hosting validation.
- [work/plans/features/closed/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md](../../work/plans/features/closed/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md):
  supplied the proven L1 implementation subsequently transplanted into L2.
- [work/plans/refactors/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md](../../work/plans/refactors/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md):
  implementation and fresh acceptance tracking.

## Current Docs

- [MONOREPO.md](../../MONOREPO.md)
- [l0/docs/reference/architecture.md](../../l0/docs/reference/architecture.md)
- [l0/docs/specs/compiler/stage1-contract.md](../../l0/docs/specs/compiler/stage1-contract.md)
- [docs/specs/compiler/diagnostic-code-catalog.md](../specs/compiler/diagnostic-code-catalog.md)
- [l1/docs/reference/architecture.md](../../l1/docs/reference/architecture.md)
- [l1/AGENTS.md](../../l1/AGENTS.md)
- [l2/AGENTS.md](../../l2/AGENTS.md)
