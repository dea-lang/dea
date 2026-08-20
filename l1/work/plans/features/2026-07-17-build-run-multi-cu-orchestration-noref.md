# Feature Plan

## Fan out build and run across compilation units

- Date: 2026-07-17
- Status: Draft
- Title: Rebuild build and run on the multi-compilation-unit APIs
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative]
- Subsystem: CLI / module graph / build orchestration / execution
- Modules:
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/link_driver.l0`
  - `l1/compiler/stage1_l0/src/l1c.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `docs/specs/compiler/cli-contract.md`
  - `l1/docs/reference/architecture.md`
  - `l1/docs/reference/c-backend-design.md`
  - `l1/docs/reference/separate-compilation.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/source_paths_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/link_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/fixtures/separate_compilation`
- Related:
  - [`l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md`][module-graph]
  - [`l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md`][fingerprints]
  - [`l1/work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md`][lifecycle]
  - [`l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md`][object-metadata]
  - [`l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md`][compile-only]
  - [`l1/work/plans/features/2026-07-24-per-module-generated-c-mode-noref.md`][generated-c]
  - [`l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md`][link-set]
  - [`l1/work/plans/features/2026-04-24-external-library-linking-cli-noref.md`][external-linking]
  - [`work/plans/bug-fixes/closed/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md`][native-temp-safety]
  - [`docs/specs/compiler/diagnostic-code-catalog.md`][diagnostic-catalog]
- Repro:
  `make -C l1 test-stage1 TESTS="cli_args_test source_paths_test driver_test analysis_test build_driver_test link_driver_test l1c_lib_test"`

## Summary

Convert `--build` and `--run` from one generated C translation unit into dependency-aware orchestration over multiple
Dea compilation units. The source target remains the user-facing root and becomes the selected entry module. Imported
providers may come from authoritative `.l1m` plus sibling `.o` artifacts or from source fallback, according to the
module graph's build/run policy. Joint interface/object reads require a stable-input precondition: callers must
serialize externally against compile-only publication and other same-stem writers.

This plan reuses the compile and standalone-link APIs instead of creating a second graph verifier, lifecycle scheduler,
or wrapper path. It also admits explicit metadata-free relocatable objects through repeatable `--foreign-object`, so
today's unmangled `extern func` bindings and future C FFI can use the same raw-object boundary in build, run, and link
modes.

## Dependencies and Ownership

1. The [module graph][module-graph] owns canonical artifact association, ordered edges, and `MRP_ALLOW_SOURCE_FALLBACK`.
2. [Fingerprints], [lifecycle emission][lifecycle], and [object metadata][object-metadata] define the Dea artifacts that
   this plan mixes with source-built units.
3. [Compile-only production][compile-only] establishes the reusable one-module analysis, C emission, object compilation,
   and interface-emission operations. Build/run may target a temporary artifact root instead of publishing the result.
4. The completed shared [native temporary-workspace safety plan][native-temp-safety] owns atomic reservation and cleanup
   of the build/run private workspace. This plan consumes that settled lifecycle rather than defining another
   temporary-root policy.
5. The [generated-C plan][generated-c] owns byte identity for the shared per-module generator and final removal of the
   legacy whole-program generator. This plan owns retention of the complete build/run C tree.
6. The [link-set plan][link-set] must land first. This plan passes verified Dea objects, foreign objects, and the source
   target's canonical module name to its common link API.
7. This plan owns graph fan-out for `--build` and `--run`, temporary artifact lifetime, source-target entry selection,
   multi-unit `--keep-c`, executable execution, and runtime argument/status forwarding.
8. [External linking][external-linking] later appends libraries, rpaths, and raw host-driver arguments to the same typed
   ordered link-input stream.

## Build and Run CLI Contract

1. Existing source forms remain primary:

   ```text
   l1c --build MODULE [-I ROOT]... [-Cf C_OBJECT]... [-o OUTPUT]
   l1c --run MODULE [-I ROOT]... [-Cf C_OBJECT]... [-- PROGRAM_ARG...]
   ```

2. `-Cf PATH` / `-Cf=PATH` / `--foreign-object PATH` / `--foreign-object=PATH` are repeatable and are valid in `--build`
   and `--run` because both modes link. Each occurrence is retained at its declaration point in the shared typed link
   input stream.

3. `--entry` is not accepted in either mode. The requested source target is always passed to the common link API as the
   entry module. This removes ambiguity even if imported or otherwise included Dea modules also define `main`.

4. `--build` keeps its executable-output behavior and current default executable name. `--run` creates a temporary
   executable, executes it, returns its exit status, and removes it after normal completion or launch failure.

5. Program arguments after `--` remain valid only for `--run`. They are passed unchanged to the generated wrapper's
   process invocation and are never interpreted as graph or linker operands.

6. `-I`, compiler/runtime controls, line-directive controls, and codegen/runtime-checking controls apply consistently to
   every source-backed unit. Link-only `--entry` and standalone positional object operands remain invalid.

## Graph Expansion and Provider Selection

1. Begin with the requested source target and expand its full ordered module closure using `MRP_ALLOW_SOURCE_FALLBACK`.
2. For every non-virtual import, an interface found through explicit `-I` roots remains authoritative. The driver does
   not replace it with source merely because a source implementation is also available.
3. An interface-backed node resolves its sibling `.o` through the canonical artifact association. The object must exist,
   produce valid Dea metadata, name the expected module, and match the interface's whole-module fingerprint.
4. A provider with no selected interface may fall back to source when the graph policy permits it. Missing both forms,
   malformed authoritative interfaces, source/interface identity mismatches, or an interface without a usable sibling
   object fail before the final link.
5. Virtual modules participate in analysis according to their existing built-in rules but do not produce user Dea object
   inputs or lifecycle calls unless their owning implementation already requires one.
6. Ordered side-effect imports remain graph edges even when no declaration is referenced. They affect source build
   order, object verification, initialization, and finalization.
7. An authoritative interface and its sibling object must remain unchanged from interface selection through object
   verification and submission to the common link API. Compile-only publication provides endpoint rollback, not an
   atomic reader-visible snapshot; build/run callers must serialize externally against same-stem publication or
   mutation.

## Source Compilation Fan-Out

1. Topologically order all source-backed nodes dependency-first, with ordered direct-import edges as the deterministic
   tie-breaker. Compile each canonical module once.
2. Reuse the internal one-module compile path from [compile-only production][compile-only] and the exact shared
   per-module generator governed by the [generated-C plan][generated-c]. Each source unit emits only its definitions,
   imported declarations, lifecycle symbols, optional entry bridge, metadata, and fingerprinted interface.
3. Build/run stage generated `.c`, `.o`, and `.l1m` companions beneath the atomically reserved invocation-private
   workspace supplied by the [native temporary-workspace safety plan][native-temp-safety]. They do not publish over a
   user's compile-only artifacts.
4. Downstream source units analyze against the staged interfaces of already compiled source providers while continuing
   to honor authoritative `-I` providers chosen during graph expansion.
5. Interface-backed provider objects are caller-owned inputs. Build/run inspect and forward them unchanged and never
   replace, rename, or delete them. The caller-owned interface/object pair remains stable for the complete joint-read
   interval described above.
6. Any analysis, emission, object compilation, interface verification, or graph-consistency failure aborts the fan-out,
   removes invocation-owned temporaries, and does not invoke the final host linker.

## Common Link and Entry Selection

1. Supply every source-built and interface-backed Dea object to the common link API together with the source target's
   canonical module name as the explicit entry selection.
2. The target must define a resolved, zero-parameter, non-extern source `main` and therefore carry `HAS_ENTRY` plus
   `I5entry`. Another module's `I5entry` never substitutes for a target without an eligible bridge.
3. Multiple entry-eligible modules are allowed because the target selects exactly one. Only the target bridge is
   invoked; all Dea modules still receive dependency-ordered initialization and reverse-order finalization.
4. Forward foreign objects through the common classification path. They may satisfy ordinary unmangled external symbols
   but never become graph providers, entry candidates, or lifecycle participants.
5. Preserve the common link API's typed input order. Source-built and interface-backed Dea operands occupy their
   deterministic graph positions; user-declared foreign objects keep their relative declaration order.
6. The wrapper, exact runtime link inputs, object classification, fingerprint checks, and final host compiler invocation
   remain owned by the [link-set plan][link-set]. Normal families receive one selected archive; TinyCC receives the
   complete variant-matched raw-object set when available, with archive fallback. Build/run surface the common link
   API's structured failures without rewriting them.
7. The common link executor accepts explicit wrapper and capture paths and never allocates or cleans a workspace.
   Build/run derives those paths beneath its atomically reserved invocation-private workspace and retains ownership of
   whole-workspace cleanup. The standalone link adapter's output-local transaction is not reused here.

## Multi-Unit Generated C Retention

The existing single generated-C `--keep-c` result cannot represent a multi-unit build. In build and run modes this plan
changes it to retain the complete generated-C tree:

1. `--build -o PATH --keep-c` retains C under `PATH.dea-c/`. A build using the default executable name uses that name
   with the same `.dea-c` suffix.
2. `--run --keep-c` retains C beneath a deterministic working-directory path based on the source target's canonical
   module name, with an existing path handled by the same explicit replacement/error policy chosen for build output.
3. Module C files mirror canonical dotted paths beneath the retained root, and the generated process wrapper is named
   `__dea_wrapper.c` at its root.
4. Every retained module C file is the exact byte sequence passed to the host compiler and is byte-identical to `--gen`
   and `-c --keep-c` for the same target module, resolved graph, fingerprints, code-generation settings, and compiler
   version. Retention copies bytes; it does not regenerate or rewrite C.
5. Only generated C is retained. Temporary objects, staged interfaces, wrapper objects, and the run executable are still
   removed unless another owning option explicitly documents their retention.
6. CLI and backend references document the directory result and the migration from the legacy single-file behavior.

## Implementation Phases

### Phase 1: Shared orchestration interfaces

Extract the reusable one-module compile operation and common link request/result types. Keep standalone `-c` and
`--link` behavior unchanged while adding temporary artifact roots and explicit entry selection for callers.

### Phase 2: Build/run graph fan-out

Expand `MRP_ALLOW_SOURCE_FALLBACK`, resolve interface/object pairs, compile source-backed nodes once in deterministic
order, and pass the complete object set to the common linker.

### Phase 3: Foreign objects and execution

Accept repeatable `--foreign-object`, preserve ordered typed inputs, execute run-mode output with unchanged arguments,
and propagate launch failures and program status.

### Phase 4: Retention, cleanup, and documentation

Implement the multi-unit `--keep-c` tree, make all invocation-owned cleanup paths idempotent, and update CLI,
architecture, C-backend, and separate-compilation references.

## Diagnostics

1. Provisionally reserve `L1C-2130` through `L1C-2149` for build/run graph expansion, interface/object association,
   source fan-out, selected-target entry failures, retained-C output, temporary cleanup, execution, and mode-specific
   option diagnostics.
2. Reuse graph, fingerprint, metadata, classification, wrapper, and host-link diagnostics from their owning plans when
   the meaning is unchanged. Do not mint a build/run duplicate for the same failed invariant.
3. Re-check `L1C-2130` through `L1C-2149` against the live [diagnostic catalog][diagnostic-catalog] immediately before
   implementation and move the whole provisional block if any code has been assigned.

## ADR Impact

- Decision: Run `--build` and `--run` through one verified multi-compilation-unit orchestration pipeline.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Graph fan-out, provider selection, entry selection, and link ordering form the durable L1 multi-unit
    execution boundary.
- Decision: Use the canonical module graph and provider rules for build/run graph expansion.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0018-canonical-artifact-association-and-module-graph.md`
  - Rationale: ADR-0018 already defines artifact identity, graph discovery, and provider authority.
- Decision: Make `.l1m` artifacts active build/run inputs rather than a future-only interface format.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0014-module-interface-artifact.md`
  - Rationale: ADR-0014 must reflect the interface artifact's operational role in multi-unit orchestration.
- Decision: Replace ADR-0018's deferred orchestration statements with the implemented build/run graph behavior.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0018-canonical-artifact-association-and-module-graph.md`
  - Rationale: The plan settles work that ADR-0018 currently describes as future integration.
- Decision: Compose per-module backend and lifecycle entrypoints across every source unit selected by build/run.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0020-per-module-backend-and-lifecycle-abi.md`
  - Rationale: ADR-0020 must record how its module-local ABI participates in whole-graph build and execution.
- Decision: Keep each authoritative `.l1m` and sibling `.o` pair stable through selection, verification, and link
  submission.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md`
  - Rationale: ADR-0022 provides endpoint rollback rather than a reader snapshot, so build/run must serialize
    externally.
- Decision: Retain module C that is byte-identical to corresponding `--gen` and `-c --keep-c` output.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: This contributes the build/run portion of the generated-C child plan's cross-mode identity ADR.
- Decision: Stage build/run artifacts in the shared atomically reserved native workspace.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/`
  - Rationale: The shared native-workspace plan owns reservation, trust validation, and cleanup policy.

## Non-Goals

1. Reimplementing link graph verification, wrapper generation, lifecycle order, or object classification.
2. Publishing every source fallback as a persistent compile-only artifact set.
3. Allowing `--entry` to override the requested build/run source target.
4. Treating foreign objects as Dea modules or allowing a foreign C `main` to replace the wrapper.
5. Adding external libraries, rpaths, package discovery, archives through `--foreign-object`, or arbitrary raw link
   arguments.
6. Parallel source compilation, persistent build caches, incremental invalidation, or a package-level build manifest.

## Verification Criteria

01. A source target and multiple source-backed dependencies compile as distinct translation units, link, and run.
02. Mixed source-backed and authoritative interface/object providers use the documented precedence and verify matching
    module identities and whole-module fingerprints. A provider's `.o + .l1m` pair remains usable when its canonical
    `.c` is absent.
03. Missing sibling objects, mismatched interfaces and objects, malformed metadata, cycles, and missing providers fail
    before the host linker and clean invocation-owned artifacts.
04. Two or more modules may define an entry-eligible `main`; build/run select the requested source target, invoke only
    its `I5entry`, and do not issue the standalone link mode's ambiguous-entry diagnostic.
05. A target without an entry-eligible bridge fails even when another linked module supplies `I5entry`.
06. Init calls are dependency-first, fini calls are their exact reverse, and side-effect-only imports remain ordered.
07. A tiny metadata-free C provider satisfies today's unmangled `extern func` through repeatable `--foreign-object` in
    both `--build` and `--run`; it receives no entry or lifecycle calls.
08. A valid or malformed Dea object cannot bypass verification through `--foreign-object`, and a foreign C `main` is
    rejected through the common classification path.
09. Run-mode arguments and the selected entry status round-trip unchanged; launch and host-link failures remain
    distinguishable.
10. `--keep-c` retains the documented mirrored C tree plus `__dea_wrapper.c`, while objects, staged interfaces, and run
    executables follow their normal cleanup rules.
11. Each retained module C file is byte-identical to the corresponding `--gen` and `-c --keep-c` output for identical
    graph and code-generation inputs.
12. Mixed typed inputs preserve their documented deterministic ordering for later extension by libraries and raw
    host-driver arguments.
13. Focused normal and trace tests pass, followed by `make -C l1 test` once implementation is complete.
14. Concrete diagnostics are registered in the shared catalog before closure.
15. The build/run contract records the stable-input precondition for every interface/object pair, and tests do not
    assume compile-only publication supplies a reader-visible snapshot.

[compile-only]: closed/2026-07-17-compile-only-artifact-production-noref.md
[diagnostic-catalog]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[external-linking]: 2026-04-24-external-library-linking-cli-noref.md
[fingerprints]: closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[generated-c]: 2026-07-24-per-module-generated-c-mode-noref.md
[initiative]: ../../initiatives/0001-separate-compilation-and-linking.md
[lifecycle]: closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md
[link-set]: closed/2026-07-17-link-set-driver-and-wrapper-noref.md
[module-graph]: closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[native-temp-safety]: ../../../../work/plans/bug-fixes/closed/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md
[object-metadata]: closed/2026-07-17-object-metadata-emission-and-readers-noref.md
