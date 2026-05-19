# L0 Project Status

Version: 2026-05-19

This document summarizes what is implemented in this repository today and what defines the current Dea/L0 `1.0.0`
release.

L0 now lives as one language subtree inside the Dea monorepo; monorepo release tags use the `l0-vX.Y.Z` namespace while
historical pre-monorepo tags remain legacy references. The monorepo also contains the active Dea/L1 bootstrap subtree
under `l1/`.

## Scope and Canonical References

Use this file as a status snapshot. For implementation details, use:

- [docs/project-status.md](../../docs/project-status.md) for the Dea-wide monorepo status snapshot.
- [l0/docs/reference/architecture.md](reference/architecture.md) for pass structure and data flow.
- [l0/docs/specs/compiler/stage1-contract.md](specs/compiler/stage1-contract.md) for external interfaces and guarantees.
- [l0/docs/reference/c-backend-design.md](reference/c-backend-design.md) for backend lowering and generated C behavior.
- [l0/docs/specs/runtime/trace.md](specs/runtime/trace.md) for tracing flags and runtime trace semantics.
- [l0/docs/reference/grammar.md](reference/grammar.md) for accepted concrete syntax.
- [l0/docs/reference/standard-library.md](reference/standard-library.md) for current std/sys module APIs.
- [l0/docs/specs/compiler/cli-contract.md](specs/compiler/cli-contract.md) for the shared CLI contract across stages.
- [l0/docs/specs/compiler/stage2-contract.md](specs/compiler/stage2-contract.md) for Stage 2 contract and provenance.

## Current Status

### Stage 1

Stage 1 (`compiler/stage1_py`) is complete and remains the reference implementation for language behavior, diagnostics,
and C generation.

At a high level, it provides:

- the full current frontend pipeline from lexing through type checking,
- C99 code generation for the implemented L0 language surface,
- the shared public CLI surface documented in [l0/docs/specs/compiler/cli-contract.md](specs/compiler/cli-contract.md),
- tracing support via `--trace-arc` and `--trace-memory`.

### Stage 2

Stage 2 (`compiler/stage2_l0`) is self-hosted and currently the main delivery vehicle for normal developer, install,
distribution, and release workflows.

At a high level, it provides:

- full public CLI parity with Stage 1 across `--check`, `--tok`, `--ast`, `--sym`, `--type`, `--gen`, `--build`, and
  `--run`,
- self-hosted C99 generation, build, and run flows,
- repo-local, install-prefix, and distribution delivery paths,
- strict triple-bootstrap validation via `make triple-test`,
- embedded provenance in artifact-producing Stage 2 binaries via `--version`,
- release packaging plus docs/PDF publishing automation through the repository workflows,
- current parity fixes for Stage 2 diagnostics, drop-liveness checks, string comparisons, bare enum variants in
  top-level bindings, ARC borrowed-parameter reassignment, unwrap-cast ARC cleanup, optional-wrapper typedef ordering,
  and Windows trace-runner behavior.

Stage 1 remains the behavioral oracle for equivalent Stage 2 paths.

## Language and Library Coverage

The current implemented language surface covers the core bootstrap subset used throughout this repository:

- functions, structs, enums, type aliases, and top-level `let`,
- modules/imports with qualified-name disambiguation,
- structured control flow including `if`, `while`, `for`, `match`, `case`, and `with`/`cleanup`,
- explicit nullability, `new`/`drop`, ARC-managed `string`, casts, postfix `expr?`, value-based `string`
  equality/ordering operators, and the `+` string concatenation operator.

The standard library now includes the core runtime-facing and bootstrap-facing modules for I/O, strings, text, paths,
filesystem access, the shared integer helper surface in `std.integer`, time, randomness, assertions, optionals, and the
current container set. Use [l0/docs/reference/standard-library.md](reference/standard-library.md) for the canonical
module-by-module reference.

## Delivery and Validation

The current repository state supports three practical ways to use L0:

- source-tree Stage 1 usage through `./scripts/l0c`,
- repo-local Dea builds under `build/dea/bin` via `make use-dev-stage1` / `make use-dev-stage2`,
- install-prefix and relocatable distribution archives built from the self-hosted Stage 2 compiler.

Validation is centered on:

- Stage 1 and Stage 2 test suites,
- strict triple-bootstrap reproducibility checks,
- workflow/distribution regression tests for build metadata, archives, and release-tag policy,
- strict docs generation and packaged-reference validation.

## Platform Support

The current development support baseline remains:

- Tier 1 hosts: Linux and macOS for Stage 1 and Stage 2 workflows.
- Tier 1 Windows toolchain: MSYS2 `UCRT64` with MinGW-w64 GCC or Clang for build, test, install, and distribution
  workflows. MSYS2 `MINGW64` is supported as an alternate validation environment. Generated native `cmd.exe` launchers
  can invoke the packaged toolchain outside the MSYS2 shell.
- Tier 2 / experimental: MSVC-family builds remain outside the validated release matrix.

## Known Limitations and Constraints

These remain true in the `1.0.0` release:

1. Backend output is one C translation unit (no multi-object/header split pipeline yet).
2. Arrays/slices are not implemented, and pointer indexing is not part of the current L0 language surface; indexing
   syntax exists only as dormant frontend shape and all user-facing indexing expressions are rejected during semantic
   analysis.
3. No address-of (`&`) operator in language semantics.
4. No generics, traits, or macros.
5. Reserved/future keywords and operators are lexed for diagnostics and staged evolution.
6. Bitwise operators, top-level `const`, and further language extensions are deferred to Dea/L1.
