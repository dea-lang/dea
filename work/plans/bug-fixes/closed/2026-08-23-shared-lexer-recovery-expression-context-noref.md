# Bug Fix Plan

## Preserve expression context after recovered lexer tokens

- Date: 2026-08-24
- Status: Completed
- Title: Update signed-literal context from the parser-visible recovery token in all frontends
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Python Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: The logical recovery-token contract in ADR-0009 defines the predecessor token seen by context-sensitive
  lexing.
- Porting rule: Implement the same logical-predecessor rule in all three lexers while allowing their physical wrapper
  layouts to remain intentionally different.
- Target status:
  - L0 Python Stage 1: Pending
  - L0 Stage 2: Pending
  - L1 Stage 1: Pending
- Subsystem: Lexer recovery / Signed numeric literals / Parser-visible token context
- Modules:
  - `l0/compiler/stage1_py/l0_lexer.py`
  - `l0/compiler/stage2_l0/src/lexer.l0`
  - `l0/compiler/stage2_l0/src/tokens.l0`
  - `l1/compiler/stage1_l0/src/lexer.l0`
  - `l1/compiler/stage1_l0/src/tokens.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/lexer/test_lexer.py`
  - `l0/compiler/stage1_py/tests/lexer/test_lexer_errors.py`
  - `l0/compiler/stage1_py/tests/lexer/test_lexer_tokens.py`
  - `l0/compiler/stage2_l0/tests/lexer_test.l0`
  - `l0/compiler/stage2_l0/tests/lexer_error_cleanup_test.l0`
  - `l1/compiler/stage1_l0/tests/lexer_test.l0`
  - `l1/compiler/stage1_l0/tests/lexer_error_cleanup_test.l0`
- Related:
  - `docs/decisions/0009-logical-lexer-error-recovery-tokens-and-codepoint-columns.md`
  - `work/plans/refactors/closed/2026-06-10-shared-lexer-error-recovery-tokens-and-codepoint-columns-noref.md`
  - `work/plans/bug-fixes/closed/2026-06-09-shared-lex-0040-recovery-noref.md`
- Repro: Tokenize `2147483648 -5`; all three frontends currently treat the second source token as signed `-5` after the
  recoverable overflow wrapper instead of exposing binary minus followed by positive `5`.

## Summary

The lexers use the previous token kind to decide whether `-` begins a signed integer literal or is a binary operator.
After a recoverable numeric error, tokenization records the physical lexer-error wrapper as that predecessor. The
wrapper is not an expression-ending token even when its recovery payload is an integer, so the following `-5` is
incorrectly folded into one negative literal.

The behavior violates ADR-0009: parser decisions are defined over logical recovery tokens, not their physical wrapper
representation. The same defect is reproduced in L0 Python Stage 1 and is source-identical in the two native lexers.

## ADR Impact

- Decision: Use the parser-visible recovery token as the predecessor for context-sensitive lexing decisions.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0009-logical-lexer-error-recovery-tokens-and-codepoint-columns.md`
  - Rationale: ADR-0009 already establishes that parser lookahead and recovery decisions operate on the logical token;
    this plan corrects one lexer state update that still uses the physical wrapper.

## Current State and Root Cause

1. Each lexer appends the physical token returned by its scanning routine and then stores that physical token kind in
   `prev_kind` or `_prev_kind`.
2. Recoverable numeric overflow returns a lexer-error wrapper whose payload contains a parser-visible integer token.
3. The wrapper kind is not included among expression-ending token kinds.
4. The next `-` is consequently classified as a unary sign even though the recovered integer logically ended an
   expression.

## Scope of This Fix

1. Centralize selection of the logical predecessor kind after every scanned token.
2. Use a wrapper's recovery token when present and retain the prior logical context for wrappers that have no recovery
   token, according to ADR-0009.
3. Cover overflow, malformed numeric suffixes, malformed string/byte literals with recovery, consecutive wrappers, and
   no-recovery wrappers.
4. Verify both token dumps and parser-visible behavior without changing their intentionally different representations.
5. Preserve exactly-once deferred diagnostic emission.

## Diagnostics

No diagnostic code is added or reassigned. Existing `LEX-*` diagnostics and recovery payloads remain unchanged.

## Non-Goals

1. Redesigning lexer-error wrapper layouts.
2. Changing which numeric forms permit a leading sign.
3. Moving signed-literal disambiguation from the lexer into the parser as part of this fix.

## Verification

1. Assert the logical sequence for `2147483648 -5` is recovery integer, minus, positive integer, EOF in all frontends.
2. Add adjacent controls where minus must remain unary, including after delimiters and operators.
3. Verify each deferred lexer diagnostic is emitted exactly once through parser backtracking.
4. Run the focused lexer/parser suites for all targets, then `make test` from the repository root.

## Verification Criteria

1. Physical wrappers no longer corrupt signed-literal context.
2. Parser-visible tokens and diagnostic spans remain consistent with ADR-0009.
3. L0 Stage 1, L0 Stage 2, and L1 Stage 1 agree on every focused recovery sequence.

## Implementation Outcome

1. All three lexers now store the payload-free expression-ending state of the parser-visible predecessor rather than the
   physical token kind.
2. Recovery wrappers derive that state from their literal recovery payload, while no-recovery wrappers preserve the
   preceding logical state across one or more skipped wrappers.
3. Signed-minus classification therefore treats recovered literals as operands without copying or retaining native
   recovery payloads.
4. Regression coverage includes overflow or malformed numeric recovery, malformed string and byte literals, consecutive
   wrappers, no-recovery wrappers after operands and operators, and parser-visible binary-minus behavior.

## Verification Outcome

1. The focused Python lexer/error suites passed (46 tests). L0 Stage 2 and L1 Stage 1 lexer, lexer cleanup, and parser
   suites passed in normal and ARC/memory trace modes.
2. Repository-root `make test` passed: 1,470 L0 Python tests, all 55 L0 Stage 2 tests including triple bootstrap, all
   workflows and examples, and all 67 L1 Stage 1 tests and examples completed successfully.
3. The independent read-only review found that the initial regressions stopped at physical token streams. The accepted
   finding was fixed with full-module parser tests that assert one deferred lexer diagnostic, a preserved module AST,
   and no parser cascade in every frontend; follow-up review reported no remaining issue.
