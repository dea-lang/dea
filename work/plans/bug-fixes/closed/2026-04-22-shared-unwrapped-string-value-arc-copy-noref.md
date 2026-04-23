# Bug Fix Plan

## Shared unwrapped string scrutinee ARC copy

- Date: 2026-04-22
- Status: Completed
- Title: Preserve ARC ownership when unwrapped strings are copied into match and case scrutinees
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Python Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L1 `std.types` exposed the runtime crash, and equivalent traced repros confirm that L0 Python Stage 1 should
  remain the behavioral oracle for the shared fix
- Porting rule: Fix L0 Python Stage 1 first, port mechanically to L0 Stage 2, then port the homologous self-hosted
  change to L1 Stage 1 while preserving backend ownership parity
- Target status:
  - L0 Python Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Backend ARC lowering / optional string unwrap / match and case scrutinee cleanup
- Modules:
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage2_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_trace_arc.py`
  - `l0/compiler/stage2_l0/tests/l0c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/compiler/shared/l1/stdlib/std/types.l1`
  - `l0/docs/reference/ownership.md`
  - `l1/docs/reference/ownership.md`
- Smallest repro:
  ```l1
  module repro_case;

  import std.string;

  func main() -> int {
      let opt: string? = concat_s("o", "k") as string?;
      case (opt as string) {
          "ok" => { return 0; }
          else { return 1; }
      }
  }
  ```
- `std.types`-shaped repro:
  ```l1
  module repro;

  import std.string;

  enum Value {
      String(s: string);
      OptString(s: string?);
  }

  func get_opt_value(v: Value) -> Value? {
      match (v) {
          OptString(x) => {
              if (x == null) {
                  return null;
              }
              return String(x as string);
          }
          _ => { return v; }
      }
  }

  func main() -> int {
      let unwrapped = get_opt_value(OptString(concat_s("o", "k") as string?));
      if (unwrapped == null) {
          return 1;
      }
      match (unwrapped as Value) {
          String(s) => { return 0; }
          _ => { return 2; }
      }
  }
  ```

## Summary

Unwrapping an optional string into a `match` or `case` scrutinee can produce a value that later double-releases or
releases after free. The same missing ownership stabilization also affects unwrapping `Value?` into a string-bearing
enum value and matching it by value.

The failure was observed while reviewing `l1/compiler/shared/l1/stdlib/std/types.l1`: `get_opt_value(OptString(...))`
returns `String(x as string)`, and matching the returned `Value.String` can abort at runtime with an invalid string
refcount state.

## Current State

Known L1 observations:

- `std.types` checks and a minimal import/build smoke test pass.
- Direct `OptString` construction plus `is_optional` / `is_null` checks pass.
- Direct `String(concat_s(...))` construction and matching pass.
- `get_opt_value(OptInt(...))` passes.
- `get_opt_value(OptString(null))` passes.
- `get_opt_value(OptString(concat_s(...) as string?))` followed by matching the returned `Value.String` can crash with
  `_rt_free_string: invalid string refcount state`.

Initial trace investigation confirmed the issue is shared:

- L0 Python Stage 1: affected; trace shows one retain followed by three releases of the same heap string in the enum
  repro, and `case (opt as string)` releases the same string twice.
- L0 Stage 2: affected; the enum repro aborts with `panic-invalid-state`, and `case (opt as string)` emits the same
  invalid final release pattern.
- L1 Stage 1: affected; the enum repro emits the same invalid final release pattern, and `case (opt as string)` aborts
  with `panic-invalid-state`.

Across all three targets, the traced enum repro follows the same ownership pattern:

1. one retain for the `String(x as string)` return value;
2. one release for the source optional or returned temporary owner;
3. one release for `_scrutinee`;
4. one final release against already-freed storage.

## Root Cause

- The `match` and `case` lowering paths initialize `_scrutinee` directly from `be_emit_expr(...)` / `_emit_expr(...)`,
  then mark `_scrutinee` as owned for rvalue ARC cleanup.
- When the scrutinee expression is an unwrap cast from a place, such as `opt as string` or `unwrapped as Value`, the
  generated C copies borrowed payload storage into `_scrutinee` without using the existing copy-with-retains helper.
- Matching `unwrapped as Value` copies the wrapped enum payload into a scrutinee without a corresponding deep retain for
  string-bearing variants, while `case (opt as string)` copies a plain string without retaining it.
- Cleanup for the source `Value?`, match scrutinee, and parameter copy may each release the same string unless the copy
  is ownership-stabilized.
- L0 and L1 share the same backend ownership gap because L1 Stage 1 is seeded from the L0 Stage 2 backend, while L0
  Stage 1 shows the same missing-retain behavior and remains the ownership oracle.

## Scope of This Fix

In scope:

- Reproduce and trace the minimal failing ownership path in L1.
- Check whether the equivalent L0 program fails in L0 Python Stage 1 and L0 Stage 2.
- Fix the shared backend ownership rule so scrutinee copies from place-like unwrap casts retain strings or nested
  string-bearing fields before any source cleanup can release them.
- Add focused ARC/runtime regressions that fail without the fix.

Not in scope:

- Changing nullable semantics or `string?` unwrap syntax.
- Changing the public shape of `std.types` except for temporary workarounds needed to keep the module usable.
- New diagnostic codes; this is runtime ownership lowering, not user-facing diagnostics.

## Implementation

### Phase 1 - L0 Python Stage 1

1. Update `match` and `case` scrutinee lowering in `l0/compiler/stage1_py/l0_backend.py` so `_scrutinee` initialization
   keeps the existing raw-expression lowering, but immediately retains `_scrutinee` itself whenever the scrutinee is an
   unwrap cast from a place and carries ARC data.
2. Preserve the current borrowed pattern bindings: the fix belongs at `_scrutinee` initialization, not in arm-local
   payload bindings.
3. Keep the ownership behavior aligned with `l0/docs/reference/ownership.md`: copying a `string` or string-bearing enum
   into a new owner must retain before any source cleanup can run.

### Phase 2 - L0 Stage 2

1. Port the Stage 1 `_scrutinee` retain rule mechanically into `l0/compiler/stage2_l0/src/backend.l0`.
2. Keep the Stage 2 generated C shape aligned with Stage 1, especially for unwrap casts from places such as
   `opt as string` and `unwrapped as Value`.

### Phase 3 - L1 Stage 1

1. Port the Stage 2 fix mechanically into `l1/compiler/stage1_l0/src/backend.l0`.
2. Verify that the `std.types` path and the standalone `case (opt as string)` repro both stop double-releasing the same
   string.

### Phase 4 - Regression Coverage

1. Add a focused ARC regression for the smallest `case (opt as string)` repro in each affected target.
2. Add regression coverage for the enum `OptString` to `String(x as string)` path, including the returned `Value?`
   matched by value.
3. Add or update generated-C assertions if the retained `_scrutinee` initialization can be checked robustly.

## Verification

```bash
cd l0 && ../.venv/bin/python -m pytest compiler/stage1_py/tests/backend/test_trace_arc.py -q
cd l0 && ../.venv/bin/python compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py
cd l0 && make test-stage2 TESTS="l0c_lib_test"
cd l1 && ../.venv/bin/python compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py
cd l1 && make test-stage1 TESTS="l0c_lib_test"
make clean test-all
```

## Outcome

- Fixed shared `match` / `case` scrutinee ARC handling by retaining `_scrutinee` when an unwrap cast from a place copies
  ARC-managed data into a new owner.
- Ported the same retain rule across L0 Python Stage 1, L0 Stage 2, and L1 Stage 1.
- Added focused ARC regressions for `case (opt as string)` and for matching the returned `Value?` from an
  `OptString -> String(x as string)` path.
- Added L1 driver coverage through `std.types` with `std_types_opt_string_main`.

## Validation Run

Completed on 2026-04-23:

```bash
cd l0 && ../.venv/bin/python -m pytest compiler/stage1_py/tests/backend/test_trace_arc.py -q
cd l0 && ../.venv/bin/python compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py
cd l0 && make test-stage2 TESTS="l0c_lib_test"
cd l1 && ../.venv/bin/python compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py
cd l1 && make test-stage1 TESTS="l0c_lib_test"
make clean test-all
```

## Verification Criteria

- The minimal `case (opt as string)` fixture runs without invalid refcount failures.
- The minimal `OptString(concat_s(...)) -> String(x as string)` fixture runs without invalid refcount failures.
- ARC trace triage reports balanced string retains/releases for the minimal fixture.
- A `Value?` returned from a function can be matched by value without releasing the same string twice.
- A direct `std.types.get_opt_value(OptString(...))` usage runs successfully once `std.types` is included.
- Relevant normal and trace suites pass for every affected target.
