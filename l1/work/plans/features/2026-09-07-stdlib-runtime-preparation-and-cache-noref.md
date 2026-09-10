# Feature Plan

## L1 standalone-link discovery and stdlib/runtime preparation and caching

- Date: 2026-09-07
- Last edited: 2026-09-10
- Status: Draft
- Title: L1 standalone-link discovery and stdlib/runtime preparation and caching
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Compiler driver / standard library / runtime / bootstrap / standalone linking / module graph / interface
  discovery
- Modules:
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/src/cli_args/`
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/interface_emitter.l0`
  - `l1/compiler/stage1_l0/src/compile_driver/`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/link_driver/`
  - `l1/compiler/stage1_l0/src/module_graph.l0`
  - `l1/compiler/stage1_l0/src/module_interface.l0`
  - `l1/compiler/stage1_l0/src/interface_fingerprint.l0`
  - `l1/compiler/stage1_l0/src/compiler_filesystem.l0`
  - `l1/compiler/shared/l1/stdlib/`
  - `l1/compiler/shared/runtime/`
  - `l1/Makefile`
  - `l1/scripts/build_stage1_l1c.py`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/link_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/module_graph_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_fingerprint_test.l0`
  - `l1/compiler/stage1_l0/tests/fixtures/separate_compilation/`
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_support_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_build_config_test.py`
  - `l1/compiler/stage1_l0/tests/compiler_runtime_build_env_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_compile_only_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_build_run_multi_cu_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_link_set_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_help_output_test.py`
- Related:
  - [l1/work/plans/features/closed/2026-09-07-standalone-link-interface-discovery-noref.md][link-discovery] (superseded)
  - [l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][bootstrap-productization]
  - [docs/specs/compiler/cli-contract.md][cli-contract]
  - [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]
  - [l1/docs/reference/separate-compilation.md][separate-compilation]
  - [l1/docs/reference/c-backend-design.md][backend]
  - [l1/docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md][interface-authority]
  - [l1/docs/decisions/0036-ordered-external-link-inputs-and-cli-only-dependency-ownership.md][external-inputs]
- Repro: `l1c --compile l1/examples/demo.l1 -o build/modules/demo.o` after bootstrap without manually prepared stdlib
  interfaces.

## Summary

Bootstrap should prepare reusable stdlib module pairs and the matching runtime after building `l1c`. Ordinary compiler
commands should automatically prepare missing managed artifacts and then continue. Explicit preparation remains useful
for prewarming, forced rebuilding, and controlled build environments.

Separate semantic interface availability from native artifact compatibility. A change of external C compiler can reuse
matching `.l1m` interfaces while selecting or preparing different native objects and runtime inputs. Preparing those
inputs does not rebuild application or third-party objects supplied by the caller.

Managed stdlib discovery is enabled by default, independently of `-I`. This is the authoritative phased plan for
interface-assisted provider discovery and the preparation/cache service. It absorbs the unimplemented scope of
[l1/work/plans/features/closed/2026-09-07-standalone-link-interface-discovery-noref.md][link-discovery]; that historical
plan is closed only as superseded, not as implemented.

Implement interface discovery with caller-prepared fixtures first, then the preparation/cache service, then
managed-provider integration. All phases share one integrated acceptance and closure gate. Keep the reusable module
contract as a verified `.l1m` interface paired with an opaque sibling `.o`, and link only the required dependency
closure.

## Current State

- `--link` rejects `-I` with `L1C-2031`.
- The caller currently supplies the complete set of Dea objects explicitly, including required stdlib providers.
- The linker verifies sibling interfaces, module identities, fingerprints, entry selection, lifecycle ordering, and
  `require`/`link` provenance. Native objects remain opaque caller-trusted inputs.
- Foreign objects and external libraries are explicitly owned by the CLI's ordered native-input stream.
- Bootstrap builds the compiler and runtime support but does not prepare reusable stdlib `.o`/`.l1m` pairs.
- Build/run compile a source dependency closure in a private workspace; their temporary module artifacts are not a
  reusable stdlib cache.
- Compile-only requires verified interfaces for non-virtual imports rather than falling back to their sources.
- Stdlib source roots and explicit interface roots are separate discovery inputs.
- Native runtime selection already distinguishes checking/trace variants and TinyCC compatibility objects.
- L1 remains bootstrap-only. Its installed payload contract must be coordinated with the existing productization plan;
  this feature does not itself implement an installer or distribution workflow.

## Defaults Chosen

### Standalone-link interface discovery

With matching managed stdlib/runtime support, a program whose remaining dependencies are bundled modules links without
an interface-path option:

```sh
l1c --link build/modules/demo.o -o demo
```

The linker reads `demo.l1m`, discovers the required bundled providers, and uses matching installed or cached artifacts.
Missing managed support is prepared automatically unless preparation has been disabled. Project and third-party
dependencies still require explicit objects or additional interface roots:

```sh
l1c --link build/modules/demo.o -I build/modules -o demo
```

These examples describe planned behavior, not currently available CLI capabilities.

1. Register and validate all explicitly supplied Dea objects before resolving missing providers. Preserve their original
   paths and their authority over discovered providers. Duplicate explicit identities remain errors.
2. Follow verified `import module` records recursively for non-virtual dependencies. Search for missing providers in
   explicit `-I` roots in declaration order, then in the matching managed stdlib root when enabled.
3. Managed discovery is limited to the bundled stdlib/system providers. With no `-I`, explicit objects and the managed
   stdlib remain available; arbitrary project directories are not implicitly searched.
4. Treat the first selected interface as authoritative and require its sibling object. Invalid interfaces, missing
   sibling objects, identity failures, or fingerprint mismatches fail without searching for a replacement in a later
   root or the cache.
5. For managed stdlib artifacts, finish any permitted preparation before selecting complete provider pairs. Automatic
   preparation cannot repair or replace an invalid explicitly selected provider.
6. Discover each dependency once. Do not add unrelated cached modules. `require` and `link` expectations remain semantic
   checks; they do not independently introduce objects or lifecycle edges.

### Ordering and validation

Insert discovered objects in dependency order immediately before the first explicit root needing them. Preserve relative
order among all explicit operands, including foreign objects and native-library controls. Retain existing entry
selection, duplicate-identity checks, lifecycle ordering, cycle detection, fingerprint validation, and `require`/`link`
reachability and provenance rules.

Keep foreign objects, native libraries, their search paths, rpaths, and raw link arguments explicit. Native object bytes
remain opaque. No `.l1m` format or object ABI change is required.

The link driver consumes the same once-per-command native preparation context as runtime selection. Toolchain discovery,
identity memo validation, cache-key construction, artifact validation, and maintenance belong to the shared
preparation/cache service below; do not duplicate those algorithms in provider discovery. Apply its identity-validation
performance targets and instrumented warm-path requirements. Finish any permitted managed preparation and integrity
validation before exposing complete provider pairs. Only required providers enter the link set even when preparation
builds a complete stdlib configuration.

### Preparation interface and mode boundaries

Add a preparation mode with no positional source target. Reuse the existing C compiler, C options, trace, and checking
selectors:

```sh
l1c --prepare-stdlib --c-compiler gcc
l1c --prepare-stdlib --c-compiler gcc --force
l1c --prepare-stdlib --c-compiler gcc --stdlib-cache _cache/dea
```

- Bootstrap, explicit preparation, and automatic preparation call the same internal operation.
- Native preparation builds all bundled `std.*` and `sys.*` modules in dependency order, plus the matching runtime
  variant. Preparation uses its own dependency interfaces and cannot recursively trigger default-cache preparation.
- Ordinary preparation reuses a complete matching configuration. `--force` is valid only with explicit preparation and
  rebuilds the selected configuration in place.
- Build/run and standalone linking automatically prepare missing required managed native support, then resume the
  original command.
- Compile-only and generated-C modes use matching interfaces and headers without requiring native provider objects.
  Missing managed interfaces can be regenerated through the frontend without invoking a C compiler.
- Source inspection and interface-emission modes retain their existing ability to operate without a C toolchain.
- Add `--no-auto-prepare`: allow managed discovery and reuse, but fail on a miss with the exact preparation command.
- Add `--no-stdlib-cache`: disable managed artifact discovery and preparation for caller-managed operation.
- Cache controls apply to the modes that consume managed artifacts. Disabling automatic preparation or managed-cache use
  is incompatible with explicitly requesting preparation.

Automatic preparation covers bundled stdlib/runtime inputs. Explicit objects and ordered `-I` providers precede managed
stdlib providers; `-I` is not required to activate managed discovery. Custom system roots and runtime overrides retain
their authority. Invalid explicitly selected providers remain errors rather than triggers to replace them from the
cache. Application and third-party dependency sources are not implicitly compiled by compile-only or standalone link.

### Artifact identity and selection

- Keep semantic interface identity separate from native configuration identity. Native profiles contain canonical
  `.o`/`.l1m` pairs, matching runtime headers, and runtime native inputs.
- Identify Dea inputs by content, including private stdlib implementation changes, runtime sources/headers, and the Dea
  compiler build. Public interface fingerprints alone are insufficient cache identities.
- A compiler implementation fingerprint identifies compiler contents and the implementation components discovered by its
  supported toolchain adapter. Retain compiler family and full version/build information as readable metadata; neither
  is sufficient for equality, including when different compiler contents report the same version.
- A preparation fingerprint is a versioned hash of Dea compiler/source inputs, compiler implementation identity,
  effective target, ordered effective native options, SDK/sysroot and relevant dependency inputs, and trace/checking
  settings. Include fingerprint-schema and adapter revisions so changed identity rules invalidate earlier records.
- Effective target includes architecture, OS/object format, ABI, and required CPU features. Host-dependent options such
  as `-march=native` contribute their resolved meaning rather than only their literal spelling.
- Compiler paths are discovery inputs, not substitutes for content identity. Preserve invocation aliases and account for
  path-dependent component selection and behavior in the preparation fingerprint.
- Use exact preparation matching. Different compiler implementations select separate native entries even when their ABIs
  are compatible, including across major releases or between minor releases. This is a reuse policy, not a general proof
  that differing configurations are ABI-incompatible. Do not introduce an ABI-compatibility inference engine.
- Each supported toolchain adapter documents its component discovery, selection inputs, and detection limits. Cover
  existing GCC, Clang/Apple Clang, and TinyCC workflows; this feature does not add MSVC support.
- Opaque wrappers and undeclared external toolchain changes retain forced preparation and caller-managed artifacts as
  recovery paths. Do not claim complete identity detection for unsupported arrangements or add an identity-override CLI.
- Retain different configurations so switching back reuses prior preparation. Do not add general project-output caching,
  physical interface deduplication machinery, or automatic cache pruning in this plan.

### Machine-local identity memo and fast validation

Keep a machine-local identity memo separate from the potentially shared artifact cache. The memo records discovered
components, remembered content digests, and the local metadata used to validate those digests. Shared artifact selection
uses content/configuration fingerprints; another machine's paths, file identities, or timestamps never establish a local
memo hit. Selecting a shared artifact root does not make the identity memo portable.

For each native-consuming command:

1. Resolve compiler selection, effective options, relevant environment, and platform selection.
2. Load the local identity record and validate its discovery dependencies, including invocation aliases and relevant
   search/configuration changes. Validating yesterday's component files is insufficient if today's selection would find
   a different component or an earlier search-path candidate.
3. Rediscover components when selection dependencies change; otherwise reuse the recorded component inventory.
4. Reuse each remembered content digest when file identity, size, and high-resolution modification/change timestamps
   match. Hash new or changed components and check that their metadata did not change during hashing. Do not accept a
   digest from an unstable read.
5. Resolve effective target requirements, including native CPU features, and construct the preparation fingerprint.
6. Select matching installed/cached artifacts or invoke preparation under the existing policy.

Resolve the native preparation context once per command and pass it through preparation and provider selection. Use
native metadata operations and streaming SHA-256; avoid shell hashing commands and per-module toolchain probes. Where
selection requires a platform resolver query, include it in identity validation rather than trusting stale discovery.
Compiler probes must have bounded execution and captured output. Probe failures must not authorize stale reuse.

A missing or invalid memo triggers recomputation; validate memo records before reuse. Explicit `--force` bypasses
remembered discovery and digests as well as rebuilding artifacts. Changes that preserve all checked metadata remain an
explicit detection limitation; forced preparation is recovery, not automatic detection. Concurrent toolchain replacement
is outside the supported preparation contract. Track relevant SDK/header dependencies and search changes without
recursively scanning the entire SDK on every invocation.

### Identity-validation performance

Measure identity validation separately from full artifact validation and preparation. On designated local reference
machines, target under 10 ms p95 for warm direct-toolchain identity validation and under 100 ms p95 when warm validation
requires platform resolver queries. Unchanged warm validation performs no compiler-binary content reads, no recursive
SDK scans, and no repeated probes per module.

Record cold-discovery costs separately, including toolchain size and benchmark environment. A local feasibility
measurement on 2026-09-09 hashed a 272 MB Apple Clang executable in about 1.1 seconds; it is not a portable guarantee or
an end-to-end cache benchmark. Keep reference-machine timing measurements separate from ordinary CI correctness checks;
CI verifies operation counts and behavior rather than enforcing noisy wall-clock thresholds.

### Managed artifact layout and completion manifests

Use the same versioned artifact layout and manifest format for installed prepared artifacts and writable cache entries.
Ownership comes from the root's role, not from a different artifact format. The preparation service owns the layout:

```text
<artifact-root>/v1/
  interfaces/<interface-set-key>/
    manifest.json
    modules/std/io.l1m
    include/dea_rt.h
    include/l1_real.h
  native/<preparation-key>/
    manifest.json
    modules/std/io.l1m
    modules/std/io.o
    include/dea_rt.h
    include/l1_real.h
    lib/libdea_rt.a
    generated/std/io.c
<writable-cache>/v1/locks/
  interfaces-<interface-set-key>.lock
  native-<preparation-key>.lock
<machine-local-state>/v1/identities/
  <local-selection-key>.json
```

Module paths above are examples; include the complete prepared bundled module set. Use full hexadecimal
content/configuration keys, not compiler-version directory names. Interface sets remain independent of native
toolchains. Native profiles contain their own canonical sibling `.l1m`/`.o` pairs and matching headers; use the existing
selected runtime archive name or TinyCC runtime-object layout as appropriate. Retain generated C for the existing
build/run retention contract.

Each `manifest.json` identifies its schema, entry kind and key, records the identity inputs and descriptive compiler
metadata, and inventories required artifacts using relative paths, sizes, and content digests. A native manifest also
identifies its interface set. Hash a defined canonical encoding of identity fields; exclude descriptive metadata and the
output inventory from the preparation key. Artifact digests are validated by the consumer policy below, separately from
compiler-identity validation.

The manifest itself is the completion record. Under the preparation lock, invalidate it before rebuilding, write
artifacts normally, and write the complete manifest last. A missing, malformed, or truncated manifest does not authorize
reuse. This preserves the ordinary-write contract without adding transactions or a second completion flag. Lock-file
existence is not lock ownership; process-lifetime coordination supplies ownership and release on exit.

Identity memos retain local paths, discovery dependencies, component file identities, size, high-resolution timestamps,
and remembered content digests. They remain machine-local even when artifact storage is shared. Local metadata never
establishes a portable artifact identity. Lookup computes a key and opens its directory directly; no global index or
"current compiler" pointer is required.

### Artifact validation and corruption handling

Validate managed artifacts before exposing a provider root or runtime input. Native consumers validate the complete
native profile inventory, including interfaces, objects, runtime inputs, headers, and retained generated C. Modes that
need only interfaces/headers validate the semantic set without resolving a native toolchain or reading native outputs.
The ordinary `.l1m` parsing, semantic fingerprint, and graph checks still run for selected interfaces on every command;
an artifact digest does not replace them. Explicit objects, `-I` providers, and runtime overrides retain their existing
validation and error authority rather than acquiring managed-cache repair behavior.

1. Read and parse the small completion manifest on every lookup. Check its supported schema, kind, key, canonical
   identity digest, required module/runtime roles, unique relative inventory paths, sizes, and SHA-256 digest syntax.
   Reject absolute paths, parent traversal, symlink escapes, and non-regular artifact files. The expected bundled module
   inventory for ordinary matching-key lookup comes from the identified Dea input set; a shortened manifest cannot
   silently declare a partial profile complete.
2. On first use by this machine, or after a manifest change, stream and verify SHA-256 for every inventoried artifact.
   Check file metadata before and after reading and reject unstable reads. Memoize only successful validations in
   machine-local state, keyed by the resolved entry location, manifest-content digest, and validation-schema revision.
3. On warm reuse, reread the manifest and check every inventory file's identity, size, and high-resolution
   modification/change timestamps. Reuse a verified digest only when these match the local validation memo; otherwise
   rehash the changed file. A changed size already invalidates the entry. Do not rescan other cache configurations or
   recursively walk the SDK. Warm artifact validation is measured separately from the compiler-identity time budget.
4. Never trust another host's validation memo, including for installed or shared artifacts. If the filesystem cannot
   supply reliable change metadata, rehash on each use instead of taking the metadata fast path. Missing, corrupt, or
   unwritable local memo state only loses the optimization; it does not authorize an unchecked artifact hit.

Use these outcomes consistently across installed, local, and system roots:

| Entry state                                                                                                                    | Consumer action                                                                                                               |
| ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| No matching key, unsupported schema, or absent/unparseable completion manifest                                                 | Treat as unavailable; continue managed lookup, then prepare on a miss when permitted                                          |
| Supported parsed manifest with inconsistent identity/inventory, missing/unreadable artifact, unstable read, or digest mismatch | Fail with the root, entry, and affected file/reason; do not use a later root or automatically overwrite the completed profile |
| Complete profile with successful integrity validation                                                                          | Reuse, then apply the existing interface and link checks                                                                      |

This separates retryable incomplete preparation from corruption of a completed entry. Before recreating an incomplete
writable entry, acquire its preparation lock and recheck completion. A corrupt completed writable entry is repaired by
explicit `--prepare-stdlib --stdlib-cache <root> --force`, or removed by scoped cleanup followed by normal automatic
preparation. Both maintenance paths retain external serialization against consumers. Installed corruption requires
installation repair or explicit preparation of a matching local profile that takes precedence; compiler commands never
modify the installed payload. With `--no-auto-prepare`, unavailable entries report the exact preparation command;
corruption still reports an integrity failure rather than a preparation-disabled miss.

Preparation hashes the written outputs and validates the full manifest/inventory before reporting success; failed
validation leaves no usable completion manifest. `--force` and `--clean-cache` bypass artifact-validation memos as well
as their other documented work. Metadata-preserving content changes may evade ordinary warm reuse, as with compiler
digest memoization; explicit cleanup rehashes and detects them. Concurrent external modification or corruption of
artifacts is outside the supported consumption contract. These hashes detect accidental corruption; manifests are
trusted managed metadata, not signatures authenticating an untrusted cache writer.

### Minimal on-demand cache cleanup

Implement maintenance in the shared preparation/cache service, not in the standalone-link provider walker:

```sh
l1c --clean-cache
l1c --clean-cache --scrub
l1c --clean-cache --cache-scope system --system-stdlib-cache /shared/dea
l1c --clean-cache --scrub --cache-scope system --system-stdlib-cache /shared/dea
```

- `--clean-cache` inspects managed entries in the selected writable cache on demand. Validate only entries whose schema
  can be established safely and is supported by this cleaner. Preserve unfamiliar schemas and entries whose schema
  cannot be determined safely, including when a damaged manifest prevents classification. Unsupported does not mean
  obsolete: another L1 version may still use that schema.
- Within an established supported schema, remove entries with invalid completion manifests, missing required artifacts,
  or artifact digest mismatches. For every supported complete entry, rehash the entire inventory without trusting
  validation memos; cleanup checks stored artifact integrity rather than comparing its compiler identity with the
  currently selected compiler. Preserve complete entries even when their compiler, architecture, or checking
  configuration differs from the current one.
- When cleaning another Dea configuration, check its stored manifest/inventory structure, role consistency, and all
  artifact digests without requiring its sources or compiler installation or imposing the current bundled module list.
- Local cleanup applies the same schema gate to identity and artifact-validation memos: preserve unfamiliar or
  indeterminate schemas. Within supported schemas, discard invalid identity memos or those whose recorded compiler
  components no longer exist, plus artifact-validation memos whose entries are missing or no longer match their recorded
  manifest. A compiler missing on this machine is not sufficient reason to delete shared native artifacts.
- `--scrub` removes all recognized managed cache entries in the selected scope regardless of schema support or validity.
  Local scrub also clears recognized machine-local identity and artifact-validation memos across schemas; system scrub
  does not clear any machine-local identity or artifact-validation state. Schema-independent recognition of managed data
  remains required; scrub does not claim unrelated files merely because their format is unfamiliar.
- `--cache-scope` accepts `local` or `system`, defaults to `local`, and is valid only with `--clean-cache`. `--scrub` is
  valid only with `--clean-cache`. Cleanup cannot be combined with preparation, compilation, or linking modes and does
  not require a working C compiler or trigger automatic preparation.
- Restrict removal to recognized managed cache data in the selected root. Preserve unrelated files, installed prepared
  artifacts, and coordination infrastructure; do not follow substituted paths outside the selected root.
- Require external serialization against preparation and artifact consumers, as for forced rebuilding. Preparation locks
  alone do not protect a linker already consuming objects. Concurrent cleanup and consumption are not supported.
- Report the selected root and removed/skipped entries through the existing verbosity contract. Permission or I/O errors
  are actionable failures, not reasons to switch roots. A later normal invocation may prepare removed support again.

Do not add timestamps for last use, expiration periods, age-based deletion, usage tracking, automatic pruning, or a
general cache-management subsystem. File timestamps used by the identity memo remain part of fast digest validation;
they are not retention metadata.

### Ordinary writes and preparation coordination

Use ordinary writes and a completion manifest. Invalidate completion before rebuilding and mark success only after the
required artifacts are ready. Failed or interrupted preparation leaves the selected configuration unavailable; a later
invocation may retry.

Serialize preparation per managed artifact set, including shared interface preparation. One process prepares while
others wait, acquire the coordination lock, and recheck completion before doing work. Coordination must release when the
preparing process exits, including abnormal exit. Prepare shared interfaces before acquiring native-configuration
coordination to avoid recursive lock acquisition. Different configurations may prepare independently.

Do not introduce cache transactions, immutable generations, rollback, or reader pinning. Reuse existing per-module
artifact handling unchanged; do not add cache-wide staging. Explicit forced rebuilding remains a maintenance operation
requiring external serialization against consumers. Preservation of its previous contents and concurrent consumption
during forced rebuilding are not guaranteed.

### Output and failures

Send preparation messages to stderr, preserving program output and compiler output on stdout. Use the existing counted
verbosity options:

| Verbosity    | Preparation output                                                                                                                                |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Default      | Announce each actual preparation or rebuild, identifying compiler and target; report completion or failure. Successful cache reuse remains quiet. |
| `-v` / `-vv` | Add configuration selection, reuse/rebuild reasons, cache paths, module progress, and compiler commands.                                          |
| `-vvv`       | Add detailed identity inputs, dependency resolution, and cache-validation decisions.                                                              |

Describe a new configuration rather than only a new target: changing compiler, options, or checking mode may require
preparation without changing target architecture. A normal miss produces progress rather than an error. Missing
compilers, unsupported configurations, unavailable source inputs, unwritable caches, and compilation failures terminate
the original command with actionable diagnostics. Preserve relevant host-compiler errors at every verbosity level and do
not retry indefinitely.

### Bootstrap and installed ownership

| Storage class                | Purpose                                                                               | Read | Prepare/write                    | Clean/scrub                     |
| ---------------------------- | ------------------------------------------------------------------------------------- | ---- | -------------------------------- | ------------------------------- |
| Local cache                  | Per-user or explicitly selected development cache; writable and disposable            | Yes  | Yes                              | Yes, with local scope           |
| System cache                 | Configured machine-wide/shared cache; writable and disposable with appropriate access | Yes  | Yes, when selected and permitted | Yes, with explicit system scope |
| Installed prepared artifacts | Bundled compiler installation payload                                                 | Yes  | No                               | Never                           |

Use the term "installed prepared artifacts" for bundled files even when their layout matches cache entries. System scope
never means the installed payload, and cleanup is not an installation-management operation. A system cache is optional;
selecting it must not silently clean a local cache or an installation when its root is unavailable or access is denied.
Do not automatically elevate privileges.

Bootstrap prewarms the default configuration after building `l1c`. Automatic preparation makes prewarming an
optimization rather than a prerequisite for correctness.

Local writable-root precedence is `--stdlib-cache`, then `L1_STDLIB_CACHE`, then the environment default:

| Environment                   | Default writable root                                       |
| ----------------------------- | ----------------------------------------------------------- |
| Repository development        | `$L1_BUILD_DIR/cache`                                       |
| Installed compiler on Linux   | `$XDG_CACHE_HOME/dea/l1`, falling back to `~/.cache/dea/l1` |
| Installed compiler on macOS   | `~/Library/Caches/dea/l1`                                   |
| Installed compiler on Windows | Local AppData under `Dea\L1\Cache`                          |

Resolve relative overrides against the invocation directory. An explicit writable-cache selection must not silently fall
back to another writable cache.

Configure one optional system/shared root with `--system-stdlib-cache PATH`, then `L1_SYSTEM_STDLIB_CACHE`; absent or
empty environment configuration disables that root. There is no implicit machine-wide directory or system-cache
creation. Both root options are valid in managed-artifact-consuming modes, explicit preparation, and cleanup. They
identify writable caches, never an installed payload. `--stdlib-cache` always overrides the local root; it does not
replace or retarget the configured system root. A caller may deliberately point the selected local write root at a
shared directory when prewarming it.

Managed lookup order is selected local cache, installed prepared artifacts at the active prefix's `prepared/` root when
installed context exists, then the configured system cache. Explicit objects and ordered `-I` roots precede all three.
Check only the requested exact interface/native key, apply the artifact-validation policy at each candidate, and select
an entire semantic set or native profile from one root rather than mixing a profile's modules and runtime across roots.
Deduplicate canonical aliases while preserving the first position. Root choices never enter portable content identity.
`--no-stdlib-cache` disables all three managed provider sources and automatic preparation.

Automatic preparation after a managed miss always writes to the selected local root, even if the system root is
writable. Explicit `--prepare-stdlib` and bootstrap prewarming populate that same selected write root, reusing only a
valid matching entry already there; an installed/system hit does not satisfy an explicit request to populate it.
`--force` rebuilds only that destination. To prewarm a system cache, use
`l1c --prepare-stdlib --stdlib-cache <system-root>` explicitly. This requires ordinary filesystem write access and never
automatically elevates privileges or writes to the installed payload.

For cleanup, local scope uses the selected local root; system scope requires `--system-stdlib-cache` or
`L1_SYSTEM_STDLIB_CACHE`. Reject an explicit `--stdlib-cache` together with system cleanup scope rather than silently
ignoring it; `L1_STDLIB_CACHE` does not select the system cleanup destination. A missing configured system cleanup root
or denied access fails without touching another root. Ordinary lookup treats a nonexistent cache directory as a miss; an
existing reached root that is unreadable or not a directory is a configuration error. Failure to create/write the
selected preparation destination terminates the command without choosing another destination. Root checks are lazy: a
successful earlier managed hit does not require access to an unused later root.

Reject any writable destination that equals, contains, or lies inside the active installed payload; compare resolved
paths so a cache override cannot turn bundled files into cleanup targets. Keep machine-local identity and artifact
validation state independent of both root overrides: use `$XDG_CACHE_HOME/dea/l1-state` (falling back to
`~/.cache/dea/l1-state`) on Linux, `~/Library/Caches/dea/l1-state` on macOS, and Local AppData under `Dea\L1\State` on
Windows, with versioned `identities/` and `artifacts/` memo directories. These are validation memos, not portable
prepared providers. Namespace both memo classes by machine identity and reject records from another host, even if a user
cache directory is mounted on several machines. Failure to persist them uses fresh checks rather than relocating them
into a shared artifact root.

The installed payload contract includes read-only interfaces, default prepared native support, and the source inputs
required for rebuilding. Reuse shipped native support only when its configuration matches; otherwise prepare into the
selected writable cache. Local variants remain separate from the installed default, so clearing a writable cache does
not remove installed support artifacts.

Coordinate this contract with
[l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][bootstrap-productization]. Installers,
distribution creation, and release publication remain outside this plan. Preserve build/run generated-C retention and
cross-mode C-byte identity when using cached providers.

## Compatibility

Existing complete explicit link commands remain valid and preserve explicit-provider precedence and native-input order.
An invocation without `-I` may now succeed when its missing providers are bundled stdlib modules; requiring those
modules to be explicitly listed is intentionally relaxed. A missing project or third-party provider still fails without
an explicit object or suitable `-I` root.

The new managed-preparation exception is confined to compiler-owned stdlib/runtime support. Document this exception in
the standalone-link mode contract while preserving the separate-compilation boundary for user dependencies.

## Implementation Phases

1. Implement interface-assisted discovery with caller-prepared fixtures: permit `-I` with standalone link, update help
   and mode validation, register explicit providers before recursive lookup, and preserve authoritative ordered lookup,
   dependency deduplication, object insertion, and existing semantic checks. Exercise `link_driver/` inputs, model,
   plan, provenance, and toolchain integration without depending on the managed cache.
2. Implement preparation identity, manifests, storage, and validation: semantic/native identities, supported toolchain
   adapters, versioned fingerprints, root configuration and lookup order, a single selected write destination,
   layout/completion manifests, process-lifetime coordination, native metadata/digest support, bounded probes, and
   machine-local identity/artifact-validation memos. Cover cold/warm integrity checks and corruption authority, using
   installed-root fixtures independently of productization.
3. Implement the shared explicit preparation operation and manual CLI, including forced refresh and corruption recovery.
   Reuse frontend interface emission, per-module compilation, runtime variants, and TinyCC handling; retain generated C.
   Keep preparation inputs separate from ordinary provider discovery and prevent recursive automatic preparation.
4. Implement local/system cleanup for established supported schemas and preserve unfamiliar or indeterminate schemas.
   Use full on-demand digest verification; scrub spans all recognized managed schemas. Keep scoped deletion under
   external serialization, installed files and unrelated data outside maintenance, and no expiration or usage tracking.
5. Integrate automatic preparation and managed providers into build, run, and standalone linking, plus bootstrap
   prewarming and opt-outs. Pass one resolved preparation context through managed stdlib/runtime selection, preserve
   semantic-only operation without a C toolchain and generated-C contracts, and implement progress and actionable errors
   at the agreed verbosity levels. Default stdlib discovery needs no `-I`; explicit providers retain precedence.
6. Update the shared CLI contract and diagnostic catalog plus L1 bootstrap, separate-compilation, and runtime docs.
   Document no-`-I` stdlib linking and additional provider discovery through `-I`. Run integrated acceptance for all
   phases, create or amend the specified ADRs, and only then close this plan. Define the packaging handoff without
   depending on installation/distribution implementation; preserve its separate publication authorization boundaries.

## ADR Impact

- Decision: Discover managed stdlib providers by default and use explicit interface roots for additional standalone-link
  providers.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md`
  - Rationale: Extend provider discovery while retaining verified interface authority and opaque native inputs. Managed
    stdlib discovery works without `-I`; explicit search roots extend lookup. Preserve ADR-0036's external-input
    ownership and encounter-order contract.
- Decision: Automatically prepare managed stdlib/runtime configurations with manual controls and simple cache
  coordination.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Preparation defaults, cache ownership, verbosity, and concurrency behavior establish a durable toolchain
    contract.
- Decision: Select exact preparation fingerprints and accelerate content-digest reuse through a machine-local,
  metadata-validated identity memo.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Compiler implementation identity, effective target selection, adapter/schema revisions, and the explicit
    metadata-detection limits define when managed native artifacts may be reused locally or across machines.
- Decision: Select matching prepared runtime inputs across compiler configurations.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0027-runtime-archive-and-trace-selection-boundary.md`
  - Rationale: Extend runtime selection while preserving checking/trace variants and TinyCC compatibility handling.
- Decision: Reuse prepared bundled providers within build/run orchestration.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0033-multi-compilation-unit-build-and-run-pipeline.md`
  - Rationale: Record managed-provider reuse while preserving application compilation and generated-artifact contracts.
- Decision: Share a versioned manifest-based artifact layout across prepared roots while retaining machine-local
  identity memos and root-specific ownership.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Installed and cached artifacts share consumption and completion rules, while portable artifact identity
    remains separate from local validation state and installation ownership. Cold digest verification, warm metadata
    validation, and explicit corruption repair establish the integrity boundary.
- Decision: Provide explicit schema/validity cleanup and exhaustive scrub for local or system writable caches.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Scoped deletion, installed-payload protection, external serialization, and the exclusion of expiration
    establish the maintenance boundary for the shared preparation service. Preserving unfamiliar and indeterminate
    schemas during normal cleanup permits multiple L1 versions to share storage; explicit scrub remains exhaustive
    across recognized managed schemas.
- Decision: Search managed local, installed, and configured system roots in order while preparing only into the selected
  local write root.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Separate lookup, explicit shared-cache prewarming, scoped maintenance, and immutable installation
    ownership so cache selection and failures have one deterministic authority.

## Diagnostic Planning

Provisionally reserve `L1C-2150` through `L1C-2169` for the new preparation, coordination, and managed-cache diagnostic
area. Include preparation-disabled misses, unusable cache/source inputs, coordination failures, and failed preparation
where existing lower-level diagnostics do not already describe the error. Include root/scope configuration failures,
artifact integrity failures, cleanup permission/removal failures, and invalid maintenance-mode combinations; reuse
existing CLI diagnostics when appropriate. Cleanup removal of invalid entries is a maintenance result, not a compilation
failure. Normal preparation progress is informational.

Recheck the range against [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] at implementation time before
assigning final codes. If any numbers have been used or reserved elsewhere, choose another available block then. Update
existing CLI mode-validation diagnostics where the new preparation mode broadens an option's valid modes.

Reuse existing interface, missing-object/provider, identity, fingerprint, cycle, entry, and provenance diagnostics.
Update `L1C-2031` to accept `--interface-path` in standalone-link mode. Discovery uses the same preparation diagnostic
area rather than reserving a second cache block. A default managed miss that can be prepared is progress, not a
missing-provider error. An invalid earlier explicit provider remains an error even when a usable managed provider
exists.

## Non-Goals

- Implementing application or third-party source dependency builds inside compile-only or standalone link.
- Rebuilding or proving the native compatibility of caller-supplied objects, or relaxing interface authority.
- Automatically discovering foreign objects or native libraries, searching arbitrary project directories without an
  explicit root, or linking every module in an interface root or cache.
- Implementing separate toolchain-detection, cache, or preparation algorithms in the link driver.
- Adding a general build cache, age-based expiration, usage tracking, automatic pruning, or transactional cache
  publication. Explicit schema/integrity cleanup and scrub are included.
- Guaranteeing concurrent consumption during an explicit forced rebuild or cleanup/scrub.
- Changing the `.l1m` format or object ABI.
- Implementing installation, distribution, release, or publication workflows.

## Verification Criteria

01. Fresh bootstrap followed by demo compilation succeeds without manually preparing stdlib modules.

02. Cold-cache build/run and standalone linking automatically prepare required support and finish successfully; warm
    invocations reuse artifacts quietly. Standalone stdlib discovery works both with and without `-I`.

03. Supported Clang/GCC/TinyCC configuration switches preserve interface reuse, select matching runtime inputs, and
    reuse previous native configurations after switching back.

04. Source, private implementation, header, compiler, options, SDK configuration, and checking/trace changes invalidate
    the appropriate artifacts. Forced preparation repairs an otherwise undetected external toolchain change.

05. Compile-only and generated-C modes need no native provider objects; source-only and interface-emission modes retain
    their no-C-toolchain behavior. Generated-C retention and cross-mode C-byte identity remain covered.

06. `--no-auto-prepare` succeeds on hits and reports the exact preparation command on misses. `--no-stdlib-cache`
    disables managed discovery/preparation while explicit-provider workflows remain usable. Invalid CLI combinations are
    rejected.

07. Default, INFO, and DEBUG output follows the contract, including visible host-compiler errors, and does not
    contaminate stdout or a program's output under `--run`.

08. Failed or interrupted preparation leaves no usable completion marker. A later invocation repairs the configuration;
    no rollback or previous-generation preservation is required.

09. Concurrent cold requests prepare one shared artifact set and both finish; process exit releases coordination. Shared
    interface preparation does not deadlock with native preparation, and different configurations can proceed
    independently.

10. Read-only installed payload fixtures, writable user defaults, project-local overrides, and relative-root resolution
    work. Clearing a writable cache permits automatic rebuilding and leaves the installed default intact.

11. Explicit objects, ordered `-I` roots, custom system roots, and runtime overrides keep their authority. An invalid
    explicitly selected provider is not hidden by automatic preparation or a later managed provider.

12. Different compiler contents reporting the same version, ABI-compatible major releases, and changed minor releases
    select separate native entries while preserving matching semantic interfaces. Fingerprint-schema and adapter
    revisions invalidate records created under earlier identity rules.

13. File replacement, alias/symlink retargeting, changed subordinate tools, and selection of a different search-path
    candidate invalidate the applicable memo discovery or digest state. SDK/header inputs, ordered options, target
    architecture, ABI, and resolved native CPU features affect preparation selection.

14. Shared artifact-cache fixtures use independent machine-local identity memos. Matching content/configuration may
    reuse shared artifacts, but another machine's metadata cannot establish a memo hit or mask target differences.

15. Missing or corrupt memo records recompute identity. Forced preparation refreshes discovery and digests, including
    otherwise undetected metadata-preserving changes. Probe failure/timeout and files changing during hashing never
    authorize stale or unstable reuse.

16. Instrumented warm-path tests, including standalone linking, verify one resolved native preparation context per
    command and no compiler-binary content reads, recursive SDK scans, or repeated per-module discovery.
    Reference-machine benchmarks report p95 identity-validation time against the stated targets, separately from full
    artifact validation, preparation, and cold-discovery costs.

17. Integrated cold/warm build, run, and standalone-link acceptance passes with interface reuse, matching managed
    stdlib/runtime selection, and explicit-provider precedence before this plan closes.

18. Root-option precedence, relative paths, environment selection, disabled system defaults, and local/installed/system
    hit ordering are deterministic. Verify canonical alias deduplication, whole-profile selection, corruption authority,
    and explicit object/`-I` precedence with distinguishable fixtures.

19. Automatic misses write only to the selected local root. Explicit preparation populates that root even with matching
    installed/system entries; explicit shared-root prewarming works. Root access/write failures and overlapping
    installed destinations do not cause fallback writes or installed-payload changes.

20. Local and system cleanup select only their documented roots; invalid combinations fail without modification. Within
    established supported schemas, cleanup removes incomplete, inconsistent, missing-artifact, and digest-corrupt
    entries without a C compiler, and retains valid entries. Unfamiliar or indeterminate schemas are preserved for both
    artifacts and local memos. Exercise two L1 versions sharing storage: each cleaner preserves the other's unfamiliar
    entries, while scrub clears all recognized managed entries in scope regardless of schema. Installed files, unrelated
    files, and coordination infrastructure remain intact; missing local compilers do not invalidate shared native
    entries.

21. First-use and changed-manifest validation hash the complete inventory; unchanged warm reuse performs metadata checks
    without reading native artifact contents. Changed metadata rehashes affected files. Exercise size changes, same-size
    corruption, manifest replacement, shortened inventories, path escapes, unstable reads, and independent host memos.

22. Corrupt completed profiles fail without automatic overwrite or later-root substitution, including with
    `--no-auto-prepare`. Explicit cleanup/force repairs writable support under external serialization; installed
    fixtures remain unchanged. Missing/unparseable completion manifests permit lock-and-recheck recovery on a miss.
    Validation memo loss or unreliable metadata never permits unchecked hits; cleanup detects metadata-preserving
    corruption by hashing independently of memos.

23. Scope and integrity tests cover semantic-only modes without native toolchains, all native consuming modes, and
    retained generated C. Record artifact-validation costs separately from identity timing; maintenance adds no last-use
    timestamps, expiration, or automatic pruning. Installed fixtures suffice for integrated acceptance without
    productization.

24. The CLI accepts `--link ... -I ...` and documents the option. Other incompatible mode/option combinations remain
    rejected as specified.

25. A demo link without `-I` discovers required bundled `std.*` and `sys.*` providers and matching runtime support. A
    cold managed configuration prepares automatically; a warm invocation reuses it.

26. Ordered `-I` roots discover transitive project/third-party providers. Without those roots or explicit objects, a
    missing non-bundled provider fails rather than being compiled from source.

27. Explicit providers win over `-I` and managed providers, including when their operands occur after consumers.
    Duplicate explicit module identities still fail.

28. The first selected interface remains authoritative. Bad interfaces, absent sibling objects, wrong identities, and
    fingerprint mismatches are not hidden by later roots or usable cached alternatives.

29. Transitive and shared dependencies are included once, unrelated providers are excluded, and discovered objects
    appear before the first explicit root that needs them without changing relative explicit-operand order.

30. Cycles, entry ambiguity, invalid entry selection, and unreachable or inconsistent `require`/`link` expectations
    remain covered. Initialization/finalization ordering and explicit native-library ordering remain unchanged.

31. `--no-auto-prepare` still discovers matching managed providers and fails only when preparation is needed.
    `--no-stdlib-cache` disables that provider source while explicit and `-I` workflows remain usable.

32. Complete explicit no-`-I` link commands remain valid. New no-`-I` success cases are limited to missing managed
    bundled providers; the mode does not rebuild caller-supplied objects or compile non-bundled sources.

33. Shared build/run link planning and generated-C behavior retain their existing regression coverage.

During implementation, run focused CLI, graph, link, compiler/cache/bootstrap tests followed by L1 `make test-all`, ADR
validation, and the required pre-commit checks. Recording this Draft plan requires documentation validation only.

[backend]: ../../../docs/reference/c-backend-design.md
[bootstrap-productization]: ../tools/2026-04-02-l1-bootstrap-productization-noref.md
[cli-contract]: ../../../../docs/specs/compiler/cli-contract.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[external-inputs]: ../../../docs/decisions/0036-ordered-external-link-inputs-and-cli-only-dependency-ownership.md
[interface-authority]: ../../../docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md
[link-discovery]: closed/2026-09-07-standalone-link-interface-discovery-noref.md
[separate-compilation]: ../../../docs/reference/separate-compilation.md
