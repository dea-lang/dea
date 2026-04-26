# L1 C Backend Design

Version: 2026-04-26

This is the canonical backend implementation document for the current Dea/L1 bootstrap compiler.

Related docs:

- Compiler architecture and pass flow: [architecture.md](architecture.md)
- Language/runtime rationale and policy: [design-decisions.md](design-decisions.md)
- Current status snapshot: [l1/docs/project-status.md](../project-status.md)

## Overview

Current code generation is implemented only in `compiler/stage1_l0/src/` and is split into:

- backend orchestration in `backend.l0`
- C emission in `c_emitter.l0`
- string literal escaping/encoding helpers in `string_escape.l0`

Input is a fully typed analysis result. Output is one C99 translation unit that is then compiled by the selected host C
compiler for `--build` and `--run`.

`compiler/stage2_l1/` does not currently provide a second backend implementation.

## Responsibilities Split

### Backend orchestration (`backend.l0`)

- validates generation preconditions
- orders type emission using dependency-aware traversal
- lowers statements and expressions into emitter operations
- manages ownership-sensitive cleanup scheduling
- emits function bodies and early-exit cleanup paths

### C emitter (`c_emitter.l0`)

- emits includes, declarations, definitions, and formatting
- maps semantic types to runtime/C representations
- performs C identifier hygiene and name mangling
- emits helper calls for checked arithmetic, allocation, retain/release, casts, and unwraps

## Generated Unit Layout

The generated C file is organized in this order:

1. file header and includes
2. forward declarations
3. builtin and wrapper typedefs
4. function pointer typedefs plus struct and enum definitions in dependency order
5. top-level `let` storage
6. function declarations
7. hidden module/global init functions for deferred top-level `let` initializers
8. non-extern function definitions
9. C `main` wrapper when the entry module defines `main`

Current backend target is a single C translation unit. Top-level `const` and constant `let` initializers lower directly
into C storage initializers; non-constant top-level `let` initializers lower as zero/default-initialized storage plus
hidden per-module init assignments.

For `--build` / `--run`, that generated unit now compiles against `dea_rt.h` and links `libdea_rt.a` or
`libdea_rt_traced.a` instead of inlining the runtime bodies into the user translation unit.

## Type Lowering

### Builtins

- `int` lowers through the runtime integer typedefs in `compiler/shared/runtime/include/dea_rt.h`
- `byte`, `bool`, and `string` likewise lower through runtime-defined C-facing types
- `float` lowers to C `float` only when the enforced L1 floating-point contract is satisfied
- `double` lowers to C `double` only when the enforced L1 floating-point contract is satisfied
- `void` lowers to C `void`

Current L1 prefix policy is:

- `dea_*` for public generated/runtime C identifiers
- `DEA_*` for public generated/runtime preprocessor names
- `rt_*` for stable runtime API entry points used by generated C and stdlib declarations
- `_rt_*` for private runtime helpers
- `_dea_*` / `_DEA_*` for touched non-`_rt_` private runtime names that previously carried historical `l0` spellings

The emitter actively mangles user/source names that start with reserved generated/runtime prefixes, including both the
legacy `l0` families and the current `dea` families, to avoid collisions in generated C.

Generated output now includes the public runtime header `dea_rt.h`. The internal helper `dea_siphash.h` lives only in
the compiled runtime implementation and is not part of the generated-C surface or the public L1 ABI.

Runtime artifacts are produced per toolchain: the official archives (`libdea_rt.a` and `libdea_rt_traced.a`) match the
platform compiler's object format, while tcc additionally builds raw `.o` objects under
`build/dea/runtime/tcc/{default,traced}/`. When the active C compiler family is tcc, the build driver links those
objects directly to avoid object-format mismatches such as Darwin tcc ELF objects versus platform Mach-O archives.

### Floating-point backend contract

For FP-using programs, the generated C header now emits explicit compile-time checks instead of assuming every host C
target is acceptable.

Current enforcement:

- generated C includes `float.h` and `math.h` and rejects targets that do not provide `INFINITY` and `NAN`
- generated C rejects targets unless `FLT_RADIX == 2`, `FLT_MANT_DIG == 24`, `FLT_MAX_EXP == 128`, `DBL_MANT_DIG == 53`,
  and `DBL_MAX_EXP == 1024`
- generated C rejects macro-visible fast-math configurations such as `__FAST_MATH__` and MSVC `/fp:fast`
- build/run mode also rejects known-invalid explicit `L1_CFLAGS` / `--c-options` such as `-ffast-math`, `-Ofast`,
  `-ffinite-math-only`, `-fno-signed-zeros`, `-funsafe-math-optimizations`, `-fassociative-math`, and
  `-freciprocal-math`

This keeps plain C lowering honest: `float` and `double` remain direct C scalars only on hosts whose representation and
build mode preserve the L1 floating-point contract.

### Structs, enums, pointers, and nullable values

- user-defined structs lower to C structs with mangled module-qualified names
- enums lower to tagged unions
- function pointer types lower to signature-specific `dea_func_*` typedefs over plain C function pointers
- pointer-shaped nullable values use `NULL` representation
- non-pointer nullable values lower to wrapper structs carrying `has_value` plus the wrapped value
- non-null values used in matching nullable contexts lower to present wrappers; for example, returning `0 as ulong` from
  a `ulong?` function stores the converted `ulong` payload in `dea_opt_ulong`
- explicit integer casts to nullable integer targets lower as a checked cast to the inner C type followed by wrapper
  construction; for example, `0 as ulong?` lowers through the same `int` to `ulong` range check as `0 as ulong`

## Statement and Expression Lowering

Implemented lowering currently includes:

- literals, local/global references, unary/binary operators, direct and indirect calls, field/index access, casts, and
  constructors
- `new` allocation and `drop` deallocation via runtime helpers
- `if`, `while`, `for`, `match`, `case`, `with`, `break`, `continue`, and `return`
- `expr?` null-propagation lowering with early return on empty
- checked integer arithmetic and narrowing via runtime helpers

## Ownership and Cleanup Model

The backend is responsible for scheduling cleanup; the emitter materializes the concrete C.

Key rules:

- ARC-managed `string` values use runtime retain/release helpers
- returning an owned local may be lowered as a move
- scope exit cleanup runs in reverse declaration order
- early exits run pending `with` cleanup before normal owned-value cleanup
- enum and struct cleanup recursively releases owned fields for active values

See [ownership.md](ownership.md) for the language-facing ownership rules that this lowering must preserve.

## Entry Point Behavior

When the entry module defines `main`, backend emits a host C `main(int argc, char **argv)` wrapper that:

- initializes runtime argument state
- calls the hidden global module-init chain when any imported module needs deferred top-level initialization
- calls the mangled L1 entry function
- returns `int`/`bool` results as host `int`
- discards other return values and exits with `0`

## Debuggability

- generated C is emitted in labeled sections
- source mapping can include `#line` directives
- runtime tracing flags such as `--trace-arc` and `--trace-memory` are forwarded into generated C preprocessor toggles

## Current Constraints

1. Backend output is one `.c` file.
2. The only implemented backend is the bootstrap backend in `stage1_l0`.
3. The runtime and ABI surface assume a C99-compatible host toolchain.
4. Optimization is delegated to the host C compiler; backend priority is correctness and explicit lowering.

## Testing Coverage

Current backend validation is centered on the copied bootstrap test suite under `compiler/stage1_l0/tests/`, especially:

- `backend_test.l0`
- `c_emitter_test.l0`
- `driver_test.l0`
- `build_driver_test.l0`

Ownership and trace-oriented validation also uses:

- `run_trace_tests.py`
- `run_test_trace.py`
- `check_trace_log.py`

These tests exercise the current bootstrap compiler implementation, not a self-hosted Stage 2 compiler.
