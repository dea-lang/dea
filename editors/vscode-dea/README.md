# Dea Language Support for VS Code

This source extension provides TextMate syntax highlighting and editing configuration for:

- Dea/L0 (`dea-l0`, `.l0`, `source.dea.l0`)
- Dea/L1 (`dea-l1`, `.l1`, `source.dea.l1`)

It intentionally provides no language server, diagnostics, completion, hover, navigation, document symbols, semantic
tokens, or refactoring features. See the parent [`editors/README.md`](../README.md) for installation and validation.

## L2 identity

`.l2` files use VS Code `dea-l2`, TextMate `source.dea.l2`, and Vim `dea_l2`. Emacs and Ctags recognize `.l2`;
Tree-sitter uses the existing compatible structural grammar. L2 initially shares L1 syntax but remains a distinct
compiler language identity. `.l1` implementation files under L2 still use the L1 editor identity. Compiler diagnostics
remain authoritative; editor grammar acceptance does not establish validity.
