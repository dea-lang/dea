# Feature Plan

## Canonicalize and verify whole-module interface fingerprints

- Date: 2026-07-17
- Status: Draft
- Title: Canonicalize and verify whole-module interface fingerprints
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: [l1/work/initiatives/0001-separate-compilation-and-linking.md][initiative]
- Subsystem: Module interfaces / ABI fingerprinting / compatibility diagnostics
- Modules:
  - `l1/compiler/stage1_l0/src/module_interface.l0`
  - `l1/compiler/stage1_l0/src/mi_utils.l0`
  - `l1/compiler/stage1_l0/src/parser/interface.l0`
  - `l1/compiler/stage1_l0/src/interface_emitter.l0`
  - `l1/compiler/stage1_l0/src/interface_fingerprint.l0`
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/shared/runtime/internal/dea_siphash.h`
  - `l1/compiler/shared/runtime/src/dea_rt_hash.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l1/docs/specs/compiler/abi.md`
  - `l1/docs/specs/compiler/module-interface-format.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/interface_fingerprint_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_replay_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/compiler_runtime_build_env_test.py`
- Related:
  - [l1/work/plans/features/closed/2026-04-24-separate-compilation-driver-surface-noref.md][foundation]
  - [l1/work/plans/features/closed/2026-04-24-interface-fingerprints-and-object-metadata-noref.md][superseded]
  - [l1/work/plans/features/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md][module-graph]
  - [l1/work/plans/features/2026-07-17-object-metadata-emission-and-readers-noref.md][object-metadata]
  - [l1/docs/specs/compiler/abi.md][abi]
  - [l1/docs/specs/compiler/module-interface-format.md][module-format]
  - [docs/specs/compiler/diagnostic-code-catalog.md][diagnostic-catalog]
- Repro:
  `make -C l1 test-stage1 TESTS="interface_fingerprint_test interface_test interface_replay_test analysis_test driver_test compiler_runtime_build_env_test.py"`

## Summary

The current `.l1m` model has one module fingerprint placeholder plus a second, conflicting per-symbol hash scheme on
every declaration and dependency entry. It accepts and preserves empty or non-canonical hash strings without validating
their spelling, does not hash producer output, and replays a parsed interface without proving that its declared
fingerprint matches its public surface.

This plan replaces that ambiguity with one whole-module compatibility value. Producers hash the canonical effective
public surface with SipHash-1-3, write `sip13:` followed by exactly 16 lowercase hexadecimal digits, and consumers
recompute the same digest before semantic replay. Dependency records keep their current
`require module::symbol == "...";` and `link module::symbol == "...";` grammar, but each value is the provider module's
tagged whole-module fingerprint. Declaration suffix hashes are removed. Object embedding and link-time comparison remain
in the later [object-metadata plan][object-metadata].

## Dependencies and ordering

1. The completed interface-emission and [direct-replay foundation][foundation] provide canonical interface projection,
   parsing, and semantic replay.
2. This plan may land before or after the [module-graph plan][module-graph]. Its producer and consumer checks operate on
   one `ModuleInterface`; dependency records can use synthetic fixtures until graph population is available.
3. Once both plans are complete, graph projection copies each parsed provider's verified whole-module fingerprint into
   every `require` or `link` entry naming that provider.
4. The [object-metadata plan][object-metadata] is blocked on both plans because it serializes verified module-level
   provider and consumer expectations, not the obsolete per-symbol hashes.

## Defaults chosen

### Algorithm, key, and encoding

1. Use the existing portable `siphash13(...)` implementation from `l1/compiler/shared/runtime/internal/dea_siphash.h`.
   SipHash-1-3 is the only supported algorithm in the version 1 interface-fingerprint contract. The threat model is
   accidental staleness and corruption, not an adversarial collision attack.
2. Use the fixed 16-byte ASCII key `DeaL1-fp-v1-key!`, whose bytes are
   `44 65 61 4c 31 2d 66 70 2d 76 31 2d 6b 65 79 21`. The key is public, versioned as part of the LBI ABI, and distinct
   from the runtime's process hash-flooding key.
3. Hash the canonical byte stream as UTF-8 bytes with LF separators and no terminating NUL.
4. Encode the unsigned 64-bit result as exactly 16 lowercase hexadecimal digits, including leading zeroes. The raw
   digest formatter does not add `0x` or use variable width.
5. Spell the textual `.l1m` value as exactly `sip13:<digest>`, with the lowercase `sip13` algorithm identifier and the
   lowercase 16-digit digest. The tagged envelope contains exactly one colon, a nonempty identifier matching
   `[a-z][a-z0-9]*`, and a nonempty payload. A missing or additional colon, an empty component, or invalid identifier
   casing or characters is malformed. After validating that envelope, select the algorithm before validating its
   algorithm-specific payload: an identifier other than `sip13` receives an unsupported-algorithm diagnostic, while a
   malformed `sip13` payload receives a malformed-fingerprint diagnostic. The tag is mandatory: an untagged digest does
   not implicitly select SipHash-1-3.
6. Stage 1 uses a narrow compiler-support wrapper around `siphash13(...)` because the bootstrap language has no public
   unsigned 64-bit scalar. The wrapper accepts canonical bytes and the fixed key and returns the raw 16-digit digest; a
   compiler-side formatter attaches the `sip13:` tag. The bridge is compiler-internal, adds no language or stdlib API,
   and must be covered by the normal and traced runtime symbol checks.

### Canonical fingerprint input

The fingerprint input is a versioned canonical serialization named `l1-interface-fingerprint-v1`. It starts with that
ASCII domain line and then serializes only the effective exported declaration surface in the same deterministic group
and name order as `.l1m` emission:

1. transparent structs, including declaration name and field names, field order, and canonical field types;
2. opaque structs, including the explicit opacity marker and declaration name only;
3. transparent enums, including declaration name, variant names and order, payload labels, and canonical payload types;
4. opaque enums, including the explicit opacity marker and declaration name only;
5. type aliases, including name and canonical target type;
6. functions, including name, parameter names and order, canonical parameter and result types, and `extern`, `unsafe`,
   and variadic state;
7. exported consts, including name, canonical type, and canonical folded literal; and
8. exported top-level lets, including name and canonical type.

Each record is length-delimited before its UTF-8 payload so punctuation or string contents cannot create ambiguous
concatenations. The canonicalizer is a dedicated data-to-bytes operation; it must not hash rendered prose, platform line
endings, map iteration order, or incidental Stage 1 pointer/data-structure layout.

The following are excluded from the input:

- the source export-manifest spelling;
- the module header and module filesystem location, because module identity is checked separately;
- the `fingerprint` declaration itself;
- `require` and `link` dependency manifests;
- private declarations, function bodies, and other implementation-only imports or details; and
- object metadata, compiler version strings, timestamps, and host-platform data.

### `.l1m` grammar migration

1. `fingerprint "<hash>";` remains immediately after the module header and becomes mandatory with the exact
   `sip13:<16 lowercase hexadecimal digits>` spelling once this plan lands.
2. Remove per-declaration `== "<hash>"` suffixes from structs, enums, aliases, functions, consts, and lets. Remove the
   corresponding `hash` fields from `InterfaceFuncEntry`, `InterfaceLetEntry`, and `InterfaceAliasEntry`; struct and
   enum interface data likewise has no declaration hash.
3. Preserve the dependency grammar. Rename its in-memory value from a generic per-symbol `hash` to
   `provider_fingerprint`, and define it as the provider module's whole-module fingerprint. Multiple symbols from the
   same provider therefore repeat the same value.
4. A dependency manifest remains excluded from the importing module's own fingerprint, so adding a private import does
   not invalidate downstream consumers of an unchanged public surface.
5. Empty, untagged, uppercase, malformed-tag, non-hexadecimal, short, and overlong fingerprint strings become invalid
   compatibility data. There is no implicit algorithm or legacy fallback because operational separate compilation has
   not shipped yet. A well-formed but unsupported lowercase algorithm identifier is diagnosed separately from malformed
   spelling.

### Producer and consumer verification

1. Producer projection first constructs the hash-free `ModuleInterface` public surface, canonicalizes it, computes the
   digest, and assigns the module fingerprint before final text emission.
2. Consumer parsing constructs the same hash-free public-surface model, validates the declared tagged fingerprint,
   recomputes it, and compares the exact canonical `sip13:<digest>` text before alias normalization, interface
   activation, name resolution, or signature replay.
3. A mismatch reports both the declared and recomputed fingerprints plus the interface path, but does not continue with
   semantic replay.
4. Cloning and projection of a verified imported interface preserve its declared fingerprint exactly. Re-emission must
   reproduce the same canonical text and digest.
5. The verifier is used by filesystem-discovered and programmatically supplied interfaces alike so tests cannot bypass
   integrity checks through an alternate entry point.

## Goal

1. Establish one stable LBI fingerprint contract for a module's effective public surface.
2. Detect corrupted, non-canonical, or stale `.l1m` content before semantic replay.
3. Remove the obsolete per-symbol declaration-hash model without changing dependency tier semantics.
4. Provide verified whole-module values that later object metadata and link-set validation can trust.
5. Keep fingerprint output byte-identical across repeated Stage 1 runs and future Stage 2 parity work.

## Implementation phases

### Phase 1: Simplify the interface model and grammar

Remove per-declaration hash storage, parsing, cloning, and emission. Retain `InterfaceDepEntry` values under the
explicit `provider_fingerprint` name. Update parser fixtures and canonical interface examples in one change so the model
cannot temporarily interpret declaration suffixes as module compatibility values.

The parser may continue to parse the fingerprint token as a string, but the fingerprint verifier owns exact spelling and
value diagnostics. Ordinary parser and replay fixtures use canonical lowercase `sip13:<digest>` examples. Retain one
explicitly named low-level parser test with a non-canonical uppercase or symbolic token to prove that constrained
parsing alone remains wire-preserving; operational consumers must still pass the verifier. Unexpected declaration
suffixes remain parser errors under the existing interface grammar family.

### Phase 2: Canonicalizer and SipHash bridge

Add `interface_fingerprint.l0` with pure helpers for canonical record framing, public-surface serialization, fingerprint
tag parsing, spelling checks, raw digest and tagged-text formatting, and comparison. Add the narrow runtime bridge
needed to obtain all 64 SipHash bits without folding to the ordinary 32-bit runtime hash API. Record the key, domain
string, canonical input rules, algorithm identifier, and encoding in the [LBI ABI document][abi].

Tests must pin both the canonical byte stream and a known-answer digest produced by the shared C `siphash13(...)`
implementation. The compiler wrapper, direct C result, normal runtime archive, and traced runtime archive must agree on
the raw digest, and the formatter must produce the pinned `sip13:<digest>` text.

### Phase 3: Producer emission

Compute the fingerprint after interface projection has finalized and sorted the effective public declarations but before
`ie_emit` writes the header. Make internal interface emission and later compile-only production use the same function.
Ensure no caller can emit a fresh operational `.l1m` with an empty or stale fingerprint.

When the [module-graph plan][module-graph] is present, copy each already verified provider fingerprint into all emitted
dependency entries for that provider. This integration must not make dependency lines part of the current module's hash
input.

### Phase 4: Consumer verification

Insert verification directly after constrained interface parsing and before the driver registers either the
wire-preserving projection clone or alias-normalized semantic clone. Fail closed on invalid spelling or digest mismatch;
do not fall back to source when the selected interface is authoritative.

Expose one verified parsing result to the transitive graph loader so each physical interface is parsed and hashed once.
Cache success only after verification completes.

### Phase 5: Documentation and compatibility cleanup

Update the [module interface format][module-format] to replace placeholders and non-canonical examples with exact tagged
whole-module values, remove declaration suffixes, and define provider-module dependency fingerprints. Update tests and
all active planning references that still describe per-symbol compatibility hashes. Do not describe object embedding or
link-time checking as implemented; those remain in [object metadata][object-metadata].

## Diagnostics

1. This plan needs a fresh signature/compatibility slice for malformed fingerprint spelling, unsupported algorithm
   identifiers, declared-versus-computed mismatch, and internal canonicalization guards that surface as user
   diagnostics.
2. Provisionally reserve `SIG-0280` to `SIG-0299` for whole-module interface fingerprint validation.
3. The former `SIG-0240` to `SIG-0259` proposal cannot be reused: that range is also reserved by the active anonymous
   embedded-struct plan. This plan intentionally moves to `SIG-0280` to `SIG-0299` to avoid the known collision.
4. Parser shape errors continue to use existing `PAR-*` codes. Object-reader and intrinsic metadata-record failures
   belong to the later metadata plan's `L1C-2050` to `L1C-2069` range; link-set graph and provider-consistency failures
   belong to the link-set plan's `L1C-2090` to `L1C-2109` range.
5. The new range is provisional despite the current audit. Re-check the live [diagnostic catalog][diagnostic-catalog]
   immediately before implementation and select another unused block of 20 if any `SIG-0280` to `SIG-0299` code has been
   assigned in the meantime.

## Non-goals

1. Interface-path search, transitive graph construction, or `require` / `link` population.
2. Object metadata record layout, object-format readers, or link-time provider verification.
3. Per-symbol compatibility hashes or a fallback for legacy placeholder interfaces.
4. Implementing algorithms other than SipHash-1-3 or accepting an omitted tag as an implicit algorithm selection.
5. Cryptographic authenticity, signing, collision resistance against malicious artifacts, or secret key management.
6. Compile-only artifact publication, host linking, entry selection, or lifecycle ordering.
7. Implementing Stage 2 before the self-hosted compiler exists.

## Verification criteria

01. Repeated projections of the same effective public surface produce byte-identical canonical input, fingerprint text,
    and `.l1m` output.
02. Source declaration order and export-manifest spelling do not change the fingerprint after canonical sorting.
03. Private declarations, function bodies, private imports, and `require` / `link` manifest changes do not change the
    importing module's own fingerprint.
04. Changes to any exported declaration name, public parameter name, signature, transparent layout, enum variant,
    opacity state, alias target, const literal, or top-level let type change the fingerprint.
05. The compiler-support wrapper matches a direct known-answer `siphash13(...)` call for the fixed key and pinned
    canonical bytes under normal and traced runtime archives.
06. Producer output always contains exactly `sip13:` followed by 16 lowercase hexadecimal digits, including leading
    zeroes.
07. Empty, untagged, uppercase, malformed-tag, non-hexadecimal, short, and overlong values are rejected before replay; a
    well-formed unknown value such as `other1:0123456789abcdef` reports unsupported algorithm rather than malformed
    digest.
08. Editing a declaration without updating the fingerprint reports a deterministic `SIG-*` mismatch before name or
    signature resolution.
09. Declaration entries no longer carry hash suffixes or in-memory hash fields.
10. Every dependency entry for one provider carries the same provider whole-module fingerprint and remains outside the
    consumer's own hash input.
11. Parse, verify, clone, and re-emit round trips preserve the declared tagged fingerprint and canonical interface
    bytes.
12. Canonical fixtures use lowercase tagged values; one explicitly low-level parser fixture retains a non-canonical
    token and proves parsing alone preserves it without bypassing operational verification.
13. Focused normal and trace tests pass, followed by `make -C l1 test` once implementation is complete.
14. Concrete diagnostics are registered in the shared catalog in the implementation change.

[abi]: ../../../docs/specs/compiler/abi.md
[diagnostic-catalog]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[foundation]: closed/2026-04-24-separate-compilation-driver-surface-noref.md
[initiative]: ../../initiatives/0001-separate-compilation-and-linking.md
[module-format]: ../../../docs/specs/compiler/module-interface-format.md
[module-graph]: 2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[object-metadata]: 2026-07-17-object-metadata-emission-and-readers-noref.md
[superseded]: closed/2026-04-24-interface-fingerprints-and-object-metadata-noref.md
