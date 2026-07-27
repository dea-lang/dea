# Tool Plan

## Require explicit ADR impact and enforce it at plan closure

- Date: 2026-07-26
- Status: Completed
- Title: Require explicit ADR impact and enforce it at plan closure
- Kind: Tooling
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - Shared plan and initiative lifecycle policy
  - ADR scope and closure-evidence policy
  - Local pre-commit enforcement
  - Unified CI enforcement
  - Existing active plan and initiative inventory
- Origin: Root lifecycle policy and `scripts/check_adr_impact.py`
- Porting rule: Keep one shared ADR-impact contract; level work trees supply only their scope-specific examples and
  destination directories.
- Target status:
  - Shared plan and initiative lifecycle policy: Implemented
  - ADR scope and closure-evidence policy: Implemented
  - Local pre-commit enforcement: Implemented
  - Unified CI enforcement: Implemented
  - Existing active plan and initiative inventory: Implemented
- Subsystem: Lifecycle policy / ADR governance / pre-commit / CI
- Modules:
  - `CLAUDE.md`
  - `work/README.md`
  - `l0/work/README.md`
  - `l1/work/README.md`
  - `scripts/check_adr_impact.py`
  - `.pre-commit-config.yaml`
  - `.github/workflows/ci.yml`
- Test modules:
  - `scripts/tests/test_check_adr_impact.py`
- Related:
  - `docs/decisions/README.md`
  - `work/audits/architectural-decisions/2026-07-26/dea-architectural-decision-audit.md`
- Repro: `python3 scripts/check_adr_impact.py --all-active`

## Summary

The ADR catalog records accepted architectural decisions, but the current plan lifecycle only asks reviewers to notice
ADR-worthy work during finalization. It does not require plans to declare their ADR impact, does not block unresolved
decisions at closure, and does not verify that a new or amended ADR lands with the plan that requires it.

This plan establishes one structured `ADR Impact` contract for plans and initiatives, validates it locally and in CI,
backfills every active lifecycle document, and leaves untouched closed history grandfathered until a later change edits
it.

## ADR Impact

- Decision: Plans and initiatives must declare architectural impact explicitly, and closure must carry verifiable ADR
  evidence for every ADR-worthy decision.
  - Scope: Dea-wide
  - Disposition: New ADR
  - ADR: `docs/decisions/0011-plan-adr-impact-and-closure-gate.md`
  - Rationale: This is a durable repository lifecycle rule that controls how future architectural decisions are captured
    across every language level.

## Defaults Chosen

1. Every active or newly created plan and initiative carries exactly one `## ADR Impact` section.
2. Each atomic record uses the fields `Decision`, `Scope`, `Disposition`, `ADR`, and `Rationale`.
3. `Pending` is valid only while a document is active; closure requires `New ADR`, `Amend ADR`, `Covered by ADR`, or
   `ADR not warranted`.
4. New, amended, and covered ADR dispositions require same-change evidence when a plan or initiative closes.
5. Untouched closed history remains exempt; adding, renaming, or modifying a closed lifecycle document opts it into the
   current contract.
6. The checker uses only the Python standard library and validates the selected Git tree rather than unstaged ambient
   content.

## Implementation

1. Document the schema, scope routing, dispositions, and closure evidence in root and level workflow guidance.
2. Add a checker for working-tree active documents, the staged index, and explicit CI base/head trees.
3. Add focused parser, path, index, Git-diff, closure-evidence, discovery, and CLI tests.
4. Add an always-run pre-commit hook and an independent unified-CI policy job.
5. Backfill the current active plans and initiatives with reviewed impact records.
6. Create the Dea-wide workflow ADR and update its index.
7. Shift only the audit backlog's provisional root ADR numbers to account for the newly occupied ADR-0011.
8. When rebasing the audit onto later `dev`, keep its baseline totals frozen, declare post-baseline closed plans and
   ADRs, and advance only provisional numbers that later accepted ADRs now occupy.

## Non-Goals

- Inferring architectural decisions automatically from plan prose.
- Rewriting untouched closed plans or initiatives.
- Creating every ADR proposed by the architectural-decision audit.
- Renumbering any existing ADR.
- Changing compiler, runtime, language, standard-library, CLI, or artifact behavior.

## Verification Criteria

1. The checker accepts all active plans and initiatives and rejects malformed, unresolved, mis-scoped, or unindexed
   records.
2. Staged and base/head modes validate the proposed Git tree and changed closed documents, including active-to-closed
   moves.
3. Closure dispositions enforce new-ADR index updates, amended ADR changes, and closed-plan links from related ADRs.
4. Untouched legacy closed documents remain exempt.
5. Focused checker tests, the audit validator, `git diff --check`, and root pre-commit pass.
6. The workflow is enforced by both pre-commit and unified CI without changing the root Makefile.

## Completion Notes

- Added the standard-library-only checker with working-tree, staged-index, and explicit base/head modes. Its
  deterministic diagnostics validate active inventories, changed closed documents, scope routing, ADR indexes, closure
  evidence, and lifecycle moves while grandfathering untouched closed history.
- Backfilled the 14 active plans and two active initiatives on the rebased `dev` baseline with 56 reviewed decision
  records. The unresolved L1 `string` to `cstr` conversion remains explicitly `Pending` in both its plan and initiative.
- Added ADR-0011 and indexed it without renumbering existing ADRs. The audit backlog's eight provisional root numbers
  are ADR-0012 through ADR-0019. After L1 ADR-0022 landed on `dev`, its five provisional L1 numbers advanced to ADR-0023
  through ADR-0027. The 24 candidates and their `2 P0`, `16 P1`, and `6 P2` priorities are unchanged.
- Added the always-run staged pre-commit hook and independent full-history CI gate, and updated lifecycle, ADR,
  contributor, and agent-skill guidance.
- The 35 focused checker tests, live and staged ADR-impact checks, audit validator, Markdown formatting check, workflow
  and pre-commit configuration validation, copyright-header check, root pre-commit, and `git diff --check` passed. A
  final read-only red-team review found no remaining actionable correctness issue.
