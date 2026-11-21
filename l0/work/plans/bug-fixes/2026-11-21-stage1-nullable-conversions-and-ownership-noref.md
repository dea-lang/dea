# Bug Fix Plan

## Lower nullable conversions and release optional payloads

- Date: 2026-11-21
- Status: Draft
- Title: Lower nullable conversions and release optional payloads
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: Type compatibility, expected-type lowering, ARC temporaries, and drop
- Modules:
  - `l0/compiler/stage1_py/l0_types.py`
  - `l0/compiler/stage1_py/l0_check_compat.py`
  - `l0/compiler/stage1_py/l0_backend_state.py`
  - `l0/compiler/stage1_py/l0_backend_convert.py`
  - `l0/compiler/stage1_py/l0_backend_lowering.py`
  - `l0/compiler/stage1_py/l0_backend_lifetime.py`
  - `l0/compiler/stage2_l0/src/expr_types/compat.l0`
  - `l0/compiler/stage2_l0/src/backend/convert.l0`
  - `l0/compiler/stage2_l0/src/backend/lowering.l0`
  - `l0/compiler/stage2_l0/src/backend/lifetime.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/integration/test_implicit_conversions.py`
  - `l0/compiler/stage1_py/tests/type_checker/test_expr_typechecker_casts_and_nullability.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage1_py/tests/backend/test_trace_arc.py`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py`
- Related:
  - [l0/docs/decisions/0007-nullability-and-casts.md](../../../../l0/docs/decisions/0007-nullability-and-casts.md)
  - [l0/docs/reference/ownership.md](../../../../l0/docs/reference/ownership.md)
  - [l0/docs/reference/c-backend-design.md](../../../../l0/docs/reference/c-backend-design.md)
- Repro: Pass a byte variable to an `int?` parameter and compile the generated C. Separately, drop a `new` allocation
  containing a present heap-backed `string?` under ARC and memory tracing.

## Summary

Accepted Stage 1 programs produce incompatible C or `ICE-1090`. Stage 2 loses the expected type of parenthesized nulls
and the initializer in `new S(null)`, aborting generation with `ICE-1292`. Its generated C also initializes a plain
string temporary with an optional-string value on a borrowed call. Dropping a heap-backed optional leaked one string and
zero objects in each stage. Structural equality failed at the Stage 1 helper boundary and passed in Stage 2.

## Fixes and regression tests

1. **Numeric widening and wrapping.** Preserve the two conversions already accepted by the Stage 1 checker:
   `byte -> int?` and `byte? -> int?`. For the former, widen the byte and construct a present integer optional. For the
   latter, evaluate once, carry absence through, and widen only a present payload. The proposed amendment to ADR-0007
   makes this composition explicit. Compile and execute calls and typed local initializers using 0 and 255, a present
   optional byte, and an absent optional byte. Assert the destination's presence and integer value separately. Include
   bare `byte -> int` and identity conversions as controls. Stage 2 already passes `byte -> int?` as an argument and a
   local at 0 and 255. Its checker rejects `byte? -> int?` with `TYP-0312` for a call and `TYP-0310` for a local. The
   general nullable-destination return precedes the optional-to-optional branch in `etc_can_assign`. Record this as a
   contract difference. If L0 adopts lifted widening, run the present/absent tests in both stages, including a
   side-effecting source evaluated once. If Stage 2 keeps explicit handling, test both rejections alongside the
   already-working plain-byte controls.
2. **Parenthesized null.** Carry the destination type through parentheses in both ordinary and owned expected-type
   emission. Compare `f(null)`, `f((null))`, and an `int?` local initialized with nested parentheses. Analysis,
   compilation, and execution must all succeed and observe absence. Keep a negative control for a non-nullable
   destination. Run the same source through the native Stage 2 checker, generator and executable. Cover its separate
   single-value allocation path: `type S = string?;` with `new S(null)` passes checking and aborts generation, while
   `let empty: S = null;` followed by `new S(empty)` works. Pass the resolved pointee type to owned initializer emission
   in `be_emit_new_expr`. Test both initializers plus `new S((null))`, read the slot to verify absence, and drop it.
   Keep this regression independent of cleanup for a present payload.
3. **Owned string argument.** A converted `string?` currently initializes a temporary declared as `l0_string`.
   Materialize the natural string once before wrapping it for the borrowed call, or register a correctly typed optional
   temporary with its matching cleanup. Run `unwrap_or_s(concat_s("a", "b"), "miss")`; require the value `"ab"` and
   balanced ARC/memory traces. Include a borrowed local string control and verify that its original owner remains valid
   after the call. In Stage 2 inspect the post-conversion type passed to `be_materialize_arc_temp`. Require the native
   launcher to compile the call before checking the result and the child trace.
4. **Dropping an optional payload.** Route a nullable value pointee through existing type-directed value cleanup after
   drop-begin validation and before drop-finish. Exercise `type S = string?;` with
   `new S(concat_s("a", "b") as string?)`, followed by `drop`. Verify a heap string was allocated, it was released, and
   the trace checker reports zero leaked strings and objects. Also drop an allocated empty optional and a null pointer;
   neither case may release an absent value. Add these cases to the Stage 2 child ARC regression. Its failing program
   already exits 0, so assert a matching string allocation/free and one object drop as well as trace balance. Initialize
   the absent control from a typed local so the allocation-initializer fix can land independently.
5. **Structural equality.** Use the semantic types' structural equality or cover all supported variants explicitly. Test
   `NullType` and `FuncType` for reflexivity, independently constructed equal signatures, and unequal parameter or
   result types. Include a nested nullable/pointer comparison. Exercise this helper directly; L0 function-pointer code
   generation is outside this fix. Keep Stage 2's successful null and function-signature comparisons as controls.

## Verification

From `l0/`, run the listed Stage 1 pytest modules with `../.venv/bin/python -m pytest -q`. Compile and execute the
conversion regressions through the fixture's host C compiler. For both ownership regressions, use the existing trace-log
checker and retain the generated cleanup excerpt and trace counts as closure evidence. Valid inputs must clear analysis
and generation without an ICE. Run
`make test-stage2 TESTS="expr_types_test backend_test l0c_build_run_test l0c_stage2_arc_trace_regression_test"` from
`l0/`. Check the native child's log with `python3 compiler/stage2_l0/scripts/check_trace_log.py LOG --triage` and run
`make test-stage2-trace` for the ownership changes. Existing type-mismatch diagnostics cover invalid controls.

## ADR Impact

- Decision: Preserve Stage 1's accepted composition of byte widening and value-optional conversion, including absence
  propagation.
  - Scope: L0
  - Disposition: Amend ADR
  - ADR: `l0/docs/decisions/0007-nullability-and-casts.md`
  - Rationale: The accepted ADR describes implicit optional promotion for an identical inner type. The proposed
    amendment records the two numeric cases the checker already accepts.
- Decision: A converted temporary and a dropped optional release the ARC data each owns.
  - Scope: L0
  - Disposition: Covered by ADR
  - ADR: `l0/docs/decisions/0008-arc-ownership-model.md`
  - Rationale: The fixes apply the existing borrowed-parameter, temporary-owner, and slot-cleanup rules to nullable
    payloads.
