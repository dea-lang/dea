# Feature Plan

## Add L1 function pointer types

- Date: 2026-04-18
- Status: Completed
- Title: Add L1 function pointer types
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Parser / type system / expression typing / C emitter / ABI
- Modules:
  - `l1/compiler/stage1_l0/src/ast.l0`
  - `l1/compiler/stage1_l0/src/parser/shared.l0`
  - `l1/compiler/stage1_l0/src/parser/decl.l0`
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/compiler/stage1_l0/src/types.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/type_resolve_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/work/initiatives/0003-c-ffi.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 TESTS="parser_test expr_types_test"`

## Summary

This completed plan introduced first-class function pointer type syntax, typing, C typedef emission, indirect calls, and
runtime coverage. Functions can now be stored, passed, compared by identity when signatures match, and called
indirectly, giving Initiative 0003 a typed callback surface for later C FFI work.

## Completion Notes

1. Function pointer types use `func(T1, T2) -> U` syntax and `(func(...) -> U)?` for nullable function pointers.
2. C typedefs use the `dea_func_` prefix with signature-derived names such as `dea_func_int_int_int`.
3. Indirect calls through function pointer values include a runtime null check before dispatch.
4. No new diagnostic codes were registered; existing type mismatch and call diagnostics cover the rejected cases added
   by this plan.
5. ARC trace validation caught an owned type leak in function-pointer call typing, which was fixed before closing the
   plan.

## Current State

1. The parser accepts `func` declarations and call expressions, but there is no `func(T, ...) -> U` type syntax in
   `parser/types.l0` and no corresponding AST type node.
2. Taking a function's name as a value is not expressible; there is no decay rule from function symbol to function
   pointer.
3. The C emitter generates direct calls to named C functions; there is no indirect-call codegen path.
4. `sys.unsafe` and the existing `dea_*` ABI do not currently surface any function-pointer types at the ABI boundary.
5. Initiative 0003 expects a typed function pointer surface for C callback interop; this plan is the dedicated
   language-core feature that the initiative's FFI phases can rely on.

## Defaults Chosen

1. Type syntax is `func(T1, T2, ...) -> U`, mirroring existing function-definition syntax without body.
2. A zero-argument function type is `func() -> U`. `void` remains the spelling for "no result" consistent with existing
   return types.
3. Function pointer types are always pointer-valued; there is no separate "function type" vs "pointer to function"
   distinction at the language level.
4. Function pointer types are nullable only when declared with the existing `?` nullability marker. Because the bare
   form `func(...) -> U?` already binds `?` to the return type (nullable `U`), a nullable function pointer is spelled
   with explicit parentheses: `(func(...) -> U)?`. Calling a null function pointer is a runtime error, not silent
   undefined behavior.
5. Two function pointer types are compatible only if their argument arity, argument types, and return type match
   exactly. Variance is not introduced in this plan.
6. Taking the value of a top-level function by bare name produces a function-pointer expression whose type is the
   function's signature. Overloaded names are not in scope because L1 has no overload resolution today.
7. Lambdas and closures are out of scope for this plan; integration with a future closure type is a follow-up.
8. The C ABI representation is a plain C function pointer (`U (*)(T1, T2, ...)`), consistent with the `dea_*` ABI policy
   for public names.

## Goal

1. Parse and represent function pointer types in the type system.
2. Type-check function-pointer values, calls, and equality/nullability.
3. Emit function pointer values, indirect calls, and type aliases/typedefs in the C backend.
4. Provide a clean handoff to Initiative 0003 so C FFI can expose and consume callback types without further language
   changes.

## Implementation Phases

### Phase 1: Type syntax

Extend `parser/types.l0` with a `func(...) -> T` type parser. Add a corresponding AST type node (`TY_FUNC_PTR` or
equivalent) carrying parameter types, return type, and nullability. Lock the spelling in
`l1/docs/reference/design-decisions.md` so later features do not drift.

### Phase 2: Values and typing

Introduce a function-name-as-value expression form (bare identifier resolving to a top-level function). In
`expr_types.l0`:

- resolve bare-name references to function-pointer values where the context expects one
- accept call expressions whose callee has function-pointer type, typing them as indirect calls
- reject mismatched signatures with dedicated diagnostics
- keep direct-call codegen for the common `name(args)` case where the callee is a statically known function

Register any new diagnostic codes in `docs/specs/compiler/diagnostic-code-catalog.md` before landing code.

### Phase 3: Nullability and comparison

Support `(func(...) -> T)?` as a nullable function pointer, disambiguated from `func(...) -> T?` (a non-nullable
function pointer returning a nullable `T`) by the explicit parentheses. Support equality comparison against `null` and
between two same-signature function pointers. Reject ordering comparisons.

### Phase 4: Backend and C emission

In `backend.l0` / `c_emitter.l0`:

- emit a `typedef U (*dea_<mangled>)(T1, T2, ...);` for each distinct function pointer signature used in a module
- lower function-name-as-value expressions to `&<c_name>` where needed or rely on C's implicit decay, whichever the
  current emitter style prefers
- lower indirect calls to `(*fp)(args)` or `fp(args)` consistent with existing style
- emit a runtime null-check for non-nullable function pointers at call sites where the compiler cannot prove
  non-nullability, matching the existing pointer-null policy

### Phase 5: FFI handoff

Coordinate with Initiative `0003-c-ffi` on which phase of the initiative will first consume this surface. Do not
implement FFI-specific plumbing in this plan; only leave a clean landing surface.

### Phase 6: Regression coverage

Add tests in:

- `parser_test.l0` — valid and invalid function pointer type syntax, including zero-args, nullable, and nested
  (pointer-to-function-returning-function-pointer) forms
- `expr_types_test.l0` — acceptance/rejection of assignment, calls, null checks, signature mismatch
- `l0c_lib_test.l0` — end-to-end dispatch-table fixture exercising stored function pointers at runtime

## Non-Goals

- lambdas or closures (tracked as a separate backlog item)
- function overloading or overload-resolution rules
- variance or subtyping between function pointer types
- typed method pointers, bound receivers, or trait-object-style dispatch
- C variadic function pointers (tracked under the varargs backlog item)
- full FFI surface (owned by Initiative 0003)

## Verification Criteria

1. `make -C l1 test-stage1 TESTS="parser_test expr_types_test"` passes with new coverage.
2. `make -C l1 test-stage1 TESTS="l0c_lib_test"` passes with a runtime dispatch-table fixture.
3. `make -C l1 test-stage1` and `make -C l1 check-examples` both pass.
4. Generated C for a function pointer-using module contains a `typedef` per distinct signature and indirect-call syntax
   at call sites.
5. Any newly registered diagnostic codes appear in `docs/specs/compiler/diagnostic-code-catalog.md`.
6. `l1/docs/reference/design-decisions.md` records the function pointer type syntax and ABI choice.

## Final Validation

- `make -C l1 test-stage1 TESTS="parser_test expr_types_test"`
- `make -C l1 test-stage1 TESTS="l0c_lib_test"`
- `make -C l1 test-stage1`
- `make -C l1 check-examples`
- `make -C l1 test-stage1-trace TESTS="expr_types_test l0c_lib_test"`
- `make -C l1 test-stage1-trace`
- `make clean test-all`
