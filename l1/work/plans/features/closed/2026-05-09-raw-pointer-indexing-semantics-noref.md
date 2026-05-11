# Feature Plan

## Finalize raw-pointer indexing semantics

- Date: 2026-05-09
- Status: Completed
- Title: Finalize raw-pointer indexing semantics
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: `l1/work/initiatives/closed/0004-array-primitives-and-unsafe-marker.md`
- Subsystem: Typing / backend / C emission / docs / tests
- Modules:
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/reference/ownership.md`
  - `l1/docs/reference/c-backend-design.md`
  - `l1/docs/roadmap.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
- Related:
  - `l1/work/initiatives/closed/0004-array-primitives-and-unsafe-marker.md`
  - `l1/docs/roadmap.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 TESTS="expr_types_test parser_test backend_test c_emitter_test"`

## Summary

Initiative `0004` already settled the intended shape of raw-pointer indexing: keep the existing `ptr[i]` syntax as a
direct C-style operation on `T*`, but make the language contract explicit before Phase 3 arrays reuse the same postfix
indexing form. This plan locks the contract in for typing, diagnostics, lowering, and docs.

## Current State

1. Stage 1 already parses `ptr[i]`, types it for non-null `T*` receivers, and lowers it to direct C indexing.
2. The current diagnostics still describe pointer indexing as unfinished rather than as a stable raw-pointer feature.
3. Safe-code gating has not yet been enforced even though Initiative `0004` now treats postfix pointer indexing as an
   `unsafe func`-only operation.
4. The current docs still describe pointer indexing as semantically unfinished, which is now stale against the
   initiative-level design.

## Defaults Chosen

1. `ptr[i]` remains direct unchecked raw-pointer indexing. No bounds checks, helper calls, or new syntax are added in
   this phase.
2. The accepted form is restricted to `ptr: T*`, `i: int`, sized non-`void` pointee `T`, and use inside an `unsafe func`
   body.
3. Ordinary `*p` and `p.field` remain available in safe code; only postfix pointer indexing is gated here.
4. Existing single-evaluation lowering behavior for side-effectful bases and indexes is the contract to preserve.
5. ARC-bearing pointee writes keep the existing slot-replacement assignment discipline.

## Goal

1. Finalize `ptr[i]` as a documented L1 language feature with stable diagnostics.
2. Enforce the `unsafe func` restriction in typing without changing the current ABI or surface syntax.
3. Lock the backend and ownership contract in with focused codegen and trace regressions.

## Implementation Phases

### Phase 1: Typing and diagnostics

Update `etc_infer_index(...)` in [expr-types] to enforce the finalized rule in this order:

1. type-check the index expression and keep `TYP-0210` for non-`int` indexes
2. reject nullable bases with `TYP-0211`
3. reject non-pointer bases with `TYP-0213`
4. reject `void*` and any future unsupported unsized pointee forms with `TYP-0215`
5. reject otherwise-valid pointer indexing outside an `unsafe func` body with `TYP-0214`
6. otherwise yield the pointee type

The implementation should keep the current behavior where independently-invalid base and index subexpressions still each
get their relevant diagnostics when both sides were type-checked.

### Phase 2: Backend and ownership contract

Keep `EX_INDEX` lowering in [backend] and [c-emitter] as direct C indexing for both expression and lvalue paths.

This phase explicitly locks in the current backend contract:

- expression reads stay as direct `base[index]`
- side-effectful lvalue bases are captured once
- side-effectful lvalue indexes are captured once
- `ptr[i] = value` continues to use the normal ARC slot-replacement path when the pointee type transitively contains
  ARC-managed data

No bounds checks, runtime helpers, or block-level `unsafe {}` mechanism are introduced here.

### Phase 3: Fixtures, regressions, and docs

Extend the existing typing, parser, backend, emitter, and trace fixtures to cover:

- accepted read and write forms inside `unsafe func`
- rejection in safe functions and top-level contexts
- rejection for nullable bases, `void*`, non-pointer bases, and non-`int` indexes
- direct `base[index]` lowering and single evaluation on side-effectful write operands
- ARC retain/release order for `ptr[i] = value` on ARC-bearing elements

Refresh [grammar], [design-decisions], [ownership], [backend-design], [roadmap], and [diag-catalog] so they describe the
finalized contract rather than the earlier placeholder wording.

## Diagnostics

This plan uses the existing `TYP-021x` range rather than reserving a new block:

1. keep `TYP-0210` for non-`int` indexes
2. keep `TYP-0211` as the shared nullable-base code
3. keep `TYP-0212` reserved for the existing L0 “indexing is not yet supported on this base” meaning
4. assign `TYP-0213` to non-pointer index bases in L1+
5. assign `TYP-0214` to pointer indexing outside an `unsafe func`
6. assign `TYP-0215` to `void*` or other unsupported unsized pointee indexing

Re-check the live [diag-catalog] at implementation time before finalizing exact meanings. If any of these slots have
been reused since drafting, choose nearby free replacements then.

## Non-Goals

1. Fixed-size array types, literals, or bounds-checked indexing.
2. Address-of, general pointer arithmetic, or slices/views.
3. Call-site `unsafe` blocks or ABI changes.
4. New runtime helpers for pointer indexing.

## Verification Criteria

1. `unsafe func read(p: int*, i: int) -> int { return p[i]; }` and matching write forms type-check cleanly.
2. `ptr[i]` outside an `unsafe func` body diagnoses with `TYP-0214`.
3. Nullable, `void*`, non-pointer, and non-`int` misuse cases report the intended `TYP-021x` diagnostics.
4. Generated C preserves direct raw indexing and the current single-evaluation write path.
5. Trace coverage shows ARC-bearing indexed writes retain incoming values before releasing overwritten slot contents.
6. [diag-catalog] is updated to match the landed diagnostics.

## Completion Notes

1. `ptr[i]` is now finalized in L1 as raw-pointer indexing on `T*`, gated to `unsafe func` bodies and still lowered to
   direct unchecked C indexing.
2. L1 preserves `TYP-0211` as the shared nullable-base diagnostic, keeps `TYP-0212` reserved for the existing L0
   meaning, and uses `TYP-0213` to `TYP-0215` for the L1-only non-pointer, unsafe-context, and unsized-pointee
   pointer-index failures.
3. The backend contract is locked in with focused codegen coverage for direct indexing and single-evaluation lvalue
   lowering, plus a trace regression for ARC slot replacement through `ptr[i] = value`.
4. Reference docs and the shared diagnostic catalog now describe pointer indexing as shipped L1 behavior rather than an
   unfinished placeholder.

## Final Validation

- `make -C l1 test-stage1`

[backend]: ../../../compiler/stage1_l0/src/backend.l0
[backend-design]: ../../docs/reference/c-backend-design.md
[c-emitter]: ../../../compiler/stage1_l0/src/c_emitter.l0
[design-decisions]: ../../docs/reference/design-decisions.md
[diag-catalog]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[expr-types]: ../../../compiler/stage1_l0/src/expr_types.l0
[grammar]: ../../docs/reference/grammar.md
[ownership]: ../../docs/reference/ownership.md
[roadmap]: ../../docs/roadmap.md
