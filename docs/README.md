# Root Documentation Layout

This root `docs/` tree is for Dea-wide and monorepo-wide stable documentation.

Today it contains:

- Dea-wide current-state material, including `project-status.md`
- Dea-wide normative specifications
- monorepo layout and shared automation documentation once stabilized
- Dea-wide reference documents that describe the project as a whole, including the
  [docs/reference/style-guide.md](reference/style-guide.md) code style guide
- future cross-level design and release-process documents

Existing level-local stable documentation remains in the owning subtree such as `l0/docs/`.

Lifecycle artifacts do not live in `docs/`. Use the sibling `work/` tree instead:

- root `work/` for Dea-wide plans and proposals
- level-local `work/` trees such as `l0/work/` and `l1/work/` for level-owned plans and proposals

## Reference

Root reference docs live under `docs/reference/` and describe the whole Dea project rather than one language level.

Examples:

- the [docs/reference/style-guide.md](reference/style-guide.md) Dea code style guide
- monorepo-wide release/status policy
- cross-level architecture notes once they exist

Language-specific references live in the owning subtree such as `l0/docs/reference/`.

## Specs

Root specs live under `docs/specs/` and define Dea-wide contracts that are not owned by one level.

Examples:

- shared compiler contracts and catalogs
- future cross-level release or compatibility policy

Language-specific specs live in the owning subtree such as `l0/docs/specs/`.

## Decisions

Root ADRs live under `docs/decisions/` and record Dea-wide architectural decisions — decisions that span both language
levels or belong to the project as a whole.

Each ADR links the decision to the closed plans that shaped it and the current docs where it is normatively recorded.
ADRs complement the `design-decisions.md` reference files (stable aggregates) and the closed plans in `work/plans/`
(execution history); they do not replace either.

Level-specific ADRs live in the owning subtree: `l0/docs/decisions/` and `l1/docs/decisions/`.
