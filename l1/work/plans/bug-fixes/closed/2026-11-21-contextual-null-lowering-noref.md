# Bug Fix Plan

## Preserve the target type of null in expressions and allocations

- Date: 2026-11-25
- Status: Completed
- Title: Preserve the target type of null in expressions and allocations
- Kind: Bug Fix
- Severity: Medium
- Subsystem: Expected-type lowering and single-value allocation initialization
- Modules:
  - `l1/compiler/src/backend/lower.l0`
  - `l1/compiler/src/backend/expr.l0`
- Test modules:
  - `l1/compiler/tests/expr_types_test.l0`
  - `l1/compiler/tests/backend_test.l0`
  - `l1/compiler/tests/l1c_build_run_multi_cu_test.py`
- Related:
  - [l1/docs/reference/design-decisions.md][nullability]
  - [l1/docs/decisions/0012-ordered-type-suffix-constructors.md][suffixes]
  - [l0/work/plans/bug-fixes/closed/2026-11-21-stage1-nullable-conversions-and-ownership-noref.md][l0-nullable]
- Repro: Pass `(null)` to an `int?` parameter or use `new S((null))` with `type S = string?;`. Before the fix, checking
  succeeded and generation failed with `ICE-1292`.

## Findings and implementation

Borrowed and owned expression lowering now inspect the literal inside grouping parentheses and use the complete
destination type to emit absence. Parenthesized places still use their original expression for ownership analysis.
Comparisons recognize a grouped null on either side. Explicit nullable casts supply the cast target, and positional
calls through function pointers supply the declared parameter types.

Single-value allocation already passed its resolved pointee type to the owned initializer after the numeric widening
work in [work/plans/features/2026-11-25-shared-nullable-numeric-widening-noref.md][widening]. Direct `new S(null)`
worked before this fix. The native regression covers direct, grouped and typed absent initializers and checks that an
initializer with a side effect executes once.

## ADR Impact

- Decision: Propagate the established nullable destination to literal emission and single-value allocation.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The checker accepts the affected expressions and the destination representations already exist. The
    repair uses the established rules for absence and borrowed arguments.

## Verification

On macOS x86_64 with Apple Clang 17, all three focused modules passed from `l1/`:

```sh
make test-compiler TESTS="expr_types_test backend_test l1c_build_run_multi_cu_test"
```

- The native fixture reads `string?` and `int*?` slots before dropping them. Generated C uses an unset `has_value` for
  `int?` and `int??` destinations and `NULL` for an `int*?` destination. Direct and indirect calls distinguish an absent
  integer from a present zero.
- A parenthesized string local copied into an optional survives reassignment of the source. With `--trace-arc` and
  `--trace-memory`, the fixture recorded seven allocations and seven drops of heap slots. Trace triage reported zero
  errors and zero leaked strings or objects. The existing variadic-call fixture also executed successfully.
- Both `let value = null;` and `let value = ((null));` still report `TYP-0052` during analysis.

[l0-nullable]: ../../../../../l0/work/plans/bug-fixes/closed/2026-11-21-stage1-nullable-conversions-and-ownership-noref.md
[nullability]: ../../../../docs/reference/design-decisions.md
[suffixes]: ../../../../docs/decisions/0012-ordered-type-suffix-constructors.md
[widening]: ../../../../../work/plans/features/2026-11-25-shared-nullable-numeric-widening-noref.md
