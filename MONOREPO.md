# Dea Monorepo

This repository hosts the Dea programming language and its levels as a monorepo.

## Root Workflow

The monorepo root owns a minimal maintenance `Makefile`:

```bash
make help   # show root-only monorepo targets
make venv   # create or sync the shared ./.venv (uv if available, pip fallback otherwise)
make test  # run each registered level's normal test entrypoint
make test-extended  # run each registered level's extended validation entrypoint
make clean  # clean each registered level plus root caches/artifacts
make clean-all  # run each level's full cleanup entrypoint plus root caches/artifacts
```

The root `Makefile` is not a dispatcher for focused level-specific targets. Root `make test` and `make test-extended`
delegate to each registered level. Extended coverage varies by level: L0 adds its dedicated Stage 2 trace sweep; L1 runs
its canonical compiler normal suite. L2 has the corresponding single-compiler gates. Use `make -C l1 test-ci` for
exhaustive L1 coverage. Build, targeted test, docs, and compiler workflows should be run inside the relevant level
directory.

The repository is a single `uv` workspace: the root `pyproject.toml` declares `l0/`, `l1/`, and `l2/` as members, owns
the shared dev/docs dependency groups, and produces a single root `uv.lock`. Level Makefiles' `venv` targets delegate to
the root, so `make venv` from any level directory converges on the same `./.venv`. `uv` is an optional accelerator: when
absent, `make venv` falls back to `python -m venv` plus `pip install` of the dependency-group specifiers extracted from
the root `pyproject.toml`.

## Windows Python environments

Windows repository tooling uses native CPython 3.14+ and native uv with the shared `.venv/Scripts/python.exe`. MSYS2
supplies the shell and C toolchain. Make selects native Python through `HOST_PYTHON` (the Windows Python launcher is the
local default), checks its family, and forwards `PYTHON` to Windows `uv sync --python`. Quote explicit paths:
`make venv PYTHON="C:/path with spaces/Python/python.exe"`. A former MSYS2 `.venv/bin/python` must be removed and
recreated as native before normal Windows tooling runs. POSIX selection and uv invocation are unchanged.

[.github/actions/setup-windows-python/action.yml](.github/actions/setup-windows-python/action.yml) provisions
checked-out Windows CI, snapshot, release, and L1 artifact-build consumers. It exports the native bootstrap as
`HOST_PYTHON`, pins `UV_PYTHON` to that native interpreter, and keeps `UV_PROJECT_ENVIRONMENT` attached to the
checkout's `.venv`. Fresh L1 artifact-verification runners have no checkout; they invoke the native
`actions/setup-python` installation explicitly while retaining the strict MSYS2 toolchain PATH.

Windows jobs validating L0 additionally provision a temporary UCRT64 Python virtual environment under `RUNNER_TEMP`,
outside the checkout. Setup exports pip-compatible requirements from the existing `uv.lock` with
`uv export --frozen --all-groups --no-emit-workspace`, then installs them using the temporary environment's own pip.
`pyproject.toml` and `uv.lock` remain the only dependency authorities; generated requirements stay temporary. Tests do
not export or install requirements. The MSYS2 pass invokes `DEA_MSYS2_TEST_PYTHON` directly through
`make -C l0 test-stage1-msys2`, with the same Stage 1 collection, data, expectations, and `-n auto -q --quiet-progress`
options as the native pass. Both honor `PYTEST_XDIST_AUTO_NUM_WORKERS`. Focused manual L0 targets add native Stage 1
when their target does not already include it. Stage 2, L1/L2, and dedicated trace suites are not repeated for Python
coverage. Environment setup and the extra pytest pass report separate elapsed times in the job summary.

Standalone L0 CI retains `windows-ucrt64-python` for the standard UCRT64 C toolchain and `windows-mingw64-python` for
manual alternate C-toolchain coverage. Both use native shared tooling and the additional UCRT64 Stage 1 pass. The old
`windows-native-python` selector is a compatibility alias for `windows-mingw64-python`; `all` includes the alternate
lane once. No standalone lane creates an MSYS2 shared `.venv`.

## Workflow inputs

Every workflow job starts with `Show inputs`, which prints the current `inputs` context as JSON in the job log and
appends it under `Workflow inputs` in the job summary. Reusable workflows report the inputs received by their own jobs.
The step uses Bash and the workspace root so it can run before checkout on Linux, macOS, and Windows.

## Ubuntu runner baselines

CI, docs, and utilities use `ubuntu-26.04`. Linux release/snapshot builders and L1 artifact acceptance/verifier jobs use
`ubuntu-24.04` to retain the native build baseline. These pins select OS releases; image and package updates continue.

Linux compiler CI uses [.github/actions/setup-linux-temp/action.yml](.github/actions/setup-linux-temp/action.yml) to set
`TMPDIR`, `TMP`, and `TEMP` to `$RUNNER_TEMP/dea-tmp`, avoiding `/tmp` quotas.

## Compiler CI

Unified CI runs selected level delegates sequentially on each native runner. A successful L0 delegate hands its Stage 2
compiler to L1; L1 hands its generated development toolchain to L2. These explicit paths reuse current-checkout,
same-run outputs without reinstalling L1. A skipped predecessor or a custom target that produces no compiler causes the
required development bootstrap to be prepared once. Invalid explicit handoffs fail without reconstruction. Intentional
compiler-construction fixtures retain their independent builds.

The single `L2_CI_DEFAULT_ENABLED` setting in `.github/workflows/ci.yml` is initially `"false"`. Unified's manual
`run_l2_ci` choices are `default`, `on`, and `off`; `off` suppresses L2 even when the central default is enabled.
Push/PR events use the central default. When enabled, L2 is selected for `l2/` or existing shared-tooling changes,
including build helpers, dependency manifests, CI actions, and compiler workflow files. Missing diff endpoints use the
same default. L0/L1 routing is unchanged; an L0/L1-only change does not automatically select L2.

Standalone L2 CI constructs an installed L1 bootstrap by default. Linux Docker isolation is independent and disabled by
default in every delegate invocation: request `run_isolation=true` in L2 CI or `l2_run_isolation=true` in Unified CI.
The latter still requires L2 to be selected. The optional Linux gate retains a Bookworm-compatible installed L1
construction environment and a second operation environment without L1. Run it when bootstrap or ownership boundaries
change; earlier isolation evidence applies to its tested inputs. Compiler CI remains separate from L1 artifact
acceptance and release workflows.

## Documentation CI

Ubuntu documentation producers explicitly select `ubuntu-26.04`, whose packaged TeX Live 2025 includes the modern
tabularray implementation needed by Doxygen 1.18. They use
[.github/actions/setup-docs-toolchain/action.yml](.github/actions/setup-docs-toolchain/action.yml) for Graphviz, Make,
EPS conversion (`texlive-font-utils` and Ghostscript), and optional full TeX installation. Doxygen converts its EPS
diagrams while generating LaTeX, including when PDF compilation is disabled. Setup verifies `dot`, `make`, `epstopdf`,
and `gs`, plus `pdflatex` and `makeindex` for PDF builds, before reference generation starts. It replaces Azure Ubuntu
archive URLs with `https://archive.ubuntu.com/ubuntu` in legacy sources, deb822 sources, and the runner's
`apt-mirrors.txt`, retaining other repositories and signing configuration. Index refresh and installation allow three
retries per failed download and use 30-second HTTP/HTTPS connection and data timeouts. Index fetch errors fail the step.
Each caller caps the whole installation at 15 minutes, including retries and package configuration; a timeout fails the
job. L0's reusable builder retains its `build_pdf` option. Full installation and reference validation run in CI; focused
local tests mock APT. Setup reports installed package versions, active EPS/PDF executable paths, and the tabularray
release selected by `kpsewhich` for PDF builds. The runner release is pinned; Ubuntu package updates remain enabled.

L0 and L1 reference generation prints live phase start/end timings and 30-second elapsed-time heartbeats, including in
quiet mode. Extraction reports each language binding and output format; rendering, normalization, strict checks, PDF
compilation, and bundle verification report separate phases. PDF logs also announce each pdfLaTeX pass and makeindex
invocation. Full subprocess output is flushed continuously to `docgen.log` and `latex.log`, retained with successful
references or failure diagnostics. Verbose mode additionally streams every subprocess line. Measure complete reference
performance in CI after runner or package changes; toolchain compatibility alone does not establish build duration.

Both full-PDF wrappers validate the final `refman.log` and require `refman.ind` before copying PDFs or creating bundles.
Unresolved references, rerun requests, and pdfTeX missing-destination warnings fail the build, including when TeX wraps
the warning or target identifier across lines. Earlier-pass messages in the aggregate `latex.log` do not fail an
otherwise complete final pass. Enum payload lists retain each XML variant's destination and label. Failed builds
preserve the prior successful reference and save diagnostics; `--pdf-fast` remains an incomplete-reference preview.

Native compiler CI and all documentation producers use upstream Doxygen 1.18.0 through
[.github/actions/setup-doxygen/action.yml](.github/actions/setup-doxygen/action.yml). The action selects the native
Linux x64, macOS Intel/ARM64, or Windows x64 archive, verifies its upstream SHA-256 checksum and CLI version, and
prepends its binary directory through `GITHUB_PATH`. Unsupported runners fail explicitly. Windows compiler jobs also
verify the resolved version inside MSYS2; Python selection follows the Windows environment policy above. Release,
snapshot, and publication consumers inherit the pin through the reusable documentation build workflows. To upgrade,
update the version, archive layouts, and upstream checksums in
[.github/actions/setup-doxygen/setup.cjs](.github/actions/setup-doxygen/setup.cjs), then validate the setup tests and
strict reference builds with full PDFs and offline bundles. Local documentation builds continue to use `doxygen` from
`PATH`.

Unified CI routes full reference validation independently for L0 and L1. The L0 workflow builds both stage references;
the L1 workflow builds the canonical XML, HTML, Markdown, LaTeX, full indexed PDF, and verified offline bundle. L1
compiler, documentation, and relevant shared-tooling changes select its reference job. Manual runs and unavailable diff
endpoints select both documentation jobs.

Like L0, the L1 reference job explicitly prints its generated `undocumented-functions.txt` report. Undocumented entries
are informational and do not fail the job. L1 has one canonical report; L0 prints both stage reports. Completed bundles
and available build/report diagnostics are retained on build failure. These validation jobs have read-only repository
permissions and perform no publication.

## AddressSanitizer capability checks

Sanitizer tests use `scripts/asan_test_support.py` to verify both normal executable startup and an actual ASan
heap-buffer-overflow diagnostic from a deliberately invalid read. Accepting `-fsanitize=address` is insufficient:
compilers such as TinyCC that silently ignore instrumentation flags are reported as unavailable.

An ordinary configured C compiler remains the selected compiler. If it lacks ASan, only the ASan-dependent checks skip;
there is no automatic substitution with another compiler. An explicit sanitizer selection such as `L0_ASAN_CC=clang`
requests mandatory coverage and fails if that compiler cannot demonstrate working ASan. Same-compiler non-PIE retries
remain available; compiler-name discovery applies only when neither ordinary nor sanitizer compiler selection is set.
The capability probe has bounded compilation/execution deadlines and disables core dumps for its intentional error.

## Cleanup contract

Each level provides bootstrap-free cleanup using the shared Python helper. `clean` removes all contents of the standard
`build/` directory, including hidden entries, plus known temporary executables and test files. It preserves custom build
trees outside `build/`. `clean-all` additionally removes the complete selected build tree: `DEA_BUILD_DIR` for L0,
`L1_BUILD_DIR` for L1, or `L2_BUILD_DIR` for L2. With the default `build/dea`, their effects overlap.

L0 `clean-dea-build` removes only the selected tree. L1/L2 `clean-runtime` removes the selected tree's `runtime/`,
`lib/`, and copied `include/dea_rt.h` and `include/l1_real.h`, preserving compiler binaries, caches, and other headers.
Cleanup needs Python but does not prepare a virtual environment or bootstrap compiler.

Cleanup prints each removal before attempting it: directory contents and wildcard matches are grouped, while isolated
files and selected build/runtime directories are listed individually. Paths are absolute to identify the owning level in
root aggregate output. Absent outputs are omitted; an already clean level reports `cleanup: nothing to remove`.

Custom cleanup directories must be inside the owning level, in an output namespace such as `out/dea` or `build/custom`.
Empty paths, the level root, paths outside the level, parent traversal, hidden top-level namespaces, source-owned
namespaces (`compiler`, `docker`, `docs`, `examples`, `scripts`, `tests`, `work`, `tools`, `editors`, and level names),
and symlink/junction directory aliases are rejected. Source-name checks are case-insensitive. Validation precedes all
deletions in each level operation, including standard cleanup within `clean-all`. Missing outputs are harmless;
permission and other deletion failures produce a nonzero exit. Generated child symlinks are unlinked without following
them. Cleanup is not transactional after deletion begins.

Run `make test-cleanup` in L0 or `make test-tooling` in L1/L2 for cleanup regressions. The tests use copied Makefiles
and disposable directories; they do not clean the working checkout.

## Language Levels

| Directory  | Description                                                        |
| ---------- | ------------------------------------------------------------------ |
| `l0/`      | Dea/L0 language, compiler, runtime, docs, examples, and tests      |
| `l1/`      | Dea/L1 canonical L0-implemented compiler, runtime, docs, and tests |
| `l2/`      | Dea/L2 canonical L1-implemented compiler, runtime, docs, and tests |
| `editors/` | Shared editor grammars, fallback modes, tags, and tests            |
| `scripts/` | Monorepo-owned automation and shared helper modules                |
| `docs/`    | Dea-wide and monorepo-wide stable documentation                    |
| `work/`    | Dea-wide and monorepo-wide plans and proposals                     |
| `tools/`   | Vendored third-party dependencies                                  |

Root-level stable documentation under [`docs/`](docs/) is reserved for Dea-wide and monorepo-wide reference/spec
material. Root-level lifecycle artifacts such as shared plans live under [`work/`](work/). Shared editor integrations,
the self-contained Tree-sitter grammar package, and their focused validation live under [`editors/`](editors/). Existing
user-facing L0 documentation remains under [`l0/`](l0/). Root-owned automation helpers live under
[`scripts/`](scripts/), while vendored third-party assets remain under [`tools/`](tools/).

## Release Tags

Pre-monorepo history keeps its original bare tags. Existing legacy tags such as `v0.9.0`, `v0.9.1`, and older
`snapshot*` releases remain valid historical references and are not renamed.

Monorepo releases use level-prefixed tags only:

- L0 stable releases: `l0-vX.Y.Z`
- L0 snapshots: `l0-snapshot-...`
- L1 versioned releases: `l1-vX.Y.Z`
- L1 snapshots: `l1-snapshot-...`

Bare `v*` tags are therefore a closed pre-monorepo namespace. New monorepo releases should not dual-tag with bare `v*`.

## Release-line Gating Policy

L0 stable releases (`l0-v*`) and L0 snapshots (`l0-snapshot-*`) remain the stable toolchain release line. L1 development
releases use the `l1-v*` and `l1-snapshot-*` namespaces.
[L1 0.1.0](https://github.com/dea-lang/dea/releases/tag/l1-v0.1.0) was published on 2026-10-13 after fresh artifact and
hosted release-workflow acceptance. Subsequent tags, dispatches, and publication actions remain separately gated.

The release and curated-note policies are recorded in
[docs/decisions/0023-l1-release-workflow-policy.md](docs/decisions/0023-l1-release-workflow-policy.md). The workflow
plan is closed; release preparation remains separate.

L1 release workflows retain the following delivery and namespace requirements:

1. L1 `make install` and `make dist` must be implemented with a stable artifact contract through
   [l1/work/plans/tools/closed/2026-04-02-l1-bootstrap-productization-noref.md](l1/work/plans/tools/closed/2026-04-02-l1-bootstrap-productization-noref.md)
   or a successor.
2. The exact archive-path output and reusable installed/archive smoke command must be documented and validated from a
   clean, relocated prefix on Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64. The installed `l1c` must work
   without source-worktree dependencies, preparing native support in a separate writable cache. Distribution archives
   must include verified canonical L1 HTML/PDF under
   [l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md](l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md),
   retargeted by the shared split plan and built from the same source/version. Historical Stage 2 docs cannot be
   relabeled.
3. Tag validation, conversion to `DEA_DIST_VERSION`, release-note baselines, publication behavior, and the smoke-test
   flow must be documented and reproducible in CI. These contracts are specified in
   [work/plans/tools/closed/2026-05-12-l1-gha-release-snapshot-workflows-noref.md](work/plans/tools/closed/2026-05-12-l1-gha-release-snapshot-workflows-noref.md).
4. The `l1-v*` and `l1-snapshot-*` tag namespaces are exclusive to L1 releases and snapshots. Check authoritative remote
   tag state before preparing each new tag; historical checks and local tag lists are insufficient.

The 2026-10-09 acceptance established the former Stage 2 product only. Fresh four-platform exact-artifact acceptance for
canonical L0-implemented L1 passed on 2026-10-11, satisfying the artifact prerequisite. The existing
`l1-productization-acceptance.yml` remains the separate build/fresh-host verification gate. Namespace reservations and
compiler CI do not establish publication readiness. The current delivery contract is
[l1/docs/decisions/0043-canonical-compiler-toolchain-delivery.md](l1/docs/decisions/0043-canonical-compiler-toolchain-delivery.md).

Workflow review, local syntax/policy validation, and hosted acceptance follow implementation. A successful manual
dispatch is not a prerequisite for writing the workflow. GitHub manual dispatch requires the workflow to exist on the
default branch before the first hosted check. Local validation does not establish successful hosted publication.

Hosted acceptance requires one deliberately prepared snapshot and one versioned release, each building and smoke-testing
all four archives before publication. These milestones passed for the generated-note workflows. Curated-note composition
is covered by focused local validation. Follow the separate tag-creation, tag-push, and remote-write authorization gates
in [AGENTS.md](AGENTS.md); implementing the plan does not authorize those actions. Snapshot dispatch with
`publish_release=false` still creates/pushes a tag and uploads a draft release, so it also requires authorization. The
completed milestones and focused local validation establish plan completion without a duplicate acceptance release. They
do not authorize publication.

The implemented workflows are [.github/workflows/l1-snapshot.yml](.github/workflows/l1-snapshot.yml),
[.github/workflows/l1-release.yml](.github/workflows/l1-release.yml), and
[.github/workflows/l1-docs-build.yml](.github/workflows/l1-docs-build.yml). Snapshot inputs are `ref` (empty selects the
default branch once), optional `snapshot_tag`, and `publish_release` (default `true`). The reusable docs workflow
requires an immutable `source_ref`, `package_version`, and `release_tag`. Every executable job reports its inputs in
both its log and summary. Both release types retain `make_latest=false` and development-toolchain labeling.

Versioned releases require `l1/docs/releases/X.Y.Z.md` at the selected source revision, beginning with `# Dea/L1 X.Y.Z`,
the development notice, and curated release content. The preparation job validates these requirements before
documentation and native builds. The publisher preserves the curated document and appends `## Commit history`, the
baseline paragraph ending with a colon, and generated commits. Snapshots keep automatic notes. Authoring and baseline
rules are in [l1/docs/releases/README.md](l1/docs/releases/README.md).

Rerun all jobs after a failed release attempt. Original source/tag identity is retained, while docs, builds, reports,
and logs are isolated by attempt; partial reruns fail rather than mix attempts. Matching drafts may replace their own
older timestamped archives. Published releases remain immutable. The publisher validates four native archives, one
matching docs bundle, its byte-identical standalone PDF, and `SHA256SUMS` before publication. Local policy validation is
available through `.venv/bin/python -m pytest -q -n 0 scripts/tests/test_l1_release.py` and L1 `make test-tooling`.

Delivery documentation distinguishes implementation, fresh acceptance, publication, and language maturity. L1 0.1.0
contains the canonical L0-implemented `l1c`, matching toolchain inputs and canonical offline HTML/full PDF, `VERSION`,
and the inventory. The release handoff retains seven assets: four native archives, the matching docs bundle and PDF, and
`SHA256SUMS`. Source/version/docs identities must agree, and release types use `make_latest=false` to preserve L0's
latest selection. L1 scope is not frozen; release does not imply language stability.

## Working In `l2/`

L2 has one `.l1` compiler implementation and physically owned `.l2` stdlib/runtime inputs. Supply compatible
`L2_BOOTSTRAP_L1C=/absolute/prefix/bin/l1c` before `make -C l2 build` or root aggregate tests. The default
`L2_BOOTSTRAP_MODE=installed` requires a complete prefix. Explicit `L2_BOOTSTRAP_MODE=development` permits a generated
L1 development launcher with matching native binary, headers, and semantic interfaces. There is no implicit sibling
checkout or PATH fallback; L2 target inputs remain physically owned by L2. Run
`L2_ISOLATION_BOOTSTRAP_PREFIX=/absolute/installed-bookworm-l1 make -C l2 test-isolation` to prove this boundary and
target execution without L1. L2 release productization is outside the split. See [l2/AGENTS.md](l2/AGENTS.md).

## Working In `l0/`

Dea/L0 works as a self-contained project inside [`l0/`](l0/). From the monorepo root, `cd l0` before running build,
test, or docs commands.

- Dea monorepo overview: [`README.md`](README.md)
- Canonical L0 overview and quickstart: [`l0/README.md`](l0/README.md)
- L0 contributor guidance: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Repository security policy: [`SECURITY.md`](SECURITY.md)
- L0 AI guidance: [`l0/AGENTS.md`](l0/AGENTS.md)

For example:

```bash
make venv   # shared by all level subtrees
cd l0
make help
make test
make test-extended
```

Third-party notices for shared vendored assets live at [`THIRD_PARTY_NOTICES`](THIRD_PARTY_NOTICES).

## Working In `l1/`

Dea/L1 provides the canonical L0-implemented compiler inside [`l1/`](l1/). From the monorepo root, `cd l1` before
running L1 bootstrap commands.

- L1 subtree pointer: [`l1/README.md`](l1/README.md)
- L1 AI guidance: [`l1/AGENTS.md`](l1/AGENTS.md)

Typical local bootstrap flow:

```bash
make venv
cd l1
make use-dev
source build/dea/bin/l1-env.sh
```
