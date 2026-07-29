# Feature Plan

## Produce compile-only artifacts with endpoint rollback

- Date: 2026-07-25
- Status: Completed
- Title: Produce compile-only object, interface, and optional C artifacts with endpoint rollback
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
  - `l1/compiler/stage1_l0/src/compile_driver.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/support/interface_fingerprint.c`
  - `l1/scripts/build_stage1_l1c.py`
  - `docs/specs/compiler/cli-contract.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - `l1/docs/project-status.md`
  - `l1/docs/reference/architecture.md`
  - `l1/docs/reference/c-backend-design.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/source_paths_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/compile_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_support_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_compile_only_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_help_output_test.py`
- Related:
  - [`l1/work/plans/features/closed/2026-04-24-separate-compilation-driver-surface-noref.md`][foundation]
  - [`l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md`][module-graph]
  - [`l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md`][fingerprints]
  - [`l1/work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md`][lifecycle]
  - [`l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md`][object-metadata]
  - [`l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md`][link-set]
  - [`l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md`][stage1-temp-safety]
  - [`work/plans/bug-fixes/closed/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md`][native-temp-safety]
  - [`docs/specs/compiler/diagnostic-code-catalog.md`][diagnostic-catalog]
- Repro:
  `make -C l1 test-stage1 TESTS="cli_args_test source_paths_test driver_test backend_test interface_test build_driver_test compile_driver_test l1c_lib_test compiler_filesystem_support_test.py l1c_stage1_compile_only_test.py l1c_stage1_help_output_test.py"`

## Summary

Make the reserved `-c` / `--compile` mode operational only after the module graph, canonical fingerprints, per-module
backend, lifecycle ABI, and object metadata shape have landed. One invocation compiles exactly one source module against
interfaces and publishes one sibling `.o` and `.l1m` reusable set. `--keep-c` also publishes the exact generated `.c`
used to compile the object. The mode never folds source-import definitions into the object and never invokes the final
host linker.

Generated C, the compiled object, and the verified interface are prepared inside one exclusively reserved sibling
transaction directory before any selected destination is replaced. Publication uses sequential backup and rename
operations with endpoint rollback: successful return leaves the complete new selected set, while a recoverable failure
returns with the prior selected set restored. This is not an atomic reader-visible snapshot.

## Dependencies and Ownership

1. The [module graph][module-graph] owns canonical paths, `MRP_REQUIRE_INTERFACE` discovery, and transitive dependency
   state.
2. [Interface fingerprints][fingerprints] must make emitted `.l1m` files self-verifying.
3. The completed [lifecycle plan][lifecycle] defines final one-module C output, and [object metadata][object-metadata]
   must make the resulting object a complete Dea link input.
4. This plan owns compile-mode CLI activation, output resolution, the host `cc -c` step, and endpoint rollback for
   publication failures.
5. The [link-set plan][link-set] consumes the published object but does not reopen the `.l1m` during standalone linking.
6. The completed [L0 Stage 1 temporary-C fix][stage1-temp-safety] closes the demonstrated bootstrap prerequisite. The
   completed shared [native temporary-workspace safety plan][native-temp-safety] owns global `--build` / `--run`
   workspaces, but remains separate from compile-only: this mode reserves its transaction directory beside the requested
   destinations and does not reuse the command-owned native build/run workspace.

## CLI and Artifact Contract

The public form is:

```text
l1c -c MODULE [-I ROOT]... [-o CANONICAL_OBJECT_PATH] [--keep-c]
```

1. `MODULE` resolves to one source implementation. An interface cannot replace the compilation target.
2. Every non-virtual import uses the module graph's `MRP_REQUIRE_INTERFACE` policy. Missing, malformed, or
   dependency-broken interfaces fail; compile-only never falls back to provider source.
3. Without `-o`, the current working directory is the artifact root and the canonical dotted module path supplies the
   stem. `foo.bar` produces `foo/bar.o` and `foo/bar.l1m`; `--keep-c` also produces `foo/bar.c`.
4. With `-o`, the value must be a non-empty `.o` file path without a trailing `/` or `\`. The same stem and directory
   with `.c` and `.l1m` suffixes are its canonical companions. Empty values, trailing separators, extensionless paths,
   directories, and non-`.o` suffixes report `L1C-2033` in the compile-only layer rather than reaching generic artifact
   identity construction.
5. Parent directories are created before staging. Existing parent components use `std.fs::is_dir()`, whose semantics
   follow trusted directory aliases; missing descendants beneath an alias are created recursively. Dangling aliases and
   aliases to non-directories are rejected. Final selected artifact destinations use no-follow classification and must
   be regular files when present, so a symlink `.c`, `.o`, or `.l1m` destination is rejected.
6. `--output`, `--c-compiler`, `--c-options`, `--runtime-include`, line-directive controls, and codegen/runtime-checking
   controls needed to produce the object become valid in compile mode, as does `--keep-c`. `--runtime-lib`, `--entry`,
   external-library flags, and runtime program arguments remain invalid because `-c` does not link or run.
7. Generated C is always an internal staged input to the host compiler. It becomes a public output only with `--keep-c`;
   otherwise the compiler never classifies, backs up, creates, overwrites, removes, or restores the canonical `.c` path.

## Endpoint-Rollback Publication

1. Analyze the source target and interface closure without writing destinations.
2. Generate final per-module C, metadata-bearing object input, and fingerprinted `.l1m` content in memory where
   practical.
3. Atomically create one unique transaction directory beside the destinations, rejecting rather than reusing any
   pre-existing candidate. Request mode `0700` on POSIX and use the repository's supported atomic Windows directory
   creation path. Write generated C and interface text inside it, then compile the staged C path with the host
   compiler's compile-only form into a staged object in the same directory.
4. Verify all three staged files exist, are regular files, and correspond to the requested canonical module before
   publication begins.
5. Preserve any pre-existing selected destination set under backup names inside the transaction directory, publish
   generated C only with `--keep-c`, publish the object, and publish the interface last. Remove backups only after all
   selected replacements succeed. If any replacement fails, restore the previous selected set before removing staged
   files.
6. Ordinary error paths use the same cleanup helper. An abrupt process termination may leave the uniquely named
   transaction directory for recovery, but later invocations never reuse it and its contents never become candidates for
   `-I` discovery.
7. A failure before publication leaves every selected pre-existing destination unchanged. In particular, failed C
   compilation never exposes a newly generated `.l1m`, and ordinary `-c` leaves any canonical `.c` path untouched. If
   rollback itself fails, retain the transaction directory and recovery files and report the dedicated rollback
   diagnostic rather than deleting the remaining evidence.
8. Successful return leaves every selected destination at the new generation. A recoverable publication failure returns
   with the exact prior selected set restored. Sequential backup, publication, and rollback may make paths temporarily
   absent or expose different generations at different selected paths while the operation is in progress.

## Publication Boundary and Threat Model

1. Endpoint rollback protects the selected artifact-set result across normal analysis, emission, host-compilation,
   publication, and rollback failures. It does not provide an atomic reader-visible snapshot. Concurrent readers and
   same-stem writers require external serialization.
2. Exclusive directory creation prevents an existing sibling path from being mistaken for the invocation's staging area.
   Final artifact, transaction, backup, validation, and cleanup paths use no-follow classification; trusted directory
   aliases in the output-parent chain are followed for directory validation and recursive creation.
3. The caller-selected destination parent and selected C compiler are trusted inputs. This plan does not claim
   containment from a same-account process that can mutate that parent, an administrator, or a malicious C compiler.
4. Global compiler temporary-root selection and native `--build` / `--run` workspace cleanup are governed by the
   completed shared [native temporary-workspace safety plan][native-temp-safety].

## Implementation Phases

### Phase 1: Activate compile-mode validation

Replace the current NYI dispatch with the exact option matrix and canonical output-path validation. Keep help, shared
CLI documentation, and diagnostics aligned across the Stage 1 entry points.

### Phase 2: Compile one graph node

Resolve the source target plus interface-only imports, run semantic analysis for the target module, generate its
fingerprinted interface and per-module C, and assert that imported definitions cannot enter the output.

### Phase 3: Compile and publish the artifact set

Add the host compiler's object-only command path, a small L1 Stage 1 filesystem support ABI for exclusive directory
creation, no-follow artifact classification, alias-following directory checks, same-filesystem rename/removal, and the
shared staging/backup/rollback helper. Preserve compiler stdout, stderr, selected compiler family, environment options,
and exit-status behavior from the existing build driver.

### Phase 4: Documentation and regression coverage

Update compile help and the CLI/architecture references. Add successful, failure, overwrite, cleanup, nested-module, and
interface-only dependency fixtures.

## Diagnostics

1. `L1C-2033`: invalid selected compile-only destination or destination parent.
2. `L1C-2034`: staged compile-only artifact validation failed.
3. `L1C-2035`: artifact-set publication failed and the previous set was restored.
4. `L1C-2036`: rollback failed and recovery files were retained.
5. Reuse `L1C-0009` for C compiler discovery, `L1C-0010` for host C compilation failure, and `L1C-9511` for an output or
   staging write failure. Target resolution, interface discovery, fingerprints, and object metadata retain their owning
   diagnostic families.

## ADR Impact

- Decision: Publish the compile-only object and interface, plus exact generated C only when requested, with output-local
  staging and endpoint rollback rather than a reader-visible snapshot.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md`
  - Rationale: ADR-0022 records the selected artifact set, validation, publication order, rollback, recovery, and
    concurrency boundary.

## Non-Goals

1. Compiling any imported source module or emitting more than one module object.
2. Selecting link inputs or an entry module from object metadata, generating a process wrapper, or invoking the host
   linker.
3. Build caching, timestamp-based incremental compilation, package manifests, or library production.
4. Making `--build` or `--run` consume interfaces; the fan-out plan owns those flows.
5. Replacing the shared native build/run temporary-workspace design or defending a caller-controlled output parent from
   another process with the same filesystem authority.

## Verification Criteria

01. A dependency-free module produces the expected sibling `.o` and `.l1m` outputs without a canonical `.c`.
02. `--keep-c` adds the exact staged `.c` to the same successful selected set.
03. A module with interface-backed imports produces only its own definitions and provider declarations.
04. Nested module names map to deterministic parent directories, and explicit `.o` output selects exact companion paths.
05. A missing or invalid imported interface fails without source fallback or selected destination changes.
06. Generated `.l1m` content has a verified whole-module fingerprint and the object classifies as valid Dea metadata.
07. Modules with and without source `main` carry the correct lifecycle and entry metadata.
08. Host C compilation failure leaves no newly published artifact and preserves any prior selected set byte-for-byte.
09. Simulated failure at each selected publication rename restores the old selected set and removes temporary/backup
    files.
10. Ordinary `-c` preserves a pre-existing canonical `.c` path, including a non-regular path, across success and
    failure.
11. A direct directory alias is accepted as an output parent, and a missing nested parent beneath it is created.
12. Dangling and non-directory parent aliases plus symlink final artifact destinations are rejected with `L1C-2033`.
13. Empty and trailing-`/` or trailing-`\` `-o` values report only `L1C-2033`, never `DRV-0072`.
14. A pre-existing transaction-directory candidate is never reused, and an unrecoverable rollback retains recovery files
    while reporting `L1C-2036`.
15. Endpoint tests prove successful return leaves the complete new selected set and recoverable failure restores the
    exact prior set; the contract does not claim reader-visible atomicity during publication or rollback.
16. Compile mode accepts only its documented compiler/codegen options and rejects link/run-only inputs.
17. Focused normal and trace tests pass, followed by `make -C l1 test` once implementation is complete.
18. Concrete new diagnostics are registered in the shared catalog before closure.

## Outcome

Implemented 2026-07-24; endpoint and concurrency contract corrected 2026-07-26.

- `-c` / `--compile` resolves one source target with interface-only imports, emits staged per-module C and a
  fingerprinted interface, compiles one metadata-bearing relocatable object, and publishes `.o` plus `.l1m` with
  endpoint rollback; `--keep-c` also publishes the exact staged C.
- The compiler-private filesystem ABI follows trusted directory aliases while creating output parents, then reserves
  sibling transaction directories and provides no-follow artifact classification, no-clobber same-filesystem moves, and
  empty-directory cleanup on POSIX and MinGW.
- Successful return leaves the complete new selected set. Recoverable publication failure restores the exact prior set;
  failed rollback retains recovery files and reports their directory. Publication and rollback do not provide a
  concurrent-reader snapshot.
- `L1C-2033` through `L1C-2036` are registered, live CLI and architecture documentation describe the implemented mode,
  and focused normal, trace, L1, and monorepo validation cover the shipped boundary.

Validation:

- Focused Stage 1 normal suite: 6 passed, including the filesystem ABI, pair/triple endpoint-rollback matrices, CLI,
  help, and end-to-end compile-only tests.
- Focused `compile_driver_test` ARC/memory trace: 1 passed.
- `make test` from `l1/`: 61 Stage 1 tests, environment stackability, and 4 examples passed.
- Root `make test`: L0 Stage 1 (`1431 passed`), L0 Stage 2 (`54 passed`), all L0 workflow/example checks, and the
  complete L1 validation passed.

[diagnostic-catalog]: ../../../../../docs/specs/compiler/diagnostic-code-catalog.md
[fingerprints]: 2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[foundation]: 2026-04-24-separate-compilation-driver-surface-noref.md
[initiative]: ../../../initiatives/0001-separate-compilation-and-linking.md
[lifecycle]: 2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md
[link-set]: 2026-07-17-link-set-driver-and-wrapper-noref.md
[module-graph]: 2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[native-temp-safety]: ../../../../../work/plans/bug-fixes/closed/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md
[object-metadata]: 2026-07-17-object-metadata-emission-and-readers-noref.md
[stage1-temp-safety]: ../../../../../l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md
