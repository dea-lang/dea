# Tool Plan

## Add tiered test validation for routine commits

- Date: 2026-07-14
- Status: Completed
- Title: Add tiered test validation for routine commits
- Kind: Tooling
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - Monorepo root test orchestration
  - Dea/L0 test orchestration
  - Dea/L1 test orchestration
  - Dea finalization policy and workflow documentation
- Origin: Monorepo root `Makefile` and `.agents/skills/finalize-dea-work/SKILL.md`
- Porting rule: Keep the `test` versus `test-all` contract shared; retain each level's existing normal and dedicated
  trace target composition.
- Target status:
  - Monorepo root test orchestration: Implemented
  - Dea/L0 test orchestration: Implemented
  - Dea/L1 test orchestration: Implemented
  - Dea finalization policy and workflow documentation: Implemented
- Subsystem: GNU Make test entrypoints / finalization validation / developer workflow documentation
- Modules:
  - `Makefile`
  - `l0/Makefile`
  - `l1/Makefile`
  - `.agents/skills/finalize-dea-work/SKILL.md`
  - `CLAUDE.md`
  - `l0/CLAUDE.md`
  - `l1/CLAUDE.md`
- Test modules:
  - `l0/tests/test_make_dea_build_workflow.py`
  - root, L0, and L1 Make dry-run validation
  - root `make clean test-all`
- Related:
  - `MONOREPO.md`
  - `CONTRIBUTING.md`
- Repro: `make clean test-all`

## Summary

The finalization workflow currently selects only full level or monorepo `test-all` aggregates for code changes. Those
aggregates include the dedicated ARC/memory trace sweeps even when a change cannot affect runtime, ownership, emitted
lifetimes, or trace infrastructure. The trace sweeps account for most of the full suite's wall time, making routine
single-change commits unnecessarily expensive.

This plan adds a `test` aggregate at the root and in both implemented levels. It preserves the current normal validation
surface while omitting only the dedicated broad trace runner. `test-all` remains the full trace-inclusive aggregate and
continues to back CI and Docker. The finalization skill will choose between the two tiers from the complete staged diff
and will reuse already-passing validation instead of repeating covered work.

## Defaults Chosen

1. `test` means normal validation without the dedicated `run_trace_tests.py` sweep. Focused trace regressions already
   embedded in normal test suites remain included.
2. `test-all` is required for runtime, memory, ownership, ARC, pointer-validation, emitted-lifetime, trace
   infrastructure, and trace-input changes, plus mixed or uncertain diffs.
3. Trace-independent compiler, Python-test, CI-routing, packaging, and tooling changes may use `test` while retaining
   any focused validation required by their subsystem.
4. A passing `test-all` satisfies `test`. A passing `test` can be combined with the missing level trace target when the
   validated inputs remain unchanged.
5. CI and Docker continue to use `test-all`; the intentionally slow L1 trace extension remains opt-in.

## Goal

1. Provide stable normal and full validation entrypoints at the monorepo root, L0, and L1.
2. Remove broad trace sweeps from routine trace-independent local finalization.
3. Preserve full trace validation whenever a diff can affect trace health or trace coverage.
4. Keep validation reuse mandatory across both tiers and make final handoffs record the chosen tier and rationale.
5. Keep developer and agent workflow documentation aligned with the shipped Make contract.

## Implementation Phases

### Phase 1: Add the Make targets and regression coverage

- Add root `test` dispatch across registered levels.
- Add L0 and L1 `test` aggregates containing every current `test-all` prerequisite except the dedicated trace target.
- Express each level's `test-all` as its `test` aggregate plus the existing trace target.
- Advertise the new target in `.PHONY` and help output.
- Extend L0 Make workflow regression coverage to prove that `test` includes normal validation and omits the dedicated
  trace runner while `test-all` retains it.

### Phase 2: Add risk-tiered finalization policy

- Classify the full staged diff independently by affected scope and trace risk.
- Document exact L0, L1, shared, and docs-only validation commands for both tiers.
- Define mandatory full-validation categories, affirmative trace-independent examples, mixed/uncertain fallback, and
  continued focused-check requirements.
- Generalize validation reuse and clean-build guidance across `test` and `test-all`.
- Require the handoff to report the selected tier, rationale, commands, and reuse evidence.

### Phase 3: Refresh workflow documentation

- Add the root and level `test` entrypoints to maintained agent, contributor, Copilot, monorepo, and status guidance.
- Explain that `test` omits the dedicated broad trace sweep while `test-all` remains the full CI/Docker backstop.
- Make trace requirements conditional on trace-sensitive work rather than every compiler change.
- Refresh edited status-document versions to `2026-07-14`.

### Phase 4: Validate, close, and commit locally

- Dry-run root, L0, and L1 `test` and `test-all` targets and inspect their command composition.
- Run root `make clean test-all` because this change alters test and trace orchestration.
- Run staged whitespace and root pre-commit checks.
- Record results, mark every target implemented, move this plan to `work/plans/tools/closed/`, and create one cohesive
  local commit. Do not push or perform any remote operation.

## Non-Goals

- Removing focused trace regression tests from normal suites.
- Changing trace event semantics, trace runner implementation, or the set of trace-eligible tests.
- Changing CI, Docker, release, or publication defaults away from `test-all`.
- Adding the intentionally slow L1 trace cases to either aggregate.
- Changing compiler, runtime, language, or standard-library behavior.

## Verification Criteria

1. Root `make test` invokes `make test` in every registered level; root `make test-all` still invokes each level's
   `test-all`.
2. L0 `make test` includes Stage 1, Stage 2, examples, workflow, and distribution validation but not
   `test-stage2-trace`; L0 `make test-all` includes both.
3. L1 `make test` includes Stage 1, environment-stackability, and example validation but not `test-stage1-trace`; L1
   `make test-all` includes both.
4. The Make workflow regression asserts the L0 target inventory and trace exclusion/inclusion contract.
5. The finalization skill selects `test` only for confidently trace-independent work and fails safe to `test-all` for
   trace-sensitive, mixed, or uncertain changes.
6. Validation reuse never repeats a covered normal suite solely to add missing trace coverage.
7. Full clean validation covers every registered level; staged whitespace checks and pre-commit pass before the local
   commit.

## Completion Notes

- Root, L0, and L1 now expose `test` for normal validation without the dedicated broad trace sweep. Each level's
  `test-all` composes that target with its existing default trace target; CI, Docker, and L1 slow-trace behavior remain
  unchanged.
- The L0 Make workflow regression advertises and dry-runs both tiers, verifies every normal component, excludes the
  dedicated trace runner from `test`, and requires it in `test-all`.
- `.agents/skills/finalize-dea-work/SKILL.md` now classifies scope and trace risk independently, fails safe on mixed or
  uncertain work, preserves focused checks, and permits unchanged passing `test` coverage to combine with only the
  missing level trace target.
- Live workflow guidance was refreshed across root, L0, and L1 agent, contributor, Copilot, monorepo, and status docs.
  Edited status documents carry `Version: 2026-07-14`. Root, L0, and L1 ADR indexes were audited and remain complete;
  this tooling policy did not require a new ADR.
- Root/L0/L1 dry runs for `test` and `test-all`, all three help outputs, Python syntax validation, and
  `git diff --check` passed. The dry runs proved that only `test-all` invokes the dedicated trace runners.
- Root `make clean test-all` completed L0 successfully: 1,327 Stage 1 tests, 54 Stage 2 cases, eight examples, all
  workflow tests, and 33 trace checks passed. The root process then received external signal 15 while building L1; no
  test failed and no validated input changed.
- The completed L0 result was reused, and only the incomplete scope was resumed with `make -C l1 test-all`. L1 passed 51
  normal implementation tests, environment-stackability, four examples, and all 37 default trace checks. Together the
  unchanged L0 and L1 results cover the full clean root validation surface without repeating passed work.
- `git diff --cached --check` passed. Root pre-commit passed both `copyright-headers` and `mdformat` after the
  Markdown-only formatting changes from the first hook run were restaged.
