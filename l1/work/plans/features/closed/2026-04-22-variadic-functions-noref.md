# Feature Plan

## Add L1 variadic functions

- Date: 2026-04-22
- Status: Completed
- Title: Add L1 variadic functions
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Parser / typing / backend / ABI / docs
- Modules:
  - `l1/compiler/stage1_l0/src/ast.l0`
  - `l1/compiler/stage1_l0/src/parser.l0`
  - `l1/compiler/stage1_l0/src/types.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/work/initiatives/0003-c-ffi.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 && make -C l1 test-stage1-trace`

## Summary

The roadmap currently groups two different concerns under "Varargs": language-level variadic functions written in L1,
and C variadic FFI at the `extern func` boundary. This plan intentionally covers only the first half: defining, calling,
and lowering L1 variadic functions. C variadic FFI remains part of Initiative `0003-c-ffi`.

This split keeps the language-core work reviewable and avoids entangling pack semantics with FFI-safe type rules,
calling-convention edge cases, and `va_list`-style C interop. The standalone plan should leave a clean handoff to the
FFI initiative rather than pre-committing its boundary rules.

## Deferral Resolution

The prerequisite slice feature landed before implementation. Variadic parameters now resolve to the existing `T[]`
descriptor surface, avoiding a bespoke pack type and any C varargs dependency. Ordinary calls materialize caller-owned
fixed-array packs; explicit final `pack...` calls forward existing compatible slice or fixed-array storage.

The earlier deferral did not block C variadic FFI: that work is a separate sibling tranche under Initiative 0003 with
its own `va_list` companion-function workaround (see "C variadic FFI scope" in
[l1/work/initiatives/0003-c-ffi.md](../../../initiatives/0003-c-ffi.md)).

## Pre-Implementation State

1. Function declarations, function types, and calls in L1 all assume a fixed arity.
2. `expr_types.l0` enforces exact argument counts for direct calls and constructor-like call surfaces.
3. The function-pointer feature established a fixed-signature type model and explicitly left C variadic function
   pointers out of scope.
4. The FFI initiative owns `extern func` evolution and is the right home for C variadic interop.

## Defaults Chosen

1. This plan adds only L1-defined variadic functions and matching L1 function-pointer types. It does not add variadic
   `extern func` declarations or any C ABI varargs rule.
2. A variadic parameter is a single trailing parameter. There is never more than one variadic parameter in a signature.
3. The working syntax default is a trailing `...` on the final parameter type, spelled `name: T...`, with the same shape
   mirrored in function-pointer types.
4. Variadic calls remain positional-only in this plan. Named-argument interaction is out of scope and is a separate
   follow-up plan, not a sequencing dependency on the standalone named-arguments plan; both features independently
   reject the cross-feature combination.
5. Inside the callee, the final variadic parameter has effective type `T[]` and uses ordinary `len`, checked indexing,
   and slice assignment behavior.
6. Explicit forwarding uses one final `pack...` argument as the complete variadic tail; it cannot be mixed with
   individual variadic values.

## Goal

1. Parse variadic function declarations and function-pointer types.
2. Type-check calls with a fixed required prefix plus zero or more trailing arguments of the variadic element type.
3. Expose the variadic pack through the implemented `T[]` body contract.
4. Lower variadic calls and callees in generated C without implying C variadic FFI support.

## Implementation Phases

### Phase 1: Surface syntax and AST

Extend parsing and AST/type representations so a function declaration or function-pointer type may end with one variadic
parameter. Enforce that the variadic parameter is last and appears at most once.

### Phase 2: Callee-side pack contract

Resolve the final parameter to `T[]`. The callee uses the existing mutable slice surface, while ordinary call arguments
live in an owned caller-side fixed-array pack for the duration of the surrounding scope.

### Phase 3: Call typing and lowering

Teach `expr_types.l0` to:

- require the fixed prefix arguments,
- accept zero or more trailing arguments matching the variadic element type,
- reject named calls for variadic functions in this plan,
- keep ordinary fixed-arity calls unchanged.

Lower generated C through an implementation-defined helper/signature scheme that stays entirely within the L1-defined
function world rather than reusing C varargs.

### Phase 4: Function pointers and forwarding

Extend function-pointer typing and emission so variadic signatures can be named and called indirectly when their fixed
prefix and variadic element type match exactly. Forward a compatible slice or fixed array with explicit final `pack...`
syntax.

### Phase 5: Docs and roadmap

1. Update `l1/docs/reference/design-decisions.md` with the final variadic syntax and pack rules.
2. Update `l1/docs/roadmap.md` so the backlog distinguishes this standalone plan from the still-open C variadic FFI work
   under Initiative `0003-c-ffi`.

## Diagnostics

1. `PAR-0520` and `PAR-0521` cover malformed parameter and spread placement.
2. `SIG-0220` rejects variadic `extern func` declarations.
3. `TYP-0740` through `TYP-0744` cover fixed-prefix, element, spread, and named-call failures.
4. All assigned codes are registered in the live diagnostic catalog.

## Non-Goals

1. C variadic FFI and variadic `extern func` declarations.
2. A general slice/array language feature.
3. Named-argument rules for variadic calls.
4. Generic parameter packs or template-style variadics.
5. Automatic backporting to L0.

## Verification Criteria

1. Variadic function declarations and matching function-pointer types parse successfully.
2. Call typing enforces a fixed required prefix plus zero or more trailing arguments of the declared element type.
3. Generated C for L1-defined variadic functions is self-consistent and does not rely on C ABI varargs.
4. The roadmap and design-decision docs clearly separate L1 variadic functions from C variadic FFI.
5. Any newly assigned diagnostic codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md`.

## Implementation Summary

Completed in L1 Stage 1. The lexer, parser, ordered type-suffix model, semantic function types, direct and indirect call
typing, C lowering, interface round trips, LBI mangling/demangling, diagnostics, runtime fixtures, trace coverage, and
reference documentation now support L1-defined variadic functions. The final `T...` parameter lowers as `T[]`, while the
`V` LBI component keeps variadic function identity distinct from a fixed slice signature. C variadic FFI remains outside
this plan.
