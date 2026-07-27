# ADR-0018: Shared Editor Tooling, Level Identities, and Compiler Authority

- Decision date: 2026-06-30
- Last edited: 2026-07-27
- Status: Accepted

## Context

L0 and L1 share a substantial syntax vocabulary, but they remain distinct language levels with different file extensions
and L1-only constructs. Separate editor implementations would duplicate grammar maintenance and drift on shared syntax.
A single undifferentiated editor identity, however, would obscure which level a file targets.

Editor parsers also operate under different requirements from the compiler. They must structure incomplete source while
a user types and should support highlighting, indentation, navigation, and text objects even when a program is not
valid. Encoding type checking or complete level-specific rejection into editor grammars would create a second semantic
authority that can silently disagree with the compiler.

## Decision

Dea maintains one shared editor-support tree under `editors/`, with distinct public identities for L0 and L1 wherever a
host supports that distinction.

The stable mappings include:

- VS Code language IDs `dea-l0` for `.l0` and `dea-l1` for `.l1`;
- TextMate scopes `source.dea.l0` and `source.dea.l1`;
- Vim filetypes `dea_l0` and `dea_l1`; and
- extension-aware L0 and L1 keyword behavior in fallback modes.

The in-repository Tree-sitter package uses grammar name `dea` and parses the richer L1 syntactic superset. Its grammar
and queries are deliberately error-tolerant and structural. Level-specific host mappings remain distinct even though
they can share that parser.

The compiler is the authority for language validity, diagnostics, types, ownership, and all other semantics. Acceptance
by TextMate, Tree-sitter, a regex fallback, or Ctags is not evidence that source is valid Dea for either level.

The baseline editor package provides syntax and structural tooling only. Compiler-backed diagnostics, hover, completion,
semantic tokens, document symbols, definitions, rename, and refactoring are deferred to a dedicated LSP or
compiler-integration design. Future semantic editor services derive their answers from compiler contracts rather than
reimplementing the language independently.

## Rationale

- One package and structural grammar avoid duplicating the large common syntax surface.
- Distinct host identities preserve the user's selected language level and prevent `.l0` and `.l1` from becoming one
  ambiguous file type.
- An L1-superset grammar offers one useful structural tree for both levels while tolerating incomplete edits.
- Keeping the compiler authoritative prevents editor convenience grammar from becoming an accidental specification.
- Deferring semantic services allows their protocol and compiler boundary to be designed deliberately rather than
  growing out of regex or parser heuristics.

## Consequences

- Shared editor code must preserve separate extension, scope, language-ID, and filetype mappings.
- The structural parser may accept L1-only forms in an L0 buffer; the compiler remains responsible for rejecting them.
- Grammar recovery and stable node shapes are preferred over fail-fast semantic strictness.
- Ctags remains a conservative top-level navigation index rather than a local-binding or reference resolver.
- Editor tests cover both level identities and incomplete-source behavior.
- A future LSP must define how compiler diagnostics and semantic data are exposed; it must not infer normative behavior
  from Tree-sitter acceptance.
- The Tree-sitter package may later be mirrored for distribution without changing the monorepo as its source of truth.

## Related Plans

- [work/plans/features/closed/2026-06-30-shared-editor-support-noref.md](../../work/plans/features/closed/2026-06-30-shared-editor-support-noref.md):
  established and implemented the shared editor baseline
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the historical decision into the ADR catalog

## Current Docs

- [docs/decisions/0004-monorepo-directory-structure.md](0004-monorepo-directory-structure.md): ownership of the shared
  `editors/` subtree
- [editors/README.md](../../editors/README.md): supported editor integrations, identities, and validation
- [editors/tree-sitter-dea/README.md](../../editors/tree-sitter-dea/README.md): structural grammar scope and consumption
- [editors/vscode-dea/package.json](../../editors/vscode-dea/package.json): public VS Code language and grammar
  identities
- [l0/docs/reference/grammar.md](../../l0/docs/reference/grammar.md): normative L0 grammar
- [l1/docs/reference/grammar.md](../../l1/docs/reference/grammar.md): normative L1 grammar
