# Feature Plan

## Catch L2 up with the stable L1 baseline

- Date: 2026-10-27
- Status: Draft
- Title: Catch L2 up with stable L1 compiler and standard-library work before sustained L2 development
- Kind: Feature
- Priority: Low
- Subsystem: Compiler / stdlib / runtime / bootstrap / validation
- Modules:
  - `l2/compiler/src/`
  - `l2/compiler/shared/l2/stdlib/`
  - `l2/compiler/shared/runtime/`
  - `l2/compiler/support/`
  - `l2/scripts/`
  - `l2/Makefile`
  - `l2/docs/`
- Test modules:
  - `l2/compiler/tests/`
  - `l2/tests/`
- Related:
  - [l2/docs/decisions/0001-independent-canonical-compiler.md][independent-compiler]
  - [l2/docs/roadmap.md][roadmap]

## Summary and activation gate

Perform one bounded source and behavior catch-up from the accepted stable L1 baseline into L2 before sustained L2
feature development begins. This is deferred work: start only after the project maintainer declares L1 stable, selects
its named release or dated baseline, and explicitly starts the L2 development phase. Its current readiness is
`not-ready`; low priority reflects that future activation gate.

The virtual rebase means reviewing and porting the accumulated compiler, runtime, stdlib, support, and regression
changes into L2-owned sources while retaining L2's independent lineage and bootstrap contract. Preserve Git history.

## Approach

1. Inventory the stable L1 delta against L2, including compiler fixes/features, profiles and dependency discovery,
   stdlib additions, runtime support, and affected tooling/docs. Record each item as adopted, already present, or
   deliberately deferred with a reason; exclude unimplemented L1 drafts.
2. Port the selected behavior with `.l1` compiler implementation/tests, `.l2` target programs/stdlib, `.l2m` interfaces,
   L2 configuration and driver names, and physically L2-owned support. Preserve the explicit installed L1 construction
   dependency and existing opt-in development mode. Resolve target inputs entirely within L2.
3. Port meaningful regressions, adapt bootstrap/target-language fixtures, and refresh the L2 reference and roadmap.
   Account for native ABI/cache invalidation where the adopted baseline requires it. Complete this catch-up before the
   deferred string-slice and IFF plans are activated.

## Diagnostic-code planning

Inspect the live [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] at activation. Preserve shared code
meanings and corresponding L1C/L2C numeric identities. Reuse diagnostics delivered by the selected stable baseline; no
new diagnostic block is reserved by this draft. Independently new conditions require explicit planning against the live
catalog before assigning codes.

## ADR Impact

- Decision: Adopt the stable predecessor baseline while preserving L2-owned target inputs and explicit L1 construction.
  - Scope: L2
  - Disposition: Covered by ADR
  - ADR: `l2/docs/decisions/0001-independent-canonical-compiler.md`
  - Rationale: The catch-up preserves the accepted level ownership and bootstrap boundary. Record any independently new
    L2 architectural choice before implementing it; at closure link this plan from the existing ADR.

## Verification criteria

1. Every selected baseline item is reconciled, with representative compiler and stdlib behavior tested through L2-owned
   fixtures. Implementation tests exercise the selected L1 bootstrap; target fixtures execute under `l2c`.
2. Focused normal/trace tests and L2 `make test-ci` pass from rebuilt affected artifacts. Record actual compiler paths
   and versions, and obtain native Linux x86_64, macOS Intel/ARM, and Windows UCRT64 coverage.
3. With an explicit installed Linux-compatible L1 bootstrap, run opt-in `make test-isolation` and prove L2 build and
   target operation with sibling trees inaccessible. Retain independent target-runtime operation after construction.
4. Current docs, the delta inventory, and ADR links agree on the delivered baseline before closing the plan.

## Non-goals

No catch-up implementation now, perpetual source parity, L1 stabilization work, new L2 language features, string-slice
or IFF implementation, self-hosting, release productization, tags, remote writes, or publication.

[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[independent-compiler]: ../../../docs/decisions/0001-independent-canonical-compiler.md
[roadmap]: ../../../docs/roadmap.md
