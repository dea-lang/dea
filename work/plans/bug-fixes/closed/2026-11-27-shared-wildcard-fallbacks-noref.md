# Bug Fix Plan

## Apply position-independent wildcard fallbacks to enum match and scalar case

- Date: 2026-11-27
- Status: Completed
- Title: Apply position-independent wildcard fallbacks to enum match and scalar case
- Kind: Bug Fix
- Severity: Medium
- Scope: Shared
- Targets:
  - L0 Stage 1 (Python)
  - L0 Stage 2 (L0)
  - Canonical L1 (L0)
  - Shared Tree-sitter grammar
  - Canonical L2 (L1), deferred
- Origin: The L0 and L1 enum match reports found that return checking and executable dispatch disagreed.
- Porting rule: Use the accepted Dea-wide semantics with level-owned fixtures. Port to L2 after the stable L1 catch-up.
- Target status:
  - L0 Stage 1: Implemented
  - L0 Stage 2: Implemented
  - Canonical L1: Implemented
  - Shared Tree-sitter grammar: Implemented
  - Canonical L2: Deferred: port and verify after the stable L1 catch-up.
- Subsystem: Enum pattern coverage, statement flow, scalar case parsing and C dispatch.
- Repro: Place an empty wildcard before returning named arms for every variant of a two-variant enum. The former checker
  reported a missing return.
- Related:
  - [l0/work/plans/bug-fixes/closed/2026-11-21-match-wildcard-precedence-and-return-flow-noref.md](../../../../l0/work/plans/bug-fixes/closed/2026-11-21-match-wildcard-precedence-and-return-flow-noref.md)
  - [l1/work/plans/bug-fixes/closed/2026-11-21-match-wildcard-dispatch-and-return-flow-noref.md](../../../../l1/work/plans/bug-fixes/closed/2026-11-21-match-wildcard-dispatch-and-return-flow-noref.md)
  - [docs/decisions/0007-case-default-arm-wildcard.md](../../../../docs/decisions/0007-case-default-arm-wildcard.md)
  - [docs/specs/compiler/diagnostic-code-catalog.md](../../../../docs/specs/compiler/diagnostic-code-catalog.md)
  - [l2/work/plans/features/2026-10-27-stable-l1-catch-up-noref.md](../../../../l2/work/plans/features/2026-10-27-stable-l1-catch-up-noref.md)

## Accepted rule

An enum `match` or scalar `case` may have at most one `_ =>` arm, anywhere. Evaluate the scrutinee once. Select a
matching explicit arm wherever it appears. Select the fallback only when every explicit arm misses. Execute the selected
body once, with no arm-to-arm fallthrough. Writing the fallback last is customary. First, middle and last positions are
equally warning-free when the fallback is reachable.

Preserve existing pattern and value forms, arm-body syntax, and each construct's rules when the fallback is absent. This
decision applies to the enum and scalar statements available today.

## Implementation and findings

- Enum coverage uses all successfully validated named arms. A bad owner, unknown variant or invalid payload contributes
  no coverage. A redundant wildcard warns once at its token. The checker still visits its body for source errors and
  excludes it from definite return, fallthrough, ownership joins and loop exits. Lowering omits that arm, so an empty
  redundant fallback cannot introduce a fallthrough path in the generated C.
- All three compilers already saved the scrutinee and preferred explicit arms in their switch or comparison chain. The
  two native emitters needed one correction for a string case with just a fallback. Its body now forms an unconditional
  block instead of emitting an orphaned C `else`.
- Scalar parsers accept values after the fallback. Malformed-arm recovery uses duplicate defaults, unmatched `else` and
  a missing arrow, with checks for exact token locations and surviving statements and declarations. `PAR-0234` is
  retired in L0 and L1. It remains assigned in L2 pending its port.
- The editor grammar admits case value arms on either side of one named `case_default_arm`. A single underscore cannot
  be lexed as an identifier after a default. Multi-character underscore-prefixed identifiers remain available.

## Acceptance results

- Across first, middle and last positions, Red returned 7, Blue returned 8 and uncovered Green returned 9. All three
  reachable wildcards were warning-free. With only Red and Blue and an empty wildcard, each ordering compiled without a
  trailing return and warned once at its own wildcard. Restoring Green produced one `TYP-0010` per ordering and zero
  `TYP-0105` warnings.
- A redundant body dropping a pointer preserved its use after the match. A separate invalid redundant body produced both
  `TYP-0105` and its ordinary type error. Unknown variants, wrong owners and wrong payload arities retained their
  diagnostics. Duplicate payload bindings report `TYP-0020` and supply no coverage. Duplicate match wildcards and
  duplicate scalar defaults and values remained errors.
- Integer and string cases selected each explicit value or the fallback, with one scrutinee evaluation and one
  observable arm effect. The fixtures also exercised a lone string fallback and hit/miss behavior without a fallback.

## Local verification

Host: macOS Intel. L0 used its Python Stage 1 compiler and native Stage 2 launcher. L1 used the canonical compiler built
with repo-local L0 Stage 2. Each level's execution suite checked and ran its own target fixtures.

- From `l0/`, run `../.venv/bin/python -m pytest -q` on the following modules under `compiler/stage1_py/tests/`:
  `parser/test_parser_recovery.py`, `integration/test_case_statement.py`, `type_checker/test_match_exhaustiveness.py`,
  `type_checker/test_control_flow.py`, `name_resolver/test_qualified_names.py`, `backend/test_codegen_semantics.py` and
  `diagnostics/test_diagnostic_codes.py`. All 450 tests passed.
- From `l0/`, run
  `make test-stage2 TESTS="parser_test expr_types_test backend_test l0c_build_run_test diagnostic_code_parity_test diagnostic_message_parity_test"`.
  All six suites passed. The focused trace runner
  `compiler/stage2_l0/scripts/run_trace_tests.py expr_types_test backend_test` reported zero leaked object and string
  pointers.
- From `l1/`, run
  `make test-compiler TESTS="parser_test expr_types_test backend_test l1c_build_run_multi_cu_test diagnostic_code_parity_test diagnostic_message_parity_test"`.
  All six suites passed. The focused trace runner `compiler/scripts/run_trace_tests.py expr_types_test backend_test`
  reported zero leaked object and string pointers.
- At the repository root, `make -C editors test` passed regeneration, all 12 corpus cases, highlight queries, TextMate
  and the five fallback editor checks. The active and staged ADR checks and root pre-commit checks passed.
- L2 implementation and verification follow the stable L1 catch-up. At activation, port the rule and the acceptance
  cases into L2-owned sources, retire its remaining `PAR-0234` registration, update its grammar reference, and build
  with an explicit `L2_BOOTSTRAP_L1C` per [l2/AGENTS.md](../../../../l2/AGENTS.md). Run `.l2` fixtures with the
  resulting `l2c --check` and `l2c --run`. Cross-platform CI is separate from local verification.

## ADR Impact

- Decision: A wildcard is a position-independent fallback in Dea enum `match` and scalar `case`.
  - Scope: Dea-wide
  - Disposition: Amend ADR
  - ADR: `docs/decisions/0007-case-default-arm-wildcard.md`
  - Rationale: The existing wildcard migration record owns the spelling and former placement restriction. One amendment
    records selection and reachability for both constructs and preserves the reason for removing the legacy default.
