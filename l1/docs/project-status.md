# L1 Project Status

Version: 2026-10-08

This document summarizes what is implemented in the Dea/L1 subtree today.

Dea/L1 currently supports local self-hosted development:

- the bootstrap compiler is `compiler/stage1_l0/`, implemented in Dea/L0; Stage 2 is implemented in Dea/L1
- the current shared assets are `compiler/shared/l1/stdlib/` plus the copied runtime sources under
  `compiler/shared/runtime/`
- `compiler/stage2_l1/` contains the self-hosted L1 compiler and its validation workflow

L0 remains the active release line. The L1 subtree is the current home for bootstrap compiler work, library surface, and
future language growth beyond L0.

Stage-separated source references and verified offline HTML/full-PDF bundles are available locally through `make docs`,
`make docs-pdf`, and `make docs-artifacts`. Each stage has an independent source inventory, navigation, search database,
PDF, and provenance manifest. Stage 2 is the distribution handoff; install/dist consumption and hosted release
attachment remain pending. See [l1/docs/README.md](README.md#generated-source-references).

## Scope and Canonical References

Use this file as the status snapshot. For implementation details, use:

- [l1/docs/reference/architecture.md](reference/architecture.md) for pass structure and data flow
- [l1/docs/reference/c-backend-design.md](reference/c-backend-design.md) for backend lowering and generated C behavior
- [l1/docs/reference/separate-compilation.md](reference/separate-compilation.md) for compile-only artifacts and
  standalone object-link behavior
- [l1/docs/reference/stdlib-preparation.md](reference/stdlib-preparation.md) for bootstrap interfaces and native reuse
- [l1/docs/reference/design-decisions.md](reference/design-decisions.md) for language and runtime rationale
- [l1/docs/reference/grammar.md](reference/grammar.md) for accepted concrete syntax
- [l1/docs/reference/ownership.md](reference/ownership.md) for ownership and cleanup behavior
- [l1/docs/reference/standard-library.md](reference/standard-library.md) for current std/sys module APIs
- [l1/docs/user/linking.md](user/linking.md) for external libraries, foreign objects, rpaths, and raw link arguments
- [l1/docs/specs/compiler/abi.md](specs/compiler/abi.md) for L1 Binary Interface symbol mangling and linkage rules
- [l1/docs/specs/compiler/module-interface-format.md](specs/compiler/module-interface-format.md) for textual `.l1m`
  module interface artifacts
- [docs/specs/compiler/cli-contract.md](../../docs/specs/compiler/cli-contract.md) for the shared cross-level CLI
  contract

The live L1 roadmap lives at [l1/docs/roadmap.md](roadmap.md).

## Current Status

### Compiler

`compiler/stage1_l0/` is the bootstrap compiler and semantic/diagnostic oracle. It provides the bootstrap frontend,
semantic analysis, C generation, compile-only artifact production, interface-authoritative standalone linking, and host
build/run integration for `.l1` inputs.

Stage 1 implementation sources remain `.l0`; Stage 2 implementation sources, L1 inputs, examples, and stdlib modules use
`.l1`.

The current compiler also synthesizes the implicit `dea` prelude module for language intrinsics. Unqualified
`sizeof(...)`, `ord(...)`, `is(...)`, `len(...)`, and `slice(...)` remain ergonomic bootstrap-stage spellings, while
their `dea::`-qualified forms are always available as stable escape hatches. `is(x, Variant)` performs payload-ignoring
enum tag comparison. `len(x)` accepts fixed arrays, slices, and strings; `slice(...)` builds an escape-restricted
non-owning view over fixed-array or slice storage.

Generated C uses the unified recursive LBI grammar: value symbols use `__deaM...N...` terminals with function type
components where needed, nominal types use `S` / `E`, and compiler-generated module lifecycle helpers use
`__deaM...I...` names. Module export manifests drive external vs. internal linkage for source-level top-level functions,
lets, and consts. In per-module output, compiler-generated `I4init`, `I4fini`, and `I5entry` infrastructure retains
external linkage independently of source exports.

The bootstrap compiler can emit deterministic textual `.l1m` module interface artifacts through the internal `-Gi` /
`--emit-interface` mode and round-trip them through a constrained interface parser. Emission computes a canonical
SipHash-1-3 fingerprint over the effective exported surface, writes the mandatory
`sip13:<16 lowercase hexadecimal digits>` value, records optional entry presence and stable first-occurrence ordered
non-virtual lifecycle imports, and fills every dependency entry with its provider module's whole-module fingerprint.
Entry, imports, `require`, and `link` are operational manifests outside the public fingerprint domain.

Resolution-aware internal entry points discover imported interfaces from ordered roots, select the first matching
`.l1m`, recursively close over `require` and `link` dependencies, and replay activated `require` providers without
loading their source. Filesystem and selected registry interfaces are rejected before graph registration or semantic
replay when a fingerprint is malformed, unsupported, inconsistent across one provider, or different from the recomputed
public-surface value. After signature replay, semantic type trees materialize nominal kinds and transparent aliases
across interface- and source-backed providers while graph and projection interfaces retain their parsed spelling. Each
resolved interface surface is validated against its own semantic `require` closure, which follows interface `require`
edges and source direct imports but excludes `link` edges. References outside that closure report `RES-0040`.

The deterministic module graph records one source, interface, registry, or virtual origin per canonical module. It
provides sorted node enumeration, canonical sibling `.c`, `.o`, and `.l1m` path associations, dependency-tier edges, and
direct source imports in exact declaration order with duplicates. Interface projection independently emits a
virtual-filtered, first-occurrence lifecycle-import view, classifies resolved cross-module public surface references as
`require`, and records remaining implementation references as `link`.

The backend exposes `backend_generate_module(...)` as the shared byte-producing operation for `--gen`, compile-only,
build, and run. It emits definitions for one selected source-backed module, external declarations for provider-owned
source and interface values and functions consumed by that target, always-present external `I4init` and `I4fini`, and
conditional external `I5entry` for a resolved, zero-parameter, non-extern source `main`. Module output contains no
process `main`, global init chain, dependency lifecycle calls, embedded Dea metadata arrays, or retention reads. The
legacy whole-program backend, combined initialization walk, and backend-owned process wrapper have been removed.

The compiler no longer carries semantic native-object readers. Standalone link treats caller objects, compiled wrapper
objects and runtime artifacts as opaque host-toolchain inputs. Managed profile validation hashes native outputs for
integrity without interpreting their format, symbols or ABI. Native-format, architecture, symbol, and embedded-control
validation belongs to the selected host compiler/linker.

Generated-C and build/run resolve imports interface-first and fall back to source only when no interface is selected.
Compile-only requires verified `.l1m` interfaces for non-virtual imports and never falls back to provider source.

The CLI implements per-module `--gen` plus `-c` / `--compile` and accepts repeatable `-I` / `--interface-path` values
with either mode. `--gen` writes stdout or exactly one requested file, accepts verified imported interfaces without
native siblings, and never invokes a host tool. Compile-only publishes the sibling per-module `.o` and `.l1m` pair
without invoking the final linker; `--keep-c` also publishes C bytes identical to `--gen` for the same resolved inputs
and options. Build/run retention copies application C from the exact files submitted to the host compiler and
regenerates managed bundled C through the same canonical generator into the mirrored `.dea-c` tree; `__dea_wrapper.c`
remains a separate link artifact. Identity is covered for source-only and mixed source/interface graphs across every
supported byte-affecting setting. Ordinary `-c` never inspects or modifies the canonical `.c` path. Output-parent
creation follows trusted directory aliases, while final artifacts and internal publication paths use no-follow
classification.

The driver stages generated C, the object, and the interface beside the selected destinations under canonical
module-relative paths. The host compiler runs from the private transaction, while its C/object operands contain only
those stable paths rather than transaction or destination prefixes. Bare compiler names are frozen to the
invocation-time command-search result before that working-directory change. Debug-producing GNU-style options record
stable `.` debug compilation-directory metadata when the configured compiler name, canonical filesystem target, or
recognized Darwin system-alias identity identifies Clang or GCC; the selected alias spelling is retained for invocation.
This neutralizes driver-controlled transaction and destination paths but does not promise byte-identical native objects,
whose remaining contents belong to the host toolchain. Successful return leaves the complete new selected set;
recoverable publication failure restores the exact prior set; failed rollback retains recovery files. Publication and
rollback use sequential renames, so concurrent readers may observe missing paths or mixed generations and same-stem
access requires external serialization. The shared semantic aliases include `-Gc` / `-Gi` / `-Gk` for generated
artifacts, `-Rp` / `-Rs` for source roots, `-Cc` / `-Co` / `-Cf` for host-C controls and explicit foreign objects, `-Ri`
/ `-Rl` for runtime paths, `-Sb` / `-Su` for runtime safety, and `-Vl` / `-Va` / `-Vm` for logging and tracing. `-V`
prints version information. The conventional `-g` and `-S` meanings remain reserved. `-L`, `-l`, `-Rr` / `--rpath`, and
`-Cl` / `--link-arg` are implemented for build, run, and standalone link.

The CLI implements `l1c -k DEA_OBJECT... [-I DIR]... [-Cf C_OBJECT]... [EXTERNAL_LINK_INPUT]... [-e MODULE] -o OUTPUT`,
with long aliases `--link`, `--foreign-object`, and `--entry`. Every positional path must have the exact terminal `.o`
suffix and a verified regular sibling `.l1m`; the interface header supplies identity, `entry;` supplies entry
eligibility, and ordered `import module` records supply lifecycle edges. The paired `.o` remains an opaque original-path
host input. `--foreign-object` asserts one regular host-compatible relocatable input without Dea inspecting its format,
symbols, `main`, reserved names, or embedded controls.

The driver registers explicit Dea providers first, then discovers missing lifecycle-import providers through ordered
`-I` roots and known bundled managed interfaces without source fallback. A selected invalid provider remains an error.
It verifies all interfaces before identity registration, then checks unique modules, provider presence, exact
provider-interface fingerprints, explicit or inferred entry, lifecycle-import cycles, and transitive lifecycle
provenance for every non-virtual `require` / `link` provider. Semantic dependency records never create lifecycle edges
or implicit objects.

An explicit depth-first frame stack computes deterministic dependency-first lifecycle order without native recursion.
The generated wrapper calls only the selected entry bridge and finalizes modules in exact reverse order. Normal compiler
families receive the selected runtime archive by exact path. TinyCC receives the complete variant-matched raw-object set
from its managed profile. Explicit runtime-library overrides take priority and select the requested exact archive.
Native inputs are checked as regular files; managed integrity validation does not infer ABI compatibility. Wrapper and
capture artifacts live in an exclusive output-local `.l1c-link-...` transaction with bounded, non-recursive cleanup;
caller inputs are not snapshotted, and the host linker receives their original safe-rendered paths and writes directly
to the caller-selected output. Native Windows rejects expansion-, quote-, or line-break-bearing host-link words and
redirection paths while the transport still passes through `cmd.exe`; build/run values known from the CLI are rejected
before source compilation.

The common link plan now retains one encounter-ordered stream across Dea objects, explicit foreign objects, `-l`
libraries, `-L` search paths, rpaths, and one-word raw host-driver arguments. Build/run expands only the source target
into its dependency-ordered Dea set. Recognized GCC and Clang driver names plus exact `cc` use explicit linker-word
rpath forwarding; TinyCC uses its documented `-Wl,-rpath=...` form; Windows and unknown families reject rpath requests.
Object-suffixed library/raw operands and response, file-list, or driver-config indirection are rejected in favor of the
typed object surfaces, while archive/shared-library words remain available. Selected runtime inputs follow the entire
user stream by exact path and cannot be shadowed by a user library search directory. MSVC rejects canonical GNU-style
`-l` / `-L` controls rather than receiving invalid words; explicit raw `.lib` inputs remain subject to that host driver.

`--build` and `--run` expand the requested source target through the canonical graph, compile each source-backed node
once into the private native workspace, and combine those objects with authoritative interface-backed objects and
foreign objects through the common verified link executor. Each source node crosses the one-module boundary by
re-analyzing against original authoritative and already staged provider interfaces before generation. The target is the
explicit entry selection. Run launches the temporary executable directly with unchanged arguments and returns its
status. `--keep-c` retains the complete mirrored `.dea-c` tree, including exact per-module C bytes and
`__dea_wrapper.c`; other staged artifacts are cleaned.

### Runtime and Standard Library

The current L1 tree includes:

- L1 stdlib modules under `compiler/shared/l1/stdlib/`
- runtime sources under `compiler/shared/runtime/`
- bootstrap-owned public headers under `$L1_BUILD_DIR/include/` and 23 verified bundled `std.*` / `sys.*` semantic
  interfaces under `$L1_BUILD_DIR/interfaces/`, generated independently of native preparation
- one managed native cache, selected by `--stdlib-cache`, `L1_STDLIB_CACHE`, or the context default, with complete
  per-configuration stdlib/runtime profiles and exact copies of the selected bundled interfaces
- content-sensitive compiler-input and supported-toolchain identities, separate generated-C/runtime options, per-key
  coordination, completion manifests, output integrity checks and machine-local memoization
- automatic preparation on native misses, quiet reuse, command-private fallback when a configuration is compilable but
  not reusable, and explicit `--prepare-stdlib`, `--no-auto-prepare` and preparation-only `--force` controls
- separate `make runtime` developer artifacts with content-sensitive per-variant build stamps; ordinary managed
  preparation does not use those archives or legacy Make settings implicitly
- the current bootstrap test suite under `compiler/stage1_l0/tests/`

Semantic-only commands do not probe a C compiler or access native cache state. Repo-local cache defaults use
`$L1_BUILD_DIR/cache`; installed-context defaults use the platform per-user cache. Installed fixtures work from a
read-only payload of semantic interfaces and rebuild inputs with an empty user cache. Productization now exposes
`make install PREFIX=...` and inventory-only `make list-installed PREFIX=...`, using a private bootstrap chain, curated
self-built Stage 2 payload, recoverable inventory publication, and native installed-state validation.
`make test-productization` covers the helpers and public orchestration. Documentation-bundle integration, distribution
commands, and full four-platform artifact acceptance remain pending. See
[l1/docs/reference/productization-inventory.md](reference/productization-inventory.md) and
[l1/docs/reference/stdlib-preparation.md](reference/stdlib-preparation.md).

These shared assets support both the bootstrap compiler and the self-hosted L1 compiler.

## Language and Library Coverage

The current implemented language surface matches the bootstrap subset exercised by the compiler, tests, and example
checks, including:

- functions, structs, enums, type aliases, top-level `let`, top-level `const`, checked scalar constant expressions and
  casts, const-valued array/case contexts, and deferred module-init lowering for non-constant top-level `let`
  initializers before user `main`
- modules/imports with qualified-name disambiguation, module-level export manifests including opaque type exports, alias
  imports, and selective imports
- structured control flow including `if`, `while`, `for`, `match`, `case`, and `with` / `cleanup`, with single-statement
  `while`, `for`, and `match` bodies accepted under the current body-local scope/cleanup rules
- function pointer types, indirect calls, same-signature function pointer identity comparisons, nullable function
  pointers, and `unsafe func` declarations plus unsafe/plain function-pointer distinctions
- L1-defined variadic functions and function pointer types, with trailing `T...` parameters, slice-backed callee packs,
  zero-or-more positional trailing arguments, and explicit final `pack...` forwarding
- fixed-width integer builtins `tiny`, `short`, `ushort`, `int`, `uint`, `long`, and `ulong`, with contextual wide
  integer literals carried through the bigint path when they exceed bootstrap `int`
- integer bitwise operators `&`, `|`, `^`, `~`, `<<`, and `>>`
- builtin `float` and `double`, real literals, the current narrow numeric conversion rules, and backend-validated
  floating-point lowering
- fixed-size arrays `T[N]`, non-owning slice views `T[]`, ordered pointer/nullable/array/slice type suffixes, contextual
  array literals and fill constructors, checked array and slice indexing, `len`/`slice`, `sizeof(T[N])`, and `new T[N]`
  / `drop`
- explicit nullability, `T` to `T?` wrapping, integer casts to nullable integer targets, `new` / `drop`, ARC-managed
  `string`, casts, postfix `expr?`, string value comparisons, same-type `T?` equality, same-type pointer identity
  equality, and `is(x, Variant)` enum tag checks
- raw-pointer indexing `ptr[i]` inside `unsafe func`, checked dynamically in checked runtime builds, checked only
  against exact hash-resident bases plus overflow/alignment in `--check-basic` builds, and lowered directly in
  `--unchecked` builds on non-null sized pointer bases
- checked allocation provenance for raw, `new`, ARC, static, and explicitly registered foreign storage; generated drop
  cleanup is extent-aware, raw/new releases cannot be mixed, and `sys.memory` exposes unsafe foreign lifetime
  registration without transferring ownership

Filesystem metadata now exposes `long?` sizes and modification seconds through `std.fs` and `sys.rt`, including
host-supported sparse extents beyond 2 GiB and timestamps outside the 32-bit seconds range. Nanoseconds remain `int?`;
whole-file string reads remain `int`-bounded and return `null` for oversized files.

The stdlib currently includes the core bootstrap modules for I/O, strings, text, paths, filesystem access, time,
randomness, assertions, optionals, the current container set, the shared `int` helper surface in `std.integer`, L1-only
`_ui` / `_l` / `_ul` `std.integer` families for `uint`, `long`, and `ulong`, wide integer string conversions in
`std.text`, `std.real` for floating-point classification, module-level real constants (`PI`, `E`, `NAN`, `INFINITY`, and
`_F` variants), basic math functions, `std.io` numeric print plus integer token-read helpers for the implemented
fixed-width integer family, and the `std.types` `Value` enum plus optionality/type-query helpers for built-in value
types.

Container access now checks vector logical length rather than reserved capacity, and filesystem path operations treat
empty paths as failures without host calls; whole-file writes also report stream-close failures.

## Delivery and Validation

The practical local workflow today is:

```bash
make use-dev-stage2
source build/dea/bin/l1-env.sh
l1c --version
make runtime
make test-stage1
make test-stage2
make test-stage2-trace
make triple-test
make test
make test-stage1-trace
make test-stage1-trace-smoke
make test-stage1-trace-all
make test-stage1-trace-children
make test-extended
make test-ci
```

`make use-dev-stage2` auto-prepares the default repo-local upstream `../l0/build/dea/bin/l0c-stage2` when needed.
`make runtime` rebuilds the repo-local runtime archives and public headers used by `--build` / `--run`. The runtime
archive compiler is controlled by `L1_RUNTIME_CC` (defaulting to `L1_CC`, then `clang` / `gcc` / `cc`, then `CC` as a
last resort); run `make clean-runtime runtime L1_RUNTIME_CC=<compiler>` when switching runtime compiler families so
cached runtime objects are rebuilt, or `make clean-all` for the broader repo-local cleanup. The additional repo-local
tcc object set used by the build driver for tcc links is controlled by `L1_TCC_OBJ_CC` (defaulting to `tcc`, then
`TCC`). If no `tcc` is available and no explicit `L1_TCC_OBJ_CC` override is set, `make runtime` prints a notice and
skips the specialized tcc object build. `make test-stage1-trace` runs the default ARC/memory trace suite and skips
intentionally slow trace cases such as `math_runtime_compile_test`; pass the test name explicitly or use
`make test-stage1-trace-all` when that slow trace coverage is needed. `make check-examples` adds warning-free
latest-stage `--check` coverage for `examples/*.l1`. `make test` runs selected Stage 1 and Stage 2 smoke suites, parity,
examples, Stage 2 tooling, and Docker/Wine runner regressions. `make test-extended` runs the Stage 1 and Stage 2 normal
suites, parity, examples, and tooling while excluding CI-only normal tests, environment reconstruction, dedicated trace
sweeps, child fixtures, and triple bootstrap. `make test-ci` adds those CI-only normal tests, environment/bootstrap
integration, the default ARC/memory trace suites, both child-fixture suites, and triple bootstrap. Linux portability is
exercised via `make test-docker`, which runs `test-extended` inside the repo-owned Docker image with GCC selected for
`L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`. Full L1 support with upstream Clang currently requires Clang 16 or newer; the
repo-owned Bookworm image supplies unsupported Clang 14. Use `DOCKER_CC=clang` to switch all three roles together only
in a separately verified environment providing supported Clang. Clang 14/15 compatibility remains planned in
[l1/work/plans/bug-fixes/2026-09-27-legacy-clang-preparation-compatibility-noref.md][legacy-clang-plan].
`make test-stage1-trace-smoke` retains a focused ARC/memory subset for quick developer diagnostics. Hosted
`make test-ci` runs the complete local-normal suites with CI-only cases, environment/bootstrap integration, both default
trace suites, child fixtures, and the strict fixed point on Windows, Linux, and macOS. The legacy `DOCKER_L0_CC`
selector remains a compatibility fallback when `DOCKER_CC` is unset. Run the Docker lane after runtime, Makefile, or
build-driver changes.

`make test-stage1-trace-children` builds the declared successful math runtime fixtures with ARC and memory tracing, runs
each executable directly, and analyzes each child stderr file independently. `TESTS="wide_math_main"` selects one
fixture. `make test-ci` always runs both children for each compiler stage, independently of parent `TESTS` selectors.
The child suite retains its build, output, trace, and report files when a fixture fails.

Stage 2 provides the same trace-target suffixes and selectors as Stage 1. `make triple-test` compares complete
retained-C inventories and bytes, applies the native platform policy, and exercises the complete normal suite and
examples through the final self-built compiler. It is required by `test-ci`, and stays separate from local
`test-extended`.

Validation is currently centered on:

- automated CI via `.github/workflows/ci.yml`, which routes L1-relevant `push`/`pull_request` changes into the reusable
  `l1-ci.yml` workflow; `workflow_dispatch` remains available for platform selection, manual C compiler selection, and
  explicit Make-target selection. Hosted CI defaults to `make test-ci`, which runs full normal suites with CI-only
  cases, environment/bootstrap integration, default trace suites, child fixtures, and triple bootstrap on Linux, macOS,
  and Windows. Each selected compiler is applied to `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`, and the resolved executable
  plus version is logged before the Make target runs.

- `make test-stage1` and the `.l0` implementation tests under `compiler/stage1_l0/tests/`

- `make test-stage1-trace` for default ARC/memory trace validation across the `.l0` implementation tests

- `make test-stage1-trace-smoke` for quick focused ARC/memory diagnostics

- `make test-stage1-trace-all` for opt-in slow trace coverage, including nested-compiler cases such as
  `math_runtime_compile_test`

- `make test-stage1-trace-children` for focused, isolated trace checks of successful L1 runtime fixtures, also included
  in `test-ci`

- `make check-examples` for warning-free latest-stage `--check` coverage across `examples/*.l1`

- `make test-env` for generated launcher and environment-stackability coverage

- `make test` as the fast local gate with representative compiler checks, parity, examples, and inexpensive tooling
  regressions

- `make test-extended` as the broad local-normal gate with both stage normal suites, parity, examples, and tooling

- `make test-ci` as the exhaustive hosted gate with CI-only normal cases, environment/bootstrap, trace suites, child
  fixtures, and triple bootstrap

- `make test-docker` as the Linux container reference path for runtime/build-driver portability

- keeping the stdlib/runtime tree usable by the bootstrap compiler

Current Stage 1 validation covers exact generated-C identity across `--gen`, compile-only retention, and build/run
retained trees for identical resolved inputs and settings.

## Platform Support

Current bootstrap expectations remain aligned with the host/toolchain assumptions inherited from the upstream L0
bootstrap path:

- Linux and macOS are the primary local-development hosts
- builds require a C99-compatible host compiler
- the default local upstream compiler is `../l0/build/dea/bin/l0c-stage2`
- reproducible bootstrap flows can override that default with `L1_BOOTSTRAP_L0C`

## Known Constraints

These remain true today:

1. The Stage 2 port, supported-host validation, and native-source review are complete. All 119 current production
   modules and 1,749 function bodies are reviewed; consolidated normal, parity, trace, child-fixture, environment, and
   strict triple-bootstrap validation passed. Stage 1 remains the semantic and diagnostic oracle. Review outcomes and
   retained constraints are recorded in
   [l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/review.md][native-review].
2. Standalone linking consumes explicit object paths plus derived sibling interfaces; it does not discover implicit Dea
   objects, compile sources, or infer external-library dependencies from modules or manifests.
3. Fixed-size arrays `T[N]` and escape-restricted non-owning slices `T[]` are implemented; owning dynamic buffers,
   shared buffers, and general escape-capable slices are not language features.
4. Address-of (`&`) and generics are not part of the current active language surface.

[legacy-clang-plan]: ../work/plans/bug-fixes/2026-09-27-legacy-clang-preparation-compatibility-noref.md
[native-review]: ../work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/review.md
