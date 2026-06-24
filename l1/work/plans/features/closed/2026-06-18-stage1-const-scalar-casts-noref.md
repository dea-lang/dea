# Feature Plan

## Compile-time scalar casts for `const`

- Date: 2026-06-18
- Status: Completed
- Title: Compile-time scalar casts for `const`
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Signature resolution / const evaluation / expression typing / backend / interfaces / docs
- Modules:
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/compiler/stage1_l0/src/signatures.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/analysis.l0`
- Test modules:
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_toplet_test.py`
- Related:
  - `l1/work/plans/features/closed/2026-04-18-l1-const-declarations-noref.md`
  - `l1/work/plans/features/closed/2026-06-17-stage1-const-value-grammar-contexts-noref.md`
  - `l1/docs/reference/design-decisions.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 TESTS="expr_types_test interface_test l1c_stage1_toplet_test.py"`

## Summary

L1 accepts explicit scalar casts in runtime expressions but rejects them in `const` initializers with `SIG-0200`, even
when the operand is another visible `const`. Extend the Stage 1 constant evaluator to fold integer-family casts,
`float`/`double` casts, and identity casts for `bool` and `string`, preserving exact static range checking and avoiding
dependent diagnostics after an invalid cast.

## Completion Notes

1. The shared constant evaluator now folds integer-family casts, `float`/`double` casts, and scalar identity casts while
   retaining precise invalid-cast state.
2. Integer casts use 32-bit `int`-backed or bigint-backed range checks and emit one `TYP-0700` without `SIG-0200` or
   array-bound cascades; excluded and non-constant cast operands retain `SIG-0200`.
3. Top-level initializers, named `case` arms, and exported interfaces lower supported casts to target-typed literals;
   generated code does not call runtime checked-cast helpers for folded const values.
4. Tests cover every integer target family, signed/unsigned boundaries, bigint values, aliases, nested/parenthesized
   casts, real casts, scalar identities, array bounds, case arms, interface round trips, and end-to-end execution.
5. Grammar, design-decision, ADR, roadmap, and diagnostic-catalog documentation now describe the shipped subset.

## Defaults Chosen

1. Integer casts cover `tiny`, `byte`, `short`, `ushort`, `int`, `uint`, `long`, and `ulong`; out-of-range values emit
   `TYP-0700` and never wrap.
2. Real casts cover only `float` to/from `double`. Integer/real casts, nullable casts, pointers, aggregates, and general
   constant arithmetic remain outside the constant-expression subset.
3. `bool` and `string` support identity casts only.
4. Exported cast constants serialize as folded target-typed literals rather than retaining cast syntax in `.l1m`.
5. `TYP-0700` is reused and broadened from literal-only wording to compile-time integer values; no new diagnostic code
   is introduced.

## Implementation

1. Add cast evaluation and explicit invalid-cast state to the reusable `ConstValue` evaluator, including 32-bit
   `int`-backed and bigint-backed range checks and target-normalized real spellings.
2. Make signature resolution recognize valid folded casts, retain `SIG-0200` for non-constant or excluded operands, and
   suppress `SIG-0200`/array-bound cascades after a precise cast diagnostic.
3. Lower supported const casts to static literals and emit folded literals in module interfaces.
4. Update grammar, design-decision, ADR, roadmap, and diagnostic-catalog documentation for the shipped subset.

## Verification Criteria

1. `const Z: ulong = 25; const I: int = Z as int;` checks, runs, and can supply an array bound and case arm.
2. All integer types, boundary values, bigint-backed values, nested/parenthesized casts, real casts, and scalar identity
   casts have positive coverage.
3. Invalid narrowing produces exactly one `TYP-0700`; non-constant and excluded casts remain `SIG-0200`.
4. Exported/imported cast constants round-trip through `.l1m`, and generated C contains no runtime cast helper for a
   folded const cast.
5. Focused tests, full Stage 1 tests, trace tests, examples, and documentation checks pass.
