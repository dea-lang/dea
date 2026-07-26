# L1 Project Status

Version: 2026-07-26

This document summarizes what is implemented in the Dea/L1 subtree today.

Dea/L1 is currently in bootstrap status:

- the runnable compiler is `compiler/stage1_l0/`, implemented in Dea/L0
- the current shared assets are `compiler/shared/l1/stdlib/` plus the copied runtime sources under
  `compiler/shared/runtime/`
- `compiler/stage2_l1/` exists only as a placeholder for a future self-hosted compiler

L0 remains the active release line. The L1 subtree is the current home for bootstrap compiler work, library surface, and
future language growth beyond L0.

## Scope and Canonical References

Use this file as the status snapshot. For implementation details, use:

- [l1/docs/reference/architecture.md](reference/architecture.md) for pass structure and data flow
- [l1/docs/reference/c-backend-design.md](reference/c-backend-design.md) for backend lowering and generated C behavior
- [l1/docs/reference/design-decisions.md](reference/design-decisions.md) for language and runtime rationale
- [l1/docs/reference/grammar.md](reference/grammar.md) for accepted concrete syntax
- [l1/docs/reference/ownership.md](reference/ownership.md) for ownership and cleanup behavior
- [l1/docs/reference/standard-library.md](reference/standard-library.md) for current std/sys module APIs
- [l1/docs/specs/compiler/abi.md](specs/compiler/abi.md) for L1 Binary Interface symbol mangling and linkage rules
- [l1/docs/specs/compiler/module-interface-format.md](specs/compiler/module-interface-format.md) for textual `.l1m`
  module interface artifacts
- [docs/specs/compiler/cli-contract.md](../../docs/specs/compiler/cli-contract.md) for the shared cross-level CLI
  contract

The live L1 roadmap lives at [l1/docs/roadmap.md](roadmap.md).

## Current Status

### Compiler

`compiler/stage1_l0/` is the only implemented L1 compiler today. It provides the bootstrap frontend, semantic analysis,
C generation, compile-only artifact production, and host build/run integration for `.l1` inputs.

The implementation sources remain `.l0`, while user-facing L1 source inputs, examples, and stdlib modules use `.l1`.

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

The bootstrap compiler can emit deterministic textual `.l1m` module interface artifacts through the internal
`--emit-interface` mode and round-trip them through a constrained interface parser. Emission computes a canonical
SipHash-1-3 fingerprint over the effective exported surface, writes the mandatory
`sip13:<16 lowercase hexadecimal digits>` value, and fills every dependency entry with its provider module's
whole-module fingerprint.

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
direct source imports in exact declaration order. Interface projection classifies resolved cross-module public surface
references as `require` and remaining implementation references as `link`.

The backend now exposes an internal `backend_generate_module(...)` entry point that emits definitions for one selected
source-backed module. It emits external declarations for provider-owned source and interface values and functions
consumed by that target, external `I8metadata` and `I7imports` byte arrays, always-present external `I4init` and
`I4fini`, and conditional external `I5entry` for a resolved, zero-parameter, non-extern source `main`. The arrays record
the module's verified whole-interface fingerprint, entry presence, and unique direct object-backed (non-virtual)
providers in first source-import order. Volatile reads from `I4init` retain both records through linker dead-strip.
Module output contains no process `main`, global init chain, or dependency lifecycle calls. Compile-only consumes this
module boundary; the legacy `backend_generate(...)` path remains the ordinary generation, build, and run path.

The compiler includes bounded readers for ELF, Mach-O, and standard COFF relocatable objects. Exact normalization covers
Darwin TinyCC ELF aliases, Mach-O and COFF I386 leading underscores, and the leading `#` on ARM64EC function symbols;
supported COFF machines are I386, ARM, ARMNT, AMD64, ARM64EC, and ARM64. The format-neutral inspection API reports
container information, exact defined symbols, process-level C `main` presence, and one of valid Dea metadata, no Dea
metadata, or malformed Dea metadata. Every external definition under the normalized, reserved `__dea` prefix without a
complete consistent metadata pair is malformed rather than foreign-compatible, even when its suffix is not valid LBI.
File access failures and unsupported or corrupt containers remain separate object-read errors. Standalone link-set
validation and host linking remain future work.

Ordinary build/run CLI imports remain source-based today. Compile-only instead requires verified `.l1m` interfaces for
non-virtual imports and never falls back to provider source.

The CLI implements `-c` / `--compile` and accepts repeatable `-I` / `--interface-path` values with that mode. One
invocation publishes the sibling per-module `.o` and `.l1m` pair without invoking the final linker; `--keep-c` also
publishes the exact staged `.c` used for host compilation. Ordinary `-c` never inspects or modifies the canonical `.c`
path. Output-parent creation follows trusted directory aliases, while final artifacts and internal publication paths use
no-follow classification.

The driver stages generated C, the object, and the interface beside the selected destinations. Successful return leaves
the complete new selected set; recoverable publication failure restores the exact prior set; failed rollback retains
recovery files. Publication and rollback use sequential renames, so concurrent readers may observe missing paths or
mixed generations and same-stem access requires external serialization. The shared semantic aliases are `-Gc` for
generated C, `-Rp` / `-Rs` for source roots, `-Cc` / `-Co` for host-C controls, `-Ri` / `-Rl` for runtime paths, and
`-Vl` for rich logging. The conventional `-g`, `-S`, `-L`, and `-l` meanings are reserved but not implemented.
Standalone linking does not exist, and `--build` / `--run` remain source-based single-CU operations.

### Runtime and Standard Library

The current L1 tree includes:

- L1 stdlib modules under `compiler/shared/l1/stdlib/`
- runtime sources under `compiler/shared/runtime/`
- repo-local runtime deliverables under `build/dea/include/dea_rt.h`, `build/dea/include/l1_real.h`,
  `build/dea/lib/libdea_rt.a`, `build/dea/lib/libdea_rt_traced.a`, `build/dea/lib/libdea_rt_check_basic.a`, and
  `build/dea/lib/libdea_rt_unchecked.a`
- content-sensitive per-variant runtime build stamps, so compiler/flag/tuning changes rebuild affected archives and tcc
  objects while identical builds remain no-ops
- the current bootstrap test suite under `compiler/stage1_l0/tests/`

This gives the subtree a complete bootstrap environment without claiming a self-hosted L1 compiler yet.

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

The stdlib currently includes the core bootstrap modules for I/O, strings, text, paths, filesystem access, time,
randomness, assertions, optionals, the current container set, the shared `int` helper surface in `std.integer`, L1-only
`_ui` / `_l` / `_ul` `std.integer` families for `uint`, `long`, and `ulong`, wide integer string conversions in
`std.text`, `std.real` for floating-point classification, module-level real constants (`PI`, `E`, `NAN`, `INFINITY`, and
`_F` variants), basic math functions, `std.io` numeric print plus integer token-read helpers for the implemented
fixed-width integer family, and the `std.types` `Value` enum plus optionality/type-query helpers for built-in value
types.

## Delivery and Validation

The practical local workflow today is:

```bash
make use-dev-stage1
source build/dea/bin/l1-env.sh
l1c --version
make runtime
make test-stage1
make test
make test-stage1-trace
make test-stage1-trace-all
make test-all
```

`make use-dev-stage1` auto-prepares the default repo-local upstream `../l0/build/dea/bin/l0c-stage2` when needed.
`make runtime` rebuilds the repo-local runtime archives and public headers used by `--build` / `--run`. The runtime
archive compiler is controlled by `L1_RUNTIME_CC` (defaulting to `L1_CC`, then `clang` / `gcc` / `cc`, then `CC` as a
last resort); run `make clean-runtime runtime L1_RUNTIME_CC=<compiler>` when switching runtime compiler families so
cached runtime objects are rebuilt, or `make clean-all` for the broader repo-local cleanup. The additional repo-local
tcc object set used by the build driver for tcc links is controlled by `L1_TCC_OBJ_CC` (defaulting to `tcc`, then
`TCC`). If no `tcc` is available and no explicit `L1_TCC_OBJ_CC` override is set, `make runtime` prints a notice and
skips the specialized tcc object build. `make test-stage1-trace` runs the default ARC/memory trace suite and skips
intentionally slow trace cases such as `math_runtime_compile_test`; pass the test name explicitly or use
`make test-stage1-trace-all` when that slow trace coverage is needed. `make check-examples` adds warning-free
latest-stage `--check` coverage for `examples/*.l1`. `make test` combines the implementation tests,
environment-stackability checks, and example checks without the dedicated broad trace sweep; `make test-all` adds the
default ARC/memory trace checks. Linux portability is exercised via `make test-docker`, which runs `test-all` inside the
repo-owned Docker image; run it after runtime, Makefile, or build-driver changes.

Validation is currently centered on:

- automated CI via `.github/workflows/ci.yml`, which routes L1-relevant `push`/`pull_request` changes into the reusable
  `l1-ci.yml` workflow; `workflow_dispatch` remains available for platform selection, manual C compiler selection, and
  opt-in slow trace coverage

- `make test-stage1` and the `.l0` implementation tests under `compiler/stage1_l0/tests/`

- `make test-stage1-trace` for default ARC/memory trace validation across the `.l0` implementation tests

- `make test-stage1-trace-all` for opt-in slow trace coverage, including nested-compiler cases such as
  `math_runtime_compile_test`

- `make check-examples` for warning-free latest-stage `--check` coverage across `examples/*.l1`

- `make test-env` for generated launcher and environment-stackability coverage

- `make test` as the normal local Stage 1, environment, and example validation entry point without the dedicated broad
  trace sweep

- `make test-all` as the combined local Stage 1, trace, environment, and example validation entry point

- `make test-docker` as the Linux container reference path for runtime/build-driver portability

- keeping the stdlib/runtime tree usable by the bootstrap compiler

Current Stage 1 validation does not include an end-to-end exact generated-C golden-file diff suite.

## Platform Support

Current bootstrap expectations remain aligned with the host/toolchain assumptions inherited from the upstream L0
bootstrap path:

- Linux and macOS are the primary local-development hosts
- builds require a C99-compatible host compiler
- the default local upstream compiler is `../l0/build/dea/bin/l0c-stage2`
- reproducible bootstrap flows can override that default with `L1_BOOTSTRAP_L0C`

## Known Constraints

These remain true today:

1. There is no implemented `stage2_l1` compiler yet.
2. Ordinary build/run CLI backend output is one legacy whole-program C translation unit; compile-only uses the internal
   module generator, but multi-CU build/run orchestration is not operational.
3. Standalone linking and multi-CU build/run orchestration are not operational.
4. Fixed-size arrays `T[N]` and escape-restricted non-owning slices `T[]` are implemented; owning dynamic buffers,
   shared buffers, and general escape-capable slices are not language features.
5. Address-of (`&`) and generics are not part of the current active language surface.

## Near-Term Direction

Near-term L1 work should focus on:

1. stabilizing and expanding the Stage-1 compiler and stdlib/runtime surface
2. improving L1-local documentation and tests
3. preparing the subtree for a later self-hosted `stage2_l1` implementation without claiming it exists today
