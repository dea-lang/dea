# ADR-0042: Self-Hosted Toolchain Delivery

- Decision date: 2026-10-09
- Last edited: 2026-10-09
- Status: Accepted

## Context

L1 needs an independently usable toolchain outside its development checkout. The delivered compiler must agree with its
semantic inputs, survive relocation, and prepare native support without writing into the installation. Installation,
archive creation, and later release automation need one ownership and artifact identity contract. Native artifact
acceptance has passed on Linux x86_64, macOS Intel/ARM, and Windows UCRT64, including fresh-host verification without
checkout or bootstrap compilers, as recorded in the productization plan.

## Decision

### Delivery stage and immutable inputs

Ship only the self-built L1 Stage 2 compiler, selected by installed `l1c`, through `make install PREFIX=...` and
`make dist`. The explicit construction chain and bootstrap selection belong to
[l1/docs/decisions/0001-bootstrap-adaptation-strategy.md][bootstrap]. Packaging preserves development compilers and
selected aliases. Package version defaults to `dev`; maturity remains `development` even for release-shaped version
strings. Delivery readiness does not establish stable-language maturity or an active hosted release line.

The curated relocatable prefix contains the compiler, launchers and activation scripts, verified bundled semantic
interfaces, public headers, stdlib/runtime rebuild inputs and symbol manifests, installation metadata, notices, guides,
and a smoke program. It excludes bootstrap compilers, compiler implementation sources/tests, native support profiles,
caches, and retained build outputs. Native support is derived into a separate selected writable cache under
[l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md][semantic-inputs]. Preparation identity
and reuse remain governed by
[l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][preparation-identity] and
[l1/docs/decisions/0040-warm-preparation-semantic-validation-reuse.md][preparation-reuse].

Direct installation may omit generated references. Every distribution requires a verified Stage 2 HTML/full indexed PDF
bundle from the same source and package version under the contract in
[l1/docs/decisions/0041-stage-separated-source-references.md][references]. Consumers snapshot and verify that bundle;
installation and packaging do not generate docs. Installed references live under `share/doc/dea/l1/autodocs/stage2/`.

### Prefix ownership and installed startup

`share/dea/l1/install-manifest.json` is the schema-1 ownership authority. Canonical prefix-relative paths enumerate
owned regular files with digests and portable modes, closed relative aliases, and the manifest itself without a
self-digest. Preflight rejects unsafe paths, input overlap, malformed prior ownership, and unowned collisions. Reinstall
preserves unrelated files and removes obsolete owned entries.

Installation publishes incomplete metadata retaining previous and intended ownership before copying payload files. Only
full payload verification permits atomic publication of complete metadata. Retry recovers ownership after process
interruption; payload copying is not an atomic upgrade or rollback transaction. Installation requires external
serialization against consumers and other installers and makes no power-loss durability guarantee.
`make list-installed PREFIX=...` reads only complete inventory and prints sorted owned paths without build or cache
prerequisites.

A private generated build-info overlay marks the delivered native compiler as installed. Before CLI parsing, it derives
the physical prefix from its executable in `bin/` and validates installation metadata, including for help/version.
Missing, unreadable, malformed, or incomplete state fails with `L1C-9515` and status 1; it never falls back to
repository mode. Startup validates metadata structure without scanning payload digests or invoking external tooling.
Install and artifact verification own full content checks. Ordinary repository-mode compilers retain their existing
startup behavior.

Installed native startup and launchers select the physical prefix as `L1_HOME` and clear inherited `L1_BUILD_DIR`, while
preserving explicit system/runtime/compiler/cache selectors. Activation moves and deduplicates the selected `bin` entry
in `PATH`; Windows compiler wrappers preserve caller environment and native exit status. Installed compiler operations
treat prefix bytes as immutable inputs.

### Provenance and archive handoff

Capture one provenance snapshot for the private compiler overlay, native version identity, standalone `VERSION`,
inventory, and distribution result. Record source identity/cleanliness, the explicit bootstrap chain, effective selected
native compiler/options, UTC build time, host and package identity, and shipped preparation-input digests. Outside Git,
source identity is explicitly unknown. Record selected build options rather than the whole process environment; recorded
paths are informational and never installed lookup roots. Packaging neither invents cache identities nor modifies
checked-in build-info modules.

Archives contain exactly one `dea-l1/` root and use `dea-l1-lang_<version>_<os>-<arch>_<YYYYMMDD-HHMMSS>.tar.gz` on
Linux/macOS or `.zip` on Windows UCRT64. Validate a complete extraction round trip before atomic archive publication;
reject an existing archive name. Optional schema-1 `DIST_RESULT` identifies this invocation's archive with its absolute
path, size/digest, package identity/provenance, and docs-bundle digest/source identity. After destination preflight,
invalidate any previous result before input validation and construction. Publish the new result atomically only after
the archive and scratch cleanup succeed. A failure may leave a verified archive but must not leave a stale success
result.

Consumers require command success, read their unique result, verify its archive digest, and pass the exact artifact to
verification. They must not select archives by globbing or parsing build logs. The field-level inventory/result schemas
and destination/concurrency rules live in [l1/docs/reference/productization-inventory.md][inventory].

### Standalone artifact verification

`make smoke-dist ARCHIVE=...` verifies the exact archive without rebuilding. Before compiler invocation, its Python
harness rejects unsafe archive members and checks exact inventory membership, payload bytes/modes, provenance,
semantic/rebuild inputs, and offline documentation. It relocates the prefix to a path containing spaces and runs from an
unrelated directory with private cache and controlled host tools. Coverage includes native/launcher identity, semantic
commands without compiler tools, compile-only output, standalone linking without `-I`, build/run, cold and warm
preparation, no-auto reuse, checking/trace configurations, forced preparation, and cache disposal. POSIX execution uses
a read-only prefix; every host verifies unchanged payload bytes. Windows semantic checks retain only required UCRT64
runtime DLLs on the isolated PATH, with unavailable C compiler selectors.

`make test-productization-acceptance` retains the exact archive, schema-1 result, portable standard-library-only Python
harness, and a success report written only after verification. Its build and verify phases allow transport to a fresh
matching native host; the verifier locates the archive by basename in the evidence directory and checks its digest.
Fresh verification jobs in `L1 Productization Acceptance` receive no source checkout or bootstrap artifacts. A combined
local run or ordinary `test-ci` result does not establish checkout independence or replace this separate artifact gate.

Installed compiler startup and preparation need no Python, Make, or bootstrap compiler. The artifact harness itself
requires Python; native output and preparation require compatible host C/linker tools. Supported archive hosts are Linux
x86_64, macOS x86_64/arm64, and Windows UCRT64 x86_64.

## Rationale

One self-built stage, immutable semantic inputs, and explicit provenance make the delivered compiler's identity
independent of development aliases. Inventory-owned recovery preserves unrelated prefix contents while detecting
interrupted installations. Native startup enforces the installed boundary without interpreter dependencies or full
payload hashing on each command. Exact archive/result verification gives later workflow consumers a reproducible
handoff, and fresh-host acceptance demonstrates independence that checkout-local tests cannot establish.

## Consequences

- A compiler-only direct prefix is valid; every distribution includes matching offline Stage 2 references.
- Relocation and read-only use preserve the installed payload; native configuration changes affect the selected cache.
- Inventory recovery requires serialized installation. Concurrent upgrades, uninstall/package-manager integration, and
  power-loss durability remain outside this contract.
- Integrity digests and recorded provenance describe and verify payload agreement; they do not establish publisher
  authentication or reproducible archive bytes across builds.
- Hosted release/snapshot workflows and docs publication consume these interfaces through their separate plan and
  authorization gates. This ADR records the delivery decision while documentation handoff and plan closure remain open.

## Related Plans

- [l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][productization]: implemented delivery and native
  acceptance; documentation handoff and closure remain active.
- [l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md][autodocs]: offline reference input
  contract.

## Current Docs

- [l1/docs/reference/productization-inventory.md][inventory]
- [l1/docs/reference/stdlib-preparation.md][preparation]
- [l1/docs/user/toolchain.md][toolchain]
- [l1/README.md][readme]
- [docs/specs/compiler/cli-contract.md][cli]
- [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]

[autodocs]: ../../work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md
[bootstrap]: 0001-bootstrap-adaptation-strategy.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[diagnostics]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[inventory]: ../reference/productization-inventory.md
[preparation]: ../reference/stdlib-preparation.md
[preparation-identity]: 0039-native-preparation-identity-and-reuse-boundary.md
[preparation-reuse]: 0040-warm-preparation-semantic-validation-reuse.md
[productization]: ../../work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md
[readme]: ../../README.md
[references]: 0041-stage-separated-source-references.md
[semantic-inputs]: 0038-bundled-semantic-inputs-and-local-native-preparation.md
[toolchain]: ../user/toolchain.md
