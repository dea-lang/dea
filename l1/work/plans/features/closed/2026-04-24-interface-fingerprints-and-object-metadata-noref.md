# Feature Plan

## Add interface fingerprints and provider-object metadata

- Date: 2026-06-13
- Status: Closed (superseded)
- Title: Add interface fingerprints and provider-object metadata
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0001-separate-compilation-and-linking.md`
- Subsystem: ABI / hashing / driver / linker verification / docs
- Modules:
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/analysis_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/0001-separate-compilation-and-linking.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: None

## Summary

The `.l1m` format alone is not enough to make separate compilation trustworthy. Initiative `0001` now commits L1 to a
three-tier verification contract:

1. producer-side fingerprint emission,
2. consumer-side re-hash verification while reading `.l1m`,
3. link-time verification against metadata embedded in the provider object.

This plan owns that contract end to end.

## Closure Notes

This draft was superseded on 2026-07-17 before implementation. The end-to-end scope was cyclic: canonical interface
hashing can land independently, object records require the finalized module graph and lifecycle anchor, and enforcement
belongs to the later link-set driver. The work is now split across:

- canonical whole-module hashing plus `.l1m` producer/consumer verification in [fingerprints];
- provider/consumer record emission and bounded object readers in [object-metadata];
- object-set consistency enforcement before host linking in [link-set].

The former provisional `SIG-0240` to `SIG-0259` reservation also collided with the active anonymous embedded-struct
plan. The fingerprint successor uses the currently free `SIG-0280` to `SIG-0299` block instead. No fingerprint or
object-metadata behavior is claimed as implemented by this closure.

## Current State

1. Stage 1 has no canonical public-surface hash for modules.
2. There is no corruption or stale-interface check when imported module information is replayed.
3. Provider object files do not embed any interface/version metadata for the driver to inspect before linking.
4. The current backend/link path relies on platform linker behavior rather than explicit Dea verification.
5. Provider-object verification depends on the driver/fan-out tranche populating the dependency graph, including
   implementation-tier records such as `link` entries, before link preparation consumes that graph.

## Defaults Chosen

1. The hash input is the canonicalized effective public surface described by Initiative `0001`, not the verbatim export
   manifest and not a per-symbol ABI hash scheme.
2. The hash algorithm is SipHash-1-3 from the shared runtime (`l1/compiler/shared/runtime/internal/dea_siphash.h`,
   `siphash13(...)`), keyed with a fixed compile-time-constant 16-byte fingerprint key distinct from the runtime's
   randomized hash-flooding key. 64-bit digest. This decision is closed at the initiative level (Initiative 0001 §0.6).
3. The `.l1m` file carries the module fingerprint text directly as `fingerprint "sip13:<digest>";`, where the digest is
   encoded as 16 lowercase hexadecimal digits.
4. Consumers re-hash parsed interface declarations and reject mismatches immediately.
5. Provider objects embed their own exported fingerprint so the driver can verify importers against the actual object it
   is about to link.
6. Each consumer object embeds, alongside its own exported fingerprint, a list of
   `(imported module, expected dependency fingerprint)` records computed at compile time from the `.l1m` files the
   consumer read. Driver-facing verification reads from object files only; in-memory driver state is not the source of
   truth, so verification is robust across separate `--build` and `--link` invocations.
7. Nominal type canonicalization follows effective visibility: transparent `struct` / `enum` declarations serialize full
   canonical layout; opaque `struct` / `enum` declarations serialize the explicit opaque marker and name only;
   unexported nominal types are absent. Changing `export T` to `export opaque { T }`, or the reverse, changes the public
   surface fingerprint.
8. `require` records remain tied to symbols directly named in the exported surface. A `require` entry for an opaque
   nominal type records a name-level dependency and expected compatibility hash; it does not imply that the consumer has
   provider layout visibility.
9. The object-embedded metadata is emitted as portable C99 `const uint8_t` arrays with mangled names, anchored against
   linker dead-strip by being referenced from the module's `_dea_init`. Driver-side discovery uses symbol-table lookup
   on ELF / Mach-O / PE-COFF, which is also `tcc`-compatible. Custom object sections and platform-specific hybrids were
   rejected at the initiative level (Initiative 0001 §0.6).

## Goal

1. Compute deterministic fingerprints over the canonical public surface.
2. Verify `.l1m` integrity at read time.
3. Embed provider fingerprints into object output and verify them at link preparation time.
4. Produce clear stale-interface and stale-object failures before the host linker emits undefined-symbol noise.

## Implementation Phases

### Phase 1: Canonical hash input and key selection

Settle the exact canonical hash input and the fixed 16-byte fingerprint key constant. The algorithm itself is closed
(SipHash-1-3, see Initiative 0001 §0.6); Phase 1 work is therefore:

- Define the canonicalization rules over the public surface (sorted symbol order, normalized whitespace, nominal
  visibility state, transparent struct/enum layout serialization, opaque struct/enum marker serialization, exported
  `const` literal encoding, exported top-level `let` type encoding) and make the canonicalization boundary explicit so
  Stage 2 parity can validate the same surface without copying incidental Stage 1 data structures.
- Choose the fixed fingerprint key constant and record it in
  [`l1/docs/specs/compiler/abi.md`](../../../../docs/specs/compiler/abi.md) once stable.
- Choose the on-disk record layout for the object-embedded metadata (small magic + version prefix + flat little-endian
  fields is the expected default).

### Phase 2: Producer and consumer verification

Wire producer-side `.l1m` fingerprint writing and consumer-side re-hash checking into the interface emission/load path.
Malformed or corrupted interface files should fail before deeper semantic replay proceeds.

### Phase 3: Provider-object metadata and link-time binding

Emit provider fingerprint metadata into object output and teach the build driver to compare importer-recorded
fingerprints against provider objects before invoking the platform linker.

Each consumer object also embeds, alongside its own exported fingerprint, a list of
`(imported module, expected dependency fingerprint)` records computed at compile time from the `.l1m` files the consumer
read. The driver pulls both producer and consumer records from object files at link preparation time and rejects
mismatches before invoking the platform linker. Verification therefore does not depend on driver-managed in-memory state
and remains robust across separate `--build` and `--link` invocations.

This phase assumes the driver has already populated the module dependency records that identify which provider objects
belong in the link set. If implementation-tier dependency entries such as `link` lines are still syntax-only, this phase
must either defer provider-object verification for them or fail with a clear diagnostic rather than silently trusting an
incomplete graph.

## Diagnostics

1. This plan is expected to need diagnostics for fingerprint mismatch, stale provider objects, and verification metadata
   failures.
2. The superseded `SIG-0240` to `SIG-0259` proposal is not an active reservation; the fingerprint successor owns
   `SIG-0280` to `SIG-0299` provisionally.
3. The object-metadata successor retains `L1C-2050` to `L1C-2069` provisionally for provider-object metadata and reader
   failures; this superseded plan no longer owns that range.
4. The successor re-checks the live catalog at implementation time before assigning final numbers and moves the block if
   any proposed slot has been used in the meantime.

## Non-Goals

1. Export/import parser syntax.
2. Runtime static-library refactoring.
3. External-library linker flags.
4. Full `extern "C"` FFI declarations.

## Verification Criteria

1. Repeated builds over the same public module surface produce identical fingerprints.
2. Consumers reject corrupted or non-canonical `.l1m` files before semantic replay continues.
3. The driver rejects stale importer/provider combinations before host linking.
4. Verification behavior is covered by deterministic analysis/driver tests.
5. Tests prove that transparent-to-opaque and opaque-to-transparent export changes produce different fingerprints.
6. Any newly assigned diagnostic codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md`.

[fingerprints]: 2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[link-set]: ../2026-07-17-link-set-driver-and-wrapper-noref.md
[object-metadata]: ../2026-07-17-object-metadata-emission-and-readers-noref.md
