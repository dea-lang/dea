# Feature Plan

## Automatically prepare and cache the standard library and runtime

- Date: 2026-09-07
- Status: Draft
- Title: Automatically prepare and cache L1 standard-library modules and matching runtime configurations
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Compiler driver / standard library / runtime / bootstrap / artifact discovery
- Modules:
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/src/cli_args/`
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/interface_emitter.l0`
  - `l1/compiler/stage1_l0/src/compile_driver/`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/link_driver/`
  - `l1/compiler/stage1_l0/src/compiler_filesystem.l0`
  - `l1/compiler/shared/l1/stdlib/`
  - `l1/compiler/shared/runtime/`
  - `l1/Makefile`
  - `l1/scripts/build_stage1_l1c.py`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_support_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_build_config_test.py`
  - `l1/compiler/stage1_l0/tests/compiler_runtime_build_env_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_compile_only_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_build_run_multi_cu_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_link_set_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_help_output_test.py`
- Related:
  - [l1/work/plans/features/2026-09-07-standalone-link-interface-discovery-noref.md][link-discovery]
  - [l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][bootstrap-productization]
  - [docs/specs/compiler/cli-contract.md][cli-contract]
  - [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]
  - [l1/docs/reference/separate-compilation.md][separate-compilation]
  - [l1/docs/reference/c-backend-design.md][backend]
- Repro: `l1c --compile l1/examples/demo.l1 -o build/modules/demo.o` after bootstrap without manually prepared stdlib
  interfaces.

## Summary

Bootstrap should prepare reusable stdlib module pairs and the matching runtime after building `l1c`. Ordinary compiler
commands should automatically prepare missing managed artifacts and then continue. Explicit preparation remains useful
for prewarming, forced rebuilding, and controlled build environments.

Separate semantic interface availability from native artifact compatibility. A change of external C compiler can reuse
matching `.l1m` interfaces while selecting or preparing different native objects and runtime inputs. Preparing those
inputs does not rebuild application or third-party objects supplied by the caller.

Managed stdlib discovery is enabled by default, independently of `-I`. The companion linking plan defines dependency
discovery and precedence; this plan supplies the managed artifacts and their preparation lifecycle. Implement its
interface-assisted discovery foundation first, then integrate the managed provider service specified here. The
coordinated order is interface discovery, preparation, then managed-provider integration. Neither plan is complete or
eligible for closure before the integrated acceptance criteria of both plans pass.

## Current State

- Bootstrap builds the compiler and runtime support but does not prepare reusable stdlib `.o`/`.l1m` pairs.
- Build/run compile a source dependency closure in a private workspace; their temporary module artifacts are not a
  reusable stdlib cache.
- Compile-only requires verified interfaces for non-virtual imports rather than falling back to their sources.
- Stdlib source roots and explicit interface roots are separate discovery inputs.
- Native runtime selection already distinguishes checking/trace variants and TinyCC compatibility objects.
- L1 remains bootstrap-only. Its installed payload contract must be coordinated with the existing productization plan;
  this feature does not itself implement an installer or distribution workflow.

## Defaults Chosen

### Preparation interface and mode boundaries

Add a preparation mode with no positional source target. Reuse the existing C compiler, C options, trace, and checking
selectors:

```sh
l1c --prepare-stdlib --c-compiler gcc
l1c --prepare-stdlib --c-compiler gcc --force
l1c --prepare-stdlib --c-compiler gcc --stdlib-cache _cache/dea
```

- Bootstrap, explicit preparation, and automatic preparation call the same internal operation.
- Native preparation builds all bundled `std.*` and `sys.*` modules in dependency order, plus the matching runtime
  variant. Preparation uses its own dependency interfaces and cannot recursively trigger default-cache preparation.
- Ordinary preparation reuses a complete matching configuration. `--force` is valid only with explicit preparation and
  rebuilds the selected configuration in place.
- Build/run and standalone linking automatically prepare missing required managed native support, then resume the
  original command.
- Compile-only and generated-C modes use matching interfaces and headers without requiring native provider objects.
  Missing managed interfaces can be regenerated through the frontend without invoking a C compiler.
- Source inspection and interface-emission modes retain their existing ability to operate without a C toolchain.
- Add `--no-auto-prepare`: allow managed discovery and reuse, but fail on a miss with the exact preparation command.
- Add `--no-stdlib-cache`: disable managed artifact discovery and preparation for caller-managed operation.
- Cache controls apply to the modes that consume managed artifacts. Disabling automatic preparation or managed-cache use
  is incompatible with explicitly requesting preparation.

Automatic preparation covers bundled stdlib/runtime inputs. Explicit objects and ordered `-I` providers precede managed
stdlib providers; `-I` is not required to activate managed discovery. Custom system roots and runtime overrides retain
their authority. Invalid explicitly selected providers remain errors rather than triggers to replace them from the
cache. Application and third-party dependency sources are not implicitly compiled by compile-only or standalone link.

### Artifact identity and selection

- Keep semantic interface identity separate from native configuration identity. Native profiles contain canonical
  `.o`/`.l1m` pairs, matching runtime headers, and runtime native inputs.
- Identify Dea inputs by content, including private stdlib implementation changes, runtime sources/headers, and the Dea
  compiler build. Public interface fingerprints alone are insufficient cache identities.
- A compiler implementation fingerprint identifies compiler contents and the implementation components discovered by its
  supported toolchain adapter. Retain compiler family and full version/build information as readable metadata; neither
  is sufficient for equality, including when different compiler contents report the same version.
- A preparation fingerprint is a versioned hash of Dea compiler/source inputs, compiler implementation identity,
  effective target, ordered effective native options, SDK/sysroot and relevant dependency inputs, and trace/checking
  settings. Include fingerprint-schema and adapter revisions so changed identity rules invalidate earlier records.
- Effective target includes architecture, OS/object format, ABI, and required CPU features. Host-dependent options such
  as `-march=native` contribute their resolved meaning rather than only their literal spelling.
- Compiler paths are discovery inputs, not substitutes for content identity. Preserve invocation aliases and account for
  path-dependent component selection and behavior in the preparation fingerprint.
- Use exact preparation matching. Different compiler implementations select separate native entries even when their ABIs
  are compatible, including across major releases or between minor releases. This is a reuse policy, not a general proof
  that differing configurations are ABI-incompatible. Do not introduce an ABI-compatibility inference engine.
- Each supported toolchain adapter documents its component discovery, selection inputs, and detection limits. Cover
  existing GCC, Clang/Apple Clang, and TinyCC workflows; this feature does not add MSVC support.
- Opaque wrappers and undeclared external toolchain changes retain forced preparation and caller-managed artifacts as
  recovery paths. Do not claim complete identity detection for unsupported arrangements or add an identity-override CLI.
- Retain different configurations so switching back reuses prior preparation. Do not add general project-output caching,
  physical interface deduplication machinery, or automatic cache pruning in this plan.

### Machine-local identity memo and fast validation

Keep a machine-local identity memo separate from the potentially shared artifact cache. The memo records discovered
components, remembered content digests, and the local metadata used to validate those digests. Shared artifact selection
uses content/configuration fingerprints; another machine's paths, file identities, or timestamps never establish a local
memo hit. Selecting a shared artifact root does not make the identity memo portable.

For each native-consuming command:

1. Resolve compiler selection, effective options, relevant environment, and platform selection.
2. Load the local identity record and validate its discovery dependencies, including invocation aliases and relevant
   search/configuration changes. Validating yesterday's component files is insufficient if today's selection would find
   a different component or an earlier search-path candidate.
3. Rediscover components when selection dependencies change; otherwise reuse the recorded component inventory.
4. Reuse each remembered content digest when file identity, size, and high-resolution modification/change timestamps
   match. Hash new or changed components and check that their metadata did not change during hashing. Do not accept a
   digest from an unstable read.
5. Resolve effective target requirements, including native CPU features, and construct the preparation fingerprint.
6. Select matching installed/cached artifacts or invoke preparation under the existing policy.

Resolve the native preparation context once per command and pass it through preparation and provider selection. Use
native metadata operations and streaming SHA-256; avoid shell hashing commands and per-module toolchain probes. Where
selection requires a platform resolver query, include it in identity validation rather than trusting stale discovery.
Compiler probes must have bounded execution and captured output. Probe failures must not authorize stale reuse.

A missing or invalid memo triggers recomputation; validate memo records before reuse. Explicit `--force` bypasses
remembered discovery and digests as well as rebuilding artifacts. Changes that preserve all checked metadata remain an
explicit detection limitation; forced preparation is recovery, not automatic detection. Concurrent toolchain replacement
is outside the supported preparation contract. Track relevant SDK/header dependencies and search changes without
recursively scanning the entire SDK on every invocation.

### Identity-validation performance

Measure identity validation separately from full artifact validation and preparation. On designated local reference
machines, target under 10 ms p95 for warm direct-toolchain identity validation and under 100 ms p95 when warm validation
requires platform resolver queries. Unchanged warm validation performs no compiler-binary content reads, no recursive
SDK scans, and no repeated probes per module.

Record cold-discovery costs separately, including toolchain size and benchmark environment. A local feasibility
measurement on 2026-09-09 hashed a 272 MB Apple Clang executable in about 1.1 seconds; it is not a portable guarantee or
an end-to-end cache benchmark. Keep reference-machine timing measurements separate from ordinary CI correctness checks;
CI verifies operation counts and behavior rather than enforcing noisy wall-clock thresholds.

### Ordinary writes and preparation coordination

Use ordinary writes and a completion manifest. Invalidate completion before rebuilding and mark success only after the
required artifacts are ready. Failed or interrupted preparation leaves the selected configuration unavailable; a later
invocation may retry.

Serialize preparation per managed artifact set, including shared interface preparation. One process prepares while
others wait, acquire the coordination lock, and recheck completion before doing work. Coordination must release when the
preparing process exits, including abnormal exit. Prepare shared interfaces before acquiring native-configuration
coordination to avoid recursive lock acquisition. Different configurations may prepare independently.

Do not introduce cache transactions, immutable generations, rollback, or reader pinning. Reuse existing per-module
artifact handling unchanged; do not add cache-wide staging. Explicit forced rebuilding remains a maintenance operation
requiring external serialization against consumers. Preservation of its previous contents and concurrent consumption
during forced rebuilding are not guaranteed.

### Output and failures

Send preparation messages to stderr, preserving program output and compiler output on stdout. Use the existing counted
verbosity options:

| Verbosity    | Preparation output                                                                                                                                |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Default      | Announce each actual preparation or rebuild, identifying compiler and target; report completion or failure. Successful cache reuse remains quiet. |
| `-v` / `-vv` | Add configuration selection, reuse/rebuild reasons, cache paths, module progress, and compiler commands.                                          |
| `-vvv`       | Add detailed identity inputs, dependency resolution, and cache-validation decisions.                                                              |

Describe a new configuration rather than only a new target: changing compiler, options, or checking mode may require
preparation without changing target architecture. A normal miss produces progress rather than an error. Missing
compilers, unsupported configurations, unavailable source inputs, unwritable caches, and compilation failures terminate
the original command with actionable diagnostics. Preserve relevant host-compiler errors at every verbosity level and do
not retry indefinitely.

### Bootstrap and installed ownership

Bootstrap prewarms the default configuration after building `l1c`. Automatic preparation makes prewarming an
optimization rather than a prerequisite for correctness.

Cache-root precedence is `--stdlib-cache`, then `L1_STDLIB_CACHE`, then the environment default:

| Environment                   | Default writable root                                       |
| ----------------------------- | ----------------------------------------------------------- |
| Repository development        | `$L1_BUILD_DIR/cache`                                       |
| Installed compiler on Linux   | `$XDG_CACHE_HOME/dea/l1`, falling back to `~/.cache/dea/l1` |
| Installed compiler on macOS   | `~/Library/Caches/dea/l1`                                   |
| Installed compiler on Windows | Local AppData under `Dea\L1\Cache`                          |

Resolve relative overrides against the invocation directory. An explicit writable-cache selection must not silently fall
back to another writable cache.

The installed payload contract includes read-only interfaces, default prepared native support, and the source inputs
required for rebuilding. Reuse shipped native support only when its configuration matches; otherwise prepare into the
selected writable cache. Local variants remain separate from the installed default, so clearing a writable cache does
not remove installed support artifacts.

Coordinate this contract with
[l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][bootstrap-productization]. Installers,
distribution creation, and release publication remain outside this plan. Preserve build/run generated-C retention and
cross-mode C-byte identity when using cached providers.

## Implementation Phases

1. Build on the companion plan's provider-discovery foundation. Introduce semantic/native identities, managed artifact
   lookup, completion state, and process-lifetime preparation coordination. Implement supported toolchain adapters,
   versioned preparation fingerprints, the machine-local identity memo, native metadata/digest support, and bounded
   output-capturing probes.
2. Implement the shared preparation operation and manual CLI. Reuse frontend interface emission, per-module compilation,
   runtime variants, and TinyCC handling; keep preparation inputs separate from ordinary provider discovery.
3. Integrate automatic preparation and opt-outs into the applicable modes. Add stderr progress at the agreed verbosity
   levels, actionable failures, and default stdlib discovery without `-I`. Pass one resolved native preparation context
   through managed stdlib and runtime selection rather than repeating compiler discovery per module.
4. Invoke preparation from bootstrap, implement cache-root selection and read-only payload discovery, and preserve
   generated-C contracts. Define the packaging handoff without implementing installers or distributions here.
5. Update the shared CLI contract and diagnostic catalog plus L1 bootstrap, separate-compilation, and runtime docs when
   the feature lands. Add the verification below in the implementation change.

## ADR Impact

- Decision: Automatically prepare managed stdlib/runtime configurations with manual controls and simple cache
  coordination.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Preparation defaults, cache ownership, verbosity, and concurrency behavior establish a durable toolchain
    contract.
- Decision: Select exact preparation fingerprints and accelerate content-digest reuse through a machine-local,
  metadata-validated identity memo.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Compiler implementation identity, effective target selection, adapter/schema revisions, and the explicit
    metadata-detection limits define when managed native artifacts may be reused locally or across machines.
- Decision: Select matching prepared runtime inputs across compiler configurations.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0027-runtime-archive-and-trace-selection-boundary.md`
  - Rationale: Extend runtime selection while preserving checking/trace variants and TinyCC compatibility handling.
- Decision: Reuse prepared bundled providers within build/run orchestration.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0033-multi-compilation-unit-build-and-run-pipeline.md`
  - Rationale: Record managed-provider reuse while preserving application compilation and generated-artifact contracts.

## Diagnostic Planning

Provisionally reserve `L1C-2150` through `L1C-2169` for the new preparation, coordination, and managed-cache diagnostic
area. Include preparation-disabled misses, unusable cache/source inputs, coordination failures, and failed preparation
where existing lower-level diagnostics do not already describe the error. Normal preparation progress is informational.

Recheck the range against [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] at implementation time before
assigning final codes. If any numbers have been used or reserved elsewhere, choose another available block then. Update
existing CLI mode-validation diagnostics where the new preparation mode broadens an option's valid modes. The companion
linking plan uses this preparation area rather than reserving another cache block.

## Non-Goals

- Implementing application or third-party source dependency builds inside compile-only or standalone link.
- Rebuilding or proving the native compatibility of caller-supplied objects.
- Adding a general build cache, cache garbage collection, or transactional cache publication.
- Guaranteeing concurrent consumption during an explicit forced rebuild.
- Changing the `.l1m` format or object ABI.
- Implementing installation, distribution, release, or publication workflows.

## Verification Criteria

01. Fresh bootstrap followed by demo compilation succeeds without manually preparing stdlib modules.
02. Cold-cache build/run and standalone linking automatically prepare required support and finish successfully; warm
    invocations reuse artifacts quietly. Standalone stdlib discovery works both with and without `-I`.
03. Supported Clang/GCC/TinyCC configuration switches preserve interface reuse, select matching runtime inputs, and
    reuse previous native configurations after switching back.
04. Source, private implementation, header, compiler, options, SDK configuration, and checking/trace changes invalidate
    the appropriate artifacts. Forced preparation repairs an otherwise undetected external toolchain change.
05. Compile-only and generated-C modes need no native provider objects; source-only and interface-emission modes retain
    their no-C-toolchain behavior. Generated-C retention and cross-mode C-byte identity remain covered.
06. `--no-auto-prepare` succeeds on hits and reports the exact preparation command on misses. `--no-stdlib-cache`
    disables managed discovery/preparation while explicit-provider workflows remain usable. Invalid CLI combinations are
    rejected.
07. Default, INFO, and DEBUG output follows the contract, including visible host-compiler errors, and does not
    contaminate stdout or a program's output under `--run`.
08. Failed or interrupted preparation leaves no usable completion marker. A later invocation repairs the configuration;
    no rollback or previous-generation preservation is required.
09. Concurrent cold requests prepare one shared artifact set and both finish; process exit releases coordination. Shared
    interface preparation does not deadlock with native preparation, and different configurations can proceed
    independently.
10. Read-only installed payload fixtures, writable user defaults, project-local overrides, and relative-root resolution
    work. Clearing a writable cache permits automatic rebuilding and leaves the installed default intact.
11. Explicit objects, ordered `-I` roots, custom system roots, and runtime overrides keep their authority. An invalid
    explicitly selected provider is not hidden by automatic preparation or a later managed provider.
12. Different compiler contents reporting the same version, ABI-compatible major releases, and changed minor releases
    select separate native entries while preserving matching semantic interfaces. Fingerprint-schema and adapter
    revisions invalidate records created under earlier identity rules.
13. File replacement, alias/symlink retargeting, changed subordinate tools, and selection of a different search-path
    candidate invalidate the applicable memo discovery or digest state. SDK/header inputs, ordered options, target
    architecture, ABI, and resolved native CPU features affect preparation selection.
14. Shared artifact-cache fixtures use independent machine-local identity memos. Matching content/configuration may
    reuse shared artifacts, but another machine's metadata cannot establish a memo hit or mask target differences.
15. Missing or corrupt memo records recompute identity. Forced preparation refreshes discovery and digests, including
    otherwise undetected metadata-preserving changes. Probe failure/timeout and files changing during hashing never
    authorize stale or unstable reuse.
16. Instrumented warm-path tests verify no compiler-binary content reads, recursive SDK scans, or repeated per-module
    discovery. Reference-machine benchmarks report p95 identity-validation time against the stated targets, separately
    from full artifact validation, preparation, and cold-discovery costs.
17. Integrated cold/warm build, run, and standalone-link acceptance passes with interface reuse, matching managed
    stdlib/runtime selection, and explicit-provider precedence before either coordinated plan closes.

During implementation, run focused compiler/cache/bootstrap tests followed by L1 `make test-all`, ADR validation, and
the required pre-commit checks. Recording this Draft plan requires documentation validation only.

[backend]: ../../../docs/reference/c-backend-design.md
[bootstrap-productization]: ../tools/2026-04-02-l1-bootstrap-productization-noref.md
[cli-contract]: ../../../../docs/specs/compiler/cli-contract.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[link-discovery]: 2026-09-07-standalone-link-interface-discovery-noref.md
[separate-compilation]: ../../../docs/reference/separate-compilation.md
