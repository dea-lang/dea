# Feature Plan

## Link verified Dea and explicit foreign objects

- Date: 2026-07-17
- Status: Draft
- Title: Add the standalone link-set driver and executable wrapper
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative]
- Subsystem: CLI / object verification / lifecycle wrapper / host linker
- Modules:
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/object_metadata.l0`
  - `l1/compiler/stage1_l0/src/object_reader.l0`
  - `l1/compiler/stage1_l0/src/link_driver.l0`
  - `l1/compiler/stage1_l0/src/wrapper_emitter.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/l1c.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `docs/specs/compiler/cli-contract.md`
  - `l1/docs/specs/compiler/abi.md`
  - `l1/docs/reference/architecture.md`
  - `l1/docs/reference/separate-compilation.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/object_metadata_test.l0`
  - `l1/compiler/stage1_l0/tests/object_reader_test.l0`
  - `l1/compiler/stage1_l0/tests/link_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/fixtures/separate_compilation`
- Related:
  - [`l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md`][module-graph]
  - [`l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md`][fingerprints]
  - [`l1/work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md`][lifecycle]
  - [`l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md`][object-metadata]
  - [`l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md`][compile-only]
  - [`l1/work/plans/features/2026-07-17-build-run-multi-cu-orchestration-noref.md`][build-run]
  - [`l1/work/plans/features/2026-04-24-external-library-linking-cli-noref.md`][external-linking]
  - [`work/plans/bug-fixes/2026-07-21-shared-structured-c-source-input-noref.md`][structured-input]
  - [`work/plans/bug-fixes/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md`][native-workspace]
  - [`docs/specs/compiler/diagnostic-code-catalog.md`][diagnostic-catalog]
- Repro:
  `make -C l1 test-stage1 TESTS="cli_args_test object_metadata_test object_reader_test link_driver_test build_driver_test l1c_lib_test"`

## Summary

Add the missing standalone link stage for Initiative `0001`. It consumes explicitly listed metadata-bearing Dea objects,
validates their complete dependency and fingerprint graph, selects one Dea entry bridge, emits a separate process
wrapper, and invokes the host compiler driver. It does not reopen `.l1m` files: object metadata is the source of truth
for module identity, ordered direct imports, expected provider fingerprints, lifecycle symbols, and entry presence.

The same mode accepts metadata-free C relocatable objects only through repeatable `--foreign-object`. Foreign objects
may satisfy current unmangled `extern func` references and future `extern "C"` declarations, but they never acquire Dea
module, fingerprint, lifecycle, dependency, or entry semantics.

## Dependencies and Ownership

1. The [module graph][module-graph] establishes ordered dependency semantics, and [fingerprints] establish provider
   compatibility values.
2. The completed [lifecycle plan][lifecycle] supplies external `I4init`, `I4fini`, and conditional `I5entry` symbols.
3. [Object metadata][object-metadata] supplies bounded readers and the `ValidDeaMetadata`, `NoDeaMetadata`, and
   `MalformedDeaMetadata` results.
4. [Compile-only production][compile-only] produces the final verified Dea objects consumed here.
5. This plan owns the public link-mode CLI, classification enforcement, graph verification, entry selection, wrapper,
   runtime archive selection, and host link invocation.
6. [Build/run fan-out][build-run] reuses the internal link API; [external linking][external-linking] later extends the
   ordered input stream with libraries, rpaths, and raw host-driver arguments.
7. This plan owns an atomically reserved output-local transaction for standalone wrapper artifacts. The common link
   executor accepts caller-supplied scratch paths and never allocates or cleans their owning workspace.
8. The active [structured-input plan][structured-input] and [shared native-workspace plan][native-workspace] are
   prerequisites for later build/run fan-out, not for standalone linking. This mode must not call `bd_temp_stem()`.

## CLI Contract

The public form is:

```text
l1c --link DEA_OBJECT... [--foreign-object C_OBJECT]... [--entry MODULE] -o OUTPUT
```

1. `--link` is an L1-specific primary mode. It requires at least one positional Dea object and exactly one output path;
   source targets, `-I`, `--keep-c`, `--all-modules`, runtime program arguments, and analysis-only options are invalid.
2. Positional operands are Dea objects and may be interleaved with options. Their encounter order is retained.
3. `--foreign-object PATH` and `--foreign-object=PATH` are repeatable, have no short alias, and contribute a typed
   foreign-object operand at their encounter position. Missing values reuse the shared missing-option-value diagnostic.
4. `--entry MODULE` accepts following-value and `=VALUE` forms, has no short alias, and may appear at most once. Its
   value must be a canonical dotted module name.
5. `-o` / `--output` is mandatory in standalone link mode and names the executable. The driver creates its existing
   parent directory only when that behavior matches current build output policy; it never treats a directory as an
   executable name.
6. Host compiler, compiler-option, runtime include/library, tracing, and runtime-checking controls needed to compile the
   wrapper and select the runtime archive are valid. External libraries and raw link arguments remain reserved until the
   external-linking plan lands.
7. Shared CLI documentation records link mode as the exception to the normal exactly-one-source-target rule.

## Object Classification Boundary

Every input is inspected before wrapper generation or host linking:

1. A positional Dea operand must produce `ValidDeaMetadata`. `NoDeaMetadata` fails with guidance to use
   `--foreign-object`; `MalformedDeaMetadata` fails with its metadata reason.
2. A foreign operand must produce `NoDeaMetadata`. A valid Dea object fails because the foreign spelling cannot bypass
   graph, fingerprint, lifecycle, or entry checks. Malformed Dea metadata also fails and is never treated as absence.
3. Object-read failures such as missing files, unreadable data, unsupported containers, and corrupt object tables are
   driver failures regardless of operand spelling.
4. Foreign inputs must be supported relocatable objects. Static archives, import libraries, shared libraries, and
   executables use the external-library surface rather than `--foreign-object`.
5. A foreign object defining the platform-normalized process symbol `main` is rejected. C code cannot replace the Dea
   wrapper or become an entry candidate through the foreign boundary.
6. A foreign object may define ordinary unmangled C symbols. It cannot satisfy a Dea module edge because it has no
   canonical module identity or provider fingerprint.

## Dea Graph and Entry Validation

1. Module identities must be unique. Repeating a path or supplying different objects with the same module identity is an
   error.
2. Every ordered import in every Dea object must name exactly one supplied Dea provider. Missing providers and duplicate
   identities fail before host linking; extra explicitly supplied Dea objects remain part of the link set.
3. Each consumer's expected provider fingerprint must exactly match the supplied provider's own embedded fingerprint.
4. The dependency graph must be acyclic. Cycle diagnostics show the canonical module chain and are independent of input
   path spelling.
5. With no `--entry`, exactly one `HAS_ENTRY` module is inferred. Zero candidates fail; multiple candidates fail and
   list every canonical candidate in deterministic order.
6. With `--entry`, the selected module must be present and carry `HAS_ENTRY` plus its matching `I5entry` symbol. An
   explicit selection remains valid when there is only one candidate.
7. Foreign objects never count as entry candidates, even if they define a symbol that resembles an LBI entry name.

## Ordering and Wrapper Contract

1. Traverse from the selected entry module, following each object's ordered direct imports. Visit dependencies before
   their consumer. After the entry component, visit any unvisited explicitly supplied Dea objects in positional order,
   again respecting their ordered dependencies.
2. Record this deterministic dependency-first sequence once. Initialization uses it directly; finalization uses its
   exact reverse. Each Dea module appears once.
3. Emit a separate C wrapper that defines the only process-level `main(int argc, char **argv)`, declares every linked
   Dea module's lifecycle symbols, and declares the selected module's entry symbol.
4. The wrapper calls `_rt_init_args(argc, argv)`, every `I4init`, the selected `I5entry`, every `I4fini` in reverse,
   then returns the normalized status. Foreign objects receive no generated calls.
5. Compile the wrapper with the selected host compiler and runtime include path. Link the wrapper object, typed Dea and
   foreign inputs in their retained order, and the selected runtime archive by exact path.
6. Preserve host compiler stdout/stderr and return a structured link failure. Remove temporary wrapper C/object files on
   success and failure without deleting any caller-supplied input.
7. Missing inputs and object-container errors detectable by the bounded readers are driver diagnostics. Unresolved
   symbols and unsupported architecture or ABI combinations among otherwise well-formed inputs remain host-link
   failures, with the host tool's output preserved.

## Standalone Link Workspace Contract

01. The parent of mandatory `-o OUTPUT` must already exist and resolve to a directory, matching current build behavior.
    Existing directory aliases in that caller-selected parent chain are trusted. The final output itself must be absent
    or a regular file; directories, symlinks, reparse points, and other objects are rejected.
02. Allocate no scratch state until object classification, graph and entry validation, host-compiler selection, runtime
    include/archive validation, and output-parent validation succeed.
03. Exclusively create `.l1c-link-<pid>-<seconds>-<nanoseconds>-<attempt>` beside the output. Try attempts `0` through
    `99`; report setup failure after exhaustion and never return an unchecked fallback.
04. The transaction owns fixed `wrapper.c`, `wrapper.o`, `compile.stdout`, `compile.stderr`, `link.stdout`, and
    `link.stderr` children. Caller-supplied objects and the final executable remain outside it.
05. POSIX creation requests mode `0700`, subject to a more restrictive process umask. This output-local boundary does
    not perform the global temporary-root owner and sticky-bit audit.
06. MinGW uses `CreateDirectoryA` and inherits the trusted output parent's ACL; the POSIX mode argument is ignored.
    No-follow classification through `FILE_FLAG_OPEN_REPARSE_POINT` rejects symlinks, junctions, devices, and other
    reparse points. The current Stage 1 native narrow-byte path encoding remains the supported Windows path contract.
07. MinGW/GCC-family wrapper compilation and PE/COFF linking are required end to end. Existing MSVC `/c`, `/Fo:`, and
    `/Fe:` construction remains unit-covered but does not establish full MSVC runtime/link support in this tranche.
08. The common link executor receives explicit scratch paths. Standalone link owns this transaction; later build/run
    supplies paths beneath its shared invocation workspace and owns that workspace's cleanup.
09. Cleanup removes only known regular children, without following aliases, then removes the verified empty real
    directory. It never recursively deletes. Unexpected or substituted contents retain the transaction and report its
    path.
10. Cleanup failure is result-bearing. It returns nonzero even after a successful host link, while preserving the
    caller-visible executable already produced.
11. The host linker writes directly to `OUTPUT`; executable publication, replacement, and partial-failure behavior are
    not wrapped in a transaction or rollback protocol.

## Implementation Phases

### Phase 1: CLI and typed operands

Add link mode, multi-object positional parsing, `--entry`, and link-mode `--foreign-object`. Store Dea and foreign
operands in one ordered typed vector and enforce the exact option matrix.

### Phase 2: Classification and graph validation

Inspect each object once, enforce operand classification, construct the canonical module map, verify dependency closure
and fingerprints, reject cycles, and resolve the entry module.

### Phase 3: Wrapper and host link

Compute lifecycle order, emit and compile the wrapper, select the runtime archive, build the host command without shell
word loss, and invoke the linker through explicit scratch paths. The standalone CLI adapter creates and cleans the
output-local transaction; the common executor never owns workspace allocation or cleanup. Keep external library options
out until their owning plan lands.

### Phase 4: Documentation and FFI-forward smoke coverage

Update CLI, ABI, architecture, and separate-compilation references. Compile a tiny C provider object, declare its
function through today's unmangled `extern func`, link it with `--foreign-object`, and run it. Initiative `0003` later
repeats the path with `extern "C"`.

## Diagnostics

1. Provisionally reserve `L1C-2090` through `L1C-2109` for link-mode option scope, object classification, graph
   completeness, fingerprint mismatch at link preparation, entry selection, wrapper compilation, and final host-link
   failures.
2. Raw object-read and malformed-metadata details retain the `L1C-2050` through `L1C-2069` area owned by the metadata
   plan. Shared missing-value/output diagnostics are reused when their meanings remain exact.
3. Re-check `L1C-2090` through `L1C-2109` against the live [diagnostic catalog][diagnostic-catalog] immediately before
   implementation and move the whole provisional block if any code has been assigned.

## ADR Impact

- Decision: Link verified Dea objects and explicitly classified foreign objects through a generated executable wrapper.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The verified link-set boundary, entry validation, foreign-object distinction, and wrapper ownership
    constrain every future linker-facing workflow.
- Decision: Isolate standalone wrapper artifacts in an atomically reserved output-local transaction supplied explicitly
  to the common link executor.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Standalone link always has a caller-selected output parent, so it can avoid the unsafe global temporary
    stem without blocking on the separate cross-level build/run workspace policy.
- Decision: Make the per-module lifecycle ABI the source of wrapper calls and deterministic initialization ordering.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0020-per-module-backend-and-lifecycle-abi.md`
  - Rationale: ADR-0020 defines the lifecycle entrypoints whose composition becomes executable-link behavior.
- Decision: Use portable object metadata as the authority for Dea-object classification and inspection.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0021-portable-object-metadata-and-inspection.md`
  - Rationale: ADR-0021 already defines metadata authority and the verified-versus-foreign object boundary.
- Decision: Expose standalone linking through the shared `--link` compiler mode contract.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: ADR-0003 owns shared compiler modes, operand validation, and level-specific extensions.

## Non-Goals

1. Discovering objects from module names or reopening `.l1m` files during link-only mode.
2. Treating metadata absence as implicit foreign authorization.
3. Producing static/shared libraries or accepting archives through `--foreign-object`.
4. External `-l`, `-L`, rpath, package manifests, or runtime dynamic loading.
5. Turning a C `main` into the process entry or defining C++ ABI interoperation.
6. Compiling source modules or implementing build/run graph fan-out.
7. Implementing structured `--c-source`, global temporary-root validation, or the shared build/run workspace lifecycle.
8. Transactional publication or rollback of the final executable.

## Verification Criteria

01. A complete Dea object graph with one entry links and runs without any `.l1m` input.
02. Zero and multiple entry candidates fail deterministically; valid explicit selection chooses one of several entry
    candidates and invokes only its `I5entry`.
03. Missing providers, duplicate module identities, cycles, and consumer/provider fingerprint mismatches fail before the
    host linker.
04. A metadata-free positional object fails with `--foreign-object` guidance.
05. A valid or malformed Dea object passed as foreign fails and cannot bypass verification.
06. A metadata-free C provider satisfies an unmangled `extern func` only through `--foreign-object` and receives no
    lifecycle or entry calls.
07. A foreign object defining C `main` is rejected.
08. Init calls are dependency-first, fini calls are the exact reverse, and side-effect-only ordered imports are honored.
09. The runtime archive is passed by exact path, wrapper temporaries are cleaned, and user inputs remain untouched.
10. Focused normal and trace tests pass, followed by `make -C l1 test` once implementation is complete.
11. Concrete diagnostics are registered in the shared catalog before closure.
12. Transaction allocation retries collisions, rejects an exhausted candidate set without fallback, and never calls
    `bd_temp_stem()`.
13. Wrapper write, compiler discovery, wrapper compile, final link, and cleanup failures remove known transaction files
    or retain and report the bounded transaction without touching caller inputs.
14. POSIX tests cover mode `0700` and trusted output-parent aliases. MinGW tests cover inherited ACL behavior,
    reparse-point rejection, spaces and drive-rooted paths, `.o` wrapper production, PE/COFF linking, and
    `RemoveDirectoryA` cleanup.
15. MSVC command-word tests preserve `/c`, `/Fo:`, and `/Fe:` construction without claiming an end-to-end support lane.

[build-run]: 2026-07-17-build-run-multi-cu-orchestration-noref.md
[compile-only]: closed/2026-07-17-compile-only-artifact-production-noref.md
[diagnostic-catalog]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[external-linking]: 2026-04-24-external-library-linking-cli-noref.md
[fingerprints]: closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[initiative]: ../../initiatives/0001-separate-compilation-and-linking.md
[lifecycle]: closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md
[module-graph]: closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[native-workspace]: ../../../../work/plans/bug-fixes/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md
[object-metadata]: closed/2026-07-17-object-metadata-emission-and-readers-noref.md
[structured-input]: ../../../../work/plans/bug-fixes/2026-07-21-shared-structured-c-source-input-noref.md
