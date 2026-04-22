# Bug Fix Plan

## Shared optional-wrapper typedef ordering

- Date: 2026-04-22
- Status: Completed
- Title: Emit user-defined optional wrapper typedefs before dependent C type definitions across L0 and L1 backends
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Python Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L1 Stage 1 exposed the bug through `std.types`; L0 Python Stage 1 remains the behavioral oracle for the shared
  backend rule
- Porting rule: Fix the shared ordering rule in L0 Python Stage 1 first, port mechanically to L0 Stage 2, then port the
  homologous self-hosted change into L1 Stage 1 while the backend structure remains aligned
- Target status:
  - L0 Python Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Backend C codegen / nullable value type lowering
- Modules:
  - `l0/compiler/stage1_py/l0_c_emitter.py`
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage2_l0/src/c_emitter.l0`
  - `l0/compiler/stage2_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_codegen_type_ordering.py`
  - `l0/compiler/stage2_l0/tests/l0c_lib_test.l0`
  - `l0/compiler/stage2_l0/tests/fixtures/driver/optional_struct_field_order_main.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/fixtures/driver/optional_struct_field_order_main.l1`
- Related:
  - `l1/compiler/shared/l1/stdlib/std/types.l1`
- Repro:
  ```l0
  module optional_struct_field_order_main;

  struct Token {}

  enum Wrapped {
      Some(value: Token?);
  }

  func main() -> int {
      return 0;
  }
  ```

## Summary

The C backends collect nullable-by-value wrapper typedefs for `T?`, but split emission into only two phases:

1. early wrappers whose inner types are builtins, before user type definitions;
2. late wrappers whose inner types are user-defined structs or enums, after every user type definition.

That ordering fails for a user-defined type whose C definition contains an optional wrapper for an already-defined user
type, such as an enum payload `Some(value: Token?)`. The generated C references `l0_opt_s_...Token` or
`dea_opt_s_...Token` inside the dependent type definition before the wrapper typedef has been emitted.

## Current State

The bug was first observed while reviewing `l1/compiler/shared/l1/stdlib/std/types.l1`, where `Value.OptUnit` used
`std.unit::Unit?`. A direct `--check` passed, but compiling a program that merely imported `std.types` failed during C
compilation because the generated enum payload used `dea_opt_s_dea_std_unit_Unit` before its typedef appeared.

The same two-phase wrapper strategy exists in:

- L0 Python Stage 1;
- L0 Stage 2;
- L1 Stage 1, seeded from the L0 Stage 2 backend.

## Root Cause

The dependency-ordered type-definition pass correctly emits the wrapped user type before any type that contains it by
value. However, the optional wrapper for that wrapped type is not emitted as part of the same readiness boundary. It is
deferred to the late optional-wrapper block, after all user type definitions, which is too late for dependent
struct/enum definitions that need the wrapper as a field type.

Forward declarations cannot fix this: the generated C field type is a typedef name, not `struct ...`, and C requires the
typedef to exist before it is used as a field type.

## Scope of This Fix

In scope:

- Share the wrapper typedef emission path so duplicate emission remains guarded by the existing `opt_emitted` tracking.
- Emit a collected optional wrapper immediately after the concrete struct or enum it wraps is defined.
- Keep the existing late pass as a fallback for collected user-defined wrappers not emitted during type-definition
  traversal.
- Add regressions that compile or run the minimal `struct Token {}; enum Wrapped { Some(value: Token?); }` shape.
- Port the same rule across L0 Python Stage 1, L0 Stage 2, and L1 Stage 1.

Not in scope:

- New diagnostic codes; this is a backend C emission ordering bug.
- Changes to nullable semantics, wrapper layout, or niche-nullable pointer representation.
- Changes to type dependency analysis beyond the existing dependency-ordered type-definition pass.
- Resolving unrelated import-shadow warnings in `std.types`.

## Approach

### Phase 1 — L0 Python Stage 1

Files:

- `l0/compiler/stage1_py/l0_c_emitter.py`
- `l0/compiler/stage1_py/l0_backend.py`

Implementation:

1. Extract one helper that emits a collected optional-wrapper typedef and records it in `_opt_emitted`.
2. Add `emit_optional_wrapper_for_defined_type(inner: Type)`, which computes the wrapper name for a just-defined struct
   or enum and emits the wrapper if it was collected.
3. After `emit_struct(...)` and `emit_enum(...)` in dependency-ordered type emission, call the new helper with
   `StructType(module_name, type_name)` or `EnumType(module_name, type_name)`.
4. Keep `emit_optional_wrappers(early=False)` after type definitions so late emission remains harmless and idempotent.

### Phase 2 — L0 Stage 2

Files:

- `l0/compiler/stage2_l0/src/c_emitter.l0`
- `l0/compiler/stage2_l0/src/backend.l0`

Port the same structure mechanically:

1. Add `cem_emit_optional_wrapper`.
2. Add `cem_emit_optional_wrapper_for_defined_type`.
3. Call it after `cem_emit_struct` and `cem_emit_enum` in `be_emit_type_definitions`.
4. Leave `cem_emit_optional_wrappers(..., false)` in place as an idempotent fallback.

### Phase 3 — L1 Stage 1

Files:

- `l1/compiler/stage1_l0/src/c_emitter.l0`
- `l1/compiler/stage1_l0/src/backend.l0`

Apply the homologous Stage 2 port, changing only naming/runtime prefixes already owned by the L1 backend.

### Phase 4 — Regression Coverage

L0 Python Stage 1:

- Extend `test_value_optional_creates_dependency` in
  `l0/compiler/stage1_py/tests/backend/test_codegen_type_ordering.py`.
- Assert the wrapped type definition precedes the optional wrapper typedef and the wrapper precedes the dependent type
  definition.
- Compile the generated C.

L0 Stage 2 and L1 Stage 1:

- Add `optional_struct_field_order_main` driver fixtures.
- Run the fixture through the existing `l0c_lib_test` / `l1c` library test harnesses in `--run` mode.

## Verification

```bash
make clean test-all
cd l0 && ../.venv/bin/python -m pytest compiler/stage1_py/tests/backend/test_codegen_type_ordering.py -q
cd l0 && make test-stage1
cd l0 && make test-stage2 TESTS="c_emitter_test l0c_lib_test"
cd l0 && make test-stage2
cd l0 && make check-examples
cd l1 && make test-stage1 TESTS="c_emitter_test l0c_lib_test"
cd l1 && make test-stage1
```

## Outcome

- Implemented immediate collected optional-wrapper emission after the concrete wrapped struct or enum is defined in L0
  Python Stage 1, L0 Stage 2, and L1 Stage 1.
- Added generated-C ordering coverage for L0 Python Stage 1 and `--run` driver fixtures for L0 Stage 2 and L1 Stage 1.
- Confirmed a minimal executable importing `std.types` builds after the L1 Stage 1 backend fix; the `RES-0021`
  import-shadow warning remains unrelated.

## Validation Run

Completed on 2026-04-22:

```bash
cd l0 && ../.venv/bin/python -m pytest compiler/stage1_py/tests/backend/test_codegen_type_ordering.py -q
cd l0 && make test-stage1
cd l0 && make test-stage2 TESTS="c_emitter_test l0c_lib_test"
cd l0 && make test-stage2
cd l0 && make check-examples
cd l1 && make test-stage1 TESTS="c_emitter_test l0c_lib_test"
cd l1 && make test-stage1
cd l1 && build/dea/bin/l1c-stage1 --build <minimal executable importing std.types>
cd l1 && build/dea/bin/l1c-stage1 --run -P compiler/stage1_l0/tests/fixtures/driver optional_struct_field_order_main
cd l1 && build/dea/bin/l1c-stage1 --check -S compiler/shared/l1/stdlib std.types
```

## Verification Criteria

- The minimal `Token?` payload fixture compiles and runs under L0 Stage 2 and L1 Stage 1.
- L0 Python Stage 1 generated C orders `struct Token`, `l0_opt_s_...Token`, then the dependent type that uses the
  wrapper.
- A minimal executable importing `std.types` builds after the L1 Stage 1 fix.
- Existing early builtin wrappers still emit before user type definitions.
- The late wrapper pass remains idempotent and emits no duplicate typedefs for wrappers already emitted after their
  wrapped type definitions.
