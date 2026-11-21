# Bug Fix Plan

## Honor module qualifiers and decode Unicode string escapes

- Date: 2026-11-21
- Status: Draft
- Title: Honor module qualifiers and decode Unicode string escapes
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: Name resolution, intrinsic dispatch, string token decoding, and case-literal checking
- Modules:
  - `l0/compiler/stage1_py/l0_resolve.py`
  - `l0/compiler/stage1_py/l0_check_expr.py`
  - `l0/compiler/stage1_py/l0_check_patterns.py`
  - `l0/compiler/stage1_py/l0_string_escape.py`
  - `l0/compiler/stage1_py/l0_lexer.py`
  - `l0/compiler/stage1_py/l0_analysis.py`
  - `l0/compiler/stage1_py/l0_backend_lowering.py`
  - `l0/compiler/stage2_l0/src/lexer.l0`
  - `l0/compiler/stage2_l0/src/type_resolve.l0`
  - `l0/compiler/stage2_l0/src/expr_types/expr.l0`
  - `l0/compiler/stage2_l0/src/expr_types/patterns.l0`
  - `l0/compiler/stage2_l0/src/backend/initializers.l0`
  - `l0/compiler/stage2_l0/src/backend/lowering.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/name_resolver/test_qualified_names.py`
  - `l0/compiler/stage1_py/tests/integration/test_ord_intrinsic.py`
  - `l0/compiler/stage1_py/tests/type_checker/test_sizeof_type_alias.py`
  - `l0/compiler/stage1_py/tests/lexer/test_string_escape.py`
  - `l0/compiler/stage1_py/tests/integration/test_case_statement.py`
  - `l0/compiler/stage2_l0/tests/lexer_test.l0`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
- Related:
  - [l0/docs/decisions/0012-name-disambiguation.md](../../../../l0/docs/decisions/0012-name-disambiguation.md)
  - [docs/specs/compiler/diagnostic-code-catalog.md](../../../../docs/specs/compiler/diagnostic-code-catalog.md)
  - [l0/docs/reference/grammar.md](../../../../l0/docs/reference/grammar.md)
- Repro: Import a module defining `sizeof(x: int) -> int` with body `return 37;`. Call `dep::sizeof(1)` and observe the
  generated C intrinsic and the wrong return value.

## Summary

Both stages dispatch qualified intrinsic names by spelling. Native Stage 2 returned 4 from `dep::sizeof(1)` and 1 from
`dep::ord(dep::B)` although both functions were defined to return 37. Stage 1 also accepts an imported enum variant
under the wrong owner. Stage 2 already diagnoses that pattern.

Stage 1 raises a Python encoding exception on surrogate escapes in a case arm. Stage 2 accepts both surrogate forms and
stores their source spelling. It also miscompiles valid escapes: `len_s("\u00E9")` returned 6 instead of 2. A case arm
written with that escape did not match a raw U+00E9 source literal. The identical Stage 1 program matched.

## Fixes and regression tests

1. **Current-module qualification.** Preserve an explicit qualifier when selecting the symbol table in `resolve_symbol`.
   Qualified lookup uses declarations owned by the named module. Unqualified lookup retains open imports, local
   shadowing, and ambiguity handling. Define `Red` only in `remote`, import it in `main`, and match a `remote::Color`
   using `main::Red`. Assert `TYP-0102` and that the rejected arm contributes no coverage. Exercise valid `remote::Red`,
   a genuine local `main::Red`, and an unqualified imported variant as controls. Retain the Stage 2 results as controls:
   the wrong owner gives `TYP-0102` and leaves the match non-exhaustive, and `remote::Red` checks.

2. **Qualified intrinsic spellings.** Resolve qualified calls to `sizeof` and `ord` as ordinary qualified names. Have
   lowering consume the intrinsic identity established by analysis so it cannot reinterpret a resolved function by its
   spelling. Declare `dep::sizeof` and `dep::ord` to return 37. Compile and execute `dep::sizeof(1)` and
   `dep::ord(dep::B)` with `B` the second enum variant. Both results must be 37, independent of host C sizes. Require
   the existing callee-lookup diagnostic (`TYP-0189`) for `missing_module::sizeof(1)` and `missing_module::ord(B)`.
   These operands are valid for the bare intrinsics. Keep bare `sizeof` on a type alias and bare enum `ord` as controls.
   Cover an existing but unimported module as well. Exercise both stages' check and run paths. Audit the Stage 2
   initializer emitter for the same name-only dispatch.

3. **Reject invalid scalars.** Stage 2 currently accepts `\uD800` and `\U0000DFFF` as six and ten bytes of escape text.
   Validate scalars before UTF-8 encoding in both stages. At the lexer boundary, assert the registered `LEX-0054` for a
   surrogate or a value above U+10FFFF with its source location. Run ordinary string and case-arm fixtures through both
   CLIs and require a structured diagnostic and a failed check. Preserve Stage 1's `EscapeDecodeError` and `TYP-0109`
   mapping when testing its case-literal decoder directly. A lexer rejection should end that source path before a second
   diagnostic or a host encoding exception.

4. **Decode valid scalars once in Stage 2.** In `ls_read_string_literal`, retain the original escape spelling for token
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

Run the listed pytest modules from `l0/` with `../.venv/bin/python -m pytest -q` and their level-relative paths. Run
`make test-stage2 TESTS="lexer_test expr_types_test l0c_build_run_test"` there. Compare the executable results from
`./scripts/l0c --run` and `./build/dea/bin/l0c-stage2 --run` on the same fixtures. Recheck the registered diagnostic
meanings against the live catalog and cover both lexical recovery and semantic dispatch.

## ADR Impact

- Decision: An explicit module qualifier identifies the owner of a declaration, including a callable whose name also
  spells an intrinsic.
  - Scope: L0
  - Disposition: Covered by ADR
  - ADR: `l0/docs/decisions/0012-name-disambiguation.md`
  - Rationale: Both lookup fixes enforce the accepted meaning of a qualified reference.
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
