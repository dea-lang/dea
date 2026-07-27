# L1 Initiative 0001 - Separate Compilation and External Linking

- Version: 2026-07-27
- Status: Active
- Kind: Initiative
- Open plans:
  - `l1/work/plans/features/2026-07-24-per-module-generated-c-mode-noref.md`
  - `l1/work/plans/features/2026-07-17-link-set-driver-and-wrapper-noref.md`
  - `l1/work/plans/features/2026-07-17-build-run-multi-cu-orchestration-noref.md`
  - `l1/work/plans/features/2026-04-24-external-library-linking-cli-noref.md`
- Closed plans:
  - `l1/work/plans/bug-fixes/closed/2026-07-26-stage1-cross-platform-ci-regressions-noref.md`
  - `l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md`
  - `l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md`
  - `l1/work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md`
  - `l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md`
  - `l1/work/plans/bug-fixes/closed/2026-07-20-stage1-module-graph-invariant-hardening-noref.md`
  - `l1/work/plans/bug-fixes/closed/2026-07-20-stage1-module-interface-resolution-hardening-noref.md`
  - `l1/work/plans/features/closed/2026-04-24-export-manifests-and-aliased-imports-noref.md`
  - `l1/work/plans/features/closed/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md`
  - `l1/work/plans/features/closed/2026-04-24-module-interface-emission-noref.md`
  - `l1/work/plans/features/closed/2026-06-13-opaque-type-exports-and-layout-hiding-noref.md`
  - `l1/work/plans/features/closed/2026-04-24-separate-compilation-driver-surface-noref.md`
  - `l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md`
  - `l1/work/plans/features/closed/2026-04-24-multi-cu-initialization-and-link-order-noref.md`
  - `l1/work/plans/features/closed/2026-04-24-interface-fingerprints-and-object-metadata-noref.md`

## Summary

This initiative sequences two interlocking goals that together turn the L1 compiler from a whole-program,
single-compilation-unit producer into a toolchain capable of compiling and linking modules independently:

1. **Separate compilation and linking of L1 compilation units.**
2. **Link external static and dynamic libraries from L1 programs.**

The two goals share design surface around the C ABI and link-time identity, so this document captures the cross-cutting
decisions, the phasing, and the dependencies. Individual phases will spawn entries under `l1/work/plans/features/` and
`l1/work/plans/refactors/` as they become actionable.

This initiative executes under the L1 roadmap ([`l1/docs/roadmap.md`][roadmap]).

## Related initiatives

- **Initiative 0002 - L1 Runtime Library** ([`closed/0002-runtime-static-library.md`][runtime-library]) is a soft
  prerequisite. It moves the runtime from header-only inclusion to a real static archive, which de-risks the link
  mechanics that this initiative depends on. Separate compilation can land independently, but the link model is cleaner
  once 0002 has settled archive linkage and the trace-variant story.
- **Initiative 0003 - C FFI** ([`0003-c-ffi.md`][c-ffi]) is a downstream consumer. C FFI requires the LBI mangling
  defined here, the separate-compilation driver surface, and the external-library linking CLI before it can express
  `extern "C"` declarations and the closed FFI-safe boundary. This initiative also owns the explicit `--foreign-object`
  path by which metadata-free C relocatable objects satisfy current unmangled `extern func` declarations and future
  `extern "C"` declarations without joining the Dea module graph.

## Non-goals

- **Package-system overhaul.** This initiative adds explicit export manifests plus namespaced import forms such as
  `import math as m;` and `import abs, pi from math;`, but it does not introduce packages, a registry, a dependency
  resolver, or a new manifest format.
- **Package management.** No registry, lock files, dependency resolver, or `Dea.toml` schema. External libraries are
  reached through CLI flags; any package-management direction is deferred indefinitely unless and until Dea decides to
  adopt one.
- **Dynamic loading at runtime.** The runtime gets no `dlopen`/`LoadLibrary` shim. Dynamic linking here means classic
  load-time linking against a `.so`/`.dylib`/`.dll`.
- **Runtime-library refactor.** Moving `l1_runtime.h` from header-only inclusion to a real static archive lives in
  Initiative 0002. This initiative consumes whatever runtime-link model 0002 settles on but does not redesign it.
- **Full C FFI surface.** `extern "C"` declarations, `cstr`, and the closed FFI-safe type boundary live in Initiative
  0003\. This initiative defines only the LBI mangling and link mechanics that 0003 builds on.
- **Backporting to L0.** L0 stays at one compilation unit per the current `1.0.0` scope boundary. Everything in this
  initiative lands in `l1/`.

## Current baseline

Relevant facts that constrain the plan at the time of writing:

- Ordinary build/run still emits **one generated C99 compilation unit per program** through the legacy backend.
  Compile-only uses the internal module backend to emit and publish exactly one selected source-backed module with
  endpoint rollback; multi-CU orchestration is not operational yet.
- The L1 backend reference ([`l1/docs/reference/c-backend-design.md`][backend-design]) is the current source of truth
  for L1 generated C behavior.
- Modules support explicit export manifests plus alias and selective import forms. Exported top-level declarations keep
  external C linkage; non-exported top-level functions and storage use `static` where the current single-CU backend can
  do so without changing semantics.
- Generated L1-defined value and function symbols use LBI `M...N...` names, nominal structs and enums use `M...S...` and
  `M...E...`, and compiler-generated module infrastructure uses `M...I...`. Everything inside a legacy `extern func`
  declaration is intentionally **not name-mangled**; this is the only FFI primitive in the language today.
- Deterministic textual `.l1m` emission, constrained parsing, canonical artifact association, interface-first discovery,
  transitive graph-backed replay, canonical whole-module fingerprinting, and pre-registration verification are
  implemented through internal APIs. Per-module C output embeds provider identity, fingerprint, entry, and ordered
  direct-import records, and bounded readers inspect ELF, Mach-O, and PE/COFF relocatables. Ordinary build/run imports
  remain source-based, and link-set provider-object consistency enforcement does not exist yet.
- The shared driver CLI implements L1 `-c` / `--compile` with ordered `-I` / `--interface-path` roots, interface-only
  import resolution, object-only host compilation, and endpoint-rollback `.o` / `.l1m` publication. `--keep-c` adds the
  exact generated `.c`; ordinary compile-only leaves that companion path untouched. Successful return leaves the
  complete new selected set, recoverable failure restores the exact prior set, and failed rollback retains recovery
  files. Sequential publication does not provide a reader-visible snapshot. Runtime discovery uses `-Ri` / `-Rl`;
  host-C, root, generated-C, and log controls use the coordinated semantic short namespaces. Standalone `--link`,
  `--entry`, and `--foreign-object` do not exist yet.
- `compiler/stage1_l0/` is the only implemented L1 compiler today. `compiler/stage2_l1/` is a placeholder for the future
  self-hosted L1 compiler, so every change in this initiative lands first in Stage 1. Once Stage 2 exists, equivalent
  behavior must be ported there with Stage 1 acting as the L1 behavioral oracle.

## Phase 0 - Anchor decisions before coding

These decisions ripple through every subsequent phase. Each gets a small design note (filed under
`l1/docs/specs/compiler/` once accepted) before the corresponding phase plan opens.

### 0.1 Visibility model

Visibility is fixed at the **module level**, not per declaration.

- Modules may declare an explicit export manifest at the top of the file with `export`.
- `export *;` exports every symbol in the module, including names that start with `_`.
- `export foo, bar;` restricts the public API strictly to the listed names.
- If no `export` statement is present, the default export set is every top-level symbol except names starting with `_`.
- `_`-prefixed names are therefore private by convention unless the module opts into `export *;`.

The export manifest defines the `.l1m` surface and the link-visible ABI. Exported symbols keep global linkage in the
generated C and object output. Non-exported top-level symbols are emitted as `static` in generated C so the C backend
can still inline and dead-strip internal helpers.

### 0.2 C ABI identity and link-symbol mangling

With separate compilation the mangled name is the link-time identity. L1 adopts the tagged-section, length-prefixed LBI
scheme specified in [`l1/docs/specs/compiler/abi.md`][abi]:

- Source values and functions use `__deaM<seg_len><seg>...N<sym_len><sym>[type-component]`; structs and enums use the
  corresponding `S` and `E` terminals.
- Compiler-generated module infrastructure symbols use `__deaM<seg_len><seg>...I<name_len><name>`.
- **Canonical source form:** the input to mangling is the module's dotted path (for example `std.integer`), not its
  filesystem path. The compiler does not see `/` or platform path separators at the mangling stage.
- **Module path encoding:** each dotted module segment becomes one length-prefixed component in the `M` section. No
  character substitution or `$`-in-identifier compiler extension is required.
- **Identifier characters:** Dea source identifiers match `[A-Za-z_][A-Za-z0-9_]*`, so the boundary between a decimal
  length and the following component is unambiguous.
- **Stability:** this normalization is part of the LBI ABI and is stable across stages. Stage 2 must produce
  byte-identical mangled names for the same source surface.
- Example: `std.integer::abs` with type `func(int) -> int` becomes `__deaM3std7integerN3absF1ii`.
- Example: module infrastructure `std.integer::init` becomes `__deaM3std7integerI4init`.
- The scheme is chosen now so later overloading, generics, and additional module infrastructure entries can extend it
  without breaking existing object names.
- Declarations inside an `extern "C"` block bypass mangling and are emitted with their declared C spelling.

Phase 0.2 is completed by
[`l1/work/plans/features/closed/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md`][symbol-linkage].

### 0.3 Module artifact format (`.l1m`)

Separate compilation uses a textual `.l1m` interface file. The format stays human-readable and L1-source-like so the
bootstrap remains inspectable and the existing parser can be reused with a constrained accept set.

Each `.l1m` records the public surface of one module in canonical form:

- `module interface <name>;` as the file header.
- `fingerprint "<hash>";` immediately after the header.
- transparent `struct` and `enum` definitions with full layout so importers can recompute size and offset information.
- opaque `struct` and `enum` declarations as explicit name-only interface forms that expose the nominal name without
  exposing fields or variants.
- `func` declarations with signature only and a terminating `;`.
- `const` declarations with literal values inlined so importers can still constant-fold and pattern-match.
- `let` declarations with type only.

The export manifest itself is not emitted as a literal `export ...;` line in the `.l1m`. The file contains only the
exported declarations, so the manifest is reflected indirectly through which declarations are present. Modules with the
same effective public surface produce byte-identical `.l1m` content regardless of whether they used `export *;`, an
explicit allowlist, or the implicit default.

Symbols are emitted in sorted, deterministic order so the fingerprint is stable regardless of source ordering. A binary
encoding remains out of scope unless profiling later proves interface parsing is a material bottleneck.

Phase 0.3 establishes the `.l1m` artifact groundwork only. It defines and implements the writer/reader contract:
projection from analyzed source to a deterministic interface file, constrained parsing of that file, and replay into the
internal structures needed by compiler tests and later import plumbing. It does not switch ordinary `--build` or `--run`
flows to consume `.l1m` files, and any emission or round-trip surface exposed during this phase is internal or
testing-oriented rather than the stable separate-compilation UX.

Phase 2.a is the phase where `.l1m` files become normal driver inputs. It is intentionally split into smaller tranches
so the interface artifact, interface-backed analysis, CLI surface, compile-only artifact writer, and build/run fan-out
do not land as one tangled change. In particular:

1. `.l1m` artifact emission and parser round-trip can land without changing ordinary source-based `--build` or `--run`.
2. Direct `.l1m` import replay can land as semantic/codegen plumbing before the user-facing driver exposes full separate
   compilation.
3. `-c` and `-I` were reserved and validated before artifact production while help and diagnostics stated that compile
   mode was NYI. They became a usable workflow when compile-only output became one implementation module plus
   interface-backed imports, not a renamed whole-closure object.
4. `--build` and `--run` fan-out belongs to a later orchestration tranche that links the required provider objects.

### 0.4 Boundary between L1 types and C types

Moved to [Initiative 0003 - C FFI][c-ffi]. Anchors the closed FFI-safe type set, the `cstr` boundary type, and the
`string -> cstr` reinterpretation contract.

### 0.5 Where runtime symbols live

Moved to [Initiative 0002 - L1 Runtime Library][runtime-library]. Anchors the `extern func rt_foo` resolution model
after the runtime split, the trace-archive selection, and the public header layout.

### 0.6 Fingerprint algorithm and object metadata embedding

The `.l1m` fingerprint and the matching provider/consumer object-embedded fingerprint records share a single algorithm
and a single embedding strategy:

- **Algorithm:** SipHash-1-3 from the shared runtime ([`l1/compiler/shared/runtime/internal/dea_siphash.h`][siphash]).
  The runtime already exposes `siphash13(...)` with a 64-bit tag and is also the L0 oracle, so Stage 2 inherits the same
  symbol when it is built on top of the shared runtime.
- **Keying discipline:** the fixed 16-byte ASCII key `DeaL1-fp-v1-key!`, distinct from the runtime's randomized
  hash-flooding key. The constant is part of the LBI ABI and is stable across stages.
- **Digest size and encoding:** 64-bit digest. Textual `.l1m` values use the mandatory canonical spelling
  `sip13:<16 lowercase hexadecimal digits>`; an omitted tag does not select an implicit algorithm. SipHash-1-3 is the
  only supported version 1 algorithm. Object metadata version 1 embeds only the 8 raw digest bytes because its format
  version fixes the algorithm; a future algorithm requires a metadata-version change.
- **Object embedding:** every Dea per-module object emits portable C99 `const uint8_t` arrays with mangled names for its
  module identity, exported fingerprint, entry presence, and ordered
  `(imported module, expected dependency fingerprint)` records. The arrays are referenced from the module lifecycle
  `I4init` entry point so the platform linker's dead-strip pass cannot remove them. The driver discovers the records via
  bounded symbol-table readers for ELF, Mach-O, and PE/COFF, which also keeps the design `tcc`-compatible.
- **Metadata-free objects:** absence of the reserved Dea metadata marker is a distinct reader result, not an implicit
  authorization to join a link set. Metadata-free C relocatable objects enter only through `--foreign-object`; a present
  but malformed marker is always an error, and a metadata-bearing Dea object cannot be reclassified as foreign to bypass
  fingerprint, lifecycle, or entry checks.

The threat model is build-time staleness and corruption, not adversaries; cryptographic strength (BLAKE3, SHA-256) is
not required and would only add bootstrap-vendoring cost. Custom object sections were rejected because they require
per-format emitter and reader paths plus quirky compiler attributes that `tcc` does not fully support.

The completed [interface fingerprint plan][interface-fingerprints] and [ADR-0019][fingerprint-adr] fix the key and
public-surface canonicalization. The completed [object metadata plan][object-metadata] and [ADR-0021][metadata-adr] fix
the record layout, symbol naming, classification contract, and bounded object-reader limits.

## Phase 1 - Runtime as a static library

Phase 1 moved to [Initiative 0002 - L1 Runtime Library][runtime-library] and is complete. It split the L1 runtime into
public headers, normal and traced static archives, and the corresponding build-driver linkage model consumed here. The
phase number is retained in this initiative so the original four-phase sequence remains visible.

## Phase 2 - Separate compilation of L1 CUs (Goal 1)

> Phase numbers are kept aligned with the original four-phase numbering in the spawned plans (Phase 2.a/2.b/2.c, Phase
> 3). Phase 1 (runtime split) lives in Initiative 0002; Phase 4 (full C FFI) lives in Initiative 0003.

The largest piece. The current `CompilationUnit` is *the program*; in L1, a CU becomes *one compilable module*, and a
program is a *link set* of CUs plus libraries.

### 2a. Pipeline split and tranche boundaries

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
   emit .l1m (interface)    emit .c (one CU per module)
                                    |
                                    v
                            cc -c -> .o
```

The implemented interface artifact, direct replay, and CLI-reservation work form the closed foundation. The remaining
work is split by dependency, not by the former whole-plan labels:

1. **Artifact layout and module graph (complete):** canonical `.l1m`/object association, explicit source/interface
   precedence, transitive interface closure, ordered direct-import edges, and semantic `require` / `link` population.
2. **Interface fingerprints (complete):** canonical whole-module hash production and verification for emitted and
   consumed `.l1m` interfaces.
3. **Per-module backend and lifecycle ABI (complete):** target-only definitions, imported declarations, always-present
   external `I4init` / `I4fini`, and `I5entry` for every resolved, zero-parameter, non-extern source `main`.
4. **Object metadata and readers (complete):** emitted graph, fingerprint, and entry records against the finalized
   lifecycle anchor and added bounded ELF, Mach-O, and PE/COFF readers with valid/absent/malformed results.
5. **Compile-only artifacts (complete):** `-c` became operational after the final metadata-bearing artifact shape
   existed and now publishes `.o + .l1m` with endpoint rollback; `--keep-c` adds the exact generated C.
6. **Per-module generated C:** migrate `--gen` to the shared one-module backend, lock cross-mode generated-C identity,
   and stabilize compiler-visible compile-only paths. Retire the legacy whole-closure generator only after build/run
   fan-out migrates its remaining callers.
7. **Standalone link set:** validate Dea and explicit foreign objects, resolve the entry module, generate the executable
   wrapper, and invoke the host linker.
8. **Build/run fan-out:** preserve `--build` and `--run` as convenience commands by reusing the same compile and link
   APIs over the source/interface graph.
9. **External libraries:** extend the ordered link-input stream with libraries, rpaths, and raw host-driver arguments.

The driver ultimately exposes these contracts:

- `-c <module> [-o <canonical-object-path>] [--keep-c]` compiles one module without linking and publishes sibling
  `.o + .l1m` with endpoint rollback; `--keep-c` adds the exact generated `.c`.
- `--gen <module> [-I <dir>]... [-o <file>]` will emit exactly one per-module C translation unit. A selected imported
  interface is authoritative and sufficient without a sibling object; source fallback is allowed only when no interface
  is selected.
- `-I <dir>` adds an interface-search root. Explicit interfaces take precedence for imports; compile-only requires an
  interface for every import, while build/run may fall back to source and schedule that module for compilation.
- `--link <dea-object> [<dea-object> ...] [--foreign-object <c-object>]... [--entry <module>] -o <out>` links an
  executable. Positional objects require valid Dea metadata; metadata-free C relocatable objects require the explicit
  repeatable foreign-object option.

`--link` infers the entry when exactly one Dea object exposes `I5entry`. Multiple candidates require `--entry`; zero
candidates, an unknown selection, or a selected module without `I5entry` fail before host linking. `--build` and `--run`
use their source target as the internal entry selection, compute the import closure, fan out per-module compile, then
call the same link API.

Future build/run consumers that jointly read an authoritative `.l1m` and its sibling `.o` require stable inputs. The
caller must ensure each pair remains unchanged from interface selection through object verification and submission to
the common link API, serializing externally against compile-only publication or other same-stem writers. The
compile-only endpoint-rollback protocol does not supply a reader snapshot.

Name resolution also moves away from the current flat import surface. `import math as m;` introduces qualified access
through `m::abs(...)`, while `import abs, pi from math;` selectively imports named exports from the provider module. The
consumer always binds against the provider's exported surface as described by its `.l1m`; local aliases do not affect
the provider's link identity.

### 2b. Backend changes

The legacy generator continues to walk every source unit in the closure. The internal module generator instead walks
only the selected source-backed module; imported values are **declared** but not defined. Per-module C output contains:

- forward declarations for every type reachable from the module's signatures (own + imported);
- external declarations for imported functions and top-level lets; non-extern L1 symbols use their provider-owned
  mangled names, while C `extern` functions retain their declared C spelling;
- full definitions for the module's own types, lets, and functions, with exported symbols kept global and non-exported
  symbols emitted as `static`.

Transparent struct layouts must be identical across CUs that see them. The simplest path: every importer re-emits the
imported transparent struct as a C declaration in its own CU, identically mangled and field-ordered. Opaque nominal
types instead replay as name-visible, layout-hidden declarations: consumers may name them and use pointers to them, but
cannot emit by-value operations that require layout.

Every compiled Dea module exposes external, no-op-capable `I4init` and `I4fini` lifecycle functions. A module defining a
resolved, zero-parameter, non-extern source `main` also exposes `I5entry`, which can call a non-exported source function
inside the owning CU and normalize `int`, `bool`, or other return forms to a C `int` status.

The completed lifecycle contract is recorded by [ADR-0020][lifecycle-adr]. Ordinary build/run remains on the legacy
whole-program generator until graph fan-out lands.

A new wrapper pseudo-module produces the process-level `main(int argc, char **argv)` shim when an executable is
requested. The driver validates the metadata-bearing Dea graph, selects one `I5entry`, emits dependency-first `I4init`
calls, invokes only the selected entry bridge, emits `I4fini` calls in exact reverse order, and returns the normalized
status. Explicit foreign objects never participate in graph ordering, lifecycle calls, fingerprint verification, or
entry selection.

### 2c. Interface-file consistency and verification contract

Each `.l1m` carries a **fingerprint** computed from the canonicalized effective public surface (function signatures,
transparent struct layouts, transparent enum tags and payload types, explicit opaque nominal declaration markers,
exported `const` literals, exported top-level `let` types, and exported type aliases). The export manifest spelling is
not hashed verbatim; only the effective surface it produces participates. Verification is explicitly tiered:

1. **Producer stage:** compiling `foo.l1` computes the canonicalized public surface, hashes it, and writes the result to
   `foo.l1m` as `fingerprint "<hash>";`.
2. **Consumer stage:** an importer that reads `foo.l1m` re-hashes the declarations it parsed. If the recomputed value
   differs from the declared fingerprint, the interface file is rejected as corrupted or non-canonical.
3. **Linker stage:** the provider's compiled object embeds its own exported fingerprint in object metadata. The driver
   verifies that every consumer's recorded dependency fingerprint matches the provider object's embedded fingerprint
   before invoking the platform linker.

The textual dependency-record grammar remains, but each populated `require` / `link` hash is the referenced provider's
canonical `sip13:<16 lowercase hexadecimal digits>` whole-module fingerprint, repeated where necessary, rather than a
per-symbol ABI hash. Object consumer records collapse dependencies by module while retaining ordered direct-import
edges, including side-effect-only imports that a used-symbol list cannot reconstruct.

The fingerprint algorithm and the object-embedding strategy are anchored in §0.6. In short: SipHash-1-3 with a fixed
key, 64-bit digest, embedded in each `.o` as portable C99 `const uint8_t` arrays with mangled names, anchored against
dead-strip from the module's `I4init` lifecycle entry point, and discovered by the driver via symbol-table lookup.

This replaces any per-symbol ABI hash scheme. The diagnostic goal is a clean stale-interface or stale-object failure
instead of undefined-symbol noise from the platform linker. Metadata-free foreign objects are outside this contract and
may satisfy only ordinary unmangled C symbols; they cannot satisfy a Dea module dependency record.

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

Module/interface and link-driver failures map onto the existing shared diagnostic families: `PAR-*` for interface-file
syntax, `RES-*` for export-manifest and selective-import name resolution, `SIG-*` / `TYP-*` for semantic
incompatibilities (including fingerprint and public-surface mismatches), `DRV-*` for source/module discovery, and
`L1C-*` for build/link-driver execution errors (including provider-object metadata and link-time verification failures).
New `MOD-*` or `LNK-*` families are introduced only if a phase plan proves that the existing family split would make
user diagnostics or Stage 1 / Stage 2 parity policy materially worse. This is the closed answer to the diagnostic-family
open question; the catalog's organizing axis stays "what compiler phase noticed it" rather than mixing in a topic axis.

Concrete codes are registered in [`docs/specs/compiler/diagnostic-code-catalog.md`][diagnostic-catalog] in the same
change that implements the diagnostic. Do not add placeholder `MOD-####` or `LNK-####` rows before concrete diagnostics
exist.

### 2f. Risks

- Determinism of per-module emission. The current single-CU emitter can produce stable output, but per-module emission
  still needs care around iteration order over hash-keyed tables in the analyzer.
- Incremental rebuilds without `make`-level help. Out of scope for this phase; the driver rebuilds whatever it's asked
  to. A future plan can add a build-graph cache.

## Phase 3 - Linking external libraries (Goal 2)

Once Phase 2 lands, this is mostly a CLI and build-driver story; the language doesn't move.

### CLI surface

Matches `cc` conventions, since users already know them:

- `-l<name>` or `-l <name>`: link library.
- `-L<dir>` or `-L <dir>`: library search path.
- `-I<dir>` or `-I <dir>`: interface search path for `.l1m` discovery during separate compilation.
- `--rpath=<dir>`: for dynamic libraries.
- `--link-arg=<flag>`: escape hatch for raw linker flags.

`-l`, `-L`, `--rpath`, and `--link-arg` are accepted by `--link`, `--build`, and `--run`. They extend the typed ordered
link-input stream established for Dea and foreign objects; order-sensitive operands are not regrouped by category.
`--link-arg` denotes one host compiler-driver argument, while rpath spelling is translated per supported compiler
family. `-I` is consumed by the compiler driver during interface discovery for compile-involving flows. L1 has no
opinion on static vs. dynamic linkage.

The former runtime-specific short aliases retired in the CLI-surface tranche: `-I` is committed to interface search,
`-L` returns to its normal library-search meaning, and runtime paths use `-Ri` / `-Rl`. The validated runtime archive is
linked by its selected exact path so a user `-L` directory cannot shadow it. Until this phase implements external
linking, syntactically complete `-L` / `-l` uses report the shared reserved-option diagnostic. Today's binding workflow
uses legacy unmangled `extern func`; Initiative 0003 later adds `extern "C"`. Neither workflow requires a raw C-header
include-path flag in the core compiler.

### Manifest support

Deferred indefinitely unless and until Dea decides to adopt package management. External library link information is
user-side via CLI flags or build-tool configuration (Makefile, IDE task, shell wrapper). No per-module `[link]` sidecar,
no `Dea.toml`, and no other in-tree manifest format is introduced by this initiative. `--link-arg=<flag>` is the
universal escape hatch for any platform-specific oddity without committing to a schema.

[Initiative 0003 - C FFI][c-ffi] may revisit this if a binding-module-local hint mechanism turns out to be necessary
there; even then, prefer extending CLI ergonomics over introducing a new file format.

### Documentation

Add a short user-facing page at [`l1/docs/user/linking.md`][linking] covering the platform-specific expectations (`.a`/
`.so`/`.dylib`/`.lib`/`.dll`), the `tcc` caveats, and the recommended pattern for binding a C library (FFI binding
module + linker flags).

## Phase 4 - Full C FFI

Phase 4 moved to [Initiative 0003 - C FFI][c-ffi] and remains downstream of this initiative. It owns `extern "C"`,
`cstr`, and the closed FFI-safe type boundary. The phase number is retained here to preserve the original sequence.

## Sequencing and dependencies

```
implemented interface/CLI foundation
             |
             +----> artifact layout + module graph ----> lifecycle ABI ----+
             |                                                             |
             +----> interface fingerprints --------------------------------+
                                                                           |
                                                                           v
                                                                  object metadata
                                                                           |
                                                                           v
                                                              compile-only artifacts
                                                                  |                |
                                                                  |                +--> per-module --gen ----+
                                                                  v                                         |
                                                                 standalone link                            |
                                                                  |                                         |
                                                                  v                                         |
                                                                 build/run fan-out -------------------------+
                                                                  |
                                                                  v
                                                     retire whole-closure generator
                                                                  |
                                                                  v
                                                          external libraries
                                                                  |
                                                                  v
                                                        Initiative 0003 FFI
```

- Initiative 0002 is complete and supplies the runtime-archive model consumed by the link plans.
- Artifact-graph, fingerprint, lifecycle, object-metadata, and compile-only work are complete. Standalone linking is the
  next tranche and consumes the final module-object shape.
- Compile-only artifacts are operational with the final lifecycle and metadata records.
- Per-module `--gen` may migrate after compile-only; legacy generator removal waits for build/run fan-out.
- Standalone link owns object classification and wrapper construction; build/run then reuse that API rather than
  creating a second link path.
- External-library options extend the finished ordered input model. Initiative 0003 consumes both external libraries and
  the explicit metadata-free `--foreign-object` boundary.

Recorded near-term tranche checkpoints:

- [x] Finalize mangling and visibility defaults.
- [x] Finalize `.l1m` format and fingerprint verification contract.
- [x] Phase 0.1: parser support for `export` and `import ... as`.
- [x] Phase 0.2: C emitter symbol mangling logic.
- [x] Phase 0.3: `.l1m` interface emission and serialization.
- [x] Opaque export follow-up: source `export opaque { ... }`, exported-surface checks, and explicit `.l1m` opaque
  projection.
- [x] Phase 2.a.1: direct `.l1m` import replay and codegen plumbing.
- [x] Reserved and validated `-c` / `--compile` plus ordered `-I` / `--interface-path` while compile dispatch remained
  NYI.
- [x] Define artifact layout, transitive interface discovery, and the deterministic module graph.
- [x] Implement canonical whole-module fingerprints and `.l1m` verification.
- [x] Emit one module per CU with external `I4init`, `I4fini`, and conditional `I5entry`.
- [x] Emit and inspect provider/consumer object metadata.
- [x] Make compile-only artifact production operational.
- [ ] Migrate `--gen` to per-module output and lock cross-mode generated-C identity.
- [ ] Implement standalone Dea/foreign-object linking and entry selection.
- [ ] Convert `--build` / `--run` to the shared multi-CU compile/link APIs.
- [ ] Add ordered external-library and raw host-driver inputs.

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
tables in the analyzer must be canonicalized at every emission point. The
[per-module generated-C plan][per-module-generated-c] owns stable compiler-visible compile-only paths and the
supported-toolchain object-identity checks.

### Documentation

Phases land with corresponding doc updates in the same change:

- New [`l1/docs/specs/compiler/module-visibility-and-imports.md`][module-visibility] capturing export manifests,
  aliasing, and selective import.
- New [`l1/docs/specs/compiler/abi.md`][abi] (Phase 0.2, finalized in Phase 2).
- New [`l1/docs/specs/compiler/module-interface-format.md`][module-interface] (Phase 0.3, expanded in Phase 2).
- New [`l1/docs/reference/separate-compilation.md`][separate-compilation] (Phase 2).
- Substantial revision of the L1 backend-design reference (Phase 2 invalidates the "single generated C compilation unit"
  assertion).
- New [`l1/docs/user/linking.md`][linking] (Phase 3).

### Diagnostic-code registration

The shared diagnostic catalog is concrete-code based; it does not currently carry placeholder reservations. This
initiative therefore does not reserve fake `MOD-####` or `LNK-####` rows up front.

Each phase plan classifies new diagnostics against the existing phase-based families:

- `PAR-*` for interface-file syntax.
- `RES-*` for export-manifest and selective-import name resolution.
- `SIG-*` / `TYP-*` for interface and ABI type/signature failures, including fingerprint and public-surface
  compatibility mismatches.
- `DRV-*` for module/interface discovery.
- `L1C-*` for build/link-driver execution failures, including provider-object metadata and link-time verification
  failures.

This is the closed answer to the diagnostic-family open question. New `MOD-*` or `LNK-*` families remain available only
if a concrete implementation phase proves a family boundary is needed; in that case, register concrete codes in
[`docs/specs/compiler/diagnostic-code-catalog.md`][diagnostic-catalog] in the same change that implements their
diagnostics.

### L0 isolation

L0 is unaffected by this initiative. All changes land in `l1/`; L0's header-only runtime and single-CU model stay as-is
per the `1.0.0` scope boundary.

## Resolved decisions

The cross-cutting questions are closed. Each decision is anchored elsewhere in this initiative; this section summarizes
the chosen answer and points at the owning section.

1. **Fingerprint hash algorithm:** SipHash-1-3 from the shared runtime, keyed with a fixed compile-time-constant 16-byte
   fingerprint key and a 64-bit digest. Textual `.l1m` values require the lowercase `sip13:` tag plus 16 lowercase
   hexadecimal digits; there is no untagged default. Object metadata version 1 stores 8 raw digest bytes and fixes the
   algorithm through its format version. Cryptographic strength is not required for the build-time staleness threat
   model. Anchored in §0.6; sub-choices (exact key constant, encoding details, canonicalization rules) are owned by
   [interface fingerprints][interface-fingerprints].
2. **Object metadata format:** portable C99 `const uint8_t` arrays with mangled names, anchored against linker
   dead-strip from each module's `I4init` lifecycle entry point. Driver-side discovery uses symbol-table lookup, which
   works uniformly across ELF, Mach-O, and PE/COFF and stays compatible with `tcc`. Custom object sections were rejected
   because they force per-format emitter and reader paths plus quirky compiler attributes. Anchored in §0.6 and §2c;
   record layout, naming, size limits, and valid/absent/malformed classification are owned by
   [object metadata][object-metadata].
3. **Diagnostic family split:** keep the existing phase-based families (`PAR-*`, `RES-*`, `SIG-*`, `TYP-*`, `DRV-*`,
   `L1C-*`). New `MOD-*` or `LNK-*` families are introduced only if a concrete phase plan demonstrates the existing
   split materially worsens user diagnostics or Stage 1 / Stage 2 parity policy. Fingerprint validation uses `SIG-0280`
   through `SIG-0284`; `SIG-0285` to `SIG-0299` remain available. The former `SIG-0240` to `SIG-0259` anonymous
   embedded-member reservation was released when its feature plan was withdrawn; existing fingerprint assignments are
   unchanged, and any future embedded-member plan must re-check the live catalog. Object metadata retains `L1C-2050` to
   `L1C-2069`; every successor records its own non-overlapping provisional range and re-check requirement. Anchored in
   §2e and §Diagnostic-code registration.
4. **External-library manifest format:** deferred indefinitely unless and until Dea decides to adopt package management.
   Phase 3 ships with CLI flags only (`-l`, `-L`, `--rpath`, `--link-arg`, plus `-I` for interface search). No
   per-module `[link]` sidecar, no `Dea.toml`, no other in-tree manifest format. Initiative 0003 may revisit this if FFI
   bindings prove a binding-module-local hint mechanism is necessary, in which case extending CLI ergonomics is
   preferred over a new file format. Anchored in §Phase 3 / Manifest support.
5. **Foreign relocatable objects:** positional `--link` objects are verified Dea CUs. A metadata-free C relocatable
   object enters through repeatable `--foreign-object`; it may satisfy unmangled C symbols but has no Dea graph,
   fingerprint, lifecycle, or entry-point role. Valid or malformed Dea metadata cannot be hidden behind the foreign
   option. Archives and shared libraries remain under the external-library options. Anchored in §0.6 and §2a.
6. **Compile-only artifact publication:** compile-only publishes `.o + .l1m` by default and adds the exact `.c` only
   with `--keep-c`. Successful return leaves the complete new selected set; recoverable failure restores the exact prior
   set; failed rollback retains recovery files. Publication is sequential and requires external serialization for
   concurrent readers or same-stem writers. Anchored in §2a and recorded by [ADR-0022][compile-only-adr].
7. **Per-module generated C:** `--gen` treats a selected `.l1m` as sufficient without inspecting its sibling object,
   shares generated-C bytes with retained compile/build/run output, uses stable module-relative compiler-visible paths,
   and retires whole-closure generation only after all production callers migrate. Owned by the active
   [per-module generated-C plan][per-module-generated-c] and its future ADR.

FFI-specific open questions live in [Initiative 0003][c-ffi]; runtime-delivery open questions live in
[Initiative 0002][runtime-library].

## ADR Impact

- Decision: Use the established LBI mangling contract for externally visible L1 symbols.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0008-lbi-symbol-mangling.md`
  - Rationale: ADR-0008 records the canonical mangling grammar consumed by separate compilation and linking.
- Decision: Use explicit export manifests and aliased imports as the module visibility boundary.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0009-module-visibility-exports-imports.md`
  - Rationale: ADR-0009 defines which declarations cross compilation-unit boundaries and how consumers name them.
- Decision: Exchange module interfaces through the canonical `.l1m` artifact.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0014-module-interface-artifact.md`
  - Rationale: ADR-0014 records the interface format and replay contract used by separate compilation.
- Decision: Associate module interfaces, objects, and providers through one canonical module graph.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0018-canonical-artifact-association-and-module-graph.md`
  - Rationale: ADR-0018 records the artifact-association and dependency-graph rules owned by this initiative.
- Decision: Verify imported interfaces through canonical whole-module fingerprints.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0019-whole-module-interface-fingerprints.md`
  - Rationale: ADR-0019 records the hash, canonicalization, and verification contract.
- Decision: Emit each compilation unit through the per-module backend and lifecycle ABI.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0020-per-module-backend-and-lifecycle-abi.md`
  - Rationale: ADR-0020 records module-local emission and the initialization, finalization, and entry hooks used at link
    time.
- Decision: Embed and inspect portable object metadata to distinguish verified Dea objects from foreign objects.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0021-portable-object-metadata-and-inspection.md`
  - Rationale: ADR-0021 records metadata authority, representation, and classification.
- Decision: Publish compile-only object and interface artifacts with endpoint rollback from one output-local
  transaction.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md`
  - Rationale: ADR-0022 records the implemented artifact set, staging boundary, validation, publication order, rollback,
    and recovery behavior used by the remaining initiative plans.
- Decision: Make `--gen` produce one module rather than a whole source closure.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The per-module generated-C child plan owns this public compiler-artifact contract.
- Decision: Preserve generated-C bytes across generation, compile-only retention, and retained build/run output.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The per-module generated-C child plan owns the cross-mode identity rule.
- Decision: Use stable module-relative host-compiler paths for deterministic compile-only objects where the toolchain
  permits.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The per-module generated-C child plan owns deterministic compiler-visible staging.
- Decision: Remove the transitional legacy whole-closure generator after all production callers migrate.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0020-per-module-backend-and-lifecycle-abi.md`
  - Rationale: ADR-0020 explicitly preserved that generator only during the staged migration.
- Decision: Extend separate compilation and linking through the shared compiler CLI mode and option contract.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: ADR-0003 owns the cross-level CLI surface and rules for level-specific extensions.
- Decision: Organize separate-compilation and linking diagnostics by compiler phase, not topic-specific families.
  - Scope: Shared
  - Disposition: Amend ADR
  - ADR: `docs/decisions/0005-diagnostic-code-catalog.md`
  - Rationale: The shared diagnostic ADR should state the phase-oriented allocation rule settled by this initiative.
- Decision: Keep external dependencies CLI-only and ordered, without package or per-module link manifests.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The child external-linking plan owns the durable dependency and ordering contract selected by this
    initiative.

## Spawned plans

(Filled in as implementation tranches become actionable. Cross-link from here to the spawned plans, and from each plan
back to this initiative.)

Phase 0 decisions are now recorded directly in this initiative. They do not need separate spawned plans unless a later
implementation tranche proves that one decision area needs additional design work.

- Phase 0.1: parser/analyzer support for export manifests and aliased/selective imports under
  [`l1/work/plans/features/closed/2026-04-24-export-manifests-and-aliased-imports-noref.md`][export-imports]
- Phase 0.2: LBI symbol mangling plus exported-vs-internal linkage emission under
  [`l1/work/plans/features/closed/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md`][symbol-linkage]
- Phase 0.3: `.l1m` interface emission, canonicalization, and parsing contract under
  [`l1/work/plans/features/closed/2026-04-24-module-interface-emission-noref.md`][interface-emission]
- Opaque export follow-up: source-level opacity, exported-surface typing, and explicit opaque `.l1m` projection under
  [`l1/work/plans/features/closed/2026-06-13-opaque-type-exports-and-layout-hiding-noref.md`][opaque-exports]. Direct
  interface replay and fingerprint canonicalization consume the nominal visibility state this plan introduces.
- Direct interface replay and compile-CLI reservation are complete under the closed
  [compile foundation][compile-foundation]. The former initialization and end-to-end fingerprint drafts were closed as
  superseded when the dependency-safe split was recorded.
- Artifact association, interface discovery, and module-graph construction completed under
  [artifact graph][artifact-graph].
- Stage 1 module-interface resolution hardening completed under [module-interface-hardening].
- Canonical whole-module hashing and `.l1m` verification completed under
  [interface fingerprints][interface-fingerprints].
- Per-module definitions plus `I4init`, `I4fini`, and `I5entry` completed under
  [lifecycle entrypoints][lifecycle-entrypoints] and recorded by [ADR-0020][lifecycle-adr].
- Provider/consumer metadata and bounded object readers completed under [object metadata][object-metadata] and recorded
  by [ADR-0021][metadata-adr].
- Single-module artifact production with endpoint rollback completed under [compile only][compile-only] and is recorded
  by [ADR-0022][compile-only-adr].
- Per-module `--gen`, cross-mode generated-C identity, and legacy-generator retirement under
  [per-module generated C][per-module-generated-c].
- Standalone Dea/foreign-object linking, entry selection, and wrapper construction under [link set][link-set].
- `--build` / `--run` graph fan-out through shared compile/link APIs under [build/run fan-out][build-run].
- Phase 3: external-library linking CLI under
  [`l1/work/plans/features/2026-04-24-external-library-linking-cli-noref.md`][library-linking]

## Glossary

- **LBI**: Dea/L1 Binary Interface.
- **CU**: compilation unit. In this initiative, a single L1 module compiled to one `.o`.
- **Interface file** (`.l1m`): textual serialized public surface of a module, sufficient for importers to type-check
  without reparsing the implementation source.
- **Fingerprint**: deterministic content hash over a module's canonicalized public surface, written to `.l1m` and
  embedded in the provider object metadata.
- **Link set**: the set of `.o` files plus libraries presented to the linker to produce one executable or library.
- **Foreign object**: an explicitly supplied metadata-free C relocatable object. It may satisfy unmangled C symbols but
  is not a Dea module and has no fingerprint, lifecycle, dependency, or entry semantics.

[abi]: ../../docs/specs/compiler/abi.md
[artifact-graph]: ../plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[backend-design]: ../../docs/reference/c-backend-design.md
[build-run]: ../plans/features/2026-07-17-build-run-multi-cu-orchestration-noref.md
[c-ffi]: 0003-c-ffi.md
[compile-foundation]: ../plans/features/closed/2026-04-24-separate-compilation-driver-surface-noref.md
[compile-only]: ../plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md
[compile-only-adr]: ../../docs/decisions/0022-transactional-compile-only-artifact-publication.md
[diagnostic-catalog]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[export-imports]: ../plans/features/closed/2026-04-24-export-manifests-and-aliased-imports-noref.md
[fingerprint-adr]: ../../docs/decisions/0019-whole-module-interface-fingerprints.md
[interface-emission]: ../plans/features/closed/2026-04-24-module-interface-emission-noref.md
[interface-fingerprints]: ../plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[library-linking]: ../plans/features/2026-04-24-external-library-linking-cli-noref.md
[lifecycle-adr]: ../../docs/decisions/0020-per-module-backend-and-lifecycle-abi.md
[lifecycle-entrypoints]: ../plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md
[link-set]: ../plans/features/2026-07-17-link-set-driver-and-wrapper-noref.md
[linking]: ../../docs/user/linking.md
[metadata-adr]: ../../docs/decisions/0021-portable-object-metadata-and-inspection.md
[module-interface]: ../../docs/specs/compiler/module-interface-format.md
[module-interface-hardening]: ../plans/bug-fixes/closed/2026-07-20-stage1-module-interface-resolution-hardening-noref.md
[module-visibility]: ../../docs/specs/compiler/module-visibility-and-imports.md
[object-metadata]: ../plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md
[opaque-exports]: ../plans/features/closed/2026-06-13-opaque-type-exports-and-layout-hiding-noref.md
[per-module-generated-c]: ../plans/features/2026-07-24-per-module-generated-c-mode-noref.md
[roadmap]: ../../docs/roadmap.md
[runtime-library]: closed/0002-runtime-static-library.md
[separate-compilation]: ../../docs/reference/separate-compilation.md
[siphash]: ../../compiler/shared/runtime/internal/dea_siphash.h
[symbol-linkage]: ../plans/features/closed/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md
