# L1 Productization Inventory Helpers

Version: 2026-10-06

The first productization milestone implements prefix ownership, recoverable payload copying, and installed-context
launcher templates. These are internal packaging primitives. L1 does not yet expose `make install`,
`make list-installed`, `make dist`, or `make smoke-dist`. The native installed-state guard, package provenance overlay,
self-hosted package construction, and artifact acceptance remain in
[l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][productization].

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
| `provenance`      | Nonempty JSON object supplied by the package builder; all values must be finite JSON values                         |
| `entries`         | Intended owned files and aliases                                                                                    |

An incomplete record additionally requires `previous_entries`, retaining the ownership of the previous installation and
any interrupted installation attempts. Both entry lists obey the same validation rules. The future builder owns the
detailed source/bootstrap/build provenance fields; the inventory helper does not invent preparation identities or native
cache keys.

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
Regular source files receive portable read or executable modes; aliases preserve their relative targets. Windows payload
builders use ordinary file copies for launcher aliases. POSIX verification checks recorded modes; Windows verification
checks bytes and file type without treating POSIX mode bits as native permissions.

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

The templates select prefix context; native installation-state validation is still pending. Shell probes exercise
context and argument/exit-code behavior without claiming real installed-compiler acceptance.

## Validation

From `l1/`, run `make test-productization`. The fixture suite covers metadata/path rejection, collisions, preservation
of unrelated files, controlled reinstalls, interrupted metadata/payload writes and deletion, digest failure, ownership
recovery, relocation with spaces, and launcher/activation behavior. It is included in `make test` and
`make test-extended`. Native `cmd.exe` cases run on Windows; unavailable host shells are reported as skipped.

[inventory]: ../../scripts/productization_inventory.py
[launchers]: ../../scripts/productization_launchers.py
[productization]: ../../work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md
