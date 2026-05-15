# L1 Work Layout

This `l1/work/` tree holds lifecycle-bound documents for the Dea/L1 subtree.

Use `l1/docs/` for stable references, the L1 roadmap, and future accepted specs. Use `l1/work/` for initiatives, plans,
and any future proposals.

## Layout

- `initiatives/` for multiphase, cross-cutting bodies of work that sequence and motivate future plans (see "Initiatives
  and plans" below)
- `plans/` for L1-local execution plans and operational work tracking
- `proposals/` for future in-discussion L1 changes if that tree becomes necessary

Use `l1/work/` only for material owned by the L1 subtree. If work spans `l0/` and `l1/`, prefer a single shared document
under the repository-root `work/` tree with explicit targets rather than separate local follow-ups.

Plan categories:

- `plans/features/`: user-facing language, compiler, or standard-library features
- `plans/tools/`: repository tooling and operational workflows
- `plans/refactors/`: internal restructures that preserve current external behavior
- `plans/bug-fixes/`: defect fixes in any subsystem

Each plan category uses:

- active plans at the category root
- closed plans under `<category>/closed/`
- plan attachments under `<category>/attachments/` when needed

Active documents live at the category root. Realized, superseded, or otherwise closed documents move into
`<category>/closed/` with cross-references updated.

When closing a plan, `git mv` it (or `mv` it if not yet tracked) into the corresponding `closed/` subdirectory, then
grep for its filename across `l1/docs/`, `l1/work/`, and any shared root docs/work files and update cross-references.

## Plan Template

```markdown
# [Bug Fix | Feature | Refactor | Tool] Plan

## [Short Title]

- Date: YYYY-MM-DD
- Status: [Draft | In Progress | Closed (fixed/implemented)]
- Title: [Full descriptive title]
- Kind: [Bug Fix | Feature | Refactor | Tooling]
- Severity: [Low | Medium | High | Critical]
- Stage: [1 | 2 | Shared]
- Subsystem: [Subsystem name]
- Modules:
  - `path/to/module.l1`
- Test modules:
  - `path/to/test_module.l1`
- Repro: [Reproduction command or path] (optional)

## Summary

...
```

Accepted proposals should graduate into `l1/docs/specs/`, `l1/docs/reference/`, or `l1/docs/implementation/` rather than
remaining under `l1/work/`.

## Initiatives and plans

Use an initiative (`l1/work/initiatives/NNNN-*.md`) for a coordinated, multiphase body of work with a defined scope and
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

When an initiative is opened, link it from the "Active initiatives" section of [`l1/docs/roadmap.md`][roadmap]. When it
is closed, move the file into `initiatives/closed/` and move its roadmap entry from "Active initiatives" to "Completed
initiatives".

## Initiative and plan membership

Initiative documents carry two membership fields in their metadata block, after `Kind: Initiative`:

- `Open plans:` — bulleted list of repo-root paths to currently open spawned plans, or `(none)`.
- `Closed plans:` — bulleted list of repo-root paths to closed spawned plans, or `(none)`.

Plans spawned by an initiative carry a `Parent Initiative:` field in their metadata block, immediately after `Stage:`,
pointing at the initiative file using the repo-root path. Standalone plans must not carry this field.

Keep the two sides in sync throughout the plan lifecycle:

- When a plan is spawned from an initiative: add its path to `Open plans:` in the initiative and add
  `Parent Initiative:` to the plan's metadata.
- When a plan is closed: move its path from `Open plans:` to `Closed plans:` in the initiative.
- When an initiative is closed: move its file to `initiatives/closed/`; leave `Open plans:` and `Closed plans:`
  unchanged.

The `Parent Initiative:` field is the authoritative signal for initiative membership. The `Related:` field may also list
an initiative when the plan merely references it without being owned by it; that alone does not make the plan a member.

[roadmap]: ../docs/roadmap.md
