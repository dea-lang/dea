# L1 Work Layout

This `l1/work/` tree holds lifecycle-bound documents for the Dea/L1 subtree.

Use `l1/docs/` for stable references, the L1 roadmap, and future accepted specs. Use `l1/work/` for initiatives, plans,
and any future proposals.

## Layout

- `initiatives/` for multiphase, cross-cutting bodies of work that sequence and motivate future plans
- `plans/` for L1-local execution plans and operational work tracking
- `proposals/` for future in-discussion L1 changes if that tree becomes necessary

Active documents live at the category root. Realized, superseded, or otherwise closed documents move into
`<category>/closed/` with cross-references updated.

Use `l1/work/` only for material owned by the L1 subtree. If work spans `l0/` and `l1/`, prefer a single shared document
under the repository-root `work/` tree with explicit targets rather than separate local follow-ups.

## Initiatives and plans

Use an initiative (`l1/work/initiatives/NNNN-*.md`) for a coordinated, multi-phase body of work with a defined scope and
end state. Use a plan (`l1/work/plans/<kind>/<slug>.md`) for a single change or work item with a defined start and end.
Plans are often spawned by an initiative phase, but can also stand alone for work that does not warrant an initiative.

Reach for a new initiative when a body of work spans multiple plans across categories, when decisions made now constrain
plans that will only be written later, or when the sequencing and dependency structure between phases is itself the
artifact worth recording. Reach for a plan directly otherwise (even a large one).

## Initiative file naming

Initiative documents use a four-digit zero-padded numeric prefix and a kebab-case slug:

```
initiatives/NNNN-short-slug.md
```

Numbers are assigned sequentially in commit order; gaps are tolerated and never reused. Slugs should identify the
initiative from the filename alone (`0001-separate-compilation-and-linking.md`, not `0001-compiler.md`).

Each initiative document carries the standard work-document metadata block (`Version`, `Status`, `Kind: Initiative`).
For initiatives, `Version: YYYY-MM-DD` is the last substantive edit date, not the creation date. As phases become
actionable, link the spawned `plans/<kind>/<slug>.md` entries from the relevant phase section in the initiative, and
link back from each plan to its parent initiative.

When an initiative is opened, link it from the "Active initiatives" section of
[`l1/docs/roadmap.md`](../docs/roadmap.md). When it is closed, move the file into `initiatives/closed/` and move its
roadmap entry from "Active initiatives" to "Completed initiatives".
