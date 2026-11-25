# Bug Fix Plan

## Repair contextual null lowering, optional ownership and structural type equality

- Date: 2026-11-25
- Status: Completed
- Title: Repair contextual null lowering, optional ownership and structural type equality
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: Type compatibility, expected-type lowering, ARC temporaries, and drop
- Modules:
  - `l0/compiler/stage1_py/l0_backend_initializers.py`
  - `l0/compiler/stage1_py/l0_backend_state.py`
  - `l0/compiler/stage1_py/l0_backend_lowering.py`
  - `l0/compiler/stage1_py/l0_backend_lifetime.py`
  - `l0/compiler/stage2_l0/src/backend/state.l0`
  - `l0/compiler/stage2_l0/src/backend/initializers.l0`
  - `l0/compiler/stage2_l0/src/backend/lowering.l0`
  - `l0/compiler/stage2_l0/src/backend/lifetime.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/integration/test_implicit_conversions.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage1_py/tests/backend/test_trace_arc.py`
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py`
- Related:
  - [l0/docs/decisions/0007-nullability-and-casts.md](../../../../../l0/docs/decisions/0007-nullability-and-casts.md)
  - [l0/docs/reference/ownership.md](../../../../../l0/docs/reference/ownership.md)
  - [l0/docs/reference/c-backend-design.md](../../../../../l0/docs/reference/c-backend-design.md)
- Repro: Pass `(null)` to an `int?` parameter and generate C. Separately, drop an allocated present heap-backed
  `string?` under ARC and memory tracing.

## Findings and implementation

Both L0 backends recognize a null literal through grouping parentheses and emit the destination's absence
representation. This covers borrowed and owned contexts, comparisons, casts and file-scope initializers. Single-value
allocation already supplied the resolved pointee type in both stages. The regression reads back slots initialized with
`null`, `(null)` and a typed absent local. The checker still rejects an `int` initialized with `((null))` with
`TYP-0310`.

For a borrowed argument such as `unwrap_or_s(concat_s("a", "b"), "miss")`, the natural source expression determines
whether it produces an owner. Both backends declare and clean up its temporary using the converted parameter type. A
borrowed string local passed to the same function keeps its owner.

Dropping a heap-backed `string?` previously freed the slot and leaked one string in each stage. Both backends now use
type-directed value cleanup on the validated pointee. The present-slot fixture emits this cleanup before drop finish:

```c
if ((l0_drop_3 != NULL))
{
    if ((*l0_drop_3).has_value) {
        rt_string_release((*l0_drop_3).value);
    }
}
_rt_drop_finish_impl((void*)(l0_drop_3), __FILE__, __LINE__);
```

Stage 1 backend type comparison now uses semantic dataclass equality, including `NullType` and `FuncType`. Direct tests
cover reflexivity, separately constructed signatures with nested nullable pointer parameters, and unequal parameters and
results. Stage 2 compares its own independently allocated types in the backend test.

The original numeric widening finding is tracked in
[work/plans/features/2026-11-25-shared-nullable-numeric-widening-noref.md][widening].

## ADR Impact

- Decision: A converted temporary and a dropped optional release the ARC data each owns.
  - Scope: L0
  - Disposition: Covered by ADR
  - ADR: `l0/docs/decisions/0008-arc-ownership-model.md`
  - Rationale: The fixes apply the existing borrowed-parameter, temporary-owner, and slot-cleanup rules to nullable
    payloads.

## Verification

Focused macOS checks used Apple Clang. Both stages compiled and ran the contextual-null fixture and reported `TYP-0310`
for its invalid control. The Stage 1 selection passed 24 cases. The Stage 2 `backend_test` passed under ARC and memory
tracing. Each stage's child-program trace checker reported zero errors, zero leaked strings and zero leaked objects for
both ownership fixtures.

| Fixture       | Observed behavior in each stage                                                                                                    |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Borrowed call | Two heap strings allocated and freed. Both calls returned the expected text and the borrowed local remained readable.              |
| Optional drop | One heap string allocated and freed. The present and absent slots each had one object drop. Dropping the null pointer was a no-op. |

To reproduce the focused checks from `l0/`:

```sh
../.venv/bin/python -m pytest -q compiler/stage1_py/tests/integration/test_implicit_conversions.py \
    compiler/stage1_py/tests/backend/test_codegen_semantics.py compiler/stage1_py/tests/backend/test_trace_arc.py \
    compiler/stage1_py/tests/type_checker/test_expr_typechecker_casts_and_nullability.py \
    -k 'contextual_null or structural_type_equality or nullable_ownership or parenthesized or comparison_temporary or drop_begin or null_to_optional or lifted_widening'
make test-stage2-trace TESTS=backend_test
build/dea/bin/l0c-stage2 --run tests/fixtures/contextual_null/contextual_null.l0
build/dea/bin/l0c-stage2 --check tests/fixtures/contextual_null/invalid.l0  # expect TYP-0310
trace_dir=$(mktemp -d)
for case in argument drop; do
    build/dea/bin/l0c-stage2 --run --trace-arc --trace-memory \
        "tests/fixtures/nullable_ownership/$case/main.l0" 2>"$trace_dir/$case.trace" || exit 1
    python3 compiler/stage2_l0/scripts/check_trace_log.py --triage "$trace_dir/$case.trace" || exit 1
done
```

[widening]: ../../../../../work/plans/features/2026-11-25-shared-nullable-numeric-widening-noref.md
