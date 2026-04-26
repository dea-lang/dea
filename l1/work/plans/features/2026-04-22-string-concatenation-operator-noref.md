# Feature Plan

## Add `+` string concatenation operator

- Date: 2026-04-22
- Status: Draft
- Title: Add `+` string concatenation operator
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Typing / backend / runtime / ARC / docs
- Modules:
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/work/plans/features/closed/2026-04-18-string-equality-operators-noref.md`
  - `l1/work/plans/features/closed/2026-04-18-string-relational-operators-noref.md`
- Repro: None

## Summary

L1 now supports content-based string equality and relational comparison, but `+` remains numeric-only. The roadmap keeps
string concatenation open because the compiler has not yet committed to the ARC ownership contract for concatenation
results or the backend/runtime helper surface needed to produce them efficiently.

This plan adds `string + string -> string` as the first concatenation surface. It is intentionally narrow: no implicit
coercions, no builder API, and no augmented assignment. The main deliverable is a stable ownership and code-generation
contract for a fresh concatenated result.

## Current State

1. The parser already accepts `+` expressions; no new expression grammar is needed.
2. `expr_types.l0` treats `+` as part of the existing arithmetic operator surface, so `string + string` is rejected by
   the current typing rules.
3. The backend/runtime already has dedicated helpers for string comparison (`rt_string_equals`, `rt_string_compare`) but
   no committed helper for concatenation result allocation and ownership.
4. The roadmap explicitly leaves string concatenation in backlog pending ARC result-ownership design.

## Defaults Chosen

1. This plan adds only `string + string -> string`.
2. Both operands must already be `string`. No implicit coercions from `byte`, numeric types, `char`-like literals, or
   nullable/string-pointer forms are introduced here.
3. The result is a fresh owned `string` value with ordinary ARC behavior. Neither operand is mutated or consumed.
4. Evaluation order stays left-to-right in source order, matching the current binary-expression contract.
5. Backend lowering should prefer a dedicated runtime helper over open-coded buffer arithmetic so ownership and
   allocation stay centralized.

## Goal

1. Accept `+` when both operands are `string`, yielding `string`.
2. Lower concatenation through a dedicated runtime/helper path that returns a fresh owned string.
3. Add typing, emitter, and end-to-end runtime coverage that locks in the ARC contract.
4. Document the new string-result semantics in the L1 reference docs and roadmap.

## Implementation Phases

### Phase 1: Typing

Extend the binary-operator typing branch in `expr_types.l0` so `+` accepts two `string` operands and yields `string`
without disturbing existing integer or real arithmetic behavior. Mixed `string`/non-`string` pairs should continue to
surface ordinary operator/type-mismatch diagnostics rather than silent coercions.

### Phase 2: Runtime and backend

Add a runtime helper (name to be chosen during implementation; `rt_string_concat` is the expected shape) that:

- accepts two source strings,
- allocates a fresh destination string with combined length,
- copies bytes in order,
- returns an owned result under the existing runtime/string conventions.

Lower string `+` in `backend.l0` through that helper, and keep `c_emitter.l0` responsible only for the call shape rather
than duplicating string-memory management inline.

### Phase 3: Tests

1. Add positive typing coverage for `string + string`.
2. Add negative coverage for mixed operands (`string + int`, `int + string`, `string + null`, and similar rejected
   forms).
3. Add backend/emitter assertions that string `+` dispatches to the concatenation helper rather than numeric `+`.
4. Add an end-to-end runtime fixture that exercises empty-string, single-byte, and multi-segment concatenation.

### Phase 4: Docs

1. Update `l1/docs/reference/design-decisions.md` to state that `string + string` yields a fresh owned string result.
2. Update `l1/docs/roadmap.md` so the string-operators backlog entry points at this plan instead of describing
   concatenation as unplanned backlog only.

## Diagnostics

1. No parser or signature diagnostics are expected for this feature because the surface reuses the existing `+` grammar.
2. Prefer existing operator/type-mismatch diagnostics for non-string or mixed-string operands.
3. If implementation reveals the need for dedicated user-facing string-concatenation diagnostics, provisionally reserve
   `TYP-0720` to `TYP-0739`. Re-check the live catalog at implementation time before assigning final numbers; if any of
   those slots were taken in the meantime, choose a different free block then.

## Non-Goals

1. String concatenation assignment such as `+=`.
2. Implicit formatting or coercion from non-string operands.
3. Builder/rope APIs or any broader string-performance redesign.
4. Named-argument or variadic-call interactions with concatenation.

## Verification Criteria

1. `string + string` type-checks and produces `string`.
2. Generated C routes string `+` through the dedicated helper path rather than numeric `+`.
3. The runtime helper returns a fresh owned result and does not regress ARC/memory behavior.
4. Existing numeric `+` behavior remains unchanged.
5. `l1/docs/reference/design-decisions.md` and `l1/docs/roadmap.md` reflect the newly planned concatenation surface.
