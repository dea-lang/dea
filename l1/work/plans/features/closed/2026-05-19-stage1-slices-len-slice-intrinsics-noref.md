# Feature Plan

## Add Stage 1 slices, `len`, and `slice`

- Date: 2026-05-19
- Status: Implemented
- Title: Add Stage 1 slice types and slice intrinsics
- Kind: Feature
- Severity: High
- Stage: L1
- Subsystem: Parser / typing / lowering / runtime / docs
- Modules:
  - `l1/compiler/stage1_l0/src/ast.l0`
  - `l1/compiler/stage1_l0/src/parser.l0`
  - `l1/compiler/stage1_l0/src/parser/shared.l0`
  - `l1/compiler/stage1_l0/src/types.l0`
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/signatures.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/docs/specs/compiler/abi.md`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/reference/ownership.md`
  - `l1/docs/reference/c-backend-design.md`
  - `l1/docs/reference/standard-library.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/type_resolve_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/fixtures/driver`
  - `l1/compiler/stage1_l0/tests/fixtures/typing`
- Related:
  - `l1/work/initiatives/closed/0004-array-primitives-and-unsafe-marker.md`
  - `l1/work/plans/features/closed/2026-05-10-fixed-size-array-primitive-noref.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro:
  `make -C l1 test-stage1 TESTS="parser_test type_resolve_test expr_types_test backend_test c_emitter_test l0c_lib_test"`

## Summary

Add the first L1 Stage 1 slice surface on top of the completed fixed-size array primitive. This plan introduces
first-class slice types `T[]`, compiler-owned `dea::len` and `dea::slice` intrinsics, checked slice indexing, and
limited contextual conversion from owning fixed-size arrays `T[N]` to non-owning slice descriptors.

The feature is intentionally narrow. Slices are non-owning local/parameter/call values in this stage, not a general
escape-capable reference type. They may be used as local variables, parameters, and call arguments, but are rejected in
returns, struct fields, top-level lets, and heap payload fields.

## Current State

1. L1 has owning fixed-size value arrays `T[N]` with bounds-checked indexing, deterministic wrapper typedefs, recursive
   ARC behavior, and positive compile-time lengths.
2. L1 has no first-class slice/view type, so APIs that need variable-length contiguous views must use library containers
   or raw pointers.
3. The compiler-owned `dea` prelude currently hosts intrinsics such as `sizeof`, `ord`, and `is`, preserving existing
   shadowing behavior for unqualified user names.
4. `_rt_panic_oob` already exists for checked array indexing and can be reused for slice index and range failures.
5. The roadmap defers language-level variadic functions until a slice/array surface exists, making this feature a
   prerequisite for re-evaluating that plan.

## Defaults Chosen

01. `T[N]` remains an owning fixed-size value array. This plan does not weaken array copy, cleanup, allocation, or
    return semantics.

02. `T[]` is a non-owning descriptor copied by value:

    ```c
    typedef struct __dea...slice... {
        dea_int len;
        T *data;
    } __dea...slice...;
    ```

03. `T[_]` is not implemented and must not receive slice semantics. It is either syntactically rejected or diagnosed as
    reserved for future language use.

04. Slices are local/parameter/call-only in this stage. They are allowed as local variables, parameters, and call
    arguments, and rejected in return types, returned expressions, struct fields, top-level lets, and heap payload
    fields.

05. `len(x)` accepts only fixed arrays and slices and returns L1 `int`.

06. `slice(x)`, `slice(x, start)`, and `slice(x, start, count)` accept only fixed arrays and slices.

07. The third `slice` argument is `count`, not `end`.

08. Slice indexing is bounds-checked before any C pointer dereference.

09. Zero-length slice results use `len = 0` and `data = NULL`.

10. Implicit `T[N] -> T[]` conversion is allowed only in known slice target contexts: function arguments, annotated
    local initialization, and assignment to existing slice variables.

11. Pointer operands to `slice` remain rejected. This plan does not add pointer-to-slice conversion or address-of.

12. The initial implementation supports `T[]`, `T*[]`, and `T?[]`. It rejects `T[]?` and `T[]*` unless those forms can
    be implemented without weakening the escape restrictions above.

13. The slice LBI type component is explicitly fixed as the single-letter `W<elem>`, producing wrapper names such as
    `__deaWi` for `int[]`. `W` denotes a non-owning window over contiguous storage and remains distinct from the `S`
    nominal struct leaf; the implementation must not invent a different or multi-letter ABI spelling.

## Goal

1. Parse and resolve `T[]` distinctly from `T[N]`, while reserving or rejecting `T[_]`.
2. Add semantic slice types with exact element-type identity and helper APIs such as `make_slice_type`, `is_slice_type`,
   and `slice_element_type`.
3. Add compiler-owned `dea::len` and `dea::slice` intrinsics with the same qualified/unqualified shadowing behavior as
   existing `dea` prelude intrinsics.
4. Type-check `len`, `slice`, slice indexing, slice assignment, and contextual fixed-array-to-slice conversion.
5. Reject slice escapes conservatively until L1 has a broader borrow/lifetime story.
6. Lower slices to deterministic generated C descriptor typedefs named from the ABI type component of the element type.
7. Document grammar, ownership, backend lowering, standard-library interactions, design decisions, roadmap status, and
   the reserved future meaning of `T[_]`.

## Implementation Phases

### Phase 1: Semantic type model

Extend AST, type representation, and type resolution with a distinct `TY_SLICE` form. Add `make_slice_type`,
`is_slice_type`, `slice_element_type`, and exact element-type array-to-slice eligibility helpers. The conversion is
structural only where the target is already known to be a slice of the same element type.

Do not represent `T[]` as a length-erased array. That distinction is required for ownership, assignment, return
diagnostics, and backend lowering.

### Phase 2: Type suffix parsing

Extend ordered type suffix parsing so `[]` is a slice suffix and `[N]` remains a fixed-size array suffix. Reserve or
reject `[_]` explicitly, and ensure it is never treated as `T[]`.

Parser tests cover valid `T[]`, nested forms such as `T*[]` and `T?[]`, invalid nullable/pointer-after-slice forms if
kept out of scope, malformed suffixes, and reserved `T[_]`.

### Phase 3: Prelude intrinsics

Extend the compiler-owned `dea` prelude with `dea::len` and `dea::slice`. Unqualified `len` and `slice` resolve as
intrinsics only when normal name lookup does not find a user-defined symbol, preserving the current shadowing model.
Qualified `dea::len` and `dea::slice` always name the compiler-owned intrinsics.

### Phase 4: Expression typing and conversion

Teach expression typing to:

- accept `len(array)` and `len(slice)` as `int`,
- accept `slice(array_or_slice)`, `slice(array_or_slice, start)`, and `slice(array_or_slice, start, count)`,
- reject non-array and non-slice operands, including raw pointers,
- require `int` for slice indexes, starts, and counts, reusing `TYP-0210` where appropriate,
- type slice indexing as the element type,
- type slice assignment using the same element assignment rules as array element assignment,
- apply `T[N] -> T[]` only in known slice contexts: function arguments, annotated local initialization, and assignment
  to existing slice variables.

No unconstrained expression should silently decay from `T[N]` to `T[]`; this avoids C-style array decay and keeps
ownership explicit.

### Phase 5: Escape diagnostics

Add conservative diagnostics that reject slices in long-lived or ownership-ambiguous locations:

- function return types,
- return expressions,
- struct fields,
- top-level lets,
- heap payload fields.

This stage does not attempt flow-sensitive escape analysis. Local variables, parameters, and call arguments are the
entire accepted slice lifetime model.

### Phase 6: C lowering

Lower each slice instantiation to a deterministic descriptor typedef using the plan-approved `W<elem>` LBI component.
The descriptor contains `dea_int len` and `T *data`, and descriptor copies are ordinary value copies with no retain,
release, cleanup, or ownership transfer.

Array-to-slice conversion forms a descriptor using the fixed array length and a pointer to the array's first element.
Slice-to-slice slicing forms a descriptor using checked range arithmetic and the original data pointer. Zero-length
results set `len = 0` and `data = NULL`.

### Phase 7: Runtime checks

Reuse `_rt_panic_oob` for slice indexing failures and range failures. Generated C must check index and slice range
conditions before pointer arithmetic or dereference. Add a small backend helper for checked slice-range lowering only if
direct lowering becomes noisy or duplicated across read, write, and slicing paths.

### Phase 8: Docs and integration

Update [`grammar.md`][grammar], [`design-decisions.md`][design-decisions], [`ownership.md`][ownership],
[`c-backend-design.md`][backend-design], [`standard-library.md`][standard-library], and [`roadmap.md`][roadmap]. The
docs should describe `T[]`, `len`, `slice`, array-to-slice conversion contexts, checked indexing, non-owning descriptor
semantics, and the reserved future meaning of `T[_]`.

## Diagnostics

1. Provisionally reserve `PAR-0640` to `PAR-0659` for slice suffix and reserved `T[_]` parsing/shape diagnostics.
2. Provisionally reserve `TYP-0820` to `TYP-0839` for slice typing, intrinsic operand, implicit conversion, and escape
   diagnostics.
3. Reuse existing `TYP-0210` for non-`int` index, start, and count expressions where appropriate.
4. Re-check these provisional reservations against the live diagnostic catalog at implementation time before assigning
   final codes. The current live catalog has array parsing in `PAR-0620` to `PAR-0623` and array typing in `TYP-0800` to
   `TYP-0807`, leaving the proposed slice-adjacent blocks free at plan creation time.

## Non-Goals

1. `T[_]` inferred-length arrays or wildcard dimensions.
2. Returning slices or storing slices in long-lived locations.
3. General borrow checking, lifetime inference, or flow-sensitive escape analysis.
4. Pointer-to-slice conversion, address-of (`&`), or broader pointer arithmetic.
5. Heap-owned dynamic buffers or shared buffer types.
6. Array or slice equality operators.
7. C FFI slice policy.
8. Backporting this feature to L0.

## Verification Criteria

01. `T[]` parses and resolves distinctly from `T[N]`.
02. `len` and qualified `dea::len` work for arrays and slices.
03. `slice` and qualified `dea::slice` work for arrays and slices with arities 1, 2, and 3.
04. Fixed-array-to-slice conversion happens only in known slice contexts.
05. Slice indexing and slicing range checks happen before pointer arithmetic or dereference.
06. Generated C contains deterministic slice structs with `dea_int len` and `T *data`.
07. Slice passing, assignment, and locals copy only the descriptor and emit no cleanup.
08. Returning slices and storing slices in long-lived locations are rejected.
09. `T[_]` is either syntactically rejected or diagnosed as reserved, never treated as `T[]`.
10. Focused coverage lands in `parser_test.l0`, `type_resolve_test.l0`, `expr_types_test.l0`, `backend_test.l0`,
    `c_emitter_test.l0`, `l0c_lib_test.l0`, and CLI/runtime fixtures under `l1/compiler/stage1_l0/tests/fixtures/driver`
    and `l1/compiler/stage1_l0/tests/fixtures/typing`.
11. `make -C l1 test-stage1 TESTS="parser_test type_resolve_test expr_types_test backend_test c_emitter_test l0c_lib_test"`
    passes.

[backend-design]: ../../../docs/reference/c-backend-design.md
[design-decisions]: ../../../docs/reference/design-decisions.md
[grammar]: ../../../docs/reference/grammar.md
[ownership]: ../../../docs/reference/ownership.md
[roadmap]: ../../../docs/roadmap.md
[standard-library]: ../../../docs/reference/standard-library.md
