# Bug Fix Plan

## Preserve enum declarations and source locations in generated references

- Date: 2026-10-25
- Status: Completed
- Title: Preserve enum declarations and source locations in generated references
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Targets:
  - L1 canonical reference generation
  - L0 Stage 1 and Stage 2 reference generation
- Origin: L1 documentation filtering and payload rendering corrections
- Porting rule: Port enum scanning and original-source recovery mechanically while preserving level-specific function
  and type translation.
- Target status:
  - L1 canonical reference generation: Implemented
  - L0 Stage 1 and Stage 2 reference generation: Implemented
- Subsystem: Documentation source filtering and enum rendering
- Modules:
  - `l1/compiler/docgen/l1_docgen_l0_filter.py`
  - `l1/compiler/docgen/l1_docgen_l0_helpers.py`
  - `l0/compiler/docgen/l0_docgen_l0_filter.py`
  - `l0/compiler/docgen/l0_docgen_l0_helpers.py`
- Test modules:
  - `l1/tests/test_docgen_filters.py`
  - `l1/tests/test_docgen_outputs.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_l0_filter.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_markdown_renderer.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_latex.py`
- Related:
  - [l0/docs/README.md](../../../../l0/docs/README.md)
- Repro: From `l0/`, run `../.venv/bin/python -m pytest -q -n 0 compiler/stage1_py/tests/cli/test_docgen_l0_filter.py`
  with payload enum and source-location regressions.

## Summary

The line-based enum adapter leaves payload syntax in Doxygen input and misses inline declarations. Doxygen can then
misclassify variants as functions and attach incorrect types or source locations to subsequent declarations. The
original-source renderer also assumes one variant per line and loses inline or multiline payload signatures.

L1 has a validated token-aware correction. Apply the same enum handling to L0, whose relevant payload syntax is shared,
and regenerate both L0 stages. Documentation tooling changes do not alter compiler or runtime behavior.

## ADR Impact

- Decision: Restore faithful enum representation and source positions in generated API documentation.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs the existing Doxygen adaptation and rendering contract without introducing a new language,
    compiler, runtime, or documentation architecture.

## Scope and Approach

1. Preserve the validated L1 implementation and its existing regression evidence.
2. Port token-aware enum detection, payload masking, separator conversion, and original-source variant recovery to L0.
3. Retain L0 nullable type spelling and function translation. Pad collapsed multiline signatures so later declarations
   retain their original line numbers.
4. Add real-Doxygen regressions for enum classification, function signatures, source locations, comments, and LF/CRLF
   inputs, plus Markdown and LaTeX payload recovery.
5. Run focused documentation tests and regenerate strict HTML, Markdown, and LaTeX for both L0 stages. Verify generated
   enum inventories and affected source locations.

## Non-Goals

- Changing either language grammar, compiler output, runtime behavior, or diagnostics.
- Porting L1 export handling to L0.
- Filling undocumented-function coverage gaps or changing the report enforcement policy.
- Pushing or publishing generated documentation.

## Verification Criteria

- Payload variants appear as enum values and retain their original signatures in rendered documentation.
- Following functions retain their return and parameter types and original declaration locations.
- Inline and multiline enums, multiline headers, comments, and LF/CRLF inputs preserve source line counts.
- L0 Stage 1 and Stage 2 strict reference generation succeeds with zero actionable Doxygen warnings under the existing
  warning policy.
- Focused documentation tests, whitespace checks, ADR Impact validation, and root pre-commit pass.

## Outcome

- Ported the enum scanner and rewriter without behavioral divergence, including payload masking, comment/literal
  handling, and source-span recovery for Markdown and LaTeX.
- Preserved L0 nullable type spelling and signature translation; added blank-line padding when collapsing multiline
  signatures.
- Added generated-XML regressions for signatures, parameters, enum classification, and original declaration/body
  locations with inline/multiline declarations and LF/CRLF inputs.
- Updated the L0 documentation layout guide to record payload and declaration-location preservation.
- Kept compiler, runtime, warning enforcement, and publication behavior unchanged.

## Verification

- Reused the unchanged L1 `make test-docgen` result (70 passed), strict `make docs` generation, and corpus checks for 41
  enums and 769 stdlib function declaration locations. Staged whitespace, ADR Impact, and root pre-commit passed before
  the local L1 commit.
- From `l0/`, `L0_CC=/usr/bin/clang ../.venv/bin/python -m pytest -q -n 0 compiler/stage1_py/tests/cli/test_docgen_*.py`
  passed all 146 documentation tests with Doxygen 1.18.0.
- From `l0/`, `make docs DOC_STAGE=all` regenerated Stage 1 and Stage 2 HTML, Markdown, and LaTeX under
  `build/docs/stage1/` and `build/docs/stage2/`.
- Corpus validation matched all 15 Stage 2 enum inventories and source locations, plus 198 function declaration
  locations in enum-containing files. Stage 1's selected L0 sources contain no enums; its generated reference and shared
  renderer regressions passed.
- Both stages had zero actionable warnings. Raw logs retain the existing allowlisted module/no-primary-interface
  diagnostics (20 messages across the Stage 1 XML/LaTeX logs and 100 across Stage 2); warning policy was not changed.
- AST comparison confirmed parity between the L0 and L1 enum scanner and rewriter, excluding level-specific docstrings.
- A broader location audit found an existing `std.unit::unit` XML declaration location of line 1, with correct body
  lines 30-32. The empty `struct Unit {}` lacks a C-like terminating semicolon in the shadow source, causing Doxygen to
  merge it with the following function. An isolated semicolon-only correction restores the declaration location to line
  30\. This pre-existing inline-struct defect is outside the enum fix; the separate allowlisted module warning does not
  cause it.
