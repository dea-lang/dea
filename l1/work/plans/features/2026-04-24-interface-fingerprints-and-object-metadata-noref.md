# Feature Plan

## Add interface fingerprints and provider-object metadata

- Date: 2026-04-24
- Status: Draft
- Title: Add interface fingerprints and provider-object metadata
- Kind: Feature
- Severity: High
- Stage: L1
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

## Current State

1. Stage 1 has no canonical public-surface hash for modules.
2. There is no corruption or stale-interface check when imported module information is replayed.
3. Provider object files do not embed any interface/version metadata for the driver to inspect before linking.
4. The current backend/link path relies on platform linker behavior rather than explicit Dea verification.

## Defaults Chosen

1. The hash input is the canonicalized public surface described by Initiative `0001`, not a per-symbol ABI hash scheme.
2. The `.l1m` file carries the module fingerprint text directly as `fingerprint "<hash>";`.
3. Consumers re-hash parsed interface declarations and reject mismatches immediately.
4. Provider objects embed their own exported fingerprint so the driver can verify importers against the actual object it
   is about to link.
5. Each consumer object embeds, alongside its own exported fingerprint, a list of
   `(imported module, expected dependency fingerprint)` records computed at compile time from the `.l1m` files the
   consumer read. Driver-facing verification reads from object files only; in-memory driver state is not the source of
   truth, so verification is robust across separate `--build` and `--link` invocations.
6. The metadata representation may be platform-specific internally, but the driver-facing verification behavior must be
   deterministic and portable.

## Goal

1. Compute deterministic fingerprints over the canonical public surface.
2. Verify `.l1m` integrity at read time.
3. Embed provider fingerprints into object output and verify them at link preparation time.
4. Produce clear stale-interface and stale-object failures before the host linker emits undefined-symbol noise.

## Implementation Phases

### Phase 1: Canonical hash input and algorithm choice

Settle the exact canonical hash input and pick the concrete fingerprint algorithm for Stage 1. The implementation should
make the canonicalization boundary explicit so later Stage 2 parity can validate the same surface without copying
incidental Stage 1 data structures.

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

## Diagnostics

1. This plan is expected to need diagnostics for fingerprint mismatch, stale provider objects, and verification metadata
   failures.
2. Provisionally reserve `SIG-0240` to `SIG-0259` for interface fingerprint and public-surface compatibility
   diagnostics.
3. Provisionally reserve `L1C-2050` to `L1C-2069` for provider-object metadata and link-time verification failures.
4. Re-check the live catalog at implementation time before assigning final numbers. If any proposed slot has been used
   in the meantime, choose a different free block then.

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
5. Any newly assigned diagnostic codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md`.
