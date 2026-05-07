# Feature Plan

## Add L1 variadic functions

- Date: 2026-04-22
- Status: Deferred
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
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/work/initiatives/0003-c-ffi.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: None

## Summary

The roadmap currently groups two different concerns under "Varargs": language-level variadic functions written in L1,
and C variadic FFI at the `extern func` boundary. This plan intentionally covers only the first half: defining, calling,
and lowering L1 variadic functions. C variadic FFI remains part of Initiative `0003-c-ffi`.

This split keeps the language-core work reviewable and avoids entangling pack semantics with FFI-safe type rules,
calling-convention edge cases, and `va_list`-style C interop. The standalone plan should leave a clean handoff to the
FFI initiative rather than pre-committing its boundary rules.

## Deferral Rationale

This plan is deferred pending a general slice/array language feature (currently a backlog item under "Language core" in
[l1/docs/roadmap.md](../../../docs/roadmap.md)). Phase 2 of this plan would otherwise have to invent a bespoke read-only
pack contract solely because L1 has no slice/array surface today. If slices/arrays land first, the variadic feature
collapses to syntactic sugar over a slice-typed trailing parameter: forwarding becomes trivial, variadic
function-pointer typing simplifies, and no throwaway pack ABI is shipped. Re-evaluate this plan once a slice/array plan
is promoted from backlog.

Deferring L1 variadics does not block C variadic FFI: that work is a separate sibling tranche under Initiative 0003 with
its own `va_list` companion-function workaround (see "C variadic FFI scope" in
[l1/work/initiatives/0003-c-ffi.md](../../initiatives/0003-c-ffi.md)).

## Current State

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
5. The pack representation may be compiler-private, but the plan must define a small, documented source-level contract
   for reading the count and individual elements inside the callee.

## Goal

1. Parse variadic function declarations and function-pointer types.
2. Type-check calls with a fixed required prefix plus zero or more trailing arguments of the variadic element type.
3. Define a bootstrap-safe body contract for consuming the variadic pack without introducing general slice/array
   features.
4. Lower variadic calls and callees in generated C without implying C variadic FFI support.

## Implementation Phases

### Phase 1: Surface syntax and AST

Extend parsing and AST/type representations so a function declaration or function-pointer type may end with one variadic
parameter. Enforce that the variadic parameter is last and appears at most once.

### Phase 2: Callee-side pack contract

Choose and document the minimal source-level surface visible inside the callee. The implementation may use hidden count
and storage parameters internally, but the plan should commit to an L1-facing contract that is stable and does not
depend on general array/slice work. The recommended direction is a narrow read-only pack surface with element count and
indexed access only.

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
prefix and variadic element type match exactly. Forwarding one variadic pack into another variadic call is in scope only
if the chosen pack contract makes it straightforward; otherwise it should be deferred explicitly.

### Phase 5: Docs and roadmap

1. Update `l1/docs/reference/design-decisions.md` with the final variadic syntax and pack rules.
2. Update `l1/docs/roadmap.md` so the backlog distinguishes this standalone plan from the still-open C variadic FFI work
   under Initiative `0003-c-ffi`.

## Diagnostics

1. This feature is likely to need dedicated parse-time diagnostics for malformed `...` placement and dedicated type
   diagnostics for variadic call mismatches.
2. Provisionally reserve `PAR-0520` to `PAR-0539` for variadic syntax/placement diagnostics and `TYP-0740` to `TYP-0759`
   for variadic typing/call diagnostics. If signature-analysis-specific diagnostics become necessary for variadic
   function types, provisionally reserve `SIG-0220` to `SIG-0239`.
3. Re-check all proposed reservations against the live catalog at implementation time before assigning final numbers; if
   any slot has been used in the meantime, choose a different free block then.

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
