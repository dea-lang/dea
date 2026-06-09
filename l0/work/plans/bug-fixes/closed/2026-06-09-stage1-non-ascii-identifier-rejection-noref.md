# Bug Fix Plan

## Reject non-ASCII identifiers in L0 Stage 1

- Date: 2026-06-09
- Status: Closed (fixed)
- Title: Reject non-ASCII identifier characters in the L0 Stage 1 Python lexer
- Kind: Bug Fix
- Severity: Medium
- Stage: 1
- Subsystem: Lexer / Parser / Diagnostics
- Modules:
  - `compiler/stage1_py/l0_lexer.py`
- Test modules:
  - `compiler/stage1_py/tests/lexer/test_lexer_errors.py`
- Related:
  - `docs/decisions/0008-source-text-encoding-and-ascii-language-vocabulary.md`
  - `docs/specs/language/source-text-and-language-vocabulary.md`
  - `l0/docs/reference/grammar.md`
  - `l0/docs/specs/compiler/stage1-contract.md`
  - `work/plans/bug-fixes/closed/2026-06-09-shared-lex-0040-recovery-noref.md`
- Repro:
  ```l0
  module main;
  func main() -> int {
      let café: int = 1;
      return café;
  }
  ```
  `./scripts/l0c --check -P <dir> main`

## Summary

L0 Stage 1 currently accepts non-ASCII letters inside identifiers because the Python lexer uses Unicode-aware
`str.isalpha()` and `str.isalnum()` when scanning identifier tokens. That behavior contradicts the documented grammar,
the new shared source-text ADR/spec, and the current L0 Stage 2 and L1 Stage 1 lexer behavior.

This plan tightens only L0 Stage 1 so the Python reference implementation enforces ASCII-only identifiers while
preserving UTF-8 source decoding and Unicode text inside comments and string literals.

## Current State

- `compiler/stage1_py/l0_driver.py` already treats source files as UTF-8 input and strips an optional BOM.
- `compiler/stage1_py/l0_lexer.py` accepts Unicode alphabetic characters in identifiers because it relies on Python's
  locale-independent Unicode character classes rather than explicit ASCII ranges.
- L0 and L1 grammar docs already define identifiers with explicit ASCII ranges.
- L0 Stage 2 and L1 Stage 1 already classify identifier bytes with ASCII helper functions.

## Root Cause

The Python lexer treats "identifier character" as a host-language Unicode concept instead of a Dea language rule. That
made the Stage 1 implementation broader than both the written grammar and the seeded native frontends.

## Scope of This Fix

- Replace Unicode-aware identifier classification in `l0_lexer.py` with explicit ASCII-only start/continue checks.
- Confirm that non-ASCII characters appearing where the grammar expects identifiers or other ASCII-only vocabulary are
  rejected through the existing lexer error path.
- Add focused tests for non-ASCII identifier rejection while preserving acceptance of Unicode text in comments and
  string literals.

## Diagnostic-Code Plan

No new diagnostic codes are expected.

- Reuse `DRV-0040` for invalid UTF-8 source decoding.
- Reuse `LEX-0040` for non-ASCII characters that appear where the lexer expects ASCII-only language vocabulary.

If implementation uncovers a distinct user-facing failure mode that cannot reuse an existing code cleanly, re-check
`docs/specs/compiler/diagnostic-code-catalog.md` at implementation time before assigning any new code.

## Approach

1. Add explicit ASCII helper predicates for identifier start and identifier continuation in `l0_lexer.py`.
2. Replace `c.isalpha()` / `self._peek().isalnum()` usage in identifier scanning with those helpers.
3. Add Stage 1 lexer coverage for:
   - a non-ASCII leading identifier character such as `café`
   - a non-ASCII character appearing after an ASCII identifier prefix
   - a non-ASCII module path component
4. Add Stage 1 positive coverage showing that UTF-8 comments and string literals remain accepted.
5. Confirm that the lexer still reports existing diagnostics and does not introduce parser follow-on noise for these
   inputs.

## Non-Goals

1. Changing L0 Stage 2 or L1 Stage 1 behavior, which already appears aligned with the ASCII identifier rule.
2. Allowing Unicode identifiers, module names, keywords, or builtin type names.
3. Changing the UTF-8 source-decoding contract.
4. Reworking string-literal or comment Unicode support beyond regression coverage.

## Verification Criteria

- `let café: int = 1;` is rejected by L0 Stage 1 with existing lexer diagnostics.
- `module café;` is rejected by L0 Stage 1 with existing lexer diagnostics.
- A source file containing Unicode text only in comments and string literals still lexes and parses successfully.
- Invalid UTF-8 input continues to fail through `DRV-0040` rather than shifting into lexer classification logic.

## Outcome

Implemented as described.

- `l0_lexer.py` now uses explicit ASCII helper predicates for identifier start and continuation.
- Unicode-aware `isalpha()` / `isalnum()` identifier classification is no longer used by L0 Stage 1.
- New regression coverage verifies non-ASCII identifier rejection and continued acceptance of Unicode comments and
  string literals.
- Validation run:
  `../.venv/bin/python -m pytest compiler/stage1_py/tests/lexer/test_lexer_errors.py compiler/stage1_py/tests/lexer/test_lexer_tokens.py compiler/stage1_py/tests/lexer/test_lexer.py`
  (35 passed).
