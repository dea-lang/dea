# Feature Plan

## Implement lifted nullable numeric widening

- Date: 2026-11-26
- Status: In progress
- Title: Implement lifted nullable numeric widening across Dea compilers
- Kind: Feature
- Priority: High
- Scope: Shared
- Subsystem: Assignment compatibility, explicit casts and expected-type lowering
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 canonical compiler
  - L2 canonical compiler
- Origin: Dea-wide language decision in ADR-0029
- Porting rule: Use the shared value semantics and each level's existing numeric widening pairs and nullable syntax.
- Target status:
  - L0 Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 canonical compiler: Implemented
  - L2 canonical compiler: Deferred: resume during the stable L1 catch-up.
- Modules:
  - `l0/compiler/stage1_py/l0_check_compat.py`, `l0/compiler/stage1_py/l0_backend_convert.py`
  - `l0/compiler/stage2_l0/src/expr_types/compat.l0`, `l0/compiler/stage2_l0/src/backend/convert.l0`
  - `l1/compiler/src/expr_types/convert.l0`, `l1/compiler/src/backend/coerce.l0`
  - `l2/compiler/src/expr_types/convert.l1`, `l2/compiler/src/backend/coerce.l1`
- Test modules:
  - `l0/compiler/stage1_py/tests/integration/test_implicit_conversions.py`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`, `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l1/compiler/tests/expr_types_test.l0`, `l1/compiler/tests/nullable_numeric_widening_test.py`
  - `l2/compiler/tests/expr_types_test.l1`, `l2/compiler/tests/l2c_build_run_multi_cu_test.py`
- Related:
  - [docs/specs/language/nullable-numeric-widening.md][spec]
  - [docs/decisions/0029-lifted-nullable-numeric-widening.md][adr]

## Summary

Both L0 stages and L1 implement ADR-0029 and passed focused local checks. L2 is the remaining target. Resume it when the
project maintainer selects a stable L1 baseline and activates
[l2/work/plans/features/2026-10-27-stable-l1-catch-up-noref.md][catch-up]. Both L0 stages also completed the
contextual-null and ARC repairs, alongside the Stage 1 structural type-equality fix.
[l0/work/plans/bug-fixes/closed/2026-11-21-stage1-nullable-conversions-and-ownership-noref.md][l0-fixes] records their
verification. L1 completed [l1/work/plans/bug-fixes/closed/2026-11-21-contextual-null-lowering-noref.md][l1-null] for
grouped null literals and [l1/work/plans/bug-fixes/closed/2026-11-21-drop-optional-payload-cleanup-noref.md][l1-drop]
for owned payload cleanup when dropping an allocated optional.

## ADR Impact

- Decision: Lift a level's implicit numeric widenings through existing nullable layers before injecting additional
  layers.
  - Scope: Dea-wide
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0029-lifted-nullable-numeric-widening.md`
  - Rationale: The language rule is accepted. This plan tracks conformance of the four compiler implementations.

## Verification results

- L0 Stage 1 compiled and executed the shared L0 fixture for absence, 0, 255, nested aliases, injection, and counted
  sources. Its implicit-conversion and cast tests cover rejected narrowing, layer removal, and incompatible payloads.

- L0 Stage 2 executed the same fixture through its native launcher. Its expression checker rejects nullable narrowing,
  loss of depth, and widening through a pointer. Both stages also compile an unread destination whose local annotation
  is the sole use of its four-layer wrapper.

- L1 passed `expr_types_test` and `nullable_numeric_widening_test.py`. The native matrix covers all 18 integer pairs and
  the floating pair with typed boundaries, nested presence states, and checked rejection of mixed optional equality,
  arithmetic, pointer, array and slice conversions.

## L2 bootstrap issue and catch-up

Building the L1-written L2 compiler with `L2_BOOTSTRAP_MODE=development` and `L2_BOOTSTRAP_L1C` set to the built L1
launcher failed with `TYP-0311` at `sec = now.sec`. L1's `std.time.WallTime.sec` is a 64-bit `long`. Three L2 compiler
helpers infer a 32-bit `int` from `let sec = 0` when constructing workspace or transaction names.

- `cfs_workspace_create` in `l2/compiler/src/compiler_filesystem.l1`
- `cd_create_transaction` in `l2/compiler/src/compile_driver/transaction.l1`
- `ld_create_transaction` in `l2/compiler/src/link_driver/transaction.l1`

The retry stopped during compiler construction, before the L2 conformance tests ran. At catch-up, confirm the clock type
against the selected stable L1 toolchain. If it is `long`, carry seconds through the locals, identity parameters and
decimal formatting at full width. Exercise a workspace collision at 2147483648 seconds and build L2 with that toolchain.
Then port the L1 widening rule and run the conformance cases below with L2-owned `.l2` sources and runtime inputs.

## Implementation constraints

- Reuse the existing predicates for ordinary type-based numeric widening. Where a scalar check is inline, share it with
  nullable conversion classification. Preserve identity and ordinary injection for all eligible types.
- Recognize equal-depth numeric lifting and then apply any extra destination layers. Keep the decision specific to
  numeric payloads. Blindly reordering the nullable branches or recursively calling general assignment compatibility
  would also admit unrelated conversions. Check callers such as pointer compatibility and operators for accidental
  propagation of the new rule.
- Use the same conversion classification for implicit contexts and for the part of `as` that accepts implicit
  conversions. Lower the source once, branch on presence before accessing each payload, widen the present scalar, and
  construct each required destination representation. Distinct optional types can have distinct native layouts.
- Retain existing diagnostics for invalid source programs. The catalog already assigns `TYP-0310`, `TYP-0311`,
  `TYP-0312`, `TYP-0315` and `TYP-0230` to the applicable contexts.
  [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]

## Verification criteria

- Use the example table in the shared spec as a common source-level oracle. At each level enumerate **every** existing
  type-based numeric widening pair and use typed variables or producing functions so literal coercion cannot mask a
  failure. Exercise absence, zero, and present values at source-domain boundaries. Include signed minima, unsigned
  maxima, and floating-point boundaries where applicable.
- Exercise initializers, assignments, calls, returns and explicit casts corresponding to accepted implicit conversions.
  Include other assignment contexts a level exposes, such as struct fields or enum payloads. Require successful
  checking, native compilation and execution. Test presence separately from the numeric payload. Use a source function
  with an observable counter and assert one call for absent and present results, including nested lifting followed by
  injection.
- Where the level supports nested nullables, cover every distinguishable state at each tested depth. For `byte??` to
  `int???`, outer absence, present-with-inner-absence, and doubly present inputs all gain one present layer around their
  converted result. Check `byte?` to `byte??` and `byte?` to `int??` with an absent source explicitly. Construct input
  from typed values so these tests run independently of contextual null literal lowering.
- Reject implicit `int?` to `byte?`, `byte?` to `int`, and (where expressible) `byte??` to `int?`. Include a typed
  source for which only a literal of the same value could convert, and pointer or aggregate controls that the existing
  rules reject. Preserve existing binary-operator promotion, nullable equality, and explicit narrowing/unwrap behavior.
- Run the focused typing and executable suites listed above from their owning levels. Record accepted and rejected
  source cases and native results per target before marking it implemented. Exercise the L2 compiler with its own target
  inputs and explicitly selected L1 bootstrap. Update the level references as support lands.

[adr]: ../../../docs/decisions/0029-lifted-nullable-numeric-widening.md
[catch-up]: ../../../l2/work/plans/features/2026-10-27-stable-l1-catch-up-noref.md
[diagnostics]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[l0-fixes]: ../../../l0/work/plans/bug-fixes/closed/2026-11-21-stage1-nullable-conversions-and-ownership-noref.md
[l1-drop]: ../../../l1/work/plans/bug-fixes/closed/2026-11-21-drop-optional-payload-cleanup-noref.md
[l1-null]: ../../../l1/work/plans/bug-fixes/closed/2026-11-21-contextual-null-lowering-noref.md
[spec]: ../../../docs/specs/language/nullable-numeric-widening.md
