# ADR-0003: Shared CLI Contract

- Decision date: 2026-03-12
- Last edited: 2026-07-16
- Status: Accepted

## Context

As Stage 2 of the L0 compiler was being built alongside Stage 1, there was a risk of the two stages diverging in their
command-line behavior (different flags, different flag names, different output formats). Users would then see
inconsistent behavior depending on which stage was active.

The same risk applies across language levels: L0 and L1 compilers should not invent incompatible CLI surfaces when they
share the same overall usage model.

## Decision

A normative shared CLI contract is defined in `docs/specs/compiler/cli-contract.md` and covers:

- The set of operating modes (`--check`, `--compile`, `--gen`, `--build`, `--run`, `--tok`, `--ast`, `--sym`, `--type`).
- Global and mode-scoped flags, including the semantic short-option namespaces used for source roots, runtime paths,
  host-C controls, and log presentation.
- Exit codes.
- Source-path resolution rules.

Both Stage 1 and Stage 2 of the L0 compiler, and the L1 compiler, must conform to the shared meanings in this contract.
The same token never acquires a different meaning at another stage or level. A level may recognize a shared operation
and report that the capability is unavailable, and documented extensions such as L1 `--emit-interface` remain allowed.
Silently changing a shared flag or exit-code meaning is a bug.

When Dea exposes an operation equivalent to a widespread compiler-driver operation, its short spelling follows that
convention. `-c`, `-I`, `-L`, and `-l` therefore mean compile without linking, interface/import search, native-library
search, and native-library selection. `-g` and `-S` are reserved for debug information and assembly output rather than
being reused for generated C and system source roots.

Dea-specific controls use exact, case-sensitive semantic namespaces: `-Gc` for generated C; `-Rp` / `-Rs` for project
and system resource roots; `-Ri` / `-Rl` for runtime paths; `-Cc` / `-Co` for host-C selection and options; and `-Vl`
for rich log presentation. Bare namespace prefixes are invalid. Namespaced values are separated or use `=VALUE`, while
canonical path/library spellings may use attached values. Only `-vv...` is a valid short-option cluster.

## Rationale

- Users should not need to know which stage is active to use the compiler.
- A written contract gives a clear target for Stage 2 parity work and for future language levels.
- Normalizing exit codes and flag names early is cheaper than fixing them after users depend on the current behavior.
- Reserving familiar driver spellings avoids locking later compilation and linking work behind historical aliases.

## Consequences

- Stage 2 parity plans reference this contract as the acceptance criterion.
- New flags and modes must be added to the contract document before being implemented in either stage.
- L1 compiler inherits the same contract, adapting only where L1-specific behavior genuinely differs.
- The coordinated alias migration is intentionally breaking for L0 2.0; L1 has no released compatibility surface.
- Long option names and level-scoped environment variables remain stable across the migration.

## Related Plans

- [l0/work/plans/features/closed/2026-03-12-shared-cli-contract-spec.md](../../l0/work/plans/features/closed/2026-03-12-shared-cli-contract-spec.md):
  introduced the contract spec
- [l0/work/plans/features/closed/2026-03-12-cli-version-flag-and-identity-text-noref.md](../../l0/work/plans/features/closed/2026-03-12-cli-version-flag-and-identity-text-noref.md):
  version flag

## Current Docs

- [docs/specs/compiler/cli-contract.md](../specs/compiler/cli-contract.md): normative CLI surface
- [l0/docs/specs/compiler/cli-contract.md](../../l0/docs/specs/compiler/cli-contract.md): complete L0 Stage 1/Stage 2
  realization
