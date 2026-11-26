# Bug Fix Plan

## Decode Unicode string escapes

- Date: 2026-11-26
- Status: Draft
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
- Related:
  - [l0/docs/reference/grammar.md](../../../../l0/docs/reference/grammar.md)
  - [l0/docs/decisions/0009-string-value-semantics.md](../../../../l0/docs/decisions/0009-string-value-semantics.md)
  - [docs/specs/compiler/diagnostic-code-catalog.md](../../../../docs/specs/compiler/diagnostic-code-catalog.md)
- Repro: Compare `len_s("\u00E9")` across both stages and pass a raw U+00E9 literal to a function with an escaped U+00E9
  case arm.

## Summary

Stage 1 raises a Python encoding exception on surrogate escapes in a case arm. Stage 2 accepts both surrogate forms and
stores their source spelling. It also miscompiles valid escapes: `len_s("\u00E9")` returned 6 instead of 2. A case arm
written with that escape did not match a raw U+00E9 source literal. The identical Stage 1 program matched.

## Fixes and regression tests

1. **Reject invalid scalars.** Stage 2 currently accepts `\uD800` and `\U0000DFFF` as six and ten bytes of escape text.
   Validate scalars before UTF-8 encoding in both stages. At the lexer boundary, assert the registered `LEX-0054` for a
   surrogate or a value above U+10FFFF with its source location. Run ordinary string and case-arm fixtures through both
   CLIs and require a structured diagnostic and a failed check. Preserve Stage 1's `EscapeDecodeError` and `TYP-0109`
   mapping when testing its case-literal decoder directly. A lexer rejection should end that source path before a second
   diagnostic or a host encoding exception.

2. **Decode valid scalars once in Stage 2.** In `ls_read_string_literal`, retain the original escape spelling for token
   display and append the scalar's UTF-8 bytes to the token value. The parser, case keys and C emitter already consume
   decoded values. Keep byte-literal restrictions and ordinary backslash escapes intact.

   - In `lexer_test`, assert spelling and payload separately for `\u00E9` (bytes `C3 A9`) and `\U0001F600` (bytes
     `F0 9F 98 80`). Accept U+D7FF and U+E000 on either side of the surrogate range. A literal with a doubled backslash,
     `"\\u00E9"`, must still contain six bytes.
   - Compile and run the same UTF-8 fixture with each launcher. Require `len_s("\u00E9") == 2` and equality to the raw
     U+00E9 literal. Call a function whose escaped case arm returns 7 and whose fallthrough returns 9. Passing the raw
     literal must yield 7. Stage 1 returned 7 and Stage 2 returned 9 in the review. Put the escaped and raw forms in
     separate arms of a second fixture and require the duplicate-value diagnostic (`TYP-0108`). Check the four-byte
     scalar's length as a separate long-form control.

## Verification

From `l0/`, run the listed Stage 1 pytest modules with `../.venv/bin/python -m pytest -q`, then run
`make test-stage2 TESTS="lexer_test l0c_build_run_test"`. Compare token spelling, decoded values, executable results and
invalid-scalar diagnostics using `./scripts/l0c` and `./build/dea/bin/l0c-stage2`. Recheck the existing diagnostic
meanings against the live catalog.

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
