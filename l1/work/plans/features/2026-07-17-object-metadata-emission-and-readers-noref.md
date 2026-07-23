# Feature Plan

## Emit and read portable Dea object metadata

- Date: 2026-07-17
- Status: Draft
- Title: Emit and read portable Dea object metadata
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative]
- Subsystem: Object ABI / backend / object readers / link verification boundary
- Modules:
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/object_metadata.l0`
  - `l1/compiler/stage1_l0/src/object_reader.l0`
  - `l1/compiler/stage1_l0/src/object_reader_elf.l0`
  - `l1/compiler/stage1_l0/src/object_reader_macho.l0`
  - `l1/compiler/stage1_l0/src/object_reader_pecoff.l0`
  - `l1/docs/specs/compiler/abi.md`
  - `l1/docs/reference/c-backend-design.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/object_metadata_test.l0`
  - `l1/compiler/stage1_l0/tests/object_reader_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/fixtures/object_metadata`
- Related:
  - [`l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md`][module-graph]
  - [`l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md`][fingerprints]
  - [`l1/work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md`][lifecycle]
  - [`l1/work/plans/features/2026-07-17-link-set-driver-and-wrapper-noref.md`][link-set]
  - [`l1/work/plans/features/closed/2026-04-24-interface-fingerprints-and-object-metadata-noref.md`][superseded-metadata]
  - [`l1/docs/specs/compiler/module-interface-format.md`][interface-format]
  - [`docs/specs/compiler/diagnostic-code-catalog.md`][diagnostic-catalog]
- Repro: `make -C l1 test-stage1 TESTS="backend_test object_metadata_test object_reader_test build_driver_test"`

## Summary

Embed enough self-describing metadata in every separately compiled Dea object to validate a standalone link without
reopening `.l1m` files. Add bounded, in-repository readers for ELF, Mach-O, and PE/COFF relocatable objects and expose a
strict three-way Dea metadata classification:

1. `ValidDeaMetadata`
2. `NoDeaMetadata`
3. `MalformedDeaMetadata`

The classification is the safety boundary used later by `--foreign-object`. Absence of Dea metadata is accepted only for
an explicitly foreign relocatable object. Any recognizable Dea ABI symbol with absent, incomplete, unsupported, or
inconsistent metadata is malformed and cannot be reclassified as foreign.

## Dependencies and Ownership

1. The [module graph plan][module-graph] supplies canonical module identity and the ordered direct provider edges,
   including imports retained only for side effects.
2. The [fingerprint plan][fingerprints] supplies the producer whole-module fingerprint and the expected fingerprint for
   every direct provider edge. This plan does not compute hashes.
3. The completed [lifecycle plan][lifecycle] supplies always-present external `I4init` and `I4fini` symbols plus
   optional `I5entry`. This plan anchors metadata through `I4init` and records whether `I5entry` is present.
4. This plan owns the wire format, metadata emission, object-container readers, and classification API. It does not
   invoke the host linker or decide whether a CLI argument is a Dea or foreign object.
5. The [link-set plan][link-set] consumes the classification, enforces positional-versus-foreign input rules, verifies
   the complete module graph, rejects foreign C `main`, and reports link-mode diagnostics.

## Current State

1. Generated object files have no self-describing module identity, interface fingerprint, ordered dependency list, or
   entry-candidate flag.
2. A standalone driver invocation cannot distinguish a matching provider object from a stale object without relying on
   platform linker failures.
3. The compiler has no object-format parser and would otherwise need to shell out to tools such as `nm` or `objdump`.
4. Treating every metadata-free object as a valid link input would allow old, stripped, or malformed Dea objects to
   bypass fingerprint and lifecycle checks.

## Metadata Symbols and Wire Format

Every Dea module object defines two external C99 `const uint8_t` arrays. Their canonical LBI names use the module's
normal `M` section and these reserved compiler-generated `I` terminals:

1. `I8metadata`: the module identity record.
2. `I7imports`: the ordered direct-import record.

Both arrays begin with this 16-byte common header:

| Offset | Field          | Encoding                                                |
| ------ | -------------- | ------------------------------------------------------- |
| 0      | Magic          | Eight ASCII bytes `DEAL1OBJ`                            |
| 8      | Format version | Little-endian `u16`; initial version is `1`             |
| 10     | Record kind    | Little-endian `u16`; `1` is identity and `2` is imports |
| 12     | Payload length | Little-endian `u32`, excluding the common header        |

The `I8metadata` payload contains, in order:

1. a little-endian `u32` flags field, where bit 0 means `HAS_ENTRY` and all other bits must be zero in version 1;
2. a little-endian `u32` byte length for the canonical dotted module name;
3. the producer's 64-bit whole-module fingerprint as eight little-endian bytes;
4. the non-NUL-terminated ASCII module-name bytes.

The `I7imports` payload starts with a little-endian `u32` record count. Each record then contains a little-endian `u32`
module-name length, the expected provider fingerprint as eight little-endian bytes, and the non-NUL-terminated canonical
dotted module-name bytes.

Metadata format version 1 is fixed to SipHash-1-3. Its eight-byte fields encode the raw digest portion of a verified
`sip13:<16 lowercase hexadecimal digits>` interface fingerprint; the textual algorithm tag is not embedded. Supporting
another fingerprint algorithm requires a new metadata format version rather than interpreting the same version 1 bytes
under a different default.

The import array contains every unique direct provider module exactly once, in first source-import order. It includes a
side-effect-only import even when no imported symbol appears in the consumer's public or private expressions. Duplicate
provider records, non-canonical names, unknown flag bits, trailing payload bytes, and any count or length inconsistent
with the containing array are malformed. There are no per-symbol compatibility hashes in object metadata.

Array symbol names, record kinds, flag bits, byte order, and version 1 layout are LBI ABI. The implementation records
them in the [ABI specification][abi]; it must not silently change this layout while adding a reader for another host
format.

## Emission and Dead-Strip Anchor

1. Per-module C emission materializes both byte arrays from the analyzed module graph and fingerprint results.
2. Arrays have external linkage so an object reader can locate them in the symbol table before linking.
3. `I4init` performs a volatile byte read from each non-empty array. This creates an object-level reference from the
   externally called lifecycle function without requiring custom sections or non-C99 attributes and prevents linker
   dead-strip from discarding the records.
4. Metadata anchoring does not change initialization order, call another module, or make initialization conditional.
5. `HAS_ENTRY` must match actual presence of the same module's external `I5entry`. Every valid object must also define
   that module's external `I4init` and `I4fini`.

## Object Inspection Interface

Add one format-neutral inspection entry point for relocatable object paths. A successful container read returns basic
format information, whether the object defines a process-level C `main`, and exactly one metadata classification:

```text
ValidDeaMetadata(module, fingerprint, ordered_imports, has_entry)
NoDeaMetadata
MalformedDeaMetadata(reason)
```

File-not-found, read failure, unsupported container kind, and corrupt object-container structure are object-read errors
outside the metadata tri-state. They must never be collapsed to `NoDeaMetadata`.

Classification rules are:

1. `ValidDeaMetadata` requires exactly one matching identity/imports pair, supported version and flags, canonical and
   mutually consistent symbol/payload module identity, valid ordered imports, matching lifecycle symbols, and entry-flag
   agreement.
2. `NoDeaMetadata` requires a valid supported relocatable object with neither metadata symbol nor any recognizable
   externally defined Dea LBI symbol using the reserved `__dea` prefix.
3. `MalformedDeaMetadata` results when any Dea metadata or LBI marker is present but the complete version 1 contract is
   not valid. Examples include one missing companion array, duplicate records, unsupported versions, truncated data,
   invalid names, old Dea objects with LBI definitions but no metadata, or lifecycle/entry inconsistencies.
4. The classifier never accepts a caller hint that changes one result into another. In particular, a valid or malformed
   Dea object cannot become `NoDeaMetadata` because it was passed through a future foreign-object option.

The format-neutral result also exposes an exact defined-symbol query used by the link-set plan to reject a foreign
object that defines C `main`. Foreign objects have no module identity, dependency edges, fingerprint obligation,
lifecycle participation, or entry eligibility.

## Bounded Format Readers

Implement object readers in L1 rather than invoking external inspection commands:

1. The ELF reader handles relocatable ELF32 and ELF64 section tables, symbol tables, and associated string tables for
   supported byte orders.
2. The Mach-O reader handles 32-bit and 64-bit relocatable objects, load commands, sections, `LC_SYMTAB`, and its string
   table for supported byte orders.
3. The PE/COFF reader handles standard COFF relocatable objects and PE/COFF section, symbol, auxiliary-symbol, and
   string table encodings needed to locate the arrays. Unsupported object variants fail explicitly.
4. Each reader normalizes only the C symbol decoration defined by its object ABI, such as a platform-added leading
   underscore, before matching canonical LBI names. It does not use fuzzy suffix matching.
5. Symbol locations are resolved through their containing section and checked against file and section bounds. Symbol
   size, when present, is an additional bound; the wire payload length supplies the exact record length where the object
   format omits symbol sizes.
6. All offset, count, alignment, and length arithmetic is overflow-checked before slicing or allocating. Counts must fit
   the remaining bounded table or payload before storage is allocated. Overlapping, out-of-range, or unterminated string
   table references are errors.
7. Readers inspect section/symbol/string data only. They do not apply relocations, load executable code, infer link
   architecture compatibility, parse archives or shared libraries, or run host tools.

Archives and shared libraries remain library/linker-argument inputs rather than foreign relocatable objects. Unsupported
architecture or ABI combinations between otherwise well-formed inputs remain host-link failures in the later link-set
plan.

## Implementation Phases

### Phase 1: Encode and decode the metadata records

Add format-independent version 1 builders and bounded decoders. Lock golden byte fixtures for identity and
ordered-import records, including empty imports and entry/no-entry identities.

### Phase 2: Emit and anchor module metadata

Emit the two arrays in per-module C, add their volatile references to `I4init`, and verify their module, fingerprint,
ordered-edge, lifecycle, and entry invariants before returning generated C.

### Phase 3: Read supported relocatable objects

Implement the three format adapters behind one symbol/section inspection facade. Use programmatically constructed
minimal fixtures for all formats and a native host-compiler smoke fixture for the active platform.

### Phase 4: Classify and expose the link-driver boundary

Implement the exact tri-state rules, expose defined-symbol lookup for foreign `main` detection, document the ABI, and
hand the typed inspection result to the later link-set plan without changing current build/run behavior.

## Diagnostics

1. Provisionally retain `L1C-2050` through `L1C-2069` for object-read, malformed metadata, unsupported metadata version,
   and intrinsic symbol/record consistency failures owned by this area.
2. The later link-set plan uses its own reservation for entry selection, graph completeness, and misuse of positional or
   foreign object classifications.
3. Re-check `L1C-2050` through `L1C-2069` against the live [diagnostic catalog][diagnostic-catalog] immediately before
   implementation. If any code has been assigned in the meantime, move this whole provisional block to a free 20-code
   range before registering concrete diagnostics.
4. Register only diagnostics that are actually implemented, with Stage 1 and future Stage 2 parity expectations stated
   in the catalog.

## Non-Goals

1. Computing or canonicalizing whole-module fingerprints.
2. Discovering source or `.l1m` files or constructing the source module graph.
3. Implementing `-c`, `--link`, `--entry`, or `--foreign-object` CLI behavior.
4. Selecting an entry module, checking graph closure, generating a process wrapper, or invoking the host linker.
5. Parsing static archives, dynamic libraries, debug information, relocations, or executable code.
6. Adding custom object sections, compiler-specific retention attributes, or dependencies on `nm`, `objdump`, or
   platform SDK libraries.
7. Supporting a fingerprint algorithm other than SipHash-1-3 in metadata format version 1.
8. Defending against maliciously crafted build inputs beyond strict bounded parsing; the initiative's threat model is
   stale or corrupted artifacts.

## Verification Criteria

01. Golden tests prove byte-identical version 1 encoding and decoding for module identity, entry presence, the raw
    SipHash-1-3 digest extracted from a canonical `sip13:` fingerprint, no imports, and multiple ordered imports.
02. Reordering direct source imports changes metadata order without sorting it; side-effect-only imports remain present;
    duplicate provider edges are coalesced at first occurrence before encoding.
03. Generated per-module C contains both external arrays and volatile references to both from external `I4init`.
04. A native compiled module object classifies as `ValidDeaMetadata` and reports the expected identity, fingerprint,
    ordered edges, lifecycle pair, and entry flag.
05. Minimal ELF, Mach-O, and PE/COFF fixtures cover valid metadata, ordinary metadata-free C objects, missing companion
    arrays, duplicate metadata, unsupported versions, entry-flag mismatches, and truncated or overflowing tables.
06. An ordinary C relocatable object with no Dea ABI symbols classifies as `NoDeaMetadata`; its process-level `main`
    definition, when present, is reported separately.
07. An old-style object with a recognizable Dea LBI definition but no version 1 metadata and every object with malformed
    metadata classify as `MalformedDeaMetadata`, never as foreign-compatible absence.
08. Fuzz-style bounded decoder tests over truncated fixture prefixes and corrupted length/count fields produce typed
    errors without crashes, out-of-bounds reads, or count-driven oversized allocations.
09. Tests prove inspection performs no external command execution and that unsupported containers receive explicit
    object-read errors.
10. Any concrete `L1C` diagnostics assigned by the implementation are registered in the shared catalog before closure.

[abi]: ../../../docs/specs/compiler/abi.md
[diagnostic-catalog]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[fingerprints]: closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[initiative]: ../../initiatives/0001-separate-compilation-and-linking.md
[interface-format]: ../../../docs/specs/compiler/module-interface-format.md
[lifecycle]: closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md
[link-set]: 2026-07-17-link-set-driver-and-wrapper-noref.md
[module-graph]: closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[superseded-metadata]: closed/2026-04-24-interface-fingerprints-and-object-metadata-noref.md
