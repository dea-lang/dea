# ADR-0021: Portable Object Metadata and Inspection

- Decision date: 2026-07-23
- Last edited: 2026-07-27
- Status: Accepted

## Context

Standalone linking must prove that each provider object matches the interfaces against which its consumers were
compiled. Reopening sibling `.l1m` files would make object identity depend on adjacent mutable files, and delegating
inspection to `nm`, `objdump`, or platform SDKs would make the bootstrap depend on host-specific command output.

The object boundary must remain portable C99, work with the supported host compilers, survive linker dead-strip, and
distinguish an ordinary foreign relocatable object from an old, stripped, incomplete, or corrupt Dea object. The
standalone-link tranche also needs exact defined-symbol lookup for lifecycle, entry, and foreign `main` checks.

## Decision

Every separately generated Dea module defines two external `const uint8_t` arrays under reserved LBI infrastructure
terminals:

- `I8metadata` is the module identity record.
- `I7imports` is the ordered direct-import record.

Both records use a version 1 binary envelope with the eight-byte ASCII magic `DEAL1OBJ`, a little-endian 16-bit version,
a little-endian 16-bit record kind, and a little-endian 32-bit payload length. The identity payload carries version 1
flags, the canonical module-name length, the producer's raw 64-bit interface fingerprint, and the canonical dotted
module name. The imports payload carries a count followed by canonical provider names and their expected raw 64-bit
fingerprints.

Metadata version 1 fixes SipHash-1-3 as the fingerprint algorithm. It stores the raw digest bytes in little-endian
order; a new fingerprint algorithm requires a new metadata format version. Imports appear once per direct object-backed
(non-virtual) provider in first source-import order, including side-effect-only imports. Duplicate providers,
non-canonical names, unknown flags, unsupported versions, and inconsistent lengths are malformed.

`I4init` performs one volatile byte read from each array before module-local initialization. This creates portable
object-level references that retain the records without custom sections, compiler-specific attributes, or changes to
cross-module lifecycle ordering.

The compiler owns bounded in-repository readers for relocatable ELF, Mach-O, and standard COFF containers. The readers
inspect only the section, load-command, symbol, and string-table data needed to locate defined symbols, recover the two
arrays, and recognize embedded linker-control carriers. They normalize only exact object-ABI aliases before matching:
canonical ELF plus Darwin TinyCC `___dea...` / `_main`, one Mach-O or COFF I386 leading underscore, and one leading `#`
on COFF ARM64EC function symbols. The standard COFF reader accepts I386, ARM, ARMNT, AMD64, ARM64EC, and ARM64; it
rejects PE images, bigobj/import objects, and other machines. Readers check all offset/count/length arithmetic and do
not invoke external inspection tools.

A successful container read reports basic container information, exact defined-symbol lookup, process-level C `main`
presence, one normalized linker-control kind, and exactly one metadata classification. The control kind is either none,
ELF dependent libraries, Mach-O linker option, or PE/COFF directive section. Standard decimal and LLVM base-64 COFF
string-table section-name indirections are resolved before control classification; directive payloads are not
interpreted or exposed. Metadata classification remains:

- valid Dea metadata, with module identity, fingerprint, ordered imports, and entry presence;
- no Dea metadata, only when neither a metadata symbol nor an external definition under the normalized `__dea` prefix is
  present; or
- malformed Dea metadata, when any Dea marker is present but the complete metadata, lifecycle, and entry contract is not
  valid.

File access failures and unsupported or corrupt object containers are read errors outside that tri-state. A caller
cannot reclassify valid or malformed Dea metadata as metadata-free. The normalized `__dea` prefix is reserved in full,
so a definition under it remains Dea evidence even when its suffix is not a valid LBI production.

## Rationale

- External byte arrays are expressible in portable C99 and expose stable LBI names in every supported object format.
- Embedding both producer identity and consumer expectations makes each object self-describing for standalone link-set
  validation.
- Anchoring from the always-present lifecycle entry point retains metadata while avoiding custom sections and
  toolchain-specific retention directives.
- A format-neutral tri-state makes the explicit foreign-object boundary safe: absence is meaningfully different from a
  recognizable but invalid Dea artifact.
- Small bounded readers keep classification deterministic across hosts and avoid parsing arbitrary command output.
- Normalizing control carriers separately from metadata preserves one format-neutral inspection pass without treating
  untrusted directive payloads as driver arguments.

## Consequences

- Per-module objects now have a versioned metadata ABI in addition to source symbols and lifecycle entry points.
- Any future change to record names, kinds, flags, byte order, or version 1 layout is an ABI change.
- Standalone link validates provider fingerprints and graph closure directly from objects and rejects foreign objects
  that define C `main`.
- Standalone link can reject format-recognized embedded linker controls for both Dea and foreign operand roles.
- Archives, shared libraries, relocations, debug information, executable loading, and architecture compatibility remain
  outside the object-reader contract.
- Compile-only production and standalone linking share the final metadata-bearing object shape.
- A future Stage 2 compiler must emit and classify byte-identical metadata under the same rules.

## Related Plans

- [l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md][object-metadata]
- [l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md][fingerprints]
- [l1/work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md][lifecycle]
- [l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md][link-set]
- [l1/work/plans/features/closed/2026-04-24-interface-fingerprints-and-object-metadata-noref.md][superseded-metadata]
- [l1/work/plans/bug-fixes/closed/2026-07-27-stage1-standalone-link-hardening-noref.md][link-hardening]

## Current Docs

- [l1/docs/specs/compiler/abi.md][abi]: normative symbols and version 1 record layout
- [l1/docs/reference/c-backend-design.md][backend]: emission, retention, and object-reader behavior
- [l1/docs/reference/architecture.md][architecture]: object-inspection pipeline and invariants
- [l1/docs/project-status.md][project-status]: implemented Stage 1 scope

[abi]: ../specs/compiler/abi.md
[architecture]: ../reference/architecture.md
[backend]: ../reference/c-backend-design.md
[fingerprints]: ../../work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[lifecycle]: ../../work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md
[link-hardening]: ../../work/plans/bug-fixes/closed/2026-07-27-stage1-standalone-link-hardening-noref.md
[link-set]: ../../work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md
[object-metadata]: ../../work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md
[project-status]: ../project-status.md
[superseded-metadata]: ../../work/plans/features/closed/2026-04-24-interface-fingerprints-and-object-metadata-noref.md
