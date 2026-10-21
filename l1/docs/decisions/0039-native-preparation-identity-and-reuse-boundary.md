# ADR-0039: Native Preparation Identity and Reuse Boundary

- Decision date: 2026-09-11
- Last edited: 2026-10-21
- Status: Accepted

## Context

Native stdlib/runtime artifacts depend on both Dea inputs and the selected native toolchain. Compiler names, versions or
Git revisions alone do not identify effective development inputs. Arbitrary wrappers and host configurations may compile
successfully without exposing enough information to validate later reuse. Forwarding the complete application C option
vector to runtime implementation sources would also change the runtime's established build policy.

## Decision

`D` identifies the effective compiler and compiler-owned preparation inputs by content. `N` combines `D`, bounded
supported toolchain observations, and separate effective stdlib and runtime native configurations. Different keys imply
no ABI compatibility, and there is no cross-`D` per-module native reuse. Application sources/graphs, project roots,
output paths, and final-only link operands do not enter the native key.

Raw environment text remains part of observation-memo selection, but does not enter `N`. A selection change requires
fresh toolchain observation; equal effective inputs can reuse the same native profile. Live directory dependencies still
detect new shadowing candidates. Generated-C and runtime target macros are observed independently, because application
defines can mask an environment-selected runtime target. The macOS build identifier remains explicit native evidence for
system implementation libraries held in the dyld shared cache. Existing loader/driver environment refusals apply before
memo lookup and are not relaxed by identity equality.

Bundled generated C uses the selected compiler, `L1_CFLAGS` followed by `--c-options`, and normal generated-C defaults.
Runtime C uses the same compiler with compiler-owned `-O2 -std=c99`, checking/trace defines and default tuning.
Supported target/CPU/ABI/sysroot settings apply to both. Make runtime variables do not configure managed preparation.
Header overrides participate in stdlib configuration and dependency observation; runtime-library overrides remain
final-only and do not produce partial profiles.

GCC, Clang/Apple Clang and TinyCC adapters authorize persistent reuse only when their required observations succeed.
Observation covers the effective compiler, required components/archiver, target/SDK/search inputs, applicable headers
and bounded implementation dependencies. Clang's persistent path uses its integrated assembler. Unsupported indirection,
opaque wrappers, unavailable observations, plugins and similar configurations decline reuse. Invocability remains
separate: consuming commands may prepare fresh support, while explicit preparation fails. Force reobserves and rebuilds
but never bypasses eligibility. TinyCC's complete raw-object runtime path has no archive dependency.

Clang runtime isolation is selected by capability before observation-memo lookup. Modern drivers use
`--no-default-config`; validated legacy drivers use an owned empty regular configuration file with `--config PATH`. The
context owns and removes that file. Only runtime command construction receives its physical path; native identity
records a stable isolation marker and never retains scratch paths or metadata. Generated-C arguments retain their
original configuration semantics, and only supported target/CPU/ABI/sysroot settings reach runtime compilation.
Normalized construction inputs retain the same isolation choice. Direct constructors recreate owned empty configuration
scratch without discovery, preserving runtime policy after the original preparation context is destroyed.

Legacy resolution reobserves effective configuration selection on every command, including warm requests. Its ordered
signature covers selected configuration files, fresh content digests, transitive response inputs, and extracted runtime
settings. The signature and isolation mechanism enter observation-memo selection alongside existing directory and
toolchain evidence. Original configuration inputs remain content-based native inputs. Missing selection evidence
declines persistent reuse; private preparation still requires safe runtime isolation. Unexpected errors and timeouts
never establish unsupported-option capability. Without observable legacy selection, private preparation requires one
absolute explicit config with readable target settings; unknown implicit target selection is an error. This adds no
concurrent external mutation guarantee.

Machine-local toolchain and artifact memos are accelerators. Reliable file identity/change metadata can reuse prior
content checks; absent, malformed or stale memo records cause fresh validation. Toolchain memo selection includes `D`,
so implementation changes cannot inherit old observation rules. There is no host identifier, cross-host portability
promise, metadata-preserving-mutation guarantee or whole-host installation fingerprint.

Discovery remains cwd-sensitive. A disposable digest-seed hint, keyed by the same selection with only cwd omitted, may
name one prior toolchain memo as candidate file evidence. The current memo's valid records take precedence; donor
records require the same reliable metadata and digest checks and are copied into the new self-contained memo. Donor
discovery never authorizes observation reuse. Force bypasses both evidence sources. Missing or unusable optional records
fall back to stable hashing; actual input failures retain existing diagnostics.

Hints use schema 1, kind `input-digest-seed`, and a validated hexadecimal memo key under the local toolchain-memo
directory. Each invocation loads at most one donor, without scanning. Successful eligible memo writes may update a hint
using ordinary best-effort writes; failed writes or lost updates only reduce reuse. There are no added locks, merge
protocol, history or pruning service. Existing cache accumulation, manual deletion and allocation-failure policy remain
unchanged. No cwd-independence classifier or observation-sharing proof is required.

Discovery keeps whole-observation invalidation. On macOS, Apple Clang batches the four generated-C dependency
configurations and all ten runtime translation units in separate invocations under their respective options. Batch
output must identify every expected source exactly once before any evidence is retained. Unavailable, ambiguous, failed,
timed-out or oversized batches retry individual probes. Other compilers/platforms use individual probes directly: the
Linux comparison did not establish a consumer improvement, and Clang multi-source commands can add frontend process
startups. Batching preserves input and negative-search coverage. Finer-grained persisted observation reuse remains
deferred.

Preparation retains its dependency-free portable C SHA-256 backend. The direct-block and round-unrolled alternatives did
not meet their predeclared consumer gates; platform acceleration shows large-file headroom with small-file setup costs.
System crypto dependencies, platform-specific dispatch and digest-context failure cleanup require a separate integration
and consumer-performance gate across supported platforms. These experiments do not adopt a system crypto dependency or
change digest bytes, stable-read checks, content coverage or metadata policy.

Managed artifact validation checks the complete manifest inventory, relative containment, sizes/digests and exact
selected semantic bytes. Native contents remain semantically opaque; `.l1m` parsing, fingerprints, graph and lifecycle
validation remain authoritative.

Explicit profiles use a separate caller-stability contract: selection restores recorded inputs and validates payload
bytes without managed identity, toolchain/DLL freshness observations or cache policy. The caller keeps external
compiler/SDK/environment inputs suitable and recreates the profile when those change. An explicit success does not
authorize managed reuse.

## Rationale

Separate identities distinguish compiler-owned content from native configuration without making semantic-only commands
pay for native validation. Separate compilation policies preserve runtime semantics while applying the same target
choices. Conservative adapter refusal avoids treating successful invocation as evidence of future reproducibility. Memos
make unchanged local work cheaper without becoming authority, and bounded observations keep the service narrower than a
general toolchain or project build system.

## Consequences

- A configuration may work automatically but be unavailable for persistent prewarming.
- Default cache hits remain quiet; verbosity explains observations, configuration and validation.
- A first invocation under changed environment text pays for fresh observations even when it retains a profile hit.
- A first invocation in a new cwd still observes selection but can avoid hashing unchanged files through a donor memo.
- Legacy warm requests retain bounded configuration probes and fresh configuration reads while reusing completed
  profiles with zero managed compilations and preparation build commands.
- Old discovery memos missing runtime target evidence are reobserved; compiler-content identity changes keep old
  profiles separate without migration.
- Working compiler/stdlib/runtime edits conservatively select a new native profile.
- Header selection changes, including generated checking/real/float branches and earlier shadow candidates, invalidate
  reuse when detected by the adapter.
- External mutation concurrent with validation/consumption and copied/shared cache portability are unsupported.
- Native integrity checks do not authenticate caller-owned object/interface pairs or infer compatible ABIs.

## Related Plans

- [l1/work/plans/refactors/closed/2026-10-21-managed-profile-client-integration-noref.md][managed-client]

- [l1/work/plans/features/closed/2026-09-30-explicit-profile-artifacts-noref.md][explicit-profile-plan]

- [l1/work/plans/bug-fixes/closed/2026-09-27-legacy-clang-preparation-compatibility-noref.md][legacy-clang]

- [l1/work/plans/refactors/closed/2026-09-30-profile-construction-boundary-noref.md][profile-boundary]

- [l1/work/plans/features/closed/2026-09-24-preparation-reuse-efficiency-noref.md][reuse-efficiency] (digest sharing,
  scoped discovery and retained portable hashing).

- [l1/work/plans/refactors/closed/2026-09-15-native-identity-environment-text-reassessment-noref.md][environment-identity]

- [l1/work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][preparation-plan]

- [l1/work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md][preparation-economy]

## Current Docs

- [l1/docs/reference/explicit-profiles.md][explicit-profiles]

- [docs/specs/compiler/cli-contract.md][cli]

- [l1/docs/reference/stdlib-preparation.md][preparation]

- [l1/docs/reference/c-backend-design.md][backend]

- [l1/docs/reference/separate-compilation.md][separate-compilation]

[backend]: ../reference/c-backend-design.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[environment-identity]: ../../work/plans/refactors/closed/2026-09-15-native-identity-environment-text-reassessment-noref.md
[explicit-profile-plan]: ../../work/plans/features/closed/2026-09-30-explicit-profile-artifacts-noref.md
[explicit-profiles]: ../reference/explicit-profiles.md
[legacy-clang]: ../../work/plans/bug-fixes/closed/2026-09-27-legacy-clang-preparation-compatibility-noref.md
[managed-client]: ../../work/plans/refactors/closed/2026-10-21-managed-profile-client-integration-noref.md
[preparation]: ../reference/stdlib-preparation.md
[preparation-economy]: ../../work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md
[preparation-plan]: ../../work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md
[profile-boundary]: ../../work/plans/refactors/closed/2026-09-30-profile-construction-boundary-noref.md
[reuse-efficiency]: ../../work/plans/features/closed/2026-09-24-preparation-reuse-efficiency-noref.md
[separate-compilation]: ../reference/separate-compilation.md
