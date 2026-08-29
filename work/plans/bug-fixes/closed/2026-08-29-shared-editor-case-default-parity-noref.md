# Bug Fix Plan

## Align shared editor case defaults and wildcard highlighting

- Date: 2026-08-29
- Status: Completed
- Title: Reject removed `case ... else` defaults and highlight wildcard arms consistently across shared editors
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - Tree-sitter grammar and highlight queries
  - VS Code TextMate regression coverage
  - Vim and Emacs fallback highlighting
  - Shared editor fixtures and documentation
- Origin: The wildcard-only `case` grammar established by ADR-0007 and the shared editor boundaries established by
  ADR-0018.
- Porting rule: Keep `_ =>` as the only structurally valid `case` default in Tree-sitter, preserve ordinary
  `if ... else`, and present standalone `_` as a wildcard in every syntax highlighter without treating regex modes as
  validators.
- Target status:
  - Tree-sitter grammar and highlight queries: Implemented
  - VS Code TextMate regression coverage: Implemented
  - Vim and Emacs fallback highlighting: Implemented
  - Shared editor fixtures and documentation: Implemented
- Subsystem: Shared editor tooling / Tree-sitter syntax / Syntax highlighting / Regression coverage
- Modules:
  - `editors/tree-sitter-dea/`
  - `editors/vscode-dea/`
  - `editors/vim/`
  - `editors/emacs/`
  - `editors/README.md`
- Test modules:
  - `editors/tree-sitter-dea/test/`
  - `editors/vscode-dea/test/`
  - `editors/tests/test_editor_support.py`
- Related:
  - `docs/decisions/0007-case-default-arm-wildcard.md`
  - `docs/decisions/0018-shared-editor-tooling-level-identities-and-compiler-authority.md`
  - `work/plans/features/closed/2026-06-30-shared-editor-support-noref.md`
- Repro: Parse `case (value) { 1 => return 1; else return 0; }` with `editors/tree-sitter-dea`; the removed `else`
  spelling currently produces a valid `case_default_arm` instead of a recovery error.

## Summary

The shared Tree-sitter grammar still accepts the removed `else Stmt` spelling for a `case` default even though L0 and L1
accept only `_ => Stmt`. The valid wildcard form parses correctly, but Tree-sitter does not capture its `_` for
highlighting, the Vim and Emacs fallbacks do not style standalone wildcards, and the current tests do not reject the
legacy form or assert wildcard presentation across editor integrations.

## ADR Impact

- Decision: Keep `_ =>` as the sole structurally valid shared `case` default while recovering removed `else` input as
  invalid syntax.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0007-case-default-arm-wildcard.md`
  - Rationale: ADR-0007 records the completed wildcard-only migration and removal of `else` defaults from both levels.
- Decision: Preserve one error-tolerant structural parser and lightweight regex highlighters without making editor
  acceptance a source-language validity guarantee.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0018-shared-editor-tooling-level-identities-and-compiler-authority.md`
  - Rationale: ADR-0018 establishes shared editor ownership, distinct level identities, compiler authority, and the
    structural-versus-regex validation boundary.

## Current State and Root Cause

1. `case_default_arm` is a choice between `_ => Stmt` and `else Stmt`, retaining the removed compatibility branch.
2. The highlight query captures `=>` but neither the anonymous `_` in `case_default_arm` nor `wildcard_pattern`.
3. TextMate already recognizes standalone `_`, while Vim and Emacs have no corresponding fallback rule.
4. Positive fixtures contain `_ =>`, but the tests neither reject legacy syntax nor assert wildcard highlighting.

## Scope of This Fix

1. Remove the Tree-sitter `else Stmt` default alternative without changing the valid `case_default_arm` node or its
   `body` field.
2. Capture `case` and `match` wildcards as constants in Tree-sitter, Vim, and Emacs while retaining the existing
   TextMate scope.
3. Preserve ordinary `if ... else`, incomplete-source recovery, level identities, and the shared L1-superset parser.
4. Add focused syntax, query, TextMate, Vim, and Emacs regressions for both language extensions.
5. Refresh editor documentation and checked-in generated parser artifacts.

## Non-Goals

1. Adding compiler diagnostics, semantic validation, or an LSP.
2. Removing `else` from keyword sets or marking it invalid in regex-only highlighters.
3. Changing Ctags, package versions, marketplace artifacts, or release state.
4. Changing the normative L0 or L1 grammar, which already documents wildcard-only defaults.

## Verification Criteria

1. Tree-sitter parses valid block and single-statement `_ =>` defaults as `case_default_arm` and reports an error for
   the removed `else Stmt` spelling.
2. An unbraced `if ... else` used as a value-arm body remains valid.
3. Tree-sitter highlights both `case` defaults and `match` patterns with `@constant.builtin`.
4. TextMate, Vim, and Emacs tests confirm standalone wildcard highlighting for `.l0` and `.l1` fixtures.
5. `STRICT_EDITOR_TOOLS=1 make -C editors test` and `make -C editors package` pass.
6. ADR-impact, staged whitespace, and pre-commit validation pass before the local commit.

## Implementation Outcome

1. Tree-sitter now accepts only `_ => Stmt` as a valid `case_default_arm`; legacy `else Stmt` input recovers through an
   `ERROR` node while ordinary `if ... else` remains valid.
2. Tree-sitter captures both `case` and `match` wildcards as `@constant.builtin`, and Vim and Emacs now style standalone
   `_` as a constant-like wildcard.
3. TextMate's existing wildcard and arrow scopes are covered for both language levels, and the fallback smoke tests
   verify wildcard presentation for `.l0` and `.l1`.
4. Generated parser artifacts and editor documentation now match the wildcard-only grammar.

## Verification Results

1. `STRICT_EDITOR_TOOLS=1 make -C editors test`: Pass with 7 TextMate tests, 10 Tree-sitter corpus parses, and 5
   fallback integration tests.
2. `make -C editors package`: Pass for the VS Code VSIX and Tree-sitter npm dry run.
3. Pinned Tree-sitter CLI 0.26.11 regeneration reproduces `src/grammar.json`, `src/node-types.json`, and `src/parser.c`
   byte-for-byte.
4. Direct legacy and valid syntax probes confirm the expected `ERROR` recovery and unchanged valid `case_default_arm`
   CST.
5. Independent read-only review found no code, query, generated-artifact, or test defect after lifecycle closure was
   identified as the only remaining action.
