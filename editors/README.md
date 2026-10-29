# Dea Editor Support

Version: 2026-10-29

This directory contains Dea syntax highlighting, editing configuration, and top-level navigation indexes. The compiler
remains authoritative: these integrations deliberately accept incomplete code and do not attempt semantic validation.

## Support Matrix

| Host             | Dea/L0 identity                  | Dea/L1 identity                  | Dea/L2 identity                  | Implementation      |
| ---------------- | -------------------------------- | -------------------------------- | -------------------------------- | ------------------- |
| VS Code/TextMate | `dea-l0`, `.l0`, `source.dea.l0` | `dea-l1`, `.l1`, `source.dea.l1` | `dea-l2`, `.l2`, `source.dea.l2` | `vscode-dea/`       |
| Vim              | `dea_l0`, `.l0`                  | `dea_l1`, `.l1`                  | `dea_l2`, `.l2`                  | `vim/`              |
| Emacs            | `dea-mode`, L0 rules             | `dea-mode`, L1 rules             | `dea-mode`, L1 rules             | `emacs/dea-mode.el` |
| Universal Ctags  | `Dea`, `.l0`                     | `Dea`, `.l1`                     | `Dea`, `.l2`                     | `ctags/dea.ctags`   |
| Tree-sitter      | Host-specific `.l0` mapping      | Host-specific `.l1` mapping      | Host-specific `.l2` mapping      | `tree-sitter-dea/`  |

L2 currently shares the L1 structural grammar while retaining a distinct compiler language identity. `.l1`
implementation files under `l2/` still use the L1 editor identity.

**Note:** JetBrains IDEs (IntelliJ IDEA, PyCharm, CLion, etc.) can use the VS Code/TextMate bundle for Dea syntax
highlighting. See below for setup instructions.

## VS Code

The extension is declarative and has no activation code. To validate and build a local VSIX from the checked-in source:

```bash
cd editors/vscode-dea
npm ci
npm test
npm run package
code --install-extension dea-language-support-0.1.0.vsix
```

Reload VS Code after installation. Opening `.l0`, `.l1` or `.l2` files selects `dea-l0`, `dea-l1` or `dea-l2`. The
extension can also be run directly from source with VS Code's Extension Development Host.

`npm test` uses `vscode-textmate` with VS Code's Oniguruma runtime to tokenize the representative and incomplete
fixtures under `vscode-dea/test/fixtures/`.

## JetBrains IDEs

JetBrains IDEs such as IntelliJ IDEA, PyCharm, and CLion support TextMate syntax highlighting using the existing VS Code
bundle.

To enable Dea highlighting:

1. Open **Settings > Editor > TextMate Bundles**.
2. Add the `editors/vscode-dea` directory as a TextMate bundle.
3. Verify that `.l0`, `.l1`, and `.l2` files are recognized correctly.

If highlighting does not work, check **Settings > Editor > File Types** for conflicting file associations.

This integration provides syntax highlighting only, not native JetBrains language support or semantic services. The
package contains no LSP client, diagnostics, completion, hover, go-to-definition, document-symbol, semantic-token,
rename, or refactoring provider.

## Vim

The `vim/` directory is a complete runtime-path fragment. For a one-off session from the repository root:

```bash
vim --cmd "set runtimepath^=$PWD/editors/vim" path/to/source.l0
```

For a persistent Vim 8 package installation, link or copy that directory beneath a package `start` directory:

```bash
mkdir -p ~/.vim/pack/dea/start
ln -s "$PWD/editors/vim" ~/.vim/pack/dea/start/dea
```

The file detector maps `.l0` to `dea_l0`, `.l1` to `dea_l1` and `.l2` to `dea_l2`. The L1 syntax extends the common L0
rules with the L1 keywords, numeric literal forms, labels, and variadic marker. L2 reuses those L1 rules. All three
modes highlight standalone `_` as a wildcard.

## Emacs

Load the fallback mode directly:

```elisp
(add-to-list 'load-path "/absolute/path/to/DEA/editors/emacs")
(require 'dea-mode)
```

`dea-mode` is registered for `.l0`, `.l1` and `.l2`. It sets the buffer-local `dea-language-level` to `0` for `.l0` and
`1` for `.l1` and `.l2`, selecting the corresponding keyword and literal rules, including standalone wildcard
highlighting.

## Universal Ctags and ETAGS

The optlib parser intentionally tags only declarations that begin at the top level: modules, functions (including
`extern` and `unsafe` forms), structs, enums, type aliases, and L1 `const` bindings. It omits fields, imports, local
bindings, enum payload binders, and semantic references.

Generate a normal tags file:

```bash
ctags --options=NONE --options=editors/ctags/dea.ctags -R l0 l1 l2
```

Generate an Emacs-compatible TAGS file from selected source roots:

```bash
ctags --options=NONE --options=editors/ctags/dea.ctags -e -f TAGS l0/examples l1/examples l2/examples
```

These commands require Universal Ctags; the unrelated `/usr/bin/ctags` shipped by some systems does not support optlib
parsers.

## Tree-sitter

The self-contained grammar package lives at `tree-sitter-dea/`. Its stable contract is:

- grammar name `dea`;
- the L1 syntactic superset, with error recovery suitable for incomplete buffers;
- wildcard-only `_ =>` `case` defaults, with removed `else` defaults recovered as invalid syntax;
- separate host mappings for `.l0`, `.l1` and `.l2`; and
- `highlights.scm`, `indents.scm`, `locals.scm`, and `tags.scm` queries.

Build and test the package from the monorepo root:

```bash
cd editors/tree-sitter-dea
npm ci
npm test
```

Remote host configuration should pin a Dea monorepo revision. The examples below use `<monorepo-revision>` as that
placeholder.

### Neovim

Current `nvim-treesitter` installs grammars from a monorepo subdirectory through `install_info.location`. Add the parser
configuration before running `:TSInstall dea` or `:TSUpdate dea`, then map all three Dea filetypes to it:

```lua
vim.api.nvim_create_autocmd("User", {
  pattern = "TSUpdate",
  callback = function()
    require("nvim-treesitter.parsers").dea = {
      install_info = {
        url = "https://github.com/dea-lang/dea",
        revision = "<monorepo-revision>",
        location = "editors/tree-sitter-dea",
        queries = "editors/tree-sitter-dea/queries",
      },
    }
  end,
})

vim.treesitter.language.register("dea", { "dea_l0", "dea_l1", "dea_l2" })
```

For local development, replace `url` with `path = "/absolute/path/to/DEA"` and keep the same `location`.

### Helix

Add the following entries to a user or project `languages.toml`, then run `hx --grammar fetch` and `hx --grammar build`:

```toml
[[language]]
name = "dea-l0"
scope = "source.dea.l0"
file-types = ["l0"]
comment-tokens = "//"
block-comment-tokens = { start = "/*", end = "*/" }
indent = { tab-width = 4, unit = "    " }
grammar = "dea"

[[language]]
name = "dea-l1"
scope = "source.dea.l1"
file-types = ["l1"]
comment-tokens = "//"
block-comment-tokens = { start = "/*", end = "*/" }
indent = { tab-width = 4, unit = "    " }
grammar = "dea"

[[grammar]]
name = "dea"
source = { git = "https://github.com/dea-lang/dea", rev = "<monorepo-revision>", subpath = "editors/tree-sitter-dea" }
```

For L2, add another language entry with `name = "dea-l2"`, `scope = "source.dea.l2"` and `file-types = ["l2"]`, using
the same comments, indentation and `grammar = "dea"` settings.

### Zed

A local Zed language extension should define separate `languages/dea-l0/config.toml`, `languages/dea-l1/config.toml` and
`languages/dea-l2/config.toml` entries with `path_suffixes = ["l0"]`, `["l1"]` and `["l2"]`, respectively. All three set
`grammar = "dea"`. Register the parser once in `extension.toml`.

Zed's grammar configuration does not expose a repository subpath. For local extension development, first extract or
mirror `editors/tree-sitter-dea/` as a repository-root grammar, then point `repository` at that local repository with a
`file://` URL and pin its local revision. A future public Zed extension needs the same thin mirror or extraction. Copy
or adapt the checked-in queries into each language directory as required by the Zed extension layout. Do not add a
language server entry: this baseline is structural only.

### Emacs

On Emacs builds with Tree-sitter support, register and install the grammar:

```elisp
(add-to-list
 'treesit-language-source-alist
 '(dea "https://github.com/dea-lang/dea"
       "<monorepo-revision>"
       "editors/tree-sitter-dea"))
(treesit-install-language-grammar 'dea)
```

The checked-in `dea-mode` remains the regex fallback. A Tree-sitter-backed mode can create a `dea` parser and consume
the shared node vocabulary without collapsing the `.l0`, `.l1` and `.l2` extension identities.

## Validation

Install the pinned Node dependencies once, then run all locally available checks:

```bash
make -C editors install-node-deps
make -C editors test
```

The fallback test runner skips Emacs or Universal Ctags checks when those executables are unavailable. CI installs all
three host tools and makes their presence mandatory:

```bash
STRICT_EDITOR_TOOLS=1 make -C editors test
```

The checked-in editor workflow also packages the VS Code extension and performs a dry-run npm package check for the
Tree-sitter grammar, catching missing or invalid package assets.
