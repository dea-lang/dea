# ADR-0030: Authoritative Module Interfaces and Opaque Native Link Inputs

- Decision date: 2026-08-21
- Last edited: 2026-08-21
- Status: Accepted
- Supersedes: [ADR-0021][object-metadata]
- Supersedes: [ADR-0028][verified-link-set]

## Context

The first standalone-link implementation made portable records embedded in each Dea object authoritative for module
identity, public fingerprint, ordered imports, and entry presence. It also classified Dea and foreign native inputs with
bounded ELF, Mach-O, and PE/COFF readers, rejected embedded linker controls, and copied accepted input bytes into an
output-local transaction before invoking the host linker.

The canonical sibling `.l1m` already carries the same Dea semantics in a portable, verified textual artifact. Keeping a
second native metadata format duplicated authority, required host-object readers in both bootstrap stages, and still did
not make object/interface publication reader-atomic. L1 therefore needs one semantic authority while stating plainly
which native behavior is caller-trusted.

## Decision

For standalone `l1c --link`, every positional Dea `.o` path requires a canonical sibling `.l1m`. The driver reads and
verifies that interface before graph registration. The interface is the sole authority for module identity, public
fingerprint, entry presence, ordered first-occurrence lifecycle imports, and `require` / `link` expectations.

The driver validates provider presence and fingerprints across the complete supplied interface set. Ordered lifecycle
imports alone define lifecycle reachability and dependency-first initialization; `require` and `link` remain semantic
expectations and do not create lifecycle edges. Every non-virtual provider named by either expectation tier must be
transitively reachable through lifecycle imports.

Native inputs are opaque host-toolchain payloads. Positional Dea objects, explicit `-Cf` / `--foreign-object` operands,
the generated wrapper object, runtime archives or objects, and optional host math linkage are not byte-inspected by Dea.
The caller asserts that each positional object matches its verified sibling interface and that every foreign object is
host-compatible. The final host command consumes the original caller paths rather than transaction-owned snapshots.

`L1_CFLAGS` and `--c-options` configure wrapper compilation and are not appended as final-link command words. Because
the wrapper object is opaque, those options may still cause the host compiler to encode toolchain-specific linker
controls that the final linker honors. This indirect native effect is part of the caller-trusted compiler boundary, not
part of the verified Dea link graph or typed native-operand model.

Per-module generated C retains `I4init`, `I4fini`, and conditional `I5entry`. The former `I8metadata` and `I7imports`
records, retention reads, native-object readers, Dea/foreign byte classification, embedded-control preflight, foreign
`main` preflight, and caller-input snapshots are retired.

Compile-only continues to publish a canonical sibling `.o + .l1m` pair with endpoint rollback. It validates the staged
interface and that the staged native output is a regular file, but it does not authenticate or structurally bind the
pair. Concurrent readers and same-stem writers must serialize externally.

## Rationale

- One portable interface authority removes duplicate semantic formats and host-object parsers from the bootstrap.
- Keeping lifecycle imports distinct from symbol expectations preserves source import side effects and deterministic
  initialization without turning semantic references into lifecycle edges.
- Opaque native paths match the host toolchain boundary and avoid incomplete platform-specific content policing.
- Explicitly documenting wrapper-object linker controls makes the trust boundary accurate at the object layer rather
  than only at the final command-line layer.
- Retaining endpoint rollback and bounded wrapper scratch preserves useful filesystem ownership guarantees independently
  of native-byte inspection.

## Consequences

- A mixed-generation or malicious `.o + .l1m` pair can link successfully and produce incorrect native, entry, or
  lifecycle behavior; the pair is caller-trusted.
- Dea reports interface, graph, fingerprint, entry, and lifecycle-provenance errors before host linking, but native
  format, architecture, duplicate symbol, foreign `main`, and embedded-control errors are left to the host toolchain.
- Caller paths may change between interface verification and host consumption; external serialization is required.
- Operational interface records remain outside the public-surface fingerprint, so they do not provide an object or link
  manifest binding.
- Stage 2 must preserve the interface authority, lifecycle order, wrapper ABI, and opaque native-input contract without
  reintroducing a second metadata authority.

## Related Plans

- [l1/work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md][authority-plan]

## Current Docs

- [docs/specs/compiler/cli-contract.md][cli]: public standalone-link and wrapper-option trust boundary
- [l1/docs/reference/separate-compilation.md][separate-compilation]: artifact, graph, lifecycle, and native-input rules
- [l1/docs/specs/compiler/module-interface-format.md][interface-format]: operational interface grammar and verification
- [l1/docs/specs/compiler/abi.md][abi]: retained lifecycle and entry symbols
- [l1/docs/reference/c-backend-design.md][backend]: per-module and wrapper emission behavior

[abi]: ../specs/compiler/abi.md
[authority-plan]: ../../work/plans/features/closed/2026-08-20-l1m-authoritative-standalone-linking-noref.md
[backend]: ../reference/c-backend-design.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[interface-format]: ../specs/compiler/module-interface-format.md
[object-metadata]: 0021-portable-object-metadata-and-inspection.md
[separate-compilation]: ../reference/separate-compilation.md
[verified-link-set]: 0028-verified-link-set-and-foreign-object-boundary.md
