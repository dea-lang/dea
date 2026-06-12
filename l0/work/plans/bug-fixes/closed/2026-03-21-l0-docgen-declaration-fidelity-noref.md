# Bug Fix Plan

## L0 docgen declaration fidelity

- Date: 2026-03-21
- Status: Closed
- Title: Restore faithful L0 declaration rendering in generated API docs
- Kind: Bug Fix
- Severity: High (published API docs can misstate the language surface)
- Stage: Shared
- Subsystem: Documentation / Docgen
- Modules:
  - `compiler/docgen/l0_docgen_markdown.py`
  - `compiler/docgen/l0_docgen_l0_helpers.py`
  - `compiler/docgen/l0_docgen_latex.py`
  - `compiler/stage1_py/tests/cli/test_docgen_markdown_renderer.py`
- Test modules:
  - `compiler/stage1_py/tests/cli/test_docgen_cli.py`
  - `compiler/stage1_py/tests/cli/test_docgen_latex.py`
  - `compiler/stage1_py/tests/cli/test_docgen_markdown_renderer.py`
  - `compiler/stage1_py/tests/cli/test_docgen_blog.py`
- Repro: inspect generated Markdown/HTML/blog-export pages for `.l0` declarations such as `parse_diag_count`,
  `rt_alloc`, `rt_free`, `HS_EMPTY`, and nullable struct fields like `module_path`

## Summary

Generated API docs for `.l0` sources drifted away from the original language syntax in several ways:

1. Function signatures were rendered in C syntax such as `int parse_diag_count(ParseResult *self)` instead of
   `func parse_diag_count(self: ParseResult*) -> int`.
2. Nullable markers on function parameters and return types were dropped, for example `void*?` and `string?`.
3. Top-level `let` declarations lost both their annotated type and initializer, for example `let HS_EMPTY` instead of
   `let HS_EMPTY: byte = 0`.
4. Nullable struct fields lost their `?` marker, for example `module_path: VectorString*` instead of
   `module_path: VectorString*?`.

These issues affect all generated API surfaces, including Markdown, curated HTML, Chirpy blog export, native Doxygen
LaTeX, and the generated PDF.

## Root Cause

The docs pipeline currently combines two imperfect inputs for `.l0` declarations:

1. The Doxygen shadow filter rewrites some L0 constructs into C-like syntax for compatibility.
2. The Markdown renderer historically reconstructed signatures from Doxygen XML fields such as `definition`, `type`, and
   `argsstring`.

That combination loses language fidelity because Doxygen XML does not preserve the full original `.l0` declaration
surface:

- A prior docgen strict-validation change introduced explicit lowering of `.l0` function declarations in the shadow
  filter to satisfy Doxygen strict `@param` validation. That caused the function C-syntax regression and function-side
  nullable loss.
- Top-level `let` declarations and nullable struct fields were already lossy in the original docs platform, because the
  XML never preserved their full original source text.

## Scope Of This Fix

1. Prefer the original `.l0` source declaration text for generated member signatures whenever the source file and line
   information resolve cleanly.
2. Restore L0 syntax for functions, top-level `let` declarations, type aliases, and struct fields rendered from `.l0`
   source.
3. Preserve nullable markers and initializers where they exist in the original source.
4. Keep a safe fallback to XML-derived rendering for synthetic fixtures and other cases where source recovery is not
   possible or does not match the requested member.
5. Extend the same source-backed fidelity rules to the LaTeX normalizer so the PDF matches the Markdown and HTML
   surfaces.
6. Leave the Doxygen shadow filter behavior unchanged for now, because it still serves Doxygen validation needs.

## Resolution

Implemented in this repo:

1. Added source-based `.l0` member declaration recovery in `l0_docgen_l0_helpers.py`.
2. Updated the Markdown renderer to prefer recovered source declarations for `.l0` members before falling back to
   XML-derived signatures.
3. Kept the XML-derived fallback path for tests and non-source-backed cases by validating that recovered source text
   actually matches the member name and kind.
4. Added focused renderer tests covering:
   - nullable `.l0` function signatures from source
   - top-level `let` declarations from source
   - nullable `.l0` struct fields from source
5. Extended the LaTeX normalizer to recover source-backed `.l0` declarations as well, including the real XML-vs-LaTeX
   member-id mapping used by Doxygen.
6. Preserved existing blog-export behavior by leaving the source Markdown surface canonical.

## Verification

Targeted verification:

```bash
uv run pytest compiler/stage1_py/tests/cli/test_docgen_markdown_renderer.py -k \
  'preserves_l0_signature_prefix or recovers_nullable_l0_function_signatures_from_source or \
   recovers_l0_top_level_let_from_source or recovers_nullable_l0_struct_fields_from_source or \
   normalizes_l0_function_signature_spacing'
uv run pytest compiler/stage1_py/tests/cli/test_docgen_blog.py -q
uv run pytest compiler/stage1_py/tests/cli/test_docgen_latex.py -q
uv run pytest compiler/stage1_py/tests/cli/test_docgen_cli.py -q
```

Direct LaTeX/PDF-path verification:

```bash
doxygen build/docs/.tmp/generated/Doxyfile.latex
./scripts/gen-docs.sh --strict
```

Representative spot checks:

1. `compiler/stage2_l0/src/parser.l0` functions such as `parse_diag_count`
2. `compiler/shared/l0/stdlib/sys/unsafe.l0` extern functions such as `rt_alloc` and `rt_free`
3. `compiler/shared/l0/stdlib/std/hashset.l0` and `hashmap.l0` top-level `let` constants
4. Nullable struct fields in `compiler/stage2_l0/src/ast.l0`
5. The matching LaTeX pages under `build/docs/doxygen/latex/`

## Assumptions

1. Doxygen source locations for `.l0` members remain stable enough to recover declarations from original source files.
2. The repository source tree is available when docs are generated in CI and release workflows.
3. When source recovery fails or does not match the requested member, falling back to the old XML-derived path remains
   the safest behavior.
