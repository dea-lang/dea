# ADR-0011: C Emission Strategy

- Decision date: 2026-01-21
- Last edited: 2026-05-20
- Status: Accepted

## Context

The L0 backend emits C source code. As the backend grew, C-specific emission details were being handled in both the
semantic backend layer and the C emitter layer. This created coupling and made it hard to reason about what was a
language-level decision versus a C-specific rendering detail.

A separate question was whether the emitted C should be conservative-safe (no pedantic warnings, no GCC/clang
extensions) or whether using extensions would simplify the output.

## Decision

Two principles govern C emission:

1. **Backend/emitter separation**: semantic lowering decisions (what value to compute, what ownership action to take)
   belong in the backend. C rendering details (how to spell a type, how to format an expression, what C syntax encodes a
   given action) belong in the `CEmitter`. The backend passes abstract operations to the emitter; the emitter owns all C
   fragment generation.

2. **Pedantic-clean C99**: the emitted C must be warning-free under `-Wall -Wextra` and must not produce warnings under
   `-Wpedantic` or clang's `-Wparentheses-equality`. No nonstandard attributes, no `__builtin_*`, no GCC-only syntax.
   Same-type casts are avoided to prevent `-Wpedantic` warnings from `clang -Wpedantic`.

## Rationale

- The backend/emitter boundary makes it possible to reason about semantic correctness separately from C rendering
  correctness.
- Pedantic-clean C means the generated code works unchanged across GCC, clang, TinyCC, and MSVC without
  conditional-compilation guards.
- Warning-free output also means users' own compiler warning flags do not produce noise from compiler-generated code.

## Consequences

- Any new emission pattern must go through `CEmitter` helper methods, not directly into the backend's output buffer.
- Before adding a C construct, verify it is accepted by TinyCC, GCC, clang, and in MSVC mode where applicable.

## Related Plans

- [l0/work/plans/refactors/closed/2026-03-22-backend-emitter-boundary-cleanup-noref.md](../../work/plans/refactors/closed/2026-03-22-backend-emitter-boundary-cleanup-noref.md):
  moved backend-owned C fragments behind emitter helpers
- [work/plans/bug-fixes/closed/2026-04-29-shared-cleaner-c-condition-expressions-noref.md](../../../work/plans/bug-fixes/closed/2026-04-29-shared-cleaner-c-condition-expressions-noref.md):
  suppressed `-Wparentheses-equality` by cleaner condition expressions
- [work/plans/bug-fixes/closed/2026-04-29-shared-nonscalar-same-type-cast-c99-pedantic-noref.md](../../../work/plans/bug-fixes/closed/2026-04-29-shared-nonscalar-same-type-cast-c99-pedantic-noref.md):
  avoided self-casts that trigger `-Wpedantic`
- [l0/work/plans/bug-fixes/closed/2026-03-13-linux-c99-compatibility-noref.md](../../work/plans/bug-fixes/closed/2026-03-13-linux-c99-compatibility-noref.md):
  Linux and strict C99 compatibility fixes

## Current Docs

- [l0/docs/reference/c-backend-design.md](../reference/c-backend-design.md): C emission strategy, lowering rules,
  fragment organization
- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §8 (toolchain and portability policy)
