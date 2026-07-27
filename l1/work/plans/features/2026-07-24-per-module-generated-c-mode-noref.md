# Feature Plan

## Make generated-C output per-module

- Date: 2026-07-24
- Status: Draft
- Title: Migrate generated-C mode to per-module output and retire whole-closure generation
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative]
- Subsystem: CLI / module graph / C backend / compile-only determinism
- Modules:
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/codegen_options.l0`
  - `l1/compiler/stage1_l0/src/compile_driver.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/module_graph.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `docs/specs/compiler/cli-contract.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - `l1/docs/reference/architecture.md`
  - `l1/docs/reference/c-backend-design.md`
  - `l1/docs/reference/separate-compilation.md`
  - `l1/docs/project-status.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/module_graph_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_replay_test.l0`
  - `l1/compiler/stage1_l0/tests/compile_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_help_output_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_compile_only_test.py`
  - `l1/compiler/stage1_l0/tests/fixtures/separate_compilation`
- Related:
  - [`l1/work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md`][lifecycle]
  - [`l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md`][object-metadata]
  - [`l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md`][compile-only]
  - [`l1/work/plans/features/2026-07-17-build-run-multi-cu-orchestration-noref.md`][build-run]
  - [`l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md`][stage1-temp-safety]
  - [`work/plans/bug-fixes/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md`][native-temp-safety]
- Repro:
  `make -C l1 test-stage1 TESTS="cli_args_test backend_test c_emitter_test driver_test module_graph_test interface_replay_test compile_driver_test build_driver_test l1c_lib_test l1c_stage1_help_output_test.py l1c_stage1_compile_only_test.py"`

## Summary

L1 `--gen` still routes through the legacy backend and emits one C99 translation unit for the complete source closure.
The internal module backend now emits one selected source-backed module, and compile-only uses it to publish the
reusable `.o + .l1m` pair by default. `-c --keep-c` additionally publishes the exact per-module C compiled into the
object.

This plan moves `--gen` onto that per-module operation. It preserves stdout and exact `-o FILE` output, adds
interface-first import resolution through ordered `-I` roots, emits no companion artifacts, and locks generated-C byte
identity across generation, compile-only retention, and later retained build/run output.

After the [build/run fan-out plan][build-run] migrates the last whole-program callers, this plan removes
`backend_generate(...)` and the legacy combined initialization and process-wrapper paths.

## Dependencies and Ownership

1. The closed [lifecycle plan][lifecycle] owns the one-module C boundary and lifecycle symbols.
2. The closed [object metadata plan][object-metadata] owns the metadata embedded in each generated module.
3. The closed [compile-only plan][compile-only] owns source-module analysis, host object compilation, the default
   `.o + .l1m` publication pair, and optional C retention through `--keep-c`.
4. This plan owns `--gen` resolution and output semantics, cross-mode generated-C identity, stable compiler-visible
   workspace paths, compile-only object determinism, and retirement of the legacy generator.
5. The [build/run fan-out plan][build-run] owns multi-CU orchestration and retained-C trees. Its migration must land
   before this plan removes the legacy generator, but it does not block the `--gen` migration.
6. The completed [L0 Stage 1 temporary-C fix][stage1-temp-safety] is related historical work. The active shared
   [native temporary-workspace safety plan][native-temp-safety] owns native build/run hardening but is not a
   prerequisite; L1 compile-only remains self-contained through its output-local private transaction directory and
   endpoint-rollback publication path.

## Final CLI Contract

| Invocation                    | Result                                               |
| ----------------------------- | ---------------------------------------------------- |
| `l1c --gen MODULE`            | One per-module C translation unit on stdout          |
| `l1c --gen MODULE -I ROOT`    | The same output with ordered interface-search roots  |
| `l1c --gen MODULE -o FILE`    | One per-module C translation unit at exactly `FILE`  |
| `l1c -c MODULE`               | Canonical sibling `.o` and `.l1m`                    |
| `l1c -c MODULE --keep-c`      | Canonical sibling `.c`, `.o`, and `.l1m`             |
| `l1c --build MODULE`          | Build an executable                                  |
| `l1c --build MODULE --keep-c` | Executable plus the planned retained multi-CU C tree |
| `l1c --run MODULE`            | Run the program and return its status                |
| `l1c --run MODULE --keep-c`   | Run the program and retain the planned multi-CU tree |

No complete-C-tree generation mode is introduced.

## Generated-C Contract

01. The `--gen` target must resolve from source. An interface-only target is invalid because generation requires the
    implementation body.
02. Imports use interface-first `AllowSourceFallback`, matching planned build/run graph resolution:
    - ordered `-I` roots are searched before source fallback;
    - a selected interface is authoritative;
    - source fallback is allowed only when no interface is selected.
03. A selected valid `.l1m` is sufficient for generation. `--gen` does not require or inspect the canonical sibling
    `.o`; an absent, stale, malformed, or metadata-free sibling object does not affect generation.
04. A malformed selected interface fails without source fallback. Normal graph, fingerprint, and replay validation still
    applies before emission.
05. The generated translation unit contains definitions owned by the requested module, required imported declarations
    and transparent type declarations, `I4init`, `I4fini`, conditional `I5entry`, and finalized Dea object metadata.
06. The translation unit contains no imported value definitions, dependency lifecycle calls, legacy whole-program
    initialization chain, generated process-level C `main`, executable wrapper, or embedded `.l1m` text.
07. A utility module without a valid source `main` is a valid target and emits no `I5entry`.
08. Without `-o`, generated C is written to stdout. With `-o`, the value is an exact file path; no `.c` suffix is
    required and no companion path is derived.
09. `--gen` creates no `.o`, `.l1m`, wrapper, or other artifact and never invokes the host compiler or linker.
10. `--keep-c` remains invalid with `--gen` because C is already the primary output.
11. Existing generated-C controls remain valid. Host-compiler and linker-only controls remain invalid.

## Cross-Mode Identity and Object Determinism

`--gen`, `-c`, `--build`, and `--run` must use one shared per-module C-generation operation. For the same target,
resolved graph, interface fingerprints, code-generation settings, and compiler version:

- `l1c --gen MODULE -o module.c` produces C byte-identical to the `.c` published by `l1c -c MODULE --keep-c`;
- after build/run fan-out lands, the same bytes appear for that module in the retained build/run C tree;
- output destinations and private transaction-directory names do not affect generated bytes.

Compile-only host compilation must also hide random transaction and caller-selected destination paths from the host
compiler. Place staged C and object files at stable canonical module-relative names inside the private workspace, run
the compiler with that workspace as its working directory, and pass relative paths. Toolchain reproducible-path flags
may supplement this rule but do not replace it.

Repeated compile-only invocations to different destination roots must produce byte-identical objects on supported
deterministic toolchains. Generated C remains byte-identical everywhere, but object byte identity is not required from
TinyCC or Windows/PE-COFF toolchains where the host compiler or object format injects unstable data. Tests must mark
those exceptions explicitly rather than weakening the general contract.

The completed compile-only publication semantics do not otherwise change: ordinary `-c` publishes `.o + .l1m`,
`--keep-c` adds the canonical `.c`, and compilation without `--keep-c` does not create, overwrite, remove, back up, or
restore a pre-existing canonical `.c`. Successful return leaves the complete new selected set, recoverable failure
restores the exact prior set, and failed rollback retains recovery files. Sequential publication and rollback may expose
missing paths or mixed generations; concurrent readers and same-stem writers require external serialization.

## Compatibility Decision

This is an intentional L1 compatibility change. Today, `--gen` emits a combined source-closure translation unit and may
include a process-level C `main`. After this plan it emits one linkable module CU; a valid source entry is exposed as
`I5entry`, not as the process wrapper.

Do not retain a hidden compatibility path or legacy flag. Document that:

- `--gen` inspects or externally compiles one L1 module;
- `-c` is the supported way to produce reusable Dea artifacts;
- `--build --keep-c` and `--run --keep-c` expose generated module C plus the executable wrapper;
- pure generation of a complete multi-file program tree is not supported.

L0 behavior remains unchanged.

## Implementation Phases

### Phase 1: Consolidate per-module generation

Extract or finalize one internal operation that accepts an analyzed source target and emits final per-module C through
`backend_generate_module(...)`. Route compile-only through that operation without changing its publication contract. Do
not introduce mode-specific metadata construction or a second emitter path.

### Phase 2: Migrate `--gen`

Allow ordered `-I` roots with `CM_GEN`, resolve the source target and imports under `AllowSourceFallback`, and dispatch
generation through the shared per-module operation. Preserve stdout and exact `-o FILE` behavior. Deliberately skip
provider-object discovery, object validation, host compilation, and linking.

### Phase 3: Stabilize compiler-visible paths

Change compile-only staging so the host compiler sees stable module-relative C and object paths within the private
transaction workspace. Keep the existing same-parent staging, validation, sequential publication, endpoint rollback, and
recovery-file behavior, including following trusted output-parent directory aliases while retaining no-follow final
artifact and internal-path classification. Do not add a reader-snapshot claim. Add object-identity checks for stable
supported toolchains and explicit TinyCC and Windows/PE-COFF exceptions.

### Phase 4: Verify cross-mode identity

Prove that `--gen` output, compile-only retained C, and later retained build/run module C are byte-identical for the
same resolved inputs and options. The build/run assertions may land only after their owning fan-out plan is implemented,
but this plan stays open until the complete identity contract is covered.

### Phase 5: Retire whole-closure generation

After build/run fan-out removes every remaining production caller:

- remove `backend_generate(...)`;
- remove combined whole-closure definition walks;
- remove the legacy backend-owned process wrapper and whole-program initialization chain;
- remove tests whose only purpose was preserving the superseded single-CU output.

Executable wrapper generation remains owned by the standalone link path.

### Phase 6: Documentation and lifecycle

Update the shared CLI contract and diagnostic catalog plus the L1 architecture, backend, separate-compilation,
project-status, roadmap, and initiative documents.

At closure, add the next available L1 ADR recording per-module `--gen`, cross-mode generated-C identity, stable
compiler-visible paths and object-determinism exceptions, and retirement of whole-closure generation. Amend ADR-0020's
transitional legacy-generator statements and link ADR-0022 for the unchanged compile-only publication and rollback
contract. Update the ADR index and close the plan normally.

## ADR Impact

- Decision: Make L1 `--gen` emit one per-module C translation unit rather than the complete source closure.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: This changes the public meaning of generated-C mode and removes the legacy whole-program output contract.
- Decision: Resolve `--gen` imports interface-first and treat a selected `.l1m` as authoritative without requiring its
  sibling `.o`.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0018-canonical-artifact-association-and-module-graph.md`
  - Rationale: ADR-0018 owns interface precedence, authoritative-interface failure, and source-fallback policy.
- Decision: Preserve byte-identical per-module C across `--gen`, `-c --keep-c`, and retained build/run output.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Cross-mode identity prevents mode-specific emitters and makes generated C a stable compiler artifact.
- Decision: Hide transaction and destination names from host compilation through stable module-relative workspace paths.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Stable compiler-visible paths provide deterministic objects on supported toolchains while permitting
    explicit platform exceptions.
- Decision: Publish `.o + .l1m` by default, add `.c` only with `--keep-c`, and preserve endpoint rollback.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md`
  - Rationale: ADR-0022 already owns the selected artifact set, rollback boundary, and external-serialization
    requirement.
- Decision: Retire the legacy whole-closure generator after build/run migrates to the per-module backend.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0020-per-module-backend-and-lifecycle-abi.md`
  - Rationale: ADR-0020 deliberately retained the legacy generator as a transitional path and must record its
    retirement.
- Decision: Preserve `--gen` stdout and exact `-o FILE` output without companion artifacts or host compilation.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: The shared CLI ADR owns generated-C mode, output behavior, and level-extension rules.

## Diagnostics

No new diagnostic family or code is expected. Reuse:

- `DRV-0072` through `DRV-0077` and existing parser/fingerprint diagnostics for module and interface failures;
- `L1C-2010` for output-mode validation;
- `L1C-2011` for invalid `--keep-c` mode combinations;
- `L1C-2031` for invalid interface-search-path mode combinations;
- `L1C-9511` for generated-output write failure.

Pure generation must not emit provider-object or host-compiler diagnostics because it neither discovers objects nor
invokes the compiler. Recheck every referenced code and its live wording in the shared diagnostic catalog before
implementation; reuse nearby established codes if an unforeseen case needs separate handling.

## Non-Goals

1. Generating a complete multi-CU C tree without building.
2. Adding `--gen-tree`, `--all-modules`, or an output-directory interpretation for `--gen`.
3. Retaining whole-closure output behind a compatibility flag.
4. Changing L0 `--gen`.
5. Invoking a host compiler or linker from `--gen`.
6. Requiring or validating provider objects during pure generation.
7. Changing compile-only selected-set publication, endpoint rollback, or its documented crash-consistency and
   concurrency boundary.
8. Adding build caching, package manifests, or dependency resolution.
9. Implementing build/run graph fan-out or standalone linking in this plan.

## Verification Criteria

01. `--gen` emits definitions only for the selected module; imported values appear only as declarations.
02. A utility module emits lifecycle symbols but no `I5entry` or process-level `main`; an entry module emits `I5entry`
    but no process-level `main`.
03. Interface-first precedence and authoritative-interface failures match `AllowSourceFallback`.
04. A selected valid `.l1m` succeeds when its canonical `.o` and `.c` are absent. A present stale, malformed, or
    metadata-free sibling object is ignored; a malformed selected `.l1m` fails without source fallback.
05. Source fallback works only when no interface is selected.
06. `--gen` writes stdout by default and exactly one requested file with `-o`, with no object, interface, wrapper, or
    companion output.
07. A host-compiler sentinel proves `--gen` never invokes compilation or linking.
08. Generated C is byte-identical between `--gen` and `-c --keep-c`, and later with the corresponding retained build/run
    module, for identical resolved inputs and options.
09. Compiler-visible paths are stable and do not expose transaction or destination prefixes.
10. Repeated compile-only invocations to different destinations produce byte-identical objects on stable supported
    toolchains. Tests explicitly classify TinyCC and Windows/PE-COFF object-identity exceptions.
11. A downstream separate-compilation fixture compiles a provider without `--keep-c`, confirms that only its usable
    `.o + .l1m` pair exists, compiles a consumer against the provider `.l1m`, and links the consumer and provider
    objects without recreating or reading the provider `.c`. Build/run fan-out must also consume the same
    interface/object pair with no canonical C. Existing compile-only tests preserve successful/new and
    recoverable-failure/prior endpoints without asserting an atomic reader-visible snapshot.
12. No production caller or test references `backend_generate(...)` after build/run fan-out lands.
13. Existing build, run, compile, and link behavior remains covered by normal and trace tests.
14. Help-output coverage locks the final `-I`, `--keep-c`, compile-only, build/run, and generated-C wording.

## Test Plan

Treat the no-C provider fixture as cross-plan acceptance. First compile the provider with ordinary `-c`, assert that its
canonical `.c` is absent, and compile a consumer through the published `.l1m`. After standalone linking lands, link and
run the consumer and provider objects. After build/run fan-out lands, repeat provider selection through its sibling
interface/object pair. This plan remains open until both paths pass without regenerating provider C.

Run focused normal tests, including Python CLI coverage:

```sh
make -C l1 test-stage1 TESTS="cli_args_test backend_test c_emitter_test driver_test module_graph_test interface_replay_test compile_driver_test build_driver_test l1c_lib_test l1c_stage1_help_output_test.py l1c_stage1_compile_only_test.py"
```

Run focused trace tests for the L0 test modules, then the full suite:

```sh
make -C l1 test-stage1-trace TESTS="cli_args_test backend_test c_emitter_test driver_test module_graph_test interface_replay_test compile_driver_test build_driver_test l1c_lib_test"
make -C l1 clean test-all
```

Before finalization, verify that no production caller retains the legacy backend:

```sh
rg -n 'backend_generate\(' l1/compiler/stage1_l0
```

Then run staged whitespace, link, Markdown, and repository-root pre-commit checks.

[build-run]: 2026-07-17-build-run-multi-cu-orchestration-noref.md
[compile-only]: closed/2026-07-17-compile-only-artifact-production-noref.md
[initiative]: ../../initiatives/0001-separate-compilation-and-linking.md
[lifecycle]: closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md
[native-temp-safety]: ../../../../work/plans/bug-fixes/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md
[object-metadata]: closed/2026-07-17-object-metadata-emission-and-readers-noref.md
[stage1-temp-safety]: ../../../../l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md
