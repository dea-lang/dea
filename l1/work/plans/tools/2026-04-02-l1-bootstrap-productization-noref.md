# Tool Plan

## Define the self-hosted L1 Stage 2 install and distribution workflow

- Date: 2026-04-02
- Last reviewed: 2026-10-09
- Status: In progress
- Title: Define the self-hosted L1 Stage 2 install and distribution workflow
- Kind: Tooling
- Severity: Medium
- Stage: L1
- Target status:
  - Prefix installer, inventory, and launcher adaptation: Implemented (public install/list targets, optional Stage 2
    docs, and private bootstrap orchestration; full four-platform artifact acceptance pending)
  - Native installed-state guard and package provenance: Implemented; four-platform acceptance pending
  - Distribution archive, atomic result metadata, and reusable artifact smoke command: Implemented
  - Acceptance target and isolated four-platform workflow: Implemented; hosted execution pending
  - Stage 2 HTML/PDF inclusion: Implemented for direct installs and required distributions
  - Native artifact acceptance: Linux x86_64 and macOS Intel passed with full generated Stage 2 docs; macOS ARM and
    Windows UCRT64 pending
  - Final documentation, delivery ADR, and plan closure: Pending
- Subsystem: Build workflow / install layout / distribution packaging / bootstrap docs
- Modules:
  - `l1/Makefile`
  - `l1/scripts/`
  - `l1/scripts/productization_inventory.py`
  - `l1/scripts/productization_launchers.py`
  - `l1/scripts/productization_provenance.py`
  - `l1/scripts/productization_payload.py`
  - `l1/scripts/install_toolchain.py`
  - `l1/scripts/productization_acceptance.py`
  - `.github/workflows/l1-productization-acceptance.yml`
  - `l1/scripts/package/`
  - `l1/docs/user/`
  - `l1/compiler/stage1_l0/support/installation.h`
  - `l1/scripts/build_stage2_l1c.py`
  - `l1/scripts/triple_bootstrap.py` (reuse fixed-point validation)
  - `l1/compiler/stage1_l0/src/build_info.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/compile_driver/compile.l0`
  - `l1/compiler/stage1_l0/src/link_driver/toolchain.l0`
  - `l1/compiler/stage1_l0/support/` (native prefix/state support)
  - `l1/compiler/stage2_l1/src/` (packaged compiler, build-info overlay, and installed startup)
  - `l1/compiler/shared/`
  - `l1/docs/`
  - `l1/docs/reference/productization-inventory.md`
  - `scripts/dea_tooling/`
  - `docs/specs/compiler/cli-contract.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Test modules:
  - `l1/tests/test_bootstrap_productization.py` (new install/dist regression suite)
  - `l1/tests/test_env_stackability.py`
  - `l1/tests/test_stage2_tooling.py`
  - `l1/tests/test_stage2_build_overlay.py`
  - `l1/tests/test_installation_guard.py`
  - `l1/tests/test_productization_payload.py`
  - `l1/tests/test_install_toolchain.py`
  - `l1/tests/test_productization_acceptance.py`
  - `l1/tests/test_bootstrap_identity.py`
  - `l1/compiler/stage1_l0/tests/compiler_runtime_build_env_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_build_config_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_compile_only_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_link_set_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_installed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_bootstrap_interfaces_test.py`
  - `l1/compiler/stage2_l1/tests/stage_parity_test.py`
  - Stage 1 and Stage 2 shared installed-state diagnostic cases
- Related:
  - `work/plans/refactors/closed/2026-04-02-l1-bootstrap-scaffold-noref.md`
  - [l1/work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][stdlib-preparation]
  - [work/plans/tools/2026-05-12-l1-gha-release-snapshot-workflows-noref.md][release-workflows]
  - [MONOREPO.md][monorepo]
  - [l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md][installed-inputs]
  - [l1/docs/reference/stdlib-preparation.md][preparation-contract]
  - [l1/AGENTS.md][l1-guidance]
  - [l0/docs/decisions/0023-toolchain-installation-and-distribution-layout.md][l0-delivery]
  - [l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md][autodocs]

## Summary

The `l1/` subtree supports repo-local Stage 1 and self-hosted Stage 2 development. This plan adds a relocatable
install-prefix workflow and a curated distribution archive for the self-hosted Stage 2 toolchain, with the semantic
interfaces and stdlib/runtime rebuild inputs defined below.

Follow L0's delivery model: Stage 1 remains the bootstrap and development oracle, while installation and distribution
ship only the self-hosted Stage 2 compiler. The installed `l1c` selects Stage 2. Local packaging does not establish an
active release line or stable language/toolchain maturity. Hosted publication remains owned by the separate
release-workflow plan.

## Current State

Reviewed on 2026-10-09 against the local checkout:

01. `l1/` supports both compiler stages, observable stage parity, and strict triple bootstrap. `make test` exercises
    representative suites in both stages; full hosted validation uses `make test-ci`.
02. `make build-stage1` builds a repo-local `l1c-stage1` wrapper and native binary under `build/dea/bin/`, or the
    explicitly selected repo-local `L1_BUILD_DIR`.
03. `make test-stage1` runs the complete local-normal Stage 1 suite. Installed preparation and recovery fixtures are
    CI-only unless selected explicitly. Stage 2 reuses the installed preparation Python test against its own compiler.
04. `make install PREFIX=...` builds and installs a curated Stage 2 payload with optional verified autodocs;
    `make list-installed PREFIX=...` reads its complete inventory without building. Distribution and smoke targets are
    implemented; full platform acceptance remains pending.
05. Bootstrap correctness depends on the explicit upstream compiler contract:
    - local development defaults to `../l0/build/dea/bin/l0c-stage2`
    - reproducible overrides must use `L1_BOOTSTRAP_L0C`
    - the workflow must not rely on whichever `l0c` happens to be on `PATH`
06. Bootstrap supplies public headers and verified bundled semantic interfaces independently of native program runtime.
    `make runtime` remains the developer archive/raw-object workflow; stdlib sources live under
    `compiler/shared/l1/stdlib/`.
07. Shared tooling has separate repo and prefix launcher/environment renderers. L1 development uses the repo renderers;
    its build-layout validator deliberately rejects output directories outside the L1 source tree. Prefix renderers
    currently preserve inherited home variables, do not clear `L1_BUILD_DIR`, leave an existing PATH entry in place, and
    do not scope Windows compiler-wrapper variables with `setlocal`. L1-owned installed-context adapters now override
    inherited roots, deduplicate/move PATH entries, and scope Windows wrapper state without changing shared L0 defaults.
08. Automatic stdlib/runtime preparation and standalone-link discovery are implemented by the related preparation plan.
    Read-only installed fixtures contain semantic interfaces and rebuild inputs with no native profile requirement. They
    select context using `L1_HOME` with repository-mode binaries. Separate marked-compiler fixtures cover inventory
    validation and installed startup.
09. Both stages' checked-in `build_info` modules supply fallback metadata. The Stage 2 builder now accepts a private
    generated build-info module with provenance and an optional installed marker. Marked compilers validate native
    installation state before CLI parsing, including `--help` / `--version`; ordinary builds remain in repository mode.
10. Public install/list/dist/smoke-dist commands, atomic distribution result metadata, prefix/inventory/recovery
    primitives, and the fixture-based `test-productization` target are implemented. Preparation identity and storage
    internals have evolved since the original preparation plan; the current reference docs and ADR-0038 govern their
    consumption.

## Implementation Progress

The first Phase 1 milestone implements independent prefix resolution, schema 1 ownership validation, full payload
digest/mode verification, and preflighted reinstalls. Incomplete/complete metadata uses closed temporary files and
atomic replacement; retries retain previous and intended ownership, including intermediate files from interrupted
attempts. Unrelated files survive, and unsafe paths, aliases, substituted parents/hard links, malformed metadata, and
unowned collisions fail before payload mutation.

L1-owned adapters reuse shared prefix launchers while selecting their own `L1_HOME`, clearing inherited `L1_BUILD_DIR`,
retaining explicit selectors, moving/deduplicating activation PATH entries, and scoping native Windows wrapper state.
The focused fixture suite is wired into `test` and `test-extended`. Its implementation contract is recorded in
[l1/docs/reference/productization-inventory.md][inventory-contract].

Native Windows activation exposed an invalid nested percent-expansion check in the inherited MSYS2 PATH template. The L1
adapter now retains toolchain discovery but checks membership alongside prefix deduplication, adding a missing toolchain
and preserving existing entry order. Exact A/B/A assertions cover toolchain placement, case-insensitive matches, empty
entries, and literal punctuation; the toolchain need not remain the second entry after prefix switching.

The Stage 2 builder accepts an optional `build_info_overlay` file, snapshots it before construction, and stages only
that module in a private project root ahead of checked-in compiler sources. Neighboring modules cannot shadow the
compiler. Scratch is removed on success or failure, missing overlays fail before construction, and ordinary builds keep
fallback metadata. The explicit `make test-productization-build` target exercises a real self-build through a Stage 2
seed, checks embedded version output and semantic compilation after overlay removal, and verifies compiler sources and
development artifacts remain unchanged. It is separate from the lightweight fixture gate.

Package provenance collection now captures explicit bootstrap compiler reports, effective Stage 2 self-build options,
UTC build identity, normalized supported host tokens, and supplied preparation-input digests. The overlay, `VERSION`,
and inventory consume one immutable snapshot; documentation bundles share the same validated package-version selection.
The collector does not infer a preparation identity or serialize the process environment. Installed mode is an explicit
overlay-generation option, disabled by default. The standalone Stage 2 documentation generator is implemented;
distribution integration is implemented below.

The native startup milestone implements the physical-executable prefix check, schema/state validation, installed context
selection, and `L1C-9515` before command dispatch in both stages. It reuses preparation's native helpers while
preserving its strict identity JSON mode. Installer JSON limits match the bounded native reader. Native fixtures cover
invalid metadata, aliases, path substitution, relocation, and environment selection; real marked-compiler acceptance is
included in `test-productization-build`.

Validation on Linux x86_64 with `/usr/bin/gcc`, GCC 14.2.0:

- Focused provenance, inventory/launcher, and documentation-artifact regression tests passed. Native Windows cases are
  skipped on this host.
- `make test L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc`: passed documentation tests, Stage 1/Stage 2 smoke suites, parity,
  all four examples, Docker/Wine runner regressions, 22 tooling/bootstrap-identity tests, and 113 productization tests;
  fourteen native Windows productization cases skipped.
- `make -o build-stage2 test-productization-build L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc`: passed the
  generated-provenance native self-build, embedded version report, semantic compilation after overlay removal, and
  source/development-artifact preservation. The marked self-build also passed direct/launcher help, version, check,
  generation, read-only relocation, and invalid-state rejection. Reused the unchanged Stage 2 seed from the normal gate.
- `../.venv/bin/python -m pytest -q -n 0 tests/test_installation_guard.py`: all 33 native guard and JSON-bound fixtures
  passed, including physical-prefix behavior through an external executable alias.
- `../.venv/bin/python compiler/stage1_l0/tests/preparation_support_test.py`: existing preparation storage, integrity,
  and process coordination regression passed.
- `make -o build-stage1 -o build-stage2 -o runtime test-stage1-trace test-stage2-trace TESTS="l1c_lib_test preparation_test" L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc`:
  both stages passed both focused trace cases with zero leaked object/string pointers, reusing the validated compilers.
- Runtime ownership and trace instrumentation are unchanged; validation scope adds focused startup/preparation trace
  checks and real installed-mode self-build acceptance. Native Windows and macOS acceptance remain pending.

Curated payload assembly now snapshots the selected semantic/runtime inputs, verifies the complete captured interface
graph, and self-builds a separate marked Stage 2 executable. It includes launcher/activation scripts, notices, package
identity, standalone instructions, and a stdlib smoke module. The internal context-managed helper cleans up private
scratch on success/failure and leaves bootstrap outputs unchanged. Public install integration is implemented below;
artifact fixtures and dist targets are implemented below. Native Windows execution and four-platform artifact acceptance
remain pending for the revised helpers; local shell/inventory fixture success is not installed-compiler acceptance.

Curated payload milestone validation uses the same Linux/GCC toolchain:

- `../.venv/bin/python -m pytest -q -n 0 tests/test_productization_payload.py`: ten cases passed, covering source
  selection, interface/header mismatches, substituted inputs, provenance digests, shell/Windows payload forms, packaged
  links, inventory verification, and failure cleanup.
- `make -o build-stage1 -o build-stage2 -o runtime test L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc`: passed the normal gate,
  including 125 productization cases; fourteen native Windows cases skipped. Reused unchanged compiler/runtime
  artifacts.
- `L1_BUILD_DIR=build/dea L1_PRODUCTIZATION_SEED=build/dea/bin/l1c-stage2 L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc ../.venv/bin/python -m pytest -q -n 0 tests/test_stage2_build_overlay.py -k installed_startup`:
  passed real curated self-build, relocated direct/launcher use, read-only prefix compilation, cold-cache rejection with
  automatic preparation disabled, preparation/run, warm standalone linking, and unchanged payload digests. The separate
  private-overlay self-build case also passed through `test-productization-build`.
- Compiler sources, ownership behavior, trace instrumentation, and self-build implementation are unchanged. Validation
  adds curated-payload acceptance to the existing self-build test; four-platform package acceptance remains pending.

Verification on macOS Intel with `/usr/bin/clang`, Apple Clang 17.0.0 (`clang-1700.6.4.2`):

- `make test L0_CC=/usr/bin/clang L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang`: passed Stage 1/Stage 2 smoke
  checks, parity, all four examples, Docker/Wine runner regressions, existing tooling, and productization fixtures.
  Managed preparation succeeded with this compiler's supported configuration controls.
- `../.venv/bin/python -m pytest -q -n 0 tests/test_bootstrap_productization.py`: final helper revision passed 52 cases;
  fourteen native Windows cases skipped. Compiler-stage inputs remain unchanged from the normal gate.
- `make test-productization test-env L0_CC=/usr/bin/clang L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang`: passed the
  fixture suite and existing L0/L1 bash/zsh activation/bootstrap integration. The final helper revision is covered
  separately above.
- `python3 scripts/check_adr_impact.py --all-active` from the monorepo root: passed.

Private-overlay milestone validation on the same macOS Intel/Apple Clang 17 toolchain:

- `make test L0_CC=/usr/bin/clang L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang`: passed, including 22 Stage 2
  tooling/bootstrap-identity cases and 52 productization fixtures; fourteen native Windows fixtures skipped.
- `make -o build-stage2 test-productization-build L0_CC=/usr/bin/clang L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang`:
  passed the native overlay self-build in a path containing spaces, complete version report, post-overlay-removal
  semantic check, and source/development-artifact preservation. Reused the unchanged seed just built by `make test`.
- `L1_BUILD_DIR=build/dea L0_CC=/usr/bin/clang L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang ../.venv/bin/python scripts/triple_bootstrap.py`:
  passed the existing `triple-test` implementation using the already-built Stage 1/runtime prerequisites. All 137
  generated C translation units and normalized native executables matched; the final compiler passed its normal suite,
  examples, and run smoke check. No bootstrap inputs changed during validation.
- The validation tier is the normal gate plus focused native construction/fixed-point checks. Compiler source, ownership
  semantics, runtime controls, and trace behavior are unchanged.

Wine/MSYS2 validation of the revised Windows helpers used the provisioned container environment and a fresh source
snapshot. `../.venv/bin/python -m pytest -q -n 0 tests/test_bootstrap_productization.py` passed 57 cases with nine
POSIX-only cases skipped. The focused missing-toolchain regression fails against the original launcher and passes with
the revised adapter. This emulated result does not replace hosted native Windows acceptance.

Public install integration now exposes `make install PREFIX=...` and `make list-installed PREFIX=...`. The installer
validates destination/version/host inputs before bootstrap, honors an explicit upstream override, and prepares only an
absent repo-local L0 default without switching its alias. Disposable L1 Stage 1 and Stage 2 seed artifacts live under
the selected build root, with isolated native preparation and no changes to existing development compilers or aliases.
The seed must reproduce all Stage 1 semantic interface bytes before self-building the curated marked compiler. The
existing inventory helper publishes the payload and retains interrupted ownership for retry. Listing only reads the
complete inventory. Direct installs omit autodocs by default or consume an explicit verified `DOCS_ARTIFACT`.

Focused orchestration regressions cover failed bootstrap/payload construction, cleanup, artifact/alias preservation,
invalid destinations/overrides, semantic disagreement, literal prefix punctuation, missing/malformed/incomplete listing,
and Make dry-run behavior. The productization plan remains open for four-platform artifact acceptance and final
ADR/documentation closure.

Public workflow validation on Linux x86_64 with `/usr/bin/gcc`, GCC 14.2.0:

- `make test L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc`: passed the normal gate. The final focused
  `make test-productization` run passed 149 cases; fourteen native Windows cases skipped.
- `make test-env L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc`: passed environment/bootstrap integration.
- Fresh `make install PREFIX=... DEA_DIST_VERSION=install-test L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc`: prepared the
  absent upstream compiler, built the private chain, and installed the curated Stage 2 payload. Bootstrap scratch was
  removed. Relocation to a path containing spaces passed direct/launcher help, version, check, and generation without
  Python, Make, or C compilers on `PATH`. With only the required host compilation/inspection tools added, a read-only
  prefix passed compile-only, cold-cache rejection with automatic preparation disabled, preparation/run, warm standalone
  link, and build. Every payload digest remained unchanged. All three entrypoints rejected invalid installation state;
  public listing matched the recorded inventory.
- Explicit-upstream reinstall with a relative `PREFIX`, a custom `L1_BUILD_DIR` containing spaces, `-O0` construction
  flags, and stale inherited home/system/runtime/cache selectors passed. It preserved unrelated files and every
  development compiler/launcher digest, retained the selected Stage 1 alias, removed obsolete owned files, embedded the
  requested new package version, and removed private scratch.
- `make -o build-stage1 -o runtime triple-test L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc`: passed using the normal gate's
  unchanged prerequisites. All 137 generated C translation units and normalized native executables matched; the final
  compiler passed all 65 normal tests, examples, and the executable smoke check.
- Whitespace, copyright-header, Markdown-formatting, and ADR-impact checks passed.
- Native macOS and Windows acceptance for this public workflow remains pending. Compiler ownership, runtime selection,
  and trace instrumentation are unchanged; the validation tier adds install/bootstrap integration to the normal gate.

Optional Stage 2 docs installation reuses the completed artifact verifier before bootstrap. It retains a private
extracted snapshot, rechecks source identity before publication, and includes HTML/PDF plus the documentation manifest
in the ordinary payload inventory. Reinstalling without docs removes only previously owned files. Invalid stage,
version, source identity, completeness, file digests, unsafe extraction, or overlapping destinations leave an existing
prefix untouched. Bootstrap failures clean up docs scratch. Doxygen and TeX are not installation dependencies.

Docs integration validation on Linux x86_64 with `/usr/bin/gcc`, GCC 14.2.0:

- `../.venv/bin/python -m pytest -q -n 0 tests/test_install_toolchain.py tests/test_docgen_artifacts.py`: 64 cases
  passed, including docs/no-docs reinstalls, rejected bundles, source changes during construction, and scratch cleanup.
- `make clean test L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc`: passed the normal gate, including 163 productization cases;
  fourteen native Windows productization cases skipped. Compiler, runtime, and trace behavior are unchanged.
- A real `make install` with `DOCS_ARTIFACT`, `DEA_DIST_VERSION=docs-install-test`, and the same GCC controls passed.
  The input was a small verified HTML/PDF fixture carrying the current source identity, not a regenerated Doxygen
  reference. The relocated read-only prefix passed native/launcher help, version, check, and generation; direct native
  commands used an empty `PATH`. Full payload verification, docs/compiler metadata agreement, public inventory listing,
  unchanged payload digests, and scratch cleanup passed. Docs/no-docs reinstallation is covered by the fixture suite.
- Native macOS/Windows acceptance and full distribution-bundle acceptance remain pending. No compiler construction,
  ownership, runtime, or trace implementation changed; no additional triple-bootstrap or trace rerun is required.

## Distribution packaging implementation

`make dist` now uses the existing private install chain and requires a snapshotted, verified Stage 2 HTML/full-PDF
bundle. It writes curated host archives with one `dea-l1/` root, checks a complete extraction round trip, and publishes
only the finished archive. Schema-1 `DIST_RESULT` records its absolute path, size/digest, package identity/provenance,
and docs-bundle digest/source evidence. Valid prior result destinations are invalidated before input validation, and new
JSON is closed in a sibling temporary file before atomic replacement. Unsafe destinations are rejected without mutation;
interrupted publication cannot report an older archive as this invocation's success.

`make smoke-dist ARCHIVE=...` validates all members before extraction, inventory bytes/modes and exact membership,
curated exclusions, `VERSION`, preparation inputs, and offline docs. It relocates the prefix into a path containing
spaces, uses an unrelated working directory and private cache, checks native/launcher identity, and exercises semantic,
compile-only, standalone link, build/run, cold/warm preparation, checking/trace configurations, forced preparation, and
cache disposal. POSIX execution uses a read-only prefix and a native-tool-only PATH; semantic native commands have no
tools on PATH. The harness verifies unchanged payload digests after execution.

The exact public commands, archive names, result schema, and failure/consumer rules are documented in
[l1/docs/reference/productization-inventory.md][inventory-reference]. The packaging regression suite is part of both
normal gates. No compiler construction, native selection, runtime ownership, or trace implementation changes are
introduced by this phase. Native macOS ARM and Windows UCRT64 artifact acceptance, the delivery ADR/ADR-0001 amendment,
and final plan closure remain open. Hosted release/snapshot implementation remains a separate plan.

Distribution validation on Linux x86_64 with `/usr/bin/gcc`, GCC 14.2.0:

- `make test-productization`: 224 passed, 14 native Windows cases skipped; includes 61 distribution regressions for
  tar/zip round trips, safe aliases, hostile archive members, exact inventory/docs checks, and interrupted
  result/archive publication. `make test` components passed: docs tests, Stage 1/Stage 2 representative suites, parity,
  examples, Docker/Wine runner tests, Stage 2 tooling, and productization. `make test-env` passed. The container's
  tooling targets require the shared virtual environment's `bin` directory on `PATH` for bare `python` invocations.
- `make docs-artifacts DOC_STAGE=stage2`: generated and verified the full Doxygen 1.9.8 HTML reference and indexed PDF,
  using the actual Stage 2 source inventory. This acceptance used the full reference, not the earlier docs fixture.
- `make dist DOCS_ARTIFACT=<full-stage2-bundle> DIST_RESULT=<absolute-json-path>`: built the complete private chain,
  verified all 23 Stage 1/Stage 2 interface pairs, self-built the installed compiler, round-tripped the archive, and
  published a matching schema-1 result and approximately 6.6 MiB Linux archive.
- `make smoke-dist ARCHIVE=<exact-result-archive>`: passed in a separate Debian validation container mounting only the
  archive, Python validation harness, and host tools. Compiler sources, repository payload inputs, and bootstrap
  binaries were absent. Relocation/read-only checks, native metadata agreement, semantic operations without tools on
  PATH, standalone linking, native preparation/reuse, checking/trace selections, cache disposal, invalid explicit
  overrides, offline documentation, and unchanged inventory digests all passed. The restricted native-tool PATH includes
  `ldd`/`readelf` on Linux and `otool` on macOS, required by managed toolchain identity checks.
- ADR Impact validation, staged whitespace checks, and the repository pre-commit hooks passed. Compiler construction and
  runtime implementations are unchanged, so triple-bootstrap and broad trace suites were not repeated.

Tar and zip archives take file modes from the portable inventory and normalize directory/alias modes. Windows filesystem
modes cannot represent this contract reliably; extracted execute-bit assertions apply only on POSIX, while archive
metadata is validated on every host. Windows smoke setup canonicalizes environment names before filtering inherited
selectors and resolving the compiler because copying `os.environ` into a plain dictionary loses case-insensitive lookup.
`SYSTEMROOT` supplies the Windows system-command directory.

Portability validation:

- Hosted Windows UCRT64 CI passed with the archive-mode and smoke-environment fixes.
- `make clean test` passed on macOS Intel with `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC` set to `/usr/bin/clang` (Apple
  Clang 17), including 228 productization cases and 14 platform skips.
- `python -m pytest -q -n 0 tests/test_distribution.py -k "windows_smoke_environment or smoke_relocates"` passed all
  four cases under Wine/MSYS2 with GCC 16.2.0. This is focused emulation coverage, not full runner acceptance.

Regression coverage includes synthesized Windows stat modes, archive round trips, environment-name casing, explicit
compiler selection, and inherited-selector filtering. Wine/MSYS2 path assertions must account for Python reporting
`os.sep` as `/` while native diagnostics contain backslashes.

## Repeatable artifact acceptance

The dedicated `test-productization-acceptance` target builds through the existing distribution helper, validates the
exact schema-1 result against its archive, and invokes the reusable native smoke checks. It retains the archive,
original result, portable Python harness, and a success report. Separate build and verification phases support fresh
verification hosts; the default combined local run does not claim checkout unavailability.

The manual `L1 Productization Acceptance` workflow builds one full Stage 2 docs bundle and all four native archives from
the selected source/version. Verification runs in separate fresh jobs that never check out sources or download bootstrap
artifacts. Build and smoke logs are retained with artifact evidence. Ordinary four-platform `test-ci` success covers
regression fixtures and compiler validation; it does not substitute for this artifact gate. Hosted execution of the new
workflow remains pending. No release/snapshot publication implementation is included in this change.

Acceptance-gate validation on macOS Intel with `/usr/bin/clang`, Apple Clang 17.0.0 (`clang-1700.6.4.2`):

- `make test L0_CC=/usr/bin/clang L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang` passed, including 247
  productization checks and fourteen native Windows skips. After the final result-schema type checks were tightened,
  `../.venv/bin/python -m pytest -q -n 0 tests/test_productization_acceptance.py` passed all 22 cases. Compiler/runtime
  inputs and the other normal-gate components remained unchanged, so their successful results were reused.
- `make docs-artifacts DOC_STAGE=stage2 DEA_DIST_VERSION=dev` generated and verified full Stage 2 HTML and indexed PDF
  with Doxygen 1.18.0 and TeX Live 2026.
- `make test-productization-acceptance DEA_DIST_VERSION=dev DOCS_ARTIFACT=<full-bundle> ACCEPTANCE_DIR=<new-directory>`
  with the same three compiler selectors passed private bootstrap, all 23 semantic interface pairs, installed Stage 2
  self-build, archive/result verification, and complete native smoke execution.
- The transported archive and six-file harness also passed
  `python3 -I -S <harness>/productization_acceptance.py --phase verify --directory <evidence>` from an unrelated
  directory. macOS sandbox rules denied reads of the source worktrees and main checkout; a control read of `AGENTS.md`
  failed under those same rules. The verifier used external Python without site packages, and the installed compiler
  could not read repository sources or bootstrap binaries. This supplies native macOS Intel artifact acceptance,
  independently of future hosted workflow execution.
- Workflow `actionlint`, staged whitespace, ADR Impact validation, and repository pre-commit hooks passed. The gate adds
  artifact orchestration without changing compiler construction, runtime ownership, or trace implementation.

## Defaults Chosen

1. The first package is a self-hosted Stage 2 development toolchain; productization does not imply stable-release
   readiness. Follow the delivery-stage choice in
   [l0/docs/decisions/0023-toolchain-installation-and-distribution-layout.md][l0-delivery] while retaining L1's own
   semantic/input-cache contract.
2. The default local upstream compiler remains repo-local `../l0/build/dea/bin/l0c-stage2`.
3. `L1_BOOTSTRAP_L0C` selects the upstream L0 compiler used to construct L1 Stage 1. Stage 1 builds a Stage 2 seed,
   which then builds the delivered Stage 2 executable. The installed native `l1c` does not invoke L0, L1 Stage 1,
   Python, `uv`, or Make to run or prepare bundled support. Native output and native cache preparation still require a
   compatible host C compiler/linker and the preparation service's host tools.
4. Ship Stage 2 only, independently of the active repo-local `l1c` alias. Do not install Stage 1 launchers, binaries, or
   compiler implementation sources. Preserve both stages' development workflows and shared startup/diagnostic behavior;
   build and install targets must not change the selected development alias.
5. Reuse shared prefix launcher/env rendering, bootstrap selection, and narrow file/archive helpers where applicable.
   Keep L1 payload selection and build policy under `l1/scripts/`; do not import the L0 distribution builder wholesale.
6. The first payload contains the compiler, verified bundled interfaces, public headers, stdlib/runtime rebuild sources,
   internal preparation headers and installation metadata. Native configurations are derived in the selected local cache
   on demand; no native stdlib objects or runtime archives are required in the installation.

## Dependency and Packaging Handoff

The install layout and packaging helpers can build on the completed preparation service and managed standalone-link
integration from
[l1/work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][stdlib-preparation]. That work
validated installed lookup against read-only fixtures independently of this installer, so there is no dependency cycle.

The preparation plan owns semantic/native identities, completion manifests, native compilation, per-key coordination,
reuse eligibility and local-cache selection. This plan owns the installed prefix, launchers, shipped input inventory,
archive construction and relocation. Copy the verified bootstrap semantic set exactly with its compiler-owned rebuild
inputs. Installation metadata identifies those shipped inputs, including `D` if supplied, without an installed native
key, completed native-profile export/import format, or installed-profile lookup. Packaging must not introduce a second
identity algorithm or advertise copied native cache state as portable.

Treat [l1/docs/reference/stdlib-preparation.md][preparation-contract] and
[l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md][installed-inputs] as the live contract.
Keep exact interface bytes and their ordered provider authority, bundled-directory identity checks, explicit
`--no-managed-stdlib` behavior, selected-cache ownership, and corruption/private-fallback behavior. Cache manifests and
the install inventory are separate formats; neither is a replacement for the other. If the compiler does not expose a
stable preparation-input identity to packaging, record the inventory digests and provenance without inventing `D`.

Current GCC and supported Clang toolchains suffice to begin implementation; pending preparation optimizations and legacy
Clang compatibility are not prerequisites. Follow [l1/AGENTS.md][l1-guidance]: use GCC or upstream Clang 16+ for
ordinary validation, verify Apple Clang's required capabilities separately, and record actual selected compiler
versions. Do not infer Clang 14/15 support from a successful direct C build.

Stage 2 documentation is a required distribution input under
[l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md][autodocs]. Generation is implemented,
including separate Stage 1/Stage 2 HTML/PDF references and a verified docs bundle. Installer/compiler work can proceed
in parallel, but complete `make dist` acceptance waits for its Stage 2 bundle. Documentation generation requires source
files and documentation tools, not an installed compiler, so this introduces no dependency cycle.

### Self-hosted package construction

Use the explicit chain `L0 Stage 2 -> L1 Stage 1 -> L1 Stage 2 seed -> delivered L1 Stage 2`. Reuse
`build_stage1_l1c.py` and the compiler-selection/build-support helpers in `build_stage2_l1c.py`; extend the latter to
accept a private build-info overlay without modifying checked-in sources. Build in private scratch, using explicit
compiler paths rather than the selected `l1c` alias. Keep host compiler flags and compiler-runtime controls recorded and
consistent across the Stage 2 seed and final construction. Ignore inherited installation roots during bootstrap.

The Stage 2 seed runs in repository mode and builds the final executable with the installed-mode/provenance overlay.
This order permits self-building before a complete installed prefix exists. Generate and verify the bundled semantic set
through the repository-mode Stage 2 seed, require exact agreement with Stage 1's canonical interface bytes, and copy
that verified set unchanged. The final installed compiler must consume it successfully in the archive smoke checks.
Private build runtime objects and preparation caches are inputs to construction, never distribution payload.

`make triple-test` remains the existing strict fixed-point gate. Run it when implementing changes to Stage 2
construction, overlays, or native support; do not turn every `install` or `dist` invocation into a full triple-bootstrap
test run. Packaging a Stage 1-built Stage 2 seed alone does not meet the self-built delivery requirement.

## Installed Layout

`PREFIX` is required. Resolve a relative prefix against the L1 working directory and use a separate prefix-layout
resolver; never weaken the repo-local build-directory containment checks. Reject the source root and overlapping
source/build/payload paths that would overwrite build inputs or recursively copy the destination into itself.

The selected layout is:

| Prefix-relative path                                              | Contents                                                                                                                                                         |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `bin/l1c`, `bin/l1c-stage2`, `bin/l1c-stage2.native`              | Selected Stage 2 alias, prefix-relative launcher, and self-built host native executable. Use the current native-artifact naming convention.                      |
| `bin/l1-env.sh`                                                   | Sourceable bash/zsh activation, including MSYS2 bash.                                                                                                            |
| `bin/l1c.cmd`, `bin/l1c-stage2.cmd`, `bin/l1-env.cmd`             | Windows launcher/activation counterparts; Windows aliases use copies as in the current workflow.                                                                 |
| `shared/l1/stdlib/`                                               | Bundled `std.*` and `sys.*` `.l1` sources with their module-relative paths.                                                                                      |
| `shared/runtime/`                                                 | Runtime `src/`, `include/`, `internal/`, and symbol manifests needed by the preparation service.                                                                 |
| `interfaces/`                                                     | Complete verified bundled semantic `.l1m` set, copied exactly from bootstrap using module-relative paths.                                                        |
| `include/`                                                        | Public `dea_rt.h` and `l1_real.h`; rebuild-only internal headers remain under `shared/runtime/internal/`.                                                        |
| `VERSION`                                                         | Human-readable Stage 2 package identity, development status, host target, and bootstrap/build provenance.                                                        |
| `share/dea/l1/install-manifest.json`                              | Versioned inventory of payload files, file modes, relative alias targets, content digests, and compiler-owned input-set identity (including `D` where supplied). |
| `README.md`, `README-WINDOWS.md`, `share/doc/dea/l1/toolchain.md` | Self-contained Stage 2 installation/use/cache instructions with working payload or canonical repository links.                                                   |
| `share/doc/dea/l1/autodocs/stage2/`                               | Verified Stage 2 `html/`, `pdf/dea_l1_stage2_api_reference.pdf`, and docs `manifest.json`; required for distributions, optional for direct installs.             |
| `share/dea/l1/smoke/hello.l1`                                     | Small bundled smoke program importing a stdlib module and producing deterministic output.                                                                        |
| `LICENSE-MIT`, `LICENSE-APACHE`, `THIRD_PARTY_NOTICES`            | Repository license and attribution files, plus any notices required by the shipped payload.                                                                      |

Resolve installed defaults from the launcher's own prefix: `L1_HOME` points to the prefix, source lookup uses
`shared/l1/stdlib`, and semantic discovery uses `interfaces`. Installed wrappers set their own `L1_HOME` and remove
inherited repo-local `L1_BUILD_DIR` from the child environment. Activation applies the same selection in the current
shell. Explicit system roots, runtime overrides, compiler options, and `L1_STDLIB_CACHE` remain authoritative; tests
distinguish deliberate overrides from leaked repo-local layout defaults.

Activation moves the selected prefix's `bin` directory to the front of `PATH`, removes duplicate entries for that
directory, and preserves the order of other entries. An already-present entry must still move forward when switching
back from another L1 prefix. Clear shell command caches where applicable. Windows compiler launchers scope environment
and helper-variable changes with `setlocal`, restore the calling environment with `endlocal`, and preserve the native
compiler's exit status on every path. Sourceable activation scripts intentionally update the caller's environment.

Use the shared prefix renderers, adding narrowly scoped L1 adaptation where needed. Do not embed build-worktree paths or
force `L1_BUILD_DIR` to the prefix as a way to route cache writes. All relative launcher and alias targets survive
moving the entire prefix, including paths containing spaces. Invocation from any current directory works without
activation; activation is a PATH/environment convenience, not a runtime prerequisite.

Installed payload files are read-only to compiler operations. Native consumers reuse valid support or prepare from
shipped inputs into `--stdlib-cache`, then `L1_STDLIB_CACHE`, then the installed per-user default. There is no installed
native lookup tier. Explicit unusable cache roots fail; an unavailable implicit default permits fresh private support
for automatic consumers. Explicit preparation requires a usable persistent destination. Forced replacement and manual
cache disposal preserve every installed input and must be externally serialized against cache consumers.

Compile-only selects the installed public headers and semantic set without native preparation. Build/link select
complete managed native profiles, including TinyCC raw objects, while preserving explicit runtime overrides. No path
requires `L1_BUILD_DIR` or silently falls back to an unqualified shipped archive.

Intact installed launchers and native executables establish prefix context independently of inventory validity and share
one internal native installation-state check before command dispatch, including `--help` and `--version`. Missing or
invalid metadata must not downgrade installed invocation to repository mode. Validate the inventory version, required
structure, and complete state without hashing the whole payload on every launch. This requires no new public CLI mode or
external interpreter; repository invocations retain their existing startup behavior.

### Native startup and inventory handoff

Create a package-only `.l1` build-info overlay that identifies the native executable as an installed Stage 2 artifact
and embeds its package provenance. Keep the checked-in fallback and ordinary repository builds in repository mode.
Derive the installed prefix from the running executable's physical `bin/` location using native platform support;
wrappers and a valid inventory must not be prerequisites for direct native invocation. An installed marker compiled into
the package prevents a missing inventory from silently selecting repository mode. Generate the overlay in private build
scratch and never edit checked-in compiler sources during packaging.

Perform the native state check before help/version short-circuits and ordinary command dispatch. In installed mode,
select the physical prefix over stale inherited `L1_HOME` / `L1_BUILD_DIR`, while retaining explicit system, runtime,
and cache selectors. Reuse or factor the native executable-path and JSON support already available in compiler support;
do not invoke a shell parser or Python from the installed compiler. Keep shared Stage 1 startup/diagnostic behavior in
parity while leaving ordinary builds of both stages in repository mode. Extend test support-link declarations if the new
hook changes native ABI dependencies.

Define one versioned inventory schema shared by the Python installer and native reader. Its required fields describe
schema version, language level and packaged stage, `complete` or `incomplete` state, package provenance, and owned
prefix-relative entries. File entries record content digests and portable mode information; aliases record relative
targets. Incomplete records retain both previous and intended ownership for retry. Reject duplicate, absolute, escaping,
or unsupported entries before mutation. Native startup validates required structure and complete state; installer and
artifact verification own full content-digest checks. Missing/damaged payload binaries may still fail at host launch.

Adapt installed preparation fixtures explicitly to the new startup contract and keep their tests of semantic/native
separation. Fixtures using a repository executable and explicit `L1_HOME` remain useful preparation-unit coverage, but
only a packaged executable and complete inventory establish installed-entrypoint acceptance.

## Install and Archive Defaults

1. `make install PREFIX=...` executes the self-hosted construction chain and builds the verified semantic set, then
   copies the curated compiler-owned input payload through one install helper. The Stage 2 seed builds the package
   executable with the installed marker and provenance overlay. Keep this artifact separate from repo-local Stage
   1/Stage 2 executables and preserve the active development alias. Do not copy the worktree's entire build/cache
   directory.
2. Install into an empty prefix or a prefix whose unrelated files do not collide with the selected payload.
   Reinstallation uses the existing L1 inventory: replace owned files and remove obsolete owned files, preserve
   unrelated files, and reject unowned collisions. Preflight inventory paths, alias targets, and destination parents
   before copying or deleting; never follow a substituted path outside the prefix. Payload files use ordinary writes;
   installation is externally serialized against consumers and does not promise atomic payload upgrade or rollback.
   After preflight, publish an incomplete inventory with previous and intended ownership before changing any payload
   file. Publish each inventory state by writing and closing a complete temporary metadata file in the same directory,
   then replacing the authoritative manifest atomically. Never truncate the authoritative inventory in place. If that
   metadata replacement fails, stop with the prior valid state intact; no payload mutation may precede successful
   incomplete publication. Retain the incomplete inventory throughout copying and obsolete-file removal, then publish
   the complete inventory only after verification succeeds. An interrupted final publication therefore leaves a valid
   incomplete record for retry. Temporary metadata is private install scratch, never a source of payload ownership or
   part of the exported artifact. This is a process-interruption recovery contract, not a power-loss durability promise.
3. `make list-installed PREFIX=...` reads the recorded inventory and prints sorted prefix-relative file paths. It does
   not build, prepare, scan a writable user cache, or claim unrelated prefix contents as installed files. Missing or
   malformed or incomplete inventory is an error. The manifest names itself but omits its own digest. Intact installed
   launcher entrypoints also refuse missing, malformed, or incomplete installation state with an actionable repair/retry
   message; this guard requires neither Python/Make nor a host C compiler. If interruption leaves a launcher or native
   executable missing or damaged, a host launch failure is acceptable; the retained inventory must still support
   installer retry.
4. `make dist` creates the same install tree under a private staging directory and archives it with exactly one
   top-level `dea-l1/` directory. Archive names are `dea-l1-lang_<version>_<os>-<arch>_<YYYYMMDD-HHMMSS>` plus `.tar.gz`
   on Linux/macOS or `.zip` on Windows. Build time is UTC; target tokens are normalized for filenames. Emit the final
   archive path through the machine-readable handoff below. Use staging disjoint from compiler inputs and payload
   sources, even when both live beneath the repository's build directory. Publish the finished archive only after
   payload and inventory verification; a failed build must not report an earlier archive as its result.
5. Take version metadata from a nonempty explicit `DEA_DIST_VERSION`; otherwise use `dev`. The workspace Python
   package's development version is not an established L1 release-version source. Validate filename components, retain
   Stage 2 identity and development maturity labeling for every version, and never infer version from L0 release tags.
   `VERSION`, the package's native `--version` report, and the install manifest agree on package identity and record
   source/build provenance, the upstream L0 and L1 bootstrap compiler identities, Stage 2 self-build/compiler options,
   host target, and shipped preparation-input identity. Provenance paths are informational and never used for runtime
   lookup. All public repository links use `https://github.com/dea-lang/dea`.
6. Include only the table's payload and needed notices. Exclude compiler implementation/test trees, unrelated examples,
   plans, repository metadata, virtual environments, tools, build scratch, user caches, retained generated C, docs
   generators, intermediate XML/LaTeX, and Stage 1 autodocs. Include verified Stage 2 HTML/PDF only through the explicit
   docs-bundle handoff below. Check packaged documentation links rather than copying source docs with dangling
   repository-relative links.
7. The first supported native artifact matrix follows current L1 CI: Linux x86_64, macOS Intel and ARM, and Windows
   UCRT64. The artifact targets its build host family/architecture; portable archive layout does not imply native
   cross-platform compatibility or eliminate host C/system-library requirements.

### Release-workflow interface

Provide these commands from `l1/` and document their exact behavior before closing this plan:

- `make dist DEA_DIST_VERSION=<version> DOCS_ARTIFACT=<absolute-stage2-bundle-path> DIST_RESULT=<absolute-json-path>`
  consumes the verified docs bundle and writes a versioned result record only after successful archive publication.
  Require schema version 1, absolute `archive_path`, `package_version`, `stage=2`, normalized `os` / `arch`, and source
  provenance matching the payload. `DIST_RESULT` is optional for local builds; always print the resulting archive path
  for interactive use. Reject a result destination overlapping payload inputs or the archive, invalidate a prior result
  at invocation start, and replace the new record atomically. Workflows use a unique result destination and check
  command success before reading it; they must not glob old archives or parse build log prose.
- `make smoke-dist ARCHIVE=<absolute-archive-path>` invokes one reusable L1-owned smoke helper against that exact
  archive. It validates safe extraction, the single `dea-l1/` root, complete inventory and all listed payload digests,
  metadata agreement, and absence of excluded build/cache files. Reject archive traversal and escaping aliases before
  extraction. Then relocate to a path containing spaces, run installed commands from an unrelated directory with
  controlled environment/cache selection, and exercise the smoke cases in this plan. This command consumes the archive
  without rebuilding the compiler or relying on repo-local payload files. A Python/Make test harness is allowed;
  compiler child processes must demonstrate independence from those tools and the source checkout.

`DOCS_ARTIFACT` is required for distributions. Validate its level `l1`, `stage=2`, version, source revision/dirty
evidence, selected-source inventory digest, complete HTML/PDF flags, and file digests against the packaging checkout.
Extract safely and copy its `html/`, `pdf/`, and `manifest.json` beneath the payload's Stage 2 autodocs directory;
record those files in the install inventory and the docs-bundle digest in the dist result. Reject Stage 1, incomplete,
preview-only, or stale documentation before publishing an archive. Missing docs report the `make docs-artifacts`
command. The dist builder never invokes Doxygen or TeX implicitly.

Direct `make install PREFIX=...` may omit autodocs or accept the same `DOCS_ARTIFACT`. Record its actual payload in the
inventory so reinstalling with or without docs handles owned files predictably. Compiler-only installed prefixes remain
valid. Distribution smoke checks always require the offline HTML entrypoint, full PDF, matching docs manifest, and
absence of Stage 1 autodocs, without fetching network assets or generating documentation on the target host.

Use `DEA_DIST_VERSION=X.Y.Z` for the release plan's version tags and `snapshot-...` for its snapshot tags; both retain
the Stage 2 development-toolchain identification. Keep `VERSION` inside each archive. The workflow plan owns
four-platform aggregation, tag creation, notes, and publication; this plan supplies one verifiable host archive and
reusable validation command.

## Goal

1. Define the first install-prefix layout for the self-hosted L1 Stage 2 compiler.
2. Add install workflows that make the built compiler usable outside the repo-local build tree.
3. Add a minimal distribution archive workflow containing only the self-hosted Stage 2 toolchain and its required
   assets.
4. Update L1-local docs so the install/dist/bootstrap workflow is documented consistently.

## Implementation Phases

### Phase 1: Implement prefix and payload helpers

Implement the selected layout, inventory schema, path validation, prefix launcher/env adaptation, and standalone
packaged docs. Add explicit options or L1-owned adapters to the shared renderers; preserve existing L0 callers and test
their output when changing shared helpers. Implement the package build-info overlay and native startup/state check,
including direct native execution, before exposing an installed compiler.

Keep payload/inventory helpers testable with small fixtures. Use actual compiler fixtures for startup, diagnostic,
semantic-provider, and cache behavior. Register any new native support dependency in both stages' build/test helpers. Do
not expose a successful install/dist command that omits required artifacts or the installed-state guard.

### Phase 2: Add install workflows

Add the first L1 install-target surface, including:

- `make install PREFIX=...`
- `make list-installed PREFIX=...`
- installed launcher generation
- installed env activation scripts for the same shells already supported by the repo-local workflow

Use the implemented preparation service's input contract and the explicit self-hosted construction chain to produce the
separate Stage 2 package executable with embedded installed mode and matching provenance. Copy the verified semantic set
and rebuild inputs, and mark the inventory complete only after the complete payload is installed. Test relocated,
read-only prefixes, direct native entrypoints, and controlled reinstall/interruption behavior.

### Phase 3: Add distribution packaging

Add `make dist` using the same payload builder, selected archive naming, version metadata, and exclusion rules. Extract
each archive to an unrelated directory and run the installed smoke workflow there. Implement the `DIST_RESULT` record
and `make smoke-dist ARCHIVE=...` interface, including stale-result failure checks. Integrate the completed Stage 2
docs-bundle contract and require its HTML/PDF contents in each distribution. Validate actual host archives on Linux
x86_64, macOS Intel/ARM, and Windows UCRT64. Keep archive creation local; this phase creates no release tags, workflows,
or published assets.

### Phase 4: Update documentation and contributor guidance

Update the L1-local docs and contributor guidance so they describe:

- repo-local bootstrap workflow
- install-prefix workflow
- dist archive workflow
- explicit upstream compiler override behavior via `L1_BOOTSTRAP_L0C`
- the upstream L0/Stage 1/Stage 2 seed construction chain and the installed Stage 2 compiler's independent operation
- shipped read-only support, writable cache selection, configuration misses, and manual preparation controls
- the native installed-state diagnostic, package identity, exact result-record schema, and archive smoke command
- explicit Stage 2 HTML/PDF bundle input, offline docs location, and Stage 1 autodoc exclusion

Add a focused `test-productization` target for lightweight installer/inventory/launcher tests and include it in L1's
normal `test` and `test-extended` gates. Keep actual archive acceptance available through `smoke-dist`, and include the
relevant installed/compiler integration cases in the existing test runners without bypassing their CI-only
classification. Update roadmap/status docs only when implementation lands, then create/amend the specified ADRs in the
same change as plan closure. Update the release-workflow plan's dependency link and handoff to the landed commands.

If a host lane is unavailable, record it as pending and leave the plan open. Linux fixture success alone does not
establish four-platform productization readiness; no tag push or public dispatch is required to complete local artifact
validation.

## Diagnostic Planning

Install, list, and archive script failures use actionable tooling errors and nonzero exit status. The native installed
state guard now uses `L1C-9515` in the existing driver filesystem/environment diagnostic area for missing, unreadable,
malformed, unsupported, or incomplete installation state. It reports the prefix/inventory path, reason, repair/retry
guidance, and exit status 1. The shared catalog and CLI contract record this assignment. Both compiler stages contain
the same native hook; repository-mode builds leave it disabled. Existing preparation failures retain `L1C-2150` through
`L1C-2159`, including `L1C-2158` for missing semantic/preparation inputs after valid installation-state selection; do
not assign those codes to the new startup inventory failure.

## ADR Impact

- Decision: Ship the self-hosted L1 Stage 2 compiler through one relocatable install-prefix and distribution contract.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The relocatable prefix, curated semantic/source payload, inventory, native installed-state boundary,
    archive/result schema, Stage 2-only payload, self-built delivery requirement, and smoke command become toolchain
    interfaces consumed by later release workflows. Cache algorithms remain governed by the existing preparation ADRs.
- Decision: Choose the L1 bootstrap compiler from repo-local L0 Stage 2 or `L1_BOOTSTRAP_L0C`, never ambient `PATH`.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0001-bootstrap-adaptation-strategy.md`
  - Rationale: ADR-0001 owns bootstrap adaptation and must distinguish the explicit upstream compiler used to construct
    Stage 1 and the Stage 2 seed from the self-built Stage 2 compiler used after installation.

## Non-Goals

- GitHub Release publishing for L1
- generating autodocs, docs hosting, or Pages deployment for L1; consuming the Stage 2 HTML/PDF bundle is in scope
- Stage 1 install/distribution packages, bundled bootstrap compilers, or changes to language/self-hosting semantics
- a broad rewrite of the root `README.md`
- automatic inference of the upstream compiler from whichever `l0c` is active on `PATH`
- copying L0 release/docs machinery, adding an installer service, or bundling host compilers and SDKs
- implementing a second preparation/cache algorithm or shipping installed native profiles
- atomic installation, concurrent upgrades, uninstall tooling, or package-manager integration

## Verification Criteria

01. Install/dist construction honors an explicit `L1_BOOTSTRAP_L0C` and rejects an invalid override instead of using
    ambient `l0c`. The delivered executable is built by the explicit Stage 2 seed, reports Stage 2 identity, and is
    selected by installed `l1c` regardless of the active development alias. The prefix/archive contains no Stage 1
    executable, launcher, or compiler sources. Package construction preserves that alias and repository compiler
    artifacts. The package marker/provenance overlay does not modify checked-in sources.
02. A fresh install and a controlled reinstall produce exactly the curated owned payload; unrelated files survive, and
    unowned collisions, malformed inventories, substituted parents, and unsafe source/destination overlap fail before
    destructive copying. Inject interruption during initial inventory publication, payload copying/deletion, and final
    publication, including temporary metadata writes and failed replacements. Before the incomplete transition, the
    previous complete installation stays unchanged; after it, ownership remains recoverable for retry. `list-installed`
    and intact installed launcher entrypoints reject incomplete state until installation finishes, without external
    build tools. With intact entrypoint files, cover missing, unreadable, and malformed metadata through every installed
    launcher form, verify the startup diagnostic and status, and ensure invalid metadata never selects repository mode.
    Separately interrupt copying of launcher/native files, allow host launch failure, and verify unusability followed by
    successful installer retry. Repository `--help`, `--version`, and compilation still work without an install
    inventory.
03. Move both an installed tree and an extracted archive to paths containing spaces. Run `--version`, `--help`,
    `--check`, and `--gen` from an unrelated working directory without activation and without source-worktree access.
    Cover direct native invocation with home/build variables unset and with stale inherited values. Package identity
    agrees across native `--version`, `VERSION`, inventory, archive name, and result metadata.
04. Compile the bundled stdlib-using smoke program, then standalone-link its object without `-I` and run the result.
    Exercise `--build` and `--run` too. No upstream L0, Python, or Make is needed by the installed compiler; the host
    C/linker/preparation tools remain available for native operations. L1 Stage 1 and the intermediate Stage 2 seed are
    also unavailable to the installed compiler. The packaged semantic set agrees with both stages' verified output.
05. A read-only prefix containing no native stdlib/runtime support compiles the smoke module against its shipped
    semantic set. With an empty cache, `--no-auto-prepare` fails with guidance; ordinary build/run/link prepare matching
    support into the selected cache. Warm no-auto reuse succeeds, changing native configuration selects a new profile,
    and switching back reuses the original. Inspect actual headers and native link inputs; no installed archive may mask
    a miss. Exercise TinyCC with `L1_BUILD_DIR` absent and semantic-only use without native host tools.
06. Forced preparation and clearing/rebuilding a writable cache leave every installed payload digest unchanged. Invalid
    explicit providers/runtime overrides remain authoritative failures. A failed cache selection never writes into the
    prefix or silently chooses another writable root.
07. Installed wrappers override stale repo `L1_HOME`/`L1_BUILD_DIR` defaults while honoring explicit
    system/runtime/cache selectors. Activation works in bash, zsh, MSYS2 bash, and native `cmd.exe` where supported,
    with existing environment stackability and L0 activation coverage preserved. Test installed A -> B -> A and repo ->
    installed -> repo -> installed sequences, asserting resolved compiler identity, environment roots, and no duplicate
    entries for the selected directory. Native `cmd.exe` tests call installed launchers with sentinel parent environment
    values and verify their restoration plus compiler exit-code preservation on success and failure; activation still
    intentionally changes that parent environment.
08. `list-installed` is deterministic and does not invoke build tools or include writable-cache artifacts. Archive
    contents match the manifest, include one `dea-l1/` root, preserve executable/alias behavior, and contain no
    build-worktree dependencies or dangling documentation links. The result record identifies only the successful
    archive from this invocation; failure cannot expose stale success. `smoke-dist` rejects incomplete/tampered payloads
    and unsafe archive members before invoking the compiler, then tests that exact archive without rebuilding it. Every
    distribution contains verified Stage 2 HTML/PDF and its matching docs manifest, with no Stage 1 autodocs.
09. Smoke-test the curated artifact on the supported host matrix and checking/trace selections relevant to prepared
    support. Missing or incompatible native support produces an actionable preparation/toolchain failure.
10. Local install/dist success closes only this plan's delivery contract. Release/snapshot workflows remain owned by
    their separate plan and publication authorization gates.

During implementation, run the new packaging regression suite, installed/extracted smoke workflows, relevant environment
and cache/driver tests, and L1's normal validation. Use these focused commands from `l1/` after the new targets exist:

- `make test-productization`
- `make test-productization-build` for the real Stage 2 private-overlay self-build
- `make smoke-dist ARCHIVE=<archive-from-DIST_RESULT>` on each supported host
- `make test-env`
- `make test-stage1 TESTS="l1c_stage1_installed_preparation_test l1c_stage1_preparation_test"`
- `make test-stage2 TESTS="l1c_stage1_installed_preparation_test l1c_stage1_preparation_test"`
- `make test` for the normal validation gate, including stage parity
- `make triple-test` for the changed Stage 2 construction/overlay/native-support path

Explicit selectors include the installed/preparation CI-only cases; `test` and `test-extended` alone do not. Add direct
new native startup diagnostic cases to both stage selectors. Run broader or trace checks when changed compiler behavior
requires them under `l1/AGENTS.md`; do not repeat preparation benchmarks or run exhaustive `test-ci` solely for an
installer edit.

[autodocs]: closed/2026-10-05-l1-stage-separated-autodocs-noref.md
[installed-inputs]: ../../../docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md
[inventory-contract]: ../../../docs/reference/productization-inventory.md
[inventory-reference]: ../../../docs/reference/productization-inventory.md
[l0-delivery]: ../../../../l0/docs/decisions/0023-toolchain-installation-and-distribution-layout.md
[l1-guidance]: ../../../AGENTS.md
[monorepo]: ../../../../MONOREPO.md
[preparation-contract]: ../../../docs/reference/stdlib-preparation.md
[release-workflows]: ../../../../work/plans/tools/2026-05-12-l1-gha-release-snapshot-workflows-noref.md
[stdlib-preparation]: ../features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md
