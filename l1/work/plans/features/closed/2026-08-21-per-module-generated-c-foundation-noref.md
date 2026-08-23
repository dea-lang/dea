# Feature Plan

## Establish the per-module generated-C foundation

- Date: 2026-08-21
- Status: Completed
- Title: Migrate generated-C mode to one module and stabilize compile-only staging
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative]
- Subsystem: CLI / module graph / C backend / compile-only determinism
- Modules:
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/codegen_options.l0`
  - `l1/compiler/stage1_l0/src/compile_driver.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/compiler_filesystem.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/module_graph.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/compiler/stage1_l0/support/interface_fingerprint.c`
  - `docs/specs/compiler/cli-contract.md`
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
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_test.l0`
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_support_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_help_output_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_compile_only_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_toplet_test.py`
  - `l1/compiler/stage1_l0/tests/fixtures/separate_compilation`
- Related:
  - [`l1/work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md`][lifecycle]
  - [`l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md`][compile-only]
  - [`l1/work/plans/features/closed/2026-07-17-build-run-multi-cu-orchestration-noref.md`][build-run]
  - [`l1/work/plans/features/closed/2026-07-24-per-module-generated-c-mode-noref.md`][generated-c-completion]
  - [`l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md`][stage1-temp-safety]
- Repro:
  `make -C l1 test-stage1 TESTS="cli_args_test backend_test c_emitter_test driver_test module_graph_test interface_replay_test compile_driver_test compiler_filesystem_test l1c_lib_test l1c_stage1_help_output_test.py l1c_stage1_compile_only_test.py l1c_stage1_toplet_test.py compiler_filesystem_support_test.py"`

## Summary

L1 `--gen` still routes through the legacy whole-closure backend even though compile-only already generates exactly one
selected module through `backend_generate_module(...)`. Build/run fan-out needs one settled operation that produces the
same per-module C bytes without depending on a publication transaction or retaining a mode-specific emitter path.

This prerequisite plan extracts that shared operation, migrates `--gen` to it, and gives compile-only stable
module-relative compiler-visible paths. It is complete when `--gen` and `-c --keep-c` agree byte-for-byte and supported
deterministic host toolchains produce destination-independent objects. It does not wait for build/run fan-out.

The downstream [build/run plan][build-run] then consumes the settled operation and staging contract. The
[generated-C completion plan][generated-c-completion] remains open until build/run joins the byte-identity contract and
the last legacy whole-closure caller can be removed.

## Dependencies and Ownership

1. The closed [lifecycle plan][lifecycle] owns the target-only module C boundary, lifecycle symbols, and optional entry
   bridge.
2. The closed [compile-only plan][compile-only] owns `.o + .l1m` publication, optional `.c` publication, endpoint
   rollback, and the external-serialization requirement for same-stem readers and writers.
3. This plan owns the reusable per-module generation operation, `--gen` resolution/output semantics, stable
   compiler-visible compile-only paths, and supported-toolchain object determinism.
4. The [build/run plan][build-run] depends on this plan and owns graph fan-out, temporary multi-module artifacts,
   executable linking/execution, and the retained generated-C tree.
5. The [generated-C completion plan][generated-c-completion] depends on this plan and build/run fan-out. It owns
   four-mode identity verification, legacy whole-closure generator removal, and final generated-C lifecycle closure.
6. The completed [L0 Stage 1 temporary-C fix][stage1-temp-safety] is related historical work. L1 compile-only remains
   self-contained in its output-local transaction and does not adopt the shared build/run workspace.

## Generated-C CLI Contract

| Invocation                 | Result                                              |
| -------------------------- | --------------------------------------------------- |
| `l1c --gen MODULE`         | One per-module C translation unit on stdout         |
| `l1c --gen MODULE -I ROOT` | The same output with ordered interface-search roots |
| `l1c --gen MODULE -o FILE` | One per-module C translation unit at exactly `FILE` |
| `l1c -c MODULE`            | Canonical sibling `.o` and `.l1m`                   |
| `l1c -c MODULE --keep-c`   | Canonical sibling `.c`, `.o`, and `.l1m`            |

No complete-C-tree generation mode is introduced.

1. The `--gen` target resolves from source. An interface-only target is invalid because generation requires an
   implementation body.
2. Imports use interface-first `MRP_ALLOW_SOURCE_FALLBACK`: ordered `-I` roots are authoritative when selected, and
   source fallback applies only when no interface is selected.
3. A selected valid `.l1m` is sufficient for generation. `--gen` does not require, inspect, or classify its sibling `.o`
   or `.c`.
4. A malformed selected interface fails without source fallback through the existing graph, parser, fingerprint, and
   replay diagnostics.
5. Output contains only the target module's definitions, required imported declarations and transparent types, `I4init`,
   `I4fini`, and conditional `I5entry`. It contains no imported definitions, dependency lifecycle calls, generated
   process `main`, executable wrapper, embedded interface text, or native metadata.
6. Without `-o`, C is written to stdout. With `-o`, the value is an exact file path and no companion path is derived.
7. `--gen` creates no object, interface, wrapper, transaction, or other artifact and never invokes the host compiler or
   linker.
8. `--keep-c` remains invalid with `--gen`; existing generated-C controls remain valid, and host-compiler/linker-only
   controls remain invalid.

## Shared Generation and Stable Staging Contract

1. `--gen` and compile-only call one shared operation that accepts an analyzed source module plus code-generation
   settings and returns the final per-module C byte sequence.
2. For identical source, resolved graph, verified interfaces, fingerprints, code-generation settings, and compiler
   version, `--gen` output is byte-identical to `-c --keep-c` output.
3. The shared operation is independent of output destinations, private transaction names, and caller mode. Build/run can
   consume it without invoking compile-only publication.
4. Compile-only keeps its existing same-parent private transaction and publication/rollback boundary, but the host
   compiler sees stable canonical module-relative C and object paths within that transaction.
5. Random transaction and caller-selected destination prefixes are absent from host compiler input paths. Reproducible
   path flags may supplement this rule but do not replace it.
6. Repeated compile-only invocations to different output roots produce byte-identical objects on supported deterministic
   toolchains. TinyCC and Windows/PE-COFF exceptions are explicit test classifications, not a relaxation of generated-C
   byte identity.
7. Compile-only still publishes `.o + .l1m` by default, adds `.c` only with `--keep-c`, leaves an unrelated existing
   `.c` untouched otherwise, and preserves the exact endpoint rollback/recovery behavior from ADR-0022.

## Implementation Phases

### Phase 1: Consolidate per-module generation

Extract or finalize one internal operation around `backend_generate_module(...)`. Route compile-only through it without
changing analysis, host compilation, publication, rollback, or diagnostics. Keep the operation independent of output
paths and caller mode so build/run can consume it later.

### Phase 2: Migrate `--gen`

Allow ordered `-I` roots with generated-C mode, resolve under `MRP_ALLOW_SOURCE_FALLBACK`, and emit through the shared
operation. Preserve stdout and exact `-o FILE` behavior while deliberately skipping provider-object discovery, object
validation, host compilation, and linking.

### Phase 3: Stabilize compile-only compiler paths

Stage canonical module-relative C and object names inside the existing private transaction and invoke the compiler with
stable relative inputs. Preserve same-parent transaction creation, no-follow internal/final path validation, sequential
publication, endpoint rollback, and retained recovery files. Add object-identity checks for supported toolchains and
explicit TinyCC and Windows/PE-COFF exceptions.

### Phase 4: Documentation and lifecycle

Update the shared CLI contract plus L1 architecture, backend, separate-compilation, project-status, roadmap, and
initiative documents. Close this plan independently before build/run fan-out begins.

## Diagnostics

No new diagnostic block is expected. Reuse graph, parser, fingerprint, output-mode, interface-path, and write-failure
diagnostics from their owning subsystems. Pure generation must not emit provider-object or host-tool diagnostics because
it neither discovers objects nor invokes a compiler. Re-check every referenced live code before implementation and use
the nearest unused code in the established driver range if an unforeseen distinct failure needs one.

## Completion Notes

1. `--gen` now resolves a source-backed target with ordered interface-first imports under `MRP_ALLOW_SOURCE_FALLBACK`
   and emits through `backend_generate_module(...)`.
2. `cg_options_from_cli(...)` is the shared byte-affecting settings projection used by `--gen` and compile-only; focused
   integration coverage proves their generated C is byte-identical.
3. Compile-only stages canonical module-relative C, object, and interface paths inside its existing sibling transaction
   and invokes the host compiler from that root. Known relative compiler and runtime-include paths preserve their
   invocation-directory meaning.
4. Host-tool sentinel coverage proves pure generation does not compile or link and compile-only exposes no transaction
   or destination prefixes in C/object arguments. Supported non-TinyCC object identity is exercised explicitly, with
   TinyCC and Windows/PE-COFF retained as documented exceptions.
5. Existing selected-set publication, rollback, recovery retention, absent-C behavior, and build/run behavior remain
   unchanged.
6. Module-boundary filters bind optional target strings to retained locals before comparison, avoiding the bootstrap
   compiler's ownership-unsafe lowering of direct optional-string unwraps. Heap-backed emitter coverage and the
   warning-bearing generated-C integration case exercise the repaired teardown path.
7. Focused Stage 1 validation passed after the ownership repair, followed by a clean `make -C l1 clean test-all`: 65
   normal tests, all four examples, environment stackability, and 44 broad trace tests passed.

## ADR Impact

- Decision: Make L1 `--gen` emit one per-module C translation unit rather than a complete source closure.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0031-per-module-generated-c-cli-boundary.md`
  - Rationale: This changes the public meaning of generated-C mode and establishes the reusable compiler-artifact
    boundary consumed by compile-only and build/run.
- Decision: Resolve `--gen` imports interface-first while treating a selected `.l1m` as sufficient without requiring its
  sibling object.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0018-canonical-artifact-association-and-module-graph.md`
  - Rationale: ADR-0018 owns interface precedence, authoritative-interface failure, and source fallback.
- Decision: Use stable module-relative host-compiler paths for deterministic compile-only objects where the toolchain
  permits.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0032-deterministic-compile-only-staging-paths.md`
  - Rationale: Compiler-visible staging paths are a durable artifact-determinism boundary with explicit host exceptions.
- Decision: Preserve compile-only selected-set publication and endpoint rollback while changing its internal staging
  paths.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md`
  - Rationale: ADR-0022 already owns the published artifact set, rollback, recovery, and external serialization rules.
- Decision: Preserve `--gen` stdout and exact `-o FILE` output without companion artifacts or host compilation.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: The shared CLI ADR owns generated-C output behavior and level-extension rules.

## Non-Goals

1. Build/run graph fan-out, executable linking, or execution.
2. Build/run retained-C trees or four-mode identity verification.
3. Removing `backend_generate(...)` or the legacy process wrapper while build/run still calls it.
4. Generating a complete multi-CU tree or adding `--gen-tree`.
5. Changing L0 generated-C behavior.
6. Requiring or validating provider objects during pure generation.
7. Changing compile-only selected-set publication, rollback, crash consistency, or concurrency guarantees.
8. Persistent build caching, incremental invalidation, or package resolution.

## Verification Criteria

01. `--gen` emits only the selected module's definitions and never emits a process-level `main` or dependency lifecycle
    chain.
02. Utility and entry modules respectively omit or emit `I5entry`, while both emit `I4init` and `I4fini`.
03. Interface-first precedence, authoritative-interface failure, and source fallback match `MRP_ALLOW_SOURCE_FALLBACK`.
04. A selected valid `.l1m` succeeds without sibling `.o` or `.c`; a malformed selected interface fails without source
    fallback.
05. `--gen` writes stdout or exactly one requested file and creates no companion artifacts.
06. A host-tool sentinel proves `--gen` never compiles or links.
07. `--gen` output and `-c --keep-c` output are byte-identical for identical resolved inputs and options.
08. Host compiler inputs contain stable module-relative paths and no transaction or destination prefixes.
09. Compile-only object identity passes on supported deterministic toolchains with explicit TinyCC and Windows/PE-COFF
    exceptions.
10. Existing compile-only publication, rollback, recovery, and absent-C behavior remain covered.
11. No build/run behavior changes in this prerequisite tranche.
12. Focused tests pass, followed by `make -C l1 clean test-all` before closure.

[build-run]: 2026-07-17-build-run-multi-cu-orchestration-noref.md
[compile-only]: 2026-07-17-compile-only-artifact-production-noref.md
[generated-c-completion]: 2026-07-24-per-module-generated-c-mode-noref.md
[initiative]: ../../../initiatives/0001-separate-compilation-and-linking.md
[lifecycle]: 2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md
[stage1-temp-safety]: ../../../../../l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md
