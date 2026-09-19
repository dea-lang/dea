# L1 Bundled Interfaces and Native Preparation

Version: 2026-09-15

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

## CI capability reporting

From `l1/`, run the focused reporter with an exact compiler name or path:

```sh
python3 scripts/check_preparation_reuse.py --c-compiler clang --expect available
```

The reporter resolves that executable directly without the integration fixtures' filename-based compiler fallback. It
records the requested and resolved paths, version, target and preparation's compiler identity. A copied toolchain and
initially empty writable cache isolate the probe from installed inputs and existing prepared profiles. No runtime
library override or retained-C mode is used.

Separate processes run a tiny `std.io` consumer cold, warm with automatic preparation, and warm with
`--no-auto-prepare`. Available reuse requires correct program output, one native resolution per command, one complete
bundled validation on the cold consumer and zero bundled re-analysis on both warm runs, cold compilations matching the
current bundled inventory, and the same persistent entry with zero managed compilations and preparation build commands
in both warm runs. A size-changing edit to a copied runtime header must then cause guarded rejection and ordinary
preparation of a new persistent key. All other counters are recorded without platform-independent discovery-probe or
timing thresholds.

Results are `available`, `private`, `unsupported`, `error`, or `not-run`. Private capability requires two successful
ordinary consumers that rebuild managed support, a repeatable recognized ineligibility reason, no publication, and
guarded refusal. Unsupported capability currently recognizes the Clang runtime-archiver boundary only when a separate
probe confirms rejection of `--no-default-config`. Other resolution failures remain errors until their boundary is
explicitly supported by the reporter. Neither `L1C-2154` nor zero compilations alone establishes a capability outcome.
Input-stability failures, failed compiler observations, invalid fixtures, timeouts and crashes remain errors. Missing
bootstrap artifacts produce `not-run`; both categories fail even with `--expect observe`.

`--expect available` is the CI requirement for the existing full-suite configurations. `--expect private`,
`--expect unsupported`, and `--expect observe` are explicit local probe modes; observation accepts only completed
capability measurements. They do not weaken or skip the strict preparation integrations. Compiler matrix expansion is
separate work.

The shared L1 CI action runs the reporter after its Make target, including after test failure when the bootstrap is
complete. It always publishes the Markdown summary and uploads the existing L1 workdir artifact. The default
`l1/build/ci/preparation-reuse/` directory retains `report.json`, `summary.md`, invocation argv, stdout/stderr, and
observed persistent manifests. Failed expectations and partial measurements are retained; unexecuted measurements are
null. `--output-dir`, `--build-dir`, and the per-process `--timeout` can be overridden for local diagnostics. A missing
report is a CI error and does not mask an earlier Make failure.

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

On Windows, implementation-library discovery reads normal PE32/PE32+ import names directly, then applies the existing
DLL search and recursive observation rules. Checked file ranges and bounded section, descriptor and name counts keep
inspection independent of unrelated code, resource and unwind-table sizes. Malformed or unsupported observations decline
persistent reuse through the existing eligibility diagnostic. The general subprocess-output limit is unchanged. Native
compiler probes use the selected executable as their process application name. Compiler-reported tool paths accept
native, MSYS-style and extensionless Windows spellings before they enter the identity.

An adapter authorizes persistent reuse only when its required observations succeed. Opaque wrappers, plugins, profile or
LTO indirection, and unsupported backend controls decline reuse. Clang external-assembler selection, including
`-fno-integrated-as` and `-no-integrated-as`, currently uses fresh support rather than persistent reuse. A compilable
configuration can therefore succeed through private preparation while explicit prewarming fails. Missing required
compilation tools still fail with actionable diagnostics.

Toolchain and artifact memos accelerate validation; they are never semantic authority. Reliable file metadata permits
unchanged-content fast paths. Missing, malformed, or stale records cause fresh observation/hashing. Toolchain
observation selection includes `D`, so implementation changes cannot inherit older eligibility decisions. Header
dependencies cover generated checking/real/float branches, runtime translation units, and earlier search candidates.

GCC/Clang dependency output is decoded using the compiler's Make quoting before resolving paths. Ordinary backslashes in
that output remain filename bytes on POSIX and path separators on Windows; escaped whitespace, hash signs and dollars
retain their filename meaning. A compiler that loses the original filename spelling cannot authorize reuse through that
dependency. Compiler-image inspection errors decline persistent reuse without disabling invocable fresh preparation.

Metadata-preserving external mutation and concurrent external input changes are outside the contract. These checks do
not prove cache portability.

Within one native-resolution command, response and configuration files are parsed once per lexical absolute path and
syntax. The direct argument root and each selected configuration root share expanded views for runtime target selection,
eligibility and dependency observation. Repeated includes preserve argument order and multiplicity; the original native
invocation words remain unchanged. Ordinary response includes resolve from the invocation directory, while configuration
includes resolve from each including file's directory. These views are discarded when native resolution finishes; later
invocations still observe changed option inputs through the normal validation rules.

## Integrity and recovery

The sole completion manifest is published last, after the complete declared inventory is validated. It records `D`, `N`,
effective configurations, toolchain description/observation, artifact roles, relative paths, sizes, and SHA-256 values.
Validation rejects malformed/shortened records, traversal/escape, absent artifacts, digest failures, and profile
interfaces that differ from the selected semantic bytes. Native bytes are hashed for managed integrity but remain
semantically opaque; parsing, fingerprints, graph and lifecycle checks still come from `.l1m`. Preparation validates the
complete selected interface graph, including modules not imported by other bundled sources, before any native
construction. A valid warm hit skips that repetition by reusing the completed manifest: its identity and `D` equality
certify that the current validator already completed the full bundled validation over the current selected inputs, so
the umbrella analysis is not repeated, and any input change alters `D` and re-enables the complete pass. Malformed
toolchain inputs receive repair guidance even with `--no-auto-prepare`.

The command retains only the validated bundled module names in dependency order for native construction and any private
fallback retry. It releases the umbrella analysis and workspace before compiling modules. Build/run retain their initial
application analysis and bind managed native artifact paths after preparation proves exact semantic copies. Semantic
origin paths and loaded source snapshots continue to identify the original semantic inputs. Per-module source analysis
and final native sibling/provenance checks remain separate required compilation and linking boundaries.

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
