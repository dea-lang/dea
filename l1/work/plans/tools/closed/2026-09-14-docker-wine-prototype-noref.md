# Tool Plan

## Cached Wine/MSYS2 feasibility runner

- Date: 2026-09-14
- Status: Completed
- Title: Cached Wine/MSYS2 feasibility runner
- Kind: Tooling
- Severity: Medium
- Stage: 1
- Subsystem: L1 developer validation
- Modules:
  - `l1/Makefile`
  - `l1/scripts/docker_wine.py`
  - `l1/docker/wine/`
- Test modules:
  - `l1/tests/test_docker_wine.py`
- Repro: `make -C l1 docker-wine CMD=help`
- Related:
  - [l1/docker/wine/README.md][wine-guide]
  - [l1/work/plans/bug-fixes/closed/2026-09-13-native-preparation-ci-portability-noref.md][portability]

## Summary

Add an opt-in L1 feasibility prototype using the upstream experimental MSYS2 image and patched Wine. Cache package
installation in independent Docker layers, cache the Windows Python environment separately, and transfer current sources
into disposable containers without rebuilding images on ordinary runs. L0 is included only as L1's bootstrap.

## ADR Impact

- Decision: Add an experimental local Windows compatibility probe without changing supported host validation.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This bounded developer prototype does not change compiler architecture, supported platforms, or the
    authority of native Windows CI. Its operational cache choices remain local implementation details.

## Implementation

- Pin the upstream amd64 image digest; retain and document its experimental package-signature policy.
- Separate MSYS tools, GCC, Python and uv installation layers, then prepare the workspace venv in a dependent image.
- Cache Python/uv package downloads and omit their documentation/manual files after observing excessive OpenSSL manual
  extraction cost under Wine; retain runtime data, libraries, headers and Python modules.
- Derive image tags from their actual inputs; inspect and reuse existing images before considering a build.
- Transfer a filtered working-tree snapshot at execution time, including uncommitted sources and excluding host builds.
- Preserve Make arguments, test selectors, job controls, trace artifacts and exit status.
- Keep L0 targets, native CI, and ordinary Linux Docker behavior unchanged.

## Verification Criteria

- Regression tests cover cache reuse/invalidation, failed builds, source filtering, argument boundaries and artifacts.
- Build the toolchain and environment images with reusable successful intermediate layers.
- Exercise repeated `CMD=help` runs and prove no Docker build is issued on reuse.
- Probe Windows Python/GCC, L0 bootstrap, focused Windows regressions and L1 tests; record any Wine limitations without
  weakening production tests or presenting unexecuted checks as passed.
- Run applicable native L1 validation and staged repository checks.

## Validation completed

- Native `make -C l1 clean test-all L1_TEST_JOBS=4 L1_TRACE_TEST_JOBS=2`: 82 normal tests, environment stackability,
  four examples and 46 dedicated traces passed. Reuse this completed result: subsequent edits are confined to the new
  Wine runner/image recipes, its independent regressions, help text and documentation; no compiler, runtime or existing
  native test inputs changed and no external edits were observed.
- `make -C l1 test-docker-wine-runner`: all six regressions passed separately after integration into the normal
  aggregate.
- Real toolchain/environment builds succeeded. Retrying later toolchain layers reused the completed tools/GCC layers.
  Two `make -C l1 docker-wine CMD=help` invocations each reported both images reused and issued no build command.
- Windows GCC compiled and ran a native executable. Windows Python reported `os.name == "nt"`. A quoted Make argument
  probe persisted a host artifact, and a deliberate Windows shell exit propagated status 37 through Docker.
- `make -C l1 docker-wine CMD='test-env check-examples test-docker-wine-runner test-stage1-trace' TESTS=string_vector_test L1_TRACE_TEST_JOBS=1 L1_TRACE_ARTIFACT_DIR=build/wine-traces`:
  passed. Four examples and six runner regressions passed; the trace had 309 events with zero errors, warnings or leaks,
  and its report survived container removal. The existing POSIX environment-stackability check reported its expected
  Windows skip.
- A supplemental same-container build attempt was discarded after Windows rejected replacement of the executable in use
  by the main suite. The successful supplemental run above used its own isolated container.

## Outcome

The L1-first feasibility prototype is implemented with reusable toolchain and venv images and no Docker build command on
image reuse. Windows bootstrap, example validation, runner regression tests, argument/artifact transport and a focused
trace check work. L0 is present only as the bootstrap dependency; no L0 target was added.

The complete
`make -C l1 docker-wine CMD='test test-stage1-trace-smoke' L1_TEST_JOBS=2 L1_TRACE_TEST_JOBS=1 L1_TRACE_ARTIFACT_DIR=build/wine-traces`
run completed with 75 normal tests passed and seven failed, then propagated Make failure. The trace-smoke target was not
reached. Successful wrapper statuses can include optional-tool skips. The independent focused trace command above
passed. The seven failures and their diagnostic limits are recorded in [l1/docker/wine/README.md][wine-guide]: three
path/argument checks, two GCC archiver-discovery failures, one effective-target discovery failure and one existing
runtime-build timeout. Only the filesystem path mismatch was separately instrumented; the other causes remain follow-up
investigations. Production tests and timeout expectations were not weakened.

The prototype is useful for repeatable local Windows-code probes, but does not provide a clean replacement for native
Windows CI. Its supported-platform contract is unchanged. Toolchain images and successful Docker layers remain cached
locally for subsequent invocations.

## Non-goals

L0's full validation workflow, ARM64 support, image publication, native Windows CI replacement and a maintained Wine
fork are outside this prototype.

[portability]: ../../bug-fixes/closed/2026-09-13-native-preparation-ci-portability-noref.md
[wine-guide]: ../../../../docker/wine/README.md
