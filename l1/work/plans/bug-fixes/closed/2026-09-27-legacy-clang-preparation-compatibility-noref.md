# Bug Fix Plan

## Safe legacy Clang compatibility and persistent preparation

- Date: 2026-10-16
- Status: Completed
- Title: Support legacy Clang preparation with verified configuration isolation and safe persistent reuse
- Kind: Bug Fix
- Severity: Medium
- Subsystem: Native preparation / Clang configuration discovery / identity and invalidation
- Modules: `l1/compiler/support/preparation/{identity,storage,build,construction}.h`,
  `l1/compiler/support/preparation_support.c`, `l1/scripts/check_preparation_reuse.py`
- Tests: Preparation identity, compatibility, dependency arguments, ownership, CLI integration, and reuse reporting.
- Related:
  - [l1/docs/reference/stdlib-preparation.md][preparation-contract]
  - [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][identity-adr]
  - [l1/work/plans/features/closed/2026-09-24-preparation-reuse-efficiency-noref.md][reuse-investigation]
  - [l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/relaxed-toolchain/results.md][phase-three]
  - [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]

## Outcome

Validated Debian Clang 14 and 15 now support ordinary L1 compilation and persistent stdlib/runtime preparation.
Capability checks select verified configuration isolation before discovery-memo lookup. Modern Clang retains
`--no-default-config`; legacy drivers use an owned empty regular file through separate `--config PATH` arguments.
Private preparation remains available only when compilation is safe but persistent reuse cannot be authorized.

This standalone fix resolves the legacy preparation failure recorded by the preparation reuse investigation. It does not
change retained historical measurements or imply blanket compatibility for untested compiler installations. Exact
compiler provenance, reproducible commands, outcomes, and bounded warm-work accounting are retained in
[l1/work/plans/bug-fixes/attachments/2026-09-27-legacy-clang-preparation-compatibility/results.md][evidence].

## ADR Impact

- Decision: Authorize legacy Clang persistent preparation using verified configuration isolation and fresh
  configuration-selection evidence.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Extend the adapter boundary with verified legacy isolation and configuration reobservation while
    preserving content-based identity, safe private fallback, and the existing concurrent-mutation contract.

## Implemented behavior

- Detect isolation capability once per preparation context. Only an explicit rejection of the exact modern option
  authorizes the legacy probe. Unrelated errors, crashes, timeouts, and diagnostic suggestions remain errors.
- Verify that the legacy driver selects exactly the owned empty configuration and emits a compiler invocation. Insert
  the physical scratch path only into runtime argv, including archiver discovery, dependency/target probes, and runtime
  compilation. Keep original generated-C configuration semantics and supported runtime target settings.
- Own scratch for the context lifetime and release it after errors or destruction. Normalized construction inputs carry
  a stable isolation descriptor; detached constructors recreate their own scratch without discovery after the original
  context is destroyed.
- Reobserve legacy effective configuration selection before every discovery-memo lookup. The ordered signature covers
  selected paths, expanded options, fresh content digests, transitive response inputs, and extracted runtime settings.
  It supplements existing file and directory observations, detecting newly selected and higher-priority configurations.
- Include original configuration inputs and separate generated-C/runtime configuration in content-based native identity.
  Stable isolation markers replace physical scratch names. Preserve the existing `D` boundary and require no migration.
- Decline persistent reuse when selection evidence is incomplete. Unobservable legacy selection permits private
  preparation only with one absolute explicit configuration whose readable contents provide safe runtime settings;
  unknown implicit target selection is an error. Force never bypasses eligibility.
- Classify the reporter result as unsupported only after matching the isolation failure and independently confirming
  rejection of both mechanisms. Validated legacy configurations must pass strict `--expect available` checks.

The live diagnostic catalog was checked. Existing `L1C-2154` capability/eligibility, storage diagnostics, and `L1C-2156`
preparation-command failures suffice; no codes were added or reassigned.

## Findings and verification

Real Debian Clang 14.0.6 and 15.0.6 reject the modern flag but accept the separate absolute empty-config spelling,
including paths with spaces. Target-prefixed aliases select configurations through the tested user/system search roots;
adjacent configuration alone is not selected in those builds. Compiler output and owned fixtures establish the behavior,
rather than assuming modern search rules. LLVM's [Clang 16 release notes][clang-release] establish the modern option's
upstream introduction, independently of L1's validated support matrix and Apple Clang numbering.

The retained acceptance matrix covers cold preparation, prewarming, build/run/link consumers, separate-process warm and
guarded reuse, configuration invalidation, force, corruption, and restoration. Warm consumers reuse the same completed
profile with zero managed module compilations and zero preparation build commands. Configured legacy warm resolution
retains bounded probes and fresh content reads.

Dedicated tests cover explicit and implicit configurations, aliases, search overrides, nested response files,
application-only changes, selection creation/deletion/restoration/shadowing, target extraction, separate scratch roots,
all four runtime variants, concurrent contexts, detached construction, and cleanup after probe and compile failures.
Controlled native fixtures distinguish unsupported options from unrelated failures and unsafe observation. Existing
identity and integration suites retain compiler/archiver replacement, memo, environment, cwd, and artifact checks.

Supported-host regression validation covers the exhaustive `make test-ci` tier on Apple Clang and Linux GCC, plus Clang
19 as the modern compatibility control. A host I/O case correctly refused publication during a source edit and passed
its unchanged-source rerun; the remaining host tier components were completed separately. A final narrow
diagnostic-matcher correction is covered by focused final-source regressions, as detailed in the evidence report.
Synthetic POSIX and Windows argv fixtures exercise spaces, quotes, drive and UNC paths, and mixed separators; native
Windows legacy compiler execution was not performed.

An owned macOS repository-local reporter fixture experienced a concurrent `ctime` change with unchanged bytes. The
existing stable-input check correctly refused publication. Isolated temporary-directory validation passed; no input
stability or artifact-integrity checks were relaxed.

## Documentation and limits

Preparation reference, status, compiler guidance, README examples, roadmap, and ADR-0039 now describe the validated
capability boundary. GCC remains the normal Docker default; explicit legacy Clang selection is supported within the
verified scope. No compiler is substituted automatically, and unsupported configuration syntax is not translated.

No public CLI option, new diagnostic, global toolchain change, Docker base upgrade, cache migration, SHA-256 change, or
broader concurrent external mutation guarantee is introduced. No remote write or publication is part of this work.

[clang-release]: https://releases.llvm.org/16.0.0/tools/clang/docs/ReleaseNotes.html#new-compiler-flags
[diagnostics]: ../../../../../docs/specs/compiler/diagnostic-code-catalog.md
[evidence]: ../attachments/2026-09-27-legacy-clang-preparation-compatibility/results.md
[identity-adr]: ../../../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[phase-three]: ../../features/attachments/2026-09-24-preparation-reuse-efficiency/phase3/relaxed-toolchain/results.md
[preparation-contract]: ../../../../docs/reference/stdlib-preparation.md
[reuse-investigation]: ../../features/closed/2026-09-24-preparation-reuse-efficiency-noref.md
