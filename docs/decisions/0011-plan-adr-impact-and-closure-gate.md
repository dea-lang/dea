# ADR-0011: Plan ADR Impact and Closure Gate

- Decision date: 2026-07-26
- Last edited: 2026-08-21
- Status: Accepted

## Context

Dea's closed plans and initiatives are the detailed history behind its architectural decisions. The ADR directories
curate the most durable decisions, but the lifecycle previously relied on a manual finalization reminder to notice when
a plan required a new or amended ADR. A plan could close after introducing a lasting architectural constraint while
merely flagging the documentation gap for later work.

Plans also vary in scope. Dea-wide and shared decisions belong under `docs/decisions/`, while level-owned decisions
belong under the matching `lN/docs/decisions/` directory. Without an explicit declaration, reviewers and automation
cannot reliably distinguish a new decision from implementation of an existing ADR, a deliberate amendment, or work that
does not warrant an ADR.

## Decision

Every active or newly created plan and initiative contains exactly one `## ADR Impact` section. The section contains one
or more atomic records with the fields `Decision`, `Scope`, `Disposition`, `ADR`, and `Rationale`.

The allowed dispositions are:

- `Pending`: the architectural question remains unresolved while the document is active.
- `New ADR`: the decision requires a new record.
- `Amend ADR`: the decision materially changes an existing record.
- `Covered by ADR`: an existing record already governs the decision.
- `ADR not warranted`: the work contains no independent decision that merits an ADR.

`Pending` is forbidden at closure. Active `New ADR` records name the destination directory without reserving a number.
Closed `New ADR`, `Amend ADR`, and `Covered by ADR` records name exact ADR files. Dea-wide, shared, and
repository/tooling scopes route to `docs/decisions/`; level scopes route to the matching `lN/docs/decisions/`.

Closing a plan or initiative carries the ADR evidence in the same change. A new ADR must be added to its scope's
`INDEX.md`. An amended ADR must change. A covering ADR must add a resolvable `Related Plans` link to the closed
document. Every exact ADR reference must exist, be indexed, and match the declared scope.

Local pre-commit and unified CI validate the contract. They always validate the complete active inventory in the
selected Git tree and additionally validate every closed plan or initiative added, renamed, or modified by the change.
Untouched closed history is grandfathered; changing a historical document opts it into the current contract.

## Rationale

- Requiring the declaration when work is planned makes architectural questions visible before implementation hardens
  them accidentally.
- Allowing `Pending` in active documents preserves legitimate design exploration without weakening the closure gate.
- Same-change evidence prevents ADR work from becoming an unactionable handoff note.
- Scope-to-directory validation keeps level decisions out of the shared catalog and shared decisions out of a
  level-local catalog.
- Grandfathering untouched history avoids a mechanical rewrite of hundreds of closed documents while ensuring all future
  changes follow the stronger workflow.
- A structured Markdown list stays readable in plans and can be validated without introducing another data format or
  third-party parser.

## Consequences

- Plan and initiative authors must assess ADR impact explicitly, including when the conclusion is that no ADR is
  warranted.
- One plan may contain several impact records, and several plans may converge on one ADR; the workflow does not impose
  one ADR per plan.
- ADR numbers remain sequential within each directory and are assigned when the ADR is created, not reserved by active
  plans.
- Closing a plan that is covered by an existing ADR may still require editing that ADR to preserve its plan-provenance
  chain.
- Editing a legacy closed plan or initiative requires adding a compliant impact section even when the edit is otherwise
  small.
- The checker validates declarations and evidence. It does not infer architectural decisions from prose or determine
  whether reviewer judgment is substantively correct.

## Related Plans

- [work/plans/tools/closed/2026-07-26-shared-adr-impact-closure-gate-noref.md](../../work/plans/tools/closed/2026-07-26-shared-adr-impact-closure-gate-noref.md)
- [work/plans/bug-fixes/closed/2026-08-21-shared-adr-impact-push-range-chronology-noref.md](../../work/plans/bug-fixes/closed/2026-08-21-shared-adr-impact-push-range-chronology-noref.md)

## Current Docs

- [CLAUDE.md](../../CLAUDE.md): repository-wide ADR lifecycle policy
- [work/README.md](../../work/README.md): shared plan template and closure rules
- [l0/work/README.md](../../l0/work/README.md): L0 plan template and closure rules
- [l1/work/README.md](../../l1/work/README.md): L1 plan and initiative rules
- [docs/decisions/README.md](README.md): Dea-wide ADR scope and template
