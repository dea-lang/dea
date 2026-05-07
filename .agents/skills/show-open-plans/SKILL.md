---
name: show-open-plans
description: Show all open Dea plans grouped by level then by initiative, with status and location.
model: haiku
effort: low
---

### Show open plans

Use this skill when the user asks to list, show, or summarize open plans, active work, or in-flight initiatives.

Do not use this skill for:

- listing closed or archived plans
- creating or editing plans
- checking what is in a specific plan's body

## Required context

1. Read root `CLAUDE.md` first.
2. For each level that has open plans, read that level's roadmap if it exists — these are the authoritative sources for
   initiative membership:
   - `l0/docs/roadmap.md` (if present)
   - `l1/docs/roadmap.md` (if present)
   - any root-level roadmap under `docs/` (if present)

## Discovery steps

1. Find all open plan files across the repo:

   ```
   find work/plans l0/work/plans l1/work/plans -type f -name "*.md" ! -path "*/closed/*" 2>/dev/null | sort
   ```

2. For each plan file, extract the `Status:`, `Title:`, `Kind:`, `Stage:`, and `Parent Initiative:` metadata lines from
   its header block.

3. For each roadmap that exists, read its `## Active initiatives` section and standalone-plan backlog entries to
   determine which initiative, if any, each plan belongs to. A missing roadmap file is not an error — skip it.

## Output format

Group results by level first, then by initiative within each level, in this order:

**Level order:** Shared (root `work/plans/`) → L0 → L1 → future levels in ascending order.

For each level that has open plans, emit a top-level heading: `## Shared`, `## L0`, `## L1`, etc.

Within each level section, group plans as follows:

1. One subsection per active initiative that owns plans at this level, titled with the initiative number and name
   (`### Initiative NNNN — <name>`).
2. A `### Standalone Features` subsection for open feature plans not assigned to any initiative.
3. A `### Tooling / Infrastructure` subsection for open tool or infra plans not assigned to any initiative.
4. Skip any subsection that has no open plans.
5. Skip any level section that has no open plans.

Within each subsection, list plans one per line:

```
- `<Title>` — <path>
```

End with a one-line summary: total open plan count and how many active initiatives have open plans.

## Grouping rules

- A plan belongs to an initiative when it carries a `Parent Initiative:` field in its metadata. This is the
  authoritative signal; use it first.
- When `Parent Initiative:` is absent, fall back to the roadmap's active-initiative entry or backlog — if it explicitly
  links that plan under an initiative's scope, treat that as membership.
- `Related:` alone (without `Parent Initiative:`) does not establish initiative membership; a plan may list an
  initiative in `Related:` without being owned by it.
- Standalone plans are plans with no `Parent Initiative:` field and no initiative link in the roadmap.
- A plan's level is determined by its directory prefix: `work/plans/` → Shared, `l0/work/plans/` → L0, `l1/work/plans/`
  → L1, and so on.
