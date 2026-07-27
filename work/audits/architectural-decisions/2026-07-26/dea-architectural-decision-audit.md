# Dea Architectural-Decision Audit

Audit date: 2026-07-26

Repository: <https://github.com/googlielmo/dea-lang>

Audited source remote: <https://github.com/googlielmo/DEA.git>

Baseline: `dev` at `9e8e83a6c5ed545069312a91a27ac7a79055a614`

## Executive summary

At the audited commit, Dea has **47 accepted ADRs**, but those ADRs represent only the curated portion of a
substantially larger design history distributed across **233 closed plans**.

The closed plans contain **640 atomic historical architectural-decision events**. After consolidating repeated choices
and following documented supersession chains, they support **595 current, distinct, plan-grounded architectural
decisions**. The two closed L1 initiatives are reported separately: they add one initiative-only historical event and
one current decision. The expanded plan-plus-initiative universe is therefore **641 historical events** and **596
current distinct decisions**.

The history is active rather than merely cumulative. Of the 640 primary events, 600 are retained, 31 were superseded, 7
are deferred, 2 are historical only, and none are retracted or unclear. The ledger records 58 evidenced relationships:
28 supersessions, 22 broadenings, 5 narrowings, and 3 transfers into stable documentation.

Of the 595 current plan-grounded decisions, 535 are judged ADR-worthy. Existing ADRs directly or broadly cover 400,
partially cover 31, and leave 104 uncovered. Strict ADR coverage is therefore **74.77%** of ADR-worthy current plan
decisions; counting partial coverage raises it to **80.56%**. The one initiative-only current decision is also
uncovered, so the combined universe has 105 missing decisions and a strict coverage rate of **74.63%**.

Those 105 uncovered current decisions should not become 105 new ADRs. This audit proposes **24 coherent ADR
candidates**: 2 P0, 16 P1, 6 P2, and no P3. Their provisional numbering yields **23 new ADR documents and one
amendment** to the existing `L0-ADR-0014`; no accepted ADR is renumbered. The two most urgent gaps are the shared
`for`-header control-flow/cleanup contract and the L0 release identity/integrity/immutable-publication contract.

## Post-audit resolution

On 2026-07-27, all 24 candidates were implemented in their reserved directory sequences: 23 new ADRs were added and L0
ADR-0014 was amended. The accepted records are indexed under [Dea-wide ADRs](../../../../docs/decisions/INDEX.md),
[L0 ADRs](../../../../l0/docs/decisions/INDEX.md), and [L1 ADRs](../../../../l1/docs/decisions/INDEX.md).

This resolution does not rewrite the audit baseline. The event, canonical-decision, historical ADR inventory, and
coverage totals below continue to describe the audited baseline recorded above; the validator and generated statistics
carry a separate current-tree candidate-resolution overlay.

## Deliverables

- [Audit manifest](audit-manifest.md)
- [Closed-plan and initiative inventory](closed-plan-inventory.csv)
- [Historical decision-event ledger](architectural-decision-events.csv)
- [Canonical architectural-decision ledger](canonical-architectural-decisions.csv)
- [Supersession and retraction map](decision-relationships.csv)
- [Existing ADR coverage inventory](existing-adr-coverage.csv)
- [Machine-readable missing-ADR backlog](missing-adr-candidates.csv)
- [Human-readable missing-ADR backlog](missing-adr-candidates.md)
- [Recomputed aggregate statistics](audit-statistics.json)
- [Audit validator and statistics script](../../../../scripts/validate_architectural_decision_audit.py)

The CSV files are the authoritative detailed records. This report is a human-readable synthesis of those ledgers.

The canonical CSV retains all 618 historical canonical identities so event rows never lose their deduplication target.
Its `included_in_current_total=Yes` filter yields the 596 current rows, while `incoming_relationship_ids` and
`outgoing_relationship_ids` link each canonical identity to the supersession map. Thus historical identities remain
auditable without being silently included in the current-decision total.

## Methodology

### Baseline and corpus

The audit uses the immutable baseline recorded in the header and manifest. On the audit date, local `origin/dev` and
remote `refs/heads/dev` both resolved to that baseline.

Every Markdown file under the three required closed-plan patterns was read in full, including outcomes and completion
notes. Every closed L1 initiative was also read, but initiatives were kept outside the primary plan totals. Active
plans, issue discussions, commits, pull requests, and draft proposals outside the closed corpus were excluded from
primary counts.

Two files physically under the required `closed/` patterns still carry an internal `Status: Draft`. They remain in the
required 233-path inventory as zero-decision records, but none of their provisional proposal content enters the
historical-event or current-decision totals. The same conservative treatment applies to the one closed-withdrawn plan.

Dates in aggregate tables use the source file's explicit `Date` metadata. Nine files have a different filename date; the
inventory records each mismatch.

### Decision extraction

The review treated a choice as architectural only when it selected among plausible alternatives and imposed a durable
constraint on the language, compiler, runtime, ABI, standard library, bootstrap, public tooling, or material repository
architecture. It did not count phases, files to edit, tests, bug symptoms, root causes by themselves, mechanical ports,
repeated restatements, or consequences forced by a prior decision.

Each event was made atomic. Independently choosable syntax, semantic, ABI, module-boundary, and linkage choices were
split even when one source sentence combined them. Conversely, cross-stage ports of the same semantic rule were grouped
rather than inflated into separate decisions.

### Chronology, deduplication, and status

Plans were reviewed chronologically in six batches, and candidate canonical identities were maintained during each
batch. A global reconciliation then:

1. removed non-architectural and duplicate candidate events;
2. split three composite events whose parts could have been chosen independently;
3. grouped semantically identical events;
4. followed evidenced supersession, narrowing, broadening, and documentation transfer chains; and
5. checked cross-level and cross-stage parity decisions for accidental double counting.

Code change alone was not accepted as proof of supersession. A relationship needed later documentary evidence or a
strong semantic replacement recorded in current normative documentation.

### Classification and confidence

Each event has exactly one primary category. This report uses that controlled category taxonomy as its normalized
subsystem distribution; free-form plan `subsystem` metadata remains available in the inventory. Scope distinguishes
language-level, compiler-stage, shared, and repository decisions.

`Explicit` means the source stated a default, rule, decision, non-goal, or settled contract. `Embedded` means the
durable choice is clear from the adopted approach or outcome. `Inferred` would require interpretive reconstruction.
Confidence is recorded independently as High, Medium, or Low.

### ADR coverage

The three ADR indexes were used as starting inventories and checked against all underlying numbered ADR files. Coverage
was then assessed per current canonical decision, not per plan. “Strictly covered” below means either `Directly covered`
or `Covered as part of a broader ADR`; partial coverage is shown separately.

The distinction between facts and reviewer judgment is deliberate:

- paths, dates, line ranges, source wording, ADR files, and arithmetic are auditable facts;
- atomicity, canonical grouping, current status, ADR coverage, and ADR worthiness are reviewer judgments backed by the
  cited evidence.

## Headline counts

| Measure                                  | Primary closed-plan universe | Initiative supplement | Combined universe |
| ---------------------------------------- | ---------------------------: | --------------------: | ----------------: |
| Closed records                           |                    233 plans |         2 initiatives |       235 records |
| Historical decision events               |                          640 |                     1 |               641 |
| Current distinct decisions               |                          595 |                     1 |               596 |
| Current retained decisions               |                          588 |                     1 |               589 |
| Current deferred decisions               |                            7 |                     0 |                 7 |
| ADR-worthy current decisions             |                          535 |                     1 |               536 |
| Strictly ADR-covered current decisions   |                          400 |                     0 |               400 |
| Partially ADR-covered current decisions  |                           31 |                     0 |                31 |
| ADR-worthy current decisions not covered |                          104 |                     1 |               105 |
| Strict ADR coverage                      |                       74.77% |                    0% |            74.63% |

The primary totals answer the closed-plan audit question. Combined totals are provided only as a clearly labeled
supplement.

## Closed-plan distribution

### By repository area

| Repository area | Closed plans | Historical events | Events per plan |
| --------------- | -----------: | ----------------: | --------------: |
| Root/shared     |           70 |               127 |            1.81 |
| L0              |          105 |               193 |            1.84 |
| L1              |           58 |               320 |            5.52 |
| **Total**       |      **233** |           **640** |        **2.75** |

L1 has only one quarter of the plans but exactly half of the historical events. Its feature plans frequently established
several independently choosable language, ABI, interface, and runtime contracts at once.

### By plan kind

| Kind      | Closed plans | Historical events | Events per plan |
| --------- | -----------: | ----------------: | --------------: |
| Bug Fix   |           98 |                74 |            0.76 |
| Feature   |           92 |               451 |            4.90 |
| Refactor  |           27 |                82 |            3.04 |
| Tool      |           16 |                33 |            2.06 |
| **Total** |      **233** |           **640** |        **2.75** |

Bug-fix plans are the largest plan class, but many restore an already-settled contract and therefore contribute no new
event. Even so, their 74 events show that architectural rules were sometimes discovered only through correctness or
parity failures.

### By metadata month

| Month     | Closed plans | Historical events | Events per plan |
| --------- | -----------: | ----------------: | --------------: |
| 2026-02   |           23 |                67 |            2.91 |
| 2026-03   |           61 |               107 |            1.75 |
| 2026-04   |           75 |               186 |            2.48 |
| 2026-05   |           15 |                76 |            5.07 |
| 2026-06   |           33 |               109 |            3.30 |
| 2026-07   |           26 |                95 |            3.65 |
| **Total** |      **233** |           **640** |        **2.75** |

April is the largest month by both plans and events as L1 acquired its numeric, module-interface, ABI, const, callable,
and standard-library surfaces. May is the densest month per plan because arrays, slices, unsafe access, symbol mangling,
runtime archives, and ownership fixes interacted in a small number of large plans. June and July shift toward shared
recovery/control-flow contracts, runtime validation, separate compilation, artifact identity, and release architecture.

### Decisions per plan

| Plan decision count |   Plans |    Share |
| ------------------- | ------: | -------: |
| Zero                |      84 |   36.05% |
| One                 |      33 |   14.16% |
| Two to five         |      75 |   32.19% |
| Six or more         |      41 |   17.60% |
| **Total**           | **233** | **100%** |

| Statistic      | Value |
| -------------- | ----: |
| Mean           | 2.747 |
| Median         |     1 |
| Lower quartile |     0 |
| Upper quartile |     4 |
| Maximum        |    16 |

The zero-decision plans are retained in the inventory. Their presence is important: a closed plan can be useful
implementation or repair work without settling a new architectural question.

The most decision-dense plan is
`l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md` with 16
events. Two plans have 15 events: the fixed-size-array primitive and the Stage 1 slice/intrinsic plan. These counts
reflect atomic choices, not numbered implementation phases.

## Batch review checkpoints

“Checkpoint candidates” are the initial semantic extractions reported at the end of each chronological pass. “Final
events” are the plan events that survived global atomicity and deduplication review.

| Batch                       |         Records reviewed |    Checkpoint candidates |      Final plan events | Final zero-decision plans | Unresolved Medium-confidence items | Suspected links/stories at checkpoint |
| --------------------------- | -----------------------: | -----------------------: | ---------------------: | ------------------------: | ---------------------------------: | ------------------------------------: |
| L0 through February         |                 23 plans |                       73 |                     67 |                         2 |                                  2 |                                     7 |
| L0 through March            |                 61 plans |                      132 |                    107 |                        27 |                                  0 |                                    12 |
| Shared and L1 through April |                 80 plans |                      243 |                    206 |                        38 |                                  0 |                                     5 |
| May                         |                 15 plans |                       82 |                     76 |                         1 |                                  0 |                                     5 |
| June                        |                 29 plans |                       98 |                     89 |                        10 |                                  0 |                                    12 |
| July and initiatives        | 25 plans + 2 initiatives | 111 plan + 31 initiative | 95 plan + 1 initiative |    6 plans + 1 initiative |                                  2 |                                     6 |

The candidate-to-final reduction mainly removed mechanical ports, local data structures, draft-only directions, and
initiative restatements. Four atomic splits add events back after those exclusions. No unresolved Low-confidence item
remains.

The two closed initiatives are:

| Initiative                                                              | Final unique events | Treatment                                                                                                       |
| ----------------------------------------------------------------------- | ------------------: | --------------------------------------------------------------------------------------------------------------- |
| `l1/work/initiatives/closed/0002-runtime-static-library.md`             |                   1 | Adds the initiative-only rule that the runtime split is L1-only while L0 stays header-only at the 1.0 boundary. |
| `l1/work/initiatives/closed/0004-array-primitives-and-unsafe-marker.md` |                   0 | All architectural statements consolidate decisions already sourced to constituent plans.                        |

## Decision distribution by subsystem

The primary category is the normalized subsystem bucket. Historical counts use the 640 closed-plan events. Current
counts use the 595 plan-grounded current decisions.

| Primary category / normalized subsystem | Historical events | Current decisions |
| --------------------------------------- | ----------------: | ----------------: |
| ABI and linking                         |                71 |                69 |
| Backend and C emission                  |                16 |                14 |
| Bootstrap and self-hosting              |                16 |                14 |
| CLI and distribution                    |                68 |                64 |
| Diagnostics and recovery                |                31 |                24 |
| Frontend architecture                   |                39 |                36 |
| Language semantics                      |                48 |                47 |
| Language syntax                         |                35 |                34 |
| Ownership and memory safety             |                41 |                39 |
| Portability                             |                16 |                14 |
| Repository and process architecture     |                52 |                47 |
| Runtime                                 |                41 |                38 |
| Semantic analysis                       |                20 |                20 |
| Standard library                        |                71 |                66 |
| Type system                             |                75 |                69 |
| **Total**                               |           **640** |           **595** |

Type-system choices are the largest historical subsystem, closely followed by ABI/linking and the standard library.
Together those three account for 217 historical events. The relatively small backend count reflects the conservative
rule against counting mechanical lowering consequences; backend rows remain only where the generated-C or
compiler/runtime boundary is itself a durable contract.

Diagnostics has the largest proportional historical contraction: 31 events become 24 current decisions. This reflects
the move from fail-fast and phase-barrier designs to recoverable logical lexer tokens, partial parsing, and later
semantic/backend gates.

## Distribution by language level and compiler stage

### Detailed scope

| Scope              | Historical events | Current plan-grounded decisions |
| ------------------ | ----------------: | ------------------------------: |
| Dea-wide           |                 9 |                              10 |
| Shared L0/L1       |                95 |                              87 |
| L0                 |               105 |                             102 |
| L0 Stage 1         |                12 |                               7 |
| L0 Stage 2         |                43 |                              33 |
| L1                 |               261 |                             251 |
| L1 Stage 1         |                61 |                              56 |
| L1 Stage 2         |                 0 |                               0 |
| Repository/tooling |                54 |                              49 |
| **Total**          |           **640** |                         **595** |

Canonical grouping can broaden scope, which is why Dea-wide current decisions can exceed Dea-wide historical events.
Aggregating the detailed scopes yields 160 historical L0-specific events, 322 L1-specific events, 95 shared events, 9
Dea-wide events, and 54 repository/tooling events. The current equivalents are 142 L0-specific, 307 L1-specific, 87
shared, 10 Dea-wide, and 49 repository/tooling decisions.

No closed plan establishes an L1 Stage 2-specific decision. L1 decisions in the corpus are language-level or Stage
1-specific; a future mechanical port must not be counted again unless it deliberately diverges.

### Compiler-stage bucket

| Stage bucket                  | Historical events | Current plan-grounded decisions |
| ----------------------------- | ----------------: | ------------------------------: |
| Stage 1-specific              |                73 |                              63 |
| Stage 2-specific              |                43 |                              33 |
| Cross-stage or language-level |               470 |                             450 |
| Repository/tooling            |                54 |                              49 |
| **Total**                     |           **640** |                         **595** |

The cross-stage bucket includes choices scoped to L0, L1, Shared L0/L1, or Dea-wide rather than to one compiler
implementation. This prevents a semantic choice implemented in both stages from being counted twice.

## Historical status, explicitness, and confidence

### Event status

| Status          | Historical plan events |
| --------------- | ---------------------: |
| Retained        |                    600 |
| Superseded      |                     31 |
| Retracted       |                      0 |
| Deferred        |                      7 |
| Historical only |                      2 |
| Unclear         |                      0 |
| **Total**       |                **640** |

The canonical ledger has 618 historical decision identities: 589 retained, 7 deferred, 20 superseded, and 2
historical-only. Direct replacement events are grouped under one canonical question, so 31 superseded events become 20
non-current canonical identities. The 596 current combined decisions are the 589 retained plus 7 deferred rows.

### Explicitness

| Explicitness | Historical plan events |
| ------------ | ---------------------: |
| Explicit     |                    622 |
| Embedded     |                     18 |
| Inferred     |                      0 |

### Confidence

| Confidence | Historical plan events |
| ---------- | ---------------------: |
| High       |                    636 |
| Medium     |                      4 |
| Low        |                      0 |

The four Medium-confidence items are deliberately exposed for review:

- `DEA-DEC-0035`: mixed `int`/`byte` equality and relational expressions remain valid numeric operations;
- `DEA-DEC-0036`: a `with` header binding remains in scope through cleanup;
- `DEA-DEC-0626`: semantic types are finalized after source-signature resolution; and
- `DEA-DEC-0627`: an interface public surface is validated against its transitive semantic closure.

All four are architecturally important and supported by adopted plan behavior, but their sources do not label them as
standalone decisions. No Low-confidence event is included.

## Major supersession and evolution stories

The complete 58-edge graph is in [decision-relationships.csv](decision-relationships.csv). These are the most important
architectural transitions:

| Architectural question                | Earlier event(s)                       | Later event(s) or documentation        | Current result                                                                                                                                                                                     |
| ------------------------------------- | -------------------------------------- | -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Parser result contract                | `DEA-DEC-0011`                         | `DEA-DEC-0026`                         | A diagnostics-only `ParseResult` replaced the public singleton parse-error state.                                                                                                                  |
| Lexer/parser recovery                 | `DEA-DEC-0025`, `0028`, `0458`, `0268` | `DEA-DEC-0457`, `0460`, `0463`, `0467` | Recoverable logical wrapper tokens, parser execution after recoverable lexing errors, and code-point columns replaced fail-fast/direct-copy/pre-parse-barrier behavior.                            |
| Floating zero division                | `DEA-DEC-0202`                         | `DEA-DEC-0225`                         | A language-defined non-panicking result replaced delegation to host C behavior.                                                                                                                    |
| Wide integer family                   | `DEA-DEC-0217`, `0218`, `0219`         | `DEA-DEC-0231`, `0232`, `0233`         | The independently choosable temporary reservations of `uint`, `long`, and `ulong` ended when each became a defined builtin.                                                                        |
| Fixed-array length syntax             | `DEA-DEC-0396`                         | `DEA-DEC-0498`                         | Visible local and qualified const references broadened the initial literal-only grammar.                                                                                                           |
| `len` operand domain                  | `DEA-DEC-0427`                         | Current reference documentation        | String support broadened the initial array/slice-only rule; no later eligible closed plan records that extension.                                                                                  |
| Case default spelling                 | `DEA-DEC-0443`, `0444`                 | `DEA-DEC-0450`, `0574`                 | L1 is wildcard-only; L0 retains warning-bearing `else` compatibility through 1.x, with removal deferred to L0 2.0.                                                                                 |
| Module graph and interface activation | `DEA-DEC-0483`, `0486`, `0471`         | `DEA-DEC-0619`, `0622`, `0590`         | One canonical-origin module graph, recursive require/link closure, require-only semantic activation, and one effective-surface fingerprint replaced narrower direct-import/reserved-field designs. |
| Borrowed ARC parameter reassignment   | `DEA-DEC-0002`                         | `DEA-DEC-0310`                         | Entry stabilization for syntactically reassigned borrowed parameters replaced lazy first-assignment promotion.                                                                                     |
| Bootstrap native identity             | `DEA-DEC-0117`, `0154`                 | `DEA-DEC-0133`, `0134`, `0570`, `0563` | Raw retained-C identity remains universal; native identity is explicitly normalized or waived by platform without mutating executable artifacts.                                                   |
| Raw pointer safety                    | `DEA-DEC-0380`, `0388`                 | `DEA-DEC-0385`, `0533`                 | Unsafe-function gating and checked-by-default generated pointer access replaced transitional ungated and direct-unchecked indexing.                                                                |
| Documentation publication ownership   | `DEA-DEC-0078`                         | `DEA-DEC-0158`, `0160`, `0582`         | Destination-owned artifact import and explicit authorization replaced direct cross-repository checkout/commit/push.                                                                                |
| Stable release identity and notes     | `DEA-DEC-0147`, `0153`                 | `DEA-DEC-0571`, `0572`                 | `l0-vX.Y.Z` tags and checked-in notes used unchanged replaced date tags and Git-log-generated bodies.                                                                                              |
| Standard-library module names         | `DEA-DEC-0259`, `0092`                 | `DEA-DEC-0421`, `0381`                 | `std.integer` replaced the retained `std.math` integer-module name, and `sys.memory` replaced `sys.unsafe`; their module-boundary policies remain.                                                 |

The graph contains no retraction edge because the corpus provides no clear deliberate withdrawal without a successor.
That zero is a finding, not an assumption: abandoned drafts were not promoted to adopted historical events.

## ADR inventory and coverage

### Existing ADR inventory

| ADR area    | Accepted ADRs |
| ----------- | ------------: |
| Root/shared |            10 |
| L0          |            16 |
| L1          |            21 |
| **Total**   |        **47** |

All 47 index entries resolve to underlying ADR files and every numbered ADR file appears in its directory's index.

### Coverage of current plan-grounded decisions

| Coverage classification          | Current decisions |
| -------------------------------- | ----------------: |
| Directly covered                 |               286 |
| Covered as part of a broader ADR |               114 |
| Partially covered                |                31 |
| Not covered                      |               104 |
| ADR not warranted                |                60 |
| Unclear                          |                 0 |
| **Total**                        |           **595** |

The strict numerator is 400 and the ADR-worthy denominator is 535, yielding 74.77%. Including the 31 partially covered
decisions yields 80.56%. Using all current plan decisions, including the 60 for which an ADR is not warranted, strict
coverage is 67.23%.

The initiative supplement adds one ADR-worthy, uncovered ABI/linking decision. It changes the combined strict rate to
400/536, or 74.63%.

### Existing ADR support by closed plans

| Audit-derived closed-plan support    | Existing ADRs |
| ------------------------------------ | ------------: |
| More than one contributing plan      |            35 |
| Exactly one contributing plan        |             8 |
| No contributing closed plan in scope |             4 |

The four zero-plan rows are L0 ADRs 0001, 0004, 0009, and 0012. They represent foundational rules that predate or fall
outside the eligible closed-plan record, not failed ADR validation.

The audit-derived plan contributors below come from each ADR-linked canonical decision's event provenance. They are
distinct from literal “related plan” links written inside an ADR; the machine-readable ADR inventory preserves both
views. Basenames are abbreviated here; exact repository-relative paths are in
[existing-adr-coverage.csv](existing-adr-coverage.csv).

| Existing ADR                                                                       | Contributing plans | Plan basenames                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ---------------------------------------------------------------------------------- | -----------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/decisions/0001-two-stage-architecture.md`                                    |                  7 | `2026-02-14-stage2-parser-specification-noref`<br>`2026-03-09-stage2-backend-c-emitter-milestone`<br>`2026-03-11-triple-bootstrap-self-hosting-noref`<br>`2026-03-24-monorepo-language-level-layout-noref`<br>`2026-03-09-stage2-bootstrap-compiler-artifact-noref`<br>`2026-06-08-case-else-removal-l1-phase2-noref`<br>`2026-04-03-shared-diagnostic-code-catalog-noref`                                                                                                                                                                                                                                                                                                                 |
| `docs/decisions/0002-arc-ownership-model.md`                                       |                  9 | `2026-02-15-arc-bug-fixes-noref`<br>`2026-02-25-arc-opt-as-string-unwrap-ownership-noref`<br>`2026-02-28-stage1-backend-loop-continue-arc-release-uninitialized-noref`<br>`2026-05-10-fixed-size-array-primitive-noref`<br>`2026-04-20-shared-casted-place-null-propagation-arc-noref`<br>`2026-04-20-shared-top-level-arc-cleanup-and-drop-diagnostic-parity-noref`<br>`2026-04-22-shared-unwrapped-string-value-arc-copy-noref`<br>`2026-04-30-shared-arc-owned-local-reassignment-semantics-noref`<br>`2026-06-22-shared-for-header-and-statement-flow-safety-noref`                                                                                                                    |
| `docs/decisions/0003-shared-cli-contract.md`                                       |                 11 | `2026-03-10-stage2-source-paths-l0-home-fallback-noref`<br>`2026-02-24-stage2-driver-l0c-port-syntax-plumbing-noref`<br>`2026-02-28-stage2-semantic-foundation-milestone-noref`<br>`2026-03-08-l0-cflags-c-compiler-options-noref`<br>`2026-03-12-cli-version-flag-and-identity-text-noref`<br>`2026-03-12-shared-cli-contract-spec`<br>`2026-03-12-stage2-build-info-version-output-noref`<br>`2026-02-19-l0c-cli-global-mode-flags`<br>`2026-02-24-stage-independent-shared-assets-layout-noref`<br>`2026-03-13-windows-dev-install-and-prefix-workflow`<br>`2026-04-24-separate-compilation-driver-surface-noref`                                                                       |
| `docs/decisions/0004-monorepo-directory-structure.md`                              |                  6 | `2026-02-24-stage-independent-shared-assets-layout-noref`<br>`2026-03-24-monorepo-language-level-layout-noref`<br>`2026-03-02-doxygen-mcss-docs-system`<br>`2026-03-23-shell-to-python-tooling-port-noref`<br>`2026-06-30-shared-editor-support-noref`<br>`2026-05-06-shared-uv-workspace-monorepo-noref`                                                                                                                                                                                                                                                                                                                                                                                  |
| `docs/decisions/0005-diagnostic-code-catalog.md`                                   |                  7 | `2026-05-08-stage2-pointer-indexing-parity-noref`<br>`2026-06-05-duplicate-open-import-diagnostic-parity-noref`<br>`2026-03-09-stage2-backend-c-emitter-milestone`<br>`2026-06-24-stage1-scalar-const-expression-flow-noref`<br>`2026-06-07-stray-keyword-diagnostics-and-stmt-recovery-noref`<br>`2026-04-03-diagnostic-code-catalog-meanings-noref`<br>`2026-04-03-shared-diagnostic-code-catalog-noref`                                                                                                                                                                                                                                                                                 |
| `docs/decisions/0006-docs-work-taxonomy.md`                                        |                  2 | `2026-03-02-doxygen-mcss-docs-system`<br>`2026-04-04-docs-work-taxonomy-reorg-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `docs/decisions/0007-case-default-arm-wildcard.md`                                 |                  3 | `2026-07-13-release-1-1-0-preparation-noref`<br>`2026-06-08-case-else-removal-l1-phase2-noref`<br>`2026-06-07-case-default-arm-wildcard-phase1-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `docs/decisions/0008-source-text-encoding-and-ascii-language-vocabulary.md`        |                  1 | `2026-06-09-stage1-non-ascii-identifier-rejection-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `docs/decisions/0009-logical-lexer-error-recovery-tokens-and-codepoint-columns.md` |                  4 | `2026-02-24-stage2-lexer-parser-diag-unification`<br>`2026-04-17-l1-diagnostic-tab-caret-alignment-noref`<br>`2026-06-09-shared-lex-0040-recovery-noref`<br>`2026-06-10-shared-lexer-error-recovery-tokens-and-codepoint-columns-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `docs/decisions/0010-checked-runtime-pointer-access-validation.md`                 |                 10 | `2026-05-09-raw-pointer-indexing-semantics-noref`<br>`2026-06-30-runtime-pointer-access-validation-noref` (L1)<br>`2026-07-03-shared-alloc-tracker-churn-rehash-noref`<br>`2026-07-11-shared-checked-runtime-review-gaps-noref`<br>`2026-06-30-shared-runtime-pointer-access-validation-noref`<br>`2026-07-03-shared-lazy-arc-string-registration-noref`<br>`2026-07-04-shared-unchecked-build-surface-noref`<br>`2026-07-05-shared-compiler-runtime-quarantine-default-noref`<br>`2026-07-08-shared-runtime-check-basic-mode-noref`<br>`2026-07-16-shared-compiler-runtime-check-basic-default-noref`                                                                                     |
| `l0/docs/decisions/0001-foundational-language-contract.md`                         |                  0 | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `l0/docs/decisions/0002-pointer-model-no-address-of.md`                            |                  1 | `2026-05-08-stage2-pointer-indexing-parity-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `l0/docs/decisions/0003-integer-model.md`                                          |                  3 | `2026-02-27-stage1-backend-mixed-int-byte-binary-ice-1014-noref`<br>`2026-02-27-stdlib-string-conversions-noref`<br>`2026-02-27-stdlib-time-interface-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `l0/docs/decisions/0004-enum-tagged-union-model.md`                                |                  0 | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `l0/docs/decisions/0005-extern-func-ffi-boundary.md`                               |                  3 | `2026-02-27-stdlib-time-interface-noref`<br>`2026-05-08-sys-memory-rename-noref`<br>`2026-05-09-relax-null-tolerant-runtime-ffi-pointers-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `l0/docs/decisions/0006-module-system-and-imports.md`                              |                  2 | `2026-06-05-duplicate-open-import-diagnostic-parity-noref`<br>`2026-02-28-stage2-semantic-foundation-milestone-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `l0/docs/decisions/0007-nullability-and-casts.md`                                  |                  3 | `2026-02-25-arc-opt-as-string-unwrap-ownership-noref`<br>`2026-03-06-explicit-cast-constant-safety-diagnostics-noref`<br>`2026-05-09-relax-null-tolerant-runtime-ffi-pointers-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `l0/docs/decisions/0008-arc-ownership-model.md`                                    |                 11 | `2026-02-15-arc-bug-fixes-noref`<br>`2026-02-25-arc-opt-as-string-unwrap-ownership-noref`<br>`2026-02-28-stage1-backend-loop-continue-arc-release-uninitialized-noref`<br>`2026-03-11-general-logical-short-circuit-arc-temp-lowering-noref`<br>`2026-03-11-stage1-backend-condition-arc-temp-control-flow-noref`<br>`2026-03-09-stdlib-runtime-fs-path-raw-io-bootstrap-noref`<br>`2026-02-27-remove-drop-workarounds-noref`<br>`2026-04-20-shared-casted-place-null-propagation-arc-noref`<br>`2026-04-21-shared-arc-borrowed-param-reassignment-noref`<br>`2026-04-22-shared-unwrapped-string-value-arc-copy-noref`<br>`2026-04-30-shared-arc-owned-local-reassignment-semantics-noref` |
| `l0/docs/decisions/0009-string-value-semantics.md`                                 |                  0 | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `l0/docs/decisions/0010-with-statement-cleanup.md`                                 |                  4 | `2026-02-17-missing-cleanup-when-try-fails-in-with-noref`<br>`2026-02-27-with-cleanup-drop-false-positive-noref`<br>`2026-02-27-remove-drop-workarounds-noref`<br>`2026-06-22-shared-for-header-and-statement-flow-safety-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `l0/docs/decisions/0011-c-emission-strategy.md`                                    |                  5 | `2026-03-13-linux-c99-compatibility-noref`<br>`2026-03-31-msys2-mingw64-dev-environment-test-failures-noref`<br>`2026-03-09-stage2-backend-c-emitter-milestone`<br>`2026-02-28-trace-source-location`<br>`2026-03-22-backend-emitter-boundary-cleanup-noref`                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `l0/docs/decisions/0012-name-disambiguation.md`                                    |                  0 | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `l0/docs/decisions/0013-comparison-operator-scope.md`                              |                  1 | `2026-02-27-stage1-backend-mixed-int-byte-binary-ice-1014-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `l0/docs/decisions/0014-bootstrap-self-hosting-strategy.md`                        |                  7 | `2026-03-13-linux-c99-compatibility-noref`<br>`2026-03-13-windows-stage2-shell-test-regressions-noref`<br>`2026-03-17-darwin-arm64-triple-bootstrap-native-mismatch-noref`<br>`2026-03-09-stage2-backend-c-emitter-milestone`<br>`2026-03-11-triple-bootstrap-self-hosting-noref`<br>`2026-03-12-stage2-build-info-version-output-noref`<br>`2026-03-09-stage2-bootstrap-compiler-artifact-noref`                                                                                                                                                                                                                                                                                          |
| `l0/docs/decisions/0015-stdlib-module-boundaries.md`                               |                  9 | `2026-02-25-stdio-stale-errno-io-wrappers-noref`<br>`2026-02-27-stdlib-string-conversions-noref`<br>`2026-02-27-stdlib-time-interface-noref`<br>`2026-03-09-stdlib-runtime-fs-path-raw-io-bootstrap-noref`<br>`2026-02-24-stage2-util-stdlib-lift`<br>`2026-03-13-stdlib-fs-io-boundary-cleanup-noref`<br>`2026-04-14-shared-std-math-int-surface-noref`<br>`2026-05-08-sys-memory-rename-noref`<br>`2026-05-13-shared-std-math-to-std-integer-rename-noref`                                                                                                                                                                                                                               |
| `l0/docs/decisions/0016-string-value-operators.md`                                 |                  5 | `2026-04-18-string-equality-operators-noref`<br>`2026-04-18-string-relational-operators-noref`<br>`2026-04-22-string-concatenation-operator-noref`<br>`2026-04-20-prefer-native-string-operators-noref`<br>`2026-04-30-prefer-native-string-concat-operator-noref`                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `l1/docs/decisions/0001-bootstrap-adaptation-strategy.md`                          |                  1 | `2026-04-02-l1-bootstrap-scaffold-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `l1/docs/decisions/0002-dea-virtual-prelude-module.md`                             |                  3 | `2026-04-03-dea-virtual-module-noref`<br>`2026-04-20-is-intrinsic-noref`<br>`2026-05-19-stage1-slices-len-slice-intrinsics-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `l1/docs/decisions/0003-c-abi-naming-policy.md`                                    |                  3 | `2026-04-04-l1-dea-c-abi-prefix-migration-noref`<br>`2026-04-24-runtime-static-library-split-noref`<br>`2026-05-08-sys-memory-rename-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `l1/docs/decisions/0004-wide-integer-types.md`                                     |                  7 | `2026-06-08-stage1-case-builtin-literal-support-noref`<br>`2026-04-04-l1-prefixed-int-literals-noref`<br>`2026-04-04-l1-small-int-builtins-on-dea-abi-noref`<br>`2026-04-13-l1-uint-long-ulong-bigint-builtins-noref`<br>`2026-04-14-l1-std-math-wide-integer-followup-noref`<br>`2026-04-18-l1-bitwise-operators-noref`<br>`2026-06-18-stage1-const-scalar-casts-noref`                                                                                                                                                                                                                                                                                                                   |
| `l1/docs/decisions/0005-floating-point-semantics.md`                               |                  6 | `2026-06-08-stage1-case-builtin-literal-support-noref`<br>`2026-04-04-l1-float-double-literals-noref`<br>`2026-04-10-l1-numeric-literal-lexer-groundwork-noref`<br>`2026-04-13-l1-float-backend-contract-followup-noref`<br>`2026-04-14-l1-std-real-module-noref`<br>`2026-06-18-stage1-const-scalar-casts-noref`                                                                                                                                                                                                                                                                                                                                                                          |
| `l1/docs/decisions/0006-const-declarations.md`                                     |                  1 | `2026-04-18-l1-const-declarations-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `l1/docs/decisions/0007-function-pointer-types.md`                                 |                  2 | `2026-04-18-l1-function-pointer-types-noref`<br>`2026-05-08-unsafe-function-marker-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `l1/docs/decisions/0008-lbi-symbol-mangling.md`                                    |                  7 | `2026-04-18-l1-const-declarations-noref`<br>`2026-04-22-variadic-functions-noref`<br>`2026-04-24-lbi-symbol-mangling-and-linkage-noref`<br>`2026-05-08-unsafe-function-marker-noref`<br>`2026-05-10-fixed-size-array-primitive-noref`<br>`2026-05-19-stage1-slices-len-slice-intrinsics-noref`<br>`2026-05-11-unified-lbi-mangling-noref`                                                                                                                                                                                                                                                                                                                                                  |
| `l1/docs/decisions/0009-module-visibility-exports-imports.md`                      |                  3 | `2026-04-24-export-manifests-and-aliased-imports-noref`<br>`2026-04-24-lbi-symbol-mangling-and-linkage-noref`<br>`2026-06-13-opaque-type-exports-and-layout-hiding-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `l1/docs/decisions/0010-unsafe-marker-and-raw-pointer-indexing.md`                 |                  4 | `2026-05-08-unsafe-function-marker-noref`<br>`2026-05-09-raw-pointer-indexing-semantics-noref`<br>`2026-05-11-unified-lbi-mangling-noref`<br>`2026-07-05-shared-compiler-runtime-quarantine-default-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `l1/docs/decisions/0011-fixed-size-array-policy.md`                                |                  4 | `2026-05-10-fixed-size-array-primitive-noref`<br>`2026-05-11-ordered-type-suffix-constructors-noref`<br>`2026-05-19-stage1-slices-len-slice-intrinsics-noref`<br>`2026-06-17-stage1-const-value-grammar-contexts-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `l1/docs/decisions/0012-ordered-type-suffix-constructors.md`                       |                  2 | `2026-05-10-fixed-size-array-primitive-noref`<br>`2026-05-11-ordered-type-suffix-constructors-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `l1/docs/decisions/0013-opaque-type-exports-and-layout-hiding-visibility.md`       |                  2 | `2026-04-24-separate-compilation-driver-surface-noref`<br>`2026-06-13-opaque-type-exports-and-layout-hiding-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `l1/docs/decisions/0014-module-interface-artifact.md`                              |                  6 | `2026-07-20-stage1-module-interface-resolution-hardening-noref`<br>`2026-04-24-module-interface-emission-noref`<br>`2026-04-24-separate-compilation-driver-surface-noref`<br>`2026-06-13-opaque-type-exports-and-layout-hiding-noref`<br>`2026-06-18-stage1-const-scalar-casts-noref`<br>`2026-06-24-stage1-scalar-const-expression-flow-noref`                                                                                                                                                                                                                                                                                                                                            |
| `l1/docs/decisions/0015-slice-types-and-intrinsics.md`                             |                  1 | `2026-05-19-stage1-slices-len-slice-intrinsics-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `l1/docs/decisions/0016-compile-time-constant-value-contexts.md`                   |                  4 | `2026-05-10-fixed-size-array-primitive-noref`<br>`2026-06-17-stage1-const-value-grammar-contexts-noref`<br>`2026-06-18-stage1-const-scalar-casts-noref`<br>`2026-06-24-stage1-scalar-const-expression-flow-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `l1/docs/decisions/0017-l1-variadic-functions.md`                                  |                  1 | `2026-04-22-variadic-functions-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `l1/docs/decisions/0018-canonical-artifact-association-and-module-graph.md`        |                  3 | `2026-07-20-stage1-module-interface-resolution-hardening-noref`<br>`2026-04-24-separate-compilation-driver-surface-noref`<br>`2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `l1/docs/decisions/0019-whole-module-interface-fingerprints.md`                    |                  3 | `2026-04-24-module-interface-emission-noref`<br>`2026-07-17-interface-fingerprint-canonicalization-and-verification-noref`<br>`2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `l1/docs/decisions/0020-per-module-backend-and-lifecycle-abi.md`                   |                  4 | `2026-04-17-l1-let-non-constant-initializers-noref`<br>`2026-04-24-lbi-symbol-mangling-and-linkage-noref`<br>`2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref`<br>`2026-05-11-unified-lbi-mangling-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `l1/docs/decisions/0021-portable-object-metadata-and-inspection.md`                |                  1 | `2026-07-17-object-metadata-emission-and-readers-noref`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |

## Missing ADR backlog

The 24 candidates below cluster coherent architectural questions; they are not one ADR per plan. Full questions,
decisions, alternatives, rationale, consequences, plan provenance, and normative-document links are in
[missing-adr-candidates.md](missing-adr-candidates.md).

Together the clusters cover all 105 combined `Not covered` decisions and 18 adjacent `Partially covered` decisions that
are needed to state the same architectural questions coherently.

Dea-wide ADR-0011 is occupied by the plan ADR-impact and closure-gate workflow, while L1 ADR-0022 is occupied by the
transactional compile-only artifact-publication contract. The backlog therefore begins its provisional Dea-wide sequence
at ADR-0012 and its L1 sequence at ADR-0023; no existing ADR or stable candidate ID is renumbered.

| Candidate          | Proposed ADR   | Action | Priority | Destination          | Canonical decisions | Proposed title                                                      |
| ------------------ | -------------- | ------ | -------- | -------------------- | ------------------: | ------------------------------------------------------------------- |
| `DEA-ADR-CAND-001` | `DEA-ADR-0012` | New    | P0       | `docs/decisions/`    |                   6 | Shared For-Header Control Flow, Liveness, and Cleanup Semantics     |
| `DEA-ADR-CAND-002` | `L0-ADR-0017`  | New    | P0       | `l0/docs/decisions/` |                  10 | L0 Release Identity, Integrity, and Immutable Publication           |
| `DEA-ADR-CAND-003` | `DEA-ADR-0013` | New    | P1       | `docs/decisions/`    |                   5 | Compiler Diagnostic Collection, Parser Recovery, and Phase Barriers |
| `DEA-ADR-CAND-004` | `DEA-ADR-0014` | New    | P1       | `docs/decisions/`    |                   1 | Intentional Cross-Level Divergence and Parity Exceptions            |
| `DEA-ADR-CAND-005` | `DEA-ADR-0015` | New    | P1       | `docs/decisions/`    |                  10 | Shared Integer Standard-Library Naming and Failure Contract         |
| `DEA-ADR-CAND-006` | `DEA-ADR-0016` | New    | P1       | `docs/decisions/`    |                   2 | Top-Level Let Inference and Runtime-Initialization Boundaries       |
| `DEA-ADR-CAND-007` | `L0-ADR-0014`  | Amend  | P1       | `l0/docs/decisions/` |                   6 | Platform-Specific Bootstrap Artifact Identity and Provenance        |
| `DEA-ADR-CAND-008` | `L0-ADR-0018`  | New    | P1       | `l0/docs/decisions/` |                   8 | L0 Safe Standard-Stream Byte I/O Boundary                           |
| `DEA-ADR-CAND-009` | `L0-ADR-0019`  | New    | P1       | `l0/docs/decisions/` |                   2 | L0 Stage 2 Arena-Backed AST and Parser Ownership Model              |
| `DEA-ADR-CAND-010` | `L0-ADR-0020`  | New    | P1       | `l0/docs/decisions/` |                   4 | L0 Stage 2 Driver and Host-Process Boundary                         |
| `DEA-ADR-CAND-011` | `L0-ADR-0021`  | New    | P1       | `l0/docs/decisions/` |                   4 | L0 Supported Host, Toolchain, and Release Artifact Tiers            |
| `DEA-ADR-CAND-012` | `L0-ADR-0022`  | New    | P1       | `l0/docs/decisions/` |                   8 | L0 Time Model, Public Values, and Runtime Boundary                  |
| `DEA-ADR-CAND-013` | `L0-ADR-0023`  | New    | P1       | `l0/docs/decisions/` |                  10 | L0 Toolchain Installation and Distribution Layout                   |
| `DEA-ADR-CAND-014` | `L1-ADR-0023`  | New    | P1       | `l1/docs/decisions/` |                   4 | L1 Case Value Comparability and Unreachable-Arm Policy              |
| `DEA-ADR-CAND-015` | `L1-ADR-0024`  | New    | P1       | `l1/docs/decisions/` |                   5 | L1 Named-Call Syntax, Completeness, and Evaluation Order            |
| `DEA-ADR-CAND-016` | `L1-ADR-0025`  | New    | P1       | `l1/docs/decisions/` |                   3 | L1 Pointer Equality and Ordering Semantics                          |
| `DEA-ADR-CAND-017` | `L1-ADR-0026`  | New    | P1       | `l1/docs/decisions/` |                   6 | L1 Real-Library Runtime and Host-Math Linkage Boundary              |
| `DEA-ADR-CAND-018` | `L1-ADR-0027`  | New    | P1       | `l1/docs/decisions/` |                   9 | L1 Runtime Archive and Trace-Selection Boundary                     |
| `DEA-ADR-CAND-019` | `DEA-ADR-0017` | New    | P2       | `docs/decisions/`    |                   6 | Documentation Publication Ownership and Cross-Repository Boundary   |
| `DEA-ADR-CAND-020` | `DEA-ADR-0018` | New    | P2       | `docs/decisions/`    |                   5 | Shared Editor Tooling, Level Identities, and Compiler Authority     |
| `DEA-ADR-CAND-021` | `DEA-ADR-0019` | New    | P2       | `docs/decisions/`    |                   4 | Shared Standard-Library Naming and Compatibility Policy             |
| `DEA-ADR-CAND-022` | `L0-ADR-0024`  | New    | P2       | `l0/docs/decisions/` |                   2 | L0 Filesystem Metadata and Recoverable File-Read ABI                |
| `DEA-ADR-CAND-023` | `L0-ADR-0025`  | New    | P2       | `l0/docs/decisions/` |                   2 | L0 Runtime Trace Source Provenance                                  |
| `DEA-ADR-CAND-024` | `L0-ADR-0026`  | New    | P2       | `l0/docs/decisions/` |                   1 | L0 Stage 2 Semantic Result and Pass-Ordering Architecture           |

### Prioritization rationale

The P0 items combine foundational current behavior, broad cross-component effects, and a high cost of contradiction. The
`for` contract must remain aligned across parser, analyzer, flow analysis, backend, and cleanup lowering. The release
contract controls public identity, review gates, artifact integrity, sole-repository publication, and immutability.

P1 concentrates near-term architectural guidance: diagnostics/recovery, intentional parity exceptions, shared integer
APIs, top-level initialization, bootstrap identity, safe byte I/O, Stage 2 ownership/driver boundaries, supported hosts,
time, installation layout, L1 case/named-call/pointer semantics, real-library linkage, and runtime archive selection.

P2 captures durable but less urgent subsystem and process boundaries: documentation handoff, editor authority,
standard-library compatibility, filesystem ABI, trace provenance, and the Stage 2 semantic result model.

## Findings by project phase

The decision history shows four overlapping architectural phases:

1. **L0 compiler foundation and self-hosting (February–March).** Parser ownership, diagnostics, ARC lowering, CLI form,
   standard-library/runtime boundaries, bootstrap identity, host commands, portability, distribution, and release
   workflows became durable constraints.
2. **L1 language and ABI expansion (April–May).** Numeric families, consts, strings, callable types, variadics, fixed
   arrays, slices, unsafe functions, symbol mangling, interface emission, runtime archive boundaries, and
   separate-compilation surfaces account for the largest and densest decision cohort.
3. **Shared semantic hardening (June).** Recovery, diagnostic parity, case-default migration, `for`
   flow/liveness/cleanup, constant-value evaluation, case comparability, editor tooling, and checked pointer access
   increasingly became cross-level contracts.
4. **Artifact and runtime maturation (July).** Runtime-validation profiles, tracker boundaries, foreign memory, stable
   releases, interface fingerprints, object metadata, module graphs, lifecycle entry points, and interface-resolution
   closure completed the audited baseline.

This chronology explains why accepted ADRs do not map one-to-one to plans. Several ADRs consolidate years of
architectural questions in a short period, and several current rules emerged from bug-fix or bootstrap-parity plans
rather than from an explicitly named design proposal.

## Quality checks

The reproducible validator passes all structural checks:

- every required closed-plan and initiative path appears exactly once;
- every inventory decision count matches its event rows;
- plan title, date, kind, and final status match source metadata;
- every event references one primary source and a line range within that file;
- event, canonical, relationship, and candidate IDs are unique;
- every current canonical decision has at least one historical event;
- superseded/retracted status is compatible with its later relationship evidence;
- every canonical, relationship, ADR, document, and candidate reference resolves;
- all primary category, scope, status, explicitness, confidence, relationship, and ADR-coverage values belong to
  controlled vocabularies;
- all three ADR indexes exactly match their numbered files;
- ADR plan contributors and missing-ADR plan provenance are derived from canonical-event sources;
- every ADR-worthy `Not covered` current decision belongs to exactly one missing-ADR candidate;
- zero-decision plans remain in the inventory; and
- unresolved Low-confidence IDs are reported.

The semantic review separately checked that phases, tests, file edits, mechanical ports, and forced implementation
consequences were not promoted merely because a plan numbered them.

## Limitations and reviewer judgment

- This is decision archaeology from documentary evidence. It is not a claim that every architectural rule in source code
  has a corresponding plan.
- A later code change was not enough to mark a decision superseded. One exception-like case, the extension of `len` to
  strings, is tied to current normative documentation because no later eligible closed plan records it.
- Nine plans have metadata dates that differ from filename dates. Month statistics use metadata dates; checkpoint
  cohorts use filenames where necessary to preserve the requested chronological batches.
- Four events are Medium confidence and listed above. There are no included Low-confidence events.
- ADR coverage and worthiness are necessarily evaluative. The ledger records the evidence and rationale so another
  reviewer can revise those judgments without redoing corpus inventory.
- The 595 current primary decisions are canonical questions grounded in at least one closed plan. The separate
  initiative-only decision is not silently added to that denominator.
- “No retractions” means no adopted event met the audit's documentary standard for deliberate withdrawal without a
  direct successor. It does not mean no proposal was ever abandoned.
- Baseline line numbers and current-status claims apply to the audited SHA and may drift on later branches.

## Reproducibility

From a checkout of the audited commit:

```sh
python3 scripts/validate_architectural_decision_audit.py
```

To print the complete aggregate statistics:

```sh
python3 scripts/validate_architectural_decision_audit.py --json
```

To validate and regenerate the checked-in statistics snapshot:

```sh
python3 scripts/validate_architectural_decision_audit.py \
  --json \
  --write-stats work/audits/architectural-decisions/2026-07-26/audit-statistics.json
```

The script inventories the live closed corpus, validates every human-reviewed record and cross-reference, verifies the
ADR indexes, checks controlled values, and recomputes all reportable aggregates. It intentionally does not attempt to
infer decisions automatically.
