# Feature Plan

## Shared editor support baseline

- Date: 2026-06-30
- Status: Completed
- Title: Shared editor support baseline for Dea/L0 and Dea/L1
- Kind: Feature
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - VS Code TextMate package
  - Vim and Emacs fallback modes
  - Universal Ctags optlib
  - In-repository `editors/tree-sitter-dea/` grammar package
  - Editor support samples and packaging docs
- Origin: Shared Dea language surface across L0 and L1, with L1 used as the richer parser superset for structural editor
  support.
- Porting rule: Editor integrations may share one package and parser implementation, but L0 and L1 must remain distinct
  language IDs, filetypes, scopes, and file-extension mappings wherever the host editor supports that distinction.
- Target status:
  - VS Code TextMate package: Implemented
  - Vim and Emacs fallback modes: Implemented
  - Universal Ctags optlib: Implemented
  - In-repository `editors/tree-sitter-dea/` grammar package: Implemented
  - Editor support samples and packaging docs: Implemented
- Subsystem: Editor tooling / syntax highlighting / structural parsing / navigation indexes
- Modules:
  - `editors/`
  - `editors/tree-sitter-dea/`
  - `l0/docs/reference/grammar.md`
  - `l1/docs/reference/grammar.md`
- Test modules:
  - `editors/vscode-dea/test/fixtures/`
  - `editors/tests/`
  - `editors/tree-sitter-dea/test/corpus/`
- Related:
  - `l0/docs/reference/grammar.md`
  - `l1/docs/reference/grammar.md`
  - `docs/specs/language/source-text-and-language-vocabulary.md`

## Summary

Dea needs baseline editor support that works before any semantic service exists. The first supported stack is native
editor grammar and indexing support:

1. TextMate grammars for VS Code, GitHub/Linguist readiness, TextMate-compatible consumers, and Sublime fallback use.
2. A Tree-sitter grammar for structural highlighting, indentation, text objects, tags, locals, and outline-oriented
   integrations.
3. Vim and Emacs regex modes as cheap universal fallbacks.
4. Universal Ctags and ETAGS-compatible navigation indexes for top-level symbols only.

LSP is explicitly out of scope for this plan. Diagnostics, hover, completion, document symbols, go-to-definition,
semantic-token overlays, rename/refactoring, and compiler JSON output modes must be handled by a later dedicated plan.

## Current State

The repository has no checked-in `editors/` package and no Tree-sitter grammar. The current language surface is
documented in `l0/docs/reference/grammar.md` and `l1/docs/reference/grammar.md`; L0 uses `.l0` and L1 uses `.l1`.

The editor grammars must follow both the references and implementation behavior:

- identifiers are ASCII-only, while strings and comments may carry UTF-8 text;
- both line comments (`//`) and block comments (`/* ... */`, including Doxygen-style `/** ... */`) are used throughout
  the tree and must highlight correctly;
- L0 covers the core C-family Dea surface (`module`, `import`, `func`, `match`, `case`, `with`, `cleanup`, nullable
  suffixes, enum payload patterns, `=>`, `::`, and current operators);
- L1 extends the surface with `export`, selective imports, `unsafe func`, function pointer types, fixed arrays, slices,
  wider numeric literals, real literals, `%`, bitwise operators, variadics, named arguments, top-level bindings, and
  const contexts.

Piggybacking on C highlighting is a non-goal because Dea has enough distinct syntax that misleading colors would be
worse than a focused conservative grammar.

## Defaults Chosen

1. **One editor-support package, two language identities.** The repository should add a single `editors/` tree, but use
   separate L0 and L1 IDs internally: `dea-l0` / `dea-l1`, `source.dea.l0` / `source.dea.l1`, and Vim filetypes `dea_l0`
   / `dea_l1`.
2. **TextMate before Tree-sitter.** TextMate has the fastest cross-editor payoff and is the required baseline for VS
   Code syntax tokenization and later Linguist upstreaming.
3. **Tree-sitter parses the L1 superset.** The Tree-sitter grammar name is `dea`; it should accept the richer L1
   syntactic superset and stay error-tolerant while users type. L0/L1 extension and filetype mappings remain separate,
   and editor queries may avoid highlighting L1-only forms too aggressively in L0 contexts.
4. **Tree-sitter stays in the monorepo.** Its self-contained package root is `editors/tree-sitter-dea/`. The
   conventional package name matches `editors/vscode-dea/`, remains recognizable to Tree-sitter consumers, and permits a
   later mirror or extraction without reorganizing the package. A separate repository is not required for this baseline.
5. **Compiler remains authoritative.** Editor grammars are not semantic validators. They should highlight and structure
   incomplete code without trying to encode type checking or level-specific semantic rejection.
6. **Ctags is navigation-only.** The optlib should index modules, functions, structs, enums, type aliases, and top-level
   constants. Local bindings, enum payload binders, fields, imports, and overload-like semantic contexts are left to
   Tree-sitter queries or future compiler-backed services.
7. **No compiler diagnostics.** This plan does not add, reserve, or reassign diagnostic codes.

## Public Interfaces

The first implementation must expose these stable editor-facing identifiers:

```text
VS Code language IDs:
  dea-l0 -> .l0
  dea-l1 -> .l1

TextMate scopes:
  source.dea.l0
  source.dea.l1

Vim filetypes:
  dea_l0
  dea_l1

Emacs:
  dea-mode for .l0 and .l1, with extension-aware keyword sets

Ctags:
  language name Dea, mapped to .l0 and .l1

Tree-sitter:
  grammar name dea
```

The VS Code package must not contribute an LSP client, semantic-token provider, diagnostic provider, completion
provider, hover provider, definition provider, or document-symbol provider in this plan.

## Implementation Phases

### Phase 1: TextMate and lightweight fallbacks

Add `editors/` with:

- `editors/vscode-dea/package.json` contributing `dea-l0` and `dea-l1`, their `.l0` / `.l1` extensions, `source.dea.l0`
  / `source.dea.l1` grammars, and the shared language configuration;
- `editors/vscode-dea/language-configuration.json` with line comments, block comments, brackets, auto-closing pairs, and
  surrounding pairs;
- `editors/vscode-dea/syntaxes/dea-l0.tmLanguage.json` and `editors/vscode-dea/syntaxes/dea-l1.tmLanguage.json`;
- `editors/vim/ftdetect/dea.vim`, `editors/vim/syntax/dea_l0.vim`, and `editors/vim/syntax/dea_l1.vim`;
- `editors/emacs/dea-mode.el`;
- `editors/ctags/dea.ctags`.

The TextMate grammars should cover comments, strings, byte literals, integer and real literals, bool/null literals,
declaration keywords, control keywords, memory/cast keywords, builtin types, declaration names, module-qualified names,
operators, punctuation, type suffixes, and the L1-only additions. Keep the regexes conservative; avoid validating full
expression grammar or semantic legality.

### Phase 2: Representative samples and local validation

Add fixture samples copied or minimized from real Dea sources:

- L0 examples: at least one sample from `l0/examples/hello.l0` or `l0/examples/demo.l0`, plus one compiler or stdlib
  source that exercises module-qualified names, `with`/`cleanup`, enums, and block comments.
- L1 examples: at least one sample from `l1/examples/hello.l1`, `l1/examples/slices.l1`, or `l1/examples/demo.l1`, plus
  one compiler or stdlib source that exercises exports/imports, fixed arrays or slices, `unsafe func`, real literals,
  named arguments, and const contexts.
- Error-tolerant samples for incomplete comments, incomplete declarations, unterminated strings, and partial `match`,
  `case`, and `with` bodies.

Use these fixtures for TextMate tokenization checks, Vim/Emacs smoke checks, Ctags assertions, and package-manifest
validation.

### Phase 3: In-repository Tree-sitter grammar

Add a self-contained Tree-sitter package at `editors/tree-sitter-dea/`. Keeping the conventional package layout under
`editors/` makes the grammar directly versioned with the language sources while preserving the option to publish a thin
mirror later. The package should contain:

- `grammar.js`;
- `tree-sitter.json`;
- generated parser sources, package manifests, and standard bindings;
- `queries/highlights.scm`;
- `queries/indents.scm`;
- `queries/locals.scm`;
- `queries/tags.scm`;
- `test/corpus/*.txt`.

The parser should accept the L1 syntactic superset and expose a stable node vocabulary for top-level declarations,
imports/exports, function declarations, unsafe/extern functions, type aliases, structs, enums, enum variants, fields,
parameters, blocks, control statements, `match`, `case`, `with`/`cleanup`, type suffixes, function pointer types,
qualified identifiers, calls, fields, indexes, casts, and postfix try expressions.

The first query set should be conservative: keywords, builtin types, declaration names, enum variants, parameters,
fields, literals, comments, and operators. Indentation and tag queries should be useful but not semantic.

### Phase 4: Packaging and upstream readiness

Document local installation and smoke-test flows for:

- installing the VS Code package from the checked-in source;
- installing Vim files through a runtime path;
- loading `dea-mode.el` in Emacs;
- invoking Universal Ctags with `editors/ctags/dea.ctags`;
- building and loading `editors/tree-sitter-dea/` locally in Neovim, Helix, Zed, and Emacs tree-sitter modes;
- pinning the monorepo plus the grammar subpath in hosts that support subdirectory grammars.

If a host's public distribution mechanism requires a repository-root grammar, publish a thin mirror or extract
`editors/tree-sitter-dea/` in later packaging work. That publication is not required to complete this baseline.

Track GitHub Linguist as a later upstreaming step after the TextMate grammar is publicly available under an
MIT/Apache-compatible license and enough representative public `.l0` / `.l1` usage exists. A Linguist PR is not part of
this plan.

## Verification Criteria

1. Opening `.l0` and `.l1` files in the VS Code package selects `dea-l0` and `dea-l1` respectively and applies the
   correct TextMate scope.
2. VS Code comments, brackets, auto-closing pairs, and surrounding pairs work for both language IDs.
3. The VS Code package manifest contains no LSP, diagnostics, hover, completion, definition, document-symbol, or
   semantic-token contributions.
4. TextMate fixture tests cover comments, Unicode strings, declarations, L0-only surfaces, L1-only surfaces, operators,
   and malformed or incomplete code.
5. Vim ftdetect maps `.l0` to `dea_l0` and `.l1` to `dea_l1`; both syntax files load without errors in a headless Vim
   smoke test.
6. Emacs loads `dea-mode.el` non-interactively and applies the mode to `.l0` and `.l1` buffers.
7. Universal Ctags emits only top-level module/function/struct/enum/type/const tags for representative fixtures.
8. Tree-sitter corpus tests parse representative L0 and L1 samples, and query smoke tests exercise highlights, indents,
   locals, and tags.
9. Packaging docs describe editor installation paths without claiming semantic services exist.

## Non-Goals

1. LSP of any kind, including diagnostics, hover, completion, document symbols, go-to-definition, rename, refactoring,
   semantic tokens, or compiler JSON output modes.
2. Changing the Dea language grammar, lexer, parser, analyzer, compiler diagnostics, or CLI contract.
3. Replacing compiler validation with editor grammar validation.
4. Indexing local bindings or semantic references through Ctags.
5. GitHub Linguist upstreaming before the editor grammars are publicly available and sufficient in-the-wild Dea usage.
6. Packaging for every editor marketplace in the first implementation; local installable artifacts and documentation are
   sufficient for this baseline.

## Implementation Status

As of 2026-07-23, all targets are implemented under `editors/`:

- the declarative VS Code package exposes the required L0/L1 IDs and scopes, has no activation code or semantic
  providers, and is validated with the actual VS Code TextMate and Oniguruma libraries;
- Vim and Emacs provide distinct extension-aware fallback highlighting, with headless smoke coverage;
- the Universal Ctags optlib indexes the deliberately limited top-level symbol set and supports normal tags and ETAGS
  output;
- representative and malformed fixtures drive the shared validation;
- `editors/tree-sitter-dea/` contains the L1-superset grammar, generated parser, standard bindings, four planned
  queries, eight corpus cases including incomplete-source recovery, and dual MIT/Apache-2.0 licensing; and
- the editor Makefile and focused GitHub Actions workflow install, test, and package-check both Node-based editor
  packages together.

## Completion Notes

Completed on 2026-07-23.

- Kept L0 and L1 host identities distinct while sharing conservative common syntax definitions and one structural
  parser.
- Imported the complete Tree-sitter package into the monorepo and adapted package metadata for the
  `editors/tree-sitter-dea/` subdirectory.
- Documented local and pinned-subpath consumption for Neovim, Helix, and Emacs, plus Zed's repository-root grammar
  limitation and the later thin-mirror option.
- Added focused editor CI without adding activation code, compiler integration, semantic services, or publication
  workflows.

## Verification Results

- `STRICT_EDITOR_TOOLS=1 make -C editors test`: Pass for TextMate, Tree-sitter corpus/query/highlight checks, Vim,
  Emacs, and Universal Ctags.
- `make -C editors package`: Pass for VSIX creation and the Tree-sitter npm package dry run.
- Broad Tree-sitter sweep: Pass for all 138 production/example sources under the selected L0 and L1 source roots.
- Compiler fixture checks: Pass for `l0_hello`, `l0_surface`, `l1_slices`, and `l1_surface`.
- Tree-sitter Node binding load and C static/shared library builds: Pass.
- `actionlint .github/workflows/editors-ci.yml` and `git diff --check`: Pass.
