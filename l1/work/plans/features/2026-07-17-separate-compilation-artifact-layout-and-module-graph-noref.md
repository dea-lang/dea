# Feature Plan

## Define separate-compilation artifacts and the module graph

- Date: 2026-07-17
- Status: Draft
- Title: Define separate-compilation artifact layout, interface discovery, and the module graph
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: [l1/work/initiatives/0001-separate-compilation-and-linking.md][initiative]
- Subsystem: Driver / module discovery / interface closure / artifact paths
- Modules:
  - `l1/compiler/stage1_l0/src/ast.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/compiler/stage1_l0/src/module_interface.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/sem_context.l0`
  - `l1/compiler/stage1_l0/src/name_resolver.l0`
  - `l1/compiler/stage1_l0/src/signatures.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/interface_emitter.l0`
- Test modules:
  - `l1/compiler/stage1_l0/tests/source_paths_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/name_resolver_test.l0`
  - `l1/compiler/stage1_l0/tests/signatures_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_replay_test.l0`
- Related:
  - [l1/work/plans/features/closed/2026-04-24-separate-compilation-driver-surface-noref.md][foundation]
  - [l1/work/plans/features/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md][fingerprints]
  - [l1/work/plans/features/2026-07-17-compile-only-artifact-production-noref.md][compile-only]
  - [l1/work/plans/features/2026-07-17-object-metadata-emission-and-readers-noref.md][object-metadata]
  - [l1/docs/specs/compiler/module-interface-format.md][module-format]
  - [docs/specs/compiler/diagnostic-code-catalog.md][diagnostic-catalog]
- Repro:
  `make -C l1 test-stage1 TESTS="source_paths_test driver_test name_resolver_test signatures_test analysis_test interface_test interface_replay_test"`

## Summary

Direct `.l1m` replay currently works only when callers pre-parse dependency-free provider interfaces. That is not a
usable separate-compilation boundary: the driver does not discover interfaces from `-I`, rejects every transitive
`require` or `link` record, leaves implementation-tier `link` entries empty, and has no canonical association between a
module and its `.c`, `.o`, and `.l1m` artifacts.

This plan introduces one deterministic module-graph and artifact-path layer beneath compile-only, standalone linking,
and build/run fan-out. It resolves imported modules according to an explicit interface-first policy, loads the
transitive interface closure, records both semantic dependencies and ordered source imports, and gives later plans
stable APIs to consume. It does not make `-c`, `--link`, `--build`, or `--run` operational by itself.

## Dependencies and ordering

1. The [closed foundation plan][foundation] supplies direct interface replay and the reserved `-c` / `-I` CLI model.
2. This plan and the [fingerprint plan][fingerprints] may land in either order. This plan carries dependency fingerprint
   strings as opaque provider-module values; it does not compute or validate them.
3. The per-module backend/lifecycle plan may begin after this graph exists.
4. [Object metadata][object-metadata] consumes ordered direct-import edges only after this plan and fingerprinting are
   complete.
5. [Compile-only artifact production][compile-only] consumes the artifact mapping and `RequireInterface` resolution
   policy. It does not own either contract.

## Defaults chosen

### Canonical artifact association

1. A canonical dotted module name maps to a relative artifact stem by replacing each `.` separator with `/`. Module
   `foo.bar` therefore maps to `foo/bar` beneath a caller-selected artifact root.
2. The canonical artifact set for that stem is `foo/bar.c`, `foo/bar.o`, and `foo/bar.l1m`. All three files are siblings
   and identify the same module.
3. An explicit compile-only `-o` path is the canonical object path. Replacing its final `.o` suffix with `.c` or `.l1m`
   selects the two companion paths. Plan implementation rejects an explicit output that is not a regular `.o` path; it
   does not guess from an extensionless or directory path.
4. Without `-o`, the consuming mode supplies its artifact root and uses the dotted-module mapping above. The
   compile-only and build/run plans own selection of their respective roots and creation of parent directories.
5. Filesystem source paths, search-root spellings, and local import aliases never enter the artifact identity. The
   module header and graph keys use only the canonical dotted module name.
6. This plan returns path values and associations only. Atomic publication of the three-file set belongs to the
   [compile-only plan][compile-only].

### Source and interface precedence

1. The requested compilation target is always a source implementation selected by the caller; an interface cannot
   replace the module being compiled.
2. For each imported canonical module, search explicit `-I` roots in declaration order for the dotted relative path with
   an `.l1m` suffix. The first existing candidate wins, even when source for the same module also exists.
3. A selected interface is authoritative. An unreadable file, invalid UTF-8, parse failure, or header/module-name
   mismatch is an error and must not silently fall back to source.
4. If no interface exists, the resolver applies a mode policy supplied by its caller:
   - `RequireInterface` reports a missing-interface diagnostic. Compile-only uses this policy for every non-virtual
     imported module.
   - `AllowSourceFallback` resolves source through the existing system-roots-before-project-roots policy and preserves
     declaration order inside each root tier. Build/run fan-out uses this policy and schedules the source module as a
     compilation node.
5. Compiler-synthesized prelude modules retain their existing virtual-module handling and do not require `.l1m` files.
6. Programmatic direct-interface registries remain supported for focused semantic tests. Duplicate entries in that
   registry continue to use `DRV-0071`; filesystem discovery uses deterministic first-root-wins selection instead of
   treating lower-priority matches as ambiguity.

### Module graph and dependency tiers

1. One graph node represents one canonical module and records exactly one selected origin: source path, interface path,
   or compiler-synthesized module. A node also carries its canonical artifact association when real artifacts apply.
2. Source nodes retain direct imports in source declaration order, including imports that contribute no referenced
   symbol. These ordered edges are the future lifecycle and side-effect order. Sorting or deduplicating dependency
   manifests must not overwrite this sequence.
3. Interface nodes contribute manifest edges:
   - `require` is a public-surface dependency and activates the provider interface for semantic replay.
   - `link` is an implementation-only dependency and creates a graph obligation without opening provider names into the
     importing module's semantic environment.
4. The loader resolves provider modules named by both tiers recursively. It activates only the interfaces required for
   semantic replay, while retaining every resolved `link` node for later artifact and link-set construction.
5. A provider symbol used in both tiers appears only in `require`. Within each tier, entries remain sorted and
   deduplicated by `provider_module::symbol` for deterministic `.l1m` emission.
6. Dependency entry values are module-level expectations. Every entry naming one provider repeats that provider
   interface's whole-module fingerprint; no code in this plan computes a per-symbol hash. Until the parallel
   [fingerprint plan][fingerprints] lands, the resolver may carry the provider's existing placeholder value opaquely.
7. Sorted per-symbol interface records cannot reconstruct side-effect-only imports or sibling order. The graph therefore
   exposes ordered direct source-import edges separately; the [object-metadata plan][object-metadata] serializes that
   ordered module-level sequence into provider objects for later standalone linking.
8. Source and interface cycles use the existing import-cycle policy and are reported with the complete canonical module
   chain. A cache hit is not a cycle, and a failed node is never marked successfully resolved.

## Goal

1. Give all later separate-compilation modes one canonical module-to-artifact mapping.
2. Replace caller-supplied direct-only interface replay with deterministic filesystem discovery and recursive closure
   loading.
3. Preserve the distinction between public-surface `require` dependencies, implementation-only `link` dependencies, and
   ordered direct imports needed for lifecycle semantics.
4. Populate implementation-tier dependencies from resolved cross-module implementation references instead of leaving
   `link` syntax-only.
5. Keep graph construction independent of object emission, wrapper generation, and the host linker.

## Implementation phases

### Phase 1: Artifact-path and resolution types

Add focused types for canonical artifact sets, module origins, resolution policy, graph nodes, and graph edges. Extend
`source_paths.l0` with separate source and interface relative-path helpers rather than overloading the current `.l1`
resolver. Validate canonical dotted module names before constructing any path, normalize only module separators, and
return explicit diagnostics rather than partially initialized path sets.

The graph API must expose deterministic iteration independent of hashmap slot order. Node lookup may remain map-backed,
but public enumeration returns canonical module-name order. Direct import edges retain their source order through a
separate accessor.

### Phase 2: Interface-first discovery and transitive closure

Replace the direct-provider-only branch in `driver.l0` with a resolver that accepts ordered interface roots and a source
fallback policy. Parse each selected interface once, verify its header identity, cache it by canonical module name, and
recursively visit provider modules named by `require` and `link` entries.

Retire the current blanket `DRV-0070` rejection once recursive closure tests pass. Keep supplied-interface fixtures as
an adapter over the same graph loader so test-only and filesystem-backed paths cannot develop different dependency
semantics.

### Phase 3: Ordered imports and dependency population

Record every source module's `Import` declarations in their original sequence before name resolution flattens the
visible symbol surface. Extend semantic resolution to record resolved cross-module symbol references. During interface
projection:

1. collect cross-module references in exported signatures, layouts, aliases, top-level binding types, and exported const
   literals into `require`;
2. collect other resolved cross-module implementation references into `link`;
3. remove a `link` entry when the same provider symbol is present in `require`;
4. attach the provider interface's whole-module fingerprint value when one is available; and
5. sort and deduplicate only the emitted manifest groups, never the ordered direct-import edge list.

Unresolved or ambiguous references continue to be owned by their current semantic diagnostics and must not produce
speculative graph edges.

### Phase 4: Integration boundary and documentation

Expose the completed graph through analysis/library entry points used later by compile-only, metadata emission, and
build/run fan-out. Update the module-interface format documentation for recursive closure and populated `link` records,
while leaving fingerprint spelling and verification to the [fingerprint plan][fingerprints]. Keep CLI help explicit that
`-c` remains reserved until the [compile-only plan][compile-only] lands.

## Diagnostics

1. This work extends the established `DRV-0070` to `DRV-0089` separate-compilation discovery area. `DRV-0070` and
   `DRV-0071` are already assigned, so provisionally use the remaining `DRV-0072` to `DRV-0089` slots rather than
   reserving another family block.
2. Expected cases include invalid interface roots or module paths, missing required interfaces, unreadable interfaces,
   interface header mismatches, failed transitive resolution, duplicate graph identity, and dependency cycles whose
   existing generic driver code is not specific enough.
3. Parser syntax failures retain their existing `PAR-*` diagnostics. Existing source lookup failures retain `DRV-0010`
   through `DRV-0040` when their meaning remains exact.
4. The `DRV-0072` to `DRV-0089` range is provisional. Re-check the live [diagnostic catalog][diagnostic-catalog]
   immediately before implementation and choose another free range if any slot has been assigned in the meantime.

## Non-goals

1. Computing, spelling-validating, or re-hashing whole-module fingerprints.
2. Per-module C backend emission or lifecycle entry points.
3. Embedding or reading object metadata.
4. Making compile-only mode write or publish artifacts.
5. Selecting an executable entry module, topologically ordering lifecycle calls, or invoking the host linker.
6. Build caches, timestamp-based incremental compilation, or a package manifest.
7. Inferring ordered lifecycle edges from sorted `.l1m` dependency entries.

## Verification criteria

01. `foo.bar` maps deterministically to sibling `foo/bar.c`, `foo/bar.o`, and `foo/bar.l1m` beneath an artifact root; an
    explicit `.o` path selects the companion stems without rewriting its directory.
02. The entry module remains source-backed even if a matching `.l1m` exists.
03. An imported module's first matching `-I` interface wins over source and lower-priority interface roots.
04. A malformed, unreadable, or identity-mismatched selected interface fails without source fallback.
05. `RequireInterface` rejects a missing imported interface, while `AllowSourceFallback` selects and schedules source
    using the existing source-root precedence.
06. A chain of interface `require` dependencies replays transitively without `DRV-0070`.
07. Interface `link` dependencies populate graph obligations without introducing imported names into semantic scope.
08. Public-surface uses emit `require`; implementation-only uses emit `link`; a symbol used by both appears only in
    `require`.
09. Repeated uses are deduplicated and emitted deterministically, while direct import edges preserve source declaration
    order and retain unused side-effect-only imports.
10. Every dependency entry for one provider carries the same provider whole-module fingerprint value; no per-symbol hash
    is computed.
11. Graph enumeration is stable across repeated runs and independent of hashmap insertion order.
12. Focused normal and trace tests pass, followed by `make -C l1 test` once implementation is complete.
13. Concrete new diagnostic assignments are added to the shared catalog in the implementation change.

[compile-only]: 2026-07-17-compile-only-artifact-production-noref.md
[diagnostic-catalog]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[fingerprints]: 2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[foundation]: closed/2026-04-24-separate-compilation-driver-surface-noref.md
[initiative]: ../../initiatives/0001-separate-compilation-and-linking.md
[module-format]: ../../../docs/specs/compiler/module-interface-format.md
[object-metadata]: 2026-07-17-object-metadata-emission-and-readers-noref.md
