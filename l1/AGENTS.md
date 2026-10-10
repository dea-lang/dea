# AGENTS.md

Guidance for the `l1/` subtree. Read [AGENTS.md](../AGENTS.md) first and run level commands from `l1/`.

## Project Overview

L1 has one canonical compiler, `l1c`, implemented in L0 under `compiler/src/` with `.l0` sources. It accepts L1 `.l1`
programs and `.l1m` interfaces. L1 owns `compiler/shared/l1/stdlib/`, `compiler/shared/runtime/`, and its native support
under `compiler/support/`. The former L1 Stage 2 is now L2; L1 has no stage selector, parity, or triple bootstrap.

## Bootstrap Contract

Build with `L1_BOOTSTRAP_L0C=/absolute/path/to/l0c-stage2`. The development default remains
`../l0/build/dea/bin/l0c-stage2`, prepared with `make -C ../l0 use-dev-stage2`. Invalid explicit selection fails; never
select an ambient `l0c` from PATH. L0 is a build-time dependency. Installed L1 use needs no bootstrap compiler, source
checkout, Python, or Make; native output still needs supported host compiler/linker and preparation tools.

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

## Commands and Validation

```sh
make venv
make build
make use-dev
source build/dea/bin/l1-env.sh
make test
make test-extended
make test-compiler TESTS="parser_test"
make test-compiler-trace TESTS="lexer_test"
make test-compiler-trace-smoke
make test-compiler-trace-all
make test-compiler-trace-children
make test-ci
make check-examples
make test-productization
make docs-artifacts DEA_DIST_VERSION=dev
make install PREFIX=/absolute/fresh-prefix
make list-installed PREFIX=/absolute/fresh-prefix
make dist DOCS_ARTIFACT=/absolute/dea_l1_autodocs.tar.gz DIST_RESULT=/absolute/result.json
make smoke-dist ARCHIVE=/absolute/archive.tar.gz
make test-productization-acceptance DOCS_ARTIFACT=/absolute/dea_l1_autodocs.tar.gz ACCEPTANCE_DIR=/absolute/new-evidence
```

`test` is the fast local gate; `test-extended` runs the complete normal compiler suite, examples, and tooling. `test-ci`
includes CI-only normal cases and applicable environment, trace, and child-fixture gates. Use focused selectors when
changing one subsystem. Dedicated trace discovery has a separate slow-case policy: slow cases are explicit or in
`test-compiler-trace-all`. CI-only classification in normal discovery does not suppress dedicated trace coverage.

`test-productization` checks fixture-based installation, inventory/recovery, installed startup, archives, and atomic
results. `test-productization-acceptance` separately builds and verifies actual documented artifacts with portable exact
archive/result/harness evidence. `ACCEPTANCE_PHASE=build` creates the build handoff; the existing four-platform workflow
verifies on fresh runners without checkout or bootstrap artifacts. A combined local invocation does not demonstrate
checkout unavailability. None of `test`, `test-extended`, or `test-ci` establishes artifact acceptance.

## Delivery and Documentation

Installation builds a private installed-mode canonical compiler with matching semantic interfaces, rebuild inputs, and
provenance. It preserves development artifacts. `list-installed` is inventory-only with no build/venv/cache
prerequisite. Direct installation permits optional `DOCS_ARTIFACT`; distributions require verified matching canonical
HTML/full PDF. Stage-free schema-2 artifacts use fresh prefixes; do not relabel historical Stage 2 artifacts or retain
their acceptance as evidence for the new compiler. Reference generation selects actual `.l0` compiler inputs and L1
support.

Fresh native artifact acceptance is required on Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64. Report pending
platform/hosted evidence explicitly. Hosted releases remain separate work and require normal authorization gates. L1 is
not frozen and its feature plans are not automatically migrated to L2. Explicit profiles/composable builds remain
planned for L1 first, then L2, with no implementation in the split.

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
