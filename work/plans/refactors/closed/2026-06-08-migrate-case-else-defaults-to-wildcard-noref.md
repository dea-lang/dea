# Refactor Plan

## Migrate in-tree `case` default `else` arms to `_ =>`

- Date: 2026-06-08
- Status: Completed
- Title: Migrate every in-tree `case`-default `else` arm to the canonical `_ =>` spelling
- Kind: Refactor
- Scope: Shared
- Severity: Low
- Stage: Shared
- Targets:
  - L0
  - L1
- Origin: Phase 1 made `_ =>` canonical and deprecated the `else` default (`PAR-0242`); this canonicalizes the sources
- Depends on: the committed Phase 1 work and `PAR-0123` bug-fix; both `else` and `_ =>` are accepted.
- Subsystem: In-tree `.l0` / `.l1` sources, fixtures, examples
- Modules: every `.l0` / `.l1` file that uses a `case`-default `else` (enumerated by the `PAR-0242` sweep below)

## Context

Phase 1 (ADR-0007) made `_ =>` the canonical `case` default and deprecated the `else` default with the `PAR-0242`
warning, while keeping `else` working. Both spellings lower to the identical AST (`CaseElse` with a body), so rewriting
`case … else <Stmt>` to `_ => <Stmt>` is behavior-preserving — it only silences the deprecation warning.

This refactor canonicalizes all in-tree sources now, independently and at any time. It is the prerequisite for the two
Phase 2 grammar-removal plans ([L1](../../../l1/work/plans/features/2026-06-08-case-else-removal-l1-phase2-noref.md),
[L0](../../../l0/work/plans/features/2026-06-08-case-else-removal-l0-phase2-noref.md)): once no in-tree source uses an
`else` default, those plans become pure behavior-only changes (remove the grammar/parser path, retire the codes) with no
coupled migration.

## Proposed Changes

1. **Enumerate the sites.** Build/check the L0 and L1 trees with the current compilers and collect every `PAR-0242`
   emission — that is exactly the set of `case`-default `else` arms (the compiler is the oracle; a textual grep cannot
   distinguish a case-default `else` from an `if … else`, and `case`/`else` inside test *string literals* are not
   compiled as code, so they are correctly excluded). Known candidate files:
   - `.l0`: `l0/compiler/stage2_l0/src/{lexer,tokens,…}.l0`, `l0/examples/*.l0`, L0 fixtures
     (`backend_golden/match_case/main.l0`, `semantics/ok_main.l0`, `typing/typing_case_diag_err.l0`), and the L1
     compiler's `.l0` data files (`l1/compiler/stage1_l0/src/{lexer,tokens,expr_types,util/numbers,util/demangler}.l0`).
   - `.l1`: `l1/examples/*.l1`,
     `l1/compiler/stage1_l0/tests/fixtures/{semantics/ok_main, semantics/single_stmt_bodies_main, driver/single_stmt_bodies_main, typing/typing_case_diag_err, typing/typing_large_int_ok, typing/typing_large_int_err}.l1`.
2. **Rewrite** each site `case (...) { … else <Stmt> }` → `… _ => <Stmt>` (drop the `else` keyword, insert `_ =>`). Keep
   the body unchanged.
3. **Do not touch** parser-test cases that deliberately exercise the deprecated `else` via string literals
   (`test_case_else_deprecation_warning`, the `else if … else` default-body tests in `parser_test.l0`); they cover the
   still-present Phase 1 path and are removed by the grammar-removal plans, not here.
4. **Goldens:** generated-C goldens are unaffected (the AST is spelling-neutral). If any AST-dump golden captures source
   spans, regenerate it (`make refresh-goldens`), since `_ =>` and `else` differ in span.

## Verification

1. A full build of both trees emits **zero `PAR-0242` warnings**: e.g. `cd l0 && make use-dev-stage2` and
   `cd l1 && make use-dev-stage1` produce no `PAR-0242`.
2. `cd l0 && make -j test-all` + `make triple-test` pass; `cd l1 && make test-stage1` passes; both `check-examples` pass
   with no warnings or errors.
3. No change to diagnostic codes, grammar docs, parser logic, or ADRs; behavior is identical.

## Non-Goals

1. Removing `else` as a `case` default or retiring `PAR-0242`/`0243` (the grammar-removal plans).
2. Any parser, grammar, catalog, or ADR change.

## Completion Notes

- Swept all L0 and L1 source files using `PAR-0242` warnings.
- Canonicalized all instances of `else` within `case` statements to `_ =>`.
- Validated via successful L0 (`make test-all`) and L1 (`make test-stage1`) suites with zero regressions or deprecation
  warnings emitted.
