# L1 Bundled Interfaces and Native Preparation

Version: 2026-09-11

L1 supplies bundled semantic interfaces with the toolchain and derives native stdlib/runtime support when a command
needs it. Preparation covers only compiler-owned `std.*` and `sys.*` modules and runtime implementation sources.
Application and third-party objects remain caller-owned inputs.

## Bootstrap and semantic discovery

From `l1/`, `make build-stage1` builds the Stage 1 compiler, provides `dea_rt.h` and `l1_real.h` under
`$L1_BUILD_DIR/include/`, then generates and verifies all bundled `.l1m` files under `$L1_BUILD_DIR/interfaces/` using
the new frontend and canonical bundled sources. Ambient source roots, native cache settings, and C compiler overrides do
not redirect that semantic build. It does not build native L1 program-runtime archives. The upstream L0 inputs needed to
construct Stage 1 are still required.

Ordinary semantic analysis, interface emission, generated C, and compile-only imported-provider resolution use those
interfaces without preparing native support, probing a C compiler for reuse, or hashing the bundled source tree.
Compile-only invokes the C compiler for its requested module, but does not compile imported providers. Rebuild Stage 1
after editing compiler or bundled inputs that generate interfaces. Running an old semantic set after such edits is
outside the supported development workflow. Missing or invalid bundled interfaces report `L1C-2158`
bootstrap/installation repair guidance alongside any normal semantic diagnostics.

In source-resolving modes, explicit interfaces retain their existing authority. Managed interfaces occupy exactly the
canonical bundled system-root position. System roots still precede project roots; explicit `--sys-root` suppresses the
default bundled position, and `L1_SYSTEM` retains its existing root-selection meaning. Bundled sources selected through
a project root remain source-backed. The requested target always resolves from source. Compile-only never falls back to
imported non-virtual provider source. Source inspection with `--all-modules` retains the full source view.

Standalone link searches explicit Dea objects, ordered `-I` roots, then known bundled managed providers. It never falls
back to source. The first selected explicit provider remains authoritative even when invalid. Discovered objects follow
dependency order immediately before the first explicit root that needs them; explicit operands retain their relative
order. Fingerprints, entry, lifecycle, cycle, and provenance validation remain mandatory.

## Native workflow and CLI

```sh
l1c --compile app.l1 -o app.o
l1c --link app.o -o app
l1c --run app.l1
l1c --prepare-stdlib --c-compiler clang
l1c --build --c-compiler clang --no-auto-prepare app.l1 -o app
```

Build/run/link automatically reuse or prepare matching support. Cache hits are quiet. Actual preparation and corruption
recovery go to stderr; increasing `-v` exposes selection, commands, identity observations, memo decisions, and artifact
validation. Native compiler errors remain visible.

| Control               | Scope and meaning                                                                                      |
| --------------------- | ------------------------------------------------------------------------------------------------------ |
| `--prepare-stdlib`    | Primary mode with no target: produce a persistently reusable complete native profile.                  |
| `--stdlib-cache PATH` | Build, run, link, preparation: select the one cache root.                                              |
| `L1_STDLIB_CACHE`     | Environment cache selection, overridden by the CLI option; both selections are explicit.               |
| `--no-auto-prepare`   | Build, run, link: require valid reusable support and fail on a miss.                                   |
| `--force`             | Preparation only: recompute observations and identity, then rebuild and validate the selected profile. |

Preparation accepts the selected C compiler, generated-C options, runtime include override, checking/trace controls, and
`--no-line-directives`. It accepts no source/project/interface roots, runtime-library override, output, retained C,
foreign/external link operands, or program arguments. Cache controls are errors in semantic-only modes;
`--prepare-stdlib --no-auto-prepare` is invalid. Force cannot override reuse eligibility. The shared mode contract is in
[docs/specs/compiler/cli-contract.md][cli].

## Ownership and storage

The root is selected once: `--stdlib-cache`, then `L1_STDLIB_CACHE`, then the context default. Relative explicit paths
resolve from the invocation directory.

| Context           | Default                                               |
| ----------------- | ----------------------------------------------------- |
| Repository        | `$L1_BUILD_DIR/cache`                                 |
| Installed Linux   | `$XDG_CACHE_HOME/dea/l1`, otherwise `~/.cache/dea/l1` |
| Installed macOS   | `~/Library/Caches/dea/l1`                             |
| Installed Windows | Local AppData / `Dea/L1/Cache`                        |

Only `<CACHE_ROOT>/v1/` is Dea-owned. The root itself can contain unrelated files. Internal storage contains
`native/<N>/`, per-key `locks/native-<N>.lock`, and disposable `memo/toolchains/` and `memo/artifacts/` records. There
is no semantic-interface cache, installed native store, system/shared cache, host identifier, project database, cleaner,
scrubber, migration, or automatic pruning. Cross-host copying/sharing has no reuse guarantee.

A reusable profile contains exact byte copies of the selected toolchain `.l1m` files, sibling native objects, matching
runtime support, and a completion manifest. Public headers remain toolchain inputs. Generated C and runtime-build
scratch are optional, not inventory authority. Rebuilding clears known preparation scratch so stale quoted headers
cannot affect compilation. Build/run `--keep-c` regenerates canonical managed module C from the same toolchain inputs;
it does not trust or require cached C scratch. The cross-mode C-byte contract remains unchanged.

An explicitly selected unusable root is an actionable configuration error. An unavailable implicit default may still
serve a valid readable hit; otherwise consuming commands may prepare fresh command-private support. They do not select
another persistent root. `--prepare-stdlib` requires a usable persistent destination; `--no-auto-prepare` never builds
private support. Installed preparation rejects cache `v1/` subtrees overlapping the active payload, including path
aliases, and never writes into the installation.

Installed payloads provide equivalent verified semantic interfaces plus compiler, stdlib/runtime sources, headers, and
other rebuild inputs. This feature validates that contract with fixtures; installation, distribution, and relocation
workflows remain future work in [l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][productization].

## Native configuration and reuse

`D` is a content-sensitive identity for the effective compiler and compiler-owned preparation inputs, including the
selected semantic bytes. In development it tracks working inputs, not a Git revision alone. Native preparation computes
it; semantic-only commands do not use it as a bootstrap freshness check.

`N` combines `D`, the supported toolchain observation, and separate effective stdlib and runtime configurations. A
change selects a different complete profile; there is no cross-`D` per-module reuse or ABI inference between keys.
Application paths, project roots, dependency graphs, output paths, and final-link-only operands do not enter `N`.

Both native compilation classes use the selected L1 C compiler. Bundled generated C uses `L1_CFLAGS` followed by
`--c-options` and the normal generated-C defaults. Standalone link applies these options to managed module preparation
as well as its wrapper; it never appends them as arbitrary final-link words. Runtime implementation C uses the
compiler-owned `-O2 -std=c99` baseline, variant defines, and default checked quarantine tuning of 16 MiB / 4096 records.
Supported target, CPU, ABI, and sysroot settings reach both classes; arbitrary application defines/optimization flags do
not become runtime flags. Clang configuration/response files are observed, target settings are extracted, and automatic
config loading is disabled for runtime compilation after successful observation.

`L1_RUNTIME_CC`, `RUNTIME_CFLAGS`, `AR`, and `L1_RT_QUARANTINE_MAX_*` are Make/developer controls, not managed
preparation inputs. Process-time `DEA_RT_QUARANTINE_MAX_*` retuning does not change a profile. A runtime-include
override participates in stdlib native configuration and header observation; a runtime-library override remains
final-link-only. A prepared profile remains complete even when the current command links another runtime.

GCC, Clang/Apple Clang, and TinyCC have bounded adapters. They observe compiler/version/target information, required
components, header dependencies and search candidates, SDK/selection information, and relevant implementation-library
inputs. Archive-producing paths select and observe the compiler's archiver. TinyCC produces the full matching raw
runtime-object set and requires no archiver. All variants preserve the runtime ABI and exact-path final selection.

An adapter authorizes persistent reuse only when its required observations succeed. Opaque wrappers, plugins, profile or
LTO indirection, and unsupported backend controls decline reuse. Clang external-assembler selection, including
`-fno-integrated-as` and `-no-integrated-as`, currently uses fresh support rather than persistent reuse. A compilable
configuration can therefore succeed through private preparation while explicit prewarming fails. Missing required
compilation tools still fail with actionable diagnostics.

Toolchain and artifact memos accelerate validation; they are never semantic authority. Reliable file metadata permits
unchanged-content fast paths. Missing, malformed, or stale records cause fresh observation/hashing. Toolchain
observation selection includes `D`, so implementation changes cannot inherit older eligibility decisions. Header
dependencies cover generated checking/real/float branches, runtime translation units, and earlier search candidates.
Metadata-preserving external mutation and concurrent external input changes are outside the contract. These checks do
not prove cache portability.

## Integrity and recovery

The sole completion manifest is published last, after the complete declared inventory is validated. It records `D`, `N`,
effective configurations, toolchain description/observation, artifact roles, relative paths, sizes, and SHA-256 values.
Validation rejects malformed/shortened records, traversal/escape, absent artifacts, digest failures, and profile
interfaces that differ from the selected semantic bytes. Native bytes are hashed for managed integrity but remain
semantically opaque; parsing, fingerprints, graph and lifecycle checks still come from `.l1m`. Preparation validates the
complete selected interface graph, including modules not imported by other bundled sources, before reuse or miss
decisions. Malformed toolchain inputs receive repair guidance even with `--no-auto-prepare`.

Absent/incomplete same-key preparations serialize under a process-lifetime lock and recheck after waiting. Different
keys can prepare independently. Lock-file existence alone is not ownership, and process exit releases the lock. No
cache-wide transaction, reader pinning, or profile generation mechanism is provided.

A completed corrupt profile is never consumed or automatically replaced. Consuming commands prepare private support and
print a matching `--prepare-stdlib --force` repair command when persistence is eligible. Forced replacement must be
externally serialized against consumers. Windows guidance reports a literal argument vector to avoid cmd.exe expansion.
Ineligible configurations receive fresh-preparation guidance without a misleading force remedy.

To discard cached support, externally serialize deletion of the Dea-owned `<CACHE_ROOT>/v1/` subtree against users. Keep
unrelated files beside `v1/`. Later native commands reconstruct support from toolchain inputs. `make runtime` remains a
developer workflow for standalone runtime archives/objects; its products are not an implicit managed cache. Generated-C
users compiling outside `l1c` arrange their own matching runtime.

[cli]: ../../../docs/specs/compiler/cli-contract.md
[productization]: ../../work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md
