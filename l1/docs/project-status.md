# L1 Project Status

Version: 2026-04-26

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

The live L1 roadmap lives at [l1/docs/roadmap.md](roadmap.md).

## Current Status

### Compiler

`compiler/stage1_l0/` is the only implemented L1 compiler today. It provides the bootstrap frontend, semantic analysis,
C generation, and host build/run integration for `.l1` inputs.

The implementation sources remain `.l0`, while user-facing L1 source inputs, examples, and stdlib modules use `.l1`.

The current compiler also synthesizes the implicit `dea` prelude module for language intrinsics. Unqualified
`sizeof(...)`, `ord(...)`, and `is(...)` remain ergonomic bootstrap-stage spellings, while `dea::sizeof(...)`,
`dea::ord(...)`, and `dea::is(...)` are always available as the stable qualified forms. The current `is(x, Variant)`
intrinsic supports payload-ignoring enum tag comparison, including qualified variant references and enum-returning call
expressions in first position.

### Runtime and Standard Library

The current L1 tree includes:

- L1 stdlib modules under `compiler/shared/l1/stdlib/`
- runtime sources under `compiler/shared/runtime/`
- repo-local runtime deliverables under `build/dea/include/dea_rt.h`, `build/dea/include/l1_real.h`,
  `build/dea/lib/libdea_rt.a`, and `build/dea/lib/libdea_rt_traced.a`
- the current bootstrap test suite under `compiler/stage1_l0/tests/`

This gives the subtree a complete bootstrap environment without claiming a self-hosted L1 compiler yet.

## Language and Library Coverage

The current implemented language surface matches the bootstrap subset exercised by the compiler, tests, and example
checks, including:

- functions, structs, enums, type aliases, top-level `let`, top-level `const`, and deferred module-init lowering for
  non-constant top-level `let` initializers before user `main`
- modules/imports with qualified-name disambiguation
- structured control flow including `if`, `while`, `for`, `match`, `case`, and `with` / `cleanup`, with single-statement
  `while`, `for`, and `match` bodies accepted under the current body-local scope/cleanup rules
- function pointer types, indirect calls, same-signature function pointer identity comparisons, and nullable function
  pointers
- fixed-width integer builtins `tiny`, `short`, `ushort`, `int`, `uint`, `long`, and `ulong`, with contextual wide
  integer literals carried through the bigint path when they exceed bootstrap `int`
- integer bitwise operators `&`, `|`, `^`, `~`, `<<`, and `>>`
- builtin `float` and `double`, real literals, the current narrow numeric conversion rules, and backend-validated
  floating-point lowering
- explicit nullability, `T` to `T?` wrapping, integer casts to nullable integer targets, `new` / `drop`, ARC-managed
  `string`, casts, postfix `expr?`, string value comparisons, same-type `T?` equality, same-type pointer identity
  equality, and `is(x, Variant)` enum tag checks

The stdlib currently includes the core bootstrap modules for I/O, strings, text, paths, filesystem access, time,
randomness, assertions, optionals, the current container set, the shared `int` helper surface in `std.math`, L1-only
`_ui` / `_l` / `_ul` `std.math` families for `uint`, `long`, and `ulong`, wide integer string conversions in `std.text`,
`std.real` for floating-point classification, module-level real constants (`PI`, `E`, `NAN`, `INFINITY`, and `_F`
variants), basic math functions, `std.io` numeric print plus integer token-read helpers for the implemented fixed-width
integer family, and the `std.types` `Value` enum plus optionality/type-query helpers for built-in value types.

## Delivery and Validation

The practical local workflow today is:

```bash
make use-dev-stage1
source build/dea/bin/l1-env.sh
l1c --version
make runtime
make test-stage1
make test-stage1-trace
make test-stage1-trace-all
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
latest-stage `--check` coverage for `examples/*.l1`, while `make test-all` combines the implementation tests, default
ARC/memory trace checks, and example checks. Linux portability is exercised via `make test-docker`, which runs
`test-all` inside the repo-owned Docker image; run it after runtime, Makefile, or build-driver changes.

Validation is currently centered on:

- `make test-stage1` and the `.l0` implementation tests under `compiler/stage1_l0/tests/`
- `make test-stage1-trace` for default ARC/memory trace validation across the `.l0` implementation tests
- `make test-stage1-trace-all` for opt-in slow trace coverage, including nested-compiler cases such as
  `math_runtime_compile_test`
- `make check-examples` for warning-free latest-stage `--check` coverage across `examples/*.l1`
- `make test-all` as the combined local Stage 1 validation entry point
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
2. Backend output is one C translation unit.
3. Arrays/slices are not implemented as general language features.
4. Address-of (`&`) and generics are not part of the current active language surface.

## Near-Term Direction

Near-term L1 work should focus on:

1. stabilizing and expanding the Stage-1 compiler and stdlib/runtime surface
2. improving L1-local documentation and tests
3. preparing the subtree for a later self-hosted `stage2_l1` implementation without claiming it exists today
