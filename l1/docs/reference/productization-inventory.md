# L1 Productization Inventory Helpers

Version: 2026-10-07

The first productization milestone implements prefix ownership, recoverable payload copying, and installed-context
launcher templates. These are internal packaging primitives. L1 does not yet expose `make install`,
`make list-installed`, `make dist`, or `make smoke-dist`. Stage 2 construction also accepts a private build-info overlay
with generated package provenance and native installed-state validation. Self-hosted package assembly and artifact
acceptance remain in [l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][productization].

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
metadata. The guard fixtures use real native code and run through `test-productization`; platform-specific cases skip
explicitly when their host prerequisites are absent.

[installation]: ../../compiler/stage1_l0/support/installation.h
[inventory]: ../../scripts/productization_inventory.py
[launchers]: ../../scripts/productization_launchers.py
[productization]: ../../work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md
[provenance]: ../../scripts/productization_provenance.py
[stage2-builder]: ../../scripts/build_stage2_l1c.py
