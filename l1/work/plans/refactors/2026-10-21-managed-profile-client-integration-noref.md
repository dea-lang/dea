# Refactor Plan

## Integrate managed preparation with the shared profile model

- Date: 2026-10-21
- Status: Draft
- Title: Make managed preparation a client of shared profile configuration and payload validation
- Kind: Refactor
- Parent Initiative: `l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md`
- Priority: Medium
- Subsystem: Native preparation, profile construction, payload validation and managed cache policy
- Modules:
  - `l1/compiler/src/preparation.l0`
  - `l1/compiler/src/preparation/frontend.l0`
  - `l1/compiler/src/preparation/consumer.l0`
  - `l1/compiler/support/preparation_support.c`
  - `l1/compiler/support/preparation/construction.h`
  - `l1/compiler/support/preparation/profile.h`
  - `l1/compiler/support/preparation/storage.h`
  - `l1/compiler/support/preparation/identity.h`
  - `l1/compiler/support/preparation/build.h`
- Test modules:
  - `l1/compiler/tests/preparation_construction_test.py`
  - `l1/compiler/tests/preparation_support_test.py`
  - `l1/compiler/tests/preparation_identity_test.py`
  - `l1/compiler/tests/preparation_ownership_test.py`
  - `l1/compiler/tests/preparation_clang_compatibility_test.py`
  - `l1/compiler/tests/preparation_profile_test.py`
  - `l1/compiler/tests/preparation_test.l0`
  - `l1/compiler/tests/fixtures/preparation/construction.l0`
  - `l1/compiler/tests/l1c_preparation_test.py`
  - `l1/compiler/tests/l1c_managed_preparation_test.py`
  - `l1/compiler/tests/l1c_profile_test.py`
  - `l1/compiler/tests/l1c_profile_variants_test.py`
  - `l1/compiler/tests/l1c_installed_preparation_test.py`
- Related:
  - [l1/work/plans/refactors/closed/2026-09-30-profile-construction-boundary-noref.md][boundary-plan]
  - [l1/work/plans/features/closed/2026-09-30-explicit-profile-artifacts-noref.md][profile-plan]
  - [l1/work/plans/bug-fixes/closed/2026-10-19-explicit-profile-review-gaps-noref.md][profile-review]
  - [l1/docs/reference/stdlib-preparation.md][preparation]
  - [l1/docs/reference/explicit-profiles.md][profiles]
- Repro: From `l1/`, run
  `make test-compiler TESTS="preparation_construction_test preparation_profile_test l1c_managed_preparation_test l1c_profile_test"`
  with explicit supported bootstrap and native compiler selections.

## Summary

Complete Phase C of [l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md][initiative] by making managed
and command-private preparation use the same frozen configuration projection and payload-validation primitives as
explicit profile construction. Keep policy adapters for managed freshness and storage versus caller-owned explicit
artifacts. This is a bounded internal refactor with unchanged CLI, cache formats, provider authority and failure policy.
Medium priority reflects the next composability milestone without making unrelated stdlib work depend on it.

## ADR Impact

- Decision: Share profile construction inputs and payload validation while retaining separate public and managed
  authority.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0044-explicit-profile-artifact-authority.md`
  - Rationale: Record the delivered managed-client boundary without changing exact, read-only explicit selection or the
    public artifact format.
- Decision: Retain observed managed identity, conservative reuse admission and disposable memo policy.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Shared artifact code cannot make an explicit success evidence of managed freshness or weaken existing
    toolchain observation.
- Decision: Preserve manifest-certified warm semantic validation and full validation on every construction path.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0040-warm-preparation-semantic-validation-reuse.md`
  - Rationale: Moving validation must preserve the existing warm short circuit and miss, force, private-fallback and
    failure classifications.

## Current State and Remaining Gap

The October 20 primary checkout implements Phases A and B. `pr_construct` and `pc_begin_construction` /
`pc_finish_construction` already serve managed, command-private and explicit creation. Repeating that extraction or
wrapping an existing entrypoint alone does not complete Phase C.

Configuration projection still has separate assembly in `pc_managed_construction_inputs` in `preparation_support.c` and
the explicit creation path in `profile.h`. Managed completion/inventory validation in `pc_validate_entry_manifest` and
public validation in `pc_profile_payloads` repeat payload mechanics while enforcing different authority rules.
`pc_payload_artifacts` already supplies common module/runtime role expectations.

Managed schema-1 `manifest.json` binds `D`, `N`, identity and exact selected semantic bytes; warm validation may reuse
reliable artifact metadata. Its headers remain selected toolchain inputs. Public schema-1 `profile.json` additionally
records the Dea contract, frozen configuration and copied headers; consumers use its inventory without the original
bundled inputs or managed observations. These schemas and physical inventories are not interchangeable.

The closed review corrections preserve explicit response/configuration refusal, normalized argument bounds and Windows
fixture behavior. Native CI validation of the complete correction passed on Windows UCRT64 and macOS ARM, as recorded in
[l1/work/plans/bug-fixes/closed/2026-10-19-explicit-profile-review-gaps-noref.md][profile-review]. This establishes the
corrected Phase B baseline; Phase C changes require their own scoped validation.

## Scope and Defaults Chosen

1. Use one internal frozen construction description and one shared set of payload mechanics, with explicit policy
   inputs. Reuse existing records and helpers where sufficient; choose any minimal extraction during the initial
   inventory rather than introducing a general artifact framework.
2. Resolve configuration under the originating policy, then project selected compiler/archiver, ordered generated-C
   options, separate runtime options/isolation, variant, codegen, semantic/source inputs and header inputs once. The
   constructor must not reread ambient defaults. Preserve option order and cwd semantics.
3. Do not route managed preparation through `l1c_profile_create`, `l1c_profile_load` or the public option whitelist.
   Managed response/configuration handling, legacy Clang isolation and invocable-but-persistently-ineligible fallback
   retain their existing rules. Explicit creation/selection retain their stricter refusal and frozen-path rules.
4. Share expected-role, duplicate/path/containment, regular-file, size/digest and semantic-copy mechanics where their
   contracts coincide. Keep schema parsing, public-tree/header completeness, hash selection, memo access, error mapping
   and freshness admission in their policy adapters. No permissive common mode may weaken either caller.
5. Preserve `<CACHE_ROOT>/v1/`, managed `manifest.json`, `.manifest.pending`, lock and memo formats and layout. The
   managed adapter may translate its existing inventory into the common description; it need not publish `profile.json`,
   copy public headers into entries or make a cache directory directly selectable with `--profile`.
6. Keep `pr_prepare` responsible for identity, lookup, complete miss validation, eligibility, lock/recheck, force and
   fallback. Keep managed completion responsible for input freshness, completion-marker publication and recovery.
   Preserve one native context per consuming command and existing semantic provider origins.
7. Preserve ownership: the constructor borrows an owned destination; callers own publication, failure evidence and
   eventual cleanup. Command-private support outlives its final compiler/linker consumer. Explicit payloads remain
   read-only, with current output/temp overlap refusal and no managed writes or fallback.

Changing compiler/source bytes legitimately changes content-derived `D` and `N`. Preserve their derivation and input
coverage, not literal keys across compiler revisions. Leave older entries untouched; no migration, relabeling, pruning
or new compatibility claim is part of this refactor.

## Implementation Phases

### Phase 1: Pin the two adapters and their observable contracts

Recheck the named call sites and record which configuration, payload checks and error decisions are common versus
policy-owned. Capture cold, warm, forced, private-fallback and explicit-consumer behavior with the same supported native
toolchain. Extend existing fixtures only where the proposed boundary lacks an observable assertion.

Exit gate: specify the shared inputs/results, ownership and error mapping without a CLI/schema change. Include a managed
configuration accepted under current policy but refused by explicit creation, and a public-profile case with poisoned
ambient defaults. These prevent accidental policy unification.

### Phase 2: Share frozen configuration projection and construction results

Extract the minimal common projection used after managed resolution or explicit creation policy has selected inputs.
Route both through it and the existing constructor. Keep resolved runtime isolation stable without retaining owned
temporary config paths; direct construction must survive release of the original resolution context.

Exit gate: direct, managed and explicit construction use the same projection/constructor implementation for equivalent
inputs. Verify ordered generated/runtime argv, semantic copies, runtime variant and ownership. Freeing a description
must not delete a caller-owned destination; failure must not produce a valid completion marker.

### Phase 3: Share payload mechanics and integrate managed consumption

Factor common inventory/file validation out of the managed and public implementations. Use policy adapters for expected
semantic digests, metadata-assisted hashing, native-payload requirements, copied headers/public tree and diagnostics.
Retain the managed reader's absent/incomplete/corrupt distinction and lock-time recheck. A manifest-certified warm hit
must not enter construction, repeat complete bundled frontend validation or copy/hash unrelated public-header payloads.

Keep explicit compile-only's complete inventory requirement while skipping unused native object hashing; link/build/run
retain native integrity validation. Preserve managed full verification versus memo-assisted warm checks, and populate
disposable memos only after successful checks. Keep explicit consumers independent of every managed resolve/find/lock/
prepare operation.

Exit gate: both adapters demonstrably call common payload mechanics, while counterexamples retain their respective
acceptance, refusal, diagnostic and cleanup behavior. A common helper existing without both call paths using it is not
completion.

Inject an incomplete or malformed constructed inventory and require both callers to refuse completion/publication,
retaining their respective failure evidence and diagnostic policy.

### Phase 4: Validate, document and close Phase C

Run the focused gates below, broaden only for changed paths or unresolved failures, and record supported compiler
executables/versions and platform gaps. Update the internal construction/validation description in
[l1/docs/reference/stdlib-preparation.md][preparation] and [l1/docs/reference/architecture.md][architecture]; update the
explicit reference only where shared implementation facts change. Do not describe new managed freshness or public
artifact guarantees.

Amend ADR-0044 and update the named ADRs' Related Plans links when closing this plan. Move it to `refactors/closed/`,
update initiative membership and roadmap links/version, and leave Initiative 0010 active for Phase D. No dependency
scanner, cache locator or production Make conversion is needed for Phase C acceptance.

## Verification Criteria

| Scenario                          | Required observation                                                                                                                                                                                                                    |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shared implementation             | Both policy adapters use the same configuration projection, constructor and common payload checks; policy-only operations stay outside them.                                                                                            |
| Managed cold, force and warm      | Full bundled validation on construction paths; zero bundled re-analysis and native preparation compilation/build commands on an unchanged warm hit. No repeated native resolution per command.                                          |
| Managed identity and admission    | Runtime/header/semantic/toolchain changes invalidate as before; memo absence, corruption or unreliable metadata cannot authorize reuse. Legacy configuration selection remains freshly observed.                                        |
| Ineligible or unavailable storage | Explicit prewarm refusal, implicit-root fallback, explicit-root errors and `--no-auto-prepare` refusal retain their current distinctions.                                                                                               |
| Corruption and coordination       | Missing/pending manifests remain incomplete; completed corruption retains diagnostics/recovery guidance. Same-key locking, recheck, interruption and force publication do not expose a success marker early.                            |
| Payload falsification             | Duplicate or wrong roles, missing/extra inventory entries, changed semantic bytes, nonregular files, escaping paths, size/digest mismatch and unstable reads fail under each adapter's contract.                                        |
| Explicit selection isolation      | Poisoned ambient/cache settings, moved read-only profiles and unavailable original bundled inputs retain exact selection without managed activity. Compile-only and native consumers retain their distinct hash requirements.           |
| Consumer behavior                 | Existing provider precedence, lifecycle order, runtime overrides and applicable retained-C identity match equivalent managed/manual/explicit composition. Do not require identical native executables or identical scratch inventories. |
| Native variants and ownership     | Default, basic, unchecked and traced variants retain separate generated/runtime policy; GCC, supported Clang isolation and TinyCC archive/raw-object behavior remain covered. No leaked context, scratch, lock or private support.      |
| Portable paths                    | Exercise host-native separators plus simulated Windows drive/UNC, mixed separators, spaces and genuinely different-path negatives without normalizing away canonical manifest or security behavior.                                     |

From `l1/`, select an explicit `L1_BOOTSTRAP_L0C` and supported `L0_CC`, `L1_CC`, `L1_RUNTIME_CC` before these focused
implementation checks:

```sh
make test-compiler TESTS="preparation_test preparation_construction_test preparation_support_test preparation_identity_test preparation_ownership_test preparation_clang_compatibility_test preparation_profile_test"
make test-compiler TESTS="l1c_preparation_test l1c_managed_preparation_test l1c_profile_test l1c_profile_variants_test l1c_installed_preparation_test"
make test-compiler-trace TESTS="preparation_test"
```

Explicitly select integration cases even when normal discovery excludes them. Run `make test-extended` when the final
diff spans the preparation/consumer pipeline, plus affected child/environment/trace gates when applicable. Use
`make test-ci` only when exhaustive coverage is warranted by the final changes; do not repeat already covered gates
without a reason. Canonical L1 has no stage parity or triple-bootstrap gate.

When constructor ownership changes, exercise its success/failure fixture with `L1_CONSTRUCTION_TRACE=1` and inspect
cleanup alongside the focused preparation trace.

Exercise the repo-owned Linux GCC path and supported macOS/Windows native paths for affected code. Distinguish native
execution, portable simulations and reused evidence, recording unavailable coverage explicitly. Compare attributed
cold/warm work counts and interleaved timings when the refactor changes validation work; investigate unexplained
regressions without claiming an unmeasured speedup or requiring literal cache-key stability.

## Diagnostic-Code Planning

No diagnostic code or meaning change is expected. Preserve managed `L1C-2150` through `L1C-2159` and explicit-profile
`L1C-2180` through `L1C-2185`, including existing consumer classification and error precedence. Shared validation must
return enough cause information for the originating adapter to retain those meanings, rather than leaking public profile
errors into managed commands. No new block is reserved. Recheck
[docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] during implementation; an unexpectedly necessary
diagnostic requires explicit planning in the established area before assignment.

## Non-Goals

- New CLI modes, aliases, profile export/locator commands, cache schemas, public manifest/contract versions or cache
  migration.
- Changed toolchain eligibility, native option acceptance, observation/memo/hash policy, new hashing backends or
  performance experiments.
- Phase D graph/depfile interfaces, a build-plan language, package management or production compiler Make conversion.
- L0/L2 implementation changes, L2 profile adoption, a new bootstrap seed, cross-host profile distribution or broader
  ABI guarantees.
- Changed source/interface authority, language/runtime semantics, native object inspection or delivery/release work.

[architecture]: ../../../docs/reference/architecture.md
[boundary-plan]: closed/2026-09-30-profile-construction-boundary-noref.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[initiative]: ../../initiatives/0010-explicit-profiles-and-composable-builds.md
[preparation]: ../../../docs/reference/stdlib-preparation.md
[profile-plan]: ../features/closed/2026-09-30-explicit-profile-artifacts-noref.md
[profile-review]: ../bug-fixes/closed/2026-10-19-explicit-profile-review-gaps-noref.md
[profiles]: ../../../docs/reference/explicit-profiles.md
