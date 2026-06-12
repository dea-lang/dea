# Feature Plan

## Integrated Doxygen + m.css Documentation System

- Date: 2026-03-02
- Status: Implemented
- Title: Integrated Doxygen + m.css documentation system with generated HTML, Markdown, and LaTeX output
- Kind: Feature
- Severity: Low (Tooling/Docs)
- Stage: Shared
- Subsystem: Documentation
- Modules:
  - `scripts/gen-docs.sh`
  - `scripts/docs/templates/doxyfile.in`
  - `scripts/docs/templates/mcss_conf.py.in`
  - `scripts/docs/templates/mainpage_html.md.j2`
  - `scripts/docs/templates/mainpage_latex.md.j2`
  - `scripts/docs/templates/markdown_file.md.j2`
  - `scripts/docs/templates/markdown_index.md.j2`
  - `scripts/docs/templates/html_api_page.j2`
  - `scripts/docs/templates/html_api_group.j2`
  - `scripts/docs/templates/html_redirect.j2`
  - `compiler/docgen/l0_docgen.py`
  - `compiler/docgen/l0_docgen_python_filter.py`
  - `compiler/docgen/l0_docgen_markdown.py`
  - `compiler/docgen/l0_docgen_l0_filter.py`
  - `compiler/docgen/l0_docgen_l0_helpers.py`
  - `compiler/docgen/l0_docgen_latex.py`
  - `tools/m.css/`
  - `tools/m.css.L0-PATCHES.md`
  - `tools/m.css/documentation/templates/doxygen/base-class-reference.html`
  - `tools/m.css/documentation/templates/doxygen/entry-var.html`
  - `tools/m.css/documentation/templates/doxygen/details-var.html`
  - `tools/m.css/documentation/templates/doxygen/entry-enum.html`
- Test modules:
  - `compiler/stage1_py/tests/cli/test_docgen_cli.py`
  - `compiler/stage1_py/tests/cli/test_docgen_source_scope.py`
  - `compiler/stage1_py/tests/cli/test_docgen_python_filter.py`
  - `compiler/stage1_py/tests/cli/test_docgen_markdown_renderer.py`
  - `compiler/stage1_py/tests/cli/test_docgen_l0_filter.py`
  - `compiler/stage1_py/tests/cli/test_docgen_latex.py`

## Summary

Implement a reproducible API documentation pipeline that generates HTML, Markdown, Doxygen XML, and normalized LaTeX for
the Dea/L0 codebase.

This document records the decisions and features implemented across the original docs-system work, from the initial
Doxygen and m.css generation pipeline through the docs-output and wrapper polish.

It intentionally stops before the later CI publishing automation.

The pipeline is source-only and excludes tests, fixtures, examples, and hand-written repository Markdown from API
generation. It covers:

1. Stage 1 Python compiler sources
2. Stage 2 L0 compiler sources
3. Shared L0 standard library modules
4. Shared runtime headers

## Implemented Decisions

### Source manifest and extraction

- The docs source set is explicit and stable:
  - `compiler/stage1_py/**/*.py`, excluding tests and `__pycache__`
  - `compiler/stage2_l0/src/**/*.l0`
  - `compiler/stage2_l0/scripts/check_trace_log.py`
  - `compiler/shared/l0/stdlib/**/*.l0`
  - `compiler/shared/runtime/*.h`
  - `compiler/docgen/**/*.py` is intentionally excluded from generated API reference output
- Doxygen does not run against the repository root.
- A generated shadow tree under `build/docs/.tmp/shadow/` is used so all preprocessing is isolated from tracked source.
- Generated output lives under `build/docs/` and is not committed.
- After each successful run, generated artifacts are mirrored into stable preview folders under
  `build/preview/{html,markdown,pdf}` and overwritten by the next successful run.

### Vendored renderer and reproducibility

- `m.css` is vendored under `tools/m.css/` as a tracked snapshot.
- The docs pipeline never clones `m.css` at build time.
- Local renderer adjustments are documented in `tools/m.css.L0-PATCHES.md`.
- The local `m.css` patch set allows Python, C, Markdown, and Objective-C compounds in addition to C++ and hardens title
  extraction for nested/empty heading text.
- The local `m.css` template patches also align raw HTML rendering with L0 syntax conventions:
  - struct/class member sections use `Fields` / `Field documentation` for L0 compounds
  - L0 non-static members render as `name: type`
  - C/C++ member variable declarations preserve Doxygen bitfield widths (`: N`)
  - C/C++ unnamed bitfield placeholders are rendered as declaration-only types (for example `unsigned int: 0`)
  - L0 enum variants render as `Variant(payload);` without C-style `=`

### Generated Doxygen configuration

- Doxygen configuration is generated from templates instead of using a tracked root `Doxyfile`.
- The pipeline uses generated config files with absolute paths so it works from normal checkouts and phantom worktrees.
- The previous root-level `Doxyfile` and `conf.py` were replaced by generated config and template-based main pages.
- HTML-oriented and LaTeX-oriented main pages are split:
  - `mainpage_html.md.j2`
  - `mainpage_latex.md.j2`
- HTML/XML and LaTeX use separate Doxygen passes so the PDF-oriented main page does not inherit HTML wording or links.

### Stage 1 Python docstring conversion

- Google-style Python docstrings are converted into Doxygen-compatible comments before Doxygen sees them.
- Supported structured sections:
  - `Args:`
  - `Returns:`
  - `Raises:`
  - `Attributes:`
  - `Note:`
  - `See Also:`
- Introductory prose is preserved as paragraphs and bullet lists instead of being flattened.
- `See Also:` entries are emitted as Doxygen `@see` items and survive into HTML, Markdown, and LaTeX.
- Bullet lists in Python docstrings are preserved correctly even when written without blank lines between items.

### L0 parser normalization for Doxygen

- Raw `.l0` is not passed directly to Doxygen anymore for structural parsing.
- An L0 shadow-source filter rewrites declarations into a Doxygen-friendly C-like form in the shadow tree only.
- Implemented normalization includes:
  - struct fields: `name: Type;` to `Type name;`
  - enum members: `VALUE;` to `VALUE,`
  - `struct` / `enum` closing braces normalized to `};`
- This eliminates Doxygen-invented synthetic members such as `__pad0__` and stops parser bleed into later declarations.
- The fix applies to XML, HTML, Markdown, and LaTeX because it changes the parsed Doxygen model itself.

### Markdown output design

- Markdown is rendered from Doxygen XML, one file per source file.
- Output mirrors the source tree under `build/docs/markdown/`.
- Markdown pages carry:
  - source path
  - language label
  - module name when available
  - imports/includes
  - symbol table of contents
  - rendered symbol sections
- Internal links are generated as stable relative Markdown paths plus anchors.
- The Markdown index page uses original source filenames as the visible link text while keeping `.md` targets.
- `L0 signature:` prose attached after Doxygen `@return` blocks is preserved in Markdown output (instead of being
  dropped by section filtering).
- L0 signature cross-links are normalized to link the full callable form:
  - `extern [func name(args) -> Ret](...)`
  - this also repairs Doxygen forms where argument lists were emitted outside the link label.

### HTML output design

- HTML is composed from:
  1. raw `m.css` / Doxygen HTML
  2. curated generated pages layered on top
- Curated source pages live under `build/docs/html/api/...`.
- Stage browse pages are generated:
  - `stage1.html`
  - `stage2.html`
  - `shared.html`
- Compatibility pages and backlink pages are generated so raw Doxygen pages do not 404 when `m.css` omits the
  corresponding namespace/file page.
- Raw hierarchy pages are pruned from primary browsing output:
  - raw file pages (`*_8*.html`) are replaced with compatibility redirects to curated `/api/...` source pages
  - raw directory pages (`dir_*.html`) are replaced with redirects to stage/shared curated hubs
  - raw symbol leaf pages (for example `struct*.html`, `class*.html`) remain available as secondary targets
- Raw symbol leaf links that pointed back to raw file pages are retargeted to curated `/api/...` pages to avoid
  cross-surface drift.
- Search result URLs are normalized against the docs-root `search-v2.js` location so nested curated pages under
  `/api/...` resolve raw symbol targets correctly instead of producing relative-path 404s.
- Directory compounds are excluded from search indexing so pruned raw `dir_*.html` pages are not surfaced as dead search
  targets.
- The main HTML navbar was rewritten away from empty default `Pages` / `Files` / `Namespaces` views and toward the
  curated browsing structure.

### HTML information architecture

- Stage 1 Python documentation is symbol-centric:
  - module/source pages are intentionally thin hub pages
  - dedicated class/reference pages remain the primary detailed reference
- Stage 2 and Shared L0/runtime documentation is file-centric:
  - curated file/source pages remain substantive because many APIs are free functions or file-level types
- Raw Doxygen `annotated.html` remains generated but is no longer promoted in top-level navigation.
- Curated source pages retain `Reference Pages` boxes as secondary links to raw symbol leaf pages while search/index
  remains m.css-driven.
- Stage/Shared curated browse pages use a responsive two-column entry layout (file path primary, reference links in a
  separate right column on desktop) and suppress duplicate source-path text when title/path are identical.
- Shared browse pages now include only `compiler/shared/**` sources and exclude generated helper pages such as
  `docs-mainpage-html.md`.

### Curated rendering improvements

- Curated HTML and Markdown pages normalize displayed language:
  - `.l0` pages show `Dea/L0`, not `C++`
- L0 function signatures are reformatted in curated HTML/Markdown:
  - `items: VectorString*`
  - no `Type *name` display style
- Struct field rendering is normalized from C++-style `string Diagnostic::phase` to L0-style `phase: string`
- Non-L0 compound member rendering remains C-like:
  - Markdown member headings use `Member Data ...` instead of `Variable ...` for struct/class/union member variables
  - signatures render as `type name`, not `name: type`
  - anonymous Doxygen inline type IDs (`::@...`) are collapsed from rendered Markdown declarations
- Enum values are rendered explicitly in curated outputs.
- Algebraic enum payload variants such as `TT_IDENT(text: string)` are recovered from source when Doxygen XML loses
  them.
- The redundant/wrong function-body-as-variant regression was fixed so source scanning only augments real enums.
- HTML source pages display full source filenames, not `.md`-derived names.
- Shared/stdlib pages derive module names from real `module ...;` declarations, for example `std.unit`.

### LaTeX support

- Native Doxygen LaTeX is treated as a supported output, not an accidental side effect.
- The docs pipeline now exposes explicit LaTeX modes:
  - default mixed mode includes LaTeX
  - `--latex-only`
  - `--no-latex`
- A LaTeX post-processor normalizes `.l0`-derived `.tex` output instead of replacing Doxygen with a custom LaTeX
  renderer.
- Implemented LaTeX normalization includes:
  - L0 signature spacing
  - L0 signature link labels expanded to include callable form (`func name(args) -> Ret`) for runtime/header pages as
    well
  - L0 struct member presentation in `Public Attributes` and member-data sections
  - file-page module banners
  - arrow rendering in prose as `\rightarrow`
  - retargeting of mistaken L0 links away from Python symbols
  - removal of redundant/wrong `Enumerator` tables when recovered L0 `Variants` are injected
  - injected enum `Variants` blocks for payload-bearing algebraic enums
- Redundant module notes on LaTeX struct pages were removed once Doxygen’s built-in “generated from file” suffix was
  deemed sufficient.
- LaTeX file-page module banners were spaced and simplified to avoid `\paragraph`-related failures in Doxygen’s style.

### Wrapper and local tooling behavior

- `scripts/gen-docs.sh` is the canonical local entry point.
- It validates the presence of `doxygen`, `uv`, and vendored `tools/m.css`.
- It supports:
  - `--html-only`
  - `--markdown-only`
  - `--latex-only`
  - `--no-latex`
  - `--pdf`
  - `--pdf-fast`
  - `--verbose` / `-v`
- `--pdf` runs the LaTeX build and copies `refman.pdf` to `build/docs/pdf/`.
- `--pdf-fast` runs a single-pass `pdflatex` build for faster local preview PDFs (with less complete references/index).
- Quiet mode captures `m.css` warnings and LaTeX build output to temporary logs and only prints them on failure.
- PDF builds are forced into non-interactive LaTeX mode so the wrapper fails fast instead of hanging on prompts.
- Successful runs mirror HTML/Markdown/PDF artifacts into `build/preview/` for stable local browsing between rebuilds.

### Repo integration decisions

- The copyright-header hook and workflow were updated to exclude `tools/`, since vendored third-party sources are
  intentionally tracked and should not be rewritten.
- Generated docs remain outside the hand-authored `docs/` tree.
- README and CLAUDE usage docs were updated to treat docs generation as a supported workflow, including PDF generation.

## Verification

Run:

```bash
uv sync --group docs
./scripts/gen-docs.sh --strict
./scripts/gen-docs.sh --pdf
./scripts/gen-docs.sh --pdf-fast --latex-only
```

Representative focused checks:

```bash
pytest \
  compiler/stage1_py/tests/cli/test_docgen_cli.py \
  compiler/stage1_py/tests/cli/test_docgen_source_scope.py \
  compiler/stage1_py/tests/cli/test_docgen_python_filter.py \
  compiler/stage1_py/tests/cli/test_docgen_markdown_renderer.py \
  compiler/stage1_py/tests/cli/test_docgen_l0_filter.py \
  compiler/stage1_py/tests/cli/test_docgen_latex.py
```

Success criteria:

1. `build/docs/doxygen/xml/` contains Doxygen XML for the source-only manifest.
2. `build/docs/html/index.html` is generated by `m.css` and the curated browse pages exist.
3. `build/docs/markdown/index.md` is generated from the same XML and uses source filenames as link text.
4. Representative HTML and Markdown pages exist for Stage 1, Stage 2, stdlib, and runtime sources.
5. `build/docs/doxygen/latex/` is generated and the resulting `refman.pdf` builds via the wrapper.
6. Stage 2 / Shared output no longer contains synthetic `__padN__` members or gross parser-desync artifacts.
7. Stage 1 Python docstrings preserve structured sections and bullet lists across HTML, Markdown, and LaTeX.
8. `build/preview/html/`, `build/preview/markdown/`, and `build/preview/pdf/` are refreshed after successful runs.
