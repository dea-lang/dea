# ADR-0003: Shared CLI Contract

- Decision date: 2026-03-12
- Last edited: 2026-05-20
- Status: Accepted

## Context

As Stage 2 of the L0 compiler was being built alongside Stage 1, there was a risk of the two stages diverging in their
command-line behavior (different flags, different flag names, different output formats). Users would then see
inconsistent behavior depending on which stage was active.

The same risk applies across language levels: L0 and L1 compilers should not invent incompatible CLI surfaces when they
share the same overall usage model.

## Decision

A normative shared CLI contract is defined in `docs/specs/compiler/cli-contract.md` and covers:

- The set of operating modes (`--check`, `--gen`, `--build`, `--run`, `--tok`, `--ast`, `--sym`, `--type`).
- Global flags (`--verbose`, `--version`, `-P`, `-c`, `--c-options`, `--trace-arc`, `--trace-memory`,
  `L0_CFLAGS`/`L1_CFLAGS`).
- Exit codes.
- Source-path resolution rules.

Both Stage 1 and Stage 2 of the L0 compiler, and the L1 compiler, must conform to this contract. Divergence is a bug to
be fixed, not an accepted difference.

## Rationale

- Users should not need to know which stage is active to use the compiler.
- A written contract gives a clear target for Stage 2 parity work and for future language levels.
- Normalizing exit codes and flag names early is cheaper than fixing them after users depend on the current behavior.

## Consequences

- Stage 2 parity plans reference this contract as the acceptance criterion.
- New flags and modes must be added to the contract document before being implemented in either stage.
- L1 compiler inherits the same contract, adapting only where L1-specific behavior genuinely differs.

## Related Plans

- [l0/work/plans/features/closed/2026-03-12-shared-cli-contract-spec.md](../../l0/work/plans/features/closed/2026-03-12-shared-cli-contract-spec.md):
  introduced the contract spec
- [l0/work/plans/features/closed/2026-03-12-cli-version-flag-and-identity-text-noref.md](../../l0/work/plans/features/closed/2026-03-12-cli-version-flag-and-identity-text-noref.md):
  version flag

## Current Docs

- [docs/specs/compiler/cli-contract.md](../specs/compiler/cli-contract.md): normative CLI surface
