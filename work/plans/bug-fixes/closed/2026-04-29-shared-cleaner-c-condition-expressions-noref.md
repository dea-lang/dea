# Bug Fix Plan

## Emit cleaner C condition expressions across shared backends

- Date: 2026-04-29
- Status: Closed (fixed)
- Title: Suppress clang `-Wparentheses-equality` by emitting cleaner direct condition expressions across L0 and L1
  backends
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Python Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L0 Python Stage 1 remains the shared backend-rule oracle; Stage 2 and L1 Stage 1 must keep parity with that
  condition-emission policy
- Porting rule: Introduce the smallest condition-specific top-level emission rule in L0 Python Stage 1, port it
  mechanically to L0 Stage 2, then port the homologous Stage 2/L0 shape into L1 Stage 1 while preserving existing
  condition semantics and nested precedence behavior
- Target status:
  - L0 Python Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Backend C codegen / condition lowering / generated-C hygiene
- Modules:
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage1_py/l0_c_emitter.py`
  - `l0/compiler/stage1_py/l0c.py`
  - `l0/compiler/stage2_l0/src/backend.l0`
  - `l0/compiler/stage2_l0/src/build_driver.l0`
  - `l0/compiler/stage2_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_codegen_advanced.py`
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_codegen_test.py`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
- Repro:
  ```c
  if ((module_path == NULL)) {
      ...
  }
  ```

The user-visible trigger is a clang build of generated C:

```bash
clang -std=c99 -pedantic-errors -I <runtime-include-dir> generated.c
```

Representative diagnostic:

```text
warning: equality comparison with extraneous parentheses [-Wparentheses-equality]
```

## Summary

The shared backends currently over-parenthesize direct C condition expressions by composing a generic parenthesized
expression emitter with statement headers that already add `if (...)`, `while (...)`, or `for (...; ...; ...)`
parentheses. That yields warning-prone shapes such as `if ((x == NULL))` and `while ((i < n))`.

This plan adds a narrow condition-specific top-level emission path that removes only the redundant outer expression
layer for direct statement conditions while preserving precedence-protecting child parentheses. It also removes the
remaining `-Wno-parentheses` compiler-flag workaround from the shared Stage 1, Stage 2, and L1 build/test invocation
paths so the cleaner generated-C rule is enforced end to end.

## Current State

All three targeted backends lower statement conditions through dedicated control-flow helpers, but their leaf condition
emission still falls back to the generic expression emitter for comparison leaves. That is why direct condition guards
such as `x == NULL`, `i < n`, and similar comparisons appear as fully parenthesized standalone expressions when inserted
into C statement headers.

This is primarily a generated-C hygiene defect, not a language semantics defect. The generated C is valid, but clang
warns by default on the exact redundant shape produced by those headers.

## Root Cause

The backend has no condition-specific top-level emission rule. Generic expression emission is conservative and
appropriately returns self-contained fragments like `(lhs == rhs)`. Statement emission then wraps the already
parenthesized fragment inside `if (...)`, `while (...)`, or the condition slot of lowered loop structures, exposing the
redundant outer layer to clang.

The fix must be careful not to generalize into string surgery. The shared bug is at the AST/operator lowering boundary,
not in raw text post-processing.

There is one correctness-sensitive trap while introducing the new condition path: direct string equality and inequality
conditions must still lower through the runtime helper path (`rt_string_equals(...)` and its negated form) instead of
falling back to raw C equality. That special lowering already exists in generic binary emission and must be preserved in
the new condition-specific top-level path.

## Scope of This Fix

In scope:

- Add a condition-specific top-level expression helper for direct insertion into C statement headers.
- Use that helper only for statement-condition contexts, including control-flow leaf guards inside lowered `while` and
  `for` structures.
- Remove redundant outer parentheses for top-level equality and relational comparisons in direct condition contexts.
- Preserve nested precedence parentheses in child expressions, such as bitwise or additive operands inside a comparison.
- Preserve existing string equality, string relational, nullable-null, and pointer-null condition lowering rules.
- Remove `-Wno-parentheses` from the remaining shared compiler-driver and generated-C test-harness invocations.
- Add regression coverage for the no-double-parenthesized-condition invariant in all three targets.

Not in scope:

- Rewriting the full C emitter into a precedence-aware pretty-printer.
- Global parenthesis stripping on generated C strings.
- Parser, type-checker, runtime, or language syntax changes.
- Broader warning-policy cleanup beyond the specific `-Wno-parentheses` workaround tied to this bug.

## Approach

### Phase 1 — Shared condition-emission rule

Define one shared lowering rule across all three targets:

- direct condition contexts may omit the generic outermost wrapper for top-level `==`, `!=`, `<`, `<=`, `>`, and `>=`
- child expressions must continue to use normal expression emission so nested precedence remains unchanged
- any condition form without a dedicated top-level rule falls back to the existing generic expression emitter

This rule applies only at the statement-condition insertion boundary, not to arbitrary expression contexts.

### Phase 2 — L0 Python Stage 1

Add a backend helper equivalent to `emit_condition_expr(expr)` and use it where statement-condition leaves are lowered.

Behavior requirements:

- unwrap only top-level `ParenExpr` layers that exist solely around the direct condition expression
- lower direct numeric, pointer, and nullable comparisons without the generic outermost parentheses
- preserve string equality/inequality through `rt_string_equals(...)`-based lowering
- preserve string relational lowering through the runtime compare helper

The Python backend remains the first implementation and the shared policy oracle for the later ports.

### Phase 3 — L0 Stage 2

Port the same top-level condition-emission rule into the self-hosted Stage 2 backend and C emitter helpers.

Requirements:

- mirror the Stage 1 condition-specific behavior for top-level comparison leaves
- keep the existing `while (1)` / early-exit lowering structure intact
- preserve all special lowering paths already used by generic binary emission, especially string equality and nullable
  null checks

### Phase 4 — L1 Stage 1

Port the homologous Stage 2 shape into the L1 backend and C emitter helpers.

Requirements:

- keep parity with the Stage 2 policy and generated-C invariants
- preserve current L1-specific type-handling paths such as wide integer/common-int conversion logic
- preserve runtime-helper lowering for string equality and relational conditions

### Phase 5 — Regression coverage

Add focused tests that lock these invariants:

- direct condition headers do not emit `if ((x == y))`, `if ((x != y))`, `while ((i < n))`, or equivalent redundant
  top-level comparison wrappers
- nested precedence-sensitive children remain parenthesized, for example `if ((flags & mask) != 0)`
- direct string equality conditions still lower through `rt_string_equals(...)`
- direct string inequality conditions still lower through the negated runtime-helper path

### Phase 6 — Compiler-invocation cleanup

Remove the remaining `-Wno-parentheses` workaround from:

- the L0 Python Stage 1 build driver
- the L0 Stage 2 build driver
- the L1 Stage 1 build driver
- the Stage 2 generated-C parity test harness

If removal exposes any remaining warning-producing generated-C pattern, fix the generated-C shape rather than restoring
the suppression.

## Verification

Run targeted backend coverage only; no docs or diagnostic-catalog updates are expected.

```bash
cd l0 && ../.venv/bin/python -m pytest compiler/stage1_py/tests/backend/test_codegen_advanced.py -q -k "condition_headers_drop_only_outer_parens or early_return_in_loop"
cd l0 && make test-stage2 TESTS="backend_test l0c_codegen_test.py"
cd l1 && make test-stage1 TESTS="backend_test"
```

Optional manual smoke check when clang is available:

```bash
clang -std=c99 -pedantic-errors -I <runtime-include-dir> generated.c
```

## Outcome

- Implemented a condition-specific top-level emission path in L0 Python Stage 1, L0 Stage 2, and L1 Stage 1.
- Removed redundant outer parentheses from direct comparison conditions in generated C without changing backend
  control-flow lowering structure.
- Preserved precedence-protecting inner parentheses for nested condition operands.
- Preserved special string-equality and string-relational lowering through the existing runtime-helper paths in direct
  condition contexts.
- Removed the remaining `-Wno-parentheses` workaround from the shared Stage 1, Stage 2, and L1 compiler invocation paths
  and from the Stage 2 generated-C parity test harness.
- Added focused regressions that lock the no-double-parenthesized-condition invariant and the string-helper lowering
  invariant across the shared backends.

## Validation Run

Completed on 2026-04-29:

```bash
cd l0 && ../.venv/bin/python -m pytest compiler/stage1_py/tests/backend/test_codegen_advanced.py -q -k "condition_headers_drop_only_outer_parens or early_return_in_loop"
cd l0 && make test-stage2 TESTS="backend_test l0c_codegen_test.py"
cd l1 && make test-stage1 TESTS="backend_test"
```

## Assumptions

- Root shared placement is correct because the same backend rule spans L0 Python Stage 1, L0 Stage 2, and L1 Stage 1.
- No diagnostic-code planning is needed because the work introduces no new diagnostics and does not change existing
  diagnostic semantics.
- The implementation should stay minimal and local to condition emission, even if a future refactor might later
  generalize expression formatting more broadly.
