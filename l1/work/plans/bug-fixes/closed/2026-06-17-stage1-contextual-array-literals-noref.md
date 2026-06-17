# Bug Fix Plan

## L1 Stage 1 contextual array literal checks

- Date: 2026-06-17
- Status: Completed
- Title: Check array literals against fixed-size typed contexts before standalone inference
- Kind: Bug Fix
- Severity: Medium
- Stage: 1
- Subsystem: Type checker / Reference docs
- Modules:
  - `compiler/stage1_l0/src/expr_types.l0`
  - `docs/reference/design-decisions.md`
  - `docs/reference/grammar.md`
  - `docs/roadmap.md`
- Test modules:
  - `compiler/stage1_l0/tests/expr_types_test.l0`
  - `compiler/stage1_l0/tests/fixtures/typing/typing_contextual_array_literals_ok.l1`
  - `compiler/stage1_l0/tests/fixtures/typing/typing_contextual_array_literals_err.l1`
- Related:
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - `l1/work/initiatives/closed/0004-array-primitives-and-unsafe-marker.md`
  - `l1/work/plans/features/2026-05-19-stage1-slices-len-slice-intrinsics-noref.md`
- Repro: `func f(a: int[3]) -> int { return a[0]; } func main() -> int { return f([1, 2, 3]); }`

## Summary

L1 Stage 1 currently accepts array literals in annotated local initializers and explicit array constructors, but many
other typed contexts infer the expression first. Because array literals have no standalone type, those contexts report
`TYP-0801` before they can use the expected fixed-size array type. The fix should route assignment-like typed contexts
through one helper that checks array literals against direct `T[N]` expectations before falling back to ordinary
expression inference and assignability.

## Current State

The current implementation special-cases only annotated local declarations such as `let xs: int[3] = [1, 2, 3];`.
Function call arguments, return expressions, assignment statements, struct fields, enum payload fields, and `new`
initializer arguments infer the right-hand expression first. That makes a fixed-array function argument like
`sum3([1, 2, 3])` fail even though the parameter gives an unambiguous `int[3]` context.

Slice contexts correctly do not materialize array literals today. A value of type `int[3]` can convert to `int[]` in
approved slice target contexts, but a bare `[1, 2, 3]` should still be rejected for an `int[]` parameter because there
is no fixed array value to borrow from.

## Scope of This Fix

1. Add a type-checker helper that checks an expression against an expected type.
2. Make the helper accept array literals only when the expected type is directly `TY_ARRAY`.
3. Keep non-array array-literal contexts rejected with `TYP-0801`.
4. Use the helper in assignment-like typed contexts: calls, constructors, `new`, returns, assignments, and annotated
   local initializers.
5. Keep array constructor argument checking separate so its literal-vs-fill broadcast behavior remains unchanged.
6. Update L1 reference docs to state that array literals are contextual, fixed-array-only expressions with no standalone
   type.

## Diagnostic Plan

No new diagnostic codes are needed. Reuse the existing array-literal diagnostics:

- `TYP-0801` for array literals without a direct fixed-size array context
- `TYP-0802` for too many literal elements for the target length
- `TYP-0803` for element type mismatches

The live diagnostic catalog already reserves these meanings, so no provisional code block is required.

## Non-Goals

1. Adding array-literal-to-slice materialization.
2. Accepting array literals through nullable array contexts such as `int[3]?`.
3. Changing array constructor broadcast/fill semantics.
4. Changing generated C for already accepted array literals.

## Tests

Add Stage 1 typing fixture coverage for:

1. Fixed-array function arguments.
2. Nested fixed-array function arguments.
3. Short literal padding through a function argument.
4. Array literals in at least one non-call typed context.
5. Overlong literals reporting `TYP-0802`.
6. Element mismatches reporting `TYP-0803`.
7. Standalone `let a = [1, 2, 3]` reporting `TYP-0801`.
8. Slice parameter calls such as `g([1, 2, 3])` still reporting `TYP-0801`.

## Verification Criteria

Run from `l1/`:

```bash
make test-stage1
make test-stage1-trace
make check-examples
```

Run `make test-all` as well if the focused validation leaves enough time.
