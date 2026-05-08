# Bug Fix Plan

## Stage 2 pointer indexing parity and L0 diagnostic wording

- Date: 2026-05-08
- Status: Closed (fixed)
- Title: Restore L0 Stage 2 pointer-indexing parity and align unsupported-indexing diagnostics
- Kind: Bug Fix
- Severity: Critical
- Stage: Shared
- Subsystem: Parser / Type Checker / Stage 2 semantic parity
- Modules:
  - `compiler/stage1_py/l0_parser.py`
  - `compiler/stage1_py/l0_expr_types.py`
  - `compiler/stage1_py/tests/parser/test_parser_types.py`
  - `compiler/stage1_py/tests/type_checker/test_expr_typechecker_ops.py`
  - `compiler/stage2_l0/src/expr_types.l0`
  - `compiler/stage2_l0/src/parser/shared.l0`
  - `compiler/stage2_l0/tests/expr_types_test.l0`
  - `compiler/stage2_l0/tests/fixtures/typing/typing_index_diag_err.l0`
  - `compiler/stage2_l0/tests/l0c_stage2_pointer_indexing_reject_test.py`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - `docs/reference/design-decisions.md`
  - `docs/project-status.md`
- Test modules:
  - `compiler/stage1_py/tests/parser/test_parser_types.py`
  - `compiler/stage1_py/tests/type_checker/test_expr_typechecker_ops.py`
  - `compiler/stage2_l0/tests/expr_types_test.l0`
  - `compiler/stage2_l0/tests/diagnostic_message_parity_test.py`
  - `compiler/stage2_l0/tests/l0c_stage2_pointer_indexing_reject_test.py`
- Related:
  - `l0/docs/reference/design-decisions.md`
  - `l0/docs/project-status.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - `l0/work/plans/bug-fixes/closed/2026-04-03-stage2-diagnostic-code-parity-audit-noref.md`
  - `l0/work/plans/bug-fixes/closed/2026-04-03-stage2-pointer-cast-parity-noref.md`
- Repro:
  ```l0
  fn main() -> int {
      let p = new int;
      p[0] = 41;
      drop p;
      return 0;
  }
  ```
  `./scripts/l0c --gen` rejects this with `TYP-0212`, while `./build/dea/bin/l0c-stage2 --gen` previously accepted it
  and lowered raw-pointer indexing into generated C

## Summary

L0 Stage 2 currently accepts `ptr[i]` on raw pointers even though L0 Stage 1, the L0 design docs, and the L0 project
status all treat indexing as unsupported until real array types exist.

Confirmed drift today:

- Python Stage 1 rejects `int*`, `byte*`, and `string*` indexing with `TYP-0212`.
- Native Stage 2 accepts those same forms.
- Stage 2 lowers them directly to C `base[index]`, including ARC-sensitive `string*` slot replacement and copied-value
  retain behavior.

This plan restores the intended L0 surface by making Stage 2 reject all raw-pointer indexing during expression typing,
with Stage 1 diagnostic-code and message parity. It also tightens the L0 docs so they say plainly that pointer indexing
is not implemented in L0, rather than implying there might already be array-typed indexing targets.

Follow-up scope in the same fix family aligns the shared diagnostic catalog plus the emitted Stage 1 and Stage 2 parser
and type-checker wording with the current language surface:

- `PAR-9401` no longer suggests using pointer indexing as an array substitute.
- `TYP-0211` and `TYP-0212` no longer describe arrays as if they were a current supported indexing target.
- the unsupported-indexing family now consistently says indexing is not yet supported.

L1 remains explicitly out of scope.

## Current State

The intended L0 behavior is already documented:

- `l0/docs/reference/design-decisions.md` says pointer arithmetic is not part of L0 surface semantics and indexing is
  currently rejected for unsupported targets.
- `l0/docs/project-status.md` says arrays/slices are not implemented and unsupported indexing targets are rejected.

Stage 1 matches that contract. For example:

- `let p = new int; p[0] = 41;` is rejected with `TYP-0212`.
- the same rejection happens for `byte*` and `string*` pointer bases.

Stage 2 diverges:

- `compiler/stage2_l0/src/expr_types.l0` currently accepts any non-null pointer base in `etc_infer_index`.
- backend/emitter lowering then treats `EX_INDEX` as ordinary C indexing.
- direct Stage 2 `--gen` therefore exposes a language surface that L0 intentionally retracted early in the project.

Because the default `./scripts/l0c` path is Stage 1, this drift stayed mostly invisible until the repo-local native
Stage 2 binary was probed directly.

The shared diagnostic catalog and parser wording also lagged behind the same language decision:

- `PAR-9401` still told users to use pointers and `[]` indexing in expressions.
- `TYP-0211` / `TYP-0212` still described unsupported indexing in array-oriented terms.

## Root Cause

Pointer indexing appears to have been implemented in the early semantic/backend port path and then left in place after
the L0 language decision moved indexing behind future array work.

The current Stage 2 checker still follows the old rule:

1. require `int` index expressions,
2. reject nullable bases,
3. accept any pointer base and return the pointee type.

That rule is no longer valid for L0. Once Stage 1 retracted pointer indexing, Stage 2 should have switched from
"pointer-shaped bases are indexable" to "no current user-facing type is indexable unless/until arrays are introduced."

The emitted wording drift had the same root cause: diagnostics were left describing an earlier mental model where array
support was more concrete and pointer indexing was still presented as an intended stand-in.

## Scope of This Fix

1. Make L0 Stage 2 reject raw-pointer indexing for all pointer element types, including at least `int*`, `byte*`, and
   `string*`.
2. Reuse Stage 1 diagnostic behavior for indexing:
   - `TYP-0210` for non-`int` index expressions,
   - `TYP-0211` for nullable bases,
   - `TYP-0212` for non-null invalid indexing bases, including pointers and non-pointers.
3. Update the shared diagnostic catalog and the Stage 1/Stage 2 emitted wording so unsupported indexing consistently
   uses "not yet supported" language instead of array-specific guidance.
4. Update `PAR-9401` so it simply reports unsupported array-type syntax instead of directing users toward pointer
   indexing.
5. Update L0 stable docs so they state that pointer indexing is not implemented in L0; avoid wording that suggests array
   indexing already exists for some supported L0 array type.
6. Add regression coverage in Stage 1 message assertions, Stage 2 semantic fixtures, native Stage 2 message parity, and
   direct native Stage 2 compiler execution.
7. Keep L1 unchanged. This plan is L0-local and intentionally does not alter `l1/`.

## Diagnostic-Code Plan

No new diagnostic codes are needed.

This fix should continue using the existing registered diagnostics from the shared catalog:

- `PAR-9401`
- `TYP-0210`
- `TYP-0211`
- `TYP-0212`

Implementation-time rule:

- align Stage 1, Stage 2, and the shared catalog on the final wording:
  - `PAR-9401`: `array types not yet supported`
  - `TYP-0211`: `cannot index into nullable type '...'; indexing is not yet supported`
  - `TYP-0212`: `cannot index into expression of type '...'; indexing is not yet supported`
- do not reserve or introduce any new `TYP-*` block for this plan

## Approach

### 1. Restore Stage 1 checker semantics in `etc_infer_index`

Update `compiler/stage2_l0/src/expr_types.l0` so `EX_INDEX` no longer treats raw pointers as indexable.

Target behavior:

1. still type-check the index expression first and emit `TYP-0210` when needed,
2. keep the nullable-base fast path as `TYP-0211`,
3. reject plain pointer bases with `TYP-0212`,
4. leave no Stage 2 semantic path where `ptr[i]` produces the pointee type in L0.

The fix should be checker-side only. Do not add compensating backend logic for invalid pointer indexing; the expression
must fail before lowering.

### 2. Align parser and type-checker diagnostics with the intended rule

Update the shared catalog plus the emitted Stage 1 and Stage 2 diagnostics so they no longer imply that pointer indexing
is the supported fallback while arrays are absent.

Target wording:

- `PAR-9401`: `array types not yet supported`
- `TYP-0211`: `cannot index into nullable type '...'; indexing is not yet supported`
- `TYP-0212`: `cannot index into expression of type '...'; indexing is not yet supported`

Keep `TYP-0212` as the single generic invalid-index-base code. Do not split pointer and non-pointer invalid bases into
different diagnostics as part of this fix.

### 3. Tighten the L0 docs to match the actual intended rule

Update the L0 stable docs so they describe the current language surface precisely:

- pointer indexing is not implemented in L0
- array and slice types do not exist in L0 today
- the presence of indexing syntax in the parser/AST is an internal/front-end detail, not a user-facing supported
  operation

In particular, avoid wording that reads like "indexing is allowed on arrays but rejected on non-array types," because no
such L0 array surface exists.

### 4. Keep parser and AST surface unchanged

This is not a parser or grammar rollback plan.

- The parser may continue to build `EX_INDEX`.
- parser tests that only check syntax shape can remain valid.
- the user-facing semantic rule is what must be restored.

That keeps the frontend shape available for future array work without continuing to expose raw-pointer indexing as valid
L0 code today.

### 5. Preserve backend stability by making `EX_INDEX` user-inaccessible again

No direct backend/emitter change is required if the checker blocks pointer indexing first.

However, the implementation should audit whether any current Stage 2 tests or self-hosted compiler sources rely on
pointer indexing being accepted. If any such use exists, replace it with supported L0 constructs rather than preserving
the drift.

### 6. Add message and built-artifact regressions

Add regression coverage at four levels:

- Stage 1 parser/type-checker message assertions
- fixture-backed type-checker tests in `compiler/stage2_l0/tests/expr_types_test.l0`
- native Stage 2 diagnostic-message parity coverage
- one direct built-artifact regression that invokes the native Stage 2 compiler binary on a temporary source file and
  asserts rejection, because that direct path is how the bug was rediscovered

The direct built-artifact regression does not need to reuse `l0c_codegen_test.py` if a dedicated focused Python test is
clearer. A small standalone test in the style of `l0c_stage2_cleanup_policy_ice_test.py` is acceptable; if that route is
chosen, place it in a new focused file rather than extending the unrelated cleanup-policy regression.

## Tests

### Semantic fixture coverage

Extend `compiler/stage2_l0/tests/fixtures/typing/typing_index_diag_err.l0` and
`compiler/stage2_l0/tests/expr_types_test.l0` with explicit pointer-base rejection cases:

1. `int*` base indexed with `0` -> `TYP-0212`
2. `byte*` base indexed with `0` -> `TYP-0212`
3. `string*` base indexed with `0` -> `TYP-0212`
4. nullable pointer base still reports `TYP-0211`
5. non-`int` index still reports `TYP-0210`
6. legacy Stage 2 acceptance of pointer indexing is gone

### Stage 1 wording coverage

Update Stage 1 parser/type-checker tests to assert the exact final wording for:

1. `PAR-9401`
2. `TYP-0211`
3. `TYP-0212` on a pointer base
4. `TYP-0212` on a non-pointer base

### Diagnostic wording coverage

Extend the native Stage 2 message-parity coverage so future drift on `PAR-9401`, `TYP-0211`, and `TYP-0212` does not
regress silently.

### Native Stage 2 integration coverage

Add one focused Python regression that:

1. materializes a small inline repro program containing `ptr[i]`,
2. runs the repo-local native Stage 2 compiler directly with `--gen` or `--check`,
3. asserts nonzero exit,
4. asserts `TYP-0212` is present in stderr/stdout diagnostics,
5. asserts the emitted text includes `indexing is not yet supported`,
6. keeps the failing artifacts when the assertion fails.

At minimum, the direct repro should use `int*`. If the test stays cheap, include `byte*` and `string*` variants too so
the regression is explicitly generic over pointer element type.

## Verification

Minimum verification during implementation:

```bash
make DEA_BUILD_DIR=build/dev-dea test-stage2 TESTS="expr_types_test"
../.venv/bin/python -m pytest compiler/stage1_py/tests/parser/test_parser_types.py compiler/stage1_py/tests/type_checker/test_expr_typechecker_ops.py -k "array_syntax_rejected or test_index_"
python compiler/stage2_l0/tests/diagnostic_message_parity_test.py
python compiler/stage2_l0/tests/l0c_stage2_pointer_indexing_reject_test.py
```

Final verification:

```bash
make DEA_BUILD_DIR=build/dev-dea test-stage2
make DEA_BUILD_DIR=build/dev-dea test-stage2-trace
make DEA_BUILD_DIR=build/dev-dea triple-test
```

Acceptance checks:

1. Direct native Stage 2 compilation rejects `ptr[i]` for `int*`, not just via the Stage 1 wrapper path.
2. Stage 2 no longer accepts `byte*` or `string*` indexing either.
3. Stage 2 emits the Stage 1 indexing diagnostics and message text.
4. `l0/docs/reference/design-decisions.md` and `l0/docs/project-status.md` now state the stronger rule that pointer
   indexing is not implemented in L0.
5. No current self-hosting or trace validation gate regresses after the checker-side rollback.

## Non-goals

1. Implementing arrays, slices, or any new indexable L0 type.
2. Changing L1 behavior. L1 can intentionally keep pointer indexing for its roadmap work.
3. Removing `EX_INDEX` from the parser or AST.
4. Introducing new diagnostics or a new unsafe surface in L0.

## Assumptions

- Python Stage 1 remains the behavioral oracle for current released L0 semantics.
- L0 pointer indexing was intentionally retracted and should stay unavailable until a future array feature explicitly
  reintroduces safe indexing through a different plan.
- The current L0 stable docs are already correct; this work is an implementation parity repair, not a language-design
  change.
