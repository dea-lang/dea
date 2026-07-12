# Feature Plan

## `case` default arm `_ =>`, Phase 2 (L0): remove `else` and retire the interim codes

- Date: 2026-06-08
- Status: Draft
- Title: Remove `else` as a `case` default arm in L0 Stage 1 + Stage 2 and retire `PAR-0242`/`0243`
- Kind: Feature
- Scope: L0
- Severity: Medium
- Stage: L0 (Stage 1 + Stage 2)
- Target release: L0 2.0.0
- Targets:
  - L0 Stage 1
  - L0 Stage 2
- Origin: Dangling-`else` ambiguity retired by making `_ =>` the sole `case` default
- Depends on:
  - The completed source-migration prerequisite
    [work/plans/refactors/closed/2026-06-08-migrate-case-else-defaults-to-wildcard-noref.md](../../../../work/plans/refactors/closed/2026-06-08-migrate-case-else-defaults-to-wildcard-noref.md):
    all in-tree compiled `.l0` `case … else` defaults, including `.l0` files under `l1/`, are already `_ =>` before this
    plan removes the `else` grammar.
  - The completed `PAR-0123` bug fix
    ([work/plans/bug-fixes/closed/2026-06-07-stray-keyword-diagnostics-and-stmt-recovery-noref.md](../../../../work/plans/bug-fixes/closed/2026-06-07-stray-keyword-diagnostics-and-stmt-recovery-noref.md)).
  - The independent L1 Phase 2 plan has already landed
    ([l1/work/plans/features/closed/2026-06-08-case-else-removal-l1-phase2-noref.md](../../../../l1/work/plans/features/closed/2026-06-08-case-else-removal-l1-phase2-noref.md)).
- Subsystem: Parser / grammar / diagnostics / docs / ADR
- Modules:
  - `l0/compiler/stage1_py/l0_parser.py`, `l0_diagnostics.py`
  - `l0/compiler/stage1_py/tests/integration/test_case_statement.py`, `tests/diagnostics/test_diagnostic_codes.py`
  - `l0/compiler/stage2_l0/src/parser/stmt.l0`, `tests/parser_test.l0` (+ Stage 2 fixtures)
  - `l0/docs/reference/grammar.md`, `docs/specs/compiler/diagnostic-code-catalog.md`
  - `docs/decisions/0007-case-default-arm-wildcard.md`, `docs/decisions/INDEX.md` (no new ADR)
  - `scripts/diagnostic_parity.py` (remove the now-moot `l1` skip if the L1 plan added it)

## Context

This is the L0 half of Phase 2 (ADR-0007). Phase 1 made `_ =>` canonical, deprecated `else` (`PAR-0242`), and added the
ambiguity error `PAR-0243`. The prerequisite source-migration refactor has already rewritten in-tree `.l0` sources to
`_ =>`, and the independent L1 half is complete. L0 retains the compatibility spelling throughout the 1.x release line;
this plan is explicitly deferred to L0 2.0.0, where it will remove `else` as an L0 `case` default and retire the interim
codes. It is not a prerequisite for L0 1.1.0.

Note the cross-level reality: the L1 compiler is itself `.l0` (`l1/compiler/stage1_l0/src/*.l0`), compiled by L0 Stage
2, so any remaining `case … else` default there would be governed by this L0 grammar change. The prerequisite refactor
has already canonicalized those files. The L1 *parser logic* in `l1/.../parser/stmt.l0` was handled by the completed L1
Phase 2 plan and has no `case … else` of its own.

## Proposed Changes

1. **Parsers (Stage 1 oracle first, then Stage 2):** in `_parse_case_stmt` / `ps_parse_case_stmt`, remove the
   `else`-default branch; a stray `case`-arm `else` emits `PAR-0123`. Revert the Phase 1 ambiguity scaffolding: remove
   `_parse_case_value_arm_body` / `ps_parse_case_value_arm_body` and the `guard_dangling_else` parameter on
   `_parse_if_stmt` / `ps_parse_if_stmt` (and its two call sites), so `1 => if (c) x; else y;` parses cleanly. Drop the
   now-unused `_warning` / `ps_emit_warning` if unreferenced.
2. **Shared diagnostic retirement:** remove `PAR-0242`/`0243` from `l0_diagnostics.py` `DIAGNOSTIC_CODE_FAMILIES`,
   `test_diagnostic_codes.py` (`PAR_TRIGGERS` / `WARNING_CODES`), and the catalog rows; reword the Phase 1 generalized
   meanings back to `_`-only: `PAR-0234` "value arm cannot appear after the `_` default arm", `PAR-0236` "duplicate `_`
   default arm", `PAR-0238` "expected value literal or `_` in `case` arm". Remove the now-moot `PAR-0242`/`0243` `l1`
   skip added by the completed L1 plan in `scripts/diagnostic_parity.py`. Bump catalog `Version:`.
3. **Tests:** remove the L0 Phase 1 `PAR-0242`/`0243` tests and the `else if … else` default-body test; add tests that a
   stray `case`-arm `else` emits `PAR-0123`, `_ =>` is the only default, and `1 => if (c) x; else y;` parses cleanly.
4. **Grammar** (`l0/docs/reference/grammar.md`): terminal form below; remove the Phase 1 `PAR-0243`/deprecation prose;
   bump `Version:`.

```ebnf
CaseStmt    ::= "case" "(" Expr ")" "{" CaseArm* WildcardArm? "}"
CaseArm     ::= CaseLiteral "=>" Stmt
WildcardArm ::= "_" "=>" Stmt
```

5. **Lifecycle:** update `docs/decisions/0007-case-default-arm-wildcard.md` to record L0 Phase 2 complete (terminal
   grammar, retirement of `PAR-0242`/`0243`); bump `Last edited:`. Move this plan into `l0/work/plans/features/closed/`
   and add it to ADR-0007's Related Plans.

## Verification

1. `_ =>` is the only accepted L0 `case` default across Stage 1 and Stage 2; `case (x) { 1 => …; else … }` emits
   `PAR-0123`; `1 => if (c) x; else y;` parses cleanly.
2. A pre-removal build/check sweep confirms the source-migration prerequisite: no compiled in-tree `.l0` source emits
   `PAR-0242`.
3. `rg 'PAR-0242|PAR-0243' l0 l1` is empty except historical ADR/plan prose; diagnostic-code parity tests pass.
4. Whole-tree build clean: `cd l0 && make -j test-all` + `make triple-test`; `cd l1 && make test-stage1` still green;
   both `check-examples` with no warnings/errors.
5. `l0/docs/reference/grammar.md` version-bumped to terminal form; catalog updated; ADR-0007 updated; this plan closed
   and linked from the ADR.

## Non-Goals

1. Further L1 parser changes or source migration; those were completed in their separate plans.
2. Any change to `match` or `with`; the block-body alternative; new tokens/keywords; no new ADR.
