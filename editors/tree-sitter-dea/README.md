# tree-sitter-dea

[Tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammar for the [Dea](https://github.com/googlielmo/dea-lang)
L0 and L1 languages.

The grammar name is `dea`. It maps both `.l0` and `.l1` files to one structural parser that accepts the richer L1
syntactic superset. Hosts should keep their L0 and L1 language identities separate while reusing this parser.

The Dea compilers remain authoritative. This grammar intentionally favors stable syntax trees and useful recovery while
code is incomplete; it does not enforce level-specific or semantic restrictions.

## Included support

- declarations, exports, imports, structs, enums, aliases, and top-level bindings;
- safe, unsafe, and extern functions;
- statements, control flow, `match`, `case`, and `with` / `cleanup`;
- pointer, nullable, array, slice, and function-pointer types;
- calls, fields, indexes, casts, postfix try expressions, and L1 operators;
- highlights, indentation, locals, and tags queries; and
- corpus coverage for L0, L1, and incomplete-source recovery.

## Development

Node.js and a C compiler are required.

```sh
cd editors/tree-sitter-dea
npm ci
npm test
```

`npm test` regenerates `src/parser.c`, runs the corpus, parses representative `.l0` and `.l1` fixtures, validates every
shipped query, and runs strict highlight checks.

To inspect a syntax tree directly:

```sh
npx tree-sitter parse -p . path/to/source.l1
```

Generated parser sources are checked in so consumers do not need Node.js to build the C parser.

## Source coordinates

Hosts that select parsers by grammar name should map both extensions to `dea`. For example, Neovim can register the
shared parser for separate filetypes:

```lua
vim.treesitter.language.register("dea", { "dea_l0", "dea_l1" })
```

Helix language entries can retain distinct `dea-l0` and `dea-l1` names while setting `grammar = "dea"` on both. Zed
extensions should likewise register one `dea` grammar and two language configurations. Emacs users can associate both
major-mode variants with the `dea` grammar in `treesit-language-source-alist`.

Remote integrations that support a grammar subdirectory should pin both the monorepo revision and this path:

```text
repository: https://github.com/googlielmo/dea-lang
path: editors/tree-sitter-dea
```

Hosts that require a repository-root grammar need a later thin mirror or extraction. That packaging step is deliberately
outside this baseline.

## License

Licensed under either of:

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE)); or
- MIT license ([LICENSE-MIT](LICENSE-MIT)).

at your option.
