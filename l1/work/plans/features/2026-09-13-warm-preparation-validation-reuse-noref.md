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
   requirement that contradicts the current architecture.
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
2. Audit validation dependencies and observable diagnostics. Trace the preparation state transitions and compare the
   existing manifest, identity and memo schemas with the evidence each candidate would require.
3. Build isolated falsification probes for the candidates' safety claims. Keep production semantics unchanged during the
   investigation and document counterexamples as reasons to reject or narrow a candidate.
4. Measure viable prototypes with repeated interleaved runs on Intel Mac when available. Separate native resolution,
   bundled analysis, manifest/artifact validation and application compilation. Report medians and spread, plus trace
   execution and analysis time, event count, trace bytes and peak memory. Keep raw logs temporary; retain a concise
   evidence report if needed.
5. Select the justified outcome: retain the present contract, preserve it with proven validation reuse, or propose an
   explicit contract amendment. Resolve both ADR questions and specify compatibility, documentation and regression
   coverage. Any implementation proceeds as later authorized work, with this draft updated to the settled design.

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
[preparation-plan]: closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md
[semantic-adr]: ../../../docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md
[test-cost]: ../tools/closed/2026-09-13-preparation-test-cost-noref.md
