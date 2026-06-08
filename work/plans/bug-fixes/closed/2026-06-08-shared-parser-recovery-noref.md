# Bug Fix Plan

## Shared parser error recovery

- Date: 2026-06-08
- Status: Closed
- Title: Fix parser expression parsing and error recovery for loop/block structures
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L1 Stage 1 parser, parity ported back to L0 Stage 1 and L0 Stage 2
- Porting rule: Fix parser in all three compiler frontends equivalently
- Target status:
  - L0 Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Parser
- Modules:
  - `l0/compiler/stage1_py/l0_parser.py`
  - `l0/compiler/stage2_l0/src/parser/stmt.l0`
  - `l0/compiler/stage2_l0/src/parser/shared.l0`
  - `l1/compiler/stage1_l0/src/parser/stmt.l0`
  - `l1/compiler/stage1_l0/src/parser/shared.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/parser/`
  - `l0/compiler/stage2_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
- Repro: `for ( ; ; return )` and statement blocks missing semicolons

## Summary

The parser was throwing confusing errors (`PAR-0225: unexpected token in expression`) for `return` statements
immediately followed by `)` or `}`. Additionally, when an error occurred, the parser's synchronization logic
(`_sync_stmt` / `ps_sync_stmt`) failed to recognize `{` as a statement boundary, causing it to consume an opening brace
and leave the corresponding closing brace unmatched. This eventually ejected the parser back to the top level
mid-function, generating `PAR-0020: unexpected token in top level` for valid inner block statements.

This bug-fix plan addresses both bugs across the shared L0 and L1 parser stages.

## Root Cause

1. `parse_return_stmt` solely relied on checking for a semicolon to determine whether an expression should be parsed. If
   no semicolon was found, it blindly attempted expression parsing, leading to `unexpected token in expression` when
   encountering a closing parenthesis or brace.
2. `sync_stmt` lacked `TT_LBRACE` as a recognized statement boundary. Skipping the opening brace caused the block
   structure to become unbalanced, meaning a later `}` inside the same function would prematurely terminate the
   enclosing function block.

## Scope of This Fix

1. Prevent `parse_return_stmt` from attempting expression parsing if the next token is `)` or `}`.
2. Allow `sync_stmt` to stop and recover at `{`.

## Approach

### L0 Stage 1 (Python)

- In `_parse_return_stmt`, return early if `self._check(TokenKind.RPAREN)` or `self._check(TokenKind.RBRACE)`.
- In `_sync_stmt`, add `TokenKind.LBRACE` to the tuple of statement-starting keywords.

### L0 Stage 2 / L1 Stage 1

- In `ps_parse_return_stmt`, return early if `ps_check(self, ord(TT_RPAREN))` or `ps_check(self, ord(TT_RBRACE))`.
- In `ps_at_stmt_start`, return `true` if `ps_check(self, ord(TT_LBRACE))`.
