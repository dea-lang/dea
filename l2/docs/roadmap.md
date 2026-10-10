# Dea/L2 Roadmap

Version: 2026-10-10

L2 establishes an independent canonical compiler implemented in L1, with owned `.l2` stdlib/runtime inputs and `.l2m`
interfaces. The first milestone is successful build, representative language and separate-compilation tests, and actual
isolation with sibling trees inaccessible and an explicitly installed L1 bootstrap toolchain.

## Active shared work

- [2026-10-10-shared-l1-l2-canonical-compiler-split-noref](../../work/plans/refactors/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md):
  canonical split, independent ownership, and validation. No duplicate L2 implementation plan is opened.

## Future placement

Feature plans remain L1-owned until individually reassigned. Explicit profiles/composable builds are intended for L1
first and later carried forward to L2; this split neither advances that work nor depends on it. New L2 capabilities,
self-hosting, and release productization are not part of this milestone.
