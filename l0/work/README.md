# L0 Work Layout

This `l0/work/` tree holds lifecycle-bound documents for the Dea/L0 subtree.

Use `l0/docs/` for stable references, specs, implementation notes, and user guides. Use `l0/work/` for plans, proposals,
and archived execution history.

## Layout

- `plans/` for execution plans and operational work tracking
- `proposals/` for future or in-discussion changes not yet accepted as canonical

Plan categories:

- `plans/features/`: user-facing language, compiler, or standard-library features
- `plans/tools/`: repository tooling and operational workflows
- `plans/refactors/`: internal restructures that preserve current external behavior
- `plans/bug-fixes/`: defect fixes in any subsystem

Each plan category uses:

- active plans at the category root
- closed plans under `<category>/closed/`
- plan attachments under `<category>/attachments/` when needed

When closing a plan, `git mv` it into the corresponding `closed/` subdirectory, then grep for its filename across
`l0/docs/`, `l0/work/`, and any shared root docs/work files and update cross-references.

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
  - `path/to/module.l0`
- Test modules:
  - `path/to/test_module.l0`
- Repro: [Reproduction command or path] (optional)

## Summary

...

## ADR Impact

- Decision: [Short architectural question or durable choice]
  - Scope: [Dea-wide | Shared | Repository/tooling | L0 | N/A]
  - Disposition: [Pending | New ADR | Amend ADR | Covered by ADR | ADR not warranted]
  - ADR: [None | scope-matching decisions directory | exact indexed ADR path]
  - Rationale: [Why this disposition and destination are appropriate]
```

Every plan must contain exactly one `## ADR Impact` section using the complete schema and lifecycle rules in root
`AGENTS.md`. Repeat the record for independent architectural questions. Use `ADR not warranted` as the sole record when
the plan contains no ADR-worthy decision.

`Pending` is allowed while a plan is active, but it blocks closure. When closing a plan, resolve every record and
include the required ADR creation, amendment, or `Related Plans` link in the same change. Run
`python3 scripts/check_adr_impact.py --all-active` from the repository root while planning.

Accepted proposals should graduate into `l0/docs/specs/`, `l0/docs/reference/`, or `l0/docs/implementation/` rather than
remaining under `l0/work/`.
