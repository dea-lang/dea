# L1 Initiative 0001 - Separate Compilation and External Linking

- Version: 2026-06-12
- Status: Active
- Kind: Initiative
- Open plans:
  - `l1/work/plans/features/2026-04-24-separate-compilation-driver-surface-noref.md`
  - `l1/work/plans/features/2026-04-24-multi-cu-initialization-and-link-order-noref.md`
  - `l1/work/plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md`
  - `l1/work/plans/features/2026-04-24-external-library-linking-cli-noref.md`
  - `l1/work/plans/features/2026-06-13-opaque-type-exports-and-layout-hiding-noref.md`
- Closed plans:
  - `l1/work/plans/features/closed/2026-04-24-export-manifests-and-aliased-imports-noref.md`
  - `l1/work/plans/features/closed/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md`
  - `l1/work/plans/features/closed/2026-04-24-module-interface-emission-noref.md`

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
  `extern "C"` declarations and the closed FFI-safe boundary.

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

- The L1 compiler emits **one generated C99 compilation unit per program**. The whole import closure is concatenated
  into a single `.c` and compiled in one `cc` invocation.
- The L1 backend reference ([`l1/docs/reference/c-backend-design.md`][backend-design]) is the current source of truth
  for L1 generated C behavior.
- Modules support explicit export manifests plus alias and selective import forms. Exported top-level declarations keep
  external C linkage; non-exported top-level functions and storage use `static` where the current single-CU backend can
  do so without changing semantics.
- Generated L1-defined source symbols use LBI `M...S...` names, and compiler-generated module lifecycle symbols use LBI
  `M...I...` names. Everything inside a legacy `extern func` declaration is intentionally **not name-mangled**; this is
  the only FFI primitive in the language today.
- Imports are type-checked by reparsing implementation source files, not from a serialized interface artifact. There is
  no `.l1m` format yet, no fingerprint, and no link-time consistency check beyond what the platform linker surfaces.
- The current driver CLI uses `-I` and `-L` as runtime-discovery short aliases for `--runtime-include` and
  `--runtime-lib`. There is no separate-compilation entry point (`-c`) and no interface-search-path option.
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

- Source symbols use `__deaM<seg_len><seg>...S<sym_len><sym>`.
- Compiler-generated module lifecycle symbols use `__deaM<seg_len><seg>...I<life_len><life>`.
- **Canonical source form:** the input to mangling is the module's dotted path (for example `std.integer`), not its
  filesystem path. The compiler does not see `/` or platform path separators at the mangling stage.
- **Module path encoding:** each dotted module segment becomes one length-prefixed component in the `M` section. No
  character substitution or `$`-in-identifier compiler extension is required.
- **Identifier characters:** Dea source identifiers match `[A-Za-z_][A-Za-z0-9_]*`, so the boundary between a decimal
  length and the following component is unambiguous.
- **Stability:** this normalization is part of the LBI ABI and is stable across stages. Stage 2 must produce
  byte-identical mangled names for the same source surface.
- Example: `std.integer::abs` becomes `__deaM3std7integerS3abs`.
- Example: module lifecycle `std.integer::init` becomes `__deaM3std7integerI4init`.
- The scheme is chosen now so later overloading, generics, and additional module lifecycle entries can extend it without
  breaking existing object names.
- Declarations inside an `extern "C"` block bypass mangling and are emitted with their declared C spelling.

Phase 0.2 is completed by
[`l1/work/plans/features/closed/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md`][symbol-linkage].

### 0.3 Module artifact format (`.l1m`)

Separate compilation uses a textual `.l1m` interface file. The format stays human-readable and L1-source-like so the
bootstrap remains inspectable and the existing parser can be reused with a constrained accept set.

Each `.l1m` records the public surface of one module in canonical form:

- `module interface <name>;` as the file header.
- `fingerprint "<hash>";` immediately after the header.
- `struct` and `enum` definitions reproduced 1:1 from the implementation so importers can recompute size and offset
  information.
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

Phase 2.a is the first phase where `.l1m` files become normal driver inputs. That later phase is intentionally split
into smaller tranches so the interface artifact, interface-backed analysis, CLI surface, compile-only artifact writer,
and build/run fan-out do not land as one tangled change. In particular:

1. `.l1m` artifact emission and parser round-trip can land without changing ordinary source-based `--build` or `--run`.
2. Direct `.l1m` import replay can land as semantic/codegen plumbing before the user-facing driver exposes full separate
   compilation.
3. `-c` and `-I` become stable user-facing surface only when compile-only output is one implementation module plus
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
- **Keying discipline:** a fixed, compile-time-constant 16-byte fingerprint key, distinct from the runtime's randomized
  hash-flooding key. The constant is part of the LBI ABI and is stable across stages. The exact key bytes are an
  implementation detail of the spawned fingerprint plan and are recorded in [`l1/docs/specs/compiler/abi.md`][abi] once
  chosen.
- **Digest size and encoding:** 64-bit digest. Encoded as 16 lowercase hex digits in `.l1m` (`fingerprint "<hash>";`)
  and embedded as 8 raw bytes in object metadata.
- **Object embedding:** every per-module object file emits two portable C99 `const uint8_t` arrays with mangled names
  (one for the producer's exported fingerprint, one for the consumer's
  `(imported module, expected dependency fingerprint)` records). Both arrays are referenced from the module lifecycle
  `I4init` entry point so the platform linker's dead-strip pass cannot remove them. The driver discovers the records via
  symbol-table lookup, which is the same mechanism every supported object format already exposes (ELF, Mach-O, PE/COFF)
  and is also `tcc`-compatible.

The threat model is build-time staleness and corruption, not adversaries; cryptographic strength (BLAKE3, SHA-256) is
not required and would only add bootstrap-vendoring cost. Custom object sections were rejected because they require
per-format emitter and reader paths plus quirky compiler attributes that `tcc` does not fully support.

Sub-choices that remain implementation details, owned by
[`l1/work/plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md`][interface-fingerprints]: the
exact 16-byte key constant, the on-disk record layout (small magic + version prefix + flat little-endian fields is the
expected default), the exact symbol-name mangling, and the canonicalization rules over the public surface.

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

The implementation is split across explicit tranches:

1. **Interface artifact tranche:** project exports into `.l1m`, parse the file back, and test deterministic round-trips.
   This may expose an explicit `--emit-interface` developer mode, but it does not make `.l1m` a normal import input for
   build/run.
2. **Direct interface import tranche:** allow the driver/analyzer/backend to consume a direct imported `.l1m` for
   signatures, public layouts, and extern declarations. This proves interface-backed compilation of a consumer module,
   but still does not claim full build/run orchestration.
3. **Compile-only driver tranche:** expose `-c`/`--compile` and `-I` only once `-c` emits exactly one module's generated
   C/object plus its `.l1m`, consumes imports from interfaces, and does not leave a fresh `.l1m` behind when object
   compilation fails.
4. **Build/run fan-out tranche:** preserve `--build` and `--run` as convenience commands by computing the module graph,
   compiling modules individually as needed, and linking all required provider objects.

The driver ultimately gains three new modes or mode families; the existing whole-program `--build`/`--run` are preserved
as convenience orchestrators that fan out compile + link:

- `-c <module>` compiles one module without linking. It emits the module's generated C, object file, and `.l1m`
  artifact.
- `-I <dir>` adds an interface-search path used to resolve imported `.l1m` files during `-c`, `--build`, and `--run`.
- `--link <module> [<module> ...] -o <out>` drives the C linker, writes the executable. At least one module must define
  `main`.

`--build` and `--run` compute the import closure, fan out per-module compile, then link. This preserves the current
developer experience and keeps the bootstrap simple.

Name resolution also moves away from the current flat import surface. `import math as m;` introduces qualified access
through `m::abs(...)`, while `import abs, pi from math;` selectively imports named exports from the provider module. The
consumer always binds against the provider's exported surface as described by its `.l1m`; local aliases do not affect
the provider's link identity.

### 2b. Backend changes

`be_emit_function_definitions` walks every unit in the closure today. After the split it walks only the current module;
everything imported is **declared** but not defined. Per-module C output contains:

- forward declarations for every type reachable from the module's signatures (own + imported);
- `extern` declarations for imported functions and top-level lets, using their provider-owned mangled names;
- full definitions for the module's own types, lets, and functions, with exported symbols kept global and non-exported
  symbols emitted as `static`.

Struct layouts must be identical across CUs that see them. The simplest path: every importer re-emits the imported
struct as a C declaration in its own CU, identically mangled and field-ordered. The interface file therefore carries the
full structural layout, not just an opaque tag.

A new "main wrapper" pseudo-module produces the `main(int argc, char **argv)` shim and is compiled separately when an
executable is requested. It depends only on the entry module's interface. The driver topologically sorts the module
dependency graph and emits calls to each module's `I4init` lifecycle entry point in dependency order before control
reaches the user `main`.

### 2c. Interface-file consistency and verification contract

Each `.l1m` carries a **fingerprint** computed from the canonicalized public surface (function signatures, exported
struct layouts, exported enum tags and payload types, exported `const` literals, exported top-level `let` types, and the
export manifest itself). Verification is explicitly tiered:

1. **Producer stage:** compiling `foo.l1` computes the canonicalized public surface, hashes it, and writes the result to
   `foo.l1m` as `fingerprint "<hash>";`.
2. **Consumer stage:** an importer that reads `foo.l1m` re-hashes the declarations it parsed. If the recomputed value
   differs from the declared fingerprint, the interface file is rejected as corrupted or non-canonical.
3. **Linker stage:** the provider's compiled object embeds its own exported fingerprint in object metadata. The driver
   verifies that every consumer's recorded dependency fingerprint matches the provider object's embedded fingerprint
   before invoking the platform linker.

The fingerprint algorithm and the object-embedding strategy are anchored in §0.6. In short: SipHash-1-3 with a fixed
key, 64-bit digest, embedded in each `.o` as portable C99 `const uint8_t` arrays with mangled names, anchored against
dead-strip from the module's `I4init` lifecycle entry point, and discovered by the driver via symbol-table lookup.

This replaces any per-symbol ABI hash scheme. The diagnostic goal is a clean stale-interface or stale-object failure
instead of undefined-symbol noise from the platform linker.

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

- `-l<name>`: link library.
- `-L<dir>`: library search path.
- `-I<dir>`: interface search path for `.l1m` discovery during separate compilation.
- `--rpath=<dir>`: for dynamic libraries.
- `--link-arg=<flag>`: escape hatch for raw linker flags.

`-l`, `-L`, `--rpath`, and `--link-arg` are accepted by `--link`, `--build`, and `--run` and are forwarded as-is to the
host linker. `-I` is consumed by the compiler driver during interface discovery for compile-involving flows. L1 has no
opinion on static vs. dynamic linkage.

The current runtime-specific short aliases therefore need to retire as Phase 2 lands: `-I` is committed to interface
search, and `-L` returns to its normal library-search meaning. Manual `extern "C"` binding files remain the supported
FFI workflow, so the core compiler does not need a raw C-header include-path flag.

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

Moved to [Initiative 0003 - C FFI][c-ffi].

## Sequencing and dependencies

```
Initiative 0002 (runtime -> static lib) ---+
                                           | (soft prereq: link mechanics learned here)
                                           v
                                    Phase 0 (decisions)
                                           |
                                           v
                                    Phase 2 (separate compilation)
                                           |
                                           +-----> Phase 3 (external libs)
                                                          |
                                                          v
                                                   Initiative 0003 (full C FFI)
```

- Initiative 0002 (runtime split) is independently shippable and de-risks the link mechanics this initiative depends on;
  it is a soft prerequisite, not a hard one.
- Phase 2 is the longest piece and gates Phase 3 plus Initiative 0003.
- Phase 3 falls out almost for free once Phase 2 lands.
- Initiative 0003 (full C FFI) is the most language-design-heavy downstream consumer and is best done after the
  link/compile mechanics no longer move underneath it.

Recorded near-term tranche checkpoints:

- [x] Finalize mangling and visibility defaults.
- [x] Finalize `.l1m` format and fingerprint verification contract.
- [x] Phase 0.1: parser support for `export` and `import ... as`.
- [x] Phase 0.2: C emitter symbol mangling logic.
- [x] Phase 0.3: `.l1m` interface emission and serialization.
- [ ] Phase 2.a.1: direct `.l1m` import replay and codegen plumbing.
- [ ] Phase 2.a.2: `-c` compile-only and `-I` interface-path support.
- [ ] Phase 2.b: driver topological sort plus per-module `I4init` emission.
- [ ] Phase 2.c: fingerprint hashing plus provider metadata embedding in `.o`.

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

The four originally-open questions are closed. Each decision is anchored elsewhere in this initiative; this section
summarizes the chosen answer and points at the owning section.

1. **Fingerprint hash algorithm:** SipHash-1-3 from the shared runtime, keyed with a fixed compile-time-constant 16-byte
   fingerprint key, 64-bit digest, encoded as 16 lowercase hex digits in `.l1m` and 8 raw bytes in object metadata.
   Cryptographic strength is not required for the build-time staleness threat model. Anchored in §0.6; sub-choices
   (exact key constant, encoding details, canonicalization rules) are owned by
   [`l1/work/plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md`][interface-fingerprints].
2. **Object metadata format:** portable C99 `const uint8_t` arrays with mangled names, anchored against linker
   dead-strip from each module's `I4init` lifecycle entry point. Driver-side discovery uses symbol-table lookup, which
   works uniformly across ELF, Mach-O, and PE/COFF and stays compatible with `tcc`. Custom object sections were rejected
   because they force per-format emitter and reader paths plus quirky compiler attributes. Anchored in §0.6 and §2c;
   record layout and naming details are owned by the same spawned phase plan.
3. **Diagnostic family split:** keep the existing phase-based families (`PAR-*`, `RES-*`, `SIG-*`, `TYP-*`, `DRV-*`,
   `L1C-*`). New `MOD-*` or `LNK-*` families are introduced only if a concrete phase plan demonstrates the existing
   split materially worsens user diagnostics or Stage 1 / Stage 2 parity policy. The provisional reservations recorded
   in the spawned fingerprint plan (`SIG-0240` to `SIG-0259`, `L1C-2050` to `L1C-2069`) stand and must be re-checked
   against the live catalog at implementation time. Anchored in §2e and §Diagnostic-code registration.
4. **External-library manifest format:** deferred indefinitely unless and until Dea decides to adopt package management.
   Phase 3 ships with CLI flags only (`-l`, `-L`, `--rpath`, `--link-arg`, plus `-I` for interface search). No
   per-module `[link]` sidecar, no `Dea.toml`, no other in-tree manifest format. Initiative 0003 may revisit this if FFI
   bindings prove a binding-module-local hint mechanism is necessary, in which case extending CLI ergonomics is
   preferred over a new file format. Anchored in §Phase 3 / Manifest support.

FFI-specific open questions live in [Initiative 0003][c-ffi]; runtime-delivery open questions live in
[Initiative 0002][runtime-library].

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
- Phase 2.a.1 / 2.a.2: direct interface imports, compile-only, and interface-path driver surface under
  [`l1/work/plans/features/2026-04-24-separate-compilation-driver-surface-noref.md`][compile-driver]
- Phase 2.b: multi-CU init ordering and executable wrapper behavior under
  [`l1/work/plans/features/2026-04-24-multi-cu-initialization-and-link-order-noref.md`][module-init]
- Phase 2.c: fingerprint hashing, object metadata embedding, and link-time verification under
  [`l1/work/plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md`][interface-fingerprints]
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

[abi]: ../../docs/specs/compiler/abi.md
[backend-design]: ../../docs/reference/c-backend-design.md
[c-ffi]: 0003-c-ffi.md
[compile-driver]: ../plans/features/2026-04-24-separate-compilation-driver-surface-noref.md
[diagnostic-catalog]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[export-imports]: ../plans/features/closed/2026-04-24-export-manifests-and-aliased-imports-noref.md
[interface-emission]: ../plans/features/closed/2026-04-24-module-interface-emission-noref.md
[interface-fingerprints]: ../plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md
[library-linking]: ../plans/features/2026-04-24-external-library-linking-cli-noref.md
[linking]: ../../docs/user/linking.md
[module-init]: ../plans/features/2026-04-24-multi-cu-initialization-and-link-order-noref.md
[module-interface]: ../../docs/specs/compiler/module-interface-format.md
[module-visibility]: ../../docs/specs/compiler/module-visibility-and-imports.md
[roadmap]: ../../docs/roadmap.md
[runtime-library]: closed/0002-runtime-static-library.md
[separate-compilation]: ../../docs/reference/separate-compilation.md
[siphash]: ../../compiler/shared/runtime/internal/dea_siphash.h
[symbol-linkage]: ../plans/features/closed/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md
