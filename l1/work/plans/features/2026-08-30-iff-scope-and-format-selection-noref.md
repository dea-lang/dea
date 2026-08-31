# Feature Plan

## Resolve the roadmap IFF item

- Date: 2026-08-30
- Status: Draft
- Title: Identify the intended IFF format, consumer, and standard-library scope
- Kind: Feature
- Severity: Low
- Priority: 4
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0008-data-format-modules.md`
- Subsystem: Stdlib / data formats / roadmap design
- Modules:
  - `l1/docs/specs/stdlib/iff-format.md`
  - `l1/compiler/shared/l1/stdlib/std/iff.l1`
- Test modules:
  - `l1/compiler/stage1_l0/tests/iff_test.l0`
- Related:
  - `l1/work/initiatives/0008-data-format-modules.md`
  - `l1/docs/roadmap.md`
- Repro: `rg -n "IFF|Interchange File Format" l1 docs work`

## Summary

The roadmap names `IFF` without identifying the exact format, variant, consumer, or desired operations. This Priority 4
plan resolves that ambiguity before any `std.iff` implementation is authorized.

## Questions to Resolve

1. Whether `IFF` means Electronic Arts Interchange File Format, a Dea-specific interface format, or another format.
2. Which concrete consumer justifies core-stdlib ownership.
3. Required chunk identifiers, byte order, padding, nesting, size bounds, and unknown-chunk behavior.
4. Whether the API is a generic chunk reader/writer or a format-specific model.
5. Whether the work belongs in core `std.*`, an external package, compiler tooling, or should be removed from the
   roadmap.

## Approach

1. Trace the roadmap entry's history and record any motivating artifact or consumer.
2. Compare candidate meanings and reject those without a current L1 use case.
3. If retained, write an exact binary and stream contract in `l1/docs/specs/stdlib/iff-format.md`.
4. Define the smallest module surface and bounded follow-up implementation plans.
5. If not retained, update the roadmap with the explicit replacement, deferral, or removal rationale.

## Non-Goals

- implementing an ambiguous format
- treating `IFF` as a synonym for JSON
- adding a generic serialization framework without a concrete consumer
- building a separate file or buffering layer instead of using `std.stream` and `std.bytes`
- promising every historical IFF chunk dialect

## ADR Impact

- Decision: Select the exact IFF meaning, consumer, module ownership, and binary contract, or remove the item from the
  core stdlib roadmap.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: No correct API or implementation plan can be written until the roadmap acronym and motivating use case
    are identified.

## Verification Criteria

1. The conclusion cites a concrete consumer or recommends removal/deferral.
2. Any retained format has an exact byte-order, padding, nesting, unknown-chunk, and size contract.
3. Core-stdlib placement is justified against external-package or tooling ownership.
4. Follow-up plans are bounded and depend on the shared byte-buffer and stream foundations.
