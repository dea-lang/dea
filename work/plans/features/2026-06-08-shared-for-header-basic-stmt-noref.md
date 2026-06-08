# Feature Plan

## Shared `for` header `BasicStmt` grammar

- Date: 2026-06-08
- Status: Draft
- Title: Restrict shared `for` headers to non-abrupt basic statements
- Kind: Feature
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
  - Shared reference docs and diagnostic catalog
- Origin: L0 Stage 1 Python parser and L0/L1 reference grammar
- Porting rule: Settle the grammar and diagnostics in L0 Stage 1 first, then port the parser rule mechanically to L0
  Stage 2 and L1 Stage 1
- Target status:
  - L0 Stage 1: Pending
  - L0 Stage 2: Pending
  - L1 Stage 1: Pending
  - Shared reference docs and diagnostic catalog: Pending
- Subsystem: Grammar / Parser / Diagnostics / Control flow
- Modules: `l0/compiler/stage1_py/l0_parser.py`, `l0/compiler/stage2_l0/src/parser/stmt.l0`,
  `l1/compiler/stage1_l0/src/parser/stmt.l0`, `l0/docs/reference/grammar.md`, `l1/docs/reference/grammar.md`,
  `docs/specs/compiler/diagnostic-code-catalog.md`
- Test modules: `l0/compiler/stage1_py/tests/parser/`,
  `l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`, `l0/compiler/stage2_l0/tests/parser_test.l0`,
  `l1/compiler/stage1_l0/tests/parser_test.l0`
- Related:
  - `l0/docs/reference/grammar.md`
  - `l1/docs/reference/grammar.md`
  - `l0/docs/decisions/0010-with-statement-cleanup.md`
  - `work/plans/bug-fixes/closed/2026-04-10-shared-loop-control-statement-parity-noref.md`

## Summary

The shared L0/L1 grammar currently uses `SimpleStmt` in `for` init and update clauses. That admits `return`, `break`,
`continue`, and `drop` in positions that are setup/update clauses rather than loop body statements.

The intended model is:

- `SimpleStmt` describes semicolon-form statements.
- `BasicStmt` describes non-abrupt statements that may appear in `for` init/update clauses.
- `with` header items remain `SimpleStmt`, because `with (... => drop x)` is the established cleanup form and cleanup
  statements intentionally run on early exits.

This plan introduces the grammar split and parser enforcement across L0 Stage 1, L0 Stage 2, and L1 Stage 1.

## Grammar Changes

Update both reference grammars to express this shape:

```ebnf
Stmt         ::= Block | IfStmt | MatchStmt | CaseStmt | WhileStmt | ForStmt | WithStmt | SimpleStmt ";"

SimpleStmt   ::= BasicStmt | DropStmt | ReturnStmt | BreakStmt | ContinueStmt

BasicStmt    ::= LetStmt | AssignStmt | Expr

ForStmt      ::= "for" "(" ( BasicStmt )? ";" ( Expr )? ";" ( BasicStmt )? ")" ...

WithItem     ::= SimpleStmt "=>" SimpleStmt
               | SimpleStmt

DropStmt     ::= "drop" Ident

BreakStmt    ::= "break"
ContinueStmt ::= "continue"
```

Add grammar notes:

- `for` init/update clauses are not loop bodies and cannot contain `return`, `break`, `continue`, or `drop`.
- `break` and `continue` are only valid in loop bodies.
- A `with` header item or inline cleanup may contain `break` or `continue` only when the containing `with` statement is
  itself inside a loop body.

## Diagnostics

Use the unused nearby parser code `PAR-0145` for forbidden `for` init/update statements:

- Code: `PAR-0145`
- Level: All
- Meaning: `for` loop init/update must be a basic statement

This code choice is provisional. Re-check `docs/specs/compiler/diagnostic-code-catalog.md` at implementation time before
registering it; if `PAR-0145` has been consumed, choose the next suitable unused parser code in the existing `for`
statement range.

## Implementation Approach

1. Add a basic-statement parser helper in L0 Stage 1 Python.
2. Change only `for` init/update parsing to call the basic-statement helper.
3. Leave ordinary statement parsing and `with` item parsing on `SimpleStmt`.
4. Register `PAR-0145` in the shared diagnostic catalog and L0 diagnostic registry.
5. Port the same parser rule into L0 Stage 2 and L1 Stage 1.
6. Keep the existing semantic loop-depth validation for `break` and `continue`; it continues to reject
   `with (... => break)` or `with (... => continue)` outside loops and accept them inside loop bodies.

No AST split is required. `ForStmt.init` and `ForStmt.update` can continue to store statement ids/nodes whose concrete
runtime variants are limited by the parser.

## Verification

Parser-negative coverage:

- `return`, `break`, `continue`, and `drop` are rejected in `for` init position.
- `return`, `break`, `continue`, and `drop` are rejected in `for` update position.
- Rejections use `PAR-0145`.

Parser-positive coverage:

- `let`, assignment, expression, and empty clauses still parse in `for` init/update positions.
- Ordinary `return`, `break`, `continue`, and `drop` statements still parse as `SimpleStmt`.
- `with (... => drop x)` still parses and checks.
- `with (... => break)` and `with (... => continue)` are accepted when the containing `with` statement is inside a loop
  body.

Semantic-negative coverage:

- `with (... => break)` and `with (... => continue)` outside loops still report the existing not-within-loop
  diagnostics.

Suggested focused checks:

```bash
make -C l0 test-stage1
make -C l0 test-stage2 TESTS="parser_test"
make -C l1 test-stage1 TESTS="parser_test"
```

## Non-Goals

1. Restricting `with` header or inline cleanup items away from `SimpleStmt`.
2. Removing existing `return` behavior in `with` cleanup statements.
3. Introducing an `AbruptStmt` grammar nonterminal.
4. Changing backend lowering or AST shape.
