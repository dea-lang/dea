# ADR-0016: Compile-Time Constant Value Contexts

- Decision date: 2026-06-18
- Last edited: 2026-06-18
- Status: Accepted

## Context

L1 already had top-level `const` declarations and fixed-size arrays, but grammar contexts that required a constant value
still accepted only literals. This made configuration-style constants unusable in array bounds and `case` arms even when
their values were compile-time known.

## Decision

L1 has explicit compile-time constant value contexts:

- Fixed-size array suffixes accept `T[N]`, where `N` is a positive compile-time `int` constant expression.
- `case` arm values accept compile-time scalar, string, and bool constant expressions comparable with the scrutinee.
- The bootstrap source subset is literals plus visible top-level `const` references, including qualified references.
- Constant references are evaluated semantically, with recursive const-reference evaluation and cycle diagnostics.
- A referenced `const` declaration's explicit type annotation is authoritative for value-context classification.
- Array lengths resolve to concrete integer values before type lowering, signatures, interface emission, or backend
  work.
- Arithmetic and general constexpr operators remain future work.

## Rationale

- Separating source syntax from semantic constant evaluation allows the parser to accept the intended grammar without
  resolving names during parsing.
- Keeping the initial expression subset narrow preserves deterministic bootstrap behavior while leaving room for future
  pure compile-time operators.
- Treating the declaration annotation as authoritative keeps `const N: uint = 3;` distinct from `const N: int = 3;` in
  contexts that require exactly `int`.
- Resolving lengths to concrete values avoids symbolic array bounds in generated ABI and interface surfaces.

## Consequences

- Named constants can be used for fixed-size array bounds and scalar `case` arms.
- Non-const names, aggregate constants, non-`int` array bounds, non-positive array bounds, and const cycles are semantic
  diagnostics rather than parse errors when their source syntax is valid.
- Duplicate `case` arms are detected after constant evaluation, so two different names with the same value conflict.

## Related Plans

- [l1/work/plans/features/closed/2026-06-17-stage1-const-value-grammar-contexts-noref.md][const-contexts]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §7.1 (fixed-size array policy) and §17 (top-level `const`
  and `let`)
- [l1/docs/reference/grammar.md][grammar]: array suffix and `case` arm value grammar
- [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]: constant-value-context diagnostics

[const-contexts]: ../../work/plans/features/closed/2026-06-17-stage1-const-value-grammar-contexts-noref.md
[design-decisions]: ../reference/design-decisions.md
[diagnostics]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[grammar]: ../reference/grammar.md
