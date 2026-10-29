# Dea Language Support for VS Code

This source extension provides TextMate syntax highlighting and editing configuration for:

- Dea/L0 (`dea-l0`, `.l0`, `source.dea.l0`)
- Dea/L1 (`dea-l1`, `.l1`, `source.dea.l1`)
- Dea/L2 (`dea-l2`, `.l2`, `source.dea.l2`)

It intentionally provides no language server, diagnostics, completion, hover, navigation, document symbols, semantic
tokens, or refactoring features. See [editors/README.md](../README.md) for installation and validation.

L2 currently shares L1 syntax but remains a distinct compiler language identity. `.l1` implementation files under `l2/`
still use the L1 editor identity. Compiler diagnostics remain authoritative; grammar acceptance does not establish
validity.
