# L1 Initiative 0001 - Separate Compilation and External Linking

- Version: 2026-04-25
- Status: Active
- Kind: Initiative

## Summary

This initiative sequences two interlocking goals that together turn the L1 compiler from a whole-program,
single-compilation-unit producer into a toolchain capable of compiling and linking modules independently:

1. **Separate compilation and linking of L1 compilation units.**
2. **Link external static and dynamic libraries from L1 programs.**

The two goals share design surface around the C ABI and link-time identity, so this document captures the cross-cutting
decisions, the phasing, and the dependencies. Individual phases will spawn entries under `l1/work/plans/features/` and
`l1/work/plans/refactors/` as they become actionable.

This initiative executes under the L1 roadmap ([`l1/docs/roadmap.md`](../../docs/roadmap.md)).

## Related initiatives

- **Initiative 0002 - L1 Runtime Library** ([`0002-runtime-static-library.md`](0002-runtime-static-library.md)) is a
  soft prerequisite. It moves the runtime from header-only inclusion to a real static archive, which de-risks the link
  mechanics that this initiative depends on. Separate compilation can land independently, but the link model is cleaner
  once 0002 has settled archive linkage and the trace-variant story.
- **Initiative 0003 - C FFI** ([`0003-c-ffi.md`](0003-c-ffi.md)) is a downstream consumer. C FFI requires the LBI
  mangling defined here, the separate-compilation driver surface, and the external-library linking CLI before it can
  express `extern "C"` declarations and the closed FFI-safe boundary.

## Non-goals

- **Package-system overhaul.** This initiative adds explicit export manifests plus namespaced import forms such as
  `import math as m;` and `import abs, pi from math;`, but it does not introduce packages, a registry, a dependency
  resolver, or a new manifest format.
- **Package management.** No registry, lock files, dependency resolver, or `Dea.toml` schema. External libraries are
  reached through CLI flags; package management is a later concern.
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
- The L1 backend reference ([`l1/docs/reference/c-backend-design.md`](../../docs/reference/c-backend-design.md)) is the
  current source of truth for L1 generated C behavior.
- Top-level symbols inside a module are implicitly visible to importers: there is no explicit export manifest, no
  alias-backed import surface, and no per-symbol public/private split.
- Generated nominal names follow a `dea_{module}_{name}` style. Everything inside an `extern func` declaration is
  intentionally **not name-mangled**; this is the only FFI primitive in the language today.
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

With separate compilation the mangled name is the link-time identity. L1 adopts the length-prefixed LBI scheme:

- Format: `__dea<module_len><module_name><symbol_len><symbol_name>`.
- Normalization rule:
  - **Canonical source form:** the input to mangling is the module's dotted path (for example `std.math`), not its
    filesystem path. The compiler does not see `/` or platform path separators at the mangling stage.
  - **Path-component separator:** the source `.` between path components is mapped to `$` in the mangled `<module_name>`
    component (`std.math` -> `std$math`). This is the only character substitution; no other source character is
    rewritten on the way to the mangled form. The C backend targets a portability envelope where GCC, Clang, and MSVC
    all accept `$` as an identifier character by extension.
  - **Identifier characters:** Dea source identifiers match `[A-Za-z_][A-Za-z0-9_]*`, so `$` cannot appear inside an
    identifier itself. The substitution is therefore unambiguous: any `$` in a mangled `<module_name>` always represents
    a path-component separator.
  - **Stability:** this normalization is part of the LBI ABI and is stable across stages. Stage 2 must produce
    byte-identical mangled names for the same source surface.
- Example: `std.math::abs` becomes `__dea8std$math3abs`.
- The scheme is chosen now so later overloading and generics can extend it without breaking existing object names.
- Declarations inside an `extern "C"` block bypass mangling and are emitted with their declared C spelling.

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

### 0.4 Boundary between L1 types and C types

Moved to [Initiative 0003 - C FFI](0003-c-ffi.md). Anchors the closed FFI-safe type set, the `cstr` boundary type, and
the `string -> cstr` reinterpretation contract.

### 0.5 Where runtime symbols live

Moved to [Initiative 0002 - L1 Runtime Library](0002-runtime-static-library.md). Anchors the `extern func rt_foo`
resolution model after the runtime split, the trace-archive selection, and the public header layout.

## Phase 2 - Separate compilation of L1 CUs (Goal 1)

> Phase numbers are kept aligned with the original four-phase numbering in the spawned plans (Phase 2.a/2.b/2.c, Phase
> 3). Phase 1 (runtime split) lives in Initiative 0002; Phase 4 (full C FFI) lives in Initiative 0003.

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
   emit .l1m (interface)    emit .c (one CU per module)
                                    |
                                    v
                            cc -c -> .o
```

The driver gains three new modes; the existing whole-program `--build`/`--run` are preserved as convenience
orchestrators that fan out compile + link:

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
dependency graph and emits calls to each module's `_dea_init` entrypoint in dependency order before control reaches the
user `main`.

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

Module/interface and link-driver failures should first be mapped onto the existing shared diagnostic families where they
fit: `PAR-*` for interface-file syntax, `SIG-*` / `TYP-*` for semantic incompatibilities, `DRV-*` for source/module
discovery, and `L1C-*` for build/link-driver execution errors. New `MOD-*` or `LNK-*` families should be introduced only
if a phase plan proves that the existing family split would make user diagnostics or parity policy materially worse.

Concrete codes are registered in
[`docs/specs/compiler/diagnostic-code-catalog.md`](../../../docs/specs/compiler/diagnostic-code-catalog.md) in the same
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

Deferred. A per-module or per-package manifest file declaring required libraries is a natural fit once a
package-management story exists. Until then, CLI flags are sufficient.

### Documentation

Add a short user-facing page at [`l1/docs/user/linking.md`](../../docs/user/linking.md) covering the platform-specific
expectations (`.a`/`.so`/`.dylib`/`.lib`/`.dll`), the `tcc` caveats, and the recommended pattern for binding a C library
(FFI binding module + linker flags).

## Phase 4 - Full C FFI

Moved to [Initiative 0003 - C FFI](0003-c-ffi.md).

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
- [ ] Phase 0.1: parser support for `export` and `import ... as`.
- [ ] Phase 0.2: C emitter symbol mangling logic.
- [ ] Phase 0.3: `.l1m` interface emission and serialization.
- [ ] Phase 2.a: `-c` compile-only and `-I` interface-path support.
- [ ] Phase 2.b: driver topological sort plus per-module `_dea_init` emission.
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

- New
  [`l1/docs/specs/compiler/module-visibility-and-imports.md`](../../docs/specs/compiler/module-visibility-and-imports.md)
  capturing export manifests, aliasing, and selective import.
- New [`l1/docs/specs/compiler/module-interface-format.md`](../../docs/specs/compiler/module-interface-format.md) (Phase
  0.3, expanded in Phase 2).
- New [`l1/docs/specs/compiler/abi.md`](../../docs/specs/compiler/abi.md) (Phase 0.2, finalized in Phase 2).
- New [`l1/docs/reference/separate-compilation.md`](../../docs/reference/separate-compilation.md) (Phase 2).
- Substantial revision of the L1 backend-design reference (Phase 2 invalidates the "single generated C compilation unit"
  assertion).
- New [`l1/docs/user/linking.md`](../../docs/user/linking.md) (Phase 3).

### Diagnostic-code registration

The shared diagnostic catalog is concrete-code based; it does not currently carry placeholder reservations. This
initiative therefore does not reserve fake `MOD-####` or `LNK-####` rows up front.

Each phase plan must classify new diagnostics against the existing families first:

- `PAR-*` for interface-file syntax.
- `SIG-*` / `TYP-*` for interface and ABI type/signature failures.
- `DRV-*` for module/interface discovery.
- `L1C-*` for build/link-driver execution failures.

New `MOD-*` or `LNK-*` families remain available if a concrete implementation phase proves a family boundary is needed.
In that case, register concrete codes in
[`docs/specs/compiler/diagnostic-code-catalog.md`](../../../docs/specs/compiler/diagnostic-code-catalog.md) in the same
change that implements their diagnostics.

### L0 isolation

L0 is unaffected by this initiative. All changes land in `l1/`; L0's header-only runtime and single-CU model stay as-is
per the `1.0.0` scope boundary.

## Open questions

These remain open after the decisions above and should be resolved in the phase plans:

1. **Fingerprint hash algorithm.** SipHash-1-3 (already in the runtime), BLAKE3 (cryptographic, larger dependency), or a
   deterministic content hash over the canonicalized interface text?
2. **Object metadata format.** Use a custom section everywhere possible, a generated const symbol everywhere for
   portability, or a platform-specific hybrid for embedded fingerprints in provider `.o` files?
3. **Diagnostic family split.** Keep module/link diagnostics in existing families, or introduce concrete `MOD-*` or
   `LNK-*` families once implementation pressure proves they are clearer?
4. **Manifest format for external libraries.** Defer entirely until package management exists, or accept a minimal
   `[link]` section in a per-module sidecar file early?

Each open question gets a short design note under `l1/docs/specs/compiler/` once decided. FFI-specific open questions
live in [Initiative 0003](0003-c-ffi.md); runtime-delivery open questions live in
[Initiative 0002](0002-runtime-static-library.md).

## Spawned plans

(Filled in as implementation tranches become actionable. Cross-link from here to the spawned plans, and from each plan
back to this initiative.)

Phase 0 decisions are now recorded directly in this initiative. They do not need separate spawned plans unless a later
implementation tranche proves that one decision area needs additional design work.

- Phase 0.1: parser/analyzer support for export manifests and aliased/selective imports under
  [`l1/work/plans/features/2026-04-24-export-manifests-and-aliased-imports-noref.md`](../plans/features/2026-04-24-export-manifests-and-aliased-imports-noref.md)
- Phase 0.2: LBI symbol mangling plus exported-vs-internal linkage emission under
  [`l1/work/plans/features/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md`](../plans/features/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md)
- Phase 0.3: `.l1m` interface emission, canonicalization, and parsing contract under
  [`l1/work/plans/features/2026-04-24-module-interface-emission-noref.md`](../plans/features/2026-04-24-module-interface-emission-noref.md)
- Phase 2.a: compile-only and interface-path driver surface under
  [`l1/work/plans/features/2026-04-24-separate-compilation-driver-surface-noref.md`](../plans/features/2026-04-24-separate-compilation-driver-surface-noref.md)
- Phase 2.b: multi-CU init ordering and executable wrapper behavior under
  [`l1/work/plans/features/2026-04-24-multi-cu-initialization-and-link-order-noref.md`](../plans/features/2026-04-24-multi-cu-initialization-and-link-order-noref.md)
- Phase 2.c: fingerprint hashing, object metadata embedding, and link-time verification under
  [`l1/work/plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md`](../plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md)
- Phase 3: external-library linking CLI under
  [`l1/work/plans/features/2026-04-24-external-library-linking-cli-noref.md`](../plans/features/2026-04-24-external-library-linking-cli-noref.md)

## Glossary

- **LBI**: Dea L1 Binary Interface.
- **CU**: compilation unit. In this initiative, a single L1 module compiled to one `.o`.
- **Interface file** (`.l1m`): textual serialized public surface of a module, sufficient for importers to type-check
  without reparsing the implementation source.
- **Fingerprint**: deterministic content hash over a module's canonicalized public surface, written to `.l1m` and
  embedded in the provider object metadata.
- **Link set**: the set of `.o` files plus libraries presented to the linker to produce one executable or library.
