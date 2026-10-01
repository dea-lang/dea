# AGENTS.md

Guidance for AI agents working in the `l1/` subtree of the Dea monorepo.

Read `../AGENTS.md` first for monorepo-wide policy, commit conventions, planning policy, shared `.venv`, and quality
standards.

Run commands from the `l1/` directory.

## Project Overview

Dea/L1 is in self-hosted development status.

- `compiler/stage1_l0/` is the initial L1 compiler seed implemented in Dea/L0.
- `compiler/stage2_l1/` is the mechanical L1 port, built by Stage 1 and capable of self-building.
- `compiler/shared/runtime/` is the copied shared runtime tree.
- `compiler/shared/l1/stdlib/` is the copied L1 stdlib seed.

## Bootstrap Contract

- Local development defaults to the repo-local upstream L0 Stage 2 compiler at `../l0/build/dea/bin/l0c-stage2`.
- Prepare that default with `make -C ../l0 use-dev-stage2`.
- Override the upstream compiler explicitly with `L1_BOOTSTRAP_L0C=/path/to/l0c-stage2`.
- Do not rely on whichever `l0c` happens to be active on `PATH`.

## C Compiler Support for Agent Work

- Full L1 support currently requires upstream Clang 16 or newer when selecting Clang. Clang 14/15 lack
  `--no-default-config`, which current managed preparation requires. A successful direct C compilation does not
  establish full L1 compatibility or persistent reuse capability.
- Do not use Clang older than 16 for routine L1 builds, tests, benchmarks, experiments, or candidate validation until
  legacy support is implemented and this guidance is updated. Use a supported GCC toolchain or verified modern Clang.
- Verify and record the selected compiler executable and version in each actual builder, test, and measurement
  environment. An image name or the host compiler version is not sufficient evidence. Apple Clang has separate version
  numbering; verify its required configuration capabilities and L1 preparation behavior.
- The repo-owned `l1-test` image uses Bookworm and supplies Clang 14. Keep the normal Docker lane on GCC; do not select
  `DOCKER_CC=clang` in that image for full validation. A modern investigation runtime does not upgrade the separate
  builder/test image. Set `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC` explicitly for custom validation invocations.
- The sole exception is deliberate, isolated legacy compatibility or regression validation under
  [l1/work/plans/bug-fixes/2026-09-27-legacy-clang-preparation-compatibility-noref.md][legacy-clang-plan]. Label these
  runs as compatibility investigations and retain a supported compiler control. Do not use their results as evidence of
  full support before the plan's acceptance criteria pass.

## Commands

```bash
make venv
make use-dev-stage2
source build/dea/bin/l1-env.sh
l1c --help
l1c --version
make check-examples
make test-stage1
make test-stage2
make test-stage2-trace
make triple-test
make test
make test-stage1-trace
make test-stage1-trace-smoke
make test-stage1-trace-all
make test-stage1-trace-children
make test-extended
make test-ci
```

`make test` is the fast local development gate. It runs representative Stage 1 and Stage 2 smoke tests, parity,
examples, Stage 2 tooling, and Docker/Wine runner regressions. Use it after ordinary implementation work.

`make test-extended` is the broad local-normal gate for subsystem work and refactors. It runs both Stage 1 and Stage 2
normal suites, parity, examples, Stage 2 tooling, and Docker/Wine runner regressions. Normal runner discovery excludes
CI-only cases. This target omits environment reconstruction, the dedicated trace sweeps, child trace fixtures, and
triple bootstrap.

Local normal discovery retains multiplication arithmetic, all six overflow fixtures through the already-built subject
compiler, and representative managed preparation. Embedded-driver overflow compilation remains in the CI-only
`mul_runtime_compile_test` and the default trace sweep. The installed read-only toolchain fixture
(`l1c_stage1_installed_preparation_test.py`) and preparation recovery/concurrency matrix
(`l1c_stage1_preparation_test.py`) are CI-only in both stages. Run either directly with
`make test-stage1 TESTS="<test-name>"` or `make test-stage2 TESTS="<test-name>"` when changing those behaviors.

`make test-ci` is the exhaustive hosted gate. It runs `test-extended` with CI-only normal cases included, followed by
environment/bootstrap integration, both default Stage 1 and Stage 2 ARC/memory trace suites, both child-fixture suites,
and triple bootstrap. Runner output lists included CI-only cases and each category has a visible boundary. Use `test-ci`
for hosted-equivalent exhaustive validation. For subsystem changes, run the corresponding direct target or explicit test
selector; a change involving trace, environment, child-process, preparation, or fixed-point behavior does not by itself
require the entire `test-ci` suite.

`make test-stage1-trace` is the default ARC/memory trace suite and skips intentionally slow trace cases such as
`math_runtime_compile_test`. Use `make test-stage1-trace-all` to include those slow trace checks, or pass a slow test
explicitly with `TESTS="math_runtime_compile_test"` when investigating it.

Normal CI-only classification does not filter dedicated trace discovery; `slice_trace_test` remains in the default trace
sweep. The slow-trace policy is independent of the normal-suite cost policy.

`make test-stage1-trace-children` is the focused suite for successful L1 math runtime fixtures. It builds traced child
executables and analyzes each child's stderr separately; `TESTS="wide_math_main"` selects one fixture. `make test-ci`
always runs both declared children for each stage, independently of parent `TESTS` selectors.

`make test-stage1-trace-smoke` retains the focused ARC/memory trace subset for quick developer diagnostics. Hosted
Windows, Linux, and macOS run `make test-ci`, which includes the complete local-normal suites plus CI-only normal cases,
environment/bootstrap validation, default trace suites, child fixtures, and strict triple bootstrap.

`use-dev-stage1` and `use-dev-stage2` explicitly select the `l1c` alias. Build and test commands preserve its selection.
Stage 2 exposes the same trace target suffixes as Stage 1. `triple-test` runs the final self-built compiler through its
normal suite and examples; it is included in `test-ci` and excluded from `test` and `test-extended`. `make test-docker`
runs the broad local-normal `test-extended` target in the repo-owned Linux image; use `make docker CMD=test-ci` for the
exhaustive L1 container path.

## Current Scope

- This subtree supports local self-hosted development; delivery workflows remain separate.
- There is no L1 install/dist/release/docs-publish workflow yet.
- Keep root `README.md` and existing L0 user-facing docs unchanged unless the task explicitly requires a minimal
  consistency fix.

## Documentation Link Style

- This guidance is L1-only. Do not apply it to `l0/` or to monorepo-root docs by default.
- For new Markdown documents under `l1/docs/` and `l1/work/`, prefer CommonMark/GFM reference-style links over inline
  `[text](path)` links when linking repository files.
- Keep reference ids short and readable, typically one or two words joined with hyphens, such as
  `[interface-fingerprints]` or `[runtime-library]`.
- Do not include dates, numeric plan/initiative prefixes, `noref`, or file extensions in reference ids unless a real
  uniqueness conflict leaves no cleaner option.
- Reuse one reference id per target within a file, and place the reference definitions at the end of the document.
- This is a preferred style for new L1 docs and work docs. It is not a blanket backfill requirement for existing closed
  plans, and it does not require rewriting existing initiative documents unless the task explicitly asks for it.

[legacy-clang-plan]: work/plans/bug-fixes/2026-09-27-legacy-clang-preparation-compatibility-noref.md
