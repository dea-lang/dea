# Bug Fix Plan

## Shared ARC comparison temporary cleanup

- Date: 2026-09-11
- Status: Completed
- Title: Preserve owned ARC temporaries consumed by optional and string comparisons
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Python Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L0 optional-return leak investigation and isolated traced compiler experiments
- Porting rule: Implement and review L0 first, then port the ownership rule to L1 and cover its additional comparison
  paths
- Target status:
  - L0 Python Stage 1: Implemented, independently reviewed, and fully validated
  - L0 Stage 2: Implemented, independently reviewed, and fully validated
  - L1 Stage 1: Implemented, independently reviewed, and fully validated
- Subsystem: Backend expression lowering / ARC temporary ownership / condition cleanup
- Modules:
  - `l0/compiler/stage1_py/l0_backend_lowering.py`
  - `l0/compiler/stage1_py/l0_backend_lifetime.py`
  - `l0/compiler/stage2_l0/src/backend/lowering.l0`
  - `l0/compiler/stage2_l0/src/backend/lifetime.l0`
  - `l1/compiler/stage1_l0/src/backend/lower.l0`
  - `l1/compiler/stage1_l0/src/backend/expr.l0`
  - `l1/compiler/stage1_l0/src/backend/lifetime.l0`
  - `l1/compiler/stage1_l0/src/c_emitter/expr.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_trace_arc.py`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py`
  - `l0/compiler/stage2_l0/tests/fixtures/arc_comparisons/main.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/fixtures/arc_comparisons/main.l1`
- Related:
  - [l0/docs/reference/ownership.md](../../../../l0/docs/reference/ownership.md)
  - [l1/docs/reference/ownership.md](../../../../l1/docs/reference/ownership.md)
  - [l0/docs/reference/c-backend-design.md](../../../../l0/docs/reference/c-backend-design.md)
  - [l1/docs/reference/c-backend-design.md](../../../../l1/docs/reference/c-backend-design.md)
- Repro: Compile an allocating `string?` function called directly in `if (make_value() != null)` with both ARC and
  memory tracing

## Summary

Both L0 compilers lose an owned optional result when a direct null comparison observes only its presence flag. Binding
the result to a local works because the local registers its payload for cleanup. L1 has the same unregistered-operand
paths. L0 Stage 2 also omits temporary ownership in direct string ordering conditions; L1 already materializes those
string operands.

## ADR Impact

- Decision: Restore the existing ARC ownership contract for comparison operands.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This fixes omitted uses of established temporary registration and recursive cleanup without changing
    language semantics, runtime ABI, or the ownership model.

## Root Cause

Null-comparison lowering calls the expression emitter, then emits `.has_value` without materializing an owned ARC
temporary. Cleanup cannot release an owner that was never registered. The omission appears in both general expression
and condition paths in the self-hosted backends. The equivalent Stage 1 Python paths share binary lowering.

An allocating `string?` reproducer exits normally but reports `leaked_string_ptrs=1`; binding its optional result
reports zero leaks. A four-iteration loop leaks four strings. Optional aggregates containing ARC data and explicit
optional wraps of owned local strings are affected too. Existing Stage 1 ARC tests pass because the covered optional
values are bound and condition temporaries commonly pass through argument lowering, which already registers them.

L1 optional-to-optional equality also interpolates each operand repeatedly into a presence/payload expression. A
comparison of two allocating calls executes five calls and leaks five strings. Both ARC and scalar operands need stable
single-evaluation snapshots; borrowed ARC snapshots must retain before the other operand can mutate their source.

## Scope

- Register owned optional comparison operands using existing ARC temporary classification and cleanup helpers.
- Preserve borrowed places, optional unwrap borrowing, pointer optionals, null results, evaluation count, and logical
  short-circuit behavior.
- Preserve borrowed origins through identity/unwrap/try chains and retain borrowed payloads when explicitly wrapping
  them into a new optional owner. Register fresh ARC-bearing field-access bases and give `for` update temporaries a
  cleanup scope inside the update's emitted block.
- Fix L0 Stage 2 string ordering conditions and verify parity with L0 Python Stage 1.
- Check L1 null comparisons and its additional optional-to-optional equality paths; fix equivalent ownership omissions.
- Register fresh L1 ARC array bases before index evaluation, preserve nested rows and borrowed storage, and clean all
  elements on normal and early index exits.
- Add allocation-aware trace regressions and update the ownership and backend references for each implemented level.
- No diagnostic codes, runtime ABI changes, manual retains in application code, or unrelated ownership redesign.

## Implementation Sequence

1. Implement L0 Python Stage 1 and L0 Stage 2 with focused regressions that expose the original leak under combined
   memory and ARC tracing. Cover direct and reversed null comparisons, boolean values, repeated loop conditions,
   taken/skipped logical operands, ARC aggregates, explicit optional wraps, and borrowed controls.
2. Validate the L0 changes and spawn an independent read-only code-review agent. Review its findings for bugs, gaps,
   regressions, missed requirements, and insufficient tests; fix valid findings before accepting L0 completion.
3. Reproduce the applicable L1 failures with the corrected L0 bootstrap compiler. Port the settled L0 rule and extend
   coverage for L1-specific comparison and output modes where relevant.
4. Validate L1 and request a separate independent read-only review with the same criteria. Evaluate all findings and
   resolve valid issues before finalization.
5. Complete remaining normal and dedicated trace validation for both levels. Reuse unchanged successful runs. Close this
   shared plan only after both reviews and all required validation pass, then create a local commit.

## Verification Criteria

- Every evaluated owned comparison operand is evaluated once and cleaned exactly once; null and skipped operands do not
  produce invalid cleanup or unexpected allocation.
- Both condition outcomes and all tested loop exits preserve the normal ownership rules.
- Allocation-aware trace checks report no leaked objects or strings and no runtime/trace errors.
- Borrowed local and field operands remain valid after comparison and require no compensating manual retain/release.
- L0 Stage 1 ARC tests, L0 Stage 2 regression/normal/trace checks, examples, and triple bootstrap pass.
- L1 regression/normal/trace checks and examples pass with the corrected upstream L0 compiler.
- Full cross-level validation is satisfied by the applicable normal suites plus dedicated trace sweeps, with no repeated
  suites for unchanged validated inputs.
- Independent reviews for L0 and L1 are recorded with the disposition of each actionable finding.
- Active/staged ADR Impact checks, staged whitespace checks, and root pre-commit pass.

## Review Outcomes

### L0 independent review

The initial review reproduced borrowed identity-chain over-release, missing retain when rewrapping a borrowed cast or
`?` result, and an invalid cleanup scope for `for` update temporaries. These findings were accepted and fixed in both
stages. The review also exposed lost fresh aggregate field-access bases; both backends now register these bases so
unselected ARC fields are cleaned too. The permanent fixture covers each correction.

The independent recheck reports no remaining actionable findings. Six original probes and additional mixed probes for
borrowed returns, `case`/`match` scrutinees, nested projections, early update extraction, and enclosing-loop `continue`
pass under both stages with zero trace errors, warnings, or leaks. A direct Stage 2 `return` in a `for` update header
was separately confirmed to encounter a pre-existing frontend rejection; accepted update/try/continue paths validate the
cleanup change.

### L1 independent review

The reviewer found that fresh array index bases still lost ownership: `values()[0] != null` leaked both selected and
unselected optional string elements, and optional equality retained its snapshot without releasing the original array.
This pre-existing adjacent gap was accepted within the projection cleanup scope. Read and write index lowering now
registers fresh ARC array bases before lowering the index, preserving early-index cleanup, borrowed storage, and raw
nested rows. Permanent regressions cover null/equality comparisons, nested arrays, copied/returned elements, borrowed
writes, update scopes, and early `?` index exits. The independent recheck reports no remaining actionable findings. Both
original array leak probes plus fresh-array writes, early index exits, arrays of structs, projected returns, borrowed
array storage, and optional slice mutation pass with zero trace errors, warnings, or leaks. Additional probes validate
borrowed array cast/try conversions to slices, rewraps, `match`/`case` extraction, scalar optional mutation, and a
fresh-field comparison whose right operand returns early.

Full validation exposed stale nullable-equality C expectations in `backend_test.l0` and `l1c_lib_test.l0`. The
assertions now require captured operands and comparisons of captured payloads. The reviewer's follow-up requested an
explicit retain-count assertion for borrowed string snapshots; that assertion was added. The compiler-driver test
retains its executable fixture and checks comparisons of retained snapshots. The runtime fixture supplies the
truth-table, evaluation-count, mutation, and early-exit checks.

The reviewer separately identified existing code-generation failures for parenthesized `null` and explicit casts of
`null`. These abort before runtime and are not ownership regressions introduced by this change; their contextual-null
lowering remains outside this cleanup fix. A separate existing array-wrapper declaration ordering failure prevented one
struct-containing-array probe; the accepted array-of-struct and scalar-array cases validate the implemented paths.

## Validation Results

- L0: `PYTEST_XDIST_AUTO_NUM_WORKERS=4 make test-all` from `l0/` passed: 1,526 Stage 1 Python tests, 58 Stage 2 tests
  including triple bootstrap and the new ARC regression, eight examples, 13 runtime build-flag checks,
  distribution/build workflows, and 34 dedicated trace checks. All trace cases report zero leaked strings and objects.
- An earlier L0 run with 12 pytest workers encountered a timeout in the allocation-tracker quarantine stress test. The
  unchanged test passed alone, and the complete four-worker run passed without source or test workarounds.
- L1: the expanded comparison fixture passed combined tracing with 126 heap string allocations and three objects, zero
  errors/warnings, and zero leaked strings/objects.
- L1 normal validation:
  `L1_TEST_JOBS=4 L1_TRACE_TEST_JOBS=4 PYTEST_XDIST_AUTO_NUM_WORKERS=4 make -o build-stage1 test-all` completed with 71
  passing normal checks and the two stale C-expectation failures described above. After updating only those tests,
  `L1_TEST_JOBS=1 ../.venv/bin/python compiler/stage1_l0/scripts/run_tests.py -v backend_test` and the same command with
  `l1c_lib_test` both passed. Together these validate all 73 normal checks on the final implementation, including the
  full ARC regression program and generated-C identity across output modes.
- L1 environment and example checks passed via
  `L1_TRACE_TEST_JOBS=4 PYTEST_XDIST_AUTO_NUM_WORKERS=4 make -o build-stage1 test-env check-examples test-stage1-trace`;
  all four examples passed. The trace sweep passed 44 cases and encountered the same stale compiler-driver expectation.
  `L1_TRACE_TEST_JOBS=1 make -o build-stage1 test-stage1-trace TESTS=l1c_lib_test` then passed the corrected driver
  test, validating 19,605,115 events with zero leaked strings or objects. Together these runs cover all 45 default trace
  cases.
- Successful L0 suites and the unchanged L1 checks are reused. After their validation, only the two stale L1 test
  expectations and documentation/plan text changed; the affected tests are rerun explicitly. `-o build-stage1` reuses
  the just-rebuilt, focused-regression-validated L1 compiler; no compiler source, build inputs, or toolchain selection
  changed afterward.
- Staged whitespace, ADR Impact, copyright, and Markdown pre-commit checks pass.

## Completion

Both L0 stages and L1 now preserve temporary ownership during comparisons without a local-binding workaround. L1
optional equality also evaluates each operand once. The independent reviews' applicable findings are resolved, the
permanent regressions pass, and normal plus dedicated trace validation is complete for both levels. The existing
ownership contract and runtime ABI are unchanged.
