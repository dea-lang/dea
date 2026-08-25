# Feature Plan

## `case` default arm `_ =>`, Phase 2 (L1): remove `else`

- Date: 2026-06-08
- Status: Completed
- Title: Remove `else` as a `case` default arm in L1 Stage 1
- Kind: Feature
- Scope: L1
- Severity: Medium
- Stage: 1
- Target: L1 Stage 1
- Origin: Dangling-`else` ambiguity retired by making `_ =>` the sole `case` default
- Depends on:
  - The source-migration prerequisite
    [work/plans/refactors/closed/2026-06-08-migrate-case-else-defaults-to-wildcard-noref.md](../../../../../work/plans/refactors/closed/2026-06-08-migrate-case-else-defaults-to-wildcard-noref.md):
    all in-tree `.l1` `case … else` defaults must already be `_ =>` before this plan removes the `else` grammar.
  - The committed bug-fix
    ([work/plans/bug-fixes/closed/2026-06-07-stray-keyword-diagnostics-and-stmt-recovery-noref.md](../../../../../work/plans/bug-fixes/closed/2026-06-07-stray-keyword-diagnostics-and-stmt-recovery-noref.md)),
    which introduced `PAR-0123` ("else without if"). This plan routes a stray `case`-arm `else` to it.
- Subsystem: Parser / grammar / diagnostics parity / tests
- Modules:
  - `l1/compiler/stage1_l0/src/parser/stmt.l0`
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/docs/reference/grammar.md`
  - `scripts/diagnostic_parity.py`

## Context

This is the L1 half of Phase 2 of the `case` default-arm cleanup (ADR-0007). Phase 1 made `_ =>` the canonical default,
deprecated `else` (`PAR-0242` warning), and added the ambiguity error `PAR-0243`, keeping `else` working. This plan
removes `else` as an L1 `case` default after the prerequisite source-migration refactor has already rewritten in-tree
`.l1` sources to `_ =>`.

This plan is independent of the L0 half and is intended to land first: L1 is unreleased, the two levels are independent,
and both move in the same direction. The shared `PAR-0242`/`0243` retirement and the catalog/ADR updates belong to the
L0 plan
([l0/work/plans/features/closed/2026-06-08-case-else-removal-l0-phase2-noref.md](../../../../../l0/work/plans/features/closed/2026-06-08-case-else-removal-l0-phase2-noref.md)).

## Why this is safe before the L0 plan

Diagnostic parity is oracle-driven and forward-only: `scripts/diagnostic_parity.py` runs the L0 Python oracle's trigger
matrix through each self-hosted stage, with a per-stage `skip` set. Removing `else`-as-default in L1 is an intentional
behavioral divergence on the case-`else` input, not a parity failure; it is expressed by skipping `PAR-0242`/`0243` for
the `l1` stage. L0 keeps emitting and is still checked for those codes until the L0 plan retires them. There is no
reverse "emits only registered codes" check, so L1 emitting nothing/`PAR-0123` for that input while the codes remain
registered is fine.

The L1 compiler's own `.l0` data files are compiled by L0 Stage 2, so their source spelling is outside this L1 parser
change. The prerequisite refactor already canonicalizes them to `_ =>`; the L0 plan later removes the L0 grammar path
that still accepts `else`.

## Proposed Changes

1. **Parser** (`l1/compiler/stage1_l0/src/parser/stmt.l0`): in `ps_parse_case_stmt`, remove the `else`-default branch; a
   stray `case`-arm `else` emits `PAR-0123`. Revert the Phase 1 ambiguity scaffolding: remove
   `ps_parse_case_value_arm_body` and the `guard_dangling_else` parameter on `ps_parse_if_stmt` (and its two call
   sites), so value-arm `if` bodies use the plain eager-`else` parse and `1 => if (c) x; else y;` parses cleanly (no
   `PAR-0243`). Drop the now-unused `ps_emit_warning` if nothing else references it.
2. **Parity** (`scripts/diagnostic_parity.py`): add `PAR-0242` and `PAR-0243` to the `l1`-stage `skip` set (the
   intentional divergence from the oracle).
3. **Tests** (`l1/compiler/stage1_l0/tests/parser_test.l0`): remove `test_case_else_deprecation_warning` and the
   `else if … else` default-body acceptance test; add tests that a stray `case`-arm `else` emits `PAR-0123`, that `_ =>`
   is the only default, and that `1 => if (c) x; else y;` parses cleanly.
4. **Grammar** (`l1/docs/reference/grammar.md`): terminal form below; remove the Phase 1 `PAR-0243`/deprecation prose;
   bump `Version:`.

```ebnf
CaseStmt    ::= "case" "(" Expr ")" "{" CaseArm* WildcardArm? "}"
CaseArm     ::= CaseLiteral "=>" Stmt
WildcardArm ::= "_" "=>" Stmt
```

## Verification

1. `_ =>` is the only accepted L1 `case` default; `case (x) { 1 => …; else … }` emits `PAR-0123`;
   `1 => if (c) x; else y;` parses cleanly (no `PAR-0243`).
2. A pre-removal build/check sweep confirms the source-migration prerequisite: no compiled in-tree `.l1` source emits
   `PAR-0242`.
3. `cd l1 && make test-stage1` passes (incl. `diagnostic_code_parity_test` with the new `l1` skips) and
   `make check-examples` is clean.
4. L0 is untouched and stays green (`cd l0 && make test-stage2` / `make triple-test` unaffected).

## Non-Goals

1. L0 parser changes, the shared `PAR-0242`/`0243` retirement, catalog/ADR updates, and Phase 1 plan closure: all in the
   L0 plan. Any source migration belongs to the prerequisite refactor plan.
2. Any change to `match` or `with`; the block-body alternative; new tokens/keywords.

## ADR Impact

- Decision: Advance L1 to the terminal wildcard-only `case` default grammar before L0.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0007-case-default-arm-wildcard.md`
  - Rationale: ADR-0007 records the level-specific rollout and the terminal `_ =>` grammar shared by L0 and L1.
- Decision: Represent the intentional L1-ahead-of-L0 behavior as narrow parity exceptions with an upstream-convergence
  retirement condition.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0014-intentional-cross-level-divergence-and-parity-exceptions.md`
  - Rationale: ADR-0014 governs forward-only cross-level migrations and the lifecycle of their parity exceptions.
