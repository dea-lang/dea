# L1 C Backend Design

Version: 2026-07-26

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

The separate-compilation object boundary adds:

- format-independent metadata encoding and decoding in `object_metadata.l0`
- format-neutral inspection and classification in `object_reader.l0`
- bounded ELF, Mach-O, and PE/COFF adapters in `object_reader_elf.l0`, `object_reader_macho.l0`, and
  `object_reader_pecoff.l0`

Input is a fully typed analysis result. The backend exposes two supported output boundaries:

- `backend_generate(result, opts, cfg)` emits the legacy whole-program C99 translation unit used by the current `--gen`,
  `--build`, and `--run` flows.
- `backend_generate_module(result, target_module, opts, cfg)` emits one source-backed module translation unit for
  `--compile` and later separate-compilation consumers. Build and run do not use this boundary yet.

`compiler/stage2_l1/` does not currently provide a second backend implementation.

## Responsibilities Split

### Backend orchestration (`backend.l0`)

- validates generation preconditions
- selects either the legacy whole-program boundary or one canonical source-backed target module
- orders type emission using dependency-aware traversal
- lowers statements and expressions into emitter operations
- manages ownership-sensitive cleanup scheduling
- emits function bodies and early-exit cleanup paths

### C emitter (`c_emitter.l0`)

- emits includes, declarations, definitions, and formatting
- maps semantic types to runtime/C representations
- performs C identifier hygiene and name mangling
- emits helper calls for checked arithmetic, allocation, retain/release, casts, and unwraps

### Object metadata and readers

- encode and decode the fixed version 1 metadata records
- inspect relocatable object section, symbol, and string tables without external tools
- normalize only the documented object-ABI C symbol aliases before exact symbol matching
- expose defined-symbol lookup and the valid, absent, or malformed Dea metadata classification
- reject unsupported or corrupt containers as object-read errors outside that classification

## Generated Unit Layout

### Legacy whole-program output

The legacy generated C file is organized in this order:

1. file header and includes
2. forward declarations
3. builtin and wrapper typedefs
4. function pointer typedefs plus struct and enum definitions in dependency order
5. top-level `let` storage
6. function declarations
7. hidden module/global init functions for deferred top-level `let` initializers
8. non-extern function definitions
9. C `main` wrapper when the entry module defines `main`

Top-level `const` and constant `let` initializers lower directly into C storage initializers; non-constant top-level
`let` initializers lower as zero/default-initialized storage plus hidden per-module init assignments.

For `--build` / `--run`, that generated unit now compiles against `dea_rt.h` and links `libdea_rt.a`,
`libdea_rt_traced.a`, `libdea_rt_check_basic.a`, or `libdea_rt_unchecked.a` instead of inlining the runtime bodies into
the user translation unit.

### Per-module output

`backend_generate_module` emits definitions for exactly the selected source-backed module. Its generated C contains:

1. the file header, runtime includes, forward declarations, and required type declarations;
2. external declarations for provider-owned source and interface values and functions consumed by the target;
3. storage and non-extern function definitions owned by the target module, with export-driven linkage;
4. external `I8metadata` and `I7imports` byte arrays;
5. one external `I4init` definition and one external `I4fini` definition; and
6. an external `I5entry` bridge only when the target defines a resolved, zero-parameter, non-extern source `main`.

Imported non-extern L1 values and functions are declared under their provider-owned LBI names but are never defined by
the consumer translation unit. Imported C `extern` functions retain their declared C spelling. Exported target
definitions keep external linkage; non-exported target definitions use `static`. Compiler-generated `I` symbols remain
external regardless of the source export manifest.

Module output contains no process-level C `main`, legacy global init chain, or calls to dependency lifecycle functions.
The later standalone-link tranche owns the executable wrapper and cross-module ordering.

Compile-only writes this per-module C output, the host-compiled relocatable object, and the corresponding fingerprinted
interface into one sibling transaction directory. The driver publishes the object before the interface; `--keep-c` also
selects the exact staged C for publication. Sequential renames provide successful/new and recoverable-failure/prior
endpoints, not an atomic reader-visible snapshot: paths may be absent or from different generations during publication
or rollback, concurrent access requires external serialization, and failed rollback retains recovery files. The backend
does not own staging, rollback, or destination-path policy.

The identity record contains the target's canonical module name, whole-module interface fingerprint, and `HAS_ENTRY`
flag. The import record contains every unique direct object-backed (non-virtual) provider in first source-import order
with its expected fingerprint, including side-effect-only imports. `I4init` performs one volatile byte read from each
array before its ordinary module-local work, retaining both records through linker dead-strip.

## Type Lowering

### Builtins

- `int` lowers through the runtime integer typedefs in `compiler/shared/runtime/include/dea_rt.h`
- `byte`, `bool`, and `string` likewise lower through runtime-defined C-facing types
- `float` lowers to C `float` only when the enforced L1 floating-point contract is satisfied
- `double` lowers to C `double` only when the enforced L1 floating-point contract is satisfied
- `void` lowers to C `void`

Current L1 Binary Interface (LBI) naming policy is:

- Value symbols use the tagged-section encoding `__deaM<seg_len><seg>...N<sym_len><sym>[type-component]`, where the `M`
  section length-prefixes each module-path segment and the `N` terminal length-prefixes the value name. Functions append
  their function type component, so `std.integer::abs` with type `func(int) -> int` mangles as
  `__deaM3std7integerN3absF1ii`; plain `let` and `const` bindings omit the type component.
- Struct and enum type symbols use `S` and `E` terminals, for example `demo.main::Point` -> `__deaM4demo4mainS5Point`
  and `demo.main::Color` -> `__deaM4demo4mainE5Color`.
- Compiler-generated module symbols use the same `M` module section plus an `I` infrastructure section. Every module
  output defines external `I4init` and `I4fini` functions plus external `I8metadata` and `I7imports` arrays. A module
  with a resolved, zero-parameter, non-extern source `main` also defines external `I5entry`; for example, `std.integer`
  init is `__deaM3std7integerI4init`. This avoids collisions between dotted and underscored module names while keeping
  compiler infrastructure distinct from source-level values and nominal types.
- The encoding uses only ISO C99 identifier characters; no GCC `$`-in-identifier extension is required. See
  `l1/docs/specs/compiler/abi.md` for the normative spec.
- Exported symbols keep global linkage in generated C and the resulting object file.
- Non-exported top-level symbols are emitted as `static` to allow C compiler optimization.
- Exported `const` bindings are emitted with global linkage (without `static`) to satisfy ABI linking, overruling the
  internal-only `static const` default for non-exported constants.
- `DEA_*` for public generated/runtime preprocessor names.
- `rt_*` for stable runtime API entry points used by generated C and stdlib declarations.
- `_rt_*` for private runtime helpers.
- `_dea_*` / `_DEA_*` for other private runtime names.

The emitter uses these rules to ensure C identifier hygiene and stable link-time identity. The entire `__dea` prefix is
reserved: generated C uses it only for mangled L1 source or compiler-generated infrastructure symbols, and object
inspection treats every external definition whose normalized name starts with `__dea` as Dea evidence even when its
suffix is malformed.

Generated output now includes the public runtime header `dea_rt.h`. The internal helper `dea_siphash.h` lives only in
the compiled runtime implementation and is not part of the generated-C surface or the public L1 ABI.

Runtime artifacts are produced per toolchain: the official archives (`libdea_rt.a`, `libdea_rt_traced.a`,
`libdea_rt_check_basic.a`, and `libdea_rt_unchecked.a`) match the platform compiler's object format, while tcc
additionally builds raw `.o` objects under `build/dea/runtime/tcc/{default,traced,check_basic,unchecked}/`. When the
active C compiler family is tcc, the build driver links those objects directly to avoid object-format mismatches such as
Darwin tcc ELF objects versus platform Mach-O archives.

Each archive and tcc object variant depends on a content-sensitive build-configuration stamp recording its compiler,
runtime flags, mode defines, and baked tuning flags. Make therefore rebuilds affected variants when configuration
changes and preserves no-op incremental builds when the content is identical.

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

- user-defined structs lower to C structs with mangled LBI names
- enums lower to tagged unions with LBI-mangled tag names
- function pointer types lower to signature-specific `dea_func_*` typedefs over plain C function pointers
- variadic L1 function types lower their final `T...` parameter as the same `T[]` descriptor used by fixed slice
  parameters; semantic and LBI identity still distinguish the two function types
- pointer-shaped nullable values use `NULL` representation
- non-pointer nullable values lower to wrapper structs carrying `has_value` plus the wrapped value
- suffix order therefore affects layout visibility across modules: `T*?` remains a pointer-shaped nullable and needs
  only `T`'s declaration, while `T?*` points to a wrapper whose definition embeds `T` and needs `T`'s full layout
- non-null values used in matching nullable contexts lower to present wrappers; for example, returning `0 as ulong` from
  a `ulong?` function stores the converted `ulong` payload in `dea_opt_ulong`
- explicit integer casts to nullable integer targets lower as a checked cast to the inner C type followed by wrapper
  construction; for example, `0 as ulong?` lowers through the same `int` to `ulong` range check as `0 as ulong`
- fixed-size arrays lower to generated wrapper structs named with the ABI type-component layer, for example `byte[1024]`
  -> `__deaA1024_h` and `int[2][3]` -> `__deaA2_A3_i`; the wrapper contains one `data` field, and adjacent dimensions
  lower as contiguous C arrays such as `data[2][3]`
- slices lower to generated descriptor structs named from the element ABI type-component, for example `int[]` ->
  `__deaWi` and `int*[]` -> `__deaWPi`; each descriptor is
  `typedef struct __deaW... { dea_int len; T *data; } __deaW...;`, and descriptor copies are ordinary value copies with
  no retain, release, cleanup, or ownership transfer

## Statement and Expression Lowering

Implemented lowering currently includes:

- literals, local/global references, unary/binary operators, direct and indirect calls, field/index access, casts, and
  constructors
- `new` allocation and sized `drop` begin/finish via runtime helpers; begin validates exact `new` provenance, pointee
  extent, and alignment before recursive owned-field cleanup
- `if`, `while`, `for`, `match`, `case`, `with`, `break`, `continue`, and `return`
- `expr?` null-propagation lowering with early return on empty
- checked integer arithmetic and narrowing via runtime helpers
- contextual array literals, array constructors, `new T[N]`, `sizeof(T[N])`, whole-array value copies, and checked array
  indexing
- `len` and `slice` intrinsics, contextual `T[N] -> T[]` conversion, and checked slice indexing
- variadic direct and indirect calls, including empty descriptors, scope-owned fixed-array packs, and pass-through
  `pack...` slice forwarding

## Ownership and Cleanup Model

The backend is responsible for scheduling cleanup; the emitter materializes the concrete C.

Key rules:

- ARC-managed `string` values use runtime retain/release helpers
- returning an owned local may be lowered as a move
- scope exit cleanup runs in reverse declaration order
- early exits run pending `with` cleanup before normal owned-value cleanup
- `for` initialization and update execute in the surrounding loop context; body loop control alone targets the new
  `for`, and condition-false/body-break exits clean initialization-scope ARC values once
- abrupt `with` cleanup replaces the pending exit, while cleanup fallthrough resumes it; inline cleanup remains LIFO
- enum and struct cleanup recursively releases owned fields for active values
- arrays whose element type transitively contains ARC-managed data participate in retain and cleanup; cleanup walks
  elements in reverse index order
- raw-pointer indexing inside `unsafe func` lowers through runtime pointer validation in checked and `--check-basic`
  builds, with basic mode retaining exact-base validation while eliding interior treap lookups, and to direct C indexing
  in `--unchecked` builds; side-effectful lvalue bases or indexes are captured once so writes preserve single evaluation
  of both operands
- fixed-size array values lower at the wrapper boundary; flattened nested rows are raw C arrays only inside dedicated
  array helper paths
- fixed-size array indexing emits a bounds check that calls `_rt_panic_oob(index, length)` before accessing `.data`
- slice descriptors are non-owning and do not retain or clean up elements; fixed-array rvalues materialized as slice
  backing storage are registered for normal scope cleanup when their element type transitively contains ARC-managed data
- in per-module output, `I4fini` cleans only ARC-managed top-level `let` values owned by that module; it never cleans
  imported storage or calls another module's finalizer
- ordinary variadic arguments are initialized into a synthetic owning fixed-array wrapper and cleaned up with the
  surrounding scope; spread forwarding emits only the contextually converted slice descriptor
- `len(slice)` reads `.len`, `len(array)` is the compile-time length, and `len(string)` calls `rt_strlen`; slice
  indexing checks `index < 0 || index >= .len` with `_rt_panic_oob` before `.data[index]`, and `slice(...)` range
  construction checks `start`/`count` against the base length before forming the descriptor (a zero-length result uses
  `len = 0` and `data = NULL`)

See [ownership.md](ownership.md) for the language-facing ownership rules that this lowering must preserve.

## Entry Point Behavior

### Legacy process wrapper

When the entry module defines `main`, backend emits a host C `main(int argc, char **argv)` wrapper that:

- initializes runtime argument state
- calls the hidden global module-init chain when any imported module needs deferred top-level initialization
- calls the mangled L1 entry function
- returns `int` directly and maps `bool` `true` to host status `0` and `false` to `1`
- discards other return values and exits with `0`

### Per-module lifecycle and entry bridge

Every module translation unit defines an external `void I4init(void)` and `void I4fini(void)`. `I4init` performs only
the two metadata-retention reads followed by that module's deferred top-level initialization in established
within-module order. `I4fini` performs only that module's ARC-managed top-level cleanup. Apart from the retention reads,
either body has no work when the module has no corresponding initialization or cleanup, and neither function calls
another module's lifecycle entry point.

A module with a resolved, zero-parameter, non-extern source `main` definition also emits external `int I5entry(void)`,
even when source `main` is non-exported and therefore `static`. The bridge calls the source definition inside the same
translation unit, returns an `int` result directly, maps `bool` `true` to `0` and `false` to `1`, and calls every other
result form before returning `0`. It does not initialize runtime arguments or call `I4init` or `I4fini`.

## Debuggability

- generated C is emitted in labeled sections
- source mapping can include `#line` directives
- runtime tracing flags such as `--trace-arc` and `--trace-memory` are forwarded into generated C preprocessor toggles

## Current Constraints

1. Ordinary `--gen`, `--build`, and `--run` output remains one legacy whole-program `.c` file; the internal module
   generator emits one selected module without changing those flows.
2. The only implemented backend is the bootstrap backend in `stage1_l0`.
3. The runtime and ABI surface assume a C99-compatible host toolchain.
4. Optimization is delegated to the host C compiler; backend priority is correctness and explicit lowering.
5. Object inspection accepts supported relocatable ELF, Mach-O, and standard little-endian COFF objects only. COFF
   machine support is I386 (`0x014c`), ARM (`0x01c0`), ARMNT (`0x01c4`), AMD64 (`0x8664`), ARM64EC (`0xa641`), and ARM64
   (`0xaa64`); PE images, bigobj/import objects, and other machines including ARM64X (`0xa64e`) are rejected.
6. Symbol normalization is exact: ELF recognizes only canonical spellings plus Darwin TinyCC `___dea...` and `_main`
   aliases, Mach-O removes one leading underscore, COFF I386 removes one leading underscore, and COFF ARM64EC removes
   one leading `#` only from symbols whose COFF type marks a function.
7. Object inspection does not parse archives, shared libraries, relocations, debug information, or executable code, and
   it never invokes `nm`, `objdump`, or another host inspection tool.

## Testing Coverage

Current backend validation is centered on the copied bootstrap test suite under `compiler/stage1_l0/tests/`, especially:

- `backend_test.l0`
- `c_emitter_test.l0`
- `driver_test.l0`
- `build_driver_test.l0`
- `l1c_lib_test.l0`
- `object_metadata_test.l0`
- `object_reader_test.l0`

Ownership and trace-oriented validation also uses:

- `run_trace_tests.py`
- `run_test_trace.py`
- `check_trace_log.py`

These tests exercise the current bootstrap compiler implementation, not a self-hosted Stage 2 compiler.
