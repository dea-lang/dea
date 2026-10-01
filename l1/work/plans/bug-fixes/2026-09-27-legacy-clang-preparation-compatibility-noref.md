# Bug Fix Plan

## Safe legacy Clang compatibility and persistent preparation

- Date: 2026-09-27
- Status: Draft
- Title: Support legacy Clang preparation with verified configuration isolation and safe persistent reuse
- Kind: Bug Fix
- Severity: Medium
- Stage: 1
- Subsystem: Native preparation / Clang configuration discovery / identity and invalidation
- Modules:
  - `l1/compiler/stage1_l0/support/preparation/identity.h`
  - `l1/compiler/stage1_l0/support/preparation/storage.h`
  - `l1/compiler/stage1_l0/support/preparation/build.h`
  - `l1/compiler/stage1_l0/support/preparation_support.c`
  - `l1/compiler/stage1_l0/src/preparation.l0`
  - `l1/scripts/check_preparation_reuse.py`
- Test modules:
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_support_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_ownership_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_reuse_report_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_managed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_identity_windows_environment_test.py`
- Related:
  - [l1/docs/reference/stdlib-preparation.md][preparation-contract]
  - [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][identity-adr]
  - [l1/work/plans/features/2026-09-24-preparation-reuse-efficiency-noref.md][reuse-investigation]
  - [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/relaxed-toolchain/results.md][phase-three]
  - [l1/work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md][preparation-economy]
  - [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]
- Repro: In the retained Debian Bookworm builder, `clang --no-default-config -print-prog-name=ar` rejects the option;
  plain managed preparation reports `L1C-2154` despite an installed archiver.

## Summary

Support ordinary L1 compilation and persistent stdlib/runtime preparation with validated Clang 14 and 15 installations.
Use the legacy explicit-empty-config mechanism only after proving configuration isolation, discovery, identity, and
invalidation. Preserve command-private preparation for configurations that remain compilable but cannot safely authorize
reuse. Successful legacy persistent preparation is an acceptance requirement, not an optional follow-up.

This is a standalone L1 bug fix related to the preparation reuse investigation. It does not reopen completed
experiments. The document is a draft: its compatibility probes, implementation, and acceptance tests remain future work.

Until support is implemented and documented, full L1 support with upstream Clang requires version 16 or newer. Normal
agent builds, tests, benchmarks, and experiments must use supported GCC or modern Clang. The isolated legacy validation
in this plan is the explicit exception; its initial probes do not establish full support. At successful implementation,
update the interim requirements in `l1/README.md` and `l1/AGENTS.md` to reflect only the validated compatibility scope.

## ADR Impact

- Decision: Authorize legacy Clang persistent preparation using verified configuration isolation and fresh
  configuration-selection evidence.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Extend the documented adapter boundary with the legacy isolation mechanism and its configuration
    reobservation requirement, while preserving content-based identity and private fallback for insufficient evidence.

## Current State and Evidence

The retained [Phase 3 validation record][phase-three] reports that Debian Clang 14 rejects `--no-default-config`,
causing runtime archiver discovery to fail even though `ar` exists. L1 observes application configuration, extracts
supported target settings, and adds this option to prevent arbitrary application configuration flags from being reloaded
into compiler-owned runtime compilation. Both persistent and private builds use those runtime words; changing cache
policy alone cannot repair the failure.

LLVM [introduced the option][option-review] on September 16, 2022, and lists it among the new flags in the
[Clang 16 release notes][clang-release]. Upstream Clang 15 also lacks it. This establishes the option's upstream release
boundary, not a complete L1 compiler-support matrix; distribution backports and Apple Clang numbering require capability
checks rather than version-only selection.

The [Clang 14 driver][clang-fourteen] and [Clang 15 driver][clang-fifteen] load an explicit configuration path before
implicit configuration searching. A compiler-owned empty regular file supplied with the separate `--config PATH`
spelling is therefore a candidate isolation mechanism. Source inspection is not proof of successful L1 integration.

## Phase 1: Validate the Compatibility Mechanism

Use isolated Linux validation environments with real Clang 14 and 15, plus Clang 19 as the modern control. Record exact
versions, package provenance, commands, and outcomes. Keep validation tooling separate from measured historical images.

Establish that:

- Legacy compilers reject `--no-default-config` and accept `--config /absolute/path/to/empty.cfg`.
- An explicit empty regular file suppresses implicit configuration loading, including configuration selected through
  target-prefixed compiler aliases. Use an owned fixture with detectable application-only flags.
- Original configuration selection is observable, including explicit and implicit files, nested response inputs, search
  precedence, and target-dependent selection.
- Runtime commands preserve supported target/CPU/ABI/sysroot settings while excluding arbitrary application flags.
- Archiver discovery and runtime-style C compilation succeed with the isolated configuration.

Use compiler output and controlled fixtures as the behavioral oracle. Do not apply modern configuration-search rules to
legacy compilers or use `/dev/null` as the configuration file. Do not silently translate unsupported user syntax.

If configuration isolation cannot be established, retain an actionable unsupported result. If isolation works but reuse
evidence remains incomplete, allow only private preparation for that configuration. Clang 14/15 persistent support
remains an unfinished acceptance requirement until its tests pass; do not close this plan as complete based only on
private compilation success.

## Phase 2: Isolation, Discovery, and Identity

### Capability and invocation

- Detect capability once per preparation context, before memo/profile lookup. Distinguish explicit unsupported-option
  rejection from unrelated errors and timeouts.
- Retain `--no-default-config` where supported. Otherwise use the validated legacy mechanism.
- Own the empty configuration file in a context-lifetime scratch directory, with cleanup on success and failure.
- Insert its physical path only when constructing runtime commands. Apply the same mechanism to archiver discovery,
  runtime dependency/target probes, and runtime compilation.
- Preserve original generated-C arguments, configuration semantics, and extraction of supported runtime target settings.

### Fresh configuration selection

- Reobserve the compiler's effective configuration selection on every legacy resolution, including warm requests, before
  accepting discovery memos.
- Record an ordered configuration signature covering selected files, their content digests, transitive response inputs,
  and effective extracted runtime settings.
- Include that signature and the isolation mechanism in legacy observation-memo selection. This detects newly appearing
  or higher-priority configurations even when built-in search directories cannot be completely enumerated.
- Preserve existing directory dependencies and compiler/toolchain observations. The fresh signature supplements those
  checks; it does not replace input validation or broaden the existing concurrent-mutation contract.
- If effective selection or inputs cannot be observed reliably, decline persistent reuse rather than trusting stale
  evidence. Private compilation still requires a safe runtime configuration.

### Native identity

- Include original configuration inputs in the normal content-based native identity, together with separate effective
  generated-C and runtime configurations.
- Represent the legacy isolation mechanism with a stable internal identity marker. Exclude scratch paths, scratch
  metadata, and incidental probe output from identity.
- Identical inputs must yield identical native keys across processes and scratch locations. Changes to selected
  configuration content or effective target/runtime settings must invalidate the relevant identity.
- Preserve the existing `D` boundary so prior implementation memos and profiles cannot bypass new observation rules. No
  cache migration is required.

## Phase 3: Eligibility, Diagnostics, and Reporting

Do not classify legacy Clang as private-only solely because it lacks the modern flag. Permit persistent publication only
after configuration and all existing toolchain eligibility checks succeed. Eligible configurations support explicit
`--prepare-stdlib`, ordinary reuse, and `--no-auto-prepare` against a valid profile.

Compilable but unobservable configurations use existing private preparation; explicit prewarming and guarded consumption
still refuse them. `--force` refreshes evidence and rebuilds but never overrides eligibility. Keep compiler selection
explicit and never substitute GCC automatically.

Retain errors for invalid configuration, missing tools, failed compilation, and timeouts. Explain configuration
capability failures directly and preserve underlying compiler diagnostics. Under the [diagnostic catalog][diagnostics],
reuse `L1C-2154` for unavailable toolchain capabilities or reuse eligibility, existing storage diagnostics for scratch
failures, and `L1C-2156` for failed preparation commands. No new codes or reservations are planned; recheck the live
catalog at implementation time before changing diagnostic mappings.

Update the capability reporter to distinguish validated `available`, genuine `private`, and confirmed `unsupported`
outcomes. Flag rejection alone must no longer classify a successful legacy fallback as unsupported. Require
`--expect available` for validated legacy persistent configurations; keep that expectation strict for existing lanes.

## Verification and Acceptance

### Real compiler matrix

Require real Clang 14 and 15 to pass persistent preparation tests. Use Clang 19 and normal GCC/Apple Clang lanes as
regression controls, with explicit compiler selection and retained version evidence.

Verify cold preparation, explicit prewarming, build/run/standalone-link consumers, and separate-process warm reuse. Warm
consumers must reuse the same completed profile with zero managed module compilations and zero preparation build
commands. Bounded configuration probes and reads are permitted and must be reported.

### Configuration and invalidation

- Cover no selected configuration, explicit configuration, implicit configuration, target-prefixed aliases, and
  supported nested response files.
- Test creation, modification, deletion, restoration, and higher-priority shadowing of configuration files, including
  files that change only application flags.
- Exercise configuration search overrides, invocation spelling, cwd, and relevant environment changes.
- Verify independent generated-C/runtime target observations and preservation of supported ABI settings.
- Require identical native keys across different scratch directories, with no scratch file needed to validate or reuse a
  completed profile in a later process.
- Exercise compiler/archiver replacement, malformed memos, missing evidence, artifact corruption, and force.
- Verify private fallback when compilation remains safe but discovery cannot authorize reuse, and hard errors when
  isolation fails. Test unsupported options, malformed configuration, unavailable tools, and timeouts separately.

Exercise default, traced, unchecked, and basic runtime variants. Verify cleanup after successful commands, probe and
compile failures, and context destruction. Include concurrent contexts and paths containing spaces, and use existing
Windows portability fixtures for new scratch/argv handling. Keep strict persistent-reuse assertions intact.

Run focused preparation, identity, ownership, integration, and reporter suites plus the dedicated legacy matrix. Run L1
`make test-ci` on the normal supported host and Linux GCC lane because runtime invocation and context ownership affect
trace-sensitive behavior. Measure added warm-resolution work without repeating the SHA-256 benchmark matrix. Retain a
curated evidence report under the matching bug-fix attachments directory; avoid committing binaries or unnecessary raw
logs when the curated report is sufficient.

## Documentation and Completion

Document tested legacy persistent support, conditions for private fallback, and capability-based selection. Distinguish
the Clang 16 introduction of the option from compiler versions actually validated with L1. Update preparation
reference/status documentation, Docker compiler guidance, tests, and date metadata in the implementation change. Do not
present unvalidated configurations as supported.

Close the plan only after real Clang 14/15 persistent-reuse and invalidation acceptance passes. Amend ADR-0039 with the
verified legacy isolation and configuration reobservation policy and link the closed plan in its Related Plans section.
Update the roadmap, resolve links, and run active/staged ADR validation, whitespace checks, and root pre-commit.

## Non-goals

- No new CLI options, public APIs, implicit compiler switching, or blanket minimum-version compatibility promises.
- No Docker base upgrades, global toolchain changes, or edits to retained historical experiment results.
- No SHA-256 changes, relaxed metadata validation, or weakening of stable-read and artifact-integrity checks.
- No broader legacy configuration syntax emulation or expansion of concurrent external mutation guarantees.
- No push, publication, deployment, or workflow dispatch as part of this plan.

[clang-fifteen]: https://github.com/llvm/llvm-project/blob/llvmorg-15.0.7/clang/lib/Driver/Driver.cpp#L926-L965
[clang-fourteen]: https://github.com/llvm/llvm-project/blob/llvmorg-14.0.6/clang/lib/Driver/Driver.cpp#L879-L918
[clang-release]: https://releases.llvm.org/16.0.0/tools/clang/docs/ReleaseNotes.html#new-compiler-flags
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[identity-adr]: ../../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[option-review]: https://reviews.llvm.org/D134018
[phase-three]: ../features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/relaxed-toolchain/results.md
[preparation-contract]: ../../../docs/reference/stdlib-preparation.md
[preparation-economy]: ../refactors/closed/2026-09-12-native-preparation-economy-noref.md
[reuse-investigation]: ../features/2026-09-24-preparation-reuse-efficiency-noref.md
