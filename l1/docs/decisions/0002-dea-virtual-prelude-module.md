# ADR-0002: The `dea` Virtual Prelude Module

- Decision date: 2026-04-03
- Last edited: 2026-05-20
- Status: Accepted

## Context

L1 compilation units need access to built-in intrinsics (`sizeof`, `ord`, `is`) and language-level primitive names
without importing a specific source file. Placing intrinsics in a `std.*` module would conflate language primitives with
library APIs. Hard-coding bare intrinsic names into the compiler would prevent user code from defining functions named
`sizeof` or `ord`.

## Decision

The compiler synthesizes a virtual module named `dea` that is implicitly opened into every compilation unit:

- `dea` has no physical source file; it is constructed entirely by the compiler.
- `dea` is opened (not just available) automatically, so `sizeof`, `ord`, and `is` are available unqualified by default.
- `dea` has the lowest import precedence: user-defined locals and explicitly imported names shadow it normally.
- `dea::sizeof`, `dea::ord`, and `dea::is` are always available as qualified escape hatches when unqualified names are
  shadowed.
- Shadowing uses the normal name-resolution rules and warning behavior; there is no bespoke intrinsic-specific fallback.
- `dea::is(value, Variant)` compares enum tags only; it does not evaluate or synthesize payload values.
- The `dea` module leaves room for future compiler-owned type aliases and prelude-level symbols without introducing a
  synthetic source file.

## Rationale

- Putting intrinsics in a compiler-owned virtual module keeps them in the normal symbol/module system rather than
  special-casing bare keywords.
- Automatic opening avoids the boilerplate of importing `dea` in every file while still allowing qualified access for
  disambiguation.
- Lowest-precedence import ensures user code can shadow intrinsic names without compiler errors, which is important for
  library code that provides its own `sizeof`-like helpers.

## Consequences

- Every compilation unit implicitly has access to `sizeof`, `ord`, and `is` without an explicit import.
- The compiler must synthesize and register the `dea` module during name resolution before processing any user code.
- Future additions to the `dea` prelude are compiler-controlled and do not require source file changes.

## Related Plans

- [l1/work/plans/features/closed/2026-04-03-dea-virtual-module-noref.md][dea-plan]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §10 (The `dea` Prelude Module)

[dea-plan]: ../../work/plans/features/closed/2026-04-03-dea-virtual-module-noref.md
[design-decisions]: ../reference/design-decisions.md
