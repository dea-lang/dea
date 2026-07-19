# Feature Plan

## Produce transactional compile-only artifacts

- Date: 2026-07-17
- Status: Draft
- Title: Produce transactional compile-only C, object, and interface artifacts
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative]
- Subsystem: CLI / driver / C compilation / artifact publication
- Modules:
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/interface_emitter.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `docs/specs/compiler/cli-contract.md`
  - `l1/docs/reference/architecture.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/source_paths_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
- Related:
  - [`l1/work/plans/features/closed/2026-04-24-separate-compilation-driver-surface-noref.md`][foundation]
  - [`l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md`][module-graph]
  - [`l1/work/plans/features/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md`][fingerprints]
  - [`l1/work/plans/features/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md`][lifecycle]
  - [`l1/work/plans/features/2026-07-17-object-metadata-emission-and-readers-noref.md`][object-metadata]
  - [`l1/work/plans/features/2026-07-17-link-set-driver-and-wrapper-noref.md`][link-set]
  - [`docs/specs/compiler/diagnostic-code-catalog.md`][diagnostic-catalog]
- Repro:
  `make -C l1 test-stage1 TESTS="cli_args_test source_paths_test driver_test backend_test interface_test build_driver_test l1c_lib_test"`

## Summary

Make the reserved `-c` / `--compile` mode operational only after the module graph, canonical fingerprints, per-module
backend, lifecycle ABI, and object metadata shape have landed. One invocation compiles exactly one source module against
interfaces and publishes one sibling `.c`, `.o`, and `.l1m` artifact set. It never folds source-import definitions into
the object and never invokes the final host linker.

Publication is transaction-like: generated C, the compiled object, and the verified interface are prepared under unique
temporary sibling paths before any destination is replaced. Analysis, emission, C compilation, or publication failure
must not leave a fresh interface paired with a missing or stale object.

## Dependencies and Ownership

1. The [module graph][module-graph] owns canonical paths, `RequireInterface` discovery, and transitive dependency state.
2. [Interface fingerprints][fingerprints] must make emitted `.l1m` files self-verifying.
3. The [lifecycle plan][lifecycle] must define final one-module C output, and [object metadata][object-metadata] must
   make the resulting object a complete Dea link input.
4. This plan owns compile-mode CLI activation, output resolution, the host `cc -c` step, and all-or-nothing publication.
5. The [link-set plan][link-set] consumes the published object but does not reopen the `.l1m` during standalone linking.

## CLI and Artifact Contract

The public form is:

```text
l1c -c MODULE [-I ROOT]... [-o CANONICAL_OBJECT_PATH]
```

1. `MODULE` resolves to one source implementation. An interface cannot replace the compilation target.
2. Every non-virtual import uses the module graph's `RequireInterface` policy. Missing, malformed, or dependency-broken
   interfaces fail; compile-only never falls back to provider source.
3. Without `-o`, the current working directory is the artifact root and the canonical dotted module path supplies the
   stem. `foo.bar` produces `foo/bar.c`, `foo/bar.o`, and `foo/bar.l1m`.
4. With `-o`, the value must be an `.o` file path. The same stem and directory with `.c` and `.l1m` suffixes are its
   companions. Extensionless paths, directories, and non-`.o` suffixes are rejected rather than guessed.
5. Parent directories are created before staging. An existing non-directory parent or a destination that is not a
   regular file is an error.
6. `--output`, `--c-compiler`, `--c-options`, `--runtime-include`, line-directive controls, and codegen/runtime-checking
   controls needed to produce the object become valid in compile mode. `--runtime-lib`, `--entry`, external-library
   flags, and runtime program arguments remain invalid because `-c` does not link or run.
7. Generated C is a first-class output of compile-only mode, not a temporary file controlled by `--keep-c`.

## Transactional Publication

1. Analyze the source target and interface closure without writing destinations.
2. Generate final per-module C, metadata-bearing object input, and fingerprinted `.l1m` content in memory where
   practical.
3. Write generated C and interface text to unique temporary files in their destination directory. Compile the temporary
   C path with the host compiler's compile-only form into a temporary object sibling.
4. Verify all three staged files exist, are regular files, and correspond to the requested canonical module before
   publication begins.
5. Preserve any pre-existing destination set under unique same-directory backup names, rename the staged files into
   place, and remove backups only after all three replacements succeed. If any replacement fails, restore the previous
   set and remove staged files.
6. Signal interruption and ordinary error paths use the same cleanup helper. Temporary names never become candidates for
   `-I` discovery.
7. A failure before publication leaves every pre-existing destination unchanged. In particular, failed C compilation
   never exposes a newly generated `.l1m`.

## Implementation Phases

### Phase 1: Activate compile-mode validation

Replace the current NYI dispatch with the exact option matrix and canonical output-path validation. Keep help, shared
CLI documentation, and diagnostics aligned across the Stage 1 entry points.

### Phase 2: Compile one graph node

Resolve the source target plus interface-only imports, run semantic analysis for the target module, generate its
fingerprinted interface and per-module C, and assert that imported definitions cannot enter the output.

### Phase 3: Compile and publish the artifact set

Add the host compiler's object-only command path and the shared staging/backup/rollback helper. Preserve compiler
stdout, stderr, selected compiler family, environment options, and exit-status behavior from the existing build driver.

### Phase 4: Documentation and regression coverage

Update compile help and the CLI/architecture references. Add successful, failure, overwrite, cleanup, nested-module, and
interface-only dependency fixtures.

## Diagnostics

1. Reuse the remaining unassigned portion of the established compile-driver area: provisionally use `L1C-2033` through
   `L1C-2049` for compile target, output-path, host object compilation, staged publication, and rollback failures.
2. Interface discovery retains the `DRV-0072` through `DRV-0089` area owned by the module-graph plan; fingerprint and
   object-metadata failures retain their owning plans' families.
3. The range is provisional. Re-check the live [diagnostic catalog][diagnostic-catalog] immediately before
   implementation and choose another free range if any proposed code has been assigned.

## Non-Goals

1. Compiling any imported source module or emitting more than one module object.
2. Reading object metadata back, selecting an entry module, generating a process wrapper, or invoking the host linker.
3. Build caching, timestamp-based incremental compilation, package manifests, or library production.
4. Making `--build` or `--run` consume interfaces; the fan-out plan owns those flows.

## Verification Criteria

01. A dependency-free module produces the expected sibling `.c`, `.o`, and `.l1m` outputs.
02. A module with interface-backed imports produces only its own definitions and provider declarations.
03. Nested module names map to deterministic parent directories, and explicit `.o` output selects exact companion paths.
04. A missing or invalid imported interface fails without source fallback or destination changes.
05. Generated `.l1m` content has a verified whole-module fingerprint and the object classifies as valid Dea metadata.
06. Modules with and without source `main` carry the correct lifecycle and entry metadata.
07. Host C compilation failure leaves no newly published artifact and preserves any prior complete set byte-for-byte.
08. Simulated failure at each publication rename restores the old set and removes temporary/backup files.
09. Compile mode accepts only its documented compiler/codegen options and rejects link/run-only inputs.
10. Focused normal and trace tests pass, followed by `make -C l1 test` once implementation is complete.
11. Concrete new diagnostics are registered in the shared catalog before closure.

[diagnostic-catalog]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[fingerprints]: 2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[foundation]: closed/2026-04-24-separate-compilation-driver-surface-noref.md
[initiative]: ../../initiatives/0001-separate-compilation-and-linking.md
[lifecycle]: 2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md
[link-set]: 2026-07-17-link-set-driver-and-wrapper-noref.md
[module-graph]: closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[object-metadata]: 2026-07-17-object-metadata-emission-and-readers-noref.md
