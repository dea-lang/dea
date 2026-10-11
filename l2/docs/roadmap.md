# Dea/L2 Roadmap

Version: 2026-10-11

L2 establishes an independent canonical compiler implemented in L1, with owned `.l2` stdlib/runtime inputs and `.l2m`
interfaces. The initial milestone passed native compiler CI on all four platforms and two-phase Linux isolation with
sibling trees inaccessible and an explicitly installed L1 bootstrap toolchain.

## Completed shared milestone

- [work/plans/refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md](../../work/plans/refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md):
  completed the canonical split, independent ownership, coordinated development reuse, and optional isolation.

## Future placement

Feature plans remain L1-owned until individually reassigned. Explicit profiles/composable builds are intended for L1
first and later carried forward to L2; this split neither advances that work nor depends on it. New L2 capabilities,
self-hosting, and release productization are not part of this milestone.
