# ADR-0004: Monorepo Directory Structure

- Decision date: 2026-03-27
- Last edited: 2026-09-03
- Status: Accepted

## Context

The Dea repository started as a single-language L0 repository with all compiler, stdlib, docs, and tooling files at the
repository root. There was no `l0/` subdirectory. When L1 development was planned, the repository needed a per-level
layout to keep each level self-contained.

A migration plan was written on 2026-03-24 and the restructure landed on 2026-03-27, introducing `l0/` as the first
per-level subtree, trimming the root `Makefile` to monorepo-maintenance-only targets, and adding `MONOREPO.md` as the
human-facing guide. L1 was then scaffolded on 2026-04-02 as the first new level in the monorepo structure.

## Decision

The Dea monorepo uses the following directory layout:

- `l0/`, `l1/`, ...: per-level subtrees, each self-contained with its own compiler, stdlib, docs, and work artifacts.
- `editors/`: shared cross-level editor grammars, fallback modes, navigation indexes, and focused validation.
- `scripts/`: shared monorepo automation and helper modules used across levels.
- `tools/`: vendored third-party dependencies.
- `docs/`: Dea-wide and monorepo-wide stable documentation only.
- `work/`: Dea-wide and monorepo-wide lifecycle artifacts (plans, proposals, initiatives).

Python tooling uses a single `uv` workspace rooted at the repository root with one shared `.venv` and one `uv.lock`.
Level-local `make venv` targets delegate upward to the root.

The placement rule for docs and work artifacts is: if the artifact is specific to one level, it lives under that level's
subtree; if it spans levels or belongs to the project as a whole, it lives under the root `docs/` or `work/`
directories. This rule is covered in detail in [ADR-0006](0006-docs-work-taxonomy.md) (docs/work taxonomy).

## Rationale

- Per-level subtrees make each level fully self-contained: its compiler, tests, docs, and lifecycle artifacts can be
  developed and reviewed without knowledge of other levels.
- Shared top-level directories for cross-cutting concerns avoid duplicating automation and vendored dependencies across
  levels.
- A single `uv` workspace removes the need for per-level virtual environments and lock files.

## Consequences

- New language levels add a top-level subtree directory following the same layout as `l0/` and `l1/`.
- Cross-level shared work belongs in root `work/`; level-specific work stays in `lN/work/`.
- Editor integrations may preserve level-specific language identities while sharing implementation under `editors/`.

## Related Plans

- [l0/work/plans/refactors/closed/2026-03-24-monorepo-language-level-layout-noref.md](../../l0/work/plans/refactors/closed/2026-03-24-monorepo-language-level-layout-noref.md):
  monorepo layout design and migration (introduced `l0/` subtree, root `Makefile`, `MONOREPO.md`)
- [work/plans/tools/closed/2026-05-06-shared-uv-workspace-monorepo-noref.md](../../work/plans/tools/closed/2026-05-06-shared-uv-workspace-monorepo-noref.md):
  uv workspace unification (one shared venv and lockfile)
- [work/plans/features/closed/2026-06-30-shared-editor-support-noref.md](../../work/plans/features/closed/2026-06-30-shared-editor-support-noref.md):
  shared editor support and the in-repository Tree-sitter grammar package

## Current Docs

- [AGENTS.md](../../AGENTS.md): Repository Structure table
- [MONOREPO.md](../../MONOREPO.md): human-facing monorepo guide
