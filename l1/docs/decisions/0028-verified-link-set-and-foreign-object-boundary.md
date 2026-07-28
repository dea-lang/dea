# ADR-0028: Verified Link Set and Foreign-Object Boundary

- Decision date: 2026-07-27
- Last edited: 2026-07-27
- Status: Accepted

## Context

Separately compiled Dea modules carry enough portable object metadata to identify their module, fingerprint, direct
providers, lifecycle symbols, and entry bridge. Producing an executable from those objects requires a driver boundary
that treats this embedded evidence as authoritative without reopening mutable `.l1m` files.

Metadata-free C relocatable objects are also useful for satisfying the current unmangled `extern func` surface. Treating
metadata absence as implicit foreign authorization, however, would let malformed or deliberately disguised Dea objects
bypass module-graph, fingerprint, lifecycle, and entry verification.

## Decision

L1 exposes standalone executable linking through `l1c --link`. Positional operands are asserted Dea objects;
metadata-free C relocatables are accepted only through repeatable `--foreign-object` operands. The driver preserves the
typed operands in CLI encounter order and inspects every object exactly once.

Each positional object must have valid Dea metadata. Each explicit foreign object must have no Dea metadata. Valid or
malformed Dea evidence is never accepted through the foreign boundary, and a foreign object defining the normalized
process symbol `main` is rejected because the generated wrapper owns process entry.

Every supported object must also be free of format-recognized embedded linker controls. Bounded readers mark ELF
dependent-library sections, Mach-O linker-option commands, and PE/COFF directive sections without interpreting their
payloads. Either a Dea or foreign operand carrying one is rejected before module registration or scratch allocation;
libraries and raw linker controls must enter through an explicit typed surface rather than hidden object metadata. After
compiling the generated process wrapper, the driver applies the same control inspection before the final host link, so
wrapper-only C options cannot synthesize an implicit final-link input.

Before invoking a host linker, the driver verifies unique module identities, complete direct-provider closure, exact
consumer/provider fingerprints, and an acyclic dependency graph. It then selects exactly one entry-bearing module,
either by deterministic inference or explicit canonical module name.

The verified graph produces one deterministic dependency-first lifecycle order. A generated C wrapper initializes
runtime arguments, calls each Dea `I4init` in that order, invokes only the selected `I5entry`, calls `I4fini` in exact
reverse order, and returns the normalized entry status. Disconnected explicitly supplied Dea components follow the
selected entry component in positional encounter order. Foreign objects receive no generated lifecycle or entry calls.

The final host command places the wrapper first, retains every user operand in typed encounter order, and appends the
runtime link inputs selected under [ADR-0027][runtime-boundary]. Object metadata is the sole authority for standalone
Dea graph verification; `.l1m` files are not read by link mode. Input filenames that resemble host-driver options or
response files are rendered as unambiguous filesystem paths. Before host invocation, the standalone adapter writes one
transaction-owned snapshot from the exact bytes read for each operand; the final command consumes those snapshots in
typed encounter order, so concurrent caller-path replacement cannot change the verified link set.

## Rationale

An explicit typed boundary makes metadata absence a deliberate user assertion while preserving the distinction between
absence and recognizable invalid Dea evidence. Full pre-link graph verification reports stale or incomplete module sets
deterministically instead of delegating semantic consistency to host-linker symbol errors. A separate wrapper keeps
process entry and cross-module lifecycle composition out of independently compiled modules.

## Consequences

- Standalone linking requires at least one verified positional Dea object and exactly one executable output.
- Missing providers, stale fingerprints, duplicate identities, cycles, and ambiguous or absent entries fail before host
  linking or wrapper workspace allocation.
- Metadata-free foreign objects can satisfy ordinary unmangled C references but never acquire module, fingerprint,
  dependency, lifecycle, or entry semantics.
- Dea and foreign objects containing recognized embedded linker controls fail before graph, wrapper, transaction, or
  host-link work begins.
- A generated wrapper containing a recognized embedded linker control fails before final host linking.
- Unsupported object formats and architecture or ABI mismatches remain bounded-reader or host-link failures as
  appropriate.
- Original caller objects remain caller-owned and untouched; exact-byte snapshots are bounded transaction children.
- Ordinary `--build` and `--run` remain on the legacy single-CU path until their graph fan-out plan reuses the internal
  compile/link APIs.

## Related Plans

- [l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md][link-set]
- [l1/work/plans/features/closed/2026-04-24-interface-fingerprints-and-object-metadata-noref.md][superseded-metadata]
- [l1/work/plans/bug-fixes/closed/2026-07-27-stage1-standalone-link-hardening-noref.md][link-hardening]

## Current Docs

- [docs/specs/compiler/cli-contract.md][cli]: public mode and operand contract
- [l1/docs/specs/compiler/abi.md][abi]: metadata, lifecycle, and entry ABI
- [l1/docs/reference/separate-compilation.md][separate-compilation]: link-set validation and usage
- [l1/docs/reference/architecture.md][architecture]: Stage 1 link pipeline

[abi]: ../specs/compiler/abi.md
[architecture]: ../reference/architecture.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[link-hardening]: ../../work/plans/bug-fixes/closed/2026-07-27-stage1-standalone-link-hardening-noref.md
[link-set]: ../../work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md
[runtime-boundary]: 0027-runtime-archive-and-trace-selection-boundary.md
[separate-compilation]: ../reference/separate-compilation.md
[superseded-metadata]: ../../work/plans/features/closed/2026-04-24-interface-fingerprints-and-object-metadata-noref.md
