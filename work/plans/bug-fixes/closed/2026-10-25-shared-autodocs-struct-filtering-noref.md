# Bug Fix Plan

## Preserve struct declarations and source locations across reference filters

- Date: 2026-10-25
- Status: Completed
- Title: Preserve struct declarations and source locations across reference filters
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Targets:
  - L0 Stage 1 and Stage 2 reference generation
  - L1 canonical reference generation
- Origin: Validated L0 token-aware struct documentation repair
- Porting rule: Share lexical struct scanning and source-line preservation while retaining each level's type and
  function translation and L1 export filtering.
- Target status:
  - L0 Stage 1 and Stage 2 reference generation: Implemented
  - L1 canonical reference generation: Implemented
- Subsystem: Documentation source filtering
- Modules:
  - `l0/compiler/docgen/l0_docgen_l0_filter.py`
  - `l1/compiler/docgen/l1_docgen_l0_filter.py`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_docgen_l0_filter.py`
  - `l1/tests/test_docgen_filters.py`
- Related:
  - [l0/work/plans/bug-fixes/closed/2026-10-25-autodocs-inline-struct-filtering-noref.md][l0-repair]
  - [l1/docs/README.md][l1-docs]
- Repro: L1 filtering of `struct Unit { /* empty */ }` raises `ValueError`; trailing comments and split headers leave
  struct declarations unterminated.

## Summary

L0 now translates structs through token-aware spans and preserves their source locations. L1 already handles simple
inline and empty structs, including its current `std.unit` declarations, but its line-based adaptation still misreads
comments and split headers. Valid commented inline declarations can fail documentation generation. Braces in comments
can leave later fields untranslated or corrupt subsequent function metadata.

Adapt the validated scanner to L1 without changing its function-pointer, array, nullable, or qualified type conversion,
export-manifest removal, or original-source signature rendering. Both source languages handled by the L1 reference
generator remain covered. Documentation tooling changes are trace-independent and introduce no diagnostic codes.

## ADR Impact

- Decision: Restore faithful struct adaptation while preserving level-specific documentation behavior.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs the existing source adapter without changing language syntax, compiler/runtime behavior,
    public APIs, or the documentation architecture.

## Scope and approach

1. Preserve the completed L0 implementation and reuse its unchanged validation evidence.
2. Port lexical declaration/member spans and function-start detection; preserve L1 type conversion and export filtering.
3. Preserve field documentation, inline/empty/multiline/split-header forms, and source line counts.
4. Add regressions for exact generated signatures, declaration/body locations, field types and comments, L1-specific
   callbacks and arrays, export interactions, and LF/CRLF inputs.
5. Run the L1 documentation suite and strict reference generation, then independently inspect the generated corpus.

Compiler/runtime changes, undocumented-function coverage policy, and publication are outside this repair.

## Outcome

- Adapted lexical struct/member scanning and function-start detection without changing L1 type conversion, export
  filtering, parameter splitting, or function-signature translation.
- Preserved comments, nullable callback/pointer types, arrays and slices, qualified types, and original source lines.
- Restored the real `fingerprint: string` fields in `ModuleInterface` and `InterfaceHeader`: field translation now
  precedes top-level header removal.
- Added 30 regression cases covering original defects and retained L1 behavior, including actual `std.unit` metadata,
  commented structs, source locations, field documentation, exports, callbacks, arrays, and LF/CRLF inputs.
- Regenerated the L1 XML, HTML, Markdown, and LaTeX reference without changing warning or coverage policy.

## Verification

- Reused the unchanged L0 `python -m pytest -q -n 0 compiler/stage1_py/tests/cli/test_docgen_*.py` result (168 passed)
  and strict `make docs DOC_STAGE=all` generation before the local L0 commit. No covered source, tests, dependencies, or
  toolchain selection changed before reuse. Staged checks and commit hooks passed.
- Before adaptation, the initial L1 regression set reproduced 16 failures; plain `std.unit` already passed. The final
  focused filter suite passes all 53 cases.
- From `l1/`, `make test-docgen` passes all 100 documentation tests with explicit Apple Clang paths configured; the
  documentation checks do not compile native code.
- Strict `make docs` succeeds with Doxygen 1.18.0 and zero actionable warnings. The report remains at 432 undocumented
  functions with zero stdlib entries.
- Independent XML corpus validation matches all 156 structs, 715 fields, 2,592 function declaration locations, and 2,379
  function body spans. Both restored `fingerprint` fields retain their original source lines and string types.
- `std.unit::unit` retains XML return type `Unit`, definition `Unit unit`, empty arguments, declaration/body start line
  30, and body end line 32. `present()` retains lines 39-41. Markdown and HTML preserve the original L1 signatures.
- Independent AST comparison confirms the L1 type, export, parameter, and function-signature helpers are unchanged;
  shared scanning/rewriting logic matches L0 apart from level-specific docstrings.
- LF/CRLF fixtures and physical native-file path comparisons pass locally; native Windows validation was not run.
- Whitespace, staged ADR Impact, and root pre-commit checks pass.

[l0-repair]: ../../../../l0/work/plans/bug-fixes/closed/2026-10-25-autodocs-inline-struct-filtering-noref.md
[l1-docs]: ../../../../l1/docs/README.md
