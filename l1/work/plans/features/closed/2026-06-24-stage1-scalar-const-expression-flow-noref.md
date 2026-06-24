# Feature Plan

## Stage 1 scalar const-expression flow

- Date: 2026-06-24
- Status: Completed
- Title: Stage 1 scalar const-expression flow
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Signature resolution / const evaluation / expression typing / backend / interfaces / docs
- Modules:
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/specs/compiler/module-interface-format.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_toplet_test.py`
  - `l1/compiler/stage1_l0/tests/fixtures/typing/typing_const_bool_flow_err.l1`
  - `l1/compiler/stage1_l0/tests/fixtures/typing/typing_const_bool_flow_ok.l1`
  - `l1/compiler/stage1_l0/tests/fixtures/typing/typing_const_expr_err.l1`
- Related:
  - `l1/work/plans/features/closed/2026-06-17-stage1-const-value-grammar-contexts-noref.md`
  - `l1/work/plans/features/closed/2026-06-18-stage1-const-scalar-casts-noref.md`
  - `l1/docs/decisions/0016-compile-time-constant-value-contexts.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/specs/compiler/module-interface-format.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 TESTS="backend_test expr_types_test interface_test l1c_stage1_toplet_test.py"`

## Summary

Stage 1 now folds a bounded scalar expression subset inside top-level `const` declarations and threads those folded
values through every existing constant-value context. The implementation keeps direct array-bound and `case` arm syntax
restricted to literals and visible `const` references, while referenced scalar constants may use checked 32-bit `int`
operators, short-circuit boolean operators, scalar equality/comparison, and already-supported scalar casts.

This plan records the scalar const-expression tranche that builds on the prior named-constant context work and
scalar-cast work. It is a separate lifecycle record because it changed semantic constant evaluation, interface emission,
backend static initializers, and boolean liveness flow.

## Completion Notes

1. `ConstValue` now folds unary `!`, unary `-`, bitwise `~`, checked 32-bit `int` arithmetic, non-negative bitwise and
   shift operators, scalar equality/comparison, and short-circuit `&&` / `||`.
2. Invalid arithmetic, overflow, invalid shifts, divide/modulo by zero, unsupported value families, and reachable
   non-constant operands remain non-evaluable instead of becoming compiler failures.
3. Folded scalar constants are used for top-level `const` static initializers, `.l1m` interface constants, resolved
   fixed-array lengths, and const-valued `case` arm checks.
4. Boolean liveness flow now treats compile-time-known `if`, `while`, and `for` conditions as reachable or unreachable
   when the condition is a visible top-level `const`, while local shadowing keeps the condition dynamic.
5. Dead branches skipped by const boolean flow still receive ordinary type checking diagnostics; only impossible
   liveness paths are suppressed.
6. Tests cover folded arithmetic in array bounds and `case` arms, static initializer lowering, interface emission,
   invalid arithmetic diagnostics, short-circuit reachability, local shadowing, and narrowed bitwise values.

## Defaults Chosen

1. Arithmetic folding is limited to Dea's 32-bit `int` payloads. Bigint arithmetic, real arithmetic, string
   concatenation, aggregate operations, pointer/nullable operations, and general constexpr evaluation remain future
   work.
2. Bitwise `&`, `|`, `^`, `<<`, and `>>` fold only for non-negative 32-bit `int` payloads. Bitwise `~` uses the same
   32-bit `int` bounds and rejects the ordinary overflow case through non-evaluability.
3. `&&` and `||` short-circuit during const evaluation, so unreachable operands do not force a `SIG-0200` diagnostic.
   Reachable invalid operands still report the existing non-constant initializer diagnostic.
4. Interface output serializes accepted scalar const expressions as folded literals. Expression syntax is not preserved
   in `.l1m`.
5. No new diagnostic-code reservation was needed. The feature reuses `SIG-0200` for unsupported const initializers,
   `TYP-0700` for out-of-range compile-time integer values, `TYP-0815` through `TYP-0817` for array-bound contexts, and
   existing `case` value diagnostics.

## Implementation

1. Extend the shared const evaluator in [type-resolve] to fold supported unary and binary scalar expressions with
   checked 32-bit `int` helpers and short-circuit boolean evaluation.
2. Make [analysis] and [backend] consume the general folded scalar value path when emitting interface constants and
   static initializers, instead of recognizing only cast-shaped const expressions.
3. Teach [expr-types] to query compile-time boolean values for liveness reachability while preserving normal type
   diagnostics in skipped branches.
4. Update [grammar], [design-decisions], [interface-format], and [ADR-0016] so the stable docs and decision record match
   the shipped scalar subset.

## Verification Criteria

1. A named `const` such as `const WIDTH: int = (N + 1) * 2;` resolves to a concrete fixed-array length and can be used
   as a `case` arm value.
2. Folded scalar consts emit as static C literals and as folded `.l1m` literals, with no runtime helper calls for
   supported compile-time operations.
3. Divide/modulo by zero, overflow, invalid shifts, unsupported floating-point arithmetic, and reachable short-circuit
   operands report `SIG-0200`; narrowed integer values reuse `TYP-0700`.
4. Compile-time boolean flow removes impossible use-after-drop paths but keeps type errors in dead branches and treats
   local shadowing as dynamic.
5. Focused Stage 1 tests pass for backend lowering, expression typing, interface emission, and top-level const
   execution.

[adr-0016]: ../../../../docs/decisions/0016-compile-time-constant-value-contexts.md
[analysis]: ../../../../compiler/stage1_l0/src/analysis.l0
[backend]: ../../../../compiler/stage1_l0/src/backend.l0
[design-decisions]: ../../../../docs/reference/design-decisions.md
[expr-types]: ../../../../compiler/stage1_l0/src/expr_types.l0
[grammar]: ../../../../docs/reference/grammar.md
[interface-format]: ../../../../docs/specs/compiler/module-interface-format.md
[type-resolve]: ../../../../compiler/stage1_l0/src/type_resolve.l0
