# Refactor Plan

## Isolate profile construction from managed preparation policy

- Date: 2026-09-30
- Status: Draft
- Title: Isolate the L1 profile construction boundary without changing managed behavior
- Kind: Refactor
- Severity: Medium
- Stage: Shared
- Parent Initiative: `l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md`
- Targets:
  - L1 Stage 1: Pending
  - L1 Stage 2: Pending
- Subsystem: Native preparation, destination ownership and shared construction
- Modules:
  - `l1/compiler/stage1_l0/src/preparation.l0`
  - `l1/compiler/stage1_l0/src/preparation/frontend.l0`
  - `l1/compiler/stage1_l0/src/preparation/consumer.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage2_l1/src/preparation.l1`
  - `l1/compiler/stage2_l1/src/preparation/frontend.l1`
  - `l1/compiler/stage2_l1/src/preparation/consumer.l1`
  - `l1/compiler/stage2_l1/src/build_driver.l1`
  - `l1/compiler/stage1_l0/support/preparation_support.c`
  - `l1/compiler/stage1_l0/support/preparation/`
- Test modules:
  - `l1/compiler/stage1_l0/tests/preparation_test.l0`
  - `l1/compiler/stage2_l1/tests/preparation_test.l1`
  - `l1/compiler/stage1_l0/tests/preparation_support_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_ownership_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_managed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_installed_preparation_test.py`
  - `l1/tests/test_stage2_tooling.py`
- Related:
  - [l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md][initiative]
  - [l1/work/plans/features/2026-09-30-explicit-profile-artifacts-noref.md][profile-plan]
  - [l1/work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md][economy-plan]
- Repro: From `l1/`, exercise explicit preparation plus cold, warm, forced and private-fallback native consumers.

## Summary

Expose one internal construction operation underneath the current preparation policy. Its inputs describe what to build
and an already owned staging destination. Its result describes the constructed payload. Cache selection, persistent
reuse eligibility, locks and publication ownership remain with the caller.

This plan adds no CLI option and no public profile format. It prepares the smallest useful implementation boundary for
the subsequent feature, without promising a broad source decomposition or changing the existing native service ABI
beyond what the extraction needs.

## ADR Impact

- Decision: Preserve bundled semantic authority and destination lifetime while separating construction from selection.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md`
  - Rationale: The refactor reorganizes existing ownership; semantic inputs, private fallback and user workflows are
    unchanged. Add the closed-plan link when completing the work.
- Decision: Preserve identity coverage, native configurations and conservative managed reuse eligibility.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: The extracted constructor does not decide whether outputs may be reused automatically. Existing policy
    still makes that decision before managed reuse and publication.
- Decision: Preserve completed-profile validation as the managed warm-hit evidence.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0040-warm-preparation-semantic-validation-reuse.md`
  - Rationale: This change must not put bundled frontend validation back onto the unchanged warm path.

## Current State

The proposal was drafted against `dea-lang/dea` on `main`, 2026-09-30, and rechecked against the local worktree on
2026-10-01. `pr_prepare` currently coordinates resolution, lookup, complete bundled validation on misses, eligibility,
locking, private fallback and construction. `pr_build_selected` connects destination setup, `pr_frontend_prepare` and
completion. `ManagedPreparation` retains the selected native support until the final consumer finishes.

These are usable seams, but the selected destination and construction configuration are supplied through preparation
context state. Native `pc_begin_profile`, `pc_output_path` and `pc_complete_profile` also depend on cache locks or a
private root, native identity and managed completion metadata. Wrapping `pr_build_selected` alone does not establish the
required boundary. The future explicit constructor must not need a fake cache root, cache identity or cache hit.

The current contract and earlier economy work are recorded in [l1/docs/reference/stdlib-preparation.md][preparation] and
[l1/work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md][economy-plan]. Recheck current function
boundaries before changing them; the lists above identify ownership, not a demand to edit every file.

## Goal and Non-Goals

The goal is one construction implementation callable from both the existing managed/private paths and a future
caller-directed artifact path. Keep configuration normalization explicit and retain separate generated-stdlib and
runtime C configurations.

Do not add a public manifest, new command, cache schema, background process, dependency scanner, generic task scheduler,
ABI compatibility classifier or new hashing algorithm. Do not change native toolchain support, installed-layout policy,
compiler selection defaults, runtime flags, diagnostic codes or the default build workflow.

## Defaults Chosen

The policy caller owns cache identity, eligibility, lookup, locks, destination allocation, persistence, publication,
managed completion metadata and replacement. The constructor owns only registered construction scratch and payload
production within its supplied destination. Consumers borrow the result for a declared lifetime; they never take
ownership of a cache entry accidentally.

Normalize construction configuration once per command and pass the selected compiler, ordered effective generated-C
options, separate runtime options, frontend code-generation settings, semantic inputs and header inputs explicitly.
Construction must not reread `L1_CFLAGS`, compiler selection or runtime defaults after receiving that configuration.
Reuse existing records when they suffice. A new owned record is justified only where it removes ambient lookups or
lifetime ambiguity; no speculative object hierarchy is required.

The native support remains compiler-private. Do not introduce public stdlib facilities to perform this extraction. Use
shared in-process calls, not recursively spawned `l1c` commands.

## Implementation Phases

### Phase 1: Pin behavior and map responsibilities

Record the live call graph from `pr_prepare` through `pr_build_selected`, the frontend constructor and native support
completion. Identify which probes are required to execute construction and which observations exist to authorize
persistent reuse. Include native writer/completion dependencies and repeated configuration reads such as
`bd_collect_c_option_words` in that inventory. Record the constructor's reads, writes and owned paths in this plan's
implementation notes.

Extend focused tests only where a boundary is currently unobserved. Cover cold preparation, an unchanged warm hit,
explicit prewarming, force, persistent ineligibility with successful private construction, corruption and storage
failure. Use a fixed supported toolchain and matching fixtures for comparisons.

Exit gate: the current behavior is reproducible and the proposed seam can be stated without changing cache policy. If
that requires a new public artifact contract, stop the extraction at the existing boundary and carry that part into the
feature plan rather than expanding this refactor.

### Phase 2: Extract the constructor and destination ownership

Move the minimal construction inputs out of implicit selection state. Give the constructor an already owned staging
root, immutable configuration for this invocation, the verified semantic set/dependency order and public header inputs.
Return an owned payload description or a failure with retained-path information.

Leave cache-key computation, lookup, lock/recheck, persistent refusal and fallback selection outside this operation.
Separate payload production and validation from managed manifest serialization and publication; the managed adapter
retains the existing manifest and identity rules. Remove cache-lock/private-root assumptions from the construction write
authorization in favor of the supplied owned destination. Do not remove input validation or capability checks needed for
correct construction. Keep their scheduling in the existing managed path unchanged unless equivalence is directly
demonstrated. This extraction does not add a public profile format or change managed reuse admission.

Document success and failure ownership: who removes scratch, who publishes, who releases a private directory and who
keeps recovery evidence. Publication remains the existing operation; this phase must not accidentally claim atomic
reader snapshots, crash durability or general concurrent replacement.

Exit gate: a focused internal fixture reaches construction through explicit normalized inputs and an owned destination
without inventing a cache entry or reuse identity. Verify that later ambient-default changes do not alter the supplied
configuration. The fixture uses the same implementation as the existing path and leaves no leaked owners or unregistered
scratch.

### Phase 3: Reconnect managed and command-private callers

Route the existing callers through the extracted boundary, preserving warm-hit short circuits, single-command native
resolution, lock/recheck order, private-support lifetime and diagnostic precedence. Preserve the just-in-time binding of
managed native artifacts without changing authoritative semantic origins.

Retain current cache storage and manifest formats. Changes to compiler inputs naturally change the content-derived
identity; tests must compare policy and work counts, not demand that a rebuilt compiler retain the old literal key. No
identity-input dependency may be dropped merely to make a test reuse an old entry.

Implement paired Stage 1 and Stage 2 behavior in the same change set, preserving Stage 2's reviewed L1 idioms. Keep the
C service shared and avoid another stage-specific copy.

Exit gate: both stages preserve observable behavior, applicable generated-C identity and the established ownership and
cache-reuse regressions.

### Phase 4: Validate and close the bounded refactor

Run focused preparation, native-support, provider/link and Stage 2 tooling tests first. Then run the required aggregate,
trace and strict bootstrap checks for the affected ownership paths. Update current architectural documentation only for
the internal boundary that actually landed; future profile commands remain documented only in the draft feature plan.

Close this plan independently of the feature. Update the initiative's membership, ADR Related Plans links and roadmap
references in the same change. No profile feature is implied by closure.

## Verification Criteria

| Scenario                                            | Required observation                                                                                                                     |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Unchanged managed warm request                      | No profile construction or complete bundled frontend revalidation; no new repeated native resolution.                                    |
| Direct construction fixture                         | Explicit inputs and owned destination suffice without a cache identity; later ambient defaults do not change the supplied configuration. |
| Cold or forced request                              | Same normalized stdlib/runtime configurations and payload inventory, with existing diagnostics and completion rules.                     |
| Invocable but persistently ineligible configuration | Existing explicit prewarm refusal and successful automatic private fallback remain distinct.                                             |
| Explicit provider or runtime override               | Existing precedence and preparation avoidance remain unchanged.                                                                          |
| Corruption, lock contention and storage failure     | Existing recheck, recovery, fallback and retained-evidence behavior is preserved.                                                        |
| Failure and cleanup                                 | No owned allocation or registered scratch leak; private support survives through its last consumer.                                      |
| Stage parity                                        | Stage 1 and Stage 2 exercise the same cases and preserve diagnostics and applicable generated-C bytes.                                   |

Use work counts and attributed timings, not unmeasured speedup claims. Retain before/after cold and warm measurements
when a changed boundary may add work, and investigate any unexplained regression. Do not introduce a new performance
threshold without evidence.

From `l1/`, the final implementation validation includes the applicable focused suites, `make test-extended`, relevant
ownership cases through both `test-stage1-trace` and `test-stage2-trace`, and `make triple-test`. Explicitly select
`TESTS="l1c_stage1_preparation_test l1c_stage1_installed_preparation_test"` with each of `make test-stage1` and
`make test-stage2`; these shared integration cases are excluded from normal discovery by the CI-only policy.
`make test-ci` is the exhaustive hosted-equivalent gate, not an additional repeat of already covered validation.

Exercise the repo-owned Linux Docker path with GCC, and supported Windows/macOS paths when available. Verify actual
compiler executable/version in each environment under [l1/AGENTS.md][l1-agents]. An unavailable platform is an explicit
coverage gap, not a passing result. Existing evidence may be reused only under the repository's current validation
rules.

## Diagnostics and Documentation

No diagnostic identifiers are added or reassigned. Existing preparation, compile and link errors keep their meanings.
Recheck [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] if implementation reveals a genuinely new failure
category; move that feature-bearing change to the dependent plan rather than silently extending this refactor.

Maintain [l1/docs/reference/architecture.md][architecture] and [l1/docs/reference/stdlib-preparation.md][preparation] as
needed for landed ownership changes. Preserve current user instructions and command examples.

Run `python3 scripts/check_adr_impact.py --all-active` while planning, and the staged ADR, whitespace and required root
pre-commit checks before any implementation commit. This draft records intended validation only.

## Dependencies and Authorization

Coordinate overlapping edits with the active preparation-efficiency and Stage 2 source-review work. This refactor does
not authorize their deferred optimizations, legacy-toolchain changes or a Makefile conversion.

Remote pushes, tags, releases, workflow dispatches and deployments are outside this plan. Any such operation requires
its own fresh authorization under `AGENTS.md`; writing or implementing this plan is not that authorization.

[architecture]: ../../../docs/reference/architecture.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[economy-plan]: closed/2026-09-12-native-preparation-economy-noref.md
[initiative]: ../../initiatives/0010-explicit-profiles-and-composable-builds.md
[l1-agents]: ../../../AGENTS.md
[preparation]: ../../../docs/reference/stdlib-preparation.md
[profile-plan]: ../features/2026-09-30-explicit-profile-artifacts-noref.md
