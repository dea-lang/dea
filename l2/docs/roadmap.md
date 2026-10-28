# Dea/L2 Roadmap

Version: 2026-10-27

L2 establishes an independent canonical compiler implemented in L1, with owned `.l2` stdlib/runtime inputs and `.l2m`
interfaces. The initial milestone passed native compiler CI on all four platforms and two-phase Linux isolation with
sibling trees inaccessible and an explicitly installed L1 bootstrap toolchain.

## Completed shared milestone

- [work/plans/refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md](../../work/plans/refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md):
  completed the canonical split, independent ownership, coordinated development reuse, and optional isolation.

## Deferred development phase

Sustained L2 feature work has not started. Begin only after L1 is declared stable, a named stable release or dated
baseline is selected, and the project maintainer explicitly starts the L2 phase. First reconcile the accumulated L1
compiler, stdlib, runtime, support, and regression work through the catch-up plan below. Preserve L2-owned target inputs
and the explicit L1 construction dependency.

## Active standalone plans

These plans remain Draft and are scheduled after that activation gate. Readiness uses `ready`, `almost-ready`,
`not-ready`, and `speculative` as defined in the L1 [roadmap][l1-roadmap]; it is independent of lifecycle status.

| Readiness   | Plan                                                         | Activation or design gate                                                                         |
| ----------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| not-ready   | [2026-10-27-stable-l1-catch-up-noref][catch-up]              | Stable L1 baseline and explicit start of sustained L2 development.                                |
| not-ready   | [2026-06-21-cheap-string-slices-noref][string-slices]        | Complete catch-up, recheck the target-runtime inventory, and activate the optional optimization.  |
| speculative | [2026-08-30-iff-scope-and-format-selection-noref][iff-scope] | Complete catch-up and identify an exact format, concrete L2 consumer, and justified module scope. |

## Future placement

Other feature plans remain L1-owned until individually reassigned. Stable-L1 catch-up covers accepted predecessor
behavior, including delivered profiles/composable builds and stdlib work; it does not automatically adopt unimplemented
drafts. String slices and IFF are now L2-only plans and do not gate L1 stability. Self-hosting and release
productization remain separate future work.

[catch-up]: ../work/plans/features/2026-10-27-stable-l1-catch-up-noref.md
[iff-scope]: ../work/plans/features/2026-08-30-iff-scope-and-format-selection-noref.md
[l1-roadmap]: ../../l1/docs/roadmap.md#open-plan-readiness
[string-slices]: ../work/plans/features/2026-06-21-cheap-string-slices-noref.md
