# Dea Architectural-Decision Audit Manifest

- Repository: <https://github.com/googlielmo/dea-lang>
- Audited source remote: <https://github.com/googlielmo/DEA.git>
- Baseline branch: `dev`
- Audited commit: `9e8e83a6c5ed545069312a91a27ac7a79055a614`
- Baseline verification: local `origin/dev` and the remote `refs/heads/dev` both resolved to the audited commit on
  2026-07-26
- Audit date: 2026-07-26
- Reviewer: Codex, with parallel semantic-review batches and a global reconciliation pass

## Included corpus

The primary plan totals include every Markdown file matching:

- `work/plans/*/closed/*.md`
- `l0/work/plans/*/closed/*.md`
- `l1/work/plans/*/closed/*.md`

Closed initiatives are inventoried and analyzed separately:

- `l1/work/initiatives/closed/*.md`

The resulting corpus contains 233 closed plans and 2 closed initiatives. Plan dates come from each file's explicit
`Date` metadata; initiative dates come from `Version`. Filename-date cohorts are retained only for the requested review
checkpoints, because several historical filenames and metadata dates differ.

ADR coverage was checked from each index and then against every numbered ADR file in:

- `docs/decisions/`
- `l0/docs/decisions/`
- `l1/docs/decisions/`

## Post-baseline corpus and numbering context

- Post-baseline closed plan: `l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md`
- Post-baseline closed plan: `l1/work/plans/bug-fixes/closed/2026-07-26-stage1-cross-platform-ci-regressions-noref.md`
- Post-baseline closed plan: `l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md`
- Post-baseline closed plan: `work/plans/tools/closed/2026-07-26-shared-adr-impact-closure-gate-noref.md`
- Post-baseline ADR: `docs/decisions/0011-plan-adr-impact-and-closure-gate.md`
- Post-baseline ADR: `l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md`

The closed plans and ADRs above were created after the audited commit. Post-baseline closed plans and ADRs remain
excluded from the audited inventories and all baseline totals, but post-baseline ADRs occupy their official directory
numbers when the missing-ADR backlog proposes the next contiguous sequence.

## Excluded from primary totals

Active plans, proposals outside the closed corpus, issue discussions, commit messages, pull requests, source code, and
non-closed initiatives are excluded from the primary plan and historical-event totals. A file physically present under a
required `closed/` pattern is still inventoried if its internal status says `Draft` or `Withdrawn`; it contributes
decisions only when its closure records an actual settled historical choice. Current source, normative documentation,
and ADRs may be consulted to determine whether a closed-plan decision remains current or has been superseded.

## Counting definition

An architectural decision is a settled choice among plausible alternatives that can be expressed as a durable rule or
direction and that constrains future language, compiler, runtime, ABI, standard-library, bootstrap, CLI, portability, or
materially significant repository architecture.

Each historical-event row records one atomic adoption event in a primary source. Repeated restatements, mechanical
ports, implementation phases, files to edit, tests, bug symptoms, root-cause findings by themselves, and consequences
forced by an already-counted choice are not counted independently.

The canonical ledger groups semantically identical historical events and follows documented supersession and retraction
chains. Historical-event totals therefore remain larger than the count of current distinct decisions.

Initiative statements that merely consolidate an already-counted plan decision are not counted a second time.
Initiative-only atomic choices remain in the historical ledger with `included_in_primary_total=No`, so their
contribution can be reported without changing the primary closed-plan event total.

## Review order

1. L0 plans through February 2026
2. L0 plans through March 2026
3. Remaining L0, shared, and L1 plans through April 2026
4. May 2026 plans
5. June 2026 plans
6. July 2026 plans and closed initiatives
7. Global deduplication and supersession review
8. ADR coverage and missing-ADR review

## Known limitations

- The evidence base is documentary. A later code change is not treated as supersession without documentary or strong
  semantic evidence.
- `Medium` confidence records rely on a plan's implemented approach or outcome when no explicit decision label exists.
  `Low` confidence records are retained only when architecturally important and are listed for human review.
- ADR coverage is reviewer judgment: an ADR can cover several atomic decisions, and a decision can be only partially
  represented by an ADR.
- Quartiles use the inclusive method over the 233 per-plan decision counts.
- Line citations are tied to the audited commit above and may drift on later branches.
- The audit is conservative by design and may omit choices whose source plan never makes their durable character
  sufficiently clear.
