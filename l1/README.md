# Dea/L<sub>1</sub>

This subtree contains the bootstrap and self-hosted compilers for Dea/L1 inside the Dea monorepo.

The canonical project overview lives in [README.md][root-readme]. Run L1 development commands from this directory.
L1-local stable documentation lives under [l1/docs/][docs], while L1-local plans and other lifecycle artifacts live
under [l1/work/][work].

The subtree also includes minimal example programs at [examples/][examples].

Useful local documents:

- [l1/docs/project-status.md][project-status] for the current L1 implementation status
- [l1/docs/roadmap.md][roadmap] for the live L1 direction document
- [l1/docs/user/linking.md][linking] for external native-library and foreign-object linking
- [l1/docs/reference/stdlib-preparation.md][preparation] for bundled interfaces and on-demand native support
- [l1/docs/reference/productization-inventory.md][productization] for prefix ownership/recovery and launcher helpers
- [l1/docker/wine/README.md][docker-wine] for the experimental cached Windows toolchain runner
- [l1/AGENTS.md][agents] for repo-local AI guidance

At the moment the Dea/L1 source surface is `.l1`, including the copied L1 stdlib under `compiler/shared/l1/stdlib/` and
the L1-language fixture programs exercised by the bootstrap compiler tests. The `stage1_l0` compiler implementation and
its implementation tests are `.l0` sources and are built or run with the upstream `l0c-stage2` toolchain during
bootstrap.

Both compiler stages support per-module generated C, compile-only `.o + .l1m` artifact pairs, verified standalone
linking with ordered interface discovery, and multi-compilation-unit build/run across mixed source/interface graphs.
Link-involving modes also accept one ordered stream of explicit foreign objects, external libraries, search paths,
rpaths, and raw host-driver words. Stage 2 is the mechanical L1 port of the Stage 1 oracle. L1 supports Stage 2
installation with optional offline HTML/PDF references and local distribution archives with required Stage 2 docs.
Hosted release workflows remain pending.

`make test-productization` validates prefix ownership/recovery, installed-context launchers, native startup guards,
curated payload selection, public install orchestration, safe archives, and atomic distribution results. It is included
in the normal test gates.

Use `make dist DOCS_ARTIFACT=/absolute/stage2-bundle.tar.gz DIST_RESULT=/absolute/result.json` to create a curated
archive in `l1/dist/`. Run `make smoke-dist ARCHIVE=/absolute/archive.tar.gz` against the exact resulting archive. See
[l1/docs/reference/productization-inventory.md][productization] for naming, result schema, and validation.

To install a self-built Stage 2 compiler outside the development layout, run from `l1/`:

```bash
make install PREFIX="/path/to/l1" L0_CC=gcc L1_CC=gcc
make list-installed PREFIX="/path/to/l1"
"/path/to/l1/bin/l1c" --version
"/path/to/l1/bin/l1c" --run "/path/to/l1/share/dea/l1/smoke/hello.l1"
```

`PREFIX` is required; relative paths resolve against `l1/`. Installation prepares missing repo-local upstream L0 Stage
2, or honors an explicit `L1_BOOTSTRAP_L0C`. It builds private L1 Stage 1 and Stage 2 seed artifacts beneath
`L1_BUILD_DIR`, then self-builds the delivered Stage 2 executable. Development compiler artifacts and the selected `l1c`
alias are preserved. `DEA_DIST_VERSION` defaults to `dev`; every package remains a development toolchain.

The prefix is relocatable and needs no activation to run. Optionally source `<PREFIX>/bin/l1-env.sh` in bash/zsh or
MSYS2 bash, or call `<PREFIX>\\bin\\l1-env.cmd` in native Windows cmd.exe. Installed compiler operations need no L0,
Python, or Make; native output still requires a host C compiler and preparation tools. Semantic inputs remain in the
prefix, while native support is prepared in the selected writable cache. Reinstall with the same command to replace
owned files, remove obsolete owned files, and preserve unrelated files. Serialize installation against other installers
and compiler consumers. `list-installed` prints sorted recorded paths without building or scanning caches.

To include the Stage 2 offline reference, generate a bundle from the same checkout and package version, then pass its
absolute path to installation:

```bash
make docs-artifacts DOC_STAGE=stage2 DEA_DIST_VERSION=dev
make install PREFIX="/path/to/l1" DEA_DIST_VERSION=dev DOCS_ARTIFACT="/absolute/path/to/dea_l1_stage2_autodocs.tar.gz"
```

Use the bundle path printed by `docs-artifacts`. Installation verifies stage, version, source revision/tree state,
selected-source digest, HTML/PDF completeness, offline links, and file digests before bootstrap. It does not run Doxygen
or TeX. Open `<PREFIX>/share/doc/dea/l1/autodocs/stage2/html/index.html` or the PDF in the adjacent `pdf/` directory.
Omit `DOCS_ARTIFACT` for a compiler-only install; reinstalling without it removes previously owned docs and preserves
unrelated files. Regenerate the bundle after changing checkout identity or documentation inputs. See
[l1/docs/reference/productization-inventory.md][productization] for the install/recovery contract and
[l1/docs/user/toolchain.md][installed-toolchain] for installed operation.

`make build-stage1` supplies public runtime headers and the complete verified bundled interface set under
`$L1_BUILD_DIR/interfaces/`. Build/run/link prepare matching native stdlib/runtime support on demand in one local cache.
`--prepare-stdlib` explicitly prepares a reusable profile; `--no-auto-prepare` requires a valid existing profile when
bundled native support is needed.

Full L1 support currently requires **upstream Clang 16 or newer** when selecting Clang as the C compiler. Clang 14/15
lack `--no-default-config`, which managed stdlib/runtime preparation requires. The minimum version is necessary, not a
guarantee that every toolchain configuration supports persistent reuse. Apple Clang uses separate version numbering; its
selected installation must support the required configuration controls and pass L1 preparation validation.

Use Clang 16+ or the supported GCC lane for normal builds, tests, benchmarks, and experiments. The repo-owned `l1-test`
Bookworm image supplies Clang 14, so keep its default GCC selection; use a separately verified modern Clang environment
when Clang coverage is needed. Older Clang is reserved for isolated compatibility validation under
[l1/work/plans/bug-fixes/2026-09-27-legacy-clang-preparation-compatibility-noref.md][legacy-clang-plan]. That Draft plan
does not yet provide legacy support; this requirement remains in effect until support is implemented and documented.

Stage 1 validation combines the `.l0` implementation test suite under `compiler/stage1_l0/tests/` with warning-free
latest-stage `--check` coverage for `examples/*.l1`. Exact generated-C golden-file parity is not part of the active L1
Stage 1 contract.

Stage 2 compiles and runs its own `.l1` implementation tests and shares compiler-facing Python integration coverage.
`make test` is the fast local gate built from representative compiler checks, examples, parity, and inexpensive tooling
regressions. `make test-extended` runs the Stage 1 and Stage 2 normal suites, parity, examples, and tooling while
excluding CI-only normal cases and environment/trace/bootstrap integration. Hosted `make test-ci` adds those CI-only
cases, environment/bootstrap checks, both default trace suites, child fixtures, and triple bootstrap. `make triple-test`
also runs that fixed-point check directly. `make use-dev-stage1` switches back to the bootstrap compiler; ordinary
builds and tests preserve the selected alias.

Local normal suites retain multiplication arithmetic and all six overflow checks without rebuilding a compiler inside
their harness, plus representative cold/warm managed preparation. Installed read-only inputs and the preparation
recovery/concurrency matrix run in CI, as does embedded-driver overflow compilation in `mul_runtime_compile_test`. These
checks remain selectable by name through `test-stage1` and `test-stage2`. Dedicated trace discovery includes CI-only
normal cases; only the independent slow-trace policy filters its default set.

Minimal local workflow:

```bash
make use-dev-stage2
source build/dea/bin/l1-env.sh
l1c --version
```

`make use-dev-stage2` auto-prepares the default repo-local upstream `../l0/build/dea/bin/l0c-stage2` when needed.

To use an explicit upstream L0 compiler instead of the repo-local default, set `L1_BOOTSTRAP_L0C=/path/to/l0c` when
running `make build-stage1`.

[agents]: AGENTS.md
[docker-wine]: docker/wine/README.md
[docs]: docs/
[examples]: examples/
[installed-toolchain]: docs/user/toolchain.md
[legacy-clang-plan]: work/plans/bug-fixes/2026-09-27-legacy-clang-preparation-compatibility-noref.md
[linking]: docs/user/linking.md
[preparation]: docs/reference/stdlib-preparation.md
[productization]: docs/reference/productization-inventory.md
[project-status]: docs/project-status.md
[roadmap]: docs/roadmap.md
[root-readme]: ../README.md
[work]: work/
