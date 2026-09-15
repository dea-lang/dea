# Feature Plan

## Investigate reuse of bundled semantic validation on warm native preparation

- Date: 2026-09-13
- Status: Draft
- Title: Determine whether warm L1 native preparation can reuse complete bundled semantic validation
- Kind: Feature
- Severity: Medium
- Stage: 1
- Subsystem: Compiler driver / bundled semantic interfaces / native preparation identity and validation
- Modules:
  - `l1/compiler/stage1_l0/src/preparation.l0`
  - `l1/compiler/stage1_l0/src/preparation/frontend.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/driver/resolve.l0`
  - `l1/compiler/stage1_l0/support/preparation_support.c`
  - `l1/compiler/stage1_l0/support/preparation/identity.h`
  - `l1/compiler/stage1_l0/support/preparation/storage.h`
  - `l1/scripts/build_stage1_l1c.py`
- Test modules:
  - `l1/compiler/stage1_l0/tests/preparation_test.l0`
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_support_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_ownership_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_bootstrap_interfaces_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_managed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_installed_preparation_test.py`
- Related:
  - [l1/work/plans/tools/closed/2026-09-13-preparation-test-cost-noref.md][test-cost]
  - [l1/work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][preparation-plan]
  - [l1/work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md][preparation-economy]
  - [l1/docs/reference/stdlib-preparation.md][preparation]
  - [l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md][semantic-adr]
  - [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][identity-adr]
- Repro: After preparing one eligible native profile, repeat the same
  `l1c --prepare-stdlib --c-compiler clang --stdlib-cache PATH -vvv` invocation and count `_dea_preparation` analysis
  starts.

## Summary

Investigate whether a valid warm native profile can avoid repeating the full bundled interface graph analysis without
weakening semantic authority, invalid-input diagnostics, or native reuse validation. The current full-graph pass is an
explicit contract, not an established correctness defect. Keeping it is a valid outcome if a cheaper equivalent check
cannot be justified.

This is the deferred point 6 from the Intel Mac CI investigation. Points 1 through 5 are separately tracked in
[l1/work/plans/tools/closed/2026-09-13-preparation-test-cost-noref.md][test-cost]: isolate unrelated runtime tests from
automatic preparation, retain integration coverage, measure remaining trace cost, split a harness only if measurements
justify it, and avoid unnecessary native support compilation. Those changes preserve production preparation semantics.
This draft records later design work; it does not authorize implementation of a different validation contract now.

## ADR Impact

- Decision: What evidence may replace complete bundled semantic graph analysis on a warm native preparation hit?
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: The current semantic authority is established by ADR-0038 and ADR-0039. The investigation must determine
    whether unchanged validated inputs suffice, whether new evidence is required, or whether the full pass remains
    necessary. A resulting amendment or new L1 ADR has not been selected.
- Decision: How would reusable validation evidence be invalidated, published and recovered without changing cache
  ownership or diagnostic guarantees?
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: A persistent validation result could extend today's non-authoritative memo role or bootstrap contract.
    Its identity, compatibility and failure behavior require an explicit decision before implementation.

## Current State

`pr_prepare` resolves the native context, then calls `pr_frontend_order` before native profile lookup. The frontend
creates an umbrella source importing every selected bundled module, validates the complete interface graph, and returns
dependency-ordered module names. The analysis and temporary workspace are released before lookup or construction; the
owned order remains available for cold preparation and private fallback.

This includes bundled modules that no other bundled source imports, such as `std.types`. The current tests deliberately
require one `_dea_preparation` analysis on both cold and warm preparation. Invalid selected interfaces receive ordinary
frontend diagnostics plus `L1C-2158` repair guidance, including with `--no-auto-prepare`.

The native identity already includes the effective compiler, compiler-owned source inputs, complete bundled module
inventory and selected interface bytes. Development identity observes Stage 1 sources/support as well as the running
executable. Native configuration and toolchain observations then produce the native key. Reliable metadata can reuse
content hashes, but the existing toolchain/artifact memos are not semantic authority. A completed native manifest checks
inventory, identity, containment and artifact integrity; those checks are distinct from `.l1m` semantic validation.

The contracts and rationale are recorded in [l1/docs/reference/stdlib-preparation.md][preparation],
[l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md][semantic-adr] and
[l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][identity-adr]. Merely moving a native hit
return ahead of `pr_frontend_order` does not establish equivalent validation.

## Initial Measurement Context

The 2026-09-13 investigation reported the Intel Mac job growing from about 16 minutes to 51 minutes, with the trace
phase growing from 7m40s to 31m38s. The largest trace harness emitted about 10.56 GB and 76.9 million events. These are
initial whole-suite observations, before the test/build isolation work; they do not measure this plan's potential
savings.

A local probe using the Intel CI compiler reportedly reused a warm profile with zero managed module compilations and
zero identity/artifact content reads, while still analyzing all 23 bundled interfaces. A tiny no-import build took about
6.0 seconds with managed preparation versus 2.1 seconds with explicit runtime inputs. These timings were collected under
local contention and compare more than the semantic pass. They are motivation to measure, not a performance target or
predicted CI reduction.

Use the completed [l1/work/plans/tools/closed/2026-09-13-preparation-test-cost-noref.md][test-cost] as the
test-isolation baseline, then remeasure when this investigation begins. Use its remaining automatic-preparation cases so
reduced test repetition is not counted again as a production speedup.

## Questions To Resolve

1. Which exact inputs determine successful complete bundled validation? Audit compiler identity, selected interface
   contents, module inventory, semantic roots, path-sensitive behavior, format/validator versions and all relevant
   options. Establish whether `D` already covers them; do not infer coverage from the key's name.
2. Does a successful previous validation produce observable warnings or ordering-sensitive diagnostics that would need
   to be reproduced? Decide whether success-only reuse can preserve those observations without retaining stale paths or
   making serialized diagnostics authoritative.
3. Is a completed native profile sufficient evidence that the current compiler performed the required validation, or
   would an explicit validated record be needed? Examine low-level preparation callers, malformed but digest-consistent
   records and old formats. A manifest's existence or self-consistent hashes alone are not a semantic proof.
4. Should evidence be local to one native profile, shared across native configurations with the same Dea inputs, or
   produced by bootstrap? Determine whether any option would introduce a second semantic store or an installed-payload
   requirement that contradicts the current architecture. Bootstrap-produced evidence must additionally bind the
   generating bootstrap compiler identity (`L1_BOOTSTRAP_L0C`) with the same development source sensitivity as `D`:
   rebuilding under a different upstream compiler or changing validated development inputs must invalidate the record,
   and one bootstrap compiler's evidence must never certify another compiler's semantic results.
5. When evidence is missing, stale, unavailable or malformed, can the command safely fall back to the current complete
   validation before deciding miss, disabled preparation or recovery? Distinguish disposable evidence failure from
   corruption of a completed native profile.
6. How do force, a waiting writer's recheck, a readable but unwritable cache and command-private fallback behave? The
   current lock, ownership and external-serialization rules remain constraints unless a separate change is justified.

## Alternatives To Evaluate

| Alternative                                                                                 | Potential benefit                                           | Proof or cost required                                                                                                                                       |
| ------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Retain the full pass on every preparation command                                           | Preserves the current simple authority and diagnostic model | Measure the residual cost after test isolation; consider only internal improvements that retain full validation.                                             |
| Reuse a prior successful full validation tied to exact compiler and semantic input identity | Can eliminate umbrella analysis for unchanged warm inputs   | Specify evidence production, complete dependency coverage, warning behavior, invalidation and recovery; explain its relationship to non-authoritative memos. |
| Make bootstrap or installed-payload validation evidence explicit                            | May amortize validation independently of native variants    | Define freshness, relocation, payload integrity and development rebuild semantics; demonstrate why this does not make mutable interfaces implicitly trusted. |

Do not select application-closure-only validation as an equivalent optimization: today's contract validates the complete
bundled set, including unreferenced modules. Do not introduce an unchecked mode or treat native artifact integrity as
semantic correctness. Prefer no additional persistent state if measured gains do not justify its complexity.

## Required Safety Argument

For each candidate, write down the inputs, success predicate, evidence lifetime and fallback behavior before coding.
Demonstrate that every accepted warm state corresponds to a full validation of the same effective semantic inputs by the
same relevant validator. Native reuse eligibility and complete profile validation remain separate obligations.

The argument must cover:

- ordinary metadata-changing edits, additions, removals and restorations of any bundled interface or module, including
  modules outside the application's closure;
- compiler/validator replacement, development source changes, semantic root changes and supported installed layouts;
- malformed, truncated, stale, version-mismatched and digest-consistent structurally invalid evidence;
- a missing or corrupt native manifest, changed native artifacts and semantic copies differing from selected inputs;
- failure or interruption between validation, evidence publication and native manifest publication;
- sequential warm reuse, same-key wait/recheck, different native configurations and fresh private fallback;
- no-auto and explicit-preparation failure classification, application errors that currently prevent preparation, and
  explicit provider precedence;
- exact generated-C retention and final interface/fingerprint/lifecycle/provenance checks at their existing boundaries.

Metadata-preserving external mutation, concurrent external input mutation and cache copying between hosts remain outside
the existing guarantee. This investigation must not silently broaden reliance on those exclusions or claim stronger
authentication than the current local cache provides. Failed semantic validation must never publish reusable success
evidence.

## Diagnostic-Code Planning

The current preparation family in [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] defines `L1C-2150`
through `L1C-2159`; `L1C-2160` through `L1C-2169` remain reserved for this established area. No new diagnostic category
or code assignment is proposed by this investigation.

Preserve ordinary parse, fingerprint, dependency, graph and lifecycle diagnostics together with `L1C-2158` bootstrap or
installation repair guidance. Preserve the distinction between missing reusable support (`L1C-2159`), completed profile
corruption (`L1C-2153`), identity/input failure (`L1C-2151`) and the existing storage, coordination and eligibility
errors. In particular, malformed semantic inputs must not be hidden behind a later no-auto cache-miss message.

If the selected design needs an additional user-actionable diagnostic, first consider the nearby reserved preparation
numbers instead of reserving a new block. Update this plan with the specific provisional assignment and re-check the
live catalog before implementation; any number may have been used in the meantime.

## Investigation Phases

1. Reproduce the current warm/cold behavior after test isolation. Record compiler configuration, host, worker count,
   cache and memo state, interface inventory, umbrella/per-module analysis counts and native compilation counts.
   Attribute the complete bundled validation in isolation: time a warm `--no-auto-prepare` hit against a trivial
   no-import consumer and subtract the same consumer's explicit-input cost, so the isolated median pass cost `C` is
   separated from application compilation and native resolution.
2. Audit validation dependencies and observable diagnostics. Trace the preparation state transitions and compare the
   existing manifest, identity and memo schemas with the evidence each candidate would require.
3. Build isolated falsification probes for the candidates' safety claims. Keep production semantics unchanged during the
   investigation and document counterexamples as reasons to reject or narrow a candidate. Cover at minimum: replacing
   the validator or its compiler-owned inputs under an unchanged evidence key; removed, edited and restored bundled
   interfaces, including modules outside the application closure; malformed, truncated, stale, version-mismatched and
   digest-consistent structurally invalid evidence; interruption between validation, evidence publication and manifest
   publication; and warm reuse, same-key wait/recheck and no-auto failure classification after each failure mode. Map
   each probe to the matching Required Safety Argument bullet when recording its outcome.
4. Measure viable prototypes with repeated interleaved runs on Intel Mac when available. Separate native resolution,
   bundled analysis, manifest/artifact validation and application compilation. Report medians and spread, plus trace
   execution and analysis time, event count, trace bytes and peak memory. Keep raw logs temporary; retain a concise
   evidence report if needed.
5. Select the justified outcome: retain the present contract, preserve it with proven validation reuse, or propose an
   explicit contract amendment. Resolve both ADR questions and specify compatibility, documentation and regression
   coverage. Pre-register the acceptance thresholds from the Phase 1 isolated cost `C` before Phase 4 prototyping;
   starting defaults are to retain the full pass when `C` is below a 500 ms median, and otherwise to proceed only when
   the best prototype removes at least 60 percent of `C` without measurably regressing cold/miss, manifest-validation or
   trace-analysis budgets (non-overlapping medians across at least five interleaved runs each). Record `C` and the
   confirmed thresholds in this plan before any prototype runs. Any implementation proceeds as later authorized work,
   with this draft updated to the settled design.

## Phase 1 Measurement Checkpoint

- Date: 2026-09-15. Host: Intel macOS 15.7.9 (x86_64, MacBookPro16,1), 12 CPU cores; l1c analysis is single-process.
  Compiler: Apple clang 17.0.0 (clang-1700.6.4.2), x86_64-apple-darwin24.6.0.
- Interface inventory: 23 verified bundled interfaces under `$L1_BUILD_DIR/interfaces` after `make build-stage1`.
- Cold `--prepare-stdlib --c-compiler clang -vvv` into a fresh cache: 22.30 s wall; one `_dea_preparation` umbrella
  analysis, 23 per-module frontend analyses, and 23 managed module compilations. Statistics: 27 probes, 33 build
  commands, 377 identity content reads, 47 artifact content reads, 47 metadata checks, 0 option file parses, 1 option
  root expansion.
- Warm `--prepare-stdlib --c-compiler clang -vvv` against the completed profile: 0.78 s wall; one complete umbrella
  analysis, zero per-module analyses, zero managed compiles and build commands; 4 probes, 0 identity content reads, 47
  artifact content reads, 47 metadata checks. This confirms the current contract: every warm hit still performs the
  complete bundled validation while skipping all native work.
- Isolated warm pass cost `C`: a trivial no-import consumer ran via `--run --no-auto-prepare` against the warm profile,
  interleaved with the same consumer using explicit sys-root/runtime inputs, seven pairs each under a pinned
  environment. Managed warm median 1.724 s (spread 0.075 s), explicit median 0.811 s (spread 0.044 s), giving `C` of
  0.913 s. Timings are local desktop measurements under ordinary contention, not CI predictions.
- Environment sensitivity: the native identity binds `toolchain.environment.PATH`; an invocation environment whose
  `PATH` differs from the profile's reports an identical warm request as a miss (`L1C-2159` under `--no-auto-prepare`).
  Phase 1 measured with `PATH` pinned to the cold-run value. Phase 4 measurement series must each pin one environment.
- Attribution caveat: `C` combines identity resolution, toolchain observation, the umbrella analysis and manifest
  validation, minus the explicit-input path costs, so it is an upper bound on the semantic-pass share. Separating that
  share is Phase 2/4 work. Operationalizing the Phase 5 pre-registered bar with this `C`: the reuse prototype must
  reduce `C` to at most 40 percent of 0.913 s (about 0.36 s) with non-overlapping medians over at least five interleaved
  pairs, while cold/miss, manifest-validation and trace-analysis budgets must not regress; a prototype that fails this
  bar retains the full pass, and the 500 ms floor remains the boundary below which persist-new-state complexity is not
  justified.

## Native Identity Re-evaluation Note

Phase 1 exposed that the native identity binds the raw `toolchain.environment.PATH` text (see
[preparation identity][preparation-identity]), so an identical warm request becomes a miss (`L1C-2159`) whenever the
invocation `PATH` differs, even when every resolved path, image digest and toolchain observation is unchanged. The
existing staleness machinery already re-validates directory snapshots and per-file digests on every command
(`pc_discovery_current`), so the environment text is defense in depth, not the primary correctness mechanism.

To reassess when Phase 4 measures the cost of environment pinning:

- Determine whether environment-induced misses recur in realistic development and CI invocation environments.
- Consider dropping `toolchain.environment` from the native key while retaining it in the observation-memo key (the
  `cwd` field already follows this memo-only pattern), or extending the explicit decline list for untracked behavioral
  variables (the existing `LD_PRELOAD` pattern).
- Any change here belongs to native identity (ADR-0039 territory), not to the semantic-validation evidence question this
  plan investigates. It requires its own falsification probes: a `PATH` reorder with unchanged observations must
  preserve reuse, while a newly shadowing file must still force re-observation.
- No identity change is authorized by this note; it records the reassessment obligation only.

## Verification Criteria For A Later Implementation

- Cold preparation, stale/missing evidence and every changed semantic input receive complete validation before a
  reusable success is accepted. Unimported bundled modules remain covered.
- Successful warm behavior is observationally equivalent for outputs, diagnostic codes and repair guidance. Any
  intentionally changed diagnostic ordering or contract requires an explicit documented decision first.
- Deterministic counts distinguish native cache reuse from semantic-validation reuse; tests do not use wall-clock
  thresholds. Timing evidence demonstrates a meaningful improvement after points 1 through 5.
- Ordinary semantic-only and compile-only imported-provider resolution retain their existing no-native-preparation
  boundary. Build/run and standalone link retain explicit input authority and final validation.
- Force, corruption, no-auto, unwritable cache, installed layout, interruption and concurrency regressions pass; absent
  evidence never makes compilation correctness depend on persistent writable state.
- Relevant preparation, identity, managed-provider and ownership tests pass, followed by L1 `make test-all` with the
  default trace coverage. Available-host results are reported without investigating unrelated platform failures.
- Stable docs describe only the accepted implemented behavior. Before closure, resolve every Pending ADR record,
  complete the required L1 ADR/index/backlink work, update the roadmap and run active/staged ADR and repository checks.

## Non-Goals

- Implementing a production validation change as part of the present test/build cost reduction.
- Repeating test-harness splitting, explicit runtime-input selection or support-compilation optimization from points 1
  through 5.
- Caching application analyses, expanding native toolchain eligibility, inferring ABI compatibility, partial-profile
  reuse, remote/shared caching, cache pruning or changing external-input mutation guarantees.
- Adding release, distribution, publication, remote-write or workflow-dispatch steps.
- Diagnosing failures on platforms owned by other concurrent work.

[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[identity-adr]: ../../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[preparation]: ../../../docs/reference/stdlib-preparation.md
[preparation-economy]: ../refactors/closed/2026-09-12-native-preparation-economy-noref.md
[preparation-identity]: ../../../compiler/stage1_l0/support/preparation/identity.h
[preparation-plan]: closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md
[semantic-adr]: ../../../docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md
[test-cost]: ../tools/closed/2026-09-13-preparation-test-cost-noref.md
