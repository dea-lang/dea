# L1 Installation and Distribution Contract

Version: 2026-10-09

L1 exposes `make install PREFIX=...` and `make list-installed PREFIX=...` for a curated, self-built Stage 2 toolchain.
Prefix ownership, recoverable payload copying, installed-context launchers, generated provenance, and native startup
validation and optional Stage 2 documentation installation are implemented. `make dist` creates a local archive with
required Stage 2 documentation, and `make smoke-dist` validates that exact artifact. Full platform acceptance remains in
[l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][productization].

## Local distribution workflow

Run from `l1/`, using the same checkout and version for documentation and compiler construction:

```bash
make docs-artifacts DOC_STAGE=stage2 DEA_DIST_VERSION=dev
make dist DEA_DIST_VERSION=dev \
  DOCS_ARTIFACT="/absolute/path/to/l1/build/docs/artifacts/dea_l1_stage2_autodocs.tar.gz" \
  DIST_RESULT="/absolute/path/to/result.json"
make smoke-dist ARCHIVE="/absolute/archive_path/from/result.json"
```

`make dist` uses the public install builder with private staging outside the source/build trees. It requires an existing
verified Stage 2 HTML/full-PDF bundle; it never invokes documentation generators. The bundle is snapshotted before
bootstrap, validated against the checkout, and included under `share/doc/dea/l1/autodocs/stage2/`. Stage 1, compiler
implementation/tests, caches, native support profiles, generated C, and docs intermediates are excluded.

Archives live in `l1/dist/` and contain exactly one `dea-l1/` root. Names are
`dea-l1-lang_<version>_<os>-<arch>_<YYYYMMDD-HHMMSS>.tar.gz` on Linux/macOS and `.zip` on Windows UCRT64. The timestamp
comes from the payload's UTC build provenance. Supported tokens are `linux-x86_64`, `macos-x86_64`, `macos-arm64`, and
`windows-x86_64`. The version defaults to `dev`; every package retains Stage 2 development maturity. Existing archive
names are rejected rather than overwritten. Archives are closed, extracted privately, and verified against the complete
inventory and documentation contract before atomic publication. Packaging changes no development alias.

`DIST_RESULT` is optional; successful commands also print the absolute archive path. When supplied, it must be an
absolute `.json` destination outside the checkout or directly in `l1/dist/`. Symlink destinations/parents, hard-linked
files, and overlaps with inputs are rejected without deleting them. After destination preflight, any previous result is
removed before validating docs or building. A new complete JSON record is closed in a sibling temporary file and
atomically replaces the destination only after archive publication and scratch cleanup. A failed result publication can
leave a verified archive, but never a success result. This is process-interruption handling, not power-loss durability
or concurrent invocation coordination; callers must use distinct result paths and serialize identical artifact names.

The schema-1 result contains exactly these fields:

| Field                            | Meaning                                                                                                                      |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `schema_version`                 | Integer `1`.                                                                                                                 |
| `archive_path`                   | Absolute path of this invocation's newly published archive.                                                                  |
| `archive_sha256`, `archive_size` | SHA-256 hex digest and byte count of that archive.                                                                           |
| `level`, `stage`, `maturity`     | `l1`, integer `2`, and `development`.                                                                                        |
| `package_version`, `os`, `arch`  | Identity tokens matching `VERSION` and the installation inventory.                                                           |
| `provenance`                     | Exact inventory provenance: source, bootstrap chain, native compiler/options, build time/ID, and shipped preparation inputs. |
| `docs_bundle_sha256`             | SHA-256 of the snapshotted input docs bundle.                                                                                |
| `docs_source`                    | Docs manifest source revision, tree state, and selected-input digest.                                                        |

Workflow consumers must check command success before reading their unique result, verify the archive digest, and pass
its exact `archive_path` to smoke validation. Do not glob old archives or parse build logs. Hosted aggregation, tags,
release notes, and publication remain owned by the separate release/snapshot workflow plan.

`make smoke-dist` requires an absolute `ARCHIVE` and neither bootstraps nor prepares a Python environment. Its Python
harness preflights all tar/zip members before extraction, rejecting traversal, duplicate/case-colliding paths, hard
links, devices, escaping/dangling aliases, and file/parent collisions. It verifies inventory digests/modes, exact
file/directory membership, curated content, `VERSION`, shipped-input provenance, full docs identity, and offline links.

The extracted prefix moves to a path containing spaces. From an unrelated directory, smoke checks all launcher/native
help/version forms, semantic operations with no compiler tools on PATH, compile-only output, standalone link without
`-I`, cold preparation, build/run, warm no-auto reuse, checking/trace configuration switching, forced preparation, and
cache disposal. A private cache and controlled native-tool PATH exclude repository aliases and bootstrap tooling. POSIX
prefixes become read-only during execution, and all hosts verify unchanged payload bytes afterward. Select a supported C
compiler with `L1_CC`; native execution is valid only on the archive's host family/architecture. Windows retains the
UCRT64 tool and Windows system directories for DLLs and host commands during native compilation. Windows semantic-only
checks instead use a private PATH directory containing only copied UCRT64 runtime DLLs, with both C compiler selectors
pointing to an absent executable. This permits compiler startup without exposing compiler, Python, or Make tools.

## Productization acceptance gate

`make test-productization-acceptance` orchestrates distribution construction and smoke verification using the same
helpers as `dist` and `smoke-dist`. Supply the matching verified docs bundle and a new absolute evidence directory:

```bash
make test-productization-acceptance DEA_DIST_VERSION=dev \
  DOCS_ARTIFACT="/absolute/path/to/dea_l1_stage2_autodocs.tar.gz" \
  ACCEPTANCE_DIR="/absolute/path/to/new-acceptance-evidence"
```

The directory must not already exist, including after an interrupted attempt. The gate retains the exact archive,
original schema-1 `result.json`, and a small standard-library-only `harness/`. It verifies archive size/digest and
payload/docs identity against the result before invoking native smoke checks. `acceptance.json` is written only after
successful smoke execution; an earlier report is removed before retrying verification. Build evidence is retained on
verification failure. The original result's absolute `archive_path` remains provenance of construction; verification
locates the transported archive by that path's basename inside the evidence directory and checks its digest.

The default `ACCEPTANCE_PHASE=all` builds and verifies locally. `ACCEPTANCE_PHASE=build` prepares evidence for a
separate verification host. Copy the whole evidence directory to a host of the matching platform, then run:

```bash
python3 -I /absolute/evidence/harness/productization_acceptance.py \
  --phase verify --directory /absolute/evidence
```

Use native UCRT64 `python` on Windows. The verifier needs only Python's standard library and supported native host
tools; it does not need the repository, Make, documentation generators, or bootstrap compilers. Select the native
compiler with `L1_CC`. A combined local run does not establish that the checkout is unavailable.

The manual `L1 Productization Acceptance` workflow in
[.github/workflows/l1-productization-acceptance.yml][acceptance-workflow] builds one full Stage 2 docs bundle, then
builds Linux x86_64, macOS Intel/ARM, and Windows UCRT64 archives from the same selected source and version. Separate
fresh verification jobs download only the archive/result/harness evidence, with no checkout or bootstrap artifacts. They
retain the acceptance report and smoke log; build jobs retain archives and build logs. This establishes checkout
independence when the hosted jobs pass. The workflow has read-only repository permissions and no release, tag, or Pages
publication steps. It is separate from `test-ci`; running ordinary CI does not run this gate.

Native artifact acceptance passed on all four platforms on 2026-10-09, including full Stage 2 HTML/PDF and fresh-runner
verification without checkout or bootstrap compilers. The remaining productization work is the delivery decision record,
bootstrap ADR amendment, and final documentation handoff; hosted release and documentation publication remain separate.

## Public install workflow

Run the targets from `l1/`. `PREFIX` is required and relative destinations resolve against that directory. Destination
validation and package-version/host checks run before bootstrap. `DEA_DIST_VERSION` defaults to `dev`. Direct installs
omit autodocs by default. Set `DOCS_ARTIFACT` to an absolute Stage 2 bundle path generated by
`make docs-artifacts DOC_STAGE=stage2 DEA_DIST_VERSION=<version>` from the same checkout and package version.

The installer verifies the existing bundle contract before bootstrap: level/stage, version, source revision and dirty
state, selected-source digest, strict full HTML/PDF flags, file digests, and offline links. Unsafe archive members and
source/destination overlap fail without modifying the prefix. Extraction lives in private scratch beneath
`L1_BUILD_DIR`, is retained throughout construction, and is removed on success or failure. Source identity is checked
again before publication. Installation never invokes Doxygen or TeX.

Verified `html/`, `pdf/`, and `manifest.json` files are installed beneath `share/doc/dea/l1/autodocs/stage2/` and
recorded in the normal ownership inventory. Reinstalling with or without docs replaces or removes only owned
documentation; unrelated files remain. Open `html/index.html` or `pdf/dea_l1_stage2_api_reference.pdf` under that
directory without network access. A compiler-only prefix remains valid.

`install_toolchain.py` resolves `L1_BOOTSTRAP_L0C` or prepares the absent default `../l0/build/dea/bin/l0c-stage2`
through L0's `venv` and `install-dev-stage2` targets. An invalid explicit override fails without trying the default or
ambient `l0c`. Upstream preparation does not change L0's selected development alias.

L1 construction uses a disposable directory beneath the validated repo-local `L1_BUILD_DIR` (default `build/dea`). It
builds Stage 1, uses that exact compiler to build a repository-mode Stage 2 seed, and requires the seed to reproduce
Stage 1's complete semantic interface set byte-for-byte. The existing payload helper then self-builds the marked Stage 2
executable using that seed and one provenance snapshot. Host compiler selection and runtime controls agree across seed
and final construction. Inherited installation roots/runtime overrides are cleared, and native support uses a private
cache. No development compiler or selected alias is replaced, and private scratch is removed on success or failure.

The installer publishes the curated payload through the recovery protocol below. It rejects overlap with bootstrap,
payload, and source inputs. A failed construction cannot mutate the destination. Reinstall replaces owned files and
removes obsolete ownership while preserving unrelated files; serialize it against compiler consumers and other
installers. Prefix payload files become immutable inputs for compiler operations after installation.

`list-installed` has no venv, bootstrap, native compiler, or cache prerequisite. It prints sorted prefix-relative
inventory paths only and fails for missing, malformed, or incomplete metadata. It requires Python to read the record;
installed native compiler startup itself does not require Python or Make.

## Inventory schema

[l1/scripts/productization_inventory.py][inventory] defines schema version 1. The same format will be consumed by the
native startup reader. A complete record requires exactly these fields:

| Field             | Value                                                                                                               |
| ----------------- | ------------------------------------------------------------------------------------------------------------------- |
| `schema_version`  | Integer `1`                                                                                                         |
| `level`           | `"l1"`                                                                                                              |
| `stage`           | Integer `2`                                                                                                         |
| `state`           | `"complete"` or `"incomplete"`                                                                                      |
| `package_version` | Nonempty filename token beginning with an ASCII letter or digit, followed by letters, digits, `.`, `_`, `+`, or `-` |
| `maturity`        | `"development"`, independently of the package version                                                               |
| `os`, `arch`      | Nonempty lowercase ASCII target tokens; letters, digits, `_`, and `-` are allowed                                   |
| `provenance`      | Nonempty JSON object supplied by the package builder; values must satisfy the native JSON bounds below              |
| `entries`         | Intended owned files and aliases                                                                                    |

An incomplete record additionally requires `previous_entries`, retaining the ownership of the previous installation and
any interrupted installation attempts. Both entry lists obey the same validation rules. The provenance collector
supplies the detailed source/bootstrap/build provenance fields; the inventory helper does not invent preparation
identities or native cache keys.

Each entry is one of:

- A regular file: `path`, `kind: "file"`, `mode` (decimal `420` or `493`, corresponding to `0644` or `0755`), and
  lowercase SHA-256 `sha256`.
- An alias: `path`, `kind: "alias"`, and a relative `target` resolved from the alias's parent directory. Alias chains
  must terminate at a listed regular file. Absolute, escaping, dangling, cyclic, and metadata aliases are rejected.
- The manifest itself: `path: "share/dea/l1/install-manifest.json"`, `kind: "manifest"`, and `mode: 420`. The manifest
  has no self-digest.

Paths use canonical prefix-relative `/` separators. Empty components, `.`, `..`, backslashes, control characters,
Windows-reserved names/characters, trailing dots/spaces, duplicate paths, case/Unicode-equivalent collisions, and file
paths used as parent directories are rejected. Unknown record/entry fields and duplicate JSON object keys are errors.
The native JSON format limits records to 16 MiB, 100,000 value nodes, and nesting depth 64. Object keys must be strings;
strings must be valid Unicode without NUL. Numeric provenance values must be finite; schema and mode fields remain
integers. The Python validator enforces these bounds before publication. Regular source files receive portable read or
executable modes; aliases preserve their relative targets. Windows payload builders use ordinary file copies for
launcher aliases. POSIX verification checks recorded modes; Windows verification checks bytes and file type without
treating POSIX mode bits as native permissions.

## Prefix installation and recovery

`resolve_prefix` resolves relative prefixes against the L1 working directory without changing repo-local build-layout
containment. The destination cannot replace the source root, be a symlink, or overlap supplied protected input paths.
`install_payload` always protects the payload tree and L1 compiler source tree. Its caller must also supply every other
build/source input that the package construction needs to preserve.

The caller selects a curated staging tree; these helpers do not select the final toolchain payload or build a compiler.
`inventory_payload` hashes that tree, rejects unsupported filesystem nodes, and adds the self-owned manifest entry. The
source tree cannot supply installation metadata or private temporary metadata files.

Installation is externally serialized against consumers and other installers:

1. Validate intended and previous inventories, source/destination separation, destination parents, and collisions.
   Reject unowned files, substituted symlink parents, unsafe owned aliases, and hard-linked destination files before
   mutation. Existing unrelated files and directories remain unowned.
2. Publish an incomplete inventory containing previous and intended ownership. Write and close a private temporary
   record in the manifest directory, then atomically replace the authoritative manifest. A failed initial replacement
   leaves the previous inventory and payload files unchanged.
3. Copy intended files and create relative aliases, then remove obsolete owned files. Ordinary payload writes are not an
   atomic upgrade and do not promise rollback. Any interruption leaves the incomplete inventory available for retry.
4. Verify every intended payload digest, file type, portable mode where supported, and alias. Only successful
   verification permits atomic publication of the complete record. A failed final publication retains incomplete state.

A retry may use a different intended payload. Ownership retained across interrupted attempts permits removal of both
previous and intermediate obsolete files without deleting unrelated files. Temporary records never confer ownership.
This is process-interruption recovery, without a power-loss durability guarantee.

`read_inventory` validates metadata without hashing payload files. `list_installed` requires complete state and returns
sorted recorded paths, including the manifest. Neither helper invokes build tools, scans native caches, or claims
unrelated prefix contents. `verify_payload` performs full recorded content verification for installer/artifact
consumers. Missing, unreadable, malformed, and incomplete metadata produce actionable tooling errors with repair/retry
guidance.

## Launcher templates

[l1/scripts/productization_launchers.py][launchers] adapts shared prefix renderers without changing L0 defaults:

- POSIX and Windows launchers choose their own physical prefix for `L1_HOME` and clear inherited `L1_BUILD_DIR`.
- Explicit system, runtime, cache, and compiler selectors remain in the child environment.
- Bash/zsh activation moves the selected `bin` directory to the front of `PATH`, removes duplicates for that directory,
  preserves other entries in order, and clears shell command caches. It must be sourced.
- Windows compiler wrappers use `setlocal` and preserve the native exit status through `endlocal`; activation
  intentionally transfers `L1_HOME`, `PATH`, and cleared `L1_BUILD_DIR` into the caller. Activation retains the shared
  MSYS2 toolchain discovery, checks PATH membership case-insensitively, and adds a missing toolchain directory without
  duplicating an existing entry. The selected compiler directory moves to the front; other entries retain their order,
  including empty entries and literal `!` and `%` characters. Repeated prefix switching can therefore leave the
  toolchain directory after an inactive compiler directory.

The templates select prefix context. Marked native compilers independently derive and validate that context before
command dispatch. Shell-only probes still exercise argument, environment, and exit-code behavior separately.

## Private Stage 2 build-info overlay

`build_compiler` in [l1/scripts/build_stage2_l1c.py][stage2-builder] accepts an optional `build_info_overlay` path. The
caller supplies a generated L1 `build_info` module and a separate native output path. The builder snapshots that file
before construction, writes it as `build_info.l1` in private scratch, and puts that project root ahead of the checked-in
compiler source root. It copies no neighboring modules. Scratch is removed after successful construction or an
exception; `keep_c=True` still retains the generated C beside the requested output.

Missing or unreadable explicit overlays fail before construction. Invalid L1 is rejected by the selected compiler;
neither case falls back to repository metadata. Calls without an overlay retain ordinary repository build behavior. The
builder neither edits checked-in sources nor selects the development alias. Its existing construction environment
overrides inherited `L1_HOME` and clears system/runtime input overrides.

[l1/scripts/productization_provenance.py][provenance] captures one immutable snapshot for the overlay, standalone
`VERSION` text, and inventory metadata. `collect_provenance` takes explicit upstream L0, L1 Stage 1, and Stage 2 seed
paths, recorded Stage 1 construction arguments, and shipped preparation-input digests. It probes each compiler identity,
records source revision/cleanliness (explicitly unknown outside Git), uses the canonical repository URL, and returns the
effective self-build environment alongside the snapshot. Pass that returned environment to `build_compiler`; the
recorded native compiler and C flags include the builder's runtime/quarantine defaults. Only selected options enter
metadata; the process environment is not serialized. Paths are informational, never installed lookup roots.

The explicit `DEA_DIST_VERSION` or `dev` fallback is shared with documentation bundles and must be a portable filename
token. Host tokens cover Linux x86_64, macOS x86_64/arm64, and Windows UCRT64 x86_64. Build time is captured once in
UTC. Development maturity remains visible in native version output even for version strings that resemble stable
releases. `VERSION` and inventory provenance additionally retain bootstrap reports, construction arguments, and named
SHA-256 input digests. A preparation-service identity is recorded only when supplied; this helper never derives `D` or a
native cache key. The caller must provide the actual Stage 1 arguments and digests of the selected shipped inputs.

`build_info_module(installed=True)` enables the native installed marker. The default remains `False`, matching both
checked-in fallback modules and ordinary repository construction. An overlaid build alone is not a complete package.

## Native installed startup

The shared native hook in [l1/compiler/stage1_l0/support/installation.h][installation] runs before CLI parsing when the
compiled marker is enabled. Both compiler stages contain the same hook; only Stage 2 packaging enables it. Existing
preparation support provides the executable-path, filesystem, and bounded JSON helpers. Preparation identity parsing
retains its integral-only JSON mode; the inventory reader additionally accepts finite numeric provenance values.

The running executable's physical parent must be `bin/`. Its parent becomes the prefix, independently of wrappers,
`L1_HOME`, `L1_BUILD_DIR`, and inventory contents. Metadata and its parent directories must be ordinary
files/directories, not substituted links. Startup validates schema 1, L1 Stage 2, development maturity, complete state,
required fields, entry shapes, portable paths, exact duplicate paths, mode values and digest syntax, and closed relative
alias chains. Installer preflight additionally owns case/Unicode-equivalent path collision checks and destination
safety; full artifact verification owns payload hashing and physical mode checks.

Invalid state prints `L1C-9515` with the metadata path or unresolved executable context and repair/retry guidance, then
returns status 1 even for help/version. Successful startup sets `L1_HOME` to the physical prefix and clears inherited
`L1_BUILD_DIR`, preserving explicit system/runtime/compiler/cache selectors. No external interpreter, build tool, cache
write, or payload digest scan is needed. Repository-mode binaries do not invoke the hook or require inventory metadata.

## Curated payload assembly

`productization_payload.build_payload` consumes an explicit completed bootstrap layout and Stage 2 seed. It selects only
bundled `std.*`/`sys.*` sources, the exact corresponding interface set, runtime C sources and internal headers, public
headers, and the two runtime symbol manifests. Bootstrap public headers must match the source headers. Selected files
and parents must be ordinary files/directories; compiler sources, native caches, retained outputs, and unrelated build
files are excluded.

The helper captures support bytes before construction and records every captured support digest in provenance. It
validates the captured interface graph with the selected seed, then self-builds a separate marked native compiler with a
private provenance overlay. The private payload adds installed launchers/activation, `VERSION`, notices, a bundled smoke
program, and standalone instructions with package-relative or canonical repository links. Windows payloads include both
MSYS2 shell entrypoints and native Command Prompt counterparts.

Packaged guides come from `l1/docs/user/`, following the L0 convention. `README.md` and `README-WINDOWS.md` go to the
prefix root; `toolchain.md` goes to `share/doc/dea/l1/toolchain.md`.

The context-managed result is an uninstalled payload for `install_payload`; it does not publish an inventory itself.
Private scratch and payload files are removed on success or failure when the context exits. The public installer owns
the prerequisite bootstrap chain, optional verified Stage 2 documentation, and inventory publication.

## Validation

From `l1/`, run `make test-productization`. The fixture suite covers metadata/path rejection, collisions, preservation
of unrelated files, controlled reinstalls, interrupted metadata/payload writes and deletion, digest failure, ownership
recovery, relocation with spaces, and launcher/activation behavior. It is included in `make test` and
`make test-extended`. Native `cmd.exe` cases run on Windows; unavailable host shells are reported as skipped.

`make test-productization-build` is the explicit native overlay acceptance target. It builds the Stage 2 seed, uses it
to self-build a separate compiler with test provenance in a path containing spaces, removes the input overlay, verifies
generated provenance in native version output and semantic compilation, and checks that source modules and development
binaries/aliases retain their bytes. It does not establish installed-package acceptance or run automatically in the
lightweight fixture gate. The same target also self-builds a marked compiler and exercises direct and launcher
entrypoints against a relocated prefix, stale inherited roots, read-only inputs, and absent/malformed/incomplete
metadata. Its curated payload also covers compile-only use, a cold cache with automatic preparation disabled, native
preparation/run, and warm standalone linking while preserving installed digests. The guard fixtures use real native code
and run through `test-productization`; platform-specific cases skip explicitly when their host prerequisites are absent.

[acceptance-workflow]: ../../../.github/workflows/l1-productization-acceptance.yml
[installation]: ../../compiler/stage1_l0/support/installation.h
[inventory]: ../../scripts/productization_inventory.py
[launchers]: ../../scripts/productization_launchers.py
[productization]: ../../work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md
[provenance]: ../../scripts/productization_provenance.py
[stage2-builder]: ../../scripts/build_stage2_l1c.py
