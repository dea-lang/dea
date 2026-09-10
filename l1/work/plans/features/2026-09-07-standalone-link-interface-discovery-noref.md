# Feature Plan

## Discover standalone-link providers through interfaces and managed stdlib artifacts

- Date: 2026-09-07
- Last edited: 2026-09-10
- Status: Draft
- Title: Add default managed stdlib discovery and explicit interface search roots to L1 standalone linking
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Compiler CLI / standalone linking / module graph / interface discovery
- Modules:
  - `l1/compiler/stage1_l0/src/cli_args/`
  - `l1/compiler/stage1_l0/src/link_driver/inputs.l0`
  - `l1/compiler/stage1_l0/src/link_driver/model.l0`
  - `l1/compiler/stage1_l0/src/link_driver/plan.l0`
  - `l1/compiler/stage1_l0/src/link_driver/provenance.l0`
  - `l1/compiler/stage1_l0/src/link_driver/toolchain.l0`
  - `l1/compiler/stage1_l0/src/module_graph.l0`
  - `l1/compiler/stage1_l0/src/module_interface.l0`
  - `l1/compiler/stage1_l0/src/interface_fingerprint.l0`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/link_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/module_graph_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_fingerprint_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_link_set_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_help_output_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_build_run_multi_cu_test.py`
  - `l1/compiler/stage1_l0/tests/fixtures/separate_compilation/`
- Related:
  - [l1/work/plans/features/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][stdlib-preparation]
  - [docs/specs/compiler/cli-contract.md][cli-contract]
  - [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]
  - [l1/docs/reference/separate-compilation.md][separate-compilation]
  - [l1/docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md][interface-authority]
  - [l1/docs/decisions/0036-ordered-external-link-inputs-and-cli-only-dependency-ownership.md][external-inputs]
- Repro: `l1c --link build/modules/demo.o -I build/modules -o demo` currently rejects the interface-path option.

## Summary

Enable standalone linking to discover required Dea providers from verified module interfaces. Managed stdlib discovery
is enabled by default, independently of `-I`; explicit `-I` roots add project, third-party, or caller-selected stdlib
providers. Explicit objects take precedence over ordered `-I` roots, followed by managed stdlib providers.

The companion preparation plan supplies matching installed or cached stdlib/runtime artifacts and automatically prepares
missing managed support when permitted. Implement this plan's interface-assisted discovery foundation first, then
integrate that service. The final behavior and verification criteria include both changes; default managed discovery
must not be gated on the presence of `-I`. The coordinated order is interface discovery, preparation, then
managed-provider integration. Neither plan is complete or eligible for closure before the integrated acceptance criteria
of both plans pass.

The reusable module contract remains a verified `.l1m` interface paired with an opaque sibling `.o`. Link only modules
required by the dependency closure, rather than every module present in an interface root or cache.

## Current State

- `--link` rejects `-I` with `L1C-2031`.
- The caller currently supplies the complete set of Dea objects explicitly, including required stdlib providers.
- The linker verifies sibling interfaces, module identities, fingerprints, entry selection, lifecycle ordering, and
  `require`/`link` provenance. Native objects remain opaque caller-trusted inputs.
- Foreign objects and external libraries are explicitly owned by the CLI's ordered native-input stream.

## Intended User Interface

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

Explicit cache maintenance is a separate mode with no source or object operands:

```sh
l1c --clean-cache
l1c --clean-cache --cache-scope system
l1c --clean-cache --scrub
l1c --clean-cache --scrub --cache-scope system
```

The default scope is `local`; `--cache-scope local` may also be written explicitly. These commands clean writable cache
data, never installed prepared artifacts.

These examples describe the planned behavior, not currently available CLI capabilities.

## Defaults Chosen

### Provider discovery and precedence

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

### Managed preparation and manual controls

Use the companion plan's versioned preparation fingerprint, cache roots, preparation coordination, and stderr verbosity
contract. Consume the same once-per-command resolved native preparation context for managed stdlib providers and runtime
selection. Compiler/toolchain discovery, machine-local identity memo validation, and cache-key construction belong to
that service; do not implement a second algorithm or repeat discovery per module in the link driver. Apply the companion
plan's identity-validation performance targets and instrumented warm-path requirements.

Discovery may use installed artifacts or cached variants. If required managed artifacts are missing, prepare them and
continue the original link command. Only the required providers enter the final link set even when preparation builds a
complete stdlib configuration.

- `--no-auto-prepare` permits managed discovery and reuse, but reports the exact preparation command on a miss.
- `--no-stdlib-cache` disables managed discovery and preparation. The caller then supplies required providers explicitly
  or through `-I`.
- Application and third-party dependencies must already have compiled objects. Standalone linking does not compile their
  sources or rebuild caller-supplied objects for a different C compiler.
- Explicit runtime overrides retain their authority. Managed stdlib discovery and runtime selection are related
  services, but neither permits changing explicit caller inputs.
- Native preparation identity selects managed artifacts; it does not prove compatibility of caller-supplied opaque
  objects. Keep semantic interface reuse separate and preserve modes that operate without a C toolchain.

### Cache ownership and managed artifact roots

Distinguish ownership independently of lookup precedence:

| Storage class                | Purpose                                                                               | Read | Prepare/write                    | Clean/scrub                     |
| ---------------------------- | ------------------------------------------------------------------------------------- | ---- | -------------------------------- | ------------------------------- |
| Local cache                  | Per-user or explicitly selected development cache; writable and disposable            | Yes  | Yes                              | Yes, with local scope           |
| System cache                 | Configured machine-wide/shared cache; writable and disposable with appropriate access | Yes  | Yes, when selected and permitted | Yes, with explicit system scope |
| Installed prepared artifacts | Bundled compiler installation payload                                                 | Yes  | No                               | Never                           |

Use the term "installed prepared artifacts" for bundled files even when their layout matches cache entries. System scope
never means the installed payload, and cleanup is not an installation-management operation. A system cache is optional;
selecting it must not silently clean a local cache or an installation when its root is unavailable or access is denied.
Do not automatically elevate privileges.

Explicit objects and ordered `-I` roots retain their existing precedence over all managed providers. Installed prepared
artifacts, local cache entries, and configured system cache entries can supply matching managed providers through the
same preparation service. Cache scope selects the maintenance destination; it does not by itself change link lookup
precedence. Finalize system-cache root configuration, its interaction with `--stdlib-cache`, and the ordering of managed
roots in the companion preparation plan before integration; the ownership table does not establish that ordering.

### Managed layout and manifest handoff

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
output inventory from the preparation key. Recording output digests does not require rehashing every output during warm
compiler-identity validation; the preparation service must define artifact validation separately.

The manifest itself is the completion record. Under the preparation lock, invalidate it before rebuilding, write
artifacts normally, and write the complete manifest last. A missing, malformed, or truncated manifest does not authorize
reuse. This preserves the ordinary-write contract without adding transactions or a second completion flag. Lock-file
existence is not lock ownership; process-lifetime coordination supplies ownership and release on exit.

Identity memos retain local paths, discovery dependencies, component file identities, size, high-resolution timestamps,
and remembered content digests. They remain machine-local even when artifact storage is shared. Local metadata never
establishes a portable artifact identity. Lookup computes a key and opens its directory directly; no global index or
"current compiler" pointer is required.

### Minimal on-demand cache cleanup

Implement maintenance in the shared preparation/cache service, not in the standalone-link provider walker:

- `--clean-cache` inspects managed entries in the selected writable cache on demand. Remove entries with unsupported
  cache-schema versions, invalid completion manifests, or missing required artifacts. Preserve complete entries with
  supported schemas even when their compiler, architecture, or checking configuration differs from the current one.
- Local cleanup also discards invalid or unsupported-schema identity memos and memos whose recorded compiler components
  no longer exist. A compiler missing on this machine is not sufficient reason to delete shared native artifacts.
- `--scrub` removes all managed cache entries in the selected scope, including otherwise valid entries. Local scrub also
  clears machine-local identity memos; system scrub does not clear other users' or machines' local identity state.
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
they are not retention metadata. These explicit maintenance decisions extend the coordinated pair's scope. Reconcile the
companion preparation plan's earlier exclusion of cache garbage collection with this narrow cleanup contract before
implementation; automatic pruning and general cache management remain excluded.

## Compatibility

Existing complete explicit link commands remain valid and preserve explicit-provider precedence and native-input order.
An invocation without `-I` may now succeed when its missing providers are bundled stdlib modules; requiring those
modules to be explicitly listed is intentionally relaxed. A missing project or third-party provider still fails without
an explicit object or suitable `-I` root.

The new managed-preparation exception is confined to compiler-owned stdlib/runtime support. Document this exception in
the standalone-link mode contract while preserving the separate-compilation boundary for user dependencies.

## Implementation Phases

1. Permit `-I` with standalone link, update help and mode validation, and establish explicit-provider registration
   before recursive interface-assisted discovery.
2. Integrate authoritative ordered lookup, dependency deduplication, object insertion, and all existing semantic checks.
   Cover these with caller-prepared provider fixtures before depending on the managed cache.
3. Integrate the companion preparation service as the default final provider source, with no `-I` prerequisite. Apply
   matching preparation fingerprints, automatic preparation, and the two manual-control flags. Share the resolved native
   preparation context with runtime selection and retain the service's fast identity-validation path. Resolve managed
   root configuration/ordering in the companion plan and implement the shared layout, ownership distinctions, and
   explicit cleanup/scrub contract there; do not create a second cache implementation in the link driver.
4. Update the shared CLI contract, relevant diagnostic descriptions, and L1 separate-compilation docs when the feature
   lands. Document both no-`-I` stdlib linking and additional provider discovery through `-I`.

## ADR Impact

- Decision: Discover managed stdlib providers by default and use explicit interface roots for additional standalone-link
  providers.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md`
  - Rationale: Extend provider discovery while retaining verified interface authority and opaque native inputs. Managed
    stdlib discovery works without `-I`; explicit search roots extend lookup. Preserve ADR-0036's external-input
    ownership and encounter-order contract.
- Decision: Share a versioned manifest-based artifact layout across prepared roots while retaining machine-local
  identity memos and root-specific ownership.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Installed and cached artifacts share consumption and completion rules, while portable artifact identity
    remains separate from local validation state and installation ownership.
- Decision: Provide explicit schema/validity cleanup and exhaustive scrub for local or system writable caches.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Scoped deletion, installed-payload protection, external serialization, and the exclusion of expiration
    establish the maintenance boundary for the shared preparation service.

## Diagnostic Planning

Reuse existing interface, missing-object/provider, identity, fingerprint, cycle, entry, and provenance diagnostics.
Update `L1C-2031` to accept `--interface-path` in standalone-link mode. Preparation, coordination, and managed-cache
failures use the companion plan's provisionally reserved `L1C-2150` through `L1C-2169` area; this plan does not reserve
a second block. Include cleanup scope/root failures, permission and removal failures, and invalid maintenance-mode
combinations, reusing existing CLI diagnostics where applicable. Unsupported or invalid entries removed by requested
cleanup are maintenance results, not compilation failures.

Recheck all reservations and candidate reused codes against
[docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] at implementation time. A default managed-cache miss that
can be prepared is progress, not a missing-provider error. An invalid earlier explicit provider remains an error even
when a usable managed provider exists.

## Non-Goals

- Compiling application or third-party dependency sources during standalone linking.
- Automatically discovering foreign objects or native libraries.
- Searching arbitrary project directories without an explicit root.
- Linking every module in an interface root or cache.
- Relaxing interface authority or proving native object compatibility.
- Implementing a separate cache or preparation mechanism from the companion plan.
- Adding age-based expiration, usage tracking, automatic pruning, or general cache management.
- Modifying installed prepared artifacts through cache maintenance or supporting concurrent cleanup and consumption.

## Verification Criteria

01. The CLI accepts `--link ... -I ...` and documents the option. Other incompatible mode/option combinations remain
    rejected as specified.
02. A demo link without `-I` discovers required bundled `std.*` and `sys.*` providers and matching runtime support. A
    cold managed configuration prepares automatically; a warm invocation reuses it.
03. Ordered `-I` roots discover transitive project/third-party providers. Without those roots or explicit objects, a
    missing non-bundled provider fails rather than being compiled from source.
04. Explicit providers win over `-I` and managed providers, including when their operands occur after consumers.
    Duplicate explicit module identities still fail.
05. The first selected interface remains authoritative. Bad interfaces, absent sibling objects, wrong identities, and
    fingerprint mismatches are not hidden by later roots or usable cached alternatives.
06. Transitive and shared dependencies are included once, unrelated providers are excluded, and discovered objects
    appear before the first explicit root that needs them without changing relative explicit-operand order.
07. Cycles, entry ambiguity, invalid entry selection, and unreachable or inconsistent `require`/`link` expectations
    remain covered. Initialization/finalization ordering and explicit native-library ordering remain unchanged.
08. `--no-auto-prepare` still discovers matching managed providers and fails only when preparation is needed.
    `--no-stdlib-cache` disables that provider source while explicit and `-I` workflows remain usable.
09. Complete explicit no-`-I` link commands remain valid. New no-`-I` success cases are limited to missing managed
    bundled providers; the mode does not rebuild caller-supplied objects or compile non-bundled sources.
10. Shared build/run link planning and generated-C behavior retain their existing regression coverage.
11. Integrated cold/warm build, run, and standalone linking share matching managed stdlib/runtime preparation identity.
    Compiler implementation, target, and configuration changes select the appropriate providers while preserving
    matching semantic interfaces and explicit-provider precedence. Shared-cache fixtures cannot reuse an incompatible
    target or another machine's identity memo.
12. Instrumented warm linking verifies one native preparation context per command, no repeated per-module compiler
    discovery, and the companion service's no-binary-read and no-recursive-SDK-scan requirements. Measure identity
    validation separately against the companion plan's reference-machine performance targets. Neither plan closes before
    the coordinated integration acceptance passes.
13. Installed, local, and configured system prepared roots share the artifact format and identity checks while
    preserving their ownership policies. Neither local nor system cleanup/scrub modifies installed payload files or
    unrelated data; missing/inaccessible system roots never fall back to another root.
14. Cleanup removes unsupported-schema, malformed/incomplete, and missing-artifact entries, while retaining supported,
    complete configurations for other compilers or targets. Local missing-compiler memos are removed without deleting
    shared native artifacts solely because the compiler is unavailable locally. No age or last-use metadata affects
    selection.
15. Scrub removes every managed entry in the selected writable scope. Local is the default and system requires explicit
    selection. Invalid mode/flag combinations fail; cleanup requires no C compiler and performs no preparation. A later
    cold link can prepare required managed support under the normal policy.
16. Manifest inventory paths remain relative to their entry, native profiles retain canonical sibling pairs and
    generated C, and incomplete manifests cannot authorize reuse. Cleanup preserves coordination files and cannot
    traverse outside managed roots. Exercise maintenance under its documented external-serialization precondition.

During implementation, run focused CLI, graph, link, and cache-integration tests followed by L1 `make test-all`, ADR
validation, and required pre-commit checks. Recording this Draft plan requires documentation validation only.

[cli-contract]: ../../../../docs/specs/compiler/cli-contract.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[external-inputs]: ../../../docs/decisions/0036-ordered-external-link-inputs-and-cli-only-dependency-ownership.md
[interface-authority]: ../../../docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md
[separate-compilation]: ../../../docs/reference/separate-compilation.md
[stdlib-preparation]: 2026-09-07-stdlib-runtime-preparation-and-cache-noref.md
