# Feature Plan

## Shared `for` header `BasicStmt` grammar

- Date: 2026-06-08
- Status: Closed (rejected; superseded)
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
- Closed reason: Rejected as a grammar restriction. Superseded by the shared `for`-header flow-safety bug-fix plan,
  which kept simple statements in headers and fixed their analysis/lowering semantics instead of banning abrupt
  statements.
- Porting rule: Do not implement this proposal. Follow the superseding shared `for`-header flow-safety bug-fix plan.
- Target status:
  - L0 Stage 1: Superseded
  - L0 Stage 2: Superseded
  - L1 Stage 1: Superseded
  - Shared reference docs and diagnostic catalog: Superseded
- Subsystem: Grammar / Parser / Diagnostics / Control flow
- Superseded by: `work/plans/bug-fixes/closed/2026-06-22-shared-for-header-and-statement-flow-safety-noref.md`
- Related:
  - `l0/docs/reference/grammar.md`
  - `l1/docs/reference/grammar.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`

## Summary

This feature plan proposed splitting `for` header parsing so initialization/update clauses would accept only non-abrupt
basic statements. The final shared semantics keep `return`, `break`, `continue`, and `drop` valid in `for` headers, with
header `break` and `continue` targeting the surrounding loop context.

The completed bug-fix plan supersedes this proposal by:

- keeping `for` initialization on `SimpleStmt`,
- keeping update clauses on non-declaration simple statements,
- retaining `PAR-0145` specifically for update-clause `let`,
- fixing analyzer and backend semantics for header control flow and cleanup.

## Historical Proposal

The rejected grammar direction was:

```ebnf
Stmt         ::= Block | IfStmt | MatchStmt | CaseStmt | WhileStmt | ForStmt | WithStmt | SimpleStmt ";"

SimpleStmt   ::= LetStmt | BasicStmt | DropStmt | ReturnStmt | BreakStmt | ContinueStmt

ForInitStmt  ::= LetStmt | BasicStmt

BasicStmt    ::= AssignStmt | Expr

ForStmt      ::= "for" "(" ( ForInitStmt )? ";" ( Expr )? ";" ( BasicStmt )? ")" ...
```

That shape is intentionally not the current grammar. The current grammar and diagnostics are recorded in the L0/L1
grammar references and the shared diagnostic-code catalog.

## Verification

The completed fix includes parser, analyzer, backend, and trace coverage for:

- `let` remaining rejected only in update clauses with `PAR-0145`,
- non-declaration header statements remaining accepted,
- header `break` and `continue` targeting enclosing loops,
- loop/header liveness and cleanup behavior across L0 Stage 1, L0 Stage 2, and L1 Stage 1.
