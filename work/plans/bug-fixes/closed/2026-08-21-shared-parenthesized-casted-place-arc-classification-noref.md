# Bug Fix Plan

## Preserve casted-place ARC classification through parentheses

- Date: 2026-08-23
- Status: Completed
- Title: Preserve casted-place ARC classification through parenthesized expressions across shared backends
- Kind: Bug Fix
- Scope: Shared
- Severity: Critical (use-after-free and double-release on valid programs)
- Stage: Shared
- Targets:
  - L0 Python Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L0 Python Stage 1 settles the ownership-classification rule and generated-C invariant before mechanical ports
  to L0 Stage 2 and L1 Stage 1.
- Porting rule: Fix and trace-test the parenthesis-transparent cast-from-place classification in L0 Python Stage 1, then
  port the same rule and regression shape mechanically to the two self-hosted backends.
- Target status:
  - L0 Python Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Backend ARC ownership / expression temporary classification / condition lowering
- Modules:
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage2_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage1_py/tests/backend/test_trace_arc.py`
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
- Related:
  - `work/plans/bug-fixes/closed/2026-04-20-shared-casted-place-null-propagation-arc-noref.md`
  - `work/plans/bug-fixes/closed/2026-04-22-shared-unwrapped-string-value-arc-copy-noref.md`
  - `l0/work/plans/bug-fixes/closed/2026-02-25-arc-opt-as-string-unwrap-ownership-noref.md`
  - `l1/work/plans/features/closed/2026-08-21-per-module-generated-c-foundation-noref.md`
  - `l0/docs/reference/ownership.md`
  - `l1/docs/reference/ownership.md`
  - `l1/docs/roadmap.md`
- Repro: Compile and run the minimized fixture in Current State with ARC and memory tracing through L0 Python Stage 1
  and a freshly built L0 Stage 2 artifact.

## Summary

The shared backends correctly classify a direct cast from an existing place, such as `value as string`, as borrowed
storage. They lose that classification when parentheses wrap the cast, such as `(value as string)`. In an ARC-producing
expression context, the backend can then materialize the borrowed string payload as an owned temporary without retaining
it. Temporary cleanup releases the source owner's string, and normal source cleanup later releases the same allocation
again.

The failure is confirmed in both L0 compiler stages, and the homologous L1 Stage 1 backend carries the same helper
shape. The compact L1 per-module generated-C work exposed the bug while the upstream L0 compiler was compiling the L1
compiler itself. The implementation must fix the shared classification rule rather than preserve source-level local
variable workarounds.

## Current State and Reproduction Evidence

The minimized failing ownership shape is:

```l0
func parenthesized_unwrap(value: string?, expected: string) -> bool {
    return value != null && (value as string) == expected;
}

func main() -> int {
    let value: string? = concat_s("m", "") as string?;
    if (!parenthesized_unwrap(value, "m")) {
        return 1;
    }
    return 0;
}
```

Observed on 2026-08-21:

1. L0 Python Stage 1 and the repo-local L0 Stage 2 compiler both compile the program successfully.
2. The generated program releases the heap string while evaluating the comparison, reaches normal scope cleanup, and
   then aborts with `_rt_free_string: double free detected` on the second release.
3. Generated C copies the optional payload into an `l0_arc_*` temporary and releases that temporary without a preceding
   retain. The temporary is therefore an alias, not an independent owner.
4. The same failure occurs when the optional is a struct field, matching the compiler-internal discovery shape.

The first trace investigation attributed the failure to a nearby nested string concatenation in
`cem_module_target_includes_type`. A separate minimized control proved that this shape is trace-clean in both L0 stages:

```l0
func nested_concat(module_name: string, type_name: string) -> bool {
    return false || (true && accepts(module_name + "::" + type_name));
}
```

The two concatenation results are distinct owned allocations and each is released once. The serious defect is the
parenthesized cast-from-place alias, which appeared in adjacent target-selection conditions and could invalidate later
strings before the trace reported the final double release.

## Root Cause

All three backends use the same ownership-classification structure:

1. `be_is_place_expr` / `_is_place_expr` treats a parenthesized place as a place by recursively inspecting the inner
   expression.
2. `be_is_unwrap_cast_from_place` / `_is_unwrap_cast_from_place` recognizes a cast only when `EX_CAST` / `CastExpr` is
   the top-level node.
3. For `(value as string)`, the top-level node is `EX_PAREN` / `ParenExpr`. The place check reaches the inner cast and
   returns false, while the cast-from-place check rejects the outer parenthesized node without recursion.
4. `be_should_materialize_arc_temp` / `_should_materialize_arc_temp` therefore classifies the borrowed string alias as a
   fresh ARC rvalue and registers it for cleanup.
5. String comparison or call-argument lowering releases that synthetic alias temp without a balancing retain, consuming
   the source optional's reference.

The existing 2026-04-20 shared casted-place fix established the right ownership rule but did not cover parenthesized
wrappers around the cast. Existing optional-unwrap trace tests use the direct `opt as string` form, so they do not
exercise this AST topology.

ARC value-optional wrapping is the type-sensitive exception to that rule. A cast from an ARC place from `T` to `T?`
produces an owned optional value by retaining its payload; it must not be reclassified as a borrowed alias merely
because parentheses surround the cast. L0 Python Stage 1 already implemented that eager retain, while the two
self-hosted backends require the same behavior for parity.

## Scope of This Fix

1. Make cast-from-place ownership classification transparent through one or more parenthesized wrappers in all three
   backends.
2. Preserve the existing rule that a cast from an existing place remains borrowed unless the cast itself is an
   owner-producing ARC value-optional wrap or a later ownership boundary explicitly copies and retains the value.
3. Add generated-C and trace regressions for local and field-backed optional strings in comparison, logical-condition,
   call-argument, and owner-taking contexts.
4. Retain a nested string-concatenation control so the original discovery shape remains distinguished from the actual
   aliasing failure.
5. Verify L0 Stage 1, L0 Stage 2, and L1 Stage 1 behavior through freshly built compiler artifacts.

## Implementation Sequence

### Phase 1: Pin the failing and control shapes

1. Add an L0 Python Stage 1 generated-C regression for `(opt as string) == expected` inside a short-circuit condition.
2. Add L0 Stage 1 ARC trace cases for a local `string?`, a `string?` struct field, and repeated parentheses around the
   unwrap cast.
3. Add the equivalent L0 Stage 2 backend and trace cases before changing the self-hosted helper.
4. Add a nested `module_name + "::" + type_name` call-argument control under structured logical lowering and assert that
   each fresh concatenation allocation is freed exactly once.

### Phase 2: Fix L0 Python Stage 1

1. Make `_is_unwrap_cast_from_place` ignore any number of `ParenExpr` wrappers before deciding whether the expression is
   a cast whose operand is a place.
2. Exclude owner-producing, non-niche ARC `T -> T?` wraps from borrowed cast-from-place classification, mirroring the
   eager-retain path that constructs the optional value.
3. Keep `_is_place_expr` and `_should_materialize_arc_temp` responsibilities otherwise unchanged.
4. Assert that the generated C no longer creates an owned `l0_arc_*` alias for a parenthesized unwrap used as a borrowed
   comparison or call operand.
5. Assert that owner-taking boundaries still retain a copied unwrap result, ARC value-optional wraps retain exactly
   once, and genuine string-producing rvalues still receive temporary cleanup.

### Phase 3: Port the rule to L0 Stage 2

1. Port the same parenthesis-transparent classification into `be_is_unwrap_cast_from_place` in the Stage 2 backend.
2. Port the Python oracle's eager retain for owner-producing ARC value-optional wraps and keep the emitted ownership
   shape aligned across stages.
3. Build a fresh Stage 2 compiler before running the focused runtime and trace regressions so a stale repo-local
   artifact cannot mask or preserve the defect.

### Phase 4: Port the rule to L1 Stage 1

1. Port the same helper change into the homologous L1 backend.
2. Port the same eager-retain behavior for owner-producing ARC value-optional wraps.
3. Add backend and trace regressions using L1 source, including a parenthesized optional field unwrap inside a
   short-circuit string comparison.
4. Confirm the L1 compiler can compile and run the fixture without a synthetic alias release or double free.
5. Re-run the per-module generated-C integration surface that originally exposed the upstream compiler defect.

### Phase 5: Close the shared regression gap

1. Run the complete trace-inclusive L0 and L1 validation tiers.
2. Run the L0 triple-bootstrap gate to prove the self-hosted compiler reaches its fixed point with the corrected
   lowering rule.
3. Update target status and closure evidence for all three backends in one change.
4. Link the closed plan from the existing ownership ADR or current ownership documentation only if closure changes their
   related-plan inventories. No normative ownership wording change is expected.

## Diagnostics

No diagnostic code is added or reassigned. The affected programs are valid and must keep compiling; only generated ARC
ownership behavior changes.

## ADR Impact

- Decision: Restore parenthesis-transparent cast-from-place classification under the existing ARC ownership contract.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The fix restores already documented borrowed-place and retain-on-copy behavior and introduces no new
    language, runtime, ABI, or compiler architecture decision.

## Non-Goals

1. Changing nullable cast syntax, string value semantics, ARC runtime primitives, or the retain/release ABI.
2. Treating every cast as a place or suppressing cleanup for genuine string-producing rvalues.
3. Redesigning expression ownership analysis beyond the confirmed parenthesized cast-from-place gap.
4. Recompacting the defensive local variables added during the L1 per-module generated-C work. The compiler rule must be
   proven by minimized regressions rather than by depending on one production source spelling.
5. Changing string concatenation lowering without a separate failing reproduction.

## Verification

Focused checks:

```bash
cd l0 && ../.venv/bin/python -m pytest compiler/stage1_py/tests/backend/test_codegen_semantics.py compiler/stage1_py/tests/backend/test_trace_arc.py -q -k "parenthesized_unwrap or parenthesized_wrap"
cd l0 && make test-stage2 TESTS="backend_test"
cd l0 && ../.venv/bin/python compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py
cd l1 && make test-stage1 \
  TESTS="cli_args_test backend_test c_emitter_test driver_test module_graph_test \
  interface_replay_test compile_driver_test compiler_filesystem_test l1c_lib_test \
  l1c_stage1_help_output_test.py l1c_stage1_compile_only_test.py l1c_stage1_toplet_test.py \
  compiler_filesystem_support_test.py" \
  L1_BOOTSTRAP_L0C=../l0/build/dea/bin/l0c-stage2
cd l1 && ../.venv/bin/python compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py
```

Final shared validation:

```bash
make clean test-all
make -C l0 triple-test
```

The root `test-all` target already runs the complete L1 `test-all` tier, so it is not repeated separately.

## Verification Criteria

1. Parenthesized and repeatedly parenthesized casts from local and field places do not become synthetic owned ARC
   aliases in generated C.
2. No trace contains a release of the unwrapped borrowed payload before the source owner leaves scope.
3. Owner-taking copies of parenthesized unwraps still retain exactly as required by the existing ownership contract.
4. Parenthesized ARC value-optional wraps retain their place payload exactly once and balance temporary or destination
   cleanup without leaks or double retains.
5. Nested string concatenation inside a logical call operand remains trace-clean, with every fresh result released
   exactly once.
6. The focused Stage 1, Stage 2, and L1 tests pass against freshly built subject compilers.
7. Full trace triage reports no leaks, invalid refcount transitions, use-after-free events, or double releases.
8. L0 triple bootstrap and the complete L1 per-module generated-C integration surface remain green.

## Outcome

- Made cast-from-place classification ignore repeated outer parentheses in L0 Python Stage 1, L0 Stage 2, and L1 Stage
  1, preventing borrowed identity and unwrap casts from becoming unretained synthetic ARC owners.
- Kept non-niche ARC `T -> T?` casts as explicit owner-producing boundaries and aligned both self-hosted backends with
  the Python oracle's single eager payload retain.
- Added generated-C and exact ARC trace regressions for local and field unwraps, repeated-parentheses call arguments,
  owner returns, borrowed and owned optional wraps, genuine casted rvalues, and the nested-concatenation control.

## Validation Run

Completed on 2026-08-23:

- The two affected L0 Python backend test files passed all 81 tests.
- The focused L0 Stage 2 backend test and complete Stage 2 ARC regression harness passed against the fresh
  `l0/build/dea/bin/l0c-stage2` artifact.
- The focused L1 compiler and per-module generated-C integration surface passed 13/13 tests against that exact Stage 2
  bootstrap artifact, and the complete L1 Stage 1 ARC regression harness passed.
- `make clean test-all` passed: L0 Python 1456/1456, L0 Stage 2 55/55, L0 broad trace 33/33, L1 Stage 1 65/65, and L1
  broad trace 44/44, together with all examples and workflow checks.
- `make -C l0 triple-test` produced matching retained C from the second and third self-hosted compilers and passed the
  final smoke test.

## Assumptions

1. Parentheses are semantically transparent for ownership classification just as they are for type and place
   classification.
2. A cast whose underlying operand is a place remains borrowed except for an owner-producing, non-niche ARC `T -> T?`
   wrap; that cast retains its payload as part of constructing the optional owner.
3. The shared helper topology remains close enough for the L0 Stage 2 and L1 Stage 1 ports to be mechanical.
