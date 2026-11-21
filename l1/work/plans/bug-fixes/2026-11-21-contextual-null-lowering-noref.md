# Bug Fix Plan

## Preserve the target type of null in expressions and allocations

- Date: 2026-11-21
- Status: Draft
- Title: Preserve the target type of null in expressions and allocations
- Kind: Bug Fix
- Severity: Medium
- Subsystem: Expected-type lowering and single-value allocation initialization
- Modules:
  - `l1/compiler/src/backend/lower.l0`
  - `l1/compiler/src/backend/coerce.l0`
- Test modules:
  - `l1/compiler/tests/expr_types_test.l0`
  - `l1/compiler/tests/backend_test.l0`
  - `l1/compiler/tests/l1c_build_run_multi_cu_test.py`
- Related:
  - [l1/docs/reference/design-decisions.md][nullability]
  - [l1/docs/decisions/0012-ordered-type-suffix-constructors.md][suffixes]
  - [l0/work/plans/bug-fixes/2026-11-21-stage1-nullable-conversions-and-ownership-noref.md][l0-nullable]
- Repro: Pass `(null)` to an `int?` parameter, initialize an `int?` local with `((null))`, or declare
  `type S = string?;` and evaluate `new S(null)`. Compare `l1c --check` with `l1c --gen` or `l1c --run`.

## Summary

All three forms pass analysis. Generation aborts with `ICE-1292` because the emitter sees the standalone null type where
it needs the destination representation. A direct `f(null)` call works. The allocation also works when its initializer
is a typed absent local. These workarounds narrow the impact, but ordinary accepted programs abort.

## ADR Impact

- Decision: Propagate the established nullable destination to literal emission and single-value allocation.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The checker accepts all affected expressions and their destination representations already exist. The
    repair supplies the type at the two lowering sites that lose it.

## Fix and regression criteria

1. In borrowed and owned expected-type emission, recognize a null literal through any number of parentheses. Use the
   complete expected type to construct the absent value. Retain existing handling of parenthesized places and their ARC
   ownership.
2. In the single-value path of `be_emit_new_expr`, use the resolved pointee as the expected type of the owned
   initializer. Evaluate the initializer once. Keep struct, enum and array initialization on their specialized paths.
3. Compile and run `f(null)`, `f((null))`, and a typed local initialized with nested parentheses. Check absence at
   runtime. For the allocation, compare `new S(null)`, `new S((null))` and `new S(empty)` with a typed absent `empty`.
   Read the allocated slot and check absence before dropping the object. Exercise both a value optional and an optional
   pointer, whose C representations differ. An untyped null with no destination must still get its existing semantic
   diagnostic.

From `l1/`, run `make test-compiler TESTS="expr_types_test backend_test l1c_build_run_multi_cu_test"`. Check both
generated C and the executed result. Optional-to-optional numeric widening is a separate conversion-policy decision.

[l0-nullable]: ../../../../l0/work/plans/bug-fixes/2026-11-21-stage1-nullable-conversions-and-ownership-noref.md
[nullability]: ../../../docs/reference/design-decisions.md
[suffixes]: ../../../docs/decisions/0012-ordered-type-suffix-constructors.md
