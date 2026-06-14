# Feature Plan

## Add textual `.l1m` module interface emission

- Date: 2026-06-11
- Status: Draft
- Title: Add textual `.l1m` module interface emission
- Kind: Feature
- Severity: High
- Stage: L1
- Subsystem: Analysis / interface serialization / parser / docs
- Modules:
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/parser.l0`
  - `l1/compiler/stage1_l0/src/parser/decl.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/0001-separate-compilation-and-linking.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: None

## Summary

Separate compilation in Initiative `0001` depends on a textual `.l1m` file that captures the public surface of one
module in deterministic, L1-source-like form. This plan adds the interface artifact itself: what gets serialized, how it
is ordered, and how Stage 1 reads it back into a `ModuleInterface`-style representation.

Fingerprint hashing and provider-object verification are tracked separately. This plan owns the interface file shape,
canonical ordering rules, explicit/developer-facing interface emission, and parser round-trip contract. It does not make
`.l1m` files normal inputs to ordinary `--build` or `--run`; those user-facing driver flows continue to resolve imports
from source modules until later driver tranches wire interface search paths, compile-only output, and build/run fan-out.

The direct-import replay path is deliberately treated as the next tranche, not as a requirement for closing this plan.
This plan may define the in-memory structures that make replay possible, but it is complete when the artifact can be
projected, emitted, parsed, and tested deterministically.

## Current State

1. Stage 1 type-checks imports by reparsing implementation source modules, not an interface artifact.
2. There is no serializer for the public semantic surface of a module.
3. There is no constrained parser mode for `module interface ...;` files.
4. The backend and driver do not know where emitted interface files live or how they are named.
5. Ordinary `--build` and `--run` still use source-based monolithic import analysis.
6. Dependency sections in an interface file need a clear contract: this tranche may define and round-trip syntax, but
   semantic population of implementation-tier link dependencies belongs to the driver/fan-out work that consumes them.

## Defaults Chosen

1. `.l1m` is textual and human-readable, not a binary arena dump.
2. The file begins with `module interface <name>;`.
3. The file includes a `fingerprint "<hash>";` slot, but the hash algorithm and end-to-end verification policy are owned
   by the fingerprint plan.
4. Exported `struct` and `enum` definitions are emitted structurally, not opaquely, so importers can reconstruct layout.
5. Exported `func` declarations end with `;` and never carry bodies.
6. Exported `const` declarations inline literal values; exported `let` declarations carry types only.
7. Emission order is canonicalized and independent of source declaration order.
8. The export manifest itself is not emitted as a literal `export ...;` line. The `.l1m` contains only the exported
   declarations, so the manifest is reflected indirectly through which declarations appear. Modules with the same
   effective public surface produce byte-identical `.l1m` content regardless of whether the source used `export *;`, an
   explicit allowlist, or the implicit default.

## Goal

1. Serialize the public module surface into deterministic `.l1m` text.
2. Parse `.l1m` files back into interface data structures suitable for a later semantic replay tranche.
3. Define one naming and path convention for explicitly emitted interface artifacts.
4. Lay the foundation for later fingerprint and link-time verification work.

## Implementation Phases

### Phase 1: Public-surface projection

Add an analysis-to-interface projection layer that extracts only the exported surface needed by importers:

- exported type declarations,
- exported function signatures,
- exported `const` literals,
- exported top-level `let` types,
- the module fingerprint placeholder/value field.

This layer should avoid leaking backend-only details so the `.l1m` format can remain a language-facing artifact.

### Phase 2: Deterministic textual emission

Implement a stable writer for `.l1m` files. The writer should sort by a defined canonical key and emit normalized
whitespace so repeated runs over the same semantic surface produce byte-identical output.

### Phase 3: Interface parsing

Teach Stage 1 to parse `.l1m` in a constrained mode that accepts only interface-file constructs and reconstructs the
serialized public surface. Semantic replay into imported-module signature/type-resolution tables belongs to the
separate-compilation driver-surface plan.

### Phase 4: Explicit emission workflow and tests

Integrate an explicit/internal interface-emission workflow and round-tripping into the driver/library surface, without
making interface discovery part of ordinary import resolution. Add regression tests for:

- deterministic emission,
- structural type replay,
- `const` literal replay,
- interface dependency-section round trips, if `require` or `link` syntax lands in this tranche,
- malformed or incomplete interface files.

Any `.l1m` files emitted in this phase are produced only through explicit or internal interface-emission workflows. They
are not automatic side effects of ordinary monolithic `--build` or `--run`, and ordinary import resolution remains
source-based.

## Diagnostics

1. This plan is expected to need diagnostics for malformed or unsupported `.l1m` syntax and interface-file load errors.
2. Provisionally reserve `PAR-0560` to `PAR-0579` for `.l1m` syntax and constrained-parser diagnostics.
3. Provisionally reserve `DRV-0050` to `DRV-0069` for interface-file discovery, read, and format/load errors.
4. Re-check the live catalog at implementation time before assigning final numbers. If any proposed slot has been used
   in the meantime, choose a different free block then.

## Non-Goals

1. Final fingerprint hash computation.
2. Link-time verification against provider objects.
3. External-library linking CLI.
4. Runtime static-library packaging.
5. Switching ordinary import resolution from source modules to `.l1m` interfaces.
6. Exposing `-c` / `--compile` or `-I` / `--interface-path` as stable user-facing separate-compilation surface.
7. Writing `.l1m` as a side effect of object compilation.
8. Computing implementation-tier `link` dependency entries from function bodies or using them to drive provider-object
   linking.

## Verification Criteria

1. Stage 1 can emit deterministic `.l1m` files for exported module surfaces.
2. Exported structs/enums, function signatures, `const` values, and `let` types round-trip correctly through `.l1m`.
3. Malformed interface files are rejected with dedicated parser/driver diagnostics rather than generic failures.
4. The roadmap and initiative links point to this plan as the `.l1m` serialization tranche.
5. Any newly assigned diagnostic codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md`.
6. Ordinary `--build` and `--run` behavior remains source-based and does not require pre-existing `.l1m` files.
7. No stale `.l1m` artifact is produced by a failing object compilation path, because object compilation is outside this
   tranche.
8. If dependency-section syntax is included, tests distinguish parser/emitter round-trip support from later semantic
   population of `link` entries.
