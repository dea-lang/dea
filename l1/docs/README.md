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
- `decisions/` for ADR-style records linking design decisions to the closed plans that shaped them and the current docs
  where they are normatively recorded

Use `l1/work/plans/` for L1-local plans. If L1 work is actually shared with L0 or the monorepo, prefer one shared
root-owned plan under `work/plans/` instead of opening an L1-only follow-up plan for a mechanical downstream port.

## Roadmap

The L1 roadmap lives at [l1/docs/roadmap.md][roadmap]. It is the live direction document for L1 and is not
lifecycle-bound. Active initiatives under `l1/work/` execute the direction recorded there.

The roadmap, initiatives, and plans form a strict hierarchy by scope and lifetime:

- **Roadmap** ([l1/docs/roadmap.md][roadmap]): high level entry point. Captures L1's overall direction, lists active and
  completed initiatives, and records backlog ideas not yet promoted to initiatives. Edited in place; not closed.
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

For legibility, prefer reference-style file links with short, readable ids and end-of-file definitions.

Use initiative and plan filenames as the visible link text where that is the clearest reader-facing label, for example
`[0001-separate-compilation-and-linking][separate-compilation]` or
`[2026-07-17-interface-fingerprint-canonicalization-and-verification-noref][interface-fingerprints]`.

Keep reference ids short and readable, usually one or two words joined with hyphens. Avoid dates, numeric prefixes,
`noref`, and file extensions in the reference id unless a real uniqueness conflict leaves no cleaner option. For other
documents, a short document name such as `[project-status][project-status]` is preferred.

[roadmap]: roadmap.md
