# Feature Plan

## Expose semantic dependencies through P1689R5 and a Make adapter

- Date: 2026-10-21
- Status: Draft
- Title: Add L1 semantic dependency discovery with a neutral P1689R5 report and external Make composition
- Kind: Feature
- Parent Initiative: `l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md`
- Priority: Medium
- Subsystem: Compiler CLI, module resolution, separate compilation and external build integration
- Modules:
  - `l1/compiler/src/l1c.l0`
  - `l1/compiler/src/cli_args/`
  - `l1/compiler/src/driver/resolve.l0`
  - `l1/compiler/src/module_graph.l0`
  - `l1/compiler/src/module_graph/order.l0`
  - `l1/compiler/src/preparation/consumer.l0`
  - Proposed: `l1/compiler/src/dependency_report.l0`
  - Proposed: `l1/scripts/p1689_make.py`
- Test modules:
  - `l1/compiler/tests/cli_args_test.l0`
  - `l1/compiler/tests/driver_test.l0`
  - `l1/compiler/tests/module_graph_test.l0`
  - Proposed: `l1/compiler/tests/dependency_report_test.l0`
  - Proposed: `l1/compiler/tests/l1c_dependency_discovery_test.py`
  - Proposed: `l1/tests/test_p1689_make.py`
- Related:
  - `l1/work/plans/features/closed/2026-09-30-explicit-profile-artifacts-noref.md`
  - `l1/work/plans/refactors/closed/2026-10-21-managed-profile-client-integration-noref.md`
  - `docs/specs/compiler/cli-contract.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`

## Summary

Complete Phase D of [l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md][initiative] by exposing the
existing resolver's dependency knowledge as P1689R5 JSON, then adding a small external Make adapter. The compiler owns
semantic resolution and interface validation; the adapter and invoking project own build configuration, destinations,
freshness, scheduling and command execution. Existing `--build` and `--run` remain convenient compositions.

Use separate discovery and compilation inputs. Discovery receives project source roots and intentionally prebuilt
interface roots. Compilation additionally receives the local generated-interface root after providers have been updated.
This is an integration convention using existing precedence, not a new compiler selection policy.

The medium priority reflects the remaining composable-build capability required to close Initiative 0010. This draft
authorizes no implementation, remote write, release or workflow dispatch.

## ADR Impact

- Decision: Expose compiler-produced P1689R5 scheduling facts with an external Make consumer and optional explanatory
  Dea metadata.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The public dependency boundary, extension rules and separation of compiler facts from build execution are
    lasting integration contracts. Share this decision with the parent initiative.
- Decision: Preserve interface-first provider authority while using separate discovery and compilation roots.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0018-canonical-artifact-association-and-module-graph.md`
  - Rationale: The existing resolver already supplies the needed behavior. The adapter must distinguish its generated
    outputs from intentionally prebuilt inputs without adding source-over-interface precedence.
- Decision: Add a flag-selected L1 dependency-discovery mode and output-mapping option.
  - Scope: Shared
  - Disposition: Amend ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: Register the L1 extension while preserving existing option meanings, primary-mode grammar and exit codes.

## Current State

Phases A through C are complete. Canonical L1 can construct explicit profiles, compile individual source modules to
`.o + .l1m`, and perform verified standalone linking. Its resolver already records selected origins, exact source
imports, interface dependency closure and deterministic dependency order. See
[l1/docs/reference/architecture.md][architecture] and [l1/docs/reference/separate-compilation.md][compilation].

There is no stable public dependency-discovery report. Compile-only requires verified provider interfaces, so its
successful execution cannot discover the order needed for a clean first build by itself. A source-fallback analysis can
discover that order before the interfaces exist.

Imported modules remain interface-first. An old generated `model.l1m` can hide changes in `model.l1` only when the old
interface is visible through a selected interface input. An output destination never implicitly becomes an input root;
the requested target stays source-backed. Existing native build/run avoids previous local outputs by using a fresh
workspace. Preserve these rules.

## Draft Defaults

The spellings below are proposed public defaults for review, not implemented commands:

```text
l1c --scan-deps MODULE --artifact-root BUILD [-Rp SOURCE]... [-Rs SYSTEM]...
    [-I PREBUILT]... [--profile PROFILE] [--no-managed-stdlib] [-o REPORT]
```

- `--scan-deps` is an L1-only primary mode with one source target and no short alias initially.
- Require `--artifact-root PATH` to map canonical dotted source-module names to future sibling `.o` and `.l1m` paths. It
  affects report paths only and never adds an interface root or creates native outputs.
- Without `-o`, write one UTF-8 JSON document to stdout. With `-o`, write the exact report file. Keep diagnostics and
  progress on stderr; retain exit 2 for argument errors and exit 1 for analysis/report failures.
- Accept source-root and intentional interface-root controls with their current meanings. With `--profile`, select its
  verified semantic inventory under the existing exact-profile contract. Preserve explicit `-I` precedence. Do not
  construct native support, probe the host compiler, consult managed native caches or invoke native tools during scans.
- Preserve default bundled semantic selection without a profile. Profile support for this new mode does not extend
  `--check`, `--gen` or `--emit-interface`.
- V1 reports the normal two-output compilation contract. Retained-C discovery and arbitrary per-module output mappings
  are deferred; existing `--compile -o` and `--keep-c` behavior remains unchanged.
- Publish a report only after successful analysis and serialization. File output must not overwrite selected source,
  interface or profile inputs. Failure must not leave a partial accepted report or silently reuse an older report.

## Neutral Report Contract

Use the [P1689R5 format][p1689] with `version: 1` and `revision: 0`. Pin that revision in tests and documentation; do
not claim ISO standardization or redefine its version fields for Dea-specific semantics.

| Selected Dea fact                         | P1689R5 projection                                                    |
| ----------------------------------------- | --------------------------------------------------------------------- |
| Future source compilation                 | One entry in `rules`                                                  |
| Planned `.o`                              | `primary-output`                                                      |
| Planned sibling `.l1m`                    | `outputs[]` and `provides[].compiled-module-path`                     |
| Source module identity and selected `.l1` | `provides[].logical-name` and `provides[].source-path`                |
| Required module/interface                 | `requires[]` with its canonical name and known or planned `.l1m` path |

Emit one rule per selected source-backed module, in deterministic dependency-first order. Preserve each selected source
path and the caller-selected output mapping. Use the core working-directory context to make relative paths unambiguous.
Reject conflicting output ownership. Prebuilt/profile interfaces are requirements, not fabricated future compilations;
virtual modules have no filesystem artifact obligations.

P1689 `requires` denotes prerequisites of the future compilation, not only Dea's `.l1m` `require` tier. Include the
complete interface requirements needed by strict compile-only analysis, including closure through prebuilt providers and
graph-loaded link-only interfaces. Do not flatten away an obligation because it is absent from the consumer's semantic
environment. A source action reached through a prebuilt interface must still precede any action needing its generated
interface.

Use core fields for every essential scheduling fact. Optional `_dea_...` annotations may preserve selected origin,
ordered effective roots, and exact direct-import edges/order for inspection. Preserve the full resolver result
internally and document these annotations separately; neither the Make adapter nor correct scheduling may require them.
Keep a separate annotation version if needed. Removing all annotations must leave a correct build.

Keep `.l1m` authoritative for fingerprints, provider consistency, entry selection and ordered lifecycle semantics.
Continue using `l1c --link`; report order and optional annotations do not become replacement link metadata. P1689
compatibility alone does not establish automatic CMake or other build-tool integration.

## Discovery and Compilation Inputs

For a source chain `app -> model -> helper`, use these distinct input sets:

| Operation | Inputs                                                                                                       |
| --------- | ------------------------------------------------------------------------------------------------------------ |
| Discover  | Source roots, intentional prebuilt `-I` roots, selected profile or bundled semantics                         |
| Compile   | The same prebuilt roots in the same order, followed by the validated local generated-interface root          |
| Link      | Existing explicit source objects, validated interface roots, profile/native inputs and explicit target entry |

Do not feed the generated-interface root back into source discovery. In particular, after adding `import helper` to
`model.l1`, an old `BUILD/model.l1m` must not hide that edge merely because a previous build populated BUILD. Explicitly
passing BUILD as a discovery `-I` root must still retain the ordinary interface-first behavior; do not silently strip
roots or reinterpret selected interfaces as stale.

Adding the generated root for compilation or linking must not change discovery's selected prebuilt providers. Give the
adapter the same `--artifact-root BUILD` as the scanner, as caller configuration rather than a Dea annotation. Validate
source-action output mappings against that root. For each required provider without a source action, check the canonical
`BUILD/<module-path>.l1m` candidate. Require that candidate to be absent, including when it is a dangling link,
non-regular path or alias of a selected input. V1 conservatively requires disjoint generated and prebuilt provider sets,
even when an earlier explicit prebuilt root would currently mask a collision. This avoids reproducing resolver
precedence in the adapter. Diagnose conflicts before the inner Make build and require a clean or fresh artifact root; V1
does not delete old outputs or build a filtered interface tree. Unreferenced leftover files do not require cleanup.
Serialize preflight and the inner build against other writers to the same generated root.

The example Makefile uses one caller-supplied canonical module name for both discovery's `MODULE` and the final link's
`--entry MODULE`. Keep this selection outside P1689; do not infer it from rule order, object filenames or imported
`entry;` markers. A target without an eligible `main` must fail final linking even when an imported module has one.

First-build discovery describes future compilation requirements. It is not a record of what a later invocation actually
consumed. V1 uses a fresh scan and complete conservative prerequisites rather than adding compile-time depfiles.
Actual-consumed-input reporting can follow separately if integration evidence justifies it. Do not claim that a public
interface fingerprint or this report alone proves complete rebuild validity.

## Make Adapter

Implement the adapter after the neutral report and its conformance tests. The proposed `l1/scripts/p1689_make.py` reads
P1689R5 using the Python standard library and emits a Make fragment. It does not parse Dea sources, resolve module names
independently, execute compiler commands or inspect native object bytes. It remains optional repository tooling;
installed `l1c` gains no Python or Make runtime requirement.

- Emit source/interface prerequisites for both outputs of each source action and a deterministic list of source-object
  outputs for the invoking Makefile. Reject unsupported report versions, duplicate producers, conflicting mappings and
  unresolved requirements without a selected existing prebuilt interface. Before accepting the fragment, validate that
  the generated root contains no canonical interface candidates for the report-selected prebuilt provider set.
- Emit explicit grouped action rules for each `.o + .l1m` pair using GNU Make 4.3 or newer, referencing a common
  caller-owned recipe macro. The example Makefile supplies that macro using existing `--compile` with separate
  compilation inputs and a final recipe using existing `--link --entry MODULE` for the scanned canonical target. Do not
  rely on grouped implicit patterns to repair a missing unrequested peer. Deleting either output must rebuild its whole
  pair even when only the other output is requested, and parallel consumers must wait until publication completes. Pass
  the declared source and primary object destination to the recipe even when the interface target triggered it; do not
  derive the object destination from `$@`.
- Run an outer discovery/adaptation step before each inner Make build. Preserve the generated fragment's timestamp when
  its bytes are unchanged, and make that fragment an explicit prerequisite of every source action and final link. A
  changed source/provider selection must invalidate old outputs even when the newly selected input has an older
  timestamp. Conservative whole-graph invalidation is the V1 default. Avoid a self-remaking included-file loop. Fresh
  scans observe source/provider additions, removals, root reordering and newly shadowing interfaces without a
  directory-watch or negative-lookup protocol.
- The invoking Makefile supplies configuration stamps for compiler/options/profile/root changes and compile-action
  prerequisites for runtime headers and other caller-selected native compilation inputs. Final-link prerequisites
  separately cover runtime libraries, foreign inputs and prebuilt objects. Header changes must recompile affected module
  pairs rather than merely relink. Do not infer that every semantic-only bundled interface has a native sibling object.
  Document the supported adapter contract rather than imply universal host dependency discovery.
- Link dependencies include the current source-object set, so implementation-only changes relink even when public
  fingerprints are unchanged. A changed graph must also invalidate the executable when an obsolete source object is
  removed from the set. Preserve intentional prebuilt authority and standalone-link lifecycle validation.
- Escape supported paths for Make independently of JSON encoding. Diagnose path spellings the adapter cannot represent
  losslessly, including line breaks; never silently split paths. Core report support need not shrink to the adapter's
  filename subset.

Timestamp-based rebuilding may conservatively recompile consumers when identical interface bytes are republished.
Content-preserving interface publication, per-symbol invalidation and a persistent incremental database are separate
optimizations, not prerequisites for this adapter.

## Implementation Sequence

1. Register the proposed L1 mode and output-mapping option in the shared CLI contract. Reuse graph analysis, ordering,
   semantic/profile selection and diagnostics; introduce a narrow report projection and serialization boundary.
2. Implement P1689R5 output, protected report publication, deterministic path handling and compiler tests. Keep scans
   independent of generated outputs unless the caller explicitly supplies them as inputs.
3. Add the adapter and outer/inner Make fixture with generated-root preflight and explicit target-entry linking, then
   exercise clean, unchanged and incremental builds using the public report and caller configuration. Keep command
   recipes and host dependency policy in the invoking Makefile.
4. Update current CLI/help/reference documentation only when implemented. At closure create/index the L1 ADR, amend the
   shared CLI ADR, update the covered module-graph ADR's Related Plans, and synchronize the initiative and roadmap.

## Diagnostic-Code Planning

The live [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] registers the explicit-profile area through
`L1C-2199`; the inspected active plans do not reserve the proposed next slice. Provisionally reserve `L1C-2200` through
`L1C-2219` for the new dependency-report CLI/output area: invalid report or mapping configuration, output ownership/path
conflicts, unsupported path representation, and report serialization/publication failures. Reuse existing CLI,
resolution, interface and graph diagnostics where their meanings already apply.

Re-check the entire provisional range against the live catalog and active reservations at implementation time before
assigning final codes. Register only implemented meanings and mark the remainder reserved. Adapter-only malformed-JSON,
unsupported-format and Make-encoding errors are tool diagnostics, not compiler semantic codes.

## Verification Criteria

1. Parse the actual report as UTF-8 JSON and verify P1689R5 fields, version, rule ownership and deterministic output.
   Assert that scans create no native artifacts, managed cache entries or host-tool invocations. Selected profile
   interfaces work without consulting their original bundled sources.
2. Discover clean source chains and diamonds before local interfaces exist. Include side-effect imports, duplicate
   imports, transitive exported types and graph-loaded link-only providers. Missing/malformed authoritative interfaces
   retain existing diagnostics and never fall through to source.
3. Build through the adapter, standalone link and inspect output/lifecycle order. Compare behavior and applicable
   generated module-C bytes against existing explicit-profile and managed composition fixtures; do not require native
   executable byte identity. A target and an imported module both defining `main` must run the target's entry; a target
   without `main` must fail instead of running an imported entry. Rebuild without changes and observe no compilation or
   linking after the scan.
4. Add an import while leaving old generated interfaces in BUILD; discovery excluding BUILD sees the new source edge.
   Also explicitly scan with BUILD on `-I` and confirm unchanged interface-first semantics. Test distinct `-o` and `-I`
   directories and trusted directory aliases.
5. Exercise source/provider additions and removals, a newly appearing earlier provider, reordered roots, changed
   configuration/profile selection and a public-interface-preserving implementation change. Include a newly selected
   provider/source older than existing outputs to verify graph-change invalidation. Removed objects stop participating
   in the link; changed objects still trigger linking. Switch a previously source-built bundled module to profile and
   ordinary bundled selection while its old generated interface remains: preflight must reject a shadowing candidate
   before any compile/link action. After cleaning or selecting a fresh root, verify the intended provider and behavior.
   Include alias and unusable-candidate cases, plus an unreferenced leftover that must not block the build. Changing a
   caller-supplied header prerequisite must recompile its affected module pair. Never accept a previous report after a
   failed scan or preflight.
6. Delete either output of both entry and provider pairs, request only the surviving peer, run parallel consumers, and
   inject compilation/report/adapter failure. Require whole-action rebuilding, publication-before-consumption and
   preservation of prior valid artifacts under existing rollback rules. A missing prebuilt interface fails; missing
   planned source outputs remain valid before the first compile.
7. Remove all `_dea_...` properties and repeat the adapter build. Test malformed reports, unsupported versions,
   duplicate/conflicting providers, output collisions and unsupported Make path spellings before accepting a fragment.
8. Exercise spaces, Unicode, JSON quotes/backslashes, POSIX literal backslashes, Windows drive/UNC and mixed-separator
   spellings, plus genuinely different paths. Keep native-platform and simulated Windows evidence distinct; normalize
   only comparisons whose contracts permit it.

Run focused CLI/driver/graph/report tests and adapter tooling tests first, then the affected integration fixture and
normal L1 gate. New owned graph/report buffers and error paths require focused ownership traces. Complete L1 `test-ci`
and native Linux, macOS Intel/ARM64 and Windows UCRT64 evidence before initiative closure, without treating this plan
draft as implementation or verification evidence.

## Non-Goals

No second source parser, changed provider precedence, build-plan execution language, package manager, persistent
incremental compiler engine, arbitrary per-module destination planner, profile/cache migration, native dependency
discovery, compiler bootstrap conversion, production compiler/stdlib Make adoption or L2 port. Preserve the existing
language, ABI, diagnostics and compile/link publication contracts except for the explicitly planned report capability.

## Completion Criteria

The neutral compiler report is implemented before the adapter. Both pass the compiler-produced discovery and external
Make fixture with separate inputs, including clean/incremental and explicit/managed composition. All essential
scheduling data remains in P1689 core fields. Documentation and ADR work agree with the delivered behavior, and parent
membership and roadmap links are synchronized. Initiative 0010 stays active until its own completion criteria are met.

[architecture]: ../../../docs/reference/architecture.md
[compilation]: ../../../docs/reference/separate-compilation.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[initiative]: ../../initiatives/0010-explicit-profiles-and-composable-builds.md
[p1689]: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2022/p1689r5.html
