# L1 Initiative 0001 - Separate Compilation, Runtime Library, External Linking, and C FFI

- Date: 2026-04-15
- Status: Active
- Kind: Initiative

## Summary

This initiative sequences four interlocking goals that together turn the L1 compiler from a whole-program,
header-only-runtime, single-translation-unit producer into a real toolchain capable of building, linking, and binding C
libraries:

1. **Separate compilation and linking of L1 compilation units.**
2. **Move the runtime from header-only to a real static library.**
3. **Link external static and dynamic libraries from L1 programs.**
4. **Full C FFI / interoperability.**

The four goals share design surface, particularly around the C ABI, link-time identity, and the boundary between L1
types and C types, so this document captures the cross-cutting decisions, the phasing, and the dependencies. Individual
phases will spawn entries under `l1/work/plans/features/` and `l1/work/plans/refactors/` as they become actionable.

This initiative executes under the L1 roadmap ([`l1/docs/roadmap.md`](../../docs/roadmap.md)).

## Non-goals

- **Module system overhaul.** Module naming, import semantics, and qualified-name disambiguation remain as in L0. We add
  per-module artifacts; we do not redesign the module surface.
- **Package management.** No registry, lock files, dependency resolver, or `Dea.toml` schema. External libraries are
  reached through CLI flags; package management is a later concern.
- **Dynamic loading at runtime.** The runtime gets no `dlopen`/`LoadLibrary` shim. Dynamic linking here means classic
  load-time linking against a `.so`/`.dylib`/`.dll`.
- **Backporting to L0.** L0 stays at one-TU, header-only runtime per the current `1.0.0` scope boundary. Everything in
  this initiative lands in `l1/`.
- **New calling conventions.** L1 emits and consumes only the platform default C calling convention. No `stdcall`,
  `vectorcall`, or similar.

## Current baseline

Relevant facts that constrain the plan:

- The L1 compiler emits **one C99 translation unit per program**.
- The L1 backend reference ([`l1/docs/reference/c-backend-design.md`](../../docs/reference/c-backend-design.md)) is the
  current source of truth for L1 generated C behavior.
- The runtime (`compiler/shared/runtime/l1_runtime.h` plus the internal `dea_siphash.h` include) is **header-only**:
  every callable is `static` or `static inline` and is inlined into the single TU at build time.
- Optional tracing (`DEA_TRACE_ARC`, `DEA_TRACE_MEMORY`) is wired through preprocessor toggles resolved at user-TU
  compile time by `--trace-arc` and `--trace-memory`.
- Build/run mode currently discovers runtime headers with `--runtime-include` / `L1_RUNTIME_INCLUDE` and runtime
  libraries with `--runtime-lib` / `L1_RUNTIME_LIB`. L1 does not ship a separate runtime archive yet; the current Stage
  1 build driver only checks that the configured runtime-library path is a directory and forwards it as a search path.
  It does not validate specific archive filenames or inject a concrete runtime archive name yet.
- `extern func` is the only FFI primitive. Extern symbols are intentionally **not name-mangled** at the C boundary;
  everything else uses `dea_{module}_{name}`-style mangling.
- Integral and floating-point scalar types are already implemented in L1's surface and runtime; the FFI work below
  treats them as fully available.
- `compiler/stage1_l0/` is the only implemented L1 compiler today. `compiler/stage2_l1/` is a placeholder for the future
  self-hosted L1 compiler, so every change in this initiative lands first in Stage 1. Once Stage 2 exists, equivalent
  behavior must be ported there with Stage 1 acting as the L1 behavioral oracle.

## Phase 0 - Anchor decisions before coding

These decisions ripple through every subsequent phase. Each gets a small design note (filed under
`l1/docs/specs/compiler/` once accepted) before the corresponding phase plan opens.

### 0.1 Module artifact format (`.l1m`)

Separate compilation needs a serialized "module interface", the slice of `AnalysisResult` (signatures, struct/enum
infos, top-level `let` types, exported symbol table, ABI hashes) needed to type-check importers without reparsing
implementation sources.

Two viable shapes:

- **Text/L1-source-like** (`.l1m` written as a constrained L1 declaration file): readable, diff-able, parseable by the
  existing parser with a stripped-down accept set, trivial to bootstrap. Higher parse cost on every importer.
- **Binary arena dump**: compact, fast to load, requires a stable serialization codec and a schema-versioning story.

**Recommendation:** start with the text format. The cost of reparsing interfaces is negligible compared to compiling
implementations, and the diff-ability preserves the property that self-hosted bootstrap fixed-points are inspectable.
Revisit if profiling shows interface parsing dominates incremental builds.

### 0.2 Visibility model

Today every top-level symbol in a module is implicitly visible to importers. Once symbols become link-time identities,
that turns the entire module's internal helper surface into an exported ABI. We need an explicit marker for the
public/private split.

Open question: introduce a `pub` modifier (Rust-like), an `export` modifier (Zig-like), or invert to `priv`/`local`? The
choice affects every existing module in the L1 stdlib. Recommend `pub` as the addition (additive change,
default-private) but only after auditing the impact on the bootstrap stdlib.

### 0.3 C ABI identity and link-symbol mangling

With separate compilation the mangled name is the link-time identity. Decisions to fix:

- Keep `dea_{module}_{name}` as the canonical scheme, or switch to a more structured scheme that encodes the module path
  explicitly (e.g., `_D{len}{module}{len}{name}`) for tooling parity.
- Whether to expose **per-symbol ABI hashes** in the interface file so the linker driver can detect stale `.o`s with a
  clean diagnostic instead of relying on the platform linker to surface a mismatch as undefined-symbol noise.
- How the `pub`/`extern` markers interact with mangling: `extern func` already opts out of mangling for FFI; internal
  `pub` symbols stay mangled.

### 0.4 Boundary between L1 types and C types

The cornerstone for Phase 4. Decide which L1 constructs cross the FFI boundary unwrapped versus through a wrapper, and
codify a closed set of "FFI-safe" types:

- Integral and floating-point scalars cross unwrapped (already true today).
- `bool` crosses as the underlying C `_Bool` (or `dea_bool`).
- `string` **never** crosses unwrapped; it carries ARC and length metadata. A new boundary type (`cstr`, or a documented
  `byte*` discipline) is needed.
- Pointers (`T*`, `T*?`) cross as raw C pointers; ownership annotations are L1-side only.
- Owned `struct`/`enum` types do not cross; only `extern struct`/`extern enum` do.
- L1 `T?` over non-pointer `T` does not cross; the wrapper struct is L1-only.

Anything outside this set produces a dedicated diagnostic at the FFI boundary.

### 0.5 Where runtime symbols live

Once the runtime is a real static library, the `_rt_*` and `rt_*` symbols currently defined in `l1_runtime.h` become
external. That changes how `extern func rt_foo(...)` resolves:

- **Today:** the L1 declaration matches an inline `static` definition pulled in via `#include`.
- **After Phase 1:** the L1 declaration matches an `extern` declaration in a slim public header, backed by a runtime
  archive. The proposed target names are `dea_rt.h`, `dea_siphash.h`, `libdea_rt.a`, and `libdea_rt_traced.a`, but the
  Phase 1 plan must verify whether those names should replace or coexist temporarily with the current `l1_runtime.h`
  header name and any temporary artifact-name compatibility bridge.

This is a header-vs.-prototype split with no language semantics change, but it requires deciding whether trace builds
ship as a separate archive (`libdea_rt_traced.a`) or whether tracing becomes runtime-toggleable. Recommend the
separate-archive approach to preserve current behavior.

## Phase 1 - Runtime as a static library (Goal 2)

Smallest, most contained change. Do it first because it shakes out the FFI and link-driver pieces in miniature without
language semantics moving.

### Scope

- Split the current `compiler/shared/runtime/l1_runtime.h` header into a public header (prototypes, type definitions,
  public macros) plus one or more `.c` files grouped by subsystem: `dea_rt_string.c`, `dea_rt_io.c`, `dea_rt_alloc.c`,
  `dea_rt_hash.c`, `dea_rt_time.c`, `dea_rt_panic.c`, `dea_rt_math.c`. Truly internal helpers stay `static` inside their
  `.c`.
- Decide whether `dea_siphash.h` stays as a distinct internal helper include or folds into the same runtime-archive
  split, so L1 does not freeze a new public runtime layout around an unnecessary helper-header boundary.
- Trace builds are a second archive, `libdea_rt_traced.a`, compiled with `DEA_TRACE_ARC` and `DEA_TRACE_MEMORY`. The
  user-TU build no longer needs the trace toggles at compile time; the build driver picks the archive. (Trace flag
  *names* on the CLI stay as today.)
- `make runtime` produces `build/dea/lib/libdea_rt.a`, `build/dea/lib/libdea_rt_traced.a`, and copies headers under
  `build/dea/include/`.
- Once the L1 install workflow exists, `make install` lays out `$(PREFIX)/lib/libdea_rt*.a`,
  `$(PREFIX)/include/dea_rt.h`, `$(PREFIX)/include/dea_siphash.h`, plus any other public headers.
- The build driver appends `-I$(L1_HOME)/include -L$(L1_HOME)/lib -ldea_rt` (or `-ldea_rt_traced` when tracing) instead
  of relying on `#include` to inline the runtime. This is a migration of the current `--runtime-include` /
  `L1_RUNTIME_INCLUDE` and `--runtime-lib` / `L1_RUNTIME_LIB` directory plumbing into explicit `libdea_rt*` linkage once
  the real runtime archive exists.

### Validation

- Current Stage 1 validation (`make test-stage1` and `make test-all`) must still pass. Once `stage2_l1` and L1
  triple-bootstrap exist, the retained-C identity check needs to ignore the now-trivial prologue differences (no inline
  runtime body in the user TU).
- A new test compares `nm libdea_rt.a` output against a checked-in symbol manifest, locking the exported runtime
  surface. Adds/removes to that surface require an explicit manifest update in the same change.
- `tcc` validation: confirm link-order behavior. Keep the runtime archive listed *after* the user object on the link
  line. If `tcc` needs `--whole-archive`-equivalent treatment for any always-linked symbols (e.g., `_rt_panic`
  referenced from inlines that no longer exist), document it in the build driver.

### Risks

- `tcc` link semantics on Windows/MinGW are the most likely sharp edge.
- Trace-build duplication doubles the test matrix for runtime builds. Acceptable, but worth measuring.

## Phase 2 - Separate compilation of L1 CUs (Goal 1)

The largest piece. The current `CompilationUnit` is *the program*; in L1, a CU becomes *one compilable module*, and a
program is a *link set* of CUs plus libraries.

### 2a. Pipeline split

Today the pipeline runs name-resolution -> signatures -> locals -> expr-types -> backend over the whole closure. After
the split:

```
                     +-- one .l1 source --+
                     |                    |
                     v                    v
        parse + name-resolve       (load .l1m for each import)
                     |
                     v
              signatures (own module only,
              imported signatures replayed
              from interface files)
                     |
                     v
              locals + expr-types (own module)
                     |
                     v
        +------------+--------------+
        |                           |
        v                           v
   emit .l1m (interface)    emit .c (one TU per module)
                                    |
                                    v
                            cc -c -> .o
```

The driver gains three new modes; the existing whole-program `--build`/`--run` are preserved as convenience
orchestrators that fan out compile + link:

- `--emit-interface <module>` writes `<module>.l1m`.
- `--compile <module>` writes `<module>.c` and `<module>.o`. Requires `.l1m` for every import on the search path.
- `--link <module> [<module> ...] -o <out>` drives the C linker, writes the executable. At least one module must define
  `main`.

`--build` and `--run` compute the import closure, fan out per-module compile, then link. This preserves the current
developer experience and keeps the bootstrap simple.

### 2b. Backend changes

`be_emit_function_definitions` walks every unit in the closure today. After the split it walks only the current module;
everything imported is **declared** but not defined. Per-module C output contains:

- forward declarations for every type reachable from the module's signatures (own + imported);
- `extern` declarations for imported functions and top-level lets;
- full definitions for the module's own types, lets, and functions.

Struct layouts must be identical across TUs that see them. The simplest path: every importer re-emits the imported
struct as a C declaration in its own TU, identically mangled and field-ordered. The interface file therefore carries the
full structural layout, not just an opaque tag.

A new "main wrapper" pseudo-module produces the `main(int argc, char **argv)` shim and is compiled separately when an
executable is requested. It depends only on the entry module's interface.

### 2c. Interface-file consistency

Each `.l1m` carries an **ABI hash** computed from canonicalized signatures (function types, struct layouts, enum tags
and payload types, extern declarations). Each `.o` records the hash of every interface it consumed, emitted as a small
const data symbol (e.g., `static const char dea_imp_hash_<importer>_<imported>[] = "...";`) or as a custom section where
the platform supports it.

At link time the driver verifies the importer hashes against currently-installed `.l1m` files; mismatches yield a clean
diagnostic ("module X was compiled against Y v=abc, but Y is now v=def; recompile X") instead of UB at runtime.

### 2d. Make and bootstrap

Current L1 validation is Stage 1-only. Phase 2 must update the Stage 1 build/test workflow first, including any
repo-local `make` targets and test helpers that currently assume one generated C file.

When `stage2_l1` exists and L1 triple-bootstrap is introduced, the bootstrap test should rebuild the compiler as: emit
per-module interface -> per-module C -> per-module `.o` -> link. The fixed-point property should hold per-module:

- byte-identity for each `.l1m`,
- byte-identity for each per-module `.c`,
- byte-identity for each `.o` (modulo the same documented `tcc` and Windows exceptions that L0 already carries).

This is stricter than a whole-program identity check and a real diagnostic win: drift is caught at module granularity.

### 2e. Diagnostic surface

Module/interface and link-driver failures should first be mapped onto the existing shared diagnostic families where they
fit: `PAR-*` for interface-file syntax, `SIG-*` / `TYP-*` for semantic incompatibilities, `DRV-*` for source/module
discovery, and `L1C-*` for build/link-driver execution errors. New `MOD-*` or `LNK-*` families should be introduced only
if a phase plan proves that the existing family split would make user diagnostics or parity policy materially worse.

Concrete codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md` in the same change that implements the
diagnostic. Do not add placeholder `MOD-####` or `LNK-####` rows before concrete diagnostics exist.

### 2f. Risks

- Determinism of per-module emission. The current single-TU emitter can produce stable output, but per-module emission
  still needs care around iteration order over hash-keyed tables in the analyzer.
- Incremental rebuilds without `make`-level help. Out of scope for this phase; the driver rebuilds whatever it's asked
  to. A future plan can add a build-graph cache.

## Phase 3 - Linking external libraries (Goal 3)

Once Phase 2 lands, this is mostly a CLI and build-driver story; the language doesn't move.

### CLI surface

Matches `cc` conventions, since users already know them:

- `-l<name>`: link library.
- `-L<dir>`: library search path.
- `-I<dir>`: additional C include path (for FFI headers; consumed by Phase 4 `extern` decls).
- `--rpath=<dir>`: for dynamic libraries.
- `--link-arg=<flag>`: escape hatch for raw linker flags.

These flags are accepted by `--link`, `--build`, and `--run`. They are forwarded as-is to the host linker; L1 has no
opinion on static vs. dynamic linkage.

The Phase 3 plan must reconcile this surface with the current L1 runtime options: `-I` is presently an alias for
`--runtime-include`, and `-L` is presently an alias for `--runtime-lib`. Either the runtime-specific short aliases must
be retired before `-I` / `-L` become C/include-library flags, or the external-linking CLI must choose different
spelling.

### Manifest support

Deferred. A per-module or per-package manifest file declaring required libraries is a natural fit once a
package-management story exists. Until then, CLI flags are sufficient.

### Documentation

Add a short user-facing page at `l1/docs/user/linking.md` covering the platform-specific expectations
(`.a`/`.so`/`.dylib`/`.lib`/`.dll`), the `tcc` caveats, and the recommended pattern for binding a C library (FFI binding
module + linker flags).

## Phase 4 - Full C FFI (Goal 4)

The only phase that meaningfully extends the type system. Today's FFI is a single primitive: `extern func` with no name
mangling. To bind C usefully we need extern types, extern globals, and a closed set of FFI-safe types enforced by the
analyzer.

### 4a. Extern declarations

Add the following declaration forms (each lexed as a contextual `extern` keyword on the head):

- `extern struct C_Foo { ... }`: declared layout, no L1 ownership, no `new`/`drop`. Field types are constrained to
  FFI-safe types.
- `extern struct C_Foo;`: opaque struct (size unknown); usable only behind a pointer.
- `extern type CFile;`: opaque type alias for C types whose internals never matter to L1. Usable only behind a pointer.
- `extern enum C_Mode { ... }`: C enum binding lowered as an integer with named constants. The underlying integral type
  is configurable (`extern enum C_Mode : int32 { ... }`).
- `extern let errno: int;`: extern globals.
- `extern func` already exists; gains an optional link-name override (`extern("foo_v2") func bind_foo(...)`) for cases
  where the L1 identifier and the C symbol must differ (mangled C++, versioned symbols, prefix conventions).

C variadic FFI remains part of this phase. The standalone feature plan
`l1/work/plans/features/2026-04-22-variadic-functions-noref.md` is limited to L1-defined variadic functions and does not
settle `extern func` variadic semantics.

All extern declarations participate in the visibility model from Phase 0.2: an extern declaration in a `pub` position
re-exports the C binding through L1's normal import path; otherwise it is file-local.

### 4b. FFI-safe type rules

Enforced in the analyzer with dedicated diagnostics selected under the Phase 4 diagnostic policy. A type is FFI-safe iff
it is one of:

- a builtin scalar (the full integral and floating-point set, `bool`, `byte`);
- a raw pointer `T*` or `T*?` where `T` is itself FFI-safe or an opaque extern type;
- an `extern struct` (by value or pointer);
- an `extern enum` (lowered as its underlying integer);
- a `cstr` (or documented `byte*` discipline) for null-terminated C strings.

Anything else, including L1 `string`, owned `struct`/`enum`, `T?` over non-pointer `T`, and function types without an
explicit C ABI marker, is rejected at the FFI boundary.

### 4c. Header binding strategy

Two viable options, neither of which moves the compiler surface:

1. **Manual binding files.** The user writes `.l1` modules with `extern struct`/`extern func` declarations matching a C
   header. Simple, robust, no toolchain dependencies. **Recommended for L1**; it is the only option that ships with the
   compiler.
2. **`bindgen`-style auto-generation.** A separate tool reads C headers and emits L1 binding modules. **Out of scope.**
   An L1 program can do this once L1 is solid; it doesn't need to be in the compiler.

### 4d. Lifetime and ownership at the boundary

`extern struct` instances are not ARC-managed and have no L1 destructor. The rule: ownership of pointers crossing the
FFI is documented per declaration; L1 makes no claims and runs no cleanup. Idiomatic L1 wrappers (`with`/`cleanup`) over
raw FFI calls remain the standard pattern, exactly as `sys.rt` is wrapped by `std.fs`/`std.io` today.

### 4e. Calling convention

Default and only convention is the platform's C convention (`cdecl` on x86-32, System V AMD64 on x86-64 POSIX, AAPCS on
ARM, MS x64 on Windows). No surface-level convention markers in L1.

### 4f. Diagnostic surface

FFI diagnostics should reuse existing families when the failure is really parse, signature, type, driver, or build
behavior. A new `FFI-*` family remains a candidate if the FFI boundary accumulates enough cross-cutting rules that
mapping them to `SIG-*` / `TYP-*` would obscure the user-facing meaning. Concrete `FFI-*` codes should not be registered
until an implementation change introduces them.

## Sequencing and dependencies

```
Phase 0 (decisions)
        |
        v
Phase 1 (runtime -> static lib) ---+
        |                          | (link mechanics learned here)
        v                          |
Phase 2 (separate compilation) <---+
        |
        +--------------------> Phase 3 (external libs)
        |
        v
Phase 4 (full C FFI)
```

- Phase 1 is independently shippable and de-risks Phases 2 and 3.
- Phase 2 is the longest and gates everything else.
- Phase 3 falls out almost for free once Phase 2 lands.
- Phase 4 is the most language-design-heavy and best done last, when the link/compile mechanics no longer move
  underneath it.

## Cross-cutting concerns

### Stage 1 oracle and future Stage 2 parity

Every change lands in `compiler/stage1_l0/` while L1 is Stage 1-only. `stage1_l0` remains the behavioral oracle:
equivalent conditions reuse identical diagnostic codes (including `ICE-####` where applicable), and tests lock the Stage
1 behavior.

When `compiler/stage2_l1/` is implemented, this initiative must preserve a Stage 1/Stage 2 parity contract for the
equivalent surface. That future parity requirement must not be phrased as a current two-stage implementation fact.

### Determinism

Every new artifact (`.l1m`, per-module `.c`, per-module `.o`) must be byte-deterministic so current Stage 1 tests can
assert stable output and future L1 triple-bootstrap can work at finer granularity. Iteration order over hash-keyed
tables in the analyzer must be canonicalized at every emission point.

### Documentation

Phases land with corresponding doc updates in the same change:

- New `l1/docs/specs/compiler/module-interface-format.md` (Phase 0.1, expanded in Phase 2).
- New `l1/docs/specs/compiler/abi.md` (Phase 0.3, finalized in Phase 2).
- New `l1/docs/reference/separate-compilation.md` (Phase 2).
- Substantial revision of the L1 backend-design reference (Phase 2 invalidates the "single C translation unit"
  assertion).
- Update to `l1/docs/reference/design-decisions.md` capturing the FFI policy (Phase 4).
- New `l1/docs/user/linking.md` (Phase 3) and `l1/docs/user/c-ffi.md` (Phase 4).

### Diagnostic-code registration

The shared diagnostic catalog is concrete-code based; it does not currently carry placeholder reservations. This
initiative therefore does not reserve fake `MOD-####`, `LNK-####`, or `FFI-####` rows up front.

Each phase plan must classify new diagnostics against the existing families first:

- `PAR-*` for interface-file or extern-declaration syntax.
- `SIG-*` / `TYP-*` for interface, ABI, and FFI type/signature failures.
- `DRV-*` for module/interface discovery.
- `L1C-*` for build/link-driver execution failures.

New `MOD-*`, `LNK-*`, or `FFI-*` families remain available if a concrete implementation phase proves a family boundary
is needed. In that case, register concrete codes in `docs/specs/compiler/diagnostic-code-catalog.md` in the same change
that implements their diagnostics.

### L0 isolation

L0 is unaffected by this initiative. The runtime split (Phase 1) is implemented in `l1/`'s copy of the runtime tree;
L0's header-only runtime stays as-is per the `1.0.0` scope boundary.

## Open questions

These need resolution during Phase 0 but are not pre-decided here:

01. **Visibility marker spelling.** `pub`, `export`, or invert to `priv`? Default to private or default to public for
    backward compatibility with the current implicit-export behavior?
02. **Mangling scheme.** Keep `dea_{module}_{name}` or adopt a length-prefixed scheme that round-trips through external
    tools more cleanly?
03. **ABI hash algorithm.** SipHash-1-3 (already in the runtime), BLAKE3 (cryptographic, larger dependency), or a
    deterministic content hash over the canonicalized interface text?
04. **`cstr` vs. `byte*` discipline.** Introduce a distinct `cstr` type with explicit conversions from/to `string`, or
    document a `byte*` convention with helper functions in `sys.ffi`?
05. **Trace runtime delivery.** Separate `libdea_rt_traced.a` archive (recommended) or runtime-toggleable tracing via
    function pointers?
06. **Runtime artifact transition.** Replace `l1_runtime.h` immediately, decide whether `dea_siphash.h` remains a
    separate helper header or folds into the same transition, and retire the inherited `libl0runtime.*` placeholder
    naming at the same time, or carry a short compatibility bridge while the build driver and docs move to `dea_rt.h`,
    `dea_siphash.h`, and `libdea_rt.*`?
07. **External-linking CLI.** Retire the current runtime-specific `-I` / `-L` aliases so they can match C compiler
    convention, or choose different external-linking flag spellings?
08. **Diagnostic family split.** Keep module/link/FFI diagnostics in existing families, or introduce concrete `MOD-*`,
    `LNK-*`, or `FFI-*` families once implementation pressure proves they are clearer?
09. **Top-level initialization across CUs.** How are top-level `let` initializers ordered and emitted once definitions
    are split across objects, especially when imported modules expose state?
10. **Manifest format for external libraries.** Defer entirely until package management exists, or accept a minimal
    `[link]` section in a per-module sidecar file early?

Each open question gets a short design note under `l1/docs/specs/compiler/` once decided.

## Spawned plans

(Filled in as phases become actionable. Each phase spawns one or more entries under `l1/work/plans/features/` or
`l1/work/plans/refactors/`. Cross-link from here to the spawned plans, and from each plan back to this initiative.)

- Phase 0.1: `l1/work/plans/features/<slug-tbd>.md`
- Phase 0.2: `l1/work/plans/features/<slug-tbd>.md`
- Phase 0.3: `l1/work/plans/features/<slug-tbd>.md`
- Phase 0.4: `l1/work/plans/features/<slug-tbd>.md`
- Phase 0.5: `l1/work/plans/features/<slug-tbd>.md`
- Phase 1: `l1/work/plans/refactors/<slug-tbd>.md`
- Phase 2: `l1/work/plans/features/<slug-tbd>.md` (likely several)
- Phase 3: `l1/work/plans/features/<slug-tbd>.md`
- Phase 4: `l1/work/plans/features/<slug-tbd>.md` (likely several)

## Glossary

- **CU**: compilation unit. In this initiative, a single L1 module compiled to one `.o`.
- **Interface file** (`.l1m`): serialized type and signature surface of a module, sufficient for importers to type-check
  without reparsing the implementation source.
- **ABI hash**: deterministic content hash over a module's canonicalized interface, used to detect stale `.o`s at link
  time.
- **FFI-safe type**: the closed set of types permitted across an `extern` boundary (Section 4b).
- **Link set**: the set of `.o` files plus libraries presented to the linker to produce one executable or library.
- **Opaque type**: an extern type whose layout is unknown to L1; usable only behind a pointer.
