# ADR-0038: Bundled Semantic Inputs and Local Native Preparation

- Decision date: 2026-09-11
- Last edited: 2026-09-24
- Status: Accepted

## Context

Compile-only imports require authoritative interfaces, while native consumers need compatible stdlib objects and runtime
support. Requiring one installed native configuration couples semantic usability to a host compiler and checking mode. A
second semantic cache or a hierarchy of installed/system/user native stores would add ownership and recovery rules
without changing the compiler's semantic authority.

## Decision

The toolchain owns the complete verified bundled semantic interface set and all inputs needed to rebuild native support.
Repository `build-stage1` supplies public headers and generates those interfaces with the new frontend independently of
native L1 program-runtime construction. Ordinary semantic commands do not hash sources to prove bootstrap freshness;
developers rebuild bootstrap after editing interface-generating inputs.

Managed interfaces occupy exactly the bundled directory's ordered system-root position, preserving explicit interface
authority, system-before-project source order, and `L1_SYSTEM`. Explicit system roots replace the default root list but
do not disable managed providers when filesystem identity proves that a selected root is the bundled directory.
Supported aliases qualify; copied contents or unavailable identity do not. Earlier custom providers retain priority.

`--no-managed-stdlib` disables automatic bundled `std.*` and `sys.*` interfaces in source-resolving modes. Explicit
interfaces remain authoritative, requested targets stay source-backed, and compile-only still requires imported
interfaces. Source bootstrap and intentional source consumers use this opt-out. It is invalid in standalone link and
explicit preparation modes and is independent of native runtime preparation and `--no-auto-prepare`. Standalone link
resolves explicit objects, ordered `-I` roots, then known bundled managed providers, with no source fallback or project
discovery.

Native support is derived on demand into one selected local cache: CLI, then `L1_STDLIB_CACHE`, then a build-local or
installed platform per-user default. Only its `v1/` subtree is Dea-owned. Profiles contain exact selected semantic
copies, matching opaque objects, complete matching runtime support, and a completion manifest published last. Public
headers remain toolchain inputs; generated C is optional scratch. There is no installed native profile correctness
dependency.

An unusable explicit root fails. An unavailable implicit default permits a valid readable hit or fresh command-private
support for automatic consuming commands. Explicit preparation requires usable persistent storage; no-auto mode requires
valid reusable support. Installed payload overlap is rejected, including aliases.

Same-key incomplete work serializes and rechecks through a process-lifetime lock. Completed corruption is never consumed
or automatically replaced. Automatic consumers use fresh support and show eligible force-repair guidance. Forced
replacement and manual disposal require external serialization. The service has no cache-wide lock, generations, reader
pinning, cleaner/scrubber, migration, shared/system store, or application cache.

## Rationale

Directory identity gives equivalent root selections the same provider behavior without promoting copied trees to
toolchain authority. An explicit opt-out preserves intentional source workflows without overloading root selection or
native preparation controls. Existing source callers must migrate to the opt-out when naming the bundled directory.

Semantic interfaces describe the shipped language contract independently of native compiler choice. One disposable
native store keeps ownership narrow while ordinary misses remain normal compiler work. Exact semantic copies preserve
canonical sibling pairing without re-emission. Private fallback keeps native correctness independent of persistent
storage when the configuration remains compilable. Per-key coordination suffices for absent/incomplete publication;
explicit replacement avoids a new concurrent-reader protocol.

## Consequences

- Bootstrap and installed payloads must provide verified semantic artifacts and rebuild inputs.
- Native consumers can select another supported compiler/configuration without changing semantic authority.
- Explicit providers, lifecycle/fingerprint validation, opaque native inputs, and caller-owned external operands retain
  their contracts.
- Build/run keep-C regenerates canonical bundled C rather than trusting cached scratch.
- Install/dist remain separate productization work; runtime developer archives remain an explicit workflow.
- Deleting only the owned cache subtree changes preparation cost, not successful compilation semantics.

## Related Plans

- [l1/work/plans/features/2026-09-24-preparation-reuse-efficiency-noref.md][reuse-efficiency] (Phase 1; later phases
  active)

- [l1/work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][preparation-plan]

- [l1/work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md][preparation-economy]

## Current Docs

- [docs/specs/compiler/cli-contract.md][cli]
- [l1/docs/reference/stdlib-preparation.md][preparation]
- [l1/docs/reference/separate-compilation.md][separate-compilation]
- [l1/docs/reference/c-backend-design.md][backend]

[backend]: ../reference/c-backend-design.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[preparation]: ../reference/stdlib-preparation.md
[preparation-economy]: ../../work/plans/refactors/closed/2026-09-12-native-preparation-economy-noref.md
[preparation-plan]: ../../work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md
[reuse-efficiency]: ../../work/plans/features/2026-09-24-preparation-reuse-efficiency-noref.md
[separate-compilation]: ../reference/separate-compilation.md
