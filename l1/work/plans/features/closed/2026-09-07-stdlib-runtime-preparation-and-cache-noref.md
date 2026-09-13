# Feature Plan

## L1 standalone-link discovery and user stdlib/runtime preparation cache

- Date: 2026-09-11
- Originally planned: 2026-09-07
- Last edited: 2026-09-11
- Status: Completed
- Title: L1 standalone-link discovery and user stdlib/runtime preparation cache
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
  - `l1/compiler/stage1_l0/src/preparation.l0`
  - `l1/compiler/stage1_l0/src/preparation/`
  - `l1/compiler/stage1_l0/src/module_graph/order.l0`
  - `l1/compiler/stage1_l0/support/preparation_support.c`
  - `l1/compiler/stage1_l0/support/preparation/`
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
  - `l1/compiler/stage1_l0/tests/l1c_stage1_bootstrap_interfaces_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_managed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_installed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_support_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_ownership_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_test.l0`
  - `l1/compiler/stage1_l0/tests/io_runtime_test.py`
- Related:
  - [l1/work/plans/features/closed/2026-09-07-standalone-link-interface-discovery-noref.md][link-discovery] (superseded)
  - [l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][bootstrap-productization]
  - [docs/specs/compiler/cli-contract.md][cli-contract]
  - [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]
  - [l1/docs/reference/separate-compilation.md][separate-compilation]
  - [l1/docs/reference/c-backend-design.md][backend]
  - [l1/docs/decisions/0027-runtime-archive-and-trace-selection-boundary.md][runtime-selection]
  - [l1/docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md][interface-authority]
  - [l1/docs/decisions/0033-multi-compilation-unit-build-and-run-pipeline.md][build-run]
  - [l1/docs/decisions/0036-ordered-external-link-inputs-and-cli-only-dependency-ownership.md][external-inputs]
- Repro: `l1c --compile l1/examples/demo.l1 -o build/modules/demo.o` after bootstrap without manually prepared stdlib
  interfaces.

## Summary

L1 treats bundled standard-library semantic interfaces and stdlib/runtime source inputs as part of the toolchain. Native
stdlib/runtime objects are derived artifacts.

The installed toolchain therefore contains everything required to recreate bundled native support, but correctness does
not depend on a precompiled native stdlib/runtime configuration being installed.

Commands that need bundled native support prepare a matching configuration using the selected C compiler and native
settings. Reusable preparations are stored under one local managed cache root. Installed defaults are per-user;
repo-local defaults are build-local.

A cache miss is ordinary compiler work. Managed state under `<CACHE_ROOT>/v1/` is disposable and non-authoritative.
Deleting that Dea-owned subtree may increase compilation work but must not change the meaning of a successful
compilation.

Managed preparation applies only to compiler-owned bundled support. It does not cache application or third-party outputs
and does not introduce project roots, project profiles, persistent project state, or build-system semantics into `l1c`.

Standalone-link discovery remains interface-driven. Explicit Dea objects retain authority, followed by ordered explicit
interface roots, followed by bundled managed providers.

The feature deliberately does not provide a machine-wide/shared artifact store, cross-machine cache portability, cache
migration, or general cache-management subsystem.

This remains the authoritative plan for interface-assisted provider discovery and compiler-owned preparation. It absorbs
the unimplemented scope of
[l1/work/plans/features/closed/2026-09-07-standalone-link-interface-discovery-noref.md][link-discovery], which is closed
as superseded, not as implemented. Implementation and validation completed on 2026-09-11, with independent reviews of
every phase and the complete unit.

## Design Principles

1. Correctness comes from compiler inputs, semantic validation, and valid native preparation, not from the existence of
   cached native objects.
2. Persistent reuse is an optimization.
3. Semantic interface identity and native preparation identity are separate.
4. Bundled semantic interfaces may exist without native sibling objects until a native-consuming command needs them.
5. Managed preparation applies only to compiler-owned bundled support.
6. `l1c` may manage its own stdlib/runtime artifacts. It does not manage the user's build.
7. Native reuse is conservative. L1 does not infer ABI compatibility between distinct configurations.
8. A configuration may be compilable without being eligible for persistent cache reuse.
9. Cache and memo formats are internal implementation formats, not distribution or interchange formats.

## Baseline Before Implementation

- `--link` rejected `-I` with `L1C-2031`.
- The caller supplied the complete set of Dea objects explicitly, including required stdlib providers.
- The linker verifies sibling interfaces, module identities, fingerprints, entry selection, lifecycle ordering, and
  `require`/`link` provenance. Native objects remain opaque caller-trusted inputs.
- Foreign objects and external libraries are explicitly owned by the CLI's ordered native-input stream.
- Bootstrap built the compiler and native runtime support but did not supply bundled semantic interfaces or reusable
  stdlib `.o`/`.l1m` pairs.
- Build/run compile a source dependency closure in a private workspace; their temporary module artifacts are not a
  reusable stdlib cache.
- Compile-only requires verified interfaces for non-virtual imports rather than falling back to their sources.
- Stdlib source roots and explicit interface roots are separate discovery inputs.
- Native runtime selection already distinguishes checking/trace variants and TinyCC compatibility objects.
- L1 remains bootstrap-only. Its installed payload contract must be coordinated with the existing productization plan;
  this feature does not itself implement an installer or distribution workflow.

This feature extends provider discovery and compiler-owned native preparation without changing `.l1m` format, object
ABI, application dependency ownership, or caller-owned native link inputs.

## Standalone-Link Interface Discovery

With managed bundled providers available:

```sh
l1c --link build/modules/demo.o -o demo
```

may link successfully when the remaining Dea dependencies are bundled `std.*` or `sys.*` modules.

The linker reads the supplied authoritative interfaces, follows required non-virtual imports, resolves bundled semantic
providers, obtains matching native managed providers when required, and links only the dependency closure needed by the
command.

Project and third-party providers remain explicit:

```sh
l1c --link build/modules/demo.o -I build/modules -o demo
```

Provider authority is:

1. explicitly supplied Dea objects;
2. explicit `-I` roots in declaration order;
3. bundled managed stdlib providers.

Rules:

- register and validate explicit Dea objects before resolving missing providers;
- preserve their original paths and authority;
- duplicate explicit module identities remain errors;
- follow verified non-virtual imports recursively;
- managed discovery is limited to bundled `std.*` and `sys.*`;
- arbitrary project directories are never searched implicitly;
- the first selected explicit or `-I` provider remains authoritative;
- an invalid explicit or `-I` provider is an error and is not replaced by a managed provider;
- discover each dependency once;
- do not add unrelated cached modules;
- existing entry, lifecycle, fingerprint, cycle, `require`/`link`, and provenance checks remain in force.

Insert discovered objects in dependency order immediately before the first explicit root needing them. Preserve the
relative order of all explicit operands and native link controls, including providers supplied after their consumers.

Ordered lifecycle imports alone define dependency edges, dependency-first initialization, and reverse finalization.
`require` and `link` remain semantic expectations with the existing reachability and provenance checks; they do not
independently add objects or lifecycle edges.

Foreign objects, native libraries, search paths, rpaths, and raw native link arguments remain caller-owned explicit
inputs.

## Managed Semantic and Native Provider Boundary

Bundled managed providers have two distinct states.

For semantic-only consumers, the toolchain's bundled `.l1m` is sufficient. No sibling native object is required merely
to analyze, generate C, emit an interface, or compile another module.

For a native-consuming build or link, a bundled provider becomes a native provider only after a matching native profile
has been selected or prepared.

The native-consuming provider pair is then the canonical `.l1m + .o` pair from that native profile.

Native preparation copies the exact selected toolchain-owned `.l1m` bytes into the native profile to form the canonical
sibling pair. It does not independently re-emit bundled semantic interfaces. Profile validation checks byte-for-byte
correspondence with the selected semantic artifact, in addition to normal interface and graph validation. A private
implementation change can change the native object through `D` while the copied interface remains byte-identical.

This managed-provider rule is a narrow extension of the ordinary interface-backed provider contract. Explicit objects
and explicit `-I` roots retain their existing mode-specific sibling-object rules and do not acquire managed fallback. In
build/run and standalone link, explicit native providers still require the original regular sibling object. Modes that
already accept a verified imported interface without native siblings keep that behavior.

Build/run may therefore resolve a bundled provider semantically before materializing the matching native pair for final
link planning. The requested target still resolves from source and remains the entry selection. Application and
third-party source fallback, per-module compilation, command-owned workspaces, and common link planning retain the
contract in [l1/docs/decisions/0033-multi-compilation-unit-build-and-run-pipeline.md][build-run].

Preserve build/run `--keep-c` retention and cross-mode C-byte identity for identical generation inputs as specified in
[docs/specs/compiler/cli-contract.md][cli-contract]. Optional managed-preparation scratch, including generated C, does
not become required native-profile inventory.

The authoritative-interface model remains unchanged: native bytes are opaque, while the selected `.l1m` remains the
semantic authority.

## Bundled Providers in Source Resolution

For imported providers in source-resolving modes, preserve each mode's existing input and source-fallback rules:

1. Ordered explicit `-I` interfaces remain first where the mode accepts them. A selected interface is authoritative.
2. Next, preserve the existing effective source-root sequence: system roots before project roots, retaining order within
   each group. Explicit `--sys-root` roots replace the implicit bundled system root; existing `L1_SYSTEM` selection
   remains in force when no CLI system roots are supplied.
3. Exactly at the compiler-owned bundled stdlib position, select the managed bundled `.l1m` instead of falling back to
   the compiler's bundled source. A caller-selected system configuration that suppresses that implicit position also
   suppresses the managed bundled semantic-provider position; do not append another bundled fallback.
4. Project roots keep their existing position after system roots. `--project-root` does not become an override mechanism
   for bundled stdlib providers.

The managed semantic set occupies exactly the compiler-owned bundled-provider position in existing resolution. It does
not create a new provider-precedence tier in source-resolving modes.

If existing resolution selects a caller's source-backed provider, it remains source-backed and follows that mode's
existing compilation/fallback rules; the managed cache does not replace it. Compile-only still requires interfaces for
non-virtual imports and gains no application or third-party source fallback. The requested source target always remains
source-backed.

Standalone `--link` has no source-root resolution and retains its separate ordering: explicit Dea objects, ordered `-I`
roots, then managed bundled providers.

## Bundled Semantic-Interface Lifecycle

Bundled semantic interfaces are required toolchain build artifacts, available before native stdlib preparation.

Repo-local `make build-stage1` generates and verifies the complete bundled `std.*` and `sys.*` interface set after
building `l1c`. The set lives under `$L1_BUILD_DIR/interfaces/` using module-relative paths such as `std/io.l1m`.
Generation uses the newly built compiler's frontend and bundled sources; it does not compile native stdlib objects or
require native user-cache preparation. Successful bootstrap includes this semantic set, independently of optional native
prewarming.

Bootstrap semantic-set generation selects the canonical compiler-owned bundled sources directly. Ambient `L1_SYSTEM`,
project-root, or interface-path overrides must not redirect generation to caller content.

Installed toolchains ship the corresponding verified set at the prefix location owned by productization. Repo-local and
installed compilers place the semantic set according to the source-resolution or standalone-link rules above.

Repo-local semantic-set freshness is owned by `make build-stage1`. Changes to bundled sources or compiler inputs that
affect interface generation require rerunning that build before using the toolchain. Using the old compiler/semantic set
after those edits without rebuilding is outside the supported development workflow.

`l1c` performs normal selected-interface and graph validation. Missing, malformed, or internally invalid required
semantic artifacts produce detected toolchain-input errors with bootstrap rebuild or installation-repair guidance. This
is distinct from proving freshness against current source files: semantic-only commands do not rehash bundled sources to
prove that bootstrap was rerun. No additional runtime identity system or freshness-detection mechanism is required for
the semantic set.

Content-sensitive `D` remains required for native preparation; it does not turn every compiler command into a proof of
semantic-set freshness. Native preparation consumes the bootstrap-owned semantic set and copies its exact interface
bytes, without a lazy semantic cache or independent interface emission.

The semantic set is outside the native user cache. Removing the Dea-owned native cache subtree leaves the toolchain
semantic set available.

## Installed Payload

An installed L1 toolchain contains the compiler-owned inputs needed to reproduce bundled support:

```text
<installation>/
    l1c
    bundled stdlib semantic interfaces
    bundled stdlib sources
    runtime sources
    runtime/public headers
    other compiler-owned preparation inputs
```

Exact prefix paths are owned by the bootstrap/productization plan.

Native stdlib objects and runtime archives are outside this plan's installed payload. Installed native acceleration is
outside this feature's scope.

The installed payload is read-only from the preparation service's perspective. Rebuild-only headers, including
`dea_siphash.h`, remain internal preparation inputs rather than public runtime headers.

In installed context, reject a selected cache root whose managed `<CACHE_ROOT>/v1/` subtree would lie within the active
installed payload. Resolve paths sufficiently to prevent aliases from turning installed files into managed writable
state. This boundary applies to explicit selections and implicit defaults alike.

Bundled semantic interfaces belong in the installation because they describe the shipped Dea semantic contract.

Native objects belong in managed preparation because the user may select another supported C compiler, target, checking
configuration, trace configuration, or other native setting.

### Productization Handoff

This ownership model supersedes the installed-native assumptions in
[l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][bootstrap-productization]. Align that companion
plan before this plan closes; remove its default native-profile payload, native-profile export/lookup handoff, and
shipped-native-profile acceptance requirements from this delivery contract.

In particular, productization must remove:

- one default native stdlib/runtime profile under the installed prefix;
- managed lookup of installed native profiles;
- installed native cache keys from the required installation metadata.

It must continue to ship:

- bundled stdlib sources;
- bundled semantic interfaces;
- runtime sources and public headers;
- installation metadata required to identify the shipped compiler-owned input set.

Productization continues to own the prefix layout, launchers, installation inventory, archive construction, and
relocation. Its inventory identifies the shipped compiler-owned inputs, including `D` where supplied, without requiring
an installed native key or a portable native-profile export format. Read-only installed-payload fixtures with no native
support suffice to validate this feature independently of installer implementation.

Generated-C users remain responsible for arranging a matching runtime when compiling emitted C outside `l1c`. The
shipped runtime sources provide the toolchain-independent reconstruction path; this preparation/cache feature does not
add a second public runtime-export API.

## Managed Cache Root

L1 selects one local managed cache root for persistent reuse. Its availability is separate from native compilability.

Selection precedence is:

1. `--stdlib-cache PATH`;
2. `L1_STDLIB_CACHE`;
3. the default for the compiler context below.

Default roots are:

| Environment                   | Default root                                                |
| ----------------------------- | ----------------------------------------------------------- |
| Repo-local compiler           | `$L1_BUILD_DIR/cache`                                       |
| Installed compiler on Linux   | `$XDG_CACHE_HOME/dea/l1`, falling back to `~/.cache/dea/l1` |
| Installed compiler on macOS   | `~/Library/Caches/dea/l1`                                   |
| Installed compiler on Windows | local AppData under `Dea\L1\Cache`                          |

Repo-local use takes the compiler's resolved `L1_BUILD_DIR`, whose existing default is `build/dea` under `l1/`.
Repo-local bootstrap, development, and tests therefore default to build-tree storage rather than the installed
compiler's platform user cache.

A relative explicit override is resolved against the invocation directory.

Both `--stdlib-cache` and `L1_STDLIB_CACHE` are explicit storage selections. An unusable explicitly selected cache root
is an actionable configuration error.

If the implicit repo-local or platform default is unavailable or unwritable:

- build/run and standalone link may still reuse a valid profile that can be read and validated; otherwise, when
  automatic preparation is enabled, they obtain fresh command-private support without persistent writes;
- `--prepare-stdlib` fails because explicit preparation requires a usable persistent destination;
- `--no-auto-prepare` fails if no valid reusable profile can be read and validated.

`l1c` does not silently select another persistent root. An unavailable implicit default uses the existing private
preparation path when permitted, not another persistent cache.

External build tooling or CI may choose an isolated cache root explicitly. This gives the caller storage control without
introducing project semantics into `l1c`.

Persistent reuse assumes a cache root used on one host. An explicit path changes the storage location, not that trust
boundary. Copying or sharing the cache across hosts carries no reuse guarantee and is outside the supported contract. L1
need not detect that situation or bind cache state to a host identity. This feature adds no host-transfer validation or
portability mechanism.

There is no system/shared cache contract and no automatic machine-wide cache.

## Cache Layout

The managed cache uses an internal versioned layout:

```text
<CACHE_ROOT>/
    v1/
        native/
            <native-key>/
                manifest.json
                modules/
                    std/
                    sys/
                lib/

        locks/
            native-<native-key>.lock

        memo/
            toolchains/
                <selection-key>.json
            artifacts/
                <native-key>.json
```

A native profile contains the complete bundled native support for one preparation identity:

- canonical sibling `.l1m + .o` pairs for bundled native providers;
- the matching runtime archive or TinyCC runtime-object set;
- the completion manifest.

Runtime/public headers remain toolchain inputs covered by `D`, and managed compilation uses them from the toolchain
rather than copying them into each native profile. Existing explicit header overrides retain their authority and
identity requirements. The current public headers are not configuration-generated, so this profile has no `include/`
inventory. The exact toolchain-interface copies under `modules/` are required by the sibling-pair contract.

Preparation may retain additional internal scratch or diagnostics, including generated C, but such files are not
required profile inventory and do not determine whether a profile is reusable.

Preparing a complete bundled profile does not cause every module to enter a link. Provider discovery still selects only
the required dependency closure.

No global index, current-profile pointer, project database, usage database, or application-output cache is introduced.

The layout version is internal. A future compiler version may ignore an unsupported cache schema rather than migrate it.

There is no separate persistent semantic-interface cache. The required toolchain semantic set follows the bootstrap and
installation lifecycle above.

## Preparation Interface

Explicit preparation is available for prewarming and advanced maintenance:

```sh
l1c --prepare-stdlib
l1c --prepare-stdlib --c-compiler gcc
l1c --prepare-stdlib --c-compiler gcc --stdlib-cache _cache/dea
l1c --prepare-stdlib --c-compiler gcc --force
```

`--prepare-stdlib` is a primary mode with no positional source target. The shared CLI contract must record this
L1-specific target exception.

The new cache options have the following mode scope:

| Option                | Valid modes                                      |
| --------------------- | ------------------------------------------------ |
| `--stdlib-cache PATH` | `--build`, `--run`, `--link`, `--prepare-stdlib` |
| `--no-auto-prepare`   | `--build`, `--run`, `--link`                     |
| `--force`             | `--prepare-stdlib` only                          |

Other mode combinations are CLI argument errors under the shared CLI contract. In particular, `--stdlib-cache` is not
accepted as a no-op with `--compile`, `--gen`, `--check`, or other semantic-only modes.

Bootstrap/development prewarming, explicit preparation, and automatic preparation use the same preparation pipeline and
native compilation rules. Destination and publication policy differ between persistent preparation and command-private
fallback.

Native preparation builds all bundled `std.*` and `sys.*` providers in dependency order plus matching runtime support.

Ordinary behavior:

- build/run automatically prepare missing managed native support and continue;
- standalone link automatically prepares missing managed native support and continues;
- compile-only does not require native stdlib provider objects merely to compile the requested module;
- generated-C and semantic inspection modes do not require native preparation;
- source inspection and interface emission remain independent of a native C toolchain except where an existing mode
  independently requires one.

`--no-auto-prepare` permits reuse of an already valid managed native profile but forbids creating fresh native support
on a miss. A miss reports an actionable preparation-disabled diagnostic and the corresponding explicit preparation
command when the configuration is eligible for persistent preparation. For a configuration that cannot be persistently
reused, explain that automatic fresh preparation must be enabled or an eligible native configuration selected.

`--prepare-stdlib` requests persistent preparation. If the adapter cannot establish persistent-reuse eligibility, fail
with an actionable diagnostic; there is no consumer for temporary output in this mode. The guidance may direct the
caller to build/run or standalone link with automatic preparation, or to select an eligible native configuration. An
unusable persistent destination also fails explicit preparation, including when the implicit default selected it.

`--force` is valid only with explicit `--prepare-stdlib`. It bypasses cached or memoized validation results and
recomputes the required toolchain observation, native identity, and profile. It never bypasses adapter requirements,
persistent-reuse eligibility, or native identity rules. A non-cacheable configuration still fails explicit preparation,
including with `--force`. `--prepare-stdlib --no-auto-prepare` is an invalid mode/option combination.

No `--no-stdlib-cache` behavior is introduced by this feature. Disabling persistent reuse and disabling bundled managed
providers are separate concepts and are not collapsed into one flag.

No system-cache, scope, cleanup, scrub, or cache-migration CLI is introduced.

## C Compiler and Native-Option Semantics

Managed preparation uses the C compiler selected by the ordinary L1 compiler-selection rules.

Managed preparation retains two distinct native compilation configurations within one profile:

- Bundled Dea modules compile generated C with the selected L1 C compiler and effective generated-C options, including
  `L1_CFLAGS` followed by `--c-options`, as in the existing build/run path.
- Runtime implementation sources use the same selected native compiler/toolchain as the managed stdlib modules, with
  compiler-owned runtime C flags, checking/trace variant defines, runtime include inputs, and compiler-owned default
  baked tuning. The runtime flag baseline is `-O2 -std=c99`; the shipped runtime currently defaults to a 16 MiB
  quarantine byte limit and 4096 records. Arbitrary application/generated-C options are not forwarded wholesale into
  `dea_rt_*.c`.

Both compilation classes apply the supported effective target, ABI, and sysroot/SDK configuration. Compiler-owned
runtime flags must not silently build for host defaults when a different supported native configuration was selected.
The adapter resolves the applicable target settings without treating the entire application option vector as runtime
flags.

`L1_RUNTIME_CC`, `RUNTIME_CFLAGS`, `L1_RT_QUARANTINE_MAX_BYTES`, `L1_RT_QUARANTINE_MAX_COUNT`, and `AR` remain
Make/developer build controls. Managed preparation in `l1c` does not read them as configuration and does not add them to
its identity merely because they are present in the environment. Existing `DEA_RT_QUARANTINE_MAX_BYTES` and
`DEA_RT_QUARANTINE_MAX_COUNT` process-time retuning remains unchanged and does not select a native profile.

Where runtime archive production is required, the supported toolchain adapter selects an archiver compatible with the
selected native toolchain/target. Its required selection inputs and observation participate in native preparation
identity and reuse validation. An unavailable required archiver is an actionable preparation-toolchain error. TinyCC's
raw-object route has no archiver input; an archive path uses archive-tool observation when applicable. No new archiver
CLI option or whole-host toolchain fingerprinting is introduced.

Sharing one profile does not mean using the same literal C option vector for both compilation classes. Native identity
records the effective configurations actually used. This clarification adds no public runtime-options CLI and does not
change existing application C-option behavior.

For standalone link, extend the current wrapper-only meaning of `L1_CFLAGS` / `--c-options` to generated-C compilation
of managed bundled Dea modules when the command selects or creates their native profile. This extension does not replace
the runtime implementation's separate build policy or append these options as arbitrary final host-link command words.

Reflect this distinction explicitly in the shared CLI contract and user documentation.

Ordered external-link inputs such as `-l`, `-L`, rpaths, foreign objects, and raw link arguments do not become
preparation-key inputs merely because they occur in the same compiler command. They remain final-link inputs.

Existing compiler runtime-include/runtime-library overrides and system-root overrides retain their authority in their
existing modes. This does not promote the Make-only controls listed above into compiler options. Standalone link
continues to reject source-root options; accepting `-I` extends interface discovery only. An override that changes the
inputs used to compile managed bundled support must either participate in native preparation identity or make persistent
reuse unavailable when the implementation cannot identify it safely.

A runtime-include override (`--runtime-include` / `L1_RUNTIME_INCLUDE`) used while compiling managed bundled generated C
participates in the effective stdlib native configuration. A runtime-library override (`--runtime-lib` /
`L1_RUNTIME_LIB`) remains a final-link runtime selection override: it does not enter `N` and does not turn the managed
native profile into a partial profile. Preparation still produces complete managed runtime support when creating a
profile, even when that command ultimately links an explicit runtime override.

Preserve runtime selection from
[l1/docs/decisions/0027-runtime-archive-and-trace-selection-boundary.md][runtime-selection] and
[l1/docs/decisions/0036-ordered-external-link-inputs-and-cli-only-dependency-ownership.md][external-inputs]:
checking/trace variants, stable runtime-facing ABI, the selected exact-path archive for ordinary compiler families, and
the complete variant-matched TinyCC raw-object set when available with exact-archive fallback. Driver-selected runtime
inputs still follow the encounter-ordered caller stream by exact path, so user `-L` entries cannot shadow them. The
extension changes how compiler-owned support is obtained, not the typed native-input or runtime-selection contract.

## Dea Preparation-Input Identity

Semantic `.l1m` fingerprints continue to describe module semantics and are validated normally.

They are not sufficient to identify cached native implementations. A private implementation change may require different
objects without changing the public semantic fingerprint.

Define the compiler-owned Dea preparation identity:

```text
D = H(
    identity-schema-revision,
    effective l1c implementation identity,
    bundled stdlib source contents,
    bundled runtime source/header contents,
    other compiler-owned preparation inputs
)
```

The exact canonical encoding is internal but deterministic.

For an immutable installed payload, `D` may be computed during construction and shipped as installation metadata.

That metadata is trusted as part of a valid installation. Detecting arbitrary manual mutation of installed compiler
files is an installation-integrity concern, not a reason to hash the complete installation on every compiler invocation.

For a development checkout, `D` must reflect the effective working inputs and must not rely solely on a release version
or Git commit when working-tree modifications can change generated native support.

A change to any compiler-owned input represented by `D` conservatively selects a different native profile. This native
reuse requirement is separate from bootstrap ownership of semantic-set freshness.

L1 does not attempt cross-`D` per-module native reuse.

## Native Preparation Identity

A reusable native profile is selected by:

```text
N = H(
    preparation-schema-revision,
    D,
    supported-toolchain-observation,
    effective-stdlib-native-configuration,
    effective-runtime-native-configuration
)
```

The stdlib and runtime configurations are recorded separately within the same native identity. Each includes the inputs
actually applied to that compilation class, including as applicable:

- architecture;
- OS/object format;
- ABI;
- required CPU features;
- ordered effective C compile options for that compilation class;
- relevant sysroot/SDK selection;
- checking mode;
- trace mode;
- runtime-build flags, variant defines, and baked tuning for runtime compilation;
- runtime-include override inputs used for managed bundled generated-C compilation.

Changing either effective compilation configuration changes `N`. An application option that affects bundled generated C
does not thereby become a runtime compilation flag, even though both outputs share a native profile.

Host-dependent options contribute resolved meaning where the supported adapter can determine it.

Application source paths, project names, project roots, application dependency graphs, final executable paths, and
final-link-only options do not enter `N`.

Different native preparation identities select different profiles.

L1 does not infer ABI compatibility between distinct identities merely to increase cache hits.

## Supported Toolchain Observation and Persistent-Reuse Boundary

L1 distinguishes:

1. native configurations the backend can invoke;
2. native configurations for which persistent managed reuse can be validated.

Persistent reuse is allowed only when the active supported toolchain adapter can establish the observation required by
the current preparation schema. Schema and adapter revisions participate in that observation's identity so changed reuse
rules invalidate earlier records. Preserve existing GCC, Clang/Apple Clang, and TinyCC workflows; this feature does not
add support for another native compiler family.

A supported observation may contain:

- compiler family;
- resolved invocation;
- compiler executable content digest;
- readable compiler version/build metadata;
- effective target information;
- bounded adapter queries;
- selected compiler components where required;
- adapter-selected archiver and its required selection/validation inputs where archive production is used;
- SDK/sysroot or header-environment observations required by that adapter;
- declared environment or search inputs that affect preparation.

The product contract is not that L1 fingerprints an entire host compiler installation.

Instead:

> A supported adapter must either observe the native inputs it relies on well enough to validate persistent reuse, or
> decline persistent reuse for that configuration.

Adapters must not authorize a cache hit after a required observation fails.

They must not require recursive hashing of an entire SDK on every command.

Opaque wrappers, unsupported indirection, or host arrangements outside an adapter's validation boundary may therefore
remain compilable while being ineligible for persistent reuse.

In that case, build/run and standalone link with automatic preparation obtain fresh command-private bundled native
support without reusing or publishing persistent state. A compilable configuration remains usable for that consuming
command.

Explicit `--prepare-stdlib`, including `--force`, fails when persistent-reuse eligibility cannot be established. Fresh
temporary preparation is a fallback for commands that consume it, not a successful result for explicit prewarming.

When automatic preparation is disabled, lack of a reusable valid profile is a preparation-disabled miss.

There is no identity-override CLI for telling `l1c` to trust an otherwise unsupported persistent configuration.

## Machine-Local Memoization

Memoization accelerates validation. It is not a source of identity.

`memo/toolchains/` may record:

- compiler selection inputs;
- resolved paths;
- local file identity;
- file size;
- high-resolution modification/change metadata;
- previously computed content digests;
- bounded adapter-query results;
- conditions under which those results remain reusable.

A remembered digest or query result is reused only while its local validation conditions still hold. Metadata fast paths
assume the supported filesystem's file-identity and change observations; they do not prove that no external mutation has
occurred.

Missing, malformed, or stale memo state causes fresh observation.

`memo/artifacts/` may record successful validation of a native profile:

- manifest-content digest;
- validation-schema revision;
- local file identity/size/change metadata;
- previously verified artifact digests.

Missing or invalid artifact memo state causes fresh validation.

A memo never authorizes unchecked reuse merely because its cache key exists.

Memo formats are internal and disposable.

Memo fast paths depend on machine-local filesystem observations. Copying or sharing memo files across hosts carries no
validity guarantee and need not be detected.

## Completion Manifest and Integrity

Each reusable native profile contains one `manifest.json`.

The manifest records at least:

- schema revision;
- native preparation key;
- Dea input identity;
- native configuration identity;
- supported-toolchain observation needed to explain selection;
- descriptive compiler/target metadata;
- expected artifact roles;
- relative artifact paths;
- artifact sizes;
- content digests.

Descriptive metadata and output inventory do not define the input preparation key.

The manifest is the completion record. There is no second completion flag.

For ordinary creation of an absent/incomplete persistent profile:

1. acquire per-profile preparation coordination;
2. recheck whether another process completed it;
3. produce the required support;
4. compute required integrity information;
5. validate the complete output;
6. write the complete manifest last.

A missing, malformed, or truncated manifest does not authorize reuse.

Consumers validate the expected profile structure. A shortened manifest cannot redefine the expected bundled preparation
as complete.

Managed paths are relative to the profile and may not escape it.

Managed caches are trusted compiler-owned user state. External concurrent modification during preparation or
consumption, and mutations preserving all metadata trusted by a memo fast path, are outside the supported contract.
Within the supported filesystem/change-detection contract, a profile detected as invalid is never consumed. Forced
preparation recomputes observations and output validation without trusting memoized results; it does not add protection
against unsupported concurrent mutation.

Artifact digests detect accidental corruption within that validation boundary. They are not signatures and do not
authenticate an untrusted cache writer. Digest checks are confined to compiler-owned managed artifacts and do not
interpret native object structure or establish another semantic authority. Caller-owned objects and explicit native
inputs retain their existing opaque-input validation boundary.

Ordinary `.l1m` parsing, fingerprints, graph validation, lifecycle checks, and link checks still apply. Cache integrity
does not replace semantic validation.

## Cache Misses, Invalid Entries, and Recovery

The managed cache is derived state.

A profile is not reused when selection or required validation finds it to be:

- absent;
- incomplete;
- incompatible with the requested preparation identity;
- unsupported by the current cache schema;
- invalid under required toolchain observation;
- corrupt under required artifact validation.

When automatic preparation is permitted, failure to reuse a persistent profile must not by itself make an otherwise
compilable command impossible.

For an absent or incomplete profile, ordinary per-key preparation may publish a new reusable profile.

If the implicit default cache is unavailable or unwritable and no valid profile can be read and validated, automatic
preparation uses fresh command-private support without publishing persistent state. An unusable explicitly selected root
remains a configuration error under the cache-root selection rules.

For a completed persistent profile that cannot safely be reused, L1 does not require transparent in-place replacement
while other processes may already be consuming it.

The command may instead use fresh command-private prepared support. When a completed persistent profile is detected as
unusable, default stderr output identifies that fallback and gives the explicit repair guidance below, so repeated fresh
preparation does not hide the persistent problem.

This preserves correctness without introducing immutable cache generations or reader pinning solely for automatic
repair.

Persistent repair of an already completed profile is available through explicit:

```sh
l1c --prepare-stdlib --force
```

when the configuration is eligible for persistent preparation. Report the corresponding command with the same selected
cache root and effective configuration, and state that forced repair requires external serialization against consumers
of that profile. If reuse eligibility cannot be established, explain that `--force` cannot authorize persistent reuse
instead of presenting it as a repair for that limitation.

No indefinite retry is permitted.

If fresh preparation fails, the original command fails with the underlying actionable toolchain error.

With `--no-auto-prepare`, lack of a reusable profile fails without fresh preparation.

## Preparation Coordination

Ordinary persistent preparation of an absent/incomplete native profile is serialized per native key.

One process prepares while another targeting the same key waits, acquires the coordination lock, and rechecks
completion.

Different native keys may be prepared independently.

Coordination ownership follows process lifetime. Lock-file existence alone is not lock ownership.

Do not add:

- cache-wide transactions;
- immutable generations;
- rollback;
- reader pinning;
- project-wide build locks.

Explicit forced replacement remains externally serialized against consumers.

Command-private fresh support, including fallback for an unavailable implicit default or an unusable completed profile,
follows the compiler's ordinary command-owned temporary-storage safety model and does not publish persistent state.

## Output and Diagnostics

Preparation messages go to stderr.

| Verbosity    | Managed-preparation output                                                                                                                       |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Default      | Announce actual preparation needed by the command; ordinary valid reuse is quiet.                                                                |
| `-v` / `-vv` | Add configuration selection, reuse/fresh-preparation reason, cache/profile path where applicable, module progress, and native compiler commands. |
| `-vvv`       | Add identity inputs, adapter/toolchain-observation decisions, memo validation, and artifact-validation decisions.                                |

A normal cache miss followed by successful preparation is progress, not an error.

When recovering from a completed persistent profile detected as unusable, default output states that the cached profile
is unusable and fresh command-private support is being used. Include the applicable `--prepare-stdlib --force` repair
command and its serialization requirement when persistent preparation is eligible. If eligibility cannot be established,
report that limitation without suggesting `--force` can bypass it.

A configuration that is compilable but not persistently reusable may otherwise produce a verbose explanation that fresh
support is being used.

Missing compilers, unsupported required native operation, missing preparation sources, unusable explicitly selected
cache roots, cache roots that violate installed-payload ownership, coordination failures, and failed preparation
terminate the original command with actionable diagnostics. An unavailable or unwritable implicit default follows the
private-preparation fallback rules above rather than making persistent storage a requirement for ordinary compilation.
Explicit prewarming additionally reports ineligible persistent preparation or an unusable persistent destination as an
actionable failure.

Relevant host-compiler errors remain visible.

No repeated retry loop may hide a persistent preparation failure.

## Bootstrap and Prewarming

Repo-local `build-stage1` constructs a complete compiler toolchain by providing the public runtime headers, building
`l1c`, and generating the complete bundled semantic-interface set.

Remove its existing mandatory `runtime` prerequisite for native L1 program archives/objects. Keep public-header
availability independent of archive construction: provide `dea_rt.h` and `l1_real.h` under `$L1_BUILD_DIR/include/` for
the existing repo-local include lookup. Internal runtime headers remain accessible separately as preparation inputs.
Exact helper/target names are implementation details.

This removes eager L1 program-runtime construction, not the L0/bootstrap inputs needed to build the native Stage 1
compiler itself. The standalone `make runtime` developer workflow may remain, but its native products are not an
implicit managed support store. Existing explicit runtime overrides remain available.

Bootstrap or an explicit user-side setup workflow may then prewarm the selected development/user cache for an eligible
default native configuration. Native stdlib/runtime prewarming is separate and optional.

A complete installation remains usable with an absent or empty user cache.

An installer must not require that package installation occur in the eventual user's cache context.

In particular, a system/package-manager install must not populate a root user's cache and treat that as satisfying the
runtime contract for other users.

## Manual Cache Disposal

No cache cleanup subsystem is introduced.

The Dea-owned `<CACHE_ROOT>/v1/` subtree is disposable.

Documentation may instruct users to remove that subtree manually when no compiler/preparation process is consuming it.
The caller-selected `<CACHE_ROOT>` itself may contain unrelated files or sibling directories and must not be described
as disposable. Manual-disposal guidance preserves those unrelated entries and the toolchain's semantic interfaces,
headers, and rebuild inputs.

No age tracking, usage tracking, LRU, automatic pruning, or schema-aware cleanup is required.

Cache growth from intentionally retained valid configurations is accepted for the L1 scope.

## Performance

Resolve the native preparation/reuse context once per compiler command.

Do not repeat toolchain discovery or preparation identity work per module.

Warm validation should avoid rereading large compiler binaries or complete artifact contents when valid machine-local
memo state permits a bounded fast path.

Cold discovery and hashing costs are measured separately from warm reuse.

Reference-machine latency targets may remain internal engineering/regression goals. They are not public cross-platform
guarantees.

## Compatibility

Existing complete explicit standalone-link commands remain valid.

Explicit Dea providers retain precedence over bundled managed providers.

An invocation without `-I` may newly succeed when its missing providers are bundled stdlib/system modules.

A missing project or third-party provider still fails without an explicit object or suitable explicit interface root.

Managed semantic providers are a compiler-owned exception to the ordinary requirement that an interface-backed native
provider already have its sibling object at initial discovery time. Before native link planning, the managed provider is
materialized as a canonical profile `.l1m + .o` pair and then follows the same interface-authority checks.

No caller-owned object or explicit provider is automatically rebuilt.

No external library, foreign object, native search path, rpath, or raw link argument becomes managed preparation state.

The standalone-link `--c-options` documentation is intentionally amended only for generated-C compilation of managed
bundled Dea modules. Runtime implementation flags keep their separate policy, and C options remain excluded from the
final link word stream except through their existing documented effects.

No `.l1m` format or object ABI change is required.

## Shared CLI Contract Realignment

At implementation, align [docs/specs/compiler/cli-contract.md][cli-contract] and the L1 separate-compilation/runtime
documentation with this L1-only extension:

- Add `--prepare-stdlib` to the primary modes and record its no-positional-source-target exception in the operating
  model.
- Document `--stdlib-cache`, `L1_STDLIB_CACHE`, and single-host, single-root selection, including the
  `$L1_BUILD_DIR/cache` repo-local default and per-user installed defaults. Both override forms are explicit selections;
  distinguish their unusable-root error from private preparation when the implicit default is unavailable. Reject roots
  that place managed state inside the installed payload, including through aliases.
- Record the option-mode table: `--stdlib-cache` for build/run/link/preparation, `--no-auto-prepare` for build/run/link,
  and `--force` for explicit preparation only. Other combinations are argument errors. Forced preparation recomputes
  validation without overriding reuse eligibility; explicit prewarming fails for a non-cacheable configuration or an
  unusable persistent destination. Preserve the existing exit-code conventions.
- Accept ordered `--interface-path` / `-I` in standalone link. Extend the complete-explicit-set wording for recursive
  discovery while preserving explicit-provider authority, lifecycle edges, entry selection, and original caller paths.
- Record the exact bundled-provider position in source-resolving modes: explicit interfaces first, then existing
  system-before-project resolution, with the managed semantic set replacing only the compiler-owned bundled position. A
  caller system override that suppresses that position also suppresses managed bundled semantic discovery. Preserve the
  distinct standalone-link order and mode-specific source-fallback restrictions.
- Record native materialization by exact copying of toolchain `.l1m` bytes, without independent interface re-emission.
  Bootstrap generates that set from canonical bundled sources independently of ambient source/interface overrides.
  Semantic-only modes retain normal interface validation without native preparation or source-tree freshness scans.
- Extend the wrapper-only wording for `L1_CFLAGS` / `--c-options` only to generated-C compilation of managed bundled Dea
  modules. Specify compiler-owned runtime flags/tuning, the same selected compiler, applicable target/ABI/sysroot
  configuration, and adapter-selected archive production where needed. Keep the named legacy runtime Make controls out
  of `l1c` configuration. Preserve effective generated-C option order and exclusion from arbitrary final-link words;
  opaque native objects retain their documented possible indirect host-link effects.
- Record runtime-include overrides used in managed compilation in the effective stdlib native configuration.
  Runtime-library overrides retain final-link authority, do not enter `N`, and do not make managed profiles partial.
- Preserve ADR-0036's typed encounter order, native-operand validation, CLI-owned external dependencies, and exact
  runtime paths. Add no native-dependency or cache records to `.l1m`.
- Add no system-cache, cache-scope, cleanup/scrub, migration, or managed-provider-disable surface.

Existing build/run generated-C retention, cross-mode C-byte identity, compile-only publication, runtime selection, and
opaque caller-native-input behavior remain the baseline. Live contracts must be amended with implementation before the
planned surface is treated as available public behavior.

## ADR Impact

- Decision: Extend interface-assisted discovery with managed bundled semantic providers that materialize native pairs
  only when needed.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md`
  - Rationale: Installed bundled interfaces may exist without native siblings; native preparation copies their exact
    bytes into canonical profile pairs before final link planning rather than re-emitting interfaces. Explicit providers
    keep their existing mode-specific sibling-object rules, original paths, and precedence. Interface authority and
    opaque native inputs remain intact; managed integrity checks add no native semantic inspection. C-option effects
    extend only to managed bundled Dea-module compilation.
- Decision: Resolve bundled providers semantically before supplying prepared native pairs to build/run orchestration.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0033-multi-compilation-unit-build-and-run-pipeline.md`
  - Rationale: The managed semantic set replaces only the compiler-owned bundled source position within existing
    system-before-project resolution. Explicit interfaces and authoritative caller source roots retain their behavior;
    system overrides suppress the implicit managed position. Materializing managed pairs preserves
    application/third-party compilation, source-target entry selection, workspaces, common linking, and generated-C
    contracts.
- Decision: Retain canonical managed bundled C without making optional native-profile scratch an artifact authority.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0034-multi-unit-generated-c-retention-tree.md`
  - Rationale: The mirrored tree and application/wrapper copy behavior remain unchanged. Managed nodes regenerate C
    through the canonical module backend using selected toolchain inputs, so reusable profiles need not retain C.
- Decision: Preserve cross-mode module C byte identity when managed support is reused without generated-C scratch.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0035-cross-mode-generated-c-byte-identity.md`
  - Rationale: Managed regenerated C retains the identical-input byte guarantee. Explicit provider nodes still
    contribute no C; application and wrapper retention still copies exact compiler inputs. Tests cover warm profiles
    with missing and poisoned scratch as well as all producer modes.
- Decision: Obtain matching bundled native runtime support on demand without requiring an installed default archive set.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0027-runtime-archive-and-trace-selection-boundary.md`
  - Rationale: Runtime sources and headers are toolchain inputs; native support uses the selected C compiler and
    target/ABI/sysroot with compiler-owned runtime flags and tuning. Legacy runtime Make controls do not become compiler
    configuration. Preserve checking/trace variants, the public header and stable runtime ABI, exact archive selection,
    and TinyCC raw-object handling. Runtime-library overrides remain final-link selections without changing managed
    profile identity or completeness. Bootstrap provides headers independently of native program-runtime construction.
- Decision: Preserve CLI-only ownership and encounter order of external native dependencies when adding managed
  providers.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0036-ordered-external-link-inputs-and-cli-only-dependency-ownership.md`
  - Rationale: Managed bundled discovery does not change external libraries, foreign objects, search paths, rpaths, raw
    link arguments, their validation, or exact runtime-path selection. Final-link-only inputs remain outside native
    preparation identity and `.l1m` semantic records.
- Decision: Require toolchain-owned bundled semantic interfaces and rebuild inputs, with reusable derived native support
  under one local managed cache root with a disposable Dea-owned subtree.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md`
  - Rationale: Bootstrap provides public headers and owns semantic-set generation/freshness from canonical bundled
    sources without requiring native L1 program-runtime artifacts. Installations ship those inputs and cannot become
    managed writable state through cache-root selection. One single-host cache uses per-user installed or build-local
    defaults; cross-host use carries no guarantee and need not be detected. An unavailable implicit default permits
    private preparation for consuming commands. Installed native acceleration, system/project caches, and maintenance
    subsystems remain outside scope.
- Decision: Separate Dea input identity from adapter-defined native preparation identity and conservative
  persistent-reuse eligibility.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: `D` and `N` separate semantic fingerprints from implementation inputs and the distinct stdlib/runtime
    native configurations, including archiver observation when archive production is used. Exact matching covers only
    inputs observed under the schema, adapter, and supported local change-detection contract. Non-cacheable
    configurations use fresh support in consuming commands but fail explicit prewarming, even with `--force`. Memos only
    accelerate validation; no ABI inference, arbitrary host-toolchain proof, or cross-machine cache portability is
    established.

## Diagnostic Assignments

The live [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] and active reservations were rechecked during
implementation. `L1C-2150` through `L1C-2159` now cover storage selection, compiler inputs, coordination, disabled
preparation, toolchain/archiver selection, reuse eligibility, native commands, profile integrity, managed semantic
artifacts and preparation-mode misuse. `L1C-2160` through `L1C-2169` remain reserved in this area. Coverage includes:

- preparation-disabled misses;
- missing/unusable native compiler inputs or an archiver required by the selected preparation route;
- missing, malformed, or internally invalid required semantic artifacts, where normal interface/graph diagnostics need
  bootstrap rebuild or installation-repair guidance;
- explicit persistent preparation requested for a configuration whose reuse eligibility cannot be established;
- required native configurations that cannot be prepared;
- unusable explicit cache roots, or an unusable implicit default when persistent preparation is explicitly requested;
- cache roots that violate installed-payload ownership;
- preparation coordination failures;
- failed managed preparation where a lower-level diagnostic is insufficient;
- persistent-profile integrity/validation failures when fresh preparation cannot satisfy the command;
- invalid preparation-mode combinations.

Do not allocate diagnostics for:

- system cache;
- cache scope;
- cleanup/scrub;
- cache migration;
- cross-machine cache portability;
- project-cache state.

A normal miss followed by successful preparation remains informational. No diagnostic is required to detect semantic-set
staleness from using edited repo-local toolchain inputs without rerunning bootstrap, or to detect unsupported cross-host
cache use.

Existing interface, provider, fingerprint, lifecycle, entry, graph, cycle, and provenance diagnostics remain
authoritative. Update `L1C-2031` to accept `--interface-path` in standalone-link mode, and reuse existing CLI
diagnostics for invalid mode/option combinations where appropriate. Discovery does not reserve a second
preparation/cache diagnostic block.

## Verification Criteria

The feature is complete when all of the following hold.

01. A toolchain with no native cache can build/link a program using bundled stdlib providers by preparing matching
    native support automatically.
02. Removing Dea-owned `<CACHE_ROOT>/v1/` does not change successful compilation semantics. Manual-disposal guidance
    preserves unrelated root siblings and the toolchain's semantic set, public headers, and rebuild inputs.
03. Repo-local `build-stage1` provides `dea_rt.h` and `l1_real.h` under `$L1_BUILD_DIR/include/`, builds `l1c`, and
    generates/verifies the complete semantic set under `$L1_BUILD_DIR/interfaces/` without native L1 program
    stdlib/runtime preparation. Generation selects canonical bundled sources despite ambient `L1_SYSTEM`, project-root,
    or interface-path overrides. Bootstrap owns regeneration after interface-generating inputs change; semantic-only
    commands do not rehash sources to detect a skipped rebuild. Missing, malformed, or internally invalid interfaces
    receive rebuild/repair guidance. Installed toolchains ship the semantic set and headers; compile-only imports need
    no native sibling providers.
04. Native-consuming managed providers are materialized as canonical `.l1m + .o` pairs before final link planning.
    Profiles contain module pairs, runtime native outputs, and the manifest; runtime headers are consumed from the
    toolchain, with no per-profile `include/` copy. Explicit header overrides retain their authority.
05. A managed native pair contains the exact selected toolchain `.l1m` bytes. Native preparation never independently
    re-emits bundled interfaces; profile validation rejects a differing copy.
06. Standalone link preserves explicit Dea objects, ordered `-I`, then managed bundled providers. Source-resolving modes
    retain explicit interfaces followed by existing system-before-project resolution; the managed set occupies only the
    compiler-owned bundled position. Cover explicit `--sys-root` suppression, existing `L1_SYSTEM` selection,
    `--project-root` keeping its existing position, and caller-selected sources remaining source-backed where allowed.
07. Invalid explicit or `-I` providers remain errors and are not repaired from the managed cache.
08. Standalone discovery links only the required bundled dependency closure.
09. Application and third-party dependency sources are not implicitly compiled by standalone link or compile-only.
10. A compiler-owned input change represented by `D` invalidates native-profile reuse even if public interface
    fingerprints remain unchanged. Development acceptance follows the bootstrap-owned freshness workflow before using
    edited interface-generating inputs; native identity does not imply a semantic-only freshness check.
11. A native preparation input represented by `N` selects a different profile when changed, including effective stdlib
    compile options, compiler-owned runtime flags/tuning, and target/checking/trace configuration. Ambient Make-only
    runtime controls and process-time runtime retuning do not select different managed profiles.
12. Returning to an existing valid `N` reuses the existing profile.
13. Supported adapter observations invalidate reuse when their documented relevant native environment changes. Include
    the adapter-selected archiver where used; TinyCC raw-object preparation has no archiver observation or dependency.
14. An adapter that cannot validate persistent reuse must not authorize a cache hit merely because the compiler
    invocation remains executable.
15. A compilable configuration that is ineligible for persistent reuse can still compile through fresh preparation when
    automatic preparation is enabled.
16. `--no-auto-prepare` permits valid reuse but fails instead of performing fresh preparation. Enforce the option-mode
    table, including rejection of `--stdlib-cache` in compile-only, generated-C, and semantic-only modes, and rejection
    of `--prepare-stdlib --no-auto-prepare`.
17. `--prepare-stdlib` populates the selected cache for a persistently reusable supported configuration. A non-cacheable
    configuration fails explicit preparation with actionable guidance and no reusable publication or unused temporary
    preparation, including when `--force` is supplied.
18. `--prepare-stdlib --force` recomputes toolchain observation, native identity, and profile validation without
    trusting memoized results. It never bypasses adapter requirements or reuse eligibility and retains the documented
    external serialization requirement.
19. Managed bundled Dea-module compilation uses effective `L1_CFLAGS` / `--c-options` in their existing order. Runtime
    compilation uses the same selected compiler, compiler-owned flags/tuning, checking/trace settings, and applicable
    target/ABI/sysroot, without wholesale application-option forwarding or host-default target substitution. Verify that
    `l1c` does not read `L1_RUNTIME_CC`, `RUNTIME_CFLAGS`, `L1_RT_QUARANTINE_MAX_BYTES`, `L1_RT_QUARANTINE_MAX_COUNT`,
    or `AR` as managed configuration. Inspect both native command classes; C options do not become arbitrary final-link
    words.
20. Runtime-include overrides used for managed bundled generated-C compilation enter the effective stdlib native
    configuration. Runtime-library overrides retain final-link selection authority without entering `N` or producing
    partial profiles; fresh preparation still produces complete managed runtime support. Verify both CLI and environment
    overrides. Other final-link-only external options likewise do not select a different native preparation identity.
21. Interrupted ordinary preparation does not publish a complete reusable profile.
22. Concurrent ordinary preparation for the same absent/incomplete key serializes and yields one complete reusable
    profile.
23. Different native keys may prepare independently.
24. Missing/invalid memo state causes fresh validation rather than unchecked reuse.
25. Artifact-integrity validation does not replace normal `.l1m`, graph, lifecycle, or link validation.
26. A profile detected as corrupt or otherwise unusable is never consumed. Validation covers the supported local
    filesystem/change-detection contract; it does not claim detection of external concurrent modification or mutations
    preserving every metadata field trusted by the fast path.
27. When automatic preparation is allowed, an unusable persistent profile does not by itself prevent an otherwise valid
    command from obtaining fresh compiler-owned support.
28. Fresh recovery does not require unsafe in-place replacement of a completed profile.
29. Failed fresh preparation reports the underlying actionable error and does not retry indefinitely.
30. Preparation never modifies the installed toolchain payload. Reject any selected root whose managed `v1/` subtree
    lies within that payload, including `--stdlib-cache "$L1_HOME"` and path aliases that resolve there.
31. Unusable roots explicitly selected through either `--stdlib-cache` or `L1_STDLIB_CACHE` fail. An unavailable or
    unwritable implicit default permits a readable, valid profile hit or fresh command-private preparation for build/run
    and standalone link when automatic preparation is enabled; `--prepare-stdlib` fails, and `--no-auto-prepare` fails
    if no valid reusable profile can be read and validated. No alternate persistent root is selected. Verify
    CLI-over-environment precedence, relative explicit paths, `$L1_BUILD_DIR/cache` for repo-local invocations, and
    per-user platform defaults for installed invocations. Cross-host use carries no reuse guarantee and need not be
    detected or bound to a host identity.
32. The compiler does not infer a project root or create application/third-party build-cache state.
33. No system/shared cache, cross-machine reuse contract, cache migration, cleanup subsystem, usage tracking,
    expiration, or automatic pruning is required.
34. Cache hits are quiet by default; actual preparation is reported on stderr. Recovery from a completed profile
    detected as unusable explains the fresh fallback at default verbosity and gives the matching forced-repair command
    and serialization requirement when eligible. Otherwise it explains why forced persistent preparation cannot help.
35. Native preparation context is resolved once per command, not once per module.
36. Existing entry, lifecycle, native-input ordering, provenance, and explicit-provider workflows continue to pass.
    Cover explicit providers after consumers, duplicate module identities, first-selected-interface failures, transitive
    dependency deduplication, unrelated-provider exclusion, insertion before the first explicit root needing a
    dependency, cycles, entry ambiguity, and unchanged `require`/`link` reachability. Preserve compile-only publication,
    build/run `--keep-c`, and cross-mode C-byte identity.
37. No `.l1m` format or object ABI change is required.
38. The bootstrap/productization handoff no longer requires installed native prepared support for compiler correctness.
    Read-only installation fixtures ship semantic interfaces and rebuild inputs only. A cold or manually emptied user
    cache permits build/run and standalone link; `--no-auto-prepare` succeeds only after valid reusable preparation.
    Prewarming remains optional and is not tied to the installer's user context.

## Previous Implementation Assessment

The local `codex/stdlib-runtime-preparation` branch was inspected before porting. Components are classified by their
responsibility under this revised plan:

- Reusable unchanged: SHA-256 and JSON primitives, filesystem metadata and bounded subprocess helpers, process-lifetime
  per-key locks, dependency ordering, explicit provider validation, transitive standalone discovery and operand
  ordering.
- Reusable after simplification: input/toolchain observation and digest memos, completion inventories and validation,
  native compilation, runtime variants and TinyCC objects, command integration, diagnostics, concurrency and corruption
  regressions. These now serve one native cache and bootstrap-owned semantic interfaces.
- Obsolete: persistent semantic profiles, installed/system native lookup, separate state roots, host identity binding,
  portable library-store assumptions, cleanup/scrub, cache scope, native profile import/export, and per-profile headers.

Implementation is local to the present worktree, based on `codex/lean-l1-stdlib-cache-plan`.

## Implementation / Realignment Phases

1. **Preserve provider-discovery semantics**

   - retain explicit-provider authority, ordered `-I`, managed bundled fallback, dependency-closure discovery, and
     existing graph/link checks;
   - replace only the compiler-owned bundled source position, preserving effective system-root overrides and
     project-root order without adding a new source-mode provider tier;
   - make bootstrap own semantic-set freshness, generate it from canonical bundled sources independently of ambient
     overrides, and materialize native pairs by exact interface copying.

2. **Reduce preparation ownership**

   - select one single-host local managed cache root, with per-user installed defaults and `$L1_BUILD_DIR/cache` for
     repo-local use, without host-ID detection machinery; scope manual disposal to Dea-owned `<CACHE_ROOT>/v1/`;
   - reject cache-root selections that place managed state within the installed payload, including path aliases;
   - remove installed-native/system-cache assumptions and cached runtime-header copies;
   - remove the mandatory native `runtime` dependency from `build-stage1`, while independently providing public headers
     and retaining compiler-construction inputs before generating semantic interfaces;
   - retain per-key preparation, completion manifests, integrity validation within the supported change-detection
     contract, and machine-local fast-path memoization.

3. **Narrow reuse guarantees**

   - retain `D` and `N`, with distinct effective stdlib and compiler-owned runtime configurations that honor the
     selected compiler/target; keep legacy runtime Make controls outside `l1c`;
   - observe the adapter-selected archiver only where archive production uses one;
   - include runtime-header overrides used for managed compilation in the stdlib configuration; keep runtime-library
     overrides as final-link selections without changing profile identity or completeness;
   - make persistent-reuse eligibility adapter-defined and conservative;
   - permit fresh command-private support for consuming commands when a configuration is compilable but not safely
     reusable or the implicit default cache is unavailable, while rejecting explicit persistent preparation in those
     cases and preserving unusable-root errors for explicit storage selections.

4. **Reduce CLI and maintenance surface**

   - retain explicit preparation, cache-root override, `--no-auto-prepare`, and explicit `--force`, which recomputes
     validation without overriding reuse eligibility; enforce their stated mode scopes;
   - provide actionable default output for fresh recovery from an unusable completed profile;
   - remove system-cache, scope, cleaner/scrub, migration, and managed-provider-disable concepts from this feature.

5. **Align existing contracts**

   - amend ADR-0027, ADR-0030, ADR-0033, the shared CLI contract, separate-compilation docs, and runtime docs;
   - revise bootstrap productization to ship the required semantic set and rebuild inputs without installed native
     profiles or native-profile export/lookup machinery;
   - update diagnostics and acceptance tests to the simplified contract.

## Implementation Results

1. Bootstrap now supplies both public runtime headers and all 23 verified bundled semantic interfaces using the newly
   built frontend. Standalone link discovers ordered providers without source fallback; source modes retain canonical
   bundled-system placement, explicit-provider authority and source-target ownership.
2. The private native service uses one `v1/` tree, exact semantic copies, complete artifact inventories,
   process-lifetime per-key locks and completion-last publication. Installed payload aliases are protected; unavailable
   implicit storage and corrupt completed profiles use bounded private recovery where allowed.
3. Content-sensitive `D` and adapter-defined `N` retain separate generated-C and compiler-owned runtime configurations.
   GCC, Clang/Apple Clang and TinyCC paths observe their required inputs or decline persistent reuse. Tests cover actual
   runtime variants, target settings, archivers, response/config files, conditional headers, memo invalidation and quiet
   warm reuse. Scratch regeneration cannot inherit stale quoted headers.
4. The CLI exposes only preparation, cache-root selection, disabled automatic preparation and preparation-only force.
   Mode tests reject removed/meaningless controls. Recovery guidance preserves effective options, including literal
   Windows argument vectors; force does not override reuse eligibility.
5. CLI, diagnostics, separate-compilation, runtime, architecture/status docs and productization handoff now describe the
   simplified contract. Retained-C ADRs also distinguish application copying from canonical managed regeneration without
   making profile scratch authoritative. Existing harnesses explicitly obtain developer runtime fixtures when testing
   application-only host commands, and retain cold/warm stdin forwarding through `--run`.

Each implementation phase received an independent read-only review. Valid findings were evaluated and fixed before the
next phase. The independent complete-unit review also finished with no remaining actionable findings after the fixes
below.

The complete-unit review identified two additional implementation defects: malformed unreferenced bundled interfaces
could escape preparation-time semantic checks, and unbound optional string results leaked during native selection.
Preparation now validates the complete selected interface graph before reuse or miss decisions, including
`--no-auto-prepare`. Owned local bindings restore normal cleanup of executable and runtime-override strings. Regression
tests cover missing and malformed `std.types` interfaces, and a dedicated trace harness supplies controlled compiler and
runtime-override inputs after the ordinary runner's environment sanitization.

## Validation Results

The `test-all` tier applies because this work changes native runtime configuration and allocation-bearing compiler
control flow. All implementation and test inputs remained unchanged during final validation and subsequent documentation
closure; their recorded content digests were rechecked before finalization.

- From `l1/`, `L1_TEST_JOBS=6 make test-all L1_BUILD_DIR=build/stdlib-preparation-validation` with an explicit prepared
  L0 Stage 2 compiler supplied through `L1_BOOTSTRAP_L0C` passed all 80 normal tests, environment stackability, all four
  examples, and all 46 default dedicated ARC/memory trace checks. Every trace check reported zero object and string
  leaks.
- The additional `preparation_ownership_test.py` was introduced after aggregate discovery and passed separately with the
  same build and bootstrap selections. Run it from `l1/` with
  `L1_BUILD_DIR=build/stdlib-preparation-validation ../.venv/bin/python compiler/stage1_l0/tests/preparation_ownership_test.py`,
  supplying the same `L1_BOOTSTRAP_L0C`. It forces automatic compiler discovery and an explicit runtime override after
  test-environment sanitization, then requires zero trace errors and leaks.
- Independent final-review probes rejected missing, malformed, and fingerprint-invalid `std.types` interfaces in all
  four combinations of preparation, forced preparation, standalone link, and link with automatic preparation disabled.
  All 12 probes produced bootstrap-repair guidance before native work or completion publication.
- Focused service tests compiled the C support with strict warnings and covered identity, inventory integrity, storage,
  coordination, runtime variants, adapters, overrides, and recovery. CLI and integration tests covered discovery,
  precedence, retained C, corruption repair, and read-only installed payloads.
- Live documentation links and active ADR Impact validation passed. Staged whitespace, staged ADR Impact validation, and
  root pre-commit hooks form the final commit gates.

Native execution was validated on macOS with Apple Clang 17 and TinyCC. Genuine GCC execution and Linux/Windows host
execution were unavailable in this environment; those paths have adapter/fixture coverage and static review.
Installation and distribution implementation remain owned by the separate bootstrap productization plan.

## Non-Goals

- Application or third-party source dependency builds inside compile-only or standalone link.
- Application-output caching.
- Project-root discovery.
- Persistent project configuration owned by `l1c`.
- Project build profiles.
- A Dea build/package system.
- Automatic project-directory discovery.
- Automatic native-library discovery.
- Rebuilding caller-supplied objects.
- Proving compatibility of caller-supplied native objects.
- ABI inference between different native profiles.
- A machine-wide or shared system cache.
- Cross-machine prepared-artifact portability or machinery to detect cross-host use and bind caches to host IDs.
- A stable external cache format.
- Arbitrary persistent reuse through opaque wrappers or unsupported host-toolchain arrangements.
- Exhaustive recursive fingerprinting of an entire compiler installation or SDK.
- Detecting semantic-set staleness from using edited repo-local bundled inputs without rerunning the bootstrap build.
- Promoting legacy runtime Make variables into managed compiler configuration.
- Cache schema migration.
- Cache cleanup/scrub commands.
- LRU, expiration, age tracking, usage tracking, or automatic pruning.
- Cache-wide transactions.
- Immutable publication generations.
- Reader pinning.
- Automatic persistent repair of completed profiles under concurrent consumption.
- Installed native acceleration.
- Installation/distribution implementation itself.
- A new public runtime-export API for generated-C consumers.
- Changes to `.l1m` format or object ABI.

## Closure

The following closure requirements were satisfied:

- bootstrap independently provides public headers and owns semantic-set generation/freshness without mandatory native L1
  program-runtime preparation;
- managed source-mode providers occupy exactly the existing compiler-owned bundled position, and native preparation
  copies the selected interface bytes exactly;
- the shared preparation pipeline retains its distinct persistent and command-private publication policies;
- the shared CLI contract reflects the final preparation surface;
- standalone-link C-option semantics preserve separate generated-C and compiler-owned runtime configurations, selected
  target/ABI/sysroot settings, and archiver observation where required;
- ADR-0027, ADR-0030, ADR-0033, ADR-0034, ADR-0035 and the new preparation/reuse ADRs are aligned, with ADR-0036's
  preserved contract and Related Plans link recorded;
- the bootstrap productization plan's payload, lookup, metadata, and acceptance requirements use semantic interfaces and
  rebuild inputs without installed native-profile machinery;
- diagnostics and tests cover the verification criteria;
- no removed system/shared-cache, cleaner, migration, or project-cache requirement remains as a closure dependency.

Validation includes focused CLI, graph, link, preparation/cache, bootstrap and installed-context checks followed by L1
`make test-all`, ADR validation and the required pre-commit checks. Independent read-only reviews cover each phase and
the complete unit before finalization.

[backend]: ../../../../docs/reference/c-backend-design.md
[bootstrap-productization]: ../../tools/2026-04-02-l1-bootstrap-productization-noref.md
[build-run]: ../../../../docs/decisions/0033-multi-compilation-unit-build-and-run-pipeline.md
[cli-contract]: ../../../../../docs/specs/compiler/cli-contract.md
[diagnostics]: ../../../../../docs/specs/compiler/diagnostic-code-catalog.md
[external-inputs]: ../../../../docs/decisions/0036-ordered-external-link-inputs-and-cli-only-dependency-ownership.md
[interface-authority]: ../../../../docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md
[link-discovery]: 2026-09-07-standalone-link-interface-discovery-noref.md
[runtime-selection]: ../../../../docs/decisions/0027-runtime-archive-and-trace-selection-boundary.md
[separate-compilation]: ../../../../docs/reference/separate-compilation.md
