# Bug Fix Plan

## Apply position-independent wildcard fallbacks to enum match and scalar case

- Date: 2026-11-27
- Status: Draft
- Title: Apply position-independent wildcard fallbacks to enum match and scalar case
- Kind: Bug Fix
- Severity: Medium
- Scope: Shared
- Targets:
  - L0 Stage 1 (Python)
  - L0 Stage 2 (L0)
  - L1 canonical compiler (L0)
  - L2 canonical compiler (L1)
  - Shared Tree-sitter grammar
- Origin: The L0 and L1 enum-match reports found that return checking and executable dispatch disagree.
- Porting rule: Implement and verify the accepted rule in the target order above, using each level's own fixtures. L2
  participates now for this rule alone. Its stable L1 catch-up and other deferred work retain their existing gates.
- Target status:
  - L0 Stage 1: Pending
  - L0 Stage 2: Pending
  - L1 canonical compiler: Pending
  - L2 canonical compiler: Pending
  - Shared Tree-sitter grammar: Pending
- Subsystem: Match pattern coverage, statement flow, case parsing and recovery, dispatch and editor grammar
- Modules:
  - `l0/compiler/stage1_py/l0_check_patterns.py`, `l0/compiler/stage2_l0/src/expr_types/patterns.l0`
  - `l1/compiler/src/expr_types/patterns.l0`, `l2/compiler/src/expr_types/patterns.l1`
  - `editors/tree-sitter-dea/grammar.js`, `editors/tree-sitter-dea/queries/highlights.scm`
- Test modules:
  - `l0/compiler/stage1_py/tests/type_checker/test_match_exhaustiveness.py`,
    `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l1/compiler/tests/l1c_build_run_multi_cu_test.py`, `l2/compiler/tests/l2c_build_run_multi_cu_test.py`
  - `editors/tree-sitter-dea/test/corpus/control_flow.txt`, `editors/tree-sitter-dea/test/corpus/recovery.txt`
- Related:
  - [l0/work/plans/bug-fixes/2026-11-21-match-wildcard-precedence-and-return-flow-noref.md](../../../l0/work/plans/bug-fixes/2026-11-21-match-wildcard-precedence-and-return-flow-noref.md)
  - [l1/work/plans/bug-fixes/2026-11-21-match-wildcard-dispatch-and-return-flow-noref.md](../../../l1/work/plans/bug-fixes/2026-11-21-match-wildcard-dispatch-and-return-flow-noref.md)
  - [docs/decisions/0007-case-default-arm-wildcard.md](../../../docs/decisions/0007-case-default-arm-wildcard.md)
  - [docs/specs/compiler/diagnostic-code-catalog.md](../../../docs/specs/compiler/diagnostic-code-catalog.md)
- Repro: In an enum with only Red and Blue, put an empty wildcard first and return 7 and 8 from the two named arms. The
  original L0 and L1 reports observed a missing-return error even though generated dispatch selects the named arms.

## Accepted rule

An enum `match` or scalar `case` may have at most one `_ =>` arm, anywhere. Evaluate the scrutinee once. Select a
matching explicit arm wherever it appears. Select the fallback only when every explicit arm misses. Execute the selected
body once, with no arm-to-arm fallthrough. Writing the fallback last is customary. First, middle and last positions are
equally warning-free when the fallback is reachable.

Preserve existing pattern and value forms, arm-body syntax, and each construct's rules when the fallback is absent. This
decision applies to the enum and scalar statements available today.

## Implementation

1. **Enum checking and flow.** Validate every named pattern before computing wildcard reachability. Unknown and
   wrong-owner variants and invalid payload patterns supply no coverage. If a wildcard is present and the validated
   named arms cover the whole enum, warn once with `TYP-0105` at the wildcard, wherever it occurs. Check its body for
   ordinary source errors. Exclude its effects from definite return, fallthrough, ownership and liveness joins
   (including loop exits). Inspect `l0_check_patterns.py` and `l0_check_flow.py` in Python, `expr_types/patterns` and
   `expr_types/flow` in native L0, and `expr_types/patterns` and `expr_types/stmt` in canonical L1 and L2.
2. **Scalar parsing and diagnostics.** Allow value arms on either side of the one default in the Python parser and all
   three native `parser/stmt` modules. Retire `PAR-0234` from the live catalog, Stage 1 inventory and trigger matrix,
   shared `scripts/diagnostic_parity.py` fixtures, L1 `compiler/tests/fixtures/diagnostics/codes.json`, and L2
   `compiler/tests/fixtures/diagnostics.json`. Record retirement under the diagnostic stability policy and keep the
   number unavailable for reassignment. Preserve duplicate wildcards (`PAR-0176` for match, `PAR-0236` for case),
   duplicate case values (`TYP-0108`) and rejected legacy `case ... else` (`PAR-0123` for unmatched `else`). Replace
   recovery examples that depend on `PAR-0234` with genuinely malformed arms, such as a missing `=>`. Keep assertions
   for diagnostic count, exact source span, later errors, and surviving statements/declarations. The rule requires no
   new diagnostic or code reservation.
3. **Dispatch.** Inspect generated C and run probes before editing any emitter. Follow the enum switch, scalar switch,
   string comparison chain, and lone-fallback path in `l0_backend_lowering.py`, Stage 2 `backend/lowering.l0`, L1
   `backend/lower.l0`, and L2 `backend/lower.l1`. Reuse paths that already evaluate once, prefer explicit arms and
   execute one body. Review any emitter-side flow joins against the checker's reachable-arm set.
4. **Grammars and editors.** Update all three level grammar references. Preserve L0 block bodies for `match`, L1/L2
   statement bodies and each level's scalar case values. In the shared Tree-sitter grammar allow value arms before and
   after an optional, unique `case_default_arm`. Preserve that named node, `wildcard_pattern` for match and their
   highlight captures. Regenerate the checked-in parser and node metadata. Add first/middle/last corpus cases with clean
   trees and assert the fallback node in each. Keep malformed and legacy-default recovery coverage.
5. **Decision record.** Reconcile the grammars, catalog and ADR-0007 with the verified implementations. Retain the
   migration history: a trailing `else` after an unbraced `if` arm could bind to the inner `if`. Moving `_ =>` does not
   change that grammar boundary. This shared plan owns the decision and per-target results for #9 and #10.

## Acceptance matrix

Run these cases independently through each compiler using level-owned sources. Use distinct per-value assertions so
swapping Red and Blue cannot pass.

1. **Partial named coverage.** With Red, Blue and Green, return 7 for Red, 8 for Blue and 9 from the wildcard. Run all
   three wildcard positions. Each program returns the expected result for each variant with zero `TYP-0105` warnings.
2. **Complete named coverage.** With only Red and Blue, both named arms return; the wildcard body is empty and no return
   follows the match. All three orders compile, warn exactly once at the wildcard and return 7 for Red and 8 for Blue.
   Add Green without an explicit arm: the wildcard is reachable, so each order reports `TYP-0010` and zero `TYP-0105`.
3. **Validation and flow.** A bad owner, unknown variant or wrong payload arity cannot complete coverage. Reject
   duplicate wildcards. In a redundant wildcard drop a live pointer that is used after the match; its liveness must
   survive. In a separate redundant body put an ordinary type/name error and require its diagnostic. Keep exhaustive
   named-only and missing-variant (`TYP-0104`) controls.
4. **Scalar dispatch.** For integer and string scrutinees, place the fallback first, middle and last. Exercise each
   explicit value and a miss, including a match after an earlier fallback. Count scrutinee calls and record arm effects
   separately: one evaluation, exactly the expected body. Include a lone fallback, hit and miss without a fallback,
   duplicate defaults, and equal values on opposite sides of the fallback.

## Verification

Record each target's command, compiler/host, result, diagnostic counts and per-input runtime outcomes here when run.
Identify any unverified coverage. Compiler and editor acceptance is pending on all targets.

- **L0 Stage 1.** From `l0/`, run the L0 fixtures through `./scripts/l0c --check` and `./scripts/l0c --run`. Run these
  focused suites:

  ```sh
  ../.venv/bin/python -m pytest -q \
    compiler/stage1_py/tests/parser/test_parser_recovery.py \
    compiler/stage1_py/tests/integration/test_case_statement.py \
    compiler/stage1_py/tests/type_checker/test_match_exhaustiveness.py \
    compiler/stage1_py/tests/type_checker/test_control_flow.py \
    compiler/stage1_py/tests/name_resolver/test_qualified_names.py \
    compiler/stage1_py/tests/backend/test_codegen_semantics.py \
    compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py
  ```

- **L0 Stage 2.** From `l0/`, run
  `make test-stage2 TESTS="parser_test expr_types_test backend_test l0c_build_run_test diagnostic_code_parity_test diagnostic_message_parity_test"`.
  Run the same L0 fixtures through `./build/dea/bin/l0c-stage2` in both modes.

- **L1.** From `l1/`, run
  `make test-compiler TESTS="parser_test expr_types_test backend_test l1c_build_run_multi_cu_test diagnostic_code_parity_test diagnostic_message_parity_test"`.
  Run L1-owned `.l1` fixtures with the built `l1c --check` and `l1c --run`.

- **L2.** From `l2/`, export `L2_BOOTSTRAP_L1C` as the absolute path to a compatible installed `l1c`, then run
  `make build` and
  `make test-compiler TESTS="parser_test expr_types_test backend_test l2c_build_run_multi_cu_test diagnostic_contract_test"`.
  For a development bootstrap also select `L2_BOOTSTRAP_MODE=development` and the explicit built L1 launcher as
  documented in [l2/AGENTS.md](../../../l2/AGENTS.md). Run L2-owned **`.l2`** fixtures with the resulting
  `./build/dea/bin/l2c --check` and `./build/dea/bin/l2c --run`. Record the bootstrap selection separately from the
  target compiler. The `.l1` implementation tests alone cannot demonstrate L2 dispatch.

- **Editors and repository.** From the root, run `make -C editors test` (including Tree-sitter regeneration, corpus and
  queries), `python3 scripts/check_adr_impact.py --all-active`, and `make test` with the explicit L2 environment. Run
  focused ownership/trace tests for changed liveness or cleanup paths. At closure run the staged ADR and pre-commit
  checks, update the roadmaps and link the closed plans from ADR-0007.

## ADR Impact

- Decision: A wildcard is a position-independent fallback in Dea enum `match` and scalar `case`.
  - Scope: Dea-wide
  - Disposition: Amend ADR
  - ADR: `docs/decisions/0007-case-default-arm-wildcard.md`
  - Rationale: The existing wildcard migration record owns the spelling and former placement restriction. One amendment
    records selection and reachability for both constructs and preserves the reason for removing the legacy default.
