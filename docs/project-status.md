# Dea Project Status

Version: 2026-07-23

This document summarizes the current status of the Dea project at the monorepo level.

Today the repository contains one active release line, Dea/L0, plus an active bootstrap subtree for Dea/L1. L0 remains
the canonical user-facing toolchain and documentation set for current releases. L1 exists so post-L0 language evolution
can continue inside the monorepo without changing the current L0 release target.

## Scope and Canonical References

Use this file as the Dea-wide status snapshot. For more specific details, use:

- [MONOREPO.md](../MONOREPO.md) for monorepo layout and root workflow.
- [work/plans/](../work/plans/) for active and closed Dea-wide plans.
- [l0/docs/project-status.md](../l0/docs/project-status.md) for the current L0 implementation and release status.
- [l1/docs/project-status.md](../l1/docs/project-status.md) for the current L1 bootstrap implementation status.
- [l1/README.md](../l1/README.md) for the current L1 bootstrap subtree entry point.
- [docs/specs/compiler/cli-contract.md](specs/compiler/cli-contract.md) for the shared compiler CLI contract.

## Current Repository Shape

The monorepo currently contains:

- `l0/` as the implemented language, compiler, runtime, docs, examples, and release subtree.
- `l1/` as the in-progress next-level subtree.
- `editors/` for shared Dea/L0 and Dea/L1 syntax highlighting, fallback modes, navigation indexes, the in-repository
  Tree-sitter grammar, fixtures, and focused validation.
- `scripts/` for monorepo-owned automation and shared helper modules.
- `docs/` for Dea-wide and monorepo-wide stable documentation.
- `work/` for Dea-wide and monorepo-wide plans/proposals.
- `tools/` for vendored third-party dependencies.

Inside `l1/`, the initial compiler layout is:

- `compiler/stage1_l0/` for the first L1 compiler implemented in L0,
- `compiler/stage2_l1/` as a placeholder for the future self-hosted L1 stage,
- `compiler/shared/runtime/` and `compiler/shared/l1/stdlib/` for copied shared bootstrap assets.

## Language-Level Status

### Dea/L0

L0 is the current release-bearing level.

Its repository status today is:

- self-hosted through Stage 2,
- the canonical public CLI and user documentation surface,
- validated through the existing L0 test, bootstrap, packaging, and docs workflows,
- versioned under the `l0-v*` / `l0-snapshot-*` release namespace.

### Dea/L1

L1 is in bootstrap development.

Its repository status today is:

- scaffolded as a separate subtree under `l1/`,
- seeded from the runnable L0 Stage 2 compiler,
- buildable as a repo-local `l1c-stage1` compiler,
- validated through copied Stage 1 implementation tests written in `.l0` and run through the upstream L0 compiler,
- using `.l1` as the current L1 source surface for the copied L1 stdlib, example programs, and bootstrap test fixtures,
- carrying implemented post-L0 language work such as wider numeric types, real literals, bitwise operators, top-level
  `const` with checked scalar constant expressions, string value comparisons, nullable/pointer identity equality, named
  arguments, the `is(...)` enum tag intrinsic, function pointer and L1-defined variadic function types, `unsafe func`,
  raw-pointer indexing inside unsafe functions, fixed-size arrays, non-owning slices with `len`/`slice`, and
  single-statement `while` / `for` / `match` bodies,
- emitting deterministic textual `.l1m` module interfaces through the internal `--emit-interface` mode while ordinary
  imports remain source-based,
- shipping bootstrap-oriented stdlib growth such as `std.real`, wider integer I/O/math helpers, and the new `std.types`
  value-type helper surface,
- not yet an install/dist/release-bearing product.

L1 bootstrap CI validation is now automated through the unified `ci.yml` GitHub Actions workflow, which routes
L1-relevant changes into the reusable `l1-ci.yml` delegate. That path covers:

- building the L1 Stage 1 compiler via an explicit upstream L0 Stage 2 compiler on Linux, macOS, and Windows,
- running L1 Stage 1 implementation tests and default ARC/memory trace checks,
- validating `examples/*.l1` sources, and
- providing `workflow_dispatch` inputs for platform selection, manual C compiler selection, and opt-in slow trace
  coverage.

L1 release and snapshot workflows (`l1-v*` and `l1-snapshot-*`) are not yet active and will only be added when the L1
install/dist artifact contract is defined, stable, and smoke-testable. See `MONOREPO.md` for the full release-line
gating policy.

## Release Model

The Dea monorepo uses separate release lines for each language level:

- L0 releases use `l0-v*` and `l0-snapshot-*`.
- Future L1 releases will use `l1-v*` and `l1-snapshot-*`.

L1 bootstrap development currently consumes L0 as an upstream compiler toolchain. Local development defaults to the
repo-local L0 Stage 2 build, while reproducible CI/release-oriented bootstrap flows should use an explicit upstream L0
compiler path.

## Shared Monorepo State

The monorepo now has a small but real shared top-level layer:

- root `work/plans/` for Dea-wide planning,
- root `docs/` for Dea-wide status and reference documents,
- root `editors/` for distinct L0/L1 editor identities backed by shared TextMate, Vim, Emacs, Universal Ctags, and the
  in-repository `editors/tree-sitter-dea/` L1-superset grammar package,
- root `CLAUDE.md` for monorepo-wide workflow policy,
- root `Makefile` for shared `help`, `venv`, normal `test`, full trace-inclusive `test-all`, `clean`, and `clean-all`,
- root `scripts/dea_tooling/` for shared launcher/bootstrap helpers.

This shared layer is intentionally narrow. Most compiler, language, runtime, and user-facing documentation remains owned
by the relevant level subtree.

## Near-Term Direction

Near-term project direction is split cleanly by level:

1. Maintain the released Dea/L0 `1.1.0` line through documented, semantically versioned fixes and focused foundational
   changes.
2. Keep Dea/L1 focused on bootstrap stabilization and planned post-L0 language/library growth, not on release parity
   yet.
3. Only move or duplicate level-local reference documents into root `docs/reference/` when they clearly become Dea-wide
   rather than L0-specific.
