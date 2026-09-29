# Tool Plan

## Establish explicit validation tiers and reduce local test cost

- Date: 2026-09-29
- Status: Draft
- Title: Establish repo-wide development, extended, and CI validation tiers and reduce local L1 test cost
- Kind: Tooling
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - Root test orchestration and target naming
  - L0 test target naming
  - L1 local and CI test composition
  - Unified CI target routing
  - Agent and contributor validation guidance
- Origin: Root monorepo test and CI policy, prompted by L1 validation cost observed in Unified CI and local development.
- Porting rule: The tier names and intent are shared repository policy. Each language level may compose those tiers
  differently according to its own test costs and architecture. L1 receives the substantive cost reclassification in
  this plan; L0 changes target naming without requiring an equivalent suite restructuring.
- Target status:
  - Root test orchestration and target naming: Pending
  - L0 test target naming: Pending
  - L1 local and CI test composition: Pending
  - Unified CI target routing: Pending
  - Agent and contributor validation guidance: Pending
- Subsystem: Make test orchestration / test runners / GitHub Actions / developer and agent workflow
- Modules:
  - `Makefile`
  - `l0/Makefile`
  - `l1/Makefile`
  - `.github/workflows/ci.yml`
  - `.github/workflows/l0-ci.yml`
  - `AGENTS.md`
  - `.github/copilot-instructions.md`
  - `l0/AGENTS.md`
  - `l1/AGENTS.md`
  - `MONOREPO.md`
  - `l0/README.md`
  - `l1/README.md`
  - `CLAUDE.md`
  - `CONTRIBUTING.md`
  - `docs/project-status.md`
  - `l1/docs/project-status.md`
  - `l1/docs/reference/architecture.md`
  - `.agents/skills/finalize-dea-work/SKILL.md`
  - `l1/compiler/stage1_l0/scripts/run_tests.py`
  - `l1/compiler/stage1_l0/scripts/test_runner_common.py`
  - `l1/compiler/stage2_l1/scripts/run_tests.py`
  - `l1/compiler/stage2_l1/scripts/test_runner_common.py`
- Test modules:
  - `l1/tests/test_env_stackability.py`
  - `l1/tests/test_docker_wine.py`
  - `l1/tests/test_stage2_tooling.py`
  - `l1/tests/test_bootstrap_identity.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_trace_runner_common_test.py`
  - `l0/tests/test_make_dea_build_workflow.py`
  - `l0/tests/test_dist_tools_lib_fallback.py`
- Related:
  - `l1/work/plans/tools/closed/2026-09-13-preparation-test-cost-noref.md`
  - `work/plans/bug-fixes/closed/2026-08-24-shared-trace-io-amplification-noref.md`
  - `l1/work/plans/features/closed/2026-09-13-warm-preparation-validation-reuse-noref.md`
  - `docs/decisions/0004-monorepo-directory-structure.md`
- Repro: `L1_TEST_JOBS=4 L1_TRACE_TEST_JOBS=4 make -C l1 clean test-all`

## Summary

The repository currently uses `test` and `test-all` as the principal local validation tiers, while L1 additionally has
`test-ci`. The naming no longer describes the actual contracts.

`test-all` is not exhaustive. L0 keeps strict triple-bootstrap validation outside it, and L1's `test-ci` adds validation
beyond `test-all`. At the same time, L1's current local full-validation path has become too expensive for routine
development. The broad normal suites, dedicated ARC/memory tracing, environment/bootstrap integration, and fixed-point
bootstrap checks collectively turn a local validation command into a run measured in tens of minutes and, on some hosts,
around an hour or more.

Replace `test-all` repository-wide with `test-extended`, with no compatibility alias. Establish three semantic tiers:

1. `test`: fast development feedback and the default local iteration gate.
2. `test-extended`: broader local validation for substantial refactors, cross-subsystem changes, and pre-finalization
   confidence.
3. `test-ci`: exhaustive hosted validation where a level defines such a target, including checks deliberately omitted
   from routine local tiers because of cost.

The rename is repository-wide. The substantive suite reclassification is initially L1-specific. L0 preserves the current
behavior of its former `test-all` target under the new `test-extended` name.

The goal is not to reduce correctness coverage. Expensive tests remain runnable directly and remain part of CI where
applicable. The goal is to stop paying exhaustive-validation cost on every ordinary local iteration.

## Baseline

The initial timing baseline is the successful
[September 27, 2026 Unified CI run](https://github.com/dea-lang/dea/actions/runs/36348673934) titled "Fix L1 long
host-link commands on Windows."

The complete L1 CI target took approximately:

| Platform       | L1 `test-ci` |
| -------------- | -----------: |
| Linux x86_64   |       39m35s |
| macOS ARM64    |       51m28s |
| macOS Intel    |       90m51s |
| Windows UCRT64 |       76m24s |

On Linux, the principal components were approximately:

| Component                | Wall time |
| ------------------------ | --------: |
| Stage 1 regular suite    |     6m01s |
| Stage 2 construction     |     1m07s |
| Stage 2 regular suite    |     8m08s |
| Environment stackability |     2m26s |
| Stage 1 trace sweep      |     3m30s |
| Stage 2 trace sweep      |     6m49s |
| Child trace fixtures     |   seconds |
| Triple bootstrap         |    10m53s |

The two complete trace sweeps plus triple bootstrap therefore consumed about 21 minutes, over half of the Linux L1 lane.
The same categories scale worse on slower hosts.

The regular suites also contain tests whose behavior is already closer to trace, stress, bootstrap, or environment
integration than to fast semantic feedback. Representative cases from this run include:

- `preparation_identity_test.py`
- `l1c_stage1_arc_trace_regression_test.py`
- `preparation_ownership_test.py`
- `math_runtime_compile_test`
- `slice_trace_test`
- broad preparation and toolchain integration fixtures

The existing preparation-cost investigation independently recorded a 54m22s local Intel Mac `test-all` run and
multi-gigabyte trace workloads. This plan treats the problem as validation-tier composition, not merely an opportunity
for small runner optimizations.

## Defaults Chosen

1. **Rename `test-all` to `test-extended` immediately and provide no alias.**

   The old name is misleading. Keeping an alias would preserve both the ambiguity and obsolete commands indefinitely.

2. **`test` is the default developer command.**

   It must be deliberately optimized for repeated local execution. Agent guidance should recommend it after ordinary
   implementation work rather than requiring developers to prove that a change is "trace-independent" first.

3. **`test-extended` is a broader local confidence gate, not an exhaustive gate.**

   It is appropriate for substantial refactors, changes spanning several compiler subsystems, or final local validation
   when the affected surface is uncertain.

4. **L1 `test-ci` is the exhaustive hosted gate.**

   It includes `test-extended` plus tests classified as too costly for routine local validation, full trace coverage,
   bootstrap/environment integration where appropriate, and strict triple-bootstrap validation.

5. **Focused expensive targets remain first-class developer tools.**

   Moving a test into the CI tier does not make it inaccessible locally. A developer changing tracing, bootstrap,
   preparation, or another expensive subsystem should run the relevant focused target or explicitly named test.

6. **Explicit selection overrides cost classification.**

   A test marked CI-only or slow should still run when named explicitly. This matches the useful existing behavior of
   slow trace tests such as `math_runtime_compile_test`.

7. **Duration alone does not determine CI-only status.**

   Core semantic, analysis, backend, type-resolution, interface, and emitter tests should not be removed from useful
   local coverage merely because they are expensive. Expensive tests should move to CI when their cost comes from broad
   integration, repeated compiler construction, tracing, environment setup, stress matrices, or duplicated coverage that
   has a cheaper representative local signal.

8. **The three tier names describe intent, not identical implementation across levels.**

   L0 and L1 need not contain the same categories in `test-extended`. L0's current trace-inclusive validation can remain
   in `test-extended` initially. L1 needs a more aggressive split because its cost profile has become unsuitable for
   local iteration.

9. **Historical records remain historical.**

   Closed plans, old release notes, and completed-work records that mention `test-all` should not be bulk-rewritten.
   Current operational documentation, active plans, scripts, workflow defaults, and guidance must use the new target
   names.

## Goal

1. Reduce the normal L1 local edit/test loop from tens of minutes toward a few minutes.
2. Retain a meaningful middle tier for broad local validation during large refactors.
3. Keep exhaustive coverage in hosted CI.
4. Make the test-tier names accurately communicate their purpose.
5. Preserve direct access to every expensive validation category for focused local investigation.
6. Give human contributors and agents explicit guidance about which tier to use and when.

Initial timing goals are directional rather than hard pass/fail thresholds:

- L1 `test`: target approximately 5 minutes or less on the Linux hosted reference environment where feasible.
- L1 `test-extended`: target approximately 10 to 15 minutes on the same reference environment where feasible.
- L1 `test-ci`: no local-interactivity target; optimize only where doing so does not compromise exhaustive validation.

Host and toolchain variance is substantial, so these values must not become brittle test timeouts.

## L1 Classification Policy

### Keep in routine local coverage

Prefer to retain tests locally when they provide direct, high-value feedback about compiler correctness without
requiring unusually broad environment or instrumentation setup.

This includes representative coverage of:

- parsing
- name resolution
- type analysis
- expression typing
- compiler backend behavior
- C emission
- module and interface semantics
- ordinary driver behavior
- representative build/run/link behavior
- cheap runtime boundary checks
- cheap tooling and help/CLI contracts

Core compiler suites such as `backend_test`, `analysis_test`, `expr_types_test`, `interface_test`, and related semantic
suites should not become CI-only solely because their wall time is noticeable.

### Initial CI-only candidates

The first implementation should evaluate and, unless a coverage gap is found, move these categories out of routine local
aggregate tiers:

01. Strict triple bootstrap.
02. Full Stage 1 ARC/memory trace sweep.
03. Full Stage 2 ARC/memory trace sweep.
04. Declared child trace fixture sweeps.
05. Environment stackability validation that creates isolated L0/L1 build environments and rebuilds compiler stages.
06. Normal-suite tests whose primary purpose is trace validation, including `l1c_stage1_arc_trace_regression_test.py`.
07. `preparation_ownership_test.py`, which invokes trace machinery from the normal suite.
08. `slice_trace_test`, whose ordinary behavior itself enables ARC and memory tracing.
09. `math_runtime_compile_test`, which is already classified as a slow trace case and is also expensive in normal
    execution.
10. `preparation_identity_test.py`, whose broad native identity/toolchain matrix is valuable integration coverage but
    poor iterative feedback.

Shared Python tests included in both Stage 1 and Stage 2 must be classified consistently so the same CI-shaped
integration test is not accidentally paid twice by a local aggregate target.

### Expensive tests that need splitting or further measurement

Do not initially move the following classes to CI solely on timing evidence:

- `l1c_lib_test`
- `link_driver_test`
- `mul_runtime_test`
- other core compiler implementation suites with broad internal assertions

Instead, inspect whether the cost comes from a small number of stress scenarios embedded inside otherwise useful local
tests.

For example, ordinary link-driver behavior should remain local, while long-command, response-file, quoting, or
large-input stress cases may be separated into a CI-only test if they dominate the harness.

A split is justified only when it preserves representative local coverage and demonstrably removes substantial work. The
earlier preparation-cost investigation showed that naive splitting can increase total compiler construction work, so
smaller files are not automatically faster tests.

## Runner Contract

Introduce an explicit normal-test cost classification rather than encoding long exclusion lists in Make recipes.

The implementation may use names such as:

- `CI_ONLY_NORMAL_STAGE1_TESTS`
- `CI_ONLY_NORMAL_STAGE2_TESTS`

or an equivalent declarative mechanism shared by the runners.

Required behavior:

1. Default normal discovery excludes CI-only cases from routine aggregate runs.
2. Explicitly naming a CI-only test still runs it.
3. CI can request the complete normal set with an explicit runner option such as `--include-ci-only`.
4. The classification is test metadata/policy, not inferred dynamically from measured duration.
5. Runner regression tests cover default exclusion, explicit selection, invalid selectors, and complete CI inclusion.
6. Stage 1 and Stage 2 use the same conceptual policy even if their exact classified sets differ.

Do not use environment-variable-only hidden behavior for the distinction. The CI-inclusive mode should be visible in
command help and understandable from logs.

## Target Contract

### Repository root

Replace:

```text
make test
make test-all
```

with:

```text
make test
make test-extended
```

Root `test` continues to delegate to each registered level's `test`.

Root `test-extended` delegates to each registered level's `test-extended`.

Do not add a `test-all` compatibility target.

A root `test-ci` aggregate is not required by this plan. Unified CI may continue routing directly to level-specific
targets.

### L0

Rename:

```text
test-all -> test-extended
```

Preserve the existing behavior initially:

```text
test-extended = test + test-stage2-trace
```

The existing separate `triple-test` remains explicit.

Update the standalone L0 CI workflow and Unified CI from `test-all` to `test-extended`, including visible job and target
naming, so the rename does not silently reduce existing L0 hosted coverage.

Further L0 test-cost restructuring is outside this plan unless implementation reveals a direct dependency on the shared
tier changes.

### L1

The target relationship becomes conceptually:

```text
test < test-extended < test-ci
```

`test`:

- fast developer feedback
- representative Stage 1 compiler validation
- a deliberately small Stage 2 smoke/identity set where Stage 2 is present
- cheap tooling checks
- no complete trace sweep
- no triple bootstrap
- no isolated environment/bootstrap reconstruction
- no CI-only normal tests

`test-extended`:

- everything in `test`
- broad local-normal Stage 1 validation
- broad local-normal Stage 2 validation
- examples and appropriate tooling checks
- excludes CI-only normal tests
- excludes complete dedicated trace sweeps
- excludes triple bootstrap
- excludes environment/bootstrap integration classified as CI-only

`test-ci`:

- everything in `test-extended`
- complete normal tests including CI-only cases
- Stage 1 dedicated trace sweep
- Stage 2 dedicated trace sweep
- child trace fixtures
- environment/bootstrap integration checks
- strict triple bootstrap
- any other explicitly classified hosted-only stress checks

Exact `test` smoke membership should be selected by measured signal and runtime during implementation rather than frozen
from the current accidental target graph.

## Agent and Contributor Guidance

Update `AGENTS.md`, `l0/AGENTS.md`, `l1/AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, and the finalization skill so the
intended workflow is explicit.

The guidance must communicate these rules:

### Normal development

Use `make test` as the normal development gate.

It is intentionally designed for iteration and should be the default after ordinary compiler, runtime, stdlib, or
tooling changes.

### Broad local validation

Use `make test-extended` when:

- performing a substantial refactor
- changing several compiler subsystems
- changing shared interfaces with broad downstream effects
- preparing work for finalization when wider local confidence is useful
- the affected surface is uncertain enough that focused tests plus `make test` are insufficient

Do not describe this target as "all", "full", "complete", or exhaustive.

### CI validation

L1 `make test-ci` is the exhaustive hosted gate.

It may be run locally deliberately, but agents and contributors should not use it routinely as a substitute for choosing
relevant focused validation.

Changes involving tracing, bootstrap, preparation, environment setup, or another expensive subsystem should run the
affected focused target locally. They do not automatically require the entire CI suite to be run locally.

### Validation reuse

Update finalization guidance to express the tier relationship:

```text
test-ci subsumes test-extended
test-extended subsumes test
```

only when the completed run covered the same relevant source tree, build configuration, compiler/toolchain selection,
and test inputs.

A focused test does not imply any aggregate tier.

A prior aggregate result is invalidated by later changes to covered code, tests, build configuration, dependencies,
generated source, or toolchain selection under the repository's existing reuse rules.

## Current Documentation and Reference Migration

Because no compatibility alias will exist, stale operational commands become broken commands.

Update current, normative, or active references to `test-all`, including at minimum:

- Makefile help text and examples
- root, L0, and L1 `AGENTS.md`
- `MONOREPO.md`
- `CLAUDE.md`
- `CONTRIBUTING.md`
- current project-status documents
- L0/L1 current README guidance
- Docker and Wine examples
- `.github/workflows/l0-ci.yml` and `.github/workflows/ci.yml`
- `.github/copilot-instructions.md`
- L0 and L1 current README guidance
- `l1/docs/reference/architecture.md`
- agent skills that prescribe validation
- active plans whose reproduction or verification commands must remain runnable
- scripts or tests that invoke the old target by name

Do not rewrite:

- closed plans
- historical release notes
- audit evidence
- completed validation records

Those documents should continue recording the target name that actually existed when the historical work was performed.
Active-plan attachments that record completed validation results are historical evidence for this purpose and must not
be rewritten; only active instructions and future commands are migrated.

A final repository search should distinguish remaining historical occurrences from accidental live references.

## Implementation Phases

### Phase 1: Land the repo-wide target rename

1. Rename root `test-all` to `test-extended`.
2. Rename L0 `test-all` to `test-extended`.
3. Rename L1 `test-all` to `test-extended`.
4. Update `.PHONY`, help output, Docker defaults, examples, and direct target dependencies.
5. Do not add aliases.
6. Update the standalone L0 CI workflow and Unified CI default, job key, visible job name, and routed target to
   `test-extended`.
7. Update affected L0 workflow and target regression expectations.
8. Keep L1 CI routed through `test-ci`.

At the end of this phase there must be no live Make dependency on `test-all`.

### Phase 2: Add explicit L1 normal-test cost classification

1. Add runner-level classification for CI-only normal tests.
2. Preserve explicit test selection for every classified test.
3. Add an explicit CI-inclusive runner mode.
4. Cover classification behavior with runner regressions.
5. Apply equivalent policy to Stage 1 and Stage 2 where both are active.
6. Start with the initial candidate list in this plan and adjust only when a concrete local coverage gap is identified.

### Phase 3: Recompose L1 `test`

Measure the remaining local-normal suite after Phase 2.

Build a fast `test` target from representative high-signal checks. Prefer broad semantic coverage over repeated
end-to-end compiler construction.

Stage 2 should use a smoke/identity subset in this tier if its full regular suite prevents `test` from serving as an
iterative command.

Record the selected set and rationale in the Makefile/help or nearby runner documentation so membership is intentional
rather than accidental.

### Phase 4: Recompose L1 `test-extended`

Run the complete local-normal compiler coverage that remains after CI-only classification.

Include Stage 1 and Stage 2 regular suites, examples, and appropriate cheap tooling checks.

Do not add the complete dedicated trace sweeps or strict triple bootstrap merely because this is the broader local
target.

### Phase 5: Make L1 `test-ci` the explicit exhaustive union

Make `test-ci` run:

1. `test-extended`
2. CI-only normal tests
3. environment/bootstrap integration
4. full Stage 1 trace coverage
5. full Stage 2 trace coverage
6. child trace fixtures
7. triple bootstrap

Avoid accidental duplication where a CI-only normal test is also covered by a dedicated category.

Logs should make category boundaries visible enough to understand where CI time is spent.

### Phase 6: Update guidance and active documentation

Update all current operational guidance in the same change.

The L1 `AGENTS.md` section must explicitly describe `test`, `test-extended`, and `test-ci` by intended use rather than
merely listing their dependencies.

Update active plans that prescribe the removed `test-all` target. Choose `test`, `test-extended`, `test-ci`, or a
focused target according to the validation actually required by each active plan.

Do not modify closed lifecycle history solely for naming consistency.

### Phase 7: Measure the new tiers

Using the normal CI environment or equivalent reference configuration:

1. Record L1 `test` wall time.
2. Record L1 `test-extended` wall time.
3. Record L1 `test-ci` wall time.
4. Confirm all tests removed from local aggregate tiers still execute in `test-ci`.
5. Compare category timing with the baseline in this plan.
6. Identify remaining dominant local tests.

No remote dispatch is authorized by this plan. Prefer timings from the next normally authorized CI run. If a manual
timing run is later proposed, it must target the `dea-lang/dea` repository's `.github/workflows/ci.yml` workflow on the
exact implementation branch or ref recorded at that time. Before dispatch, show the exact command or action, workflow,
remote, ref, and hosted matrix effects, then obtain fresh user confirmation. Any push or other remote action remains a
separate approval gate.

If `test` or `test-extended` remains too slow for its intended use, perform another classification/splitting pass rather
than declaring the tier complete based only on functional correctness.

## ADR Impact

- Decision: Introduce repository-wide `test`, `test-extended`, and level-specific `test-ci` validation semantics and
  classify costly L1 tests by workflow role.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This changes internal repository test orchestration, naming, CI composition, and developer guidance
    without changing the language, compiler architecture, runtime contract, artifact format, or user-facing Dea
    behavior. The tier policy remains maintainable repository tooling rather than a product architecture decision.

## Non-Goals

- Reducing or deleting correctness coverage merely to meet a timing target.
- Making expensive trace or bootstrap tests inaccessible to developers.
- Moving core compiler semantic suites to CI solely because they are slow.
- Changing language, runtime, compiler, or generated-code semantics.
- Reworking L0's test composition beyond the target rename unless required by shared orchestration.
- Adding a `test-all` compatibility alias.
- Bulk-editing historical closed plans or release records.
- Introducing path-based CI skipping or change-detection heuristics.
- Sharding the hosted CI matrix as part of this first change.
- Optimizing compiler or runtime performance as a substitute for fixing validation-tier composition.
- Making timing thresholds hard test failures.
- Automatically dispatching CI or performing remote repository actions.

## Verification Criteria

01. Root, L0, and L1 Makefiles expose `test-extended` and no longer expose `test-all`.
02. No compatibility alias for `test-all` exists.
03. Root `make test-extended` delegates to `make test-extended` for every registered level.
04. L0 `test-extended` preserves the validation behavior of the former L0 `test-all`.
05. Standalone L0 CI and Unified CI route L0 through `test-extended`, with visible L0 job and target naming migrated,
    while Unified CI routes L1 through `test-ci`.
06. L1 `test` provides a materially faster development loop and does not run complete trace, environment/bootstrap, or
    triple-bootstrap validation.
07. L1 `test-extended` runs broad local-normal validation without the CI-only categories.
08. L1 `test-ci` includes every test category intentionally removed from `test` and `test-extended`.
09. CI-only normal tests remain directly runnable by explicit name.
10. Full trace targets, trace smoke targets, slow trace targets, child trace targets, and `triple-test` remain directly
    runnable.
11. Runner regression coverage proves default exclusion and explicit inclusion behavior for CI-only normal tests.
12. `test_env_stackability.py` and other environment/bootstrap integration selected for CI-only coverage still execute
    in `test-ci`.
13. Current `AGENTS.md` guidance says `make test` is the normal development gate, `make test-extended` is the broad
    local/refactor gate, and L1 `make test-ci` is the exhaustive hosted gate.
14. Agent guidance explicitly recommends focused expensive validation rather than routine local `test-ci`.
15. The finalization skill understands the `test-ci > test-extended > test` reuse relationship.
16. Current operational docs and active plans contain no obsolete `test-all` commands.
17. Remaining `test-all` repository matches are reviewed and are historical records rather than live instructions or
    invocations.
18. L1 timing measurements demonstrate a substantial reduction from the baseline, with the final measured values
    recorded before plan closure.
19. `python3 scripts/check_adr_impact.py --all-active` passes with this plan active.
20. Existing Make, runner, Docker/Wine, and workflow regression tests affected by the target rename pass.

## Completion Decision

Do not close this plan merely because the rename and runner classification have landed.

Closure requires both:

1. functional proof that exhaustive L1 coverage is still present in `test-ci`, and
2. timing evidence that the local `test` and `test-extended` tiers are meaningfully suitable for their intended
   development workflows.

If the first implementation still leaves `test-extended` near the old full-suite cost, keep the plan active and continue
profiling the remaining normal-suite long tail.
