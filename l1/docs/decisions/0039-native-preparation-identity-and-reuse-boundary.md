# ADR-0039: Native Preparation Identity and Reuse Boundary

- Decision date: 2026-09-11
- Last edited: 2026-09-21
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

Machine-local toolchain and artifact memos are accelerators. Reliable file identity/change metadata can reuse prior
content checks; absent, malformed or stale memo records cause fresh validation. Toolchain memo selection includes `D`,
so implementation changes cannot inherit old observation rules. There is no host identifier, cross-host portability
promise, metadata-preserving-mutation guarantee or whole-host installation fingerprint.

Managed artifact validation checks the complete manifest inventory, relative containment, sizes/digests and exact
selected semantic bytes. Native contents remain semantically opaque; `.l1m` parsing, fingerprints, graph and lifecycle
validation remain authoritative.

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
- Old discovery memos missing runtime target evidence are reobserved; compiler-content identity changes keep old
  profiles separate without migration.
- Working compiler/stdlib/runtime edits conservatively select a new native profile.
- Header selection changes, including generated checking/real/float branches and earlier shadow candidates, invalidate
  reuse when detected by the adapter.
- External mutation concurrent with validation/consumption and copied/shared cache portability are unsupported.
- Native integrity checks do not authenticate caller-owned object/interface pairs or infer compatible ABIs.

## Related Plans

- [l1/work/plans/refactors/closed/2026-09-15-native-identity-environment-text-reassessment-noref.md][environment-identity]

- [l1/work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][preparation-plan]

- [l1/work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md][preparation-economy]

## Current Docs

- [docs/specs/compiler/cli-contract.md][cli]
- [l1/docs/reference/stdlib-preparation.md][preparation]
- [l1/docs/reference/c-backend-design.md][backend]
- [l1/docs/reference/separate-compilation.md][separate-compilation]

[backend]: ../reference/c-backend-design.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[environment-identity]: ../../work/plans/refactors/closed/2026-09-15-native-identity-environment-text-reassessment-noref.md
[preparation]: ../reference/stdlib-preparation.md
[preparation-economy]: ../../work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md
[preparation-plan]: ../../work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md
[separate-compilation]: ../reference/separate-compilation.md
