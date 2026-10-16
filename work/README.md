# Root Work Layout

This root `work/` tree is for Dea-wide and monorepo-wide lifecycle artifacts.

Use `docs/` for stable current-state or normative material. Use `work/` for documents whose purpose is planning,
proposal discussion, implementation tracking, or closure history.

Today this tree contains:

- shared plans that span more than one language level or the monorepo itself
- future shared proposals that are not yet accepted into `docs/`
- closed history for shared work items

## Layout

- `plans/` for execution plans and operational work tracking
- `proposals/` for future or in-discussion changes not yet accepted as canonical

Create subdirectories only when they are needed for real documents.

## Shared Plans

Root plans live under `work/plans/` and use these categories:

- `features/`
- `bug-fixes/`
- `refactors/`
- `tools/`

Active plans live at the category root. Closed plans live under `<category>/closed/`. Supporting plan attachments live
under `<category>/attachments/` when needed. Attachments hold point-in-time evidence or other lifecycle material that
does not belong in stable `docs/`; they remain in the category attachment directory when the related plan closes, with
links updated to the plan's new location. Do not commit raw benchmark samples, build logs, or binaries when a curated
report is sufficient.

Determine language-level ownership before counting compiler stages. If every target belongs to one language level, put
the plan in that level's `work/` tree even when it coordinates multiple compiler stages or implementations. Single-level
ownership takes precedence over cross-stage or seeded-port coordination.

Use a root shared plan by default when any of these are true:

- the same fix or refactor spans multiple language levels
- an implementation in one language level was seeded from another level and the change should transfer between them
- the design decision is shared across language levels even if code lands in more than one subtree

Shared plans stay open until every in-scope target is implemented or explicitly deferred.

Required shared-plan metadata, in addition to the standard plan block:

- `Scope: Shared`
- `Targets:` one line per in-scope implementation
- `Origin:` where the design or first implementation is expected to settle
- `Porting rule:` whether downstream should be a mechanical port or may diverge intentionally
- `Target status:` one line per target using `Pending`, `In Progress`, `Implemented`, or `Deferred: <reason>`

Do not open a separate level-local follow-up plan just to port a mechanical parity fix already covered by a shared root
plan.

## Plan Priority and Severity

Use exactly one of these fields in a plan's metadata, according to its kind:

- `Priority` for Feature, Refactor, and Tooling plans: the relative importance of scheduling the proposed work against
  other work, considering expected benefit and dependencies. It is not a measure of implementation effort or risk, a
  deadline, or an automatic execution order.
- `Severity` for Bug Fix plans: the impact of the existing defect on correctness, safety, or supported workflows,
  considering affected scope and available workarounds. It does not by itself set scheduling urgency.

Both fields use `Low`, `Medium`, `High`, or `Critical`:

| Value    | Priority (non-defect plans)                                                                                      | Severity (bug-fix plans)                                                                                                              |
| -------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Low      | Useful optional improvement that can be deferred without blocking current objectives.                            | Minor or narrowly scoped defect with little practical disruption and an easy workaround.                                              |
| Medium   | Meaningful improvement that supports current objectives without blocking a key milestone.                        | Material impairment with a practical workaround or limited affected scope.                                                            |
| High     | Important capability or prerequisite for a key milestone that should be scheduled ahead of routine improvements. | Major correctness or supported-workflow failure with no satisfactory workaround for affected cases.                                   |
| Critical | Essential work whose deferral blocks an explicitly identified immediate project objective.                       | Severe safety or correctness failure, such as memory corruption, silent wrong results, or widespread loss of essential functionality. |

Record the concrete rationale in the plan's summary, especially for High or Critical ratings. State actual deadlines,
release blockers, and dependencies explicitly instead of encoding them only in a rating. `Stdlib Tier` independently
classifies capability groups defined in [l1/docs/roadmap.md](../l1/docs/roadmap.md#standard-library-tiers); it does not
mechanically determine Priority or Severity.

When renaming existing active non-defect metadata from Severity to Priority, retain its rating unless separately
reassessed. This preserves the recorded ranking without claiming that historical ratings followed these definitions.
Leave historical closed plans and evidence unchanged.

## ADR Impact

Every plan must contain exactly one `## ADR Impact` section using the schema, scopes, dispositions, and closure rules in
`AGENTS.md`. Add one record per independent architectural question. Root plans normally use `Dea-wide`, `Shared`, or
`Repository/tooling`; they may use `L0`, `L1`, or a future `L<N>` for a targeted level decision. A plan with no
ADR-worthy decision uses one `ADR not warranted` record.

`Pending` is allowed while a plan is active, but it blocks closure. When closing a plan, resolve every record and
include the required ADR creation, amendment, or `Related Plans` link in the same change. Run:

```bash
python3 scripts/check_adr_impact.py --all-active
```

Use this body fragment in every new root plan:

```markdown
## ADR Impact

- Decision: [Short architectural question or durable choice]
  - Scope: [Dea-wide | Shared | Repository/tooling | L0 | L1 | future L<N> | N/A]
  - Disposition: [Pending | New ADR | Amend ADR | Covered by ADR | ADR not warranted]
  - ADR: [None | scope-matching decisions directory | exact indexed ADR path]
  - Rationale: [Why this disposition and destination are appropriate]
```
