# ADR-0040: Warm Preparation Reuses Completed-Profile Semantic Validation

- Decision date: 2026-09-15
- Last edited: 2026-09-15
- Status: Accepted

## Context

Every native preparation command validated the complete bundled semantic interface graph through a generated umbrella
module, including modules no other bundled source imports. The full pass was an explicit contract established by
ADR-0038, and it ran before native profile lookup, so warm cache hits still paid the complete analysis. Phase
measurements on an Intel Mac attributed about 0.9 seconds per warm command to preparation beyond an explicit-input
floor, while native work was already skipped on hits. The investigation recorded in the closed warm-preparation
validation reuse plan audited the pass inputs, probed falsification cases, and measured a warm-skip prototype under a
pre-registered acceptance bar.

## Decision

The completion manifest is the reusable success record for semantic validation. A valid warm native profile hit, where
the existing profile validation already proves complete identity equality, `D` equality, artifact inventory, semantic
copies and containment, certifies that the current validator completed the full bundled validation over the current
selected inputs. The command returns the hit without repeating the umbrella analysis.

Only the warm-hit return may skip the pass. Cold construction, misses, unusable profiles, `--no-auto-prepare`
classification, force revalidation, private fallback and interrupted publications keep the complete pass and their
existing diagnostic behavior. No new persistent state, memo authority or store is introduced. Any input change alters
`D`, so the pass runs again before any new reuse success; warnings and failure diagnostics therefore cannot be skipped.

## Rationale

The pass is a pure function of the validator image and the content-hashed compiler-owned inputs, and `D` binds both.
Probe coverage showed removal, edit and restoration invalidation, manifest structural attacks, torn publication,
interruption and concurrency all fall back to full validation or existing classification without a counterexample. The
pre-registered bar measured the prototype at 0.269 seconds against a 0.36 second target with non-overlapping ranges over
seven interleaved pairs, so the reuse win justifies the contract change without adding a second semantic store or
inspectable provenance beyond the manifest itself.

## Consequences

- Warm-hit consumer and preparation commands perform zero `_dea_preparation` analyses; miss and construction paths still
  perform exactly one.
- The capability reporter and preparation integration tests assert zeros on warm hits and ones on cold, miss and rebuild
  paths.
- Corrupt completed profiles keep their consumer classification (`L1C-2159` with force and external-serialization
  guidance) and explicit-mode `L1C-2153`, distinct from any disposable evidence failure.
- Unsound skip experiments are rejected by design: the only legal skip is the manifest-certified warm hit.
- Trace-measurement budget evidence remains implementation-time CI data; the native identity reassessment recorded in
  the closed plan (raw `PATH` text membership in `N`) is unchanged by this decision.

## Related Plans

- [l1/work/plans/features/closed/2026-09-13-warm-preparation-validation-reuse-noref.md][warm-plan]
- [l1/work/plans/tools/closed/2026-09-13-preparation-test-cost-noref.md][test-cost]

## Current Docs

- [l1/docs/reference/stdlib-preparation.md][preparation]

[preparation]: ../reference/stdlib-preparation.md
[test-cost]: ../../work/plans/tools/closed/2026-09-13-preparation-test-cost-noref.md
[warm-plan]: ../../work/plans/features/closed/2026-09-13-warm-preparation-validation-reuse-noref.md
