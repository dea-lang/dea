# Feature Plan

## Add anonymous embedded struct members via `_ : StructType`

- Date: 2026-04-22
- Status: Draft
- Title: Add anonymous embedded struct members via `_ : StructType`
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Struct declarations / signature analysis / field resolution / backend / ABI / docs
- Modules:
  - `l1/compiler/stage1_l0/src/ast.l0`
  - `l1/compiler/stage1_l0/src/parser.l0`
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/type_resolve_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/docs/reference/design-decisions.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: None

## Summary

The roadmap currently leaves `_` struct-member semantics undecided. This plan fixes the meaning as an anonymous embedded
struct in the first member position:

```l1
struct Shape { cx: double; cy: double };
struct Square { _: Shape; size: double };
```

`Shape` is embedded anonymously inside `Square`. Promoted field access is then allowed (`q.cx` means `q._.cx`), while
ordinary outer members continue to work directly (`q.size`).

## Current State

1. Struct declarations currently model only ordinary named fields.
2. Field access resolves against fields declared directly on the struct type; there is no promoted-field lookup path.
3. Constructor arity and argument order follow the declared field list only.
4. The roadmap lists `_` struct-member semantics as open backlog work because construction, field access, layout, and
   ABI effects are not yet fixed.

## Defaults Chosen

1. `_ : T` embeds `T` anonymously when `T` resolves to a concrete struct layout. A type alias that resolves to a struct
   is acceptable; non-struct, pointer, enum, and opaque extern forms are not.
2. At most one `_` member is allowed per struct.
3. The `_` member must appear first in the field list.
4. Promoted field lookup is enabled for the embedded struct's fields, so `outer.field` may resolve through
   `outer._.field`.
5. Positional construction is flattened in declared order: embedded-struct fields first, then the outer struct's own
   remaining fields. For example, `new Square(0.0, 1.0, 42.0)` initializes `cx`, `cy`, then `size`.
6. Physical layout remains nested: the backend still emits a real inner field corresponding to `_`, and promoted access
   is purely a language-level lookup/lowering rule.
7. Any outer field whose name would collide with a promoted embedded field is rejected to avoid ambiguous field access.

## Goal

1. Parse and represent anonymous embedded struct members.
2. Enforce the "struct-only, first-position-only, single `_` only" rule.
3. Support promoted field access and flattened positional construction.
4. Preserve a simple nested C layout and make the ABI implications explicit in docs.

## Implementation Phases

### Phase 1: Declaration and signature rules

Extend struct-member parsing/AST to represent `_` distinctly from ordinary fields. In declaration/signature analysis:

- require the `_` member to be first,
- require that there is at most one `_`,
- require the embedded type to resolve to a concrete struct,
- reject promoted-name collisions between the embedded struct and outer fields.

### Phase 2: Field lookup and construction typing

Teach field lookup to search the embedded struct when a direct outer-field match is absent. Update constructor typing so
positional constructor arguments flatten the embedded struct's fields first and then the outer struct's remaining
fields.

### Phase 3: Backend lowering and layout

Keep the generated C layout nested rather than flattening ABI storage. Lower promoted field access as explicit access
through the hidden inner member. Constructor lowering should build the nested field initialization in the same flattened
source order chosen by the language contract.

### Phase 4: Docs and tests

1. Update `l1/docs/reference/grammar.md` and `l1/docs/reference/design-decisions.md` with the `_ : StructType` rule.
2. Update `l1/docs/roadmap.md` to replace the open-ended backlog wording with a cross-reference to this plan.
3. Add parser, signature/type-resolution, field-access, backend, and end-to-end constructor coverage.

## Diagnostics

1. This feature is likely to need dedicated declaration/signature diagnostics for invalid `_` placement, duplicate `_`
   members, non-struct embedded types, and promoted-name collisions.
2. Provisionally reserve `SIG-0240` to `SIG-0259` for embedded-struct declaration/signature diagnostics and `TYP-0780`
   to `TYP-0799` for promoted-field lookup and constructor-typing diagnostics.
3. Re-check these provisional reservations against the live catalog at implementation time before assigning final
   numbers; if any of the suggested slots were used in the meantime, choose a different free block then.

## Non-Goals

1. More than one anonymous embedded struct per outer struct.
2. Allowing `_` anywhere other than the first member position.
3. Embedding non-struct types.
4. ABI-level field flattening in generated C.
5. Named-constructor interaction; that belongs to the named-arguments plan.

## Verification Criteria

1. Invalid uses of `_` are rejected under the declared placement/type rules.
2. Valid promoted field access resolves as if `outer.field` meant `outer._.field`.
3. Positional construction follows the flattened source order defined by this plan.
4. Generated C preserves a simple nested layout and lowers promoted access through the embedded field.
5. `l1/docs/reference/grammar.md`, `l1/docs/reference/design-decisions.md`, and `l1/docs/roadmap.md` reflect the adopted
   embedded-struct semantics.
