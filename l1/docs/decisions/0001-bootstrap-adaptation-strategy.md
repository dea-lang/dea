# ADR-0001: Bootstrap Adaptation Strategy

- Decision date: 2026-04-02
- Last edited: 2026-05-20
- Status: Accepted

## Context

The Dea/L1 compiler needed to get runnable quickly. The question was whether to start from scratch, write L1 in some
other language, or reuse the mature L0 toolchain as a starting point.

## Decision

L1 starts as a retargeted copy of the L0 Stage 2 compiler rather than a greenfield implementation:

- The runnable L1 compiler (`compiler/stage1_l0/`) starts from copied L0 Stage 2 sources and is retargeted to emit L1
  semantics.
- The L1 reference docs start from copied L0 reference material and are rewritten to describe the real L1 bootstrap
  tree.
- Copied implementation and docs are allowed to retain historical internal names (e.g., `l0_*` prefixes) when those
  names are bootstrap artifacts rather than user-facing semantics.
- Live L1-owned helpers and tests should use L1-oriented names (`l1c_*`, `l1c_lib_test`) when the subject is the L1
  compiler.

## Rationale

- Copying a known-good baseline keeps the first L1 compiler runnable early, before any L1-specific divergence
  accumulates.
- Incremental retargeting is safer than speculative greenfield design when the L1/L0 semantic delta is still small and
  being discovered.
- The copied baseline provides a regression anchor: divergence from L0 behavior must be intentional and documented.

## Consequences

- The L1 bootstrap depends on the upstream L0 Stage 2 compiler at `../l0/build/dea/bin/l0c-stage2`; the bootstrap
  contract is recorded in `l1/CLAUDE.md`.
- L1-specific divergence from L0 semantics is documented in `l1/docs/reference/design-decisions.md` as it is introduced.
- Shared plans at the root `work/` level own decisions that apply to both levels; L1-only plans stay in `l1/work/`.

## Related Plans

- [work/plans/refactors/closed/2026-04-02-l1-bootstrap-scaffold-noref.md][scaffold]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §6 (bootstrap adaptation strategy)

[design-decisions]: ../reference/design-decisions.md
[scaffold]: ../../../work/plans/refactors/closed/2026-04-02-l1-bootstrap-scaffold-noref.md
