# Bug Fix Plan

## Decode Unicode string escapes

- Date: 2026-11-27
- Status: Completed
- Title: Decode Unicode string escapes
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: String token decoding and case-literal checking
- Modules:
  - `l0/compiler/stage1_py/l0_lexer.py`
  - `l0/compiler/stage1_py/l0_string_escape.py`
  - `l0/compiler/stage1_py/l0_check_patterns.py`
  - `l0/compiler/stage2_l0/src/lexer.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/lexer/test_string_escape.py`
  - `l0/compiler/stage1_py/tests/integration/test_case_statement.py`
  - `l0/compiler/stage2_l0/tests/lexer_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l0/tests/fixtures/unicode_string_escapes/`
- Related:
  - [l0/docs/reference/grammar.md](../../../../../l0/docs/reference/grammar.md)
  - [l0/docs/decisions/0009-string-value-semantics.md](../../../../../l0/docs/decisions/0009-string-value-semantics.md)
  - [docs/specs/compiler/diagnostic-code-catalog.md](../../../../../docs/specs/compiler/diagnostic-code-catalog.md)
- Repro: Compare `len_s("\u00E9")` across both stages and pass a raw U+00E9 literal to a function with an escaped U+00E9
  case arm.

## Findings and fix

Stage 1 accepted surrogate escapes until UTF-8 encoding raised a Python exception, including in a string `case` arm.
Both lexers now report `LEX-0054` for U+D800 through U+DFFF and values above U+10FFFF. The lexical error ends source
checking for that literal. Stage 1's standalone decoder raises `EscapeDecodeError`, which the case checker maps to the
existing `TYP-0109` when invoked directly.

Stage 2 previously stored the six source bytes of `\u00E9` as the string value. The lexer now keeps the spelling for
token display and writes each Unicode scalar's UTF-8 bytes to the value buffer. Existing string equality, case checking
and C emission consume those bytes. Escaping the backslash still yields a literal backslash, and Unicode escapes in byte
literals still require a one-byte UTF-8 encoding.

## Verification

Focused tests passed on macOS with TinyCC. From `l0/`:

- `../.venv/bin/python -m pytest -q compiler/stage1_py/tests/lexer compiler/stage1_py/tests/integration/test_case_statement.py compiler/stage1_py/tests/integration/test_byte_type.py compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`
  passed all 436 Stage 1 tests.
- `make test-stage2 TESTS="lexer_test parser_test diagnostic_code_parity_test diagnostic_message_parity_test l0c_build_run_test"`
  passed all five Stage 2 suites. Lexer tests check token spelling and bytes independently, including U+D7FF, U+E000,
  U+10FFFF and a doubled backslash.
- `../.venv/bin/python compiler/stage2_l0/scripts/run_trace_tests.py lexer_test` passed with zero leaked objects or
  strings.
- Both launchers executed `decoded.l0` with exit 0. Escaped U+00E9 and U+1F600 equal their raw spellings and have
  lengths 2 and 4. The escaped case arm returns 7 for raw U+00E9 and falls through to 9 for a different string. Both
  launchers rejected `duplicate.l0` with one `TYP-0108` and `invalid.l0` with three source-located `LEX-0054` errors.
  Token display preserved both Unicode escape spellings.

## ADR Impact

- Decision: Case-literal decoding failures enter the compiler diagnostic collection.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0013-compiler-diagnostic-collection-parser-recovery-and-phase-barriers.md`
  - Rationale: The shared diagnostic model and the existing case-literal diagnostic cover this decoder failure.
- Decision: Raw UTF-8 literal text and a Unicode escape for the same scalar denote the same L0 string value.
  - Scope: L0
  - Disposition: Covered by ADR
  - ADR: `l0/docs/decisions/0009-string-value-semantics.md`
  - Rationale: String equality and case matching depend on the decoded bytes. The repair restores the value already
    produced by Stage 1 for valid escapes.
