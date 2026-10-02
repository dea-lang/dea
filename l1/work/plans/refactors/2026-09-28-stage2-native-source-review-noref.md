# Refactor Plan

## Review and idiomatize the self-hosted L1 compiler source

- Date: 2026-09-28
- Status: In Progress
- Title: Review and idiomatize the self-hosted L1 compiler source
- Kind: Refactor
- Severity: Medium
- Stage: 2
- Subsystem: Compiler implementation / Stage 2 source / L1 language adoption
- Modules:
  - `l1/compiler/stage2_l1/src/`
- Test modules:
  - `l1/compiler/stage2_l1/tests/`
  - Shared compiler-facing integration tests under `l1/compiler/stage1_l0/tests/`
- Related:
  - [work/plans/features/closed/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md][self-hosting]
  - [l1/work/plans/refactors/closed/2026-07-08-stage1-source-decomposition-noref.md][decomposition]
  - [docs/decisions/0001-two-stage-architecture.md][two-stage]
  - [l1/docs/reference/architecture.md][architecture]
- Repro: From `l1/`, run `make test-stage2 test-stage-parity` and `make triple-test`.

## Summary

The mechanical L1 Stage 2 port is complete. The review inventory contains 120 original production modules; Phase 1
removes one unused path-wrapper module, leaving 119. The repository provides Stage 2 normal and trace tests, behavioral
parity checks, and strict triple-bootstrap validation.

Review every production module and replace inherited L0 constraints with implemented L1 facilities where this improves
correctness of representation, ownership clarity, readability, or implementation simplicity.

This is a semantics-preserving refactor. Stage 1 remains the semantic and diagnostic oracle. No public language,
runtime, ABI, CLI, diagnostic, or module-interface contract changes are planned. No new diagnostic codes are planned or
reserved.

## ADR Impact

- Decision: Apply existing L1 capabilities to the self-hosted compiler without changing its architecture or external
  contracts.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The work changes implementation choices within accepted language and compiler contracts. Architectural or
    semantic changes discovered during review require separately scoped work.

## Baseline and review evidence

Before changing compiler sources:

1. Revalidate the completed self-hosting baseline with `make test-ci`, run from `l1/`. This includes the complete normal
   suites, parity, trace suites, child fixtures, and triple bootstrap.
2. Record the selected native compiler executable, version, configuration, and validation results. Follow the
   supported-toolchain requirements in [l1/AGENTS.md][guidance].
3. Inventory all committed production modules, including modules added during the review.
4. Create `l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/review.md`.

The ledger records each module's disposition, relevant review findings, retained compatibility helpers, validation
evidence, and any separate follow-up:

- Pending.
- Reviewed, unchanged.
- Reviewed, changed.
- Reviewed, external follow-up recorded.

An external follow-up is a completed review disposition only when the current implementation remains valid and the
deferred improvement is outside this plan. It must not conceal unfinished in-scope work.

Record recurring L2 limitations in a separate section of the ledger, with concrete source examples and their
implementation cost. These are observations, not accepted feature proposals.

## Review rubric

Prefer the simplest implementation that accurately expresses an existing invariant. Feature adoption is not a completion
metric.

- **Numeric types:** Match established value domains. Preserve overflow, signedness, conversion, indexing, and
  serialization behavior. Do not widen integers without evidence.
- **Constants:** Use `const` for genuine compile-time values. Preserve runtime initialization and module lifecycle
  order.
- **Arrays and slices:** Replace fixed collections or pointer-plus-length patterns only where extent, ownership,
  lifetime, and escape rules fit. Preserve growable containers where required.
- **Dispatch and variadics:** Use function pointers or L1-defined variadics when they simplify a real interface.
  Preserve typing, evaluation order, and ownership behavior.
- **Imports and exports:** Clarify provenance and existing abstraction boundaries with selective imports, aliases, or
  opaque exports. Avoid unnecessary module restructuring.
- **Unsafe operations:** Localize raw-memory operations behind accurate `unsafe func` contracts. Preserve validation and
  cleanup behavior.
- **Operators and syntax:** Consider direct bitwise operations, numeric prefixes, string and nullable/pointer
  comparisons, named arguments, and clearer control-flow forms. Readability takes precedence over brevity.
- **Standard library:** Replace private helpers only with already implemented APIs that match semantics, ownership,
  errors, portability, and performance requirements.
- **Compatibility scaffolding:** Remove helpers needed solely for L0 limitations. Retain native bridges and wrappers
  that still serve compiler, portability, testing, or bootstrap contracts.

Review each function together with its relevant callers, callees, and data ownership. A local simplification must
preserve behavior at its boundaries.

## Implementation phases

This remains one standalone plan because all five phases apply the same review rubric and preserve the same compiler
contracts. They do not require independently designed sub-plans. Execute phases in order and track their status here;
each phase starts as Pending and becomes In Progress, then Complete when its exit gate passes. The plan stays active
until Phase 5 completes.

Use independently reviewable tranches within each phase. After each source-changing tranche, run affected implementation
tests, `make test-stage-parity`, and relevant trace coverage from `l1/`. Run `make triple-test` before treating that
tranche as complete. Record commands and results in the ledger; unchanged code does not require redundant runs against
an already validated tree.

### Phase 1: Baseline, inventory, utilities, and models

- Status: Complete
- Review scope: The 16 shared utility/model modules identified in the
  [l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/review.md][review-ledger].
  Subsystem-specific state and models remain with their owning later phases.
- Complete the baseline and review-evidence steps above before editing compiler sources.
- Assign every production module to exactly one review phase (1 through 4) in the ledger. Assign newly added modules as
  they appear and retain provenance for renamed or split modules.
- Review shared data representations, diagnostics utilities, strings, containers, paths, filesystem wrappers, and
  numeric helpers. Apply justified improvements in bounded tranches.
- Deliverable: A validated baseline, complete phase-assigned inventory, and completed utility/model review entries.
- Completion: All 16 modules reviewed (five changed, eleven unchanged); full normal/trace validation, stage parity,
  strict triple bootstrap, and seven-pair performance/allocation evidence passed. The original 120-module inventory is
  preserved; 119 modules remain after removing unused `util.path`. See the review ledger for retained helpers, all 265
  original function bodies, and exact results. Later phase statuses are recorded below.
- Exit gate: Every Phase 1 module has a completed disposition, and all source-changing tranches satisfy the common
  validation gate with required performance evidence.

### Phase 2: Frontend and semantic analysis

- Status: Complete
- Review lexing, parsing, resolution, typing, constant evaluation, imports, interfaces, and diagnostic construction.
- Prioritize representations, operators, constants, imports, and compatibility helpers while preserving diagnostic
  output and interface contracts.
- Deliverable: Completed frontend and analysis review entries, justified source changes, and targeted regression
  coverage.
- Completion: All 56 frontend/analysis modules reviewed (seven changed, 49 unchanged), covering 796 original function
  bodies and the replacement variadic matcher. Four source-changing tranches passed focused tests, stage parity,
  relevant traces and strict triple bootstrap. Repeated performance and allocation evidence is recorded in the review
  ledger. Stage 1 remains unchanged; Phases 3 through 5 remain pending.
- Exit gate: Every Phase 2 module has a completed disposition, and all source-changing tranches satisfy the common
  validation gate with required performance evidence.

### Phase 3: Backend and build orchestration

- Status: Pending
- Review lowering, C emission, lifecycle planning, artifact management, native invocation, preparation integration, and
  linking.
- Prioritize ownership and unsafe boundaries, value widths, dispatch, and compatibility scaffolding without reopening
  preparation or separate-compilation architecture.
- Deliverable: Completed backend/orchestration review entries, justified source changes, and targeted regression
  coverage.
- Exit gate: Every Phase 3 module has a completed disposition, and all source-changing tranches satisfy the common
  validation gate with required performance evidence.

### Phase 4: Remaining modules, tests, and coverage audit

- Status: Pending
- Review every remaining production module and reconcile the ledger against the current source tree.
- Adapt implementation tests only where source changes require it or materially improve their expression. Tests for
  earlier phases accompany those changes; they are not postponed until this phase.
- Audit retained compatibility helpers and document their purposes. Record any external follow-ups and L2 observations.
- Deliverable: A complete production review ledger with no Pending entries and explicit reasons for retained
  scaffolding.
- Exit gate: The inventory has no omissions, no unfinished in-scope work is deferred, and all source-changing tranches
  satisfy the common validation gate with required performance evidence.

### Phase 5: Final validation, documentation, and closure

- Status: Pending
- Run the complete validation commands and completion checks below against the consolidated implementation.
- Update implementation documentation and summarize review outcomes, retained constraints, and external follow-ups.
- Archive the plan and update its roadmap entry and links only after every completion criterion passes.
- Deliverable: Final validation evidence, accurate current documentation, and the closed plan with its completed ledger.
- Exit gate: All verification criteria pass, every earlier phase is Complete, and documentation and lifecycle checks
  pass.

Preserve Stage 1's implementation unless a separately scoped semantic fix requires coordinated changes. L1-only
implementation idioms do not require artificial L0 equivalents.

If adoption of an implemented feature exposes a compiler defect, isolate it with a reproducer and handle it separately,
with Stage 1 first and the equivalent Stage 2 fix in the same change. Do not weaken validation to accommodate it.

## Behavioral and performance constraints

- Preserve accepted and rejected programs, diagnostic codes and messages, CLI behavior, exit statuses, generated-program
  behavior, ABI, interface formats, and fingerprint rules.
- Preserve the existing intentional compiler identity difference between stages.
- Generated compiler C may differ from the pre-refactor baseline.
- Preserve the existing triple-bootstrap contract: A is built by Stage 1, B by A, and C by B; retained-C inventories
  agree with A, and B/C bytes match. Keep the existing native normalization and platform exceptions unchanged.
- Do not introduce new syntax, L2 facilities, public stdlib capabilities, or unfinished stdlib dependencies.
- Do not reopen compiler architecture, ownership rules, separate compilation, preparation policy, or cache design.

For changes plausibly affecting hot paths, allocation, artifact size, or build time, compare representative workloads
under the same toolchain and configuration. Repeat measurements sufficiently to distinguish noise. Investigate and
remove unexplained material regressions; broad optimization work remains separate.

## Validation and completion

From `l1/`, run:

```bash
make test-ci
```

Use targeted regression cases for changed boundaries, especially numeric conversions, slice lifetimes, cleanup paths,
diagnostics, and dispatch behavior. Extend parity coverage where an affected observable behavior is not already
exercised.

Completion requires:

- Every current production module has a completed ledger entry.
- Each retained compatibility helper identified during review has a concrete justification.
- Applicable normal, parity, trace, child-trace, and fixed-point checks pass.
- Performance-sensitive changes have recorded evidence.
- Documentation accurately describes the reviewed implementation.
- No semantic defect or unfinished in-scope change is hidden as deferred work.

## Documentation and lifecycle

Track this standalone plan in [l1/docs/roadmap.md][roadmap]. Creating the draft does not start the compiler refactor or
claim baseline validation has run. The ledger is created during implementation.

At implementation closure, update [l1/compiler/stage2_l1/README.md][stage2-readme],
[l1/docs/project-status.md][project-status], [l1/docs/roadmap.md][roadmap], and
[l1/docs/reference/architecture.md][architecture] where affected; archive the plan and repair its links.

Validate the document with `python3 scripts/check_adr_impact.py --all-active`, link checks, and Markdown checks. No
compiler suite is required merely to create the planning document.

[architecture]: ../../../docs/reference/architecture.md
[decomposition]: closed/2026-07-08-stage1-source-decomposition-noref.md
[guidance]: ../../../AGENTS.md
[project-status]: ../../../docs/project-status.md
[review-ledger]: attachments/2026-09-28-stage2-native-source-review/review.md
[roadmap]: ../../../docs/roadmap.md
[self-hosting]: ../../../../work/plans/features/closed/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md
[stage2-readme]: ../../../compiler/stage2_l1/README.md
[two-stage]: ../../../../docs/decisions/0001-two-stage-architecture.md
