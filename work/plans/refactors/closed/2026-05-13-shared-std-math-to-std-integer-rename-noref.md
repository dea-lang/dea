# Refactor Plan

## Rename shared `std.math` to `std.integer`

- Date: 2026-05-13
- Status: Completed
- Title: Rename shared `std.math` to `std.integer`
- Kind: Refactor
- Severity: Medium
- Stage: Shared
- Scope: Shared
- Targets:
  - `l0` stdlib / compiler / docs / tests
  - `l1` stdlib / compiler / docs / tests
- Origin: shared stdlib numeric-module naming, with `std.real` kept as the floating-point module and the integer helper
  module renamed once at the root
- Porting rule: mechanical parity across L0 and L1
- Target status:
  - `l0`: Pending
  - `l1`: Pending
- Subsystem: Stdlib / imports / docs / tests
- Modules:
  - `l0/compiler/shared/l0/stdlib/std/integer.l0`
  - `l0/compiler/shared/l0/stdlib/std/text.l0`
  - `l0/compiler/shared/l0/stdlib/std/time.l0`
  - `l0/compiler/stage2_l0/src/diag_print.l0`
  - `l0/compiler/stage2_l0/tests/math_test.l0`
  - `l0/compiler/stage2_l0/tests/fixtures/math_runtime/*.l0`
  - `l0/compiler/stage1_py/tests/backend/test_math_runtime.py`
  - `l0/docs/reference/standard-library.md`
  - `l0/docs/reference/design-decisions.md`
  - `l0/docs/project-status.md`
  - `l1/compiler/shared/l1/stdlib/std/integer.l1`
  - `l1/compiler/shared/l1/stdlib/std/text.l1`
  - `l1/compiler/shared/l1/stdlib/std/time.l1`
  - `l1/compiler/stage1_l0/src/diag_print.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/tests/math_test.l0`
  - `l1/compiler/stage1_l0/tests/math_runtime_compile_test.l0`
  - `l1/compiler/stage1_l0/tests/fixtures/io_runtime/io_numeric_main.l1`
  - `l1/compiler/stage1_l0/tests/fixtures/math_runtime/*.l0`
  - `l1/compiler/stage1_l0/tests/fixtures/math_runtime/*.l1`
  - `l1/docs/reference/standard-library.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/reference/c-backend-design.md`
  - `l1/docs/specs/compiler/abi.md`
  - `l1/docs/specs/compiler/module-interface-format.md`
  - `l1/docs/specs/compiler/module-visibility-and-imports.md`
  - `l1/docs/project-status.md`
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/0001-separate-compilation-and-linking.md`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_math_runtime.py`
  - `l0/compiler/stage2_l0/tests/math_test.l0`
  - `l1/compiler/stage1_l0/tests/math_test.l0`
  - `l1/compiler/stage1_l0/tests/math_runtime_compile_test.l0`
- Related:
  - `work/plans/features/closed/2026-04-14-shared-std-math-int-surface-noref.md`
  - `l1/work/plans/features/closed/2026-04-14-l1-std-math-wide-integer-followup-noref.md`
  - `l1/work/plans/features/closed/2026-04-14-l1-std-real-module-noref.md`
  - `work/plans/refactors/closed/2026-05-08-sys-memory-rename-noref.md`
- Repro: `rg -n "std\\.math" --glob '!**/closed/**' l0 l1`

## Summary

`std.integer` is now the public integer-helper module in both L0 and L1, while `std.real` already owns floating-point
helpers in L1. This refactor replaced the broader `std.math` name so the active tree matches the established split
between integer and floating-point helper surfaces.

This refactor renames the shared module path from `std.math` to `std.integer` across L0 and L1. It keeps `std.real`
unchanged, does not alter any helper names or semantics inside the module, and treats the rename as a hard source-level
rename with no compatibility shim.

## Current State

1. `l0/compiler/shared/l0/stdlib/std/integer.l0` and `l1/compiler/shared/l1/stdlib/std/integer.l1` both declare
   `module std.integer;`.
2. The module contents are integer-focused in both trees; L1 additionally carries `_ui`, `_l`, and `_ul` helper families
   in the same module.
3. `std.text`, `std.time`, compiler support code, and dedicated math fixtures/tests in both trees import `std.integer`
   directly.
4. L0 active docs describe `std.integer` as the shared integer helper module.
5. L1 active docs, specs, roadmap entries, and ABI/mangling examples use `std.integer` and `__deaM3std7integer` as the
   canonical integer-module examples.
6. `std.real` is already the documented floating-point module in L1 and should remain unchanged.

## Goal

1. Rename the shared public module path from `std.math` to `std.integer` in both L0 and L1.
2. Update all active imports, qualified references, file/module declarations, and current-state docs to use
   `std.integer`.
3. Keep the module contents, helper spellings, and integer/floating-point split unchanged.
4. Preserve `std.real` and `sys.real` exactly as they are today.

## Defaults Chosen

1. The new shared module name is `std.integer`.
2. `std.real` stays unchanged.
3. This is a naming-only refactor; no helper behavior, signatures, or ownership rules change.
4. No compatibility module, alias import, or transition shim remains in active code.
5. Historical closed plans may keep historical `std.math` references unless a live current-state document would become
   misleading.
6. Active L1 specs and ABI examples should be updated because module paths are canonical identities in that subtree.

## Implementation Phases

### Phase 1: Rename the shared stdlib modules

1. Move `l0/compiler/shared/l0/stdlib/std/math.l0` to `l0/compiler/shared/l0/stdlib/std/integer.l0` and change the
   module declaration to `module std.integer;`.
2. Move `l1/compiler/shared/l1/stdlib/std/math.l1` to `l1/compiler/shared/l1/stdlib/std/integer.l1` and change the
   module declaration to `module std.integer;`.
3. Keep all public helper names and implementations inside the modules unchanged.

### Phase 2: Update active consumers

1. Replace `import std.math;` with `import std.integer;` in active L0 and L1 stdlib modules, compiler sources, tests,
   and fixtures.
2. Replace active qualified references such as `std.math::abs` with `std.integer::abs`.
3. Update comments in active source files when they use `std.math` as an example module name.

### Phase 3: Refresh active documentation and examples

1. Update L0 current-state docs so the integer helper module is documented as `std.integer`.
2. Update L1 current-state docs, roadmap text, compiler specs, and active work/initiative examples so the integer helper
   module is documented as `std.integer`.
3. Update ABI and mangling examples that currently spell `std.math` so they remain accurate after the rename.

## Diagnostics

No new diagnostics. This refactor changes module naming only.

## Non-Goals

1. No rename of `std.real` or `sys.real`.
2. No unification of integer and floating-point helper modules.
3. No helper additions, removals, or semantic changes inside the renamed modules.
4. No runtime ABI change beyond the expected source-level module-path rename in generated symbol examples and imports.
5. No edits to closed historical plans unless a document is still meant to describe the live current state.

## Verification Criteria

1. `rg -n "std\\.math" l0 l1` reports only intentional historical references that the implementation leaves untouched.
2. `rg -n "^module std\\.integer;$|^import std\\.integer;$|std\\.integer::" l0 l1` finds the expected active
   replacements in both trees.
3. `make -C l0 test-stage1` passes.
4. `make -C l0 test-stage2` passes.
5. `make -C l1 test-stage1` passes.
6. L1 docs/specs that explain canonical module identities, imports, and mangled names no longer use `std.math` as the
   active integer-module example.
