# L1 Documentation Layout

This `l1/docs/` tree holds stable documentation for the Dea/L1 subtree.

At the current bootstrap stage, this tree is still intentionally narrow:

- L1 bootstrap/reference documents
- future L1 language/compiler specs once they exist

L1-local lifecycle artifacts live in the sibling `l1/work/` tree. Dea-wide stable docs live under the root `docs/` tree,
while Dea-wide lifecycle artifacts live under the root `work/` tree.

## Layout

- `roadmap.md` for the singular evergreen L1 roadmap
- `project-status.md` for the current L1 bootstrap status snapshot
- `reference/` for L1-local bootstrap and implementation references
- `specs/` for future L1-local specifications
- `implementation/` for future accepted implementation notes if needed

Use `l1/work/plans/` for L1-local plans. If L1 work is actually shared with L0 or the monorepo, prefer one shared
root-owned plan under `work/plans/` instead of opening an L1-only follow-up plan for a mechanical downstream port.

## Roadmap

The L1 roadmap lives at [l1/docs/roadmap.md](roadmap.md). It is the live direction document for L1 and is not
lifecycle-bound. Active initiatives under `l1/work/` execute the direction recorded there.

The roadmap, initiatives, and plans form a strict hierarchy by scope and lifetime:

- **Roadmap** ([l1/docs/roadmap.md](roadmap.md)): high level entry point. Captures L1's overall direction, lists active
  and completed initiatives, and records backlog ideas not yet promoted to initiatives. Edited in place; not closed.
- **Initiative** (`l1/work/initiatives/NNNN-*.md`): a coordinated, multiphase body of work with a defined scope and an
  end state. Records cross-cutting design decisions, sequences phases, and spawns one or more plans as phases become
  actionable. There can be many initiatives over L1's lifetime; each is opened, worked on, and eventually closed.
- **Plan** (`l1/work/plans/<kind>/<slug>.md`): a single change or work item with a defined start and end. Often spawned
  by an initiative phase; can also stand alone for work that does not warrant an initiative.

Reach for a roadmap edit when L1's overall direction shifts. Reach for a new initiative when a body of work spans
multiple plans across categories, when decisions made now constrain plans that will only be written later, or when the
sequencing and dependency structure between phases is itself the artifact worth recording. Reach for a plan directly
otherwise (even a large one).

When editing the roadmap, keep it directional rather than release-note-like: routine bug-fix history belongs in closed
plans and, when needed, `project-status.md`. Use roadmap completed sections for shipped work that materially changes the
L1 baseline, direction, or future planning constraints.

### Roadmap link legibility rules

For legibility, the visible link text format in `roadmap.md` is specially abbreviated as follows:
` [NNNN-initiative-slug](../work/initiatives/NNNN-initiative-slug.md)` for initiatives, and
`[plan-slug](../work/plans/<kind>/plan-slug.md)` for plans. For other documents, the visible link text is just the
filename without extension, for example `[project-status](project-status.md)`.
