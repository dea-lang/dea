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
interface-assisted discovery foundation first, then integrate the managed provider service specified here.

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
- Native identity additionally includes resolved C toolchain identity/version, target, effective native options,
  relevant SDK configuration, and trace/checking mode.
- Use conservative configuration matching. Exact preparation identity is a reuse policy, not a general proof that every
  differing native configuration is ABI-incompatible. Do not introduce an ABI-compatibility inference engine.
- Opaque wrappers and undeclared external toolchain changes retain forced preparation and caller-managed artifacts as
  recovery paths.
- Retain different configurations so switching back reuses prior preparation. Do not add general project-output caching,
  physical interface deduplication machinery, or automatic cache pruning in this plan.

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
   lookup, completion state, and process-lifetime preparation coordination.
2. Implement the shared preparation operation and manual CLI. Reuse frontend interface emission, per-module compilation,
   runtime variants, and TinyCC handling; keep preparation inputs separate from ordinary provider discovery.
3. Integrate automatic preparation and opt-outs into the applicable modes. Add stderr progress at the agreed verbosity
   levels, actionable failures, and default stdlib discovery without `-I`.
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
  - Rationale: Preparation defaults, configuration identity, cache ownership, verbosity, and concurrency behavior
    establish a durable toolchain contract.
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

During implementation, run focused compiler/cache/bootstrap tests followed by L1 `make test-all`, ADR validation, and
the required pre-commit checks. Recording this Draft plan requires documentation validation only.

[backend]: ../../../docs/reference/c-backend-design.md
[bootstrap-productization]: ../tools/2026-04-02-l1-bootstrap-productization-noref.md
[cli-contract]: ../../../../docs/specs/compiler/cli-contract.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[link-discovery]: 2026-09-07-standalone-link-interface-discovery-noref.md
[separate-compilation]: ../../../docs/reference/separate-compilation.md
