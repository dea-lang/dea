# ADR-0019: Whole-Module Interface Fingerprints

- Decision date: 2026-07-21
- Last edited: 2026-07-23
- Status: Accepted

## Context

The first `.l1m` artifact model reserved an empty module fingerprint and separate empty compatibility suffixes on every
declaration. Parsed strings were preserved but not validated. That left two competing compatibility models and allowed
stale or corrupted public-surface data to reach graph registration and semantic replay.

L1 needs one deterministic value that producers can derive from an effective public surface and consumers can verify
without source access or graph-backed nominal-kind materialization.

## Decision

L1 uses one tagged whole-module fingerprint for each `.l1m` public surface:

- Version 1 is SipHash-1-3 with fixed public ASCII key `DeaL1-fp-v1-key!`.
- Text uses exactly `sip13:<16 lowercase hexadecimal digits>`.
- Canonical UTF-8 input starts with `l1-interface-fingerprint-v1\n`. Every following declaration record and every nested
  field uses ASCII decimal byte-length framing.
- Declaration groups and names are sorted. Fields, variants, payloads, and parameters retain semantic source order.
- Canonical string literals are derived from decoded bytes rather than escape spelling. Scalar `\x`, `\u`, and `\U`
  escapes encode Unicode scalar values as UTF-8, while octal escapes retain raw-byte semantics.
- Canonical integers are decimal values within the implemented integer domain: negative values are bounded by `long` and
  non-negative values by `ulong`.
- The fingerprint includes effective exported structs, enums, aliases, function signatures, const values, and top-level
  let types.
- Module identity, the fingerprint itself, dependency manifests, private implementation, compiler metadata, and object
  metadata are excluded.
- Nominal type records contain module and name but not struct/enum kind, allowing verification before semantic
  materialization. Local declaration records retain the actual nominal kind.
- Per-declaration hash suffixes and storage are removed.
- Every `require` and `link` entry repeats the provider module's tagged whole-module fingerprint. Dependency values do
  not contribute to the consumer's digest.

Operational consumers check declared module identity, validate the module and dependency tags, require one consistent
value per provider, recompute the public-surface fingerprint, and compare it before graph registration, caching,
normalization, activation, or replay. A selected authoritative interface never falls back to source after fingerprint
failure.

## Rationale

- One module-level value gives one compatibility identity for a public surface and removes ambiguous per-symbol state.
- Length framing is unambiguous for arbitrary UTF-8 names and literals without depending on rendered source syntax.
- Decoded-value canonicalization makes raw UTF-8 and equivalent scalar escapes fingerprint-identical while preserving
  octal escapes for byte-oriented literals.
- A fixed domain and key make results stable across hosts and bootstrap stages.
- Shared declaration traversal prevents text emission and fingerprint ordering from drifting apart. Checked two-pass
  type framing avoids repeated subtree materialization without imposing a language-level depth ceiling.
- Generic nominal reference records let integrity checking precede graph and alias resolution while declaration records
  still distinguish public struct and enum changes.
- Excluding dependency manifests prevents private import changes from invalidating downstream consumers.

## Consequences

- Empty, untagged, uppercase, malformed, unsupported, and mismatched fingerprints fail before semantic replay.
- Source-backed provider surfaces are independently projected and hashed so emitted dependency expectations are
  populated without recursive hashing.
- The constrained parser may preserve an arbitrary string for a parser-only round trip, but no operational path treats
  that string as verified.
- Stage 1 retains string source spelling separately for diagnostics, consumes the lexer-decoded value in interface
  literals, and uses the shared bigint range table before canonical decimal conversion.
- Text emission and fingerprinting consume one stable kind/name ordering of borrowed declarations. Type framing first
  records checked preorder payload sizes and then streams bytes from those cached sizes; overflow is a canonicalization
  failure.
- The compiler uses a narrow allocation-free C bridge to obtain all 64 SipHash bits during Stage 1 bootstrap.
- Object metadata embedding, provider-object readers, and link-time comparison remain future work. They must consume
  this fingerprint contract rather than introduce a second public-surface hash.

## Related Plans

- [l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md][fingerprints]
- [l1/work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md][module-graph]
- [l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md][object-metadata]

## Current Docs

- [l1/docs/specs/compiler/module-interface-format.md][module-format]: canonical stream, grammar, and verification order
- [l1/docs/specs/compiler/abi.md][abi]: fixed key, algorithm, digest spelling, and compiler bridge
- [l1/docs/reference/architecture.md][architecture]: producer and consumer data flow
- [docs/specs/compiler/diagnostic-code-catalog.md][diagnostic-catalog]: fingerprint diagnostics

[abi]: ../specs/compiler/abi.md
[architecture]: ../reference/architecture.md
[diagnostic-catalog]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[fingerprints]: ../../work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[module-format]: ../specs/compiler/module-interface-format.md
[module-graph]: ../../work/plans/features/closed/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[object-metadata]: ../../work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md
