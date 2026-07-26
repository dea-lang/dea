# Bug Fix Plan

## Repair Stage 1 cross-platform CI regressions

- Date: 2026-07-26
- Status: In Progress
- Title: Repair Stage 1 cross-platform CI regressions
- Kind: Bug Fix
- Severity: High
- Stage: 1
- Parent Initiative: [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative]
- Roadmap: [`l1/docs/roadmap.md`][roadmap]
- Subsystem: Public runtime header / native compiler commands / compile-only filesystem policy / CI toolchain selection
- Modules:
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/stage1_l0/src/compile_driver.l0`
  - `l1/compiler/stage1_l0/support/interface_fingerprint.c`
  - `l1/Makefile`
  - `.github/actions/l1-ci/action.yml`
- Test modules:
  - `l1/compiler/stage1_l0/tests/interface_fingerprint_runtime_test.py`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/object_reader_test.l0`
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_support_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_compile_only_test.py`
  - `l1/compiler/stage1_l0/tests/compiler_runtime_build_env_test.py`
- Related:
  - [`l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md`][fingerprints]
  - [`l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md`][object-metadata]
  - [`l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md`][compile-only]
  - [`l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md`][transaction-adr]
- Repro: [Unified CI run 30212969416][ci-run]

## Summary

The current unified CI run exposes four related Stage 1 portability defects. Strict GCC diagnoses unused mutable storage
created by simply including the public runtime header. Two native-object smoke tests bypass the Windows-safe shell-word
joiner. Compile-only output-parent validation lets a dangling Windows directory symlink reach transaction creation.
Finally, CI and Docker do not apply one selected C compiler consistently to bootstrap, generated-program, and runtime
roles, which makes the exercised toolchain difficult to audit.

## Root Cause

The public header defines three sentinel values as file-scope static objects even when a translation unit never uses
them. The two smoke tests manually prepend a shell-quoted compiler instead of passing raw argv words through the shared
command builder. Output-parent validation consults the public `std.fs::is_dir` follow behavior before the compiler's
no-follow classifier, and MinGW reports a dangling directory symlink as directory-shaped. The L1 CI delegate omits
`L1_CC`, while the Docker recipe forwards only an optional `L0_CC`, leaving the runtime and generated-program roles to
independent fallback selection.

## Scope of This Fix

1. Replace the three public header sentinel objects with typed ISO C99 compound-literal value macros, preserving their
   names and values without adding external symbols or weakening warnings.
2. Route both native-object smoke commands through `bd_join_shell_words` with their existing GCC/MSVC argument sets.
3. Add a compiler-private follow-mode path classifier and make compile-only parent creation distinguish missing paths
   from dangling aliases while preserving valid directory aliases and `L1C-2033`.
4. Align `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC` in CI and Docker, add auditable compiler version reporting, and introduce
   `DOCKER_CC` with `DOCKER_L0_CC` as a compatibility fallback.
5. Add focused regression coverage for header inclusion, sentinel values, Windows command execution, follow/no-follow
   alias classification, compile-only rollback, and Docker variable propagation.

## Non-Goals

- Adding a recurring compiler-version matrix or pinning hosted-runner compiler majors.
- Changing public `std.fs`, the runtime ABI, `dea_rt.symbols`, the LBI/object formats, or the CLI.
- Adding diagnostics or changing the meanings of `L1C-2033` and `L1C-9511`.
- Hardening the trusted-parent filesystem race model beyond collision revalidation.
- Backporting the L1-only fix to L0.

## Verification Criteria

1. An otherwise empty C99 translation unit can include the delivered runtime header under strict GCC warnings, and all
   three sentinel value representations remain exact.
2. The backend and object-reader native compiler smoke tests pass on Windows without changing production quote rules.
3. Real directories and valid directory aliases are accepted; file aliases, dangling directory aliases, loops, and other
   invalid output parents fail with `L1C-2033` before staging and leave no transaction artifacts.
4. CI and Docker logs identify all three effective compiler roles and their resolved versions; Docker defaults all roles
   to Bookworm GCC, with one `DOCKER_CC` override and legacy `DOCKER_L0_CC` compatibility.
5. Focused normal and trace suites, full host GCC 16 validation, the full Docker GCC 12 gate, staged pre-commit, and the
   existing macOS/Ubuntu/Windows CI lanes pass.

## Local Implementation

- Public runtime sentinel objects are typed C99 value macros, with strict include-only and value-representation coverage
  across every runtime archive.
- Native-object smoke tests build raw compiler argv vectors through the shared shell-word joiner.
- The compiler-private filesystem ABI classifies both followed targets and lexical no-follow entries; compile-only
  parent creation now rejects dangling aliases before transaction creation and preserves valid directory aliases.
- CI applies one selected compiler to all three roles. Docker defaults those roles to GCC through `DOCKER_CC`, with the
  legacy selector retained as a compatibility fallback, and both entry points report resolved compiler versions.
- The accepted compile-only publication ADR now records the compiler-private follow/no-follow implementation.

## Local Verification

```bash
make -C l1 L0_CC=gcc-16 L1_CC=gcc-16 L1_RUNTIME_CC=gcc-16 \
  test-stage1 \
  TESTS="build_driver_test backend_test object_reader_test compile_driver_test interface_fingerprint_runtime_test.py runtime_symbol_manifest_test.py compiler_filesystem_support_test.py l1c_stage1_compile_only_test.py compiler_runtime_build_env_test.py"
make -C l1 L0_CC=gcc-16 L1_CC=gcc-16 L1_RUNTIME_CC=gcc-16 \
  test-stage1-trace \
  TESTS="build_driver_test backend_test object_reader_test compile_driver_test"
make -C l1 clean-all
make -C l1 L0_CC=gcc-16 L1_CC=gcc-16 L1_RUNTIME_CC=gcc-16 test-all
make -C l1 test-docker
```

Results:

- The integrated focused GCC 16 normal gate passed all 9 selected suites.
- The focused GCC 16 trace gate passed all 4 selected suites.
- The clean full GCC 16 gate passed 61 normal suites, environment stackability, all 4 examples, and 42 default trace
  suites.
- The Docker gate resolved all three roles to Debian GCC 12.2.0 and passed the same 61 normal suites, environment
  stackability, 4 examples, and 42 trace suites.
- Remote Ubuntu, Windows, and macOS CI verification remains pending the manual gate below.

## Manual Remote Gate

Implementation, local testing, plan closure, and a local commit do not authorize a push or workflow dispatch. Before
updating `origin/ci-probe` or rerunning the GitHub Actions workflow, require fresh user confirmation that discloses the
pending commit range, the exact remote branch, and the CI/CD effects of that push or dispatch.

[ci-run]: https://github.com/googlielmo/DEA/actions/runs/30212969416
[compile-only]: ../features/closed/2026-07-17-compile-only-artifact-production-noref.md
[fingerprints]: ../features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[initiative]: ../../initiatives/0001-separate-compilation-and-linking.md
[object-metadata]: ../features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md
[roadmap]: ../../../docs/roadmap.md
[transaction-adr]: ../../../docs/decisions/0022-transactional-compile-only-artifact-publication.md
