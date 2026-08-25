# ADR-0014: Intentional Cross-Level Divergence and Parity Exceptions

- Decision date: 2026-06-08
- Last edited: 2026-08-25
- Status: Accepted

## Context

Dea language levels evolve independently, but compiler parity checks use an earlier implementation as a behavioral
oracle for downstream or self-hosted stages. That relationship catches accidental drift only if a mismatch normally
means a defect.

A forward-only migration can legitimately reach an unreleased downstream level before the oracle level. The L1 removal
of deprecated `else` case defaults was such a migration: L1 had no compatibility obligation to retain the spelling,
while L0 still needed its transitional parser behavior. Requiring lockstep landing would unnecessarily couple otherwise
independent levels. Silently accepting the mismatch or disabling a broad parity suite, however, would make unrelated
regressions indistinguishable from intended evolution.

## Decision

An unreleased downstream level may complete a forward-only language migration before the level or stage that currently
acts as its parity oracle.

Every resulting oracle mismatch must be represented as an explicit, narrowly scoped parity exception. The exception
identifies the affected target and behavior or diagnostic codes, explains the intentional direction of travel, and
states the condition under which the exception is retired. The remainder of the parity suite stays active.

A parity exception is not permission for general divergence. It covers only the behavior made intentionally different by
the migration; unrelated diagnostics, parse results, semantics, and generated behavior remain subject to the oracle.
Once the upstream level adopts the same terminal behavior or ceases to be the relevant oracle, the temporary exception
is removed.

## Rationale

- Independent language levels need freedom to advance without manufacturing a flag-day migration across every compiler.
- A named exception keeps the oracle useful by distinguishing one reviewed mismatch from accidental stage drift.
- Narrow diagnostic or fixture exclusions preserve more regression coverage than disabling an entire parity suite.
- A retirement condition makes the divergence visible as temporary migration state rather than an undocumented fork in
  the language family.

## Consequences

- Forward migrations document the oracle relationship and enumerate every affected parity fixture or diagnostic code.
- Parity tooling needs per-target exception support and reviewable exception names or comments.
- A downstream compiler may reject syntax that its current oracle still accepts when the difference is an explicit
  migration step.
- Reviewers treat an unrecorded oracle mismatch as a defect, even if the downstream behavior appears preferable.
- Exceptions are removed when the upstream migration lands; they do not become a permanent compatibility layer.
- Shared ADRs and reference docs may describe temporarily different rollout phases for L0 and L1 while retaining one
  final direction.

## Related Plans

- [l1/work/plans/features/closed/2026-06-08-case-else-removal-l1-phase2-noref.md](../../l1/work/plans/features/closed/2026-06-08-case-else-removal-l1-phase2-noref.md):
  established the explicit L1-ahead-of-L0 parity exception for the `case` default migration
- [l0/work/plans/features/closed/2026-06-08-case-else-removal-l0-phase2-noref.md](../../l0/work/plans/features/closed/2026-06-08-case-else-removal-l0-phase2-noref.md):
  retired the temporary parity exception once L0 reached the terminal wildcard-only grammar
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the historical decision into the ADR catalog

## Current Docs

- [docs/decisions/0001-two-stage-architecture.md](0001-two-stage-architecture.md): oracle and mechanical-port
  architecture
- [docs/decisions/0007-case-default-arm-wildcard.md](0007-case-default-arm-wildcard.md): level-specific rollout of the
  motivating migration
- [l1/docs/reference/architecture.md](../../l1/docs/reference/architecture.md): L1 compiler and parity relationships
