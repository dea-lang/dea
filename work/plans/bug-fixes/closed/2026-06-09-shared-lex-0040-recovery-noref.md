# Bug Fix Plan

## Recover lexing on LEX-0040

- Date: 2026-06-09
- Status: Completed
- Title: Change LEX-0040 message, recover invalid characters, and stop before parser on lexer errors
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
  - Shared diagnostic catalog
- Origin: L0 Stage 1 Python
- Porting rule: Settle the diagnostic message change, lexer recovery loop, and post-lexing phase gate in L0 Stage 1
  first, then port mechanically to L0 Stage 2 and L1 Stage 1.
- Target status:
  - L0 Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
  - Shared diagnostic catalog: Implemented
- Subsystem: Lexer / Diagnostics
- Modules:
  - `l0/compiler/stage1_py/l0_lexer.py`
  - `l0/compiler/stage1_py/l0_driver.py`
  - `l0/compiler/stage2_l0/src/lexer.l0`
  - `l0/compiler/stage2_l0/src/driver.l0`
  - `l0/compiler/stage2_l0/src/parser/decl.l0`
  - `l1/compiler/stage1_l0/src/lexer.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/parser/decl.l0`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Test modules:
  - `l0/compiler/stage1_py/tests/lexer/test_lexer_errors.py`
  - `l0/compiler/stage1_py/tests/lexer/test_lexer_tokens.py`
  - `l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`
  - `l0/compiler/stage2_l0/tests/lexer_test.l0`
  - `l0/compiler/stage2_l0/tests/parser_test.l0`
  - `l0/compiler/stage2_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/lexer_test.l0`
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`

## Summary

Before this fix, when the lexer encountered an unexpected character, it emitted a `LEX-0040` error containing the raw
byte (e.g. `unexpected character ''`). For non-ASCII UTF-8 bytes, this printed unreadable garbled output since only the
initial byte was captured. Furthermore, encountering `LEX-0040` aborted tokenization immediately in the native frontends
by returning a `null` token, preventing the lexer from reporting later invalid characters in the same file.

The first recovery pass changed the lexer to continue tokenizing after invalid characters. That surfaced a second phase
handoff issue: recovered lexing could return an EOF-terminated token stream while holding lexer errors, and the driver
or `parse_module_source` helper would then enter the parser and add misleading parser diagnostics such as `PAR-0310`
from the recovered token stream.

This fix:

1. Change the `LEX-0040` diagnostic message to simply read "invalid character in source", avoiding printing the raw
   byte.
2. Introduce a recovery mechanism in all lexer implementations. Instead of returning `null` or recursing, the
   `ls_next_token()` / `_next_token()` method will loop internally, consume the invalid character, emit the error, and
   continue to scan for the next valid token.
3. Add a phase gate after tokenization: if lexer diagnostics include any errors, return those lexer diagnostics and do
   not enter the parser.

## Implementation Approach

1. Update `docs/specs/compiler/diagnostic-code-catalog.md` to change `LEX-0040` from
   `Unexpected character in source text` to `invalid character in source`.
2. In `l0_lexer.py`, update `_next_token()`:
   - Change the `LEX-0040` message emission to use the generic message (dropping the `c!r` formatting).
   - Wrap the main body of `_next_token()` in a `while True:` loop so that it can `continue` on invalid characters
     rather than relying on tail recursion.
3. In `l0/compiler/stage2_l0/src/lexer.l0` and `l1/compiler/stage1_l0/src/lexer.l0`, update `ls_next_token()`:
   - Wrap the main reading logic inside `while (true) { ... }`.
   - Update the `_ =>` switch case to emit `invalid character in source` and then `continue` instead of returning
     `null`.
4. In `l0_driver.py`, `l0/compiler/stage2_l0/src/driver.l0`, and `l1/compiler/stage1_l0/src/driver.l0`, stop between
   lexing and parsing when the lexer emitted any error diagnostics.
5. In the native `parser/decl.l0` source helpers, apply the same gate for `parse_module_source()` callers and free the
   recovered token vector before returning lexer diagnostics.
6. Update the L0 Python test suite (e.g. `test_diagnostic_codes.py`, `test_lexer_tokens.py`) to assert the new generic
   message for `LEX-0040`.
7. Ensure a file with multiple invalid characters correctly reports multiple `LEX-0040` errors without crashing and
   without entering parser recovery.

## Verification Criteria

- Non-ASCII files with invalid identifiers correctly emit `[LEX-0040] invalid character in source` without garbled raw
  bytes in the terminal.
- A file with multiple invalid characters reports every `LEX-0040` error found during tokenization.
- A file with lexer errors does not produce parser diagnostics from the recovered token stream.
- Python recursion limits are not reached on files containing hundreds of sequential invalid characters.
- Tests pass across all lexer stages.

## Outcome

Implemented across L0 Stage 1, L0 Stage 2, L1 Stage 1, and the shared diagnostic catalog. Lexer recovery now continues
inside the lexer so multiple invalid characters are reported in one pass, and the driver/parser handoff stops before the
parser phase if any lexer error was emitted.
