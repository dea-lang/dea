# Bug Fix Plan

## Preserve inline and empty struct documentation

- Date: 2026-10-25
- Status: Completed
- Title: Preserve L0 struct signatures and source locations in generated references
- Kind: Bug Fix
- Severity: Medium
- Stage: Shared
- Subsystem: Documentation source filtering
- Modules:
  - `l0/compiler/docgen/l0_docgen_l0_filter.py`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_docgen_l0_filter.py`
- Related:
  - [work/plans/bug-fixes/closed/2026-10-25-shared-autodocs-enum-filtering-noref.md](../../../../../work/plans/bug-fixes/closed/2026-10-25-shared-autodocs-enum-filtering-noref.md)
- Repro: Generate either L0 stage reference and inspect the `std.unit::unit` XML definition and location.

## Summary

The source adapter leaves inline and empty struct declarations without the C-style terminator required by Doxygen.
Doxygen merges `struct Unit {}` with the following `unit()` declaration, producing return type `struct Unit` and
declaration line 1 instead of `Unit` and line 30. Source recovery hides the incorrect type in rendered Markdown, but the
XML remains wrong.

## ADR Impact

- Decision: Translate every supported L0 struct layout without changing source line positions.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs the existing Doxygen source adapter without changing language syntax, public APIs, or the
    documentation architecture.

## Scope and approach

- Locate top-level struct declarations through the existing token-aware brace scanner, ignoring comments and literals.
- Translate fields and append closing semicolons for inline, empty, multiline, and split-header declarations.
- Preserve comments, nullable and pointer types, and source line positions.
- Restrict function translation to actual top-level keywords so function-shaped comment text remains untouched.
- Keep nullable annotations within field types so trailing Doxygen comments attach to their original fields.
- Add real-Doxygen regressions for `std.unit::unit`, following signatures, field documentation, source locations, and
  LF/CRLF inputs.
- Regenerate both stage references and verify their raw XML and rendered signatures.

Compiler/runtime behavior, warning policy, and publication are outside this repair. The change is trace-independent. No
diagnostic codes are introduced or reassigned.

## Verification

- The initial 16 regression cases failed against the original filter. The final filter suite passes all 34 cases,
  including qualified split-field types and trailing documentation attachment.
- From `l0/`, `python -m pytest -q -n 0 compiler/stage1_py/tests/cli/test_docgen_*.py` passes all 168 tests.
- Independent real-Doxygen validation across 91 production L0 files confirms all 95 structs and 424 fields retain their
  field sets, normalized types, declaration lines, and physical source paths. All 15 enum span records remain unchanged.
- Strict `make docs DOC_STAGE=all` succeeds with Doxygen 1.18.0. Both stages have zero actionable warnings; the existing
  allowlisted module messages remain (20 across Stage 1 XML/LaTeX logs, 100 across Stage 2 logs).
- Both stages contain XML return type `Unit`, definition `Unit unit`, empty arguments, declaration/body start line 30,
  and body end line 32 for `unit()`. `present()` retains declaration/body start line 39 and body end line 41. Markdown,
  HTML, and preview copies retain the original L0 signatures.
- Generated declaration locations match original sources for all 424 Stage 1 and 1,386 Stage 2 L0 functions.
- LF and CRLF inputs are covered locally; native Windows validation was not run.
- Whitespace, staged ADR Impact, and root pre-commit checks pass.
