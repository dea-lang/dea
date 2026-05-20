# ADR-0006: Const Declarations

- Decision date: 2026-04-18
- Last edited: 2026-05-20
- Status: Accepted

## Context

L1 already had top-level `let` for mutable global variables. A separate form was needed for compile-time-known constants
that should be immutable and whose initializers must be evaluable without a runtime.

## Decision

Top-level `const` is a distinct declaration form from `let`:

- `const NAME: T = EXPR;`: immutable, compile-time-constant initializer required.
- `let NAME [: T] = EXPR;`: mutable, may have runtime initializer.

`const` rules:

- An explicit type annotation is required.
- Initializers must be literals, `null`, bare zero-argument enum variants, or constructor calls whose arguments are
  themselves constant.
- `const` lowers to `static const` in generated C under the `dea_*` ABI naming scheme.
- Assignment to a `const` binding (including through a value-typed field) is a compile-time error.
- Block-local `const` is deferred; only top-level `const` is currently accepted.

## Rationale

- Requiring an explicit type avoids depending on a type inference pass over constant expressions, which is not a current
  priority.
- Restricting initializers to a decidable static subset keeps the accepted constant subset deterministic during the
  bootstrap phase.
- A separate `const` form (rather than a `let` modifier) makes immutability explicit in the declaration spelling and in
  generated code.

## Consequences

- Code using `const` for configuration values and flags gets `static const` in generated C, allowing downstream C
  compilers to optimize uses.
- The static initializer subset can be expanded incrementally as the bootstrap compiler matures.

## Related Plans

- [l1/work/plans/features/closed/2026-04-18-l1-const-declarations-noref.md][const-decls]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §17 (top-level `const` and `let`)

[const-decls]: ../../work/plans/features/closed/2026-04-18-l1-const-declarations-noref.md
[design-decisions]: ../reference/design-decisions.md
