---
name: create-dea-plan
description: Create a new Dea plan in the correct work tree with the right category, filename, metadata, and required roadmap links.
model: sonnet
effort: medium
---

### Create a new Dea plan

Use this skill when the user asks to add, draft, open, or write a new Dea plan or other lifecycle work item.

Do not use this skill for:

- stable reference/spec/status docs that belong under `docs/`
- closing or finalizing an already implemented plan
- a body of work that should be an initiative instead of a single plan

## Cross-level default rule

Treat plan rules as shared across `l0/`, `l1/`, and future `lN/` subtrees unless an explicit subtree or root rule says
otherwise.

That means:

- start from the root `CLAUDE.md` and the shared `work/README.md` policy first
- assume the same category, filename, metadata, and lifecycle rules apply across levels by default
- only introduce subtree-specific behavior when the relevant subtree docs explicitly define a narrower rule

## Required context

1. Read root `CLAUDE.md` first.
2. Read `work/README.md` when the work may be shared across levels or monorepo-owned.
3. If the scope is subtree-local, read that subtree's `CLAUDE.md` and `work/README.md`.
4. Read additional subtree docs only when that subtree has an explicit local planning rule that affects placement,
   linking, or metadata.
5. Inspect nearby active and closed plans in the target category before drafting so the new file matches current local
   naming and section conventions.
6. If scope, category, or ownership is ambiguous, clarify before writing the plan.

## Decide the right artifact first

1. **Stable current-state or normative content** belongs in `docs/`, not `work/`.
2. **One bounded change or work item** belongs in a plan.
3. **A coordinated multi-phase body of work whose phases will spawn future plans** belongs in an initiative instead.
4. **Work spanning multiple language levels, or monorepo-wide work**, should usually use one root-owned shared plan
   under `work/`, not separate follow-up plans in multiple level subtrees. Work confined to one language level remains
   level-local even when it spans multiple compiler stages or implementations.

Never place a lifecycle plan under `docs/`. Plans belong under the matching `work/` tree unless an explicit rule says
otherwise.

## Choose the correct location

### Root shared plans

Determine language-level ownership before counting compiler stages. If every target belongs to one language level, use
that level's `work/` tree even when the work spans multiple compiler stages or implementations. This single-level rule
takes precedence over the cross-stage and seeded-port indicators below.

Use the repository-root `work/` tree when any of these are true:

- the same fix or refactor spans multiple language levels
- an implementation in one language level was seeded from another level and the change should transfer between them
- the design decision is shared across language levels even if code lands in more than one subtree
- the work is monorepo-wide rather than owned by a single level

Create the file under:

- `work/plans/features/`
- `work/plans/bug-fixes/`
- `work/plans/refactors/`
- `work/plans/tools/`

### Level-local plans

Use `<level>/work/plans/<kind>/` when the work is owned by one language-level subtree, including work that coordinates
multiple compiler stages or implementations within that level. Single-level ownership takes precedence over the fact
that the plan is cross-stage, parity-oriented, or a seeded port. For example:

- `l0/work/plans/<kind>/`
- `l1/work/plans/<kind>/`
- future `lN/work/plans/<kind>/`

Assume this same subtree-local placement rule for future levels unless a later subtree doc explicitly narrows it.

### Active vs closed

- New plans start at the category root.
- Closed plans move later into `<category>/closed/`.

Do not create the file directly under `closed/`.

## Choose the correct category

- `features/`: user-visible language, compiler, runtime, stdlib, or product capabilities
- `bug-fixes/`: defects, regressions, parity mismatches, incorrect diagnostics, broken workflows
- `refactors/`: internal restructures that preserve current external behavior
- `tools/`: repo tooling, CI/CD, docs tooling, runners, packaging, install/dist workflows, helper scripts

If the work is primarily about wrong current behavior, default to `bug-fixes/` even if the implementation touches many
subsystems.

## Filename rules

Plan filenames use this shape:

```text
YYYY-MM-DD-<slug>-noref.md
```

Rules:

- Use the current date in `YYYY-MM-DD` form.
- Keep the final `-noref.md` suffix.
- Make the slug specific enough to identify the work from the filename alone.
- Do not use generic slugs such as `plan`, `new-feature`, or `compiler-fix`.
- For new level-local plans, do not repeat the owning level in the slug. If the file lives under `l0/work/...`,
  `l1/work/...`, or a future `lN/work/...` tree, do not add `l0-`, `l1-`, `ln-`, or similar level markers to the slug.
- Legacy level-local plans may already contain level prefixes; do not treat those older filenames as the rule for new
  files.
- Match nearby local naming idioms in the target tree.

Current repo conventions to follow:

- root shared plans often use a `shared-...` slug when the shared scope should be explicit
- level-local plans may still use a stage-oriented prefix such as `stage1-...` or `stage2-...` when that conveys real
  scope that is not already obvious from the directory path

For example, under `l1/work/plans/features/`, `2026-04-19-pointer-identity-equality-noref.md` is correct and
`2026-04-19-l1-pointer-identity-equality-noref.md` is not.

Use the clearest current local precedent subject to the no-level-prefix rule for new level-local plans.

## Metadata block

Start every new plan with the standard plan header and metadata block.

### Level-local plan template

```markdown
# [Bug Fix | Feature | Refactor | Tool] Plan

## [Short title]

- Date: YYYY-MM-DD
- Status: Draft
- Title: [Full descriptive title]
- Kind: [Bug Fix | Feature | Refactor | Tooling]
- Severity: [Low | Medium | High | Critical]
- Stage: [match nearby plans in the target tree]
- Subsystem: [subsystem summary]
- Modules:
  - `path/to/module`
- Test modules:
  - `path/to/test`
- Related:
  - `path/to/related-plan-or-doc.md`
- Repro: `command or focused repro`
```

Notes:

- New plans should normally start with `Status: Draft`.
- `# Tool Plan` pairs with `Kind: Tooling`.
- Include `Related:` when there are meaningful links; omit it only when there is nothing useful to reference.
- Include `Repro:` when there is a concrete repro command, fixture, or focused entrypoint.
- Use the stage/value style already used by nearby plans in the same tree and category.

### Root shared-plan extra metadata

Root shared plans need the standard block plus these required fields:

```markdown
- Scope: Shared
- Targets:
  - [target implementation]
- Origin: [where the design or first implementation settles]
- Porting rule: [mechanical port or intentional divergence rule]
- Target status:
  - [target]: Pending
```

For shared plans:

- use `Stage: Shared`
- include one `Targets:` line per in-scope implementation
- include one `Target status:` line per target using `Pending`, `In Progress`, `Implemented`, or `Deferred: <reason>`

## Body structure rules

After the metadata block, follow the structure already used by nearby plans in the same tree. For a new draft plan, the
body usually needs at least:

- `## Summary`
- `## ADR Impact`
- current-state and/or root-cause context
- goal/scope
- phased implementation or approach sections
- non-goals
- verification criteria

Use the closest local precedent:

- bug-fix plans often include `## Current State`, `## Root Cause`, `## Scope of This Fix`, `## Approach`, or explicit
  hypotheses to resolve
- feature and tooling plans often include `## Defaults Chosen`, `## Goal`, `## Implementation Phases`, and
  `## Verification Criteria`
- shared plans often include target-specific status and porting guidance

Do not write an `Outcome`, `Results`, or completed verification section in a brand-new draft plan unless the user is
actually documenting already landed work.

## ADR Impact requirement

Every new plan must contain exactly one `## ADR Impact` section. Follow the canonical schema, scopes, dispositions, and
closure rules in root `CLAUDE.md`. Start with one record per independent architectural question:

```markdown
## ADR Impact

- Decision: Short architectural question or durable choice.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: The decision remains open while the plan is active.
```

Choose the scope from the architectural decision's ownership, not merely from the files being edited. Use `Pending` only
for a genuinely unresolved active-plan question. When the direction is already known, select `New ADR`, `Amend ADR`,
`Covered by ADR`, or `ADR not warranted` immediately:

- An active `New ADR` record points to the correct decision directory.
- `Amend ADR` and `Covered by ADR` point to an exact existing, indexed ADR.
- A plan with no ADR-worthy decision has one `ADR not warranted` record with `Scope: N/A`, `ADR: None`, and substantive
  rationale.

Do not omit the section with the intention of deciding at closure. Run
`python3 scripts/check_adr_impact.py --all-active` after creating the plan.

## Remote and publication approval gates

A plan may describe remote or publication work, but it never authorizes that work. This remains true when the user asks
to implement the whole plan.

When a plan includes any push, tag, release, workflow dispatch, cross-repository write, documentation deployment, or
site publication:

- mark each such phase as a manual user-approval gate
- state the exact remote, branch, tag, artifact, or deployment target governed by the gate
- state the known automatic effects, including release creation, asset publication, Pages deployment, or downstream
  repository dispatches
- require fresh user confirmation immediately before the gated operation; an earlier request to draft or implement the
  plan does not satisfy the gate
- keep publication-dependent targets and the plan active until the authorized operation completes and is verified, or
  until the user explicitly defers or cancels that target

Do not describe material as user-reviewed unless the user reviewed the exact version. Agent review, tests, CI, or an
implementation request are not substitutes for user review. Any later content change invalidates the prior review and
requires the updated material to be reviewed again before publication.

Sandbox, tool, or command-escalation approval grants technical capability only. It never satisfies a user-approval gate.

## Diagnostic-code planning rules

If the planned work may introduce or reassign compiler diagnostic codes, inspect
`docs/specs/compiler/diagnostic-code-catalog.md` and carry explicit diagnostic-code planning in the draft.

Use these rules:

- For new features and, more generally, for any new diagnostic category/slice introduced by the work, provisionally
  reserve one unused block of 20 codes per impacted family/category.
- Typical examples include a new language construct, a new driver option family, or another new area expected to add
  several related diagnostics.
- Write the proposed reservation explicitly in the plan, for example `SIG-0340` to `SIG-0359` or `PAR-1580` to
  `PAR-1599`.
- When the work only needs a few new diagnostics inside an already established area, first suggest using unused codes in
  the pre-existing nearby range instead of reserving a fresh block. Older ranges often exist in blocks of 10.
- If that pre-existing range is full or clearly too small for the planned work, suggest a new currently unreserved block
  of 20 codes instead.
- Treat every code reservation written in a plan as provisional rather than final.
- State explicitly in the plan that the suggested block must be re-checked against the live catalog at implementation
  time because the proposed numbers may have been used in the elapsed time between planning and implementation; if so,
  the block must be changed then.

When diagnostic-code planning is relevant, include enough detail in the body to make the reservation actionable:

- which families/categories are impacted
- whether the plan expects reuse of unused numbers in an existing range or a fresh 20-code reservation
- the specific provisional range(s) being suggested
- the implementation-time re-check note

## Explicit subtree link and update rules

Only apply subtree-specific link/update work when the subtree docs explicitly require it.

Current explicit rule:

If you create a new L1-local lifecycle artifact, update `l1/docs/roadmap.md` in the same change:

- standalone plans go under `## Active standalone plans`
- initiatives go under `## Active initiatives`

When editing `l1/docs/roadmap.md`, refresh its `Version: YYYY-MM-DD` metadata if needed.

### Roadmap link legibility rules

For legibility, the visible link text in `roadmap.md` uses special abbreviated forms. These rules apply only inside
`roadmap.md`; everywhere else, follow the general "repository-root paths as visible link text" rule from the writing
rules below.

- plans: `[plan-slug](../work/plans/<kind>/plan-slug.md)` — visible text is the bare plan slug, without the `.md`
  extension and without the `../work/plans/<kind>/` prefix
- initiatives: `[NNNN-initiative-slug](../work/initiatives/NNNN-initiative-slug.md)` — visible text is the bare
  `NNNN-initiative-slug`, without the `.md` extension
- other documents: visible text is just the filename without extension, for example
  `[design-decisions](reference/design-decisions.md)` or `[project-status](project-status.md)`

Apply these rules to every link added to `roadmap.md`, including cross-references inside backlog bullets, not just the
`Active standalone plans` / `Active initiatives` entries.

## Initiative handoff rule

If the request clearly needs an initiative instead of a plan, do not force it into `plans/`.

Use a subtree-local initiative workflow only when that subtree explicitly documents one.

Current explicit example:

For L1, initiatives live at:

```text
l1/work/initiatives/NNNN-kebab-case-slug.md
```

Use the next available zero-padded number, carry the initiative metadata block, and add the roadmap entry under
`Active initiatives`. The initiative also requires exactly one `## ADR Impact` section under the root policy.

## Writing rules

- Keep the plan factual, concrete, and scoped to the actual work item.
- Do not document draft future work as shipped behavior in stable docs.
- Use repository-root paths as visible Markdown link text for repo files.
- Prefer explicit module/test lists over vague subsystem descriptions.
- Match the formatting and section style of nearby current plans instead of inventing a new template variation.
- If the user asked only for the plan, do not implement code changes.

## Deliverable checklist

- correct artifact type chosen
- correct `work/` tree selected
- correct category selected
- filename follows `YYYY-MM-DD-<slug>-noref.md`
- metadata block matches current repo rules
- shared-plan metadata included when needed
- exactly one ADR Impact section included with one record per independent architectural question
- ADR scope, disposition, and destination follow the root policy
- diagnostic-code reservation guidance included when the work may add new diagnostics
- explicit subtree link/update steps followed where required, for example the current `l1/docs/roadmap.md` rule
- no lifecycle plan written under `docs/`
- every remote or publication phase has an explicit manual user-approval gate with destination and downstream effects
- no unverified claim that the user reviewed or approved exact publication material
