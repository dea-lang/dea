# Feature Plan

## Introduce `is` intrinsic for enum payload-ignoring comparison

- Date: 2026-04-20
- Status: Completed
- Title: Introduce `is` intrinsic for enum payload-ignoring comparison
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Parser / Typing / Backend / Specs
- Modules:
  - `l1/compiler/stage1_l0/src/dea_prelude.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/project-status.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
- Related:
  - `l1/docs/roadmap.md`
- Repro: `make -C l1 test-stage1 TESTS="parser_test expr_types_test backend_test"`

## Summary

The current L1 implementation uses the `ord(x) == ord(EnumVariant)` pattern to test whether a value has a specific enum
tag. This is cumbersome and requires synthesizing dummy payload values for variants that carry data (e.g.,
`ord(x) == ord(RGB(0,0,0))`), generating unnecessary allocation or initialization just for a tag check.

This plan introduces an `is(x, Variant)` intrinsic into the implicit `dea` module to replace manual `ord` comparison.
The intrinsic evaluates true if the tag of `x` matches the tag of `Variant`, ignoring the payload of `x`.

## Goal

Provide a clean, ergonomic syntax `is(expr, EnumVariant)` that checks enum tags without constructing dummy payloads.

## Implementation Phases

### Phase 1: `is` Intrinsic Support

1. Keep `is` on the existing ordinary-call parser path and add explicit parser coverage for bare payload variants,
   qualified variant names, and call expressions in first position.
2. Update `expr_types.l0` to typecheck `is(value, EnumVariant)`. The first argument must be any enum-typed expression,
   and the second must be a variant reference of that enum type, including qualified forms.
3. Lower `is(expr, EnumVariant)` in `backend.l0` to a direct enum-tag comparison in the emitted C code, without
   synthesizing payload initialization.
4. Update `l1/docs/reference/design-decisions.md` to document `is(x, Variant)`.

### Phase 2: Refactor Existing L1 Code

1. Audit and replace `ord(x) == ord(...)` occurrences with `is(x, ...)` in `l1/compiler/shared/l1/stdlib/**/*.l1`.
2. Update L1 examples in `l1/examples/` and test fixtures to use `is` instead of `ord`.

## Completion Notes

1. Landed `dea::is` in the synthesized prelude with explicit `bool` typing alongside `sizeof` and `ord`.
2. Implemented typing diagnostics `TYP-0245` through `TYP-0248` for arity, non-enum first arguments, invalid
   second-argument forms, and wrong-enum variant references.
3. Added coverage for:
   - bare payload variants such as `is(c, RGB)`
   - enum-returning call expressions such as `is(get_key(), String)`
   - qualified variant names such as `is(x, config.types::String)`
   - shadowed local `is` functions versus qualified `dea::is`
4. Audited the current L1 tree for phase-2 `ord(x) == ord(...)` conversions and found no stdlib or example sites to
   rewrite in this tranche.
5. Validation completed with `make -C l1 test-stage1 TESTS="parser_test expr_types_test backend_test"` and repo-root
   `make clean test-all`.

## Verification Criteria

- `is(x, Variant)` parses and type-checks successfully.
- It correctly evaluates to a boolean `true` when the enum tags match.
- Code generation produces efficient tag comparison without constructing temporary payload values.
- All stdlib and compiler tests pass.
- No new memory leaks are introduced (verified via ARC trace rules).
