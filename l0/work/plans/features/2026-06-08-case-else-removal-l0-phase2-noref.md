# Feature Plan

## `case` default arm `_ =>`, Phase 2 (L0): remove `else` and retire the interim codes

- Date: 2026-06-08
- Status: Draft
- Title: Remove `else` as a `case` default arm in L0 Stage 1 + Stage 2 and retire `PAR-0242`/`0243`
- Kind: Feature
- Scope: L0
- Severity: Medium
- Stage: L0 (Stage 1 + Stage 2)
- Targets:
  - L0 Stage 1
  - L0 Stage 2
- Origin: Dangling-`else` ambiguity retired by making `_ =>` the sole `case` default
- Depends on:
  - The source-migration prerequisite
    [work/plans/refactors/2026-06-08-migrate-case-else-defaults-to-wildcard-noref.md](../../../../work/plans/refactors/2026-06-08-migrate-case-else-defaults-to-wildcard-noref.md):
    all in-tree compiled `.l0` `case … else` defaults, including `.l0` files under `l1/`, must already be `_ =>` before
    this plan removes the `else` grammar.
  - The committed `PAR-0123` bug-fix. Independent of the L1 plan
    ([l1/work/plans/features/2026-06-08-case-else-removal-l1-phase2-noref.md](../../../../l1/work/plans/features/2026-06-08-case-else-removal-l1-phase2-noref.md));
    intended to land second.
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
`_ =>`; this plan removes `else` as an L0 `case` default and retires the interim codes. It carries the shared cleanup;
the L1 half is a separate plan.

Note the cross-level reality: the L1 compiler is itself `.l0` (`l1/compiler/stage1_l0/src/*.l0`), compiled by L0 Stage
2, so any remaining `case … else` default there would be governed by this L0 grammar change. The prerequisite refactor
must therefore have already canonicalized those files before this plan lands. (The L1 *parser logic* in
`l1/.../parser/stmt.l0` is the L1 plan's concern and has no `case … else` of its own.)

## Proposed Changes

1. **Parsers (Stage 1 oracle first, then Stage 2):** in `_parse_case_stmt` / `ps_parse_case_stmt`, remove the
   `else`-default branch; a stray `case`-arm `else` emits `PAR-0123`. Revert the Phase 1 ambiguity scaffolding: remove
   `_parse_case_value_arm_body` / `ps_parse_case_value_arm_body` and the `guard_dangling_else` parameter on
   `_parse_if_stmt` / `ps_parse_if_stmt` (and its two call sites), so `1 => if (c) x; else y;` parses cleanly. Drop the
   now-unused `_warning` / `ps_emit_warning` if unreferenced.
2. **Shared diagnostic retirement:** remove `PAR-0242`/`0243` from `l0_diagnostics.py` `DIAGNOSTIC_CODE_FAMILIES`,
   `test_diagnostic_codes.py` (`PAR_TRIGGERS` / `WARNING_CODES`), and the catalog rows; reword the Phase 1 generalized
   meanings back to `_`-only: `PAR-0234` "value arm cannot appear after the `_` default arm", `PAR-0236` "duplicate `_`
   default arm", `PAR-0238` "expected value literal or `_` in `case` arm". If the L1 plan landed first and added a
   `PAR-0242`/`0243` `l1` skip in `scripts/diagnostic_parity.py`, remove it (now moot). Bump catalog `Version:`.
3. **Tests:** remove the L0 Phase 1 `PAR-0242`/`0243` tests and the `else if … else` default-body test; add tests that a
   stray `case`-arm `else` emits `PAR-0123`, `_ =>` is the only default, and `1 => if (c) x; else y;` parses cleanly.
4. **Grammar** (`l0/docs/reference/grammar.md`): terminal form below; remove the Phase 1 `PAR-0243`/deprecation prose;
   bump `Version:`.

```ebnf
CaseStmt    ::= "case" "(" Expr ")" "{" CaseArm* WildcardArm? "}"
CaseArm     ::= CaseLiteral "=>" Stmt
WildcardArm ::= "_" "=>" Stmt
```

5. **Lifecycle:** update `docs/decisions/0007-case-default-arm-wildcard.md` to record Phase 2 complete (terminal
   grammar, retirement of `PAR-0242`/`0243`); bump `Last edited:`. `git mv` the Phase 1 plan
   (`work/plans/features/2026-06-07-case-default-arm-wildcard-phase1-noref.md`) into `closed/` and repoint ADR-0007's
   Related Plans link.

## Verification

1. `_ =>` is the only accepted L0 `case` default across Stage 1 and Stage 2; `case (x) { 1 => …; else … }` emits
   `PAR-0123`; `1 => if (c) x; else y;` parses cleanly.
2. A pre-removal build/check sweep confirms the source-migration prerequisite: no compiled in-tree `.l0` source emits
   `PAR-0242`.
3. `rg 'PAR-0242|PAR-0243' l0 l1` is empty except historical ADR/plan prose; diagnostic-code parity tests pass.
4. Whole-tree build clean: `cd l0 && make -j test-all` + `make triple-test`; `cd l1 && make test-stage1` still green;
   both `check-examples` with no warnings/errors.
5. `l0/docs/reference/grammar.md` version-bumped to terminal form; catalog updated; ADR-0007 updated; Phase 1 plan
   closed and its ADR link repointed.

## Non-Goals

1. L1 parser changes (the L1 plan) and any source migration (the prerequisite refactor plan).
2. Any change to `match` or `with`; the block-body alternative; new tokens/keywords; no new ADR.
