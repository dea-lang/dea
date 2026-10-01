# Feature Plan

## Create and consume explicit L1 profile artifacts

- Date: 2026-09-30
- Status: Draft
- Title: Add caller-owned L1 profiles with `--create-profile` and `--profile PATH`
- Kind: Feature
- Severity: Medium
- Stage: Shared
- Parent Initiative: `l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md`
- Targets:
  - L1 Stage 1: Pending
  - L1 Stage 2: Pending
- Subsystem: Explicit native support artifacts, CLI selection, compilation and linking
- Depends on: `l1/work/plans/refactors/closed/2026-09-30-profile-construction-boundary-noref.md`
- Modules:
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/cli_args/`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/src/preparation.l0`
  - `l1/compiler/stage1_l0/src/preparation/`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/compiler/stage1_l0/src/compile_driver.l0`
  - `l1/compiler/stage1_l0/src/compile_driver/`
  - `l1/compiler/stage1_l0/src/link_driver.l0`
  - `l1/compiler/stage1_l0/src/link_driver/`
  - Corresponding modules under `l1/compiler/stage2_l1/src/` with `.l1` suffixes.
  - `l1/compiler/stage1_l0/support/preparation_support.c`
  - `l1/compiler/stage1_l0/support/preparation/`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage2_l1/tests/cli_args_test.l1`
  - `l1/compiler/stage1_l0/tests/preparation_test.l0`
  - `l1/compiler/stage2_l1/tests/preparation_test.l1`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_managed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_installed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_profile_test.py` (proposed shared integration test).
  - `l1/compiler/stage1_l0/tests/profile_test.l0` (proposed implementation test).
  - `l1/compiler/stage2_l1/tests/profile_test.l1` (proposed paired implementation test).
  - Both stages' normal/trace runner registrations for the new coverage.
- Related:
  - [l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md][initiative]
  - [l1/work/plans/refactors/closed/2026-09-30-profile-construction-boundary-noref.md][boundary-plan]
  - [l1/docs/reference/stdlib-preparation.md][preparation]
  - [l1/docs/reference/separate-compilation.md][separate-compilation]
- Repro: The proposed explicit compilation sequence under Public CLI Contract.

## Summary

Introduce a complete caller-owned profile and use it without managed cache discovery or automatic preparation.
`--create-profile` is a primary mode that constructs the artifact at `-o PATH`. `--profile PATH` is a selector for
`--compile`, `--link`, `--build` and `--run`.

The initial implementation reuses the existing bundled semantic bootstrap, native constructor, per-module compiler and
verified linker. It does not make arbitrary stdlib projects, a compiler dependency scanner, a new cache format or a
Make-managed compiler build prerequisites.

This is an additive feature. Commands and artifact layouts described below are proposed, not available in the inspected
baseline. Ordinary commands without `--profile` preserve the current managed behavior.

## ADR Impact

- Decision: Publish a caller-owned profile independently of managed cache storage and consume an exact profile through a
  selector rather than a cache hint.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Public format, construction, lifetime, validation and strict selection need one durable artifact
    contract. Create the resulting ADR in `l1/docs/decisions/` and share it with the parent initiative. The shared CLI
    ADR amendment below remains separate.
- Decision: Define caller-managed external toolchain stability separately from managed freshness observation.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Explicit selection cannot promise automatic detection of external mutations while bypassing the
    observations that detect them. Clarify the opt-in responsibility without weakening managed reuse.
- Decision: Add explicit profile provider/header/runtime selection without changing ordinary bundled discovery.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md`
  - Rationale: The new opt-in authority replaces bundled discovery only when the user supplies a profile.
- Decision: Retain `.l1m` semantic authority and opaque native objects within profile-backed linking.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md`
  - Rationale: Payload checks detect damage but do not authenticate native semantics, inspect symbols or establish
    arbitrary cross-toolchain ABI compatibility.
- Decision: Extend the existing flag-based CLI with one L1 mode and one selector.
  - Scope: Shared
  - Disposition: Amend ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: Register the L1 extension in the shared CLI contract while preserving existing meanings and leaving L0's
    implementation unchanged.

## Current State and Gap

The proposal was drafted against `dea-lang/dea`, branch `main`, on 2026-09-30 and rechecked against the local worktree
on 2026-10-01. Recheck current sources before implementation.

`--prepare-stdlib` builds or reuses an eligible managed cache entry. Automatic consumers can fall back to fresh private
support when persistent reuse is ineligible. Compile-only already avoids native preparation for imported providers;
standalone linking may still trigger it. `--no-auto-prepare` disables construction, not identity observation or lookup.

The internal native profile already carries module pairs, runtime support and completion evidence. Public headers remain
separate toolchain inputs, and private cache layout/metadata are not a public artifact API. The new profile must supply
those required consumer inputs without exposing or depending on cache memos.

Current compile/link helpers collect `L1_CFLAGS` through `bd_collect_c_option_words`, select runtime defaults separately
and create managed preparation contexts. Bundled discovery also consults the original source directory. Explicit profile
selection must bypass those paths or supply their resolved inputs directly; filling existing CLI fields alone does not
establish configuration or source independence.

See [l1/docs/reference/stdlib-preparation.md][preparation] and
[l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][reuse-adr].

## Defaults Chosen

1. Use exactly `--create-profile` and `--profile PATH`. Do not add aliases, subcommands, profile registries or a new
   executable.
2. Create one complete native configuration and runtime variant per profile. Preserve the existing separate policies for
   generated stdlib C and runtime implementation C; do not forward arbitrary application flags into runtime sources.
3. Require a new, explicit output directory. Do not search the cache, overwrite an existing profile or implement
   in-place repair in the first version.
4. Preserve managed CLI controls and behavior. `--prepare-stdlib` remains managed prewarming, not an alias for
   `--create-profile`.
5. Treat explicit profiles as caller-stable inputs, with read-only consumption and no fallback. State the external
   toolchain responsibility rather than implying that a manifest makes mutable dependencies immutable.
6. Start with existing supported host/toolchain configurations. Separate invocability from persistent reuse eligibility,
   but do not turn unavailable capabilities into supported configurations.

## Public CLI Contract

After the feature is complete, the following sequence should work. `pkg.util` is independent of other application
modules, and `app` imports it. The source root contains the corresponding declared module names.

```sh
l1c --create-profile --c-compiler clang --check-basic -o build/profile

l1c --compile pkg.util --project-root src \
    --profile build/profile -I build/modules -o build/modules/pkg/util.o

l1c --compile app --project-root src \
    --profile build/profile -I build/modules -o build/modules/app.o

l1c --link build/modules/app.o -I build/modules \
    --profile build/profile -o build/app

l1c --build app --project-root src --profile build/profile -o build/app-direct
```

The commands are independent invocations, not steps hidden behind another mandatory driver.

### Creation

`--create-profile` accepts no program target and requires exactly one nonempty `-o`/`--output` destination. It uses the
canonical bundled semantic inputs and the existing preparation configuration surface: native compiler/options,
public-header selection, generated-C settings and checking/trace controls as applicable.

It rejects another primary mode, `--profile`, source/project/interface roots, runtime-library replacement, foreign/link
operands, program arguments, `--stdlib-cache`, `--no-auto-prepare`, `--force` and `--keep-c`. Cache-location environment
variables do not redirect it or cause cache access. Parent creation and path validation follow the repository's existing
safe filesystem helpers.

It constructs the requested artifact without cache lookup or persistent eligibility as an admission condition. A
configuration that can correctly build fresh private support may create an explicit profile even when automatic
persistent reuse cannot be established. Required compiler capabilities, option validation and stable input handling
still apply. Resolve the compiler family, runtime options and required construction tools separately from managed
identity observation. Missing optional freshness evidence must not become an indirect reuse-eligibility gate. In
particular, this feature does not independently add legacy Clang support.

Success is exit status 0 with the complete selected profile. CLI misuse uses status 2; construction, validation or
publication failure uses status 1. Human progress and native diagnostics go to stderr. No parseable success log is
required: the caller already knows the output path.

### Selection

`--profile PATH` accepts exactly one nonempty existing profile root. A relative path resolves against the invocation
working directory. It is valid only with compile, link, build and run in version 1; other modes can be considered later.

Selection reads the named artifact or fails. It never searches managed caches, calculates a managed selection key,
reconstructs DLL/compiler freshness evidence, prepares missing support, repairs the profile, chooses another profile or
writes profile/cache memos. Ordinary compiler execution, input validation and payload-integrity reads still occur.

Profile-owned configuration is authoritative. Restore its selected compiler and ordered effective native/codegen
configuration instead of reselecting defaults from `PATH`, `L1_CC` or `L1_CFLAGS`. Omitted runtime/codegen settings use
the profile's settings. Explicit conflicting settings fail before compilation; redundant explicit settings are accepted
only when ordinary normalization matches the recorded configuration, without probing alternate compiler identities.
Retain which CLI settings were supplied so omitted defaults are not mistaken for explicit conflicts. Initially lock the
complete preparation configuration rather than inventing a classifier for supposedly ABI-neutral flag differences.

Resolve the selected profile and settings once, then pass that configuration through frontend generation, module
compilation, wrapper compilation and final linking. Keep the separate generated-C and runtime policies and the existing
final-link operand contract. None of those consumers may recollect ambient C options, reselect a compiler or recover
runtime defaults after selection. Audit shared helpers and early preflight as well as the main mode dispatch.

Preserve project source selection and explicit `-I` provider precedence. The profile supplies the bundled provider tier
and exact runtime/header inputs. Determine bundled provider membership and paths from its validated inventory, without
checking for corresponding sources under the original installation. Missing profile providers fail; they never fall back
to the installation or managed cache. A differing explicit provider is still subject to existing fingerprint, graph and
lifecycle validation; an invalid selected explicit provider remains an error.

For the bounded first version, reject explicit `--sys-root`, `--runtime-include`, `--runtime-lib` and
`--no-managed-stdlib` with `--profile`. Ignore ambient system/runtime selection defaults, including `L1_SYSTEM`,
`L1_RUNTIME_INCLUDE`, `L1_RUNTIME_LIB` and runtime lookup through `L1_BUILD_DIR`, when the profile is selected. These
restrictions belong only to the new selector and do not change existing commands. Document them in the CLI help instead
of silently mixing two system environments.

Explicit `--stdlib-cache` with `--profile` is an error. Ambient cache variables are ignored. In build/run/link,
`--no-auto-prepare` is accepted as redundant and does not trigger a cache check. Existing mode-scoping still rejects
that flag in compile-only mode. Final-link operands and `--entry` retain their existing mode-specific meanings.

## Profile Artifact Contract

### Required contents

Use a dedicated versioned public manifest, provisionally named `profile.json`, with a payload layout such as:

```text
profile/
    profile.json
    include/
        dea_rt.h
        l1_real.h
    modules/
        std/io.l1m
        std/io.o
        ...
    runtime/
        <the selected variant's archive or declared TinyCC object set>
```

Preserve sibling `.o + .l1m` association. Copy the complete public-header dependency set needed by generated C and the
wrapper, not just two filenames if that set changes. Keep all payload references relative to the profile root. Runtime
input roles and order must support the existing TinyCC raw-object distinction without generalizing it into a new public
arbitrary-runtime-object feature.

The manifest declares its format version, an explicitly maintained Dea compilation-contract version, producer
information, selected native configuration, runtime variant, generated-C options, separate runtime build options,
selected compiler invocation path and family, module inventory and payload paths/sizes/digests. Explicit target settings
are configuration. Observed target, compiler version and component descriptions are separate optional provenance, which
may be unavailable for an invocable configuration whose managed reuse is refused. Do not invent observations or require
managed discovery to populate them.

Both compiler stages support the same contract version. A matching version declares a supported Dea interface/runtime
protocol, not proof of native ABI compatibility. Phase 1 must define which incompatible interface, code-generation,
header/runtime and lifecycle changes require a contract-version bump and how both stages reject unsupported versions.
Producer provenance and managed content identities are not substitutes for that maintenance rule.

The final field spelling, required/optional distinction and serialization limits are a Phase 1 deliverable. The manifest
is data, not a shell program: store argument arrays, not executable command strings. Do not embed an unrestricted
environment dump or credentials. Do not export cache keys, lock paths, memo paths or optional scratch as consumption
authority.

Phase 1 must also define how relative path-bearing native options and response/configuration files retain their meaning
between creation and consumption, including changes of working directory. Distinguish rebased profile-owned paths from
caller-maintained external inputs and record any required directory assumptions. Settle supported normalization and
explicit rejection rules before enabling creation; do not silently reinterpret stored arguments against a different cwd
or claim that recording argv freezes referenced files.

### Ownership, publication and local movement

The creator owns only its new output and registered sibling staging area. Reject an existing output, unsafe final path
or overlap with protected inputs/installation payload before mutation. Build into an exclusively created sibling staging
directory, validate its complete payload, write completion metadata last and publish to the absent destination. Use
existing filesystem primitives and the trusted-parent/external-serialization boundary.

A recoverable failure must not leave a usable-looking partial profile or alter an existing destination. Cleanup removes
only registered owned contents; unexpected files or cleanup failure retain evidence and report the location. Do not
promise concurrent same-destination writers, hostile-parent safety, crash durability or a general atomic replacement
API. `--force` does not override these rules.

After success, consumers never modify the profile. To change it, create a new destination and select that explicitly. Do
not use mutable hard-linked source/header inputs as if they were frozen payload copies.

The profile should remain usable after moving/copying its directory on the same host with the selected external
toolchain unchanged. Consumption must not require the creating cache or original bundled source location. This is not a
cross-host distribution, cross-compiler compatibility or toolchain relocation guarantee.

### Validation and external stability

At creation, verify completeness, native build success, all interface identities/fingerprints, header/runtime selection
and payload digests. At consumption, validate schema, supported contract version, path containment, declared inventory
and configuration before invoking host tools. Verify the bytes actually consumed: compile-only need not hash unused
native provider objects; linking validates selected provider payloads and runtime/header inputs. Always perform existing
`.l1m` semantic verification and graph/lifecycle checks.

Do not reconstruct current installed source identity or external compiler/DLL identity merely to select an explicit
profile. The user is responsible for keeping the chosen compiler, SDK, environment and other external native inputs
suitable and stable, and for rebuilding the profile when those assumptions change. Using an absolute compiler path
prevents accidental `PATH` reselection; it does not freeze that executable or its dependencies.

This opt-in responsibility is intentionally different from managed automatic reuse. Document it at the selector and
artifact contracts, not only in a warning buried in implementation notes. A changed toolchain may require explicit
recreation even when cheap manifest checks still pass. Do not silently advertise automatic freshness for this path.

Hashes detect payload inconsistency relative to a trusted manifest. They do not authenticate an untrusted profile,
inspect native symbols, prove object/interface semantic agreement or turn foreign-code preconditions into safe code.
Retain [l1/docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md][native-adr].

## Composition and Retained C

Keep the verified linker responsible for entry selection, provider completion, lifecycle order, wrapper generation,
wrapper compilation and the native link. There is no `--emit-wrapper` prerequisite.

Profile modules are prebuilt providers. In the first version, `--keep-c` retains only C actually generated by that
consumer and its wrapper, just as for other explicit interface/object providers. Profile consumption does not recompile
bundled modules or regenerate their C from current installation sources. The public profile need not retain generated C.

Compare module-C identity under identical resolved inputs and options; do not promise equal retained-file inventories
between a managed build that regenerates bundled C and an explicit build that consumes prebuilt providers. Preserve the
existing no-profile retention contract and [l1/docs/decisions/0035-cross-mode-generated-c-byte-identity.md][byte-adr].

## Implementation Phases

### Phase 1: Freeze the smallest public contract

Build on the completed prerequisite
[l1/work/plans/refactors/closed/2026-09-30-profile-construction-boundary-noref.md][boundary-plan]. Specify manifest
fields/limits, configuration precedence, authority order, diagnostic meanings and publication/lifetime rules before
enabling new commands. Audit public-header dependencies and runtime variants. Recheck diagnostic availability and
proposed filenames against the live repository.

Keep producer provenance, payload integrity, Dea protocol compatibility and external freshness as separate concepts.
Freeze required versus optional manifest fields, compatibility-version bump rules, bounded reader behavior and the
working-directory/path policy for native options and response/configuration files. Write the CLI scope table, redundant
setting normalization and caller-stability contract. Specify creation/publication ownership on every failure path. No
inherited managed key may be mistaken for a permanent compatibility certificate.

Exit gate: the contract is implementable with the extracted constructor and existing compile/link machinery. Record the
settled representation decisions in this plan; do not enable new commands with unresolved manifest, compatibility,
relative-path, trust or overwrite semantics. These are feature-phase deliverables, not prerequisites for starting the
construction-boundary refactor.

### Phase 2: Deliver creation plus explicit-profile linking

Add `--create-profile` and `--link --profile`. Initially produce application objects with the existing compile-only path
and matching explicit configuration, then link them using the created profile. Use one supported GCC or modern Clang
installation for the first vertical test and add other supported cases before final closure.

Choose the explicit-provider path before constructing a managed preparation context. Validate the profile, obtain its
provider/header/runtime configuration and run the existing verified linker. Read bundled membership from the profile
inventory, with no original-source existence probe. Prove that a missing/corrupt selected profile fails even when a
valid managed cache is available.

Exit gate: a native executable is constructed through the explicit artifact; no managed resolve/find/lock/prepare
operation occurs during its link. Creation succeeds for a tested invocable configuration whose persistent reuse is
refused, without changing that refusal in the managed path.

### Phase 3: Extend selection to compile, build and run

Teach compile-only to obtain interfaces, headers and locked native/codegen settings from the profile. It still produces
one ordinary `.o + .l1m` pair and never compiles imported providers. Route frontend and host-tool helpers through the
resolved configuration, including their early preflight checks. Preserve compile-only endpoint rollback.

Pass the same explicit support selection through the existing build/run graph and link operations. Avoid managed
materialization and retain no-profile behavior. Keep source-graph analysis, per-node one-module compilation, entry
selection, foreign operands and output/run lifecycle unchanged.

Exit gate: the public sequence above works through both stages, including read-only profile consumption and runtime
variant inheritance. Stage 1 consumes Stage 2-created profiles and Stage 2 consumes Stage 1-created profiles under the
same supported native configuration. Preserve Stage 2's reviewed L1 idioms while implementing paired behavior. Help
reports only implemented mode combinations at each intermediate landing.

### Phase 4: Prove manual composition without adding a build system

Create a small fixture with a leaf module, a dependent module, an entry module, a bundled import and a C shim supplied
through the existing foreign-object surface. Use a fixed declared order in a test script to create one profile, compile
the modules, link and run. A fixed fixture order is not an application dependency-discovery implementation.

Compare this with `--build --profile` and the ordinary managed path using equivalent configurations. Check behavior,
diagnostics for focused invalid cases, lifecycle order and applicable generated-C bytes. No native byte-identity
requirement is introduced beyond the existing supported bootstrap policy.

Exit gate: the same constructor/compiler/linker implementations support manual and convenient composition. No copied
frontend, import parser, cache-key calculator or wrapper generator appears in the external script.

### Phase 5: Complete validation, documentation and closure

Run the matrix below through Stage 1 and Stage 2. Register shared compiler-facing integration tests through the explicit
subject-compiler mechanism. Use focused tests during implementation, then the required aggregate/trace suites and strict
bootstrap for closure. Record actual supported native compiler paths/versions and coverage gaps.

Update the shared CLI and diagnostic catalogs, L1 preparation and separate-compilation references, architecture, help
and roadmap in the same relevant implementation changes. Write the exact profile specification under `l1/docs/` when
implemented; do not turn this draft into a current-state reference prematurely.

Resolve ADR Impact, create/index the L1 profile ADR shared with the parent initiative, amend the named L1 ADRs and the
separate shared CLI ADR, and update Related Plans links. Close this feature without waiting for general dependency
discovery or Make conversion; the parent initiative remains active until all four of its phases are implemented.

## Verification Criteria

| Area                  | Required cases                                                                                                                                                                                                                                                                                |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CLI                   | Missing/repeated selector, missing output, incompatible modes/flags, empty paths, inherited settings, normalized redundant settings and conflicting explicit settings rejected before native work.                                                                                            |
| Creation              | Complete canonical set, default/basic/unchecked/traced configurations, correct separate runtime policy, supported compiler capabilities and invocable-but-reuse-ineligible construction.                                                                                                      |
| Selection             | Exact root, no cache fallback, no implicit repair, missing/incomplete/corrupt/unknown-version profiles, provider precedence and profile-configuration mismatch.                                                                                                                               |
| No hidden preparation | Instrumented absence of managed identity discovery, cache lookup/locks, native-support construction and persistent memo writes after explicit selection. Ordinary host compilation is allowed.                                                                                                |
| Profile independence  | Read-only profile; invalid/unavailable cache; changed ambient `L1_CC`/`L1_CFLAGS` and system/runtime defaults across compile/link/build/run; consume a moved/copied profile with original bundled sources, interfaces and headers unavailable.                                                |
| Native option paths   | Relative include/sysroot options and response/configuration files, changed cwd and moved profile follow the frozen Phase 1 rules, including explicit rejection of unsupported forms.                                                                                                          |
| Safety and ownership  | Existing output rejection, path escape/alias/overlap rejection, injected construction/publication failures, retained unexpected scratch and caller-owned input preservation.                                                                                                                  |
| Compiler semantics    | Interface verification, imported-provider requirements, entry/lifecycle checks, foreign inputs, float-option restrictions, compile rollback and retained-C rules.                                                                                                                             |
| Compatibility         | Stage 1-created profiles consumed by Stage 2 and Stage 2-created profiles consumed by Stage 1 under the same native configuration; unsupported contract versions rejected; GCC/Clang and TinyCC runtime shapes on applicable supported hosts without inventing cross-toolchain compatibility. |
| Regression            | Existing explicit prewarming, force, cold/warm managed requests, no-auto-prepare refusal, corruption/private fallback and current cache-location behavior still pass.                                                                                                                         |

Payload hashing is not prohibited. Record its scope and cost separately from external toolchain identity work. Add no
new persistent validation memo to make the first implementation appear cheap. Measure before considering such an
optimization.

From `l1/`, use applicable focused tests, `make test-extended`, relevant ownership cases through both
`test-stage1-trace` and `test-stage2-trace`, and `make triple-test`. Explicitly select
`TESTS="l1c_stage1_preparation_test l1c_stage1_installed_preparation_test"` with each of `make test-stage1` and
`make test-stage2`; these shared integration cases are CI-only in normal discovery. Use `make test-ci` for exhaustive
hosted-equivalent coverage, reusing already completed applicable validation under the repository rules.

Exercise the repo-owned Linux Docker path with GCC. Follow [l1/AGENTS.md][l1-agents] for supported-host and
native-compiler selection. Report unavailable platforms honestly. A deliberately failed persistent-reuse observation is
not evidence that an unsupported compiler has become supported.

## Diagnostic-Code Planning

Profiles add a new driver/artifact category. Provisionally reserve `L1C-2180` through `L1C-2199`, which are not
registered in the inspected [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]. Do not reuse retired or
reserved link codes, or consume the existing bundled-preparation reservation merely because the code paths are nearby.

Suggested initial assignments are `L1C-2180` for profile-specific CLI/configuration conflicts, `L1C-2181` for an invalid
creation destination, `L1C-2182` for an unreadable/incomplete/unsupported manifest, `L1C-2183` for invalid payload
inventory/paths/integrity, `L1C-2184` for a declared contract/configuration mismatch, and `L1C-2185` for profile
publication/cleanup failure. Use established generic CLI, semantic and native-compilation diagnostics where those
meanings already apply; avoid duplicate fallback errors after a specific cause.

These numbers are planning reservations only. Recheck the live catalog and other active reservations before assigning or
implementing them; choose another unused block of 20 if they have been taken. Update registered meanings and phase
help/tests in the same implementation changes. Stage 2 reuses the same codes and meanings.

## Non-Goals and Migration Boundaries

No `--deps`, `--depfile`, serialized native-command plan, public wrapper mode, general JSON stdlib API, new package
format, profile cache selector, cache export/eviction service or new build executable is included. Profile selection in
`--check`, `--gen` and `--emit-interface` remains outside this plan.

Do not rename or remove `--prepare-stdlib`, `--stdlib-cache`, `L1_STDLIB_CACHE`, `--no-auto-prepare` or `--force`. The
managed-cache client refactor belongs to the later initiative phase; it must not become a condition for accepting this
additive explicit path. Do not accept the legacy private cache layout as a public profile accidentally.

No release/distribution workflow or automatic cross-host reuse is promised. Do not relax managed identity, provenance,
metadata or hashing policy. Production compiler Make conversion and ordinary-project stdlib construction remain later
work.

## Planning and Authorization

Keep initiative membership and roadmap links synchronized. Run `python3 scripts/check_adr_impact.py --all-active` during
planning, and staged ADR/whitespace plus required root pre-commit checks before implementation commits. No completed
verification is claimed by this draft.

This plan authorizes no remote operation. Pushes, releases, tags, hosted workflow dispatches and deployment require
separate fresh approval under the repository's authorization rules.

[boundary-plan]: ../refactors/closed/2026-09-30-profile-construction-boundary-noref.md
[byte-adr]: ../../../docs/decisions/0035-cross-mode-generated-c-byte-identity.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[initiative]: ../../initiatives/0010-explicit-profiles-and-composable-builds.md
[l1-agents]: ../../../AGENTS.md
[native-adr]: ../../../docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md
[preparation]: ../../../docs/reference/stdlib-preparation.md
[reuse-adr]: ../../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[separate-compilation]: ../../../docs/reference/separate-compilation.md
