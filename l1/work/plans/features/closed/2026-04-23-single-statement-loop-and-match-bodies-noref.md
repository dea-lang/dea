# Feature Plan

## Allow single-statement `while`/`for` bodies and `match` arms

- Date: 2026-04-23
- Status: Completed
- Title: Allow single-statement `while`/`for` bodies and `match` arms
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Parser / scope analysis / backend / grammar docs
- Modules:
  - `l1/compiler/stage1_l0/src/parser/stmt.l0`
  - `l1/compiler/stage1_l0/src/locals.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/locals_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/docs/reference/grammar.md`
- Repro: `make -C l1 test-stage1 TESTS="parser_test locals_test backend_test l0c_lib_test" && make clean test-all`

## Summary

Current L1 requires block bodies for `while`, `for`, and `match` arms, even though `if` branches and `case` arms already
operate over generic `Stmt`. This plan relaxes those three grammar positions so terse forms such as
`while (...) x = x + 1;` and `match (...) { Red() => return 1; }` become valid without changing the existing block form.

## Completion Notes

1. `ps_parse_while_stmt()`, `ps_parse_for_stmt()`, and `ps_parse_match_stmt()` now parse body positions through
   `ps_parse_stmt()`, preserving existing `for` clause semicolon handling while allowing non-block loop and match-arm
   bodies.
2. `locals.l0` now routes `while`, `for`, `match`, and `case` bodies through one shared synthetic-scope helper so block
   and non-block bodies both receive the same body-local scope contract.
3. `backend.l0` now lowers loop bodies and match arms through the same scoped-body helper, so single-statement forms
   keep the same cleanup, pattern-binding, and control-flow behavior as block bodies.
4. Regression coverage now includes parser, locals, backend, and CLI/runtime tests plus dedicated semantics and driver
   fixtures for single-statement `while`, `for`, `match`, and `case` forms.
5. `l1/docs/reference/grammar.md` now documents `WhileStmt`, `ForStmt`, and `MatchArm` over `Stmt`, and
   `l1/docs/roadmap.md` now records the feature as shipped baseline rather than active planned work.

## Current State

1. `ps_parse_case_stmt()` already uses `ps_parse_stmt()` for both value arms and `else`, so
   `case (name) { "Mario" => return 1; "Luigi" => return 2; else return 0; }` is already supported.
2. `ps_parse_while_stmt()`, `ps_parse_for_stmt()`, and `ps_parse_match_stmt()` still hard-wire `ps_parse_block()` for
   their body positions.
3. `l1/compiler/stage1_l0/src/locals.l0` and `l1/compiler/stage1_l0/src/backend.l0` also assume block bodies for
   `while`, `for`, and `match` arms, so parser-only relaxation would be incomplete.

## Defaults Chosen

1. `while` and `for` bodies accept any `Stmt`, matching the existing `if` then/else rule.
2. `match` arms accept any `Stmt`, matching the existing `case` arm and `else` rule.
3. Single-statement loop bodies and single-statement `match` arms still execute inside a fresh synthetic body scope so
   local bindings, pattern bindings, and cleanup stay body-local.
4. Existing block-bodied forms remain valid with no semantic change.

## Goal

1. Parse `while`, `for`, and `match` body positions as generic statements.
2. Preserve the current scope, cleanup, and control-flow behavior for both block and non-block bodies.
3. Document the relaxed grammar for `while`, `for`, and `match` statement bodies.

## Implementation Phases

### Phase 1: Parser and grammar reference

Update `l1/compiler/stage1_l0/src/parser/stmt.l0` so `while`, `for`, and `match` use `ps_parse_stmt()` for body
positions while keeping the current clause parsing and semicolon rules for simple statements. Update
`l1/docs/reference/grammar.md` so `WhileStmt`, `ForStmt`, and `MatchArm` use `Stmt`.

### Phase 2: Scope and lowering parity

Update `l1/compiler/stage1_l0/src/locals.l0` and `l1/compiler/stage1_l0/src/backend.l0` so these newly relaxed body
positions follow the same scope and cleanup contract regardless of whether the parsed body is a block or a single
statement. The intended model is the existing `case` arm / `if` branch behavior: create the expected child scope, visit
block bodies as blocks, and visit non-block bodies as single statements under that same scope.

### Phase 3: Tests and docs alignment

1. Add parser coverage for `while (...) simple_stmt;`, `for (...) simple_stmt;`,
   `match (...) { Variant => simple_stmt; _ => simple_stmt; }`, and the existing `case` single-statement precedent.
2. Add locals/backend/end-to-end coverage proving loop-body locals stay scoped to the body and pattern-bound names
   remain visible inside single-statement match arms.
3. Keep `l1/docs/reference/grammar.md` aligned with the implemented `Stmt`-body grammar after the parser change lands.

## Non-Goals

1. Changing `with` to accept non-block bodies; it remains block-only.
2. Adding new match-pattern families such as literals, nested patterns, or or-patterns.
3. Changing `for` header grammar beyond the body position.
4. Introducing new diagnostics unless implementation uncovers a missing existing error path; reuse current diagnostic
   codes where possible.

## Verification Criteria

1. `while (...) x = x + 1;`, `for (...) doSomething();`, and
   `match (col) { Red() => return 1; Green() => return 2; _ => x = 3; }` parse and lower successfully.
2. `case (name) { "Mario" => return 1; "Luigi" => return 2; else return 0; }` remains accepted.
3. Loop-body and match-arm scopes/cleanup match the current block-bodied contract.
4. `l1/docs/reference/grammar.md` and `l1/docs/roadmap.md` reflect the active plan and grammar contract.
