# Feature Plan

## Add ordered type suffix constructors

- Date: 2026-05-11
- Status: Completed
- Title: Add ordered type suffix constructors
- Kind: Feature
- Severity: High
- Stage: L1
- Subsystem: Parser / typing / interfaces / backend / docs
- Modules:
  - `l1/compiler/stage1_l0/src/ast.l0`
  - `l1/compiler/stage1_l0/src/parser/shared.l0`
  - `l1/compiler/stage1_l0/src/parser/expr.l0`
  - `l1/compiler/stage1_l0/src/types.l0`
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/signatures.l0`
  - `l1/compiler/stage1_l0/src/interface_emitter.l0`
  - `l1/compiler/stage1_l0/src/module_interface.l0`
  - `l1/compiler/stage1_l0/src/parser/interface.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/specs/compiler/abi.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/type_resolve_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
- Related:
  - `l1/work/plans/features/2026-05-10-fixed-size-array-primitive-noref.md`
  - `l1/work/initiatives/0004-array-primitives-and-unsafe-marker.md`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/specs/compiler/abi.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro:
  `make -C l1 test-stage1 TESTS="parser_test type_resolve_test expr_types_test c_emitter_test backend_test interface_test"`

## Summary

Relax L1's pointer and nullable type suffix grammar from a fixed `*... ?` shape to a regular ordered suffix stack:

```ebnf
Type       ::= SimpleType TypeSuffix*
TypeSuffix ::= "*" | "?"
```

Suffixes apply left-to-right. `T?*` is a pointer to an optional `T`, `T*?` is an optional pointer to `T`, and `T??` is
an optional optional `T`. Nested optional types are not collapsed.

This plan must land before restarting the fixed-size array primitive implementation. Fixed-size arrays should then add
`[N]` as another ordered type constructor instead of extending the current `base + pointer_depth + is_nullable` model.

## Current State

1. The reference grammar admits `T`, `T*`, `T**`, `T?`, and `T*?`, but rejects `T?*`, `T??`, and arbitrary
   pointer/nullable interleavings.
2. Parsed `TypeRef` still carries the legacy shape `name`, `pointer_depth`, and `is_nullable`, with recent ordered
   suffix support acting as an overlay rather than the canonical representation.
3. `TypeExpr` parsing for type-accepting intrinsics has its own suffix recognition logic, so it can diverge from
   ordinary type parsing.
4. C lowering currently niche-optimizes nullable pointers, but the implementation must not reuse that single `NULL`
   representation for nested optional pointer forms such as `T*??`.

## Defaults Chosen

1. Type suffixes are semantic unary constructors applied left-to-right.
2. `T??` represents three states: outer null, outer present with inner null, and outer present with inner present `T`.
3. Nullable pointer niche lowering applies only to the immediate semantic shape `Optional(Pointer(_))`.
4. `T*??` lowers with an outer optional wrapper so it can distinguish outer absence from an inner null pointer.
5. `T?*` is allowed because optional values are first-class storage values in L1.
6. `void*` remains allowed; `void?` and `void?*` are rejected because `void?` is not a value object.
7. `TypeExpr` uses the same suffix rules as ordinary `Type`.

## Goal

1. Make the AST and semantic type model represent ordered type constructors directly.
2. Keep exact nested optional and pointer structure through type resolution, equality, formatting, signatures, and
   interface round-tripping.
3. Make backend and C emitter lowering recursive so nested optionals over pointer-shaped values preserve information.
4. Update reference grammar, design decisions, and ABI notes to document the relaxed suffix model.
5. Add tests that lock the relaxed grammar and prevent fixed-size-array work from reintroducing ad hoc parser
   disambiguation bugs.

## Implementation Phases

### Phase 1: Parser and AST

Make ordered type suffixes the canonical parsed representation for ordinary types and function pointer types. Preserve
legacy `pointer_depth` and `is_nullable` fields only as temporary compatibility shims if needed during the patch, and
remove or de-emphasize them once all consumers use the ordered suffix list.

Align `TypeExpr` parsing with ordinary type parsing. It should accept the same suffix chains in type-accepting
intrinsics such as `sizeof(T?*)`, without misclassifying value indexing expressions in ordinary call arguments.

### Phase 2: Semantic types

Represent pointer and optional as recursive type constructors rather than derived metadata on a named base. Update type
resolution, equality, cloning, formatting, alias expansion, cycle handling, and assignability helpers so they preserve
the exact constructor tree.

Add helper predicates with precise meanings, including `is_pointer_type`, `is_optional_type`, and a nullable-pointer
niche predicate that matches only `Optional(Pointer(_))`.

### Phase 3: Interfaces and signatures

Carry ordered suffix structure through signature collection, module interfaces, interface parsing, and interface
emission. Interface round-trips must preserve `T?*`, `T*?`, and `T??` distinctly.

### Phase 4: Backend and C lowering

Make nullable lowering recursive:

- `T*?` may use the pointer null niche.
- `T?` lowers to a wrapper with `has_value` and `value`.
- `T??` lowers to a wrapper whose value is the inner optional representation.
- `T?*` lowers to a pointer to the optional value representation.
- `T*??` lowers to an outer wrapper around the inner nullable pointer representation.

Update optional wrapper keys and dependency emission so every distinct nested optional form has a stable, non-colliding
C representation and appears after any dependent wrapper/type definitions it needs.

### Phase 5: Docs and fixed-array handoff

Update the reference docs to describe ordered suffixes and left-to-right meaning. Update the fixed-size array plan or
follow-up restart notes so `T[N]` is added later as another ordered type constructor rather than repeating the legacy
metadata model.

## Diagnostics

This plan should reuse existing type diagnostics where possible:

1. Keep `SIG-0011` and `TYP-0278` for `void?`.
2. Use existing unknown-type and symbol-is-not-type diagnostics for failed type resolution.
3. Add new parser or typing codes only if implementation discovers a genuinely new diagnostic category that cannot be
   expressed by existing codes.
4. If new codes are needed, re-check `docs/specs/compiler/diagnostic-code-catalog.md` at implementation time before
   assigning them.

## Non-Goals

1. Fixed-size arrays themselves; this plan only prepares the suffix/type-constructor model they should build on.
2. Collapsing or normalizing nested optionals.
3. New optional operators or broader optional pattern syntax.
4. New implicit conversions between different optional depths.
5. Changing current nullable equality beyond what is necessary to preserve existing behavior for the newly representable
   exact types.

## Verification Criteria

1. Parser and type-resolution tests cover `T`, `T*`, `T**`, `T?`, `T*?`, `T?*`, `T??`, `T*?*?`, `T?*?*?`, `void*`,
   rejected `void?`, and rejected `void?*`.
2. `TypeExpr` tests prove the same suffix chains work in `sizeof` and other type-accepting intrinsics.
3. Interface tests prove `T*?`, `T?*`, and `T??` round-trip without collapsing or reordering.
4. C-emitter/backend tests prove distinct lowering for `T*?`, `T*??`, and `T?*`.
5. Nullable behavior tests cover assignment, equality where currently supported, unwrap/try behavior, and casts over
   nested optionals where existing rules apply.
6. Regression tests prove ordinary call arguments shaped like `value[index]` are parsed as value indexing, not
   `TypeExpr`.
7. `make -C l1 test-stage1` passes.
