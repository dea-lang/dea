# Dea Source Text and Language Vocabulary

Version: 2026-06-09

Normative shared specification for Dea source-text encoding and the character repertoire of the language vocabulary.

## Related Docs

- [docs/decisions/0008-source-text-encoding-and-ascii-language-vocabulary.md](../../decisions/0008-source-text-encoding-and-ascii-language-vocabulary.md):
  shared architectural decision for this policy.
- [l0/docs/specs/compiler/stage1-contract.md](../../../l0/docs/specs/compiler/stage1-contract.md): current L0 Stage 1
  driver contract.
- [l0/docs/reference/grammar.md](../../../l0/docs/reference/grammar.md): L0 lexical grammar.
- [l1/docs/reference/grammar.md](../../../l1/docs/reference/grammar.md): L1 lexical grammar.

## Scope

This specification applies to Dea source files across language levels unless a future Dea-wide document explicitly
narrows it.

## Canonical source encoding

- The canonical encoding of Dea source files is UTF-8.
- Compiler implementations decode source as UTF-8 before lexing.
- A UTF-8 byte order mark may be accepted and stripped when a level-local compiler contract says so.
- Source bytes that are not valid UTF-8 are not valid Dea source text.

## Unicode-bearing source regions

- Comments may contain arbitrary Unicode characters representable in UTF-8, subject to the existing lexical terminators
  of the comment form in use.
- String literal payload text may contain arbitrary Unicode characters representable in UTF-8, subject to the existing
  delimiter and escape rules of the level grammar.
- These Unicode allowances do not expand the spelling rules for identifiers, keywords, builtin type names, module names,
  or other language-vocabulary tokens.

## ASCII-only language vocabulary

The Dea language vocabulary is ASCII-only. This rule applies to every grammar-defined spelling that participates in
lexing, parsing, name lookup, or module resolution, including:

- identifiers
- keywords and reserved words
- builtin type names
- module path components
- operator and punctuation tokens
- file-name components derived from module paths

In practice, this means:

- identifier character classes are defined by explicit ASCII ranges rather than by a Unicode alphabetic category
- module names are dot-separated ASCII identifiers
- module file paths derived from those names are ASCII-only path segments plus ASCII separators and level-local file
  extensions such as `.l0` or `.l1`
- compiler implementations do not apply Unicode normalization, case folding, or locale-dependent classification to the
  language vocabulary

## Implementation consequences

- A non-ASCII UTF-8 character is not automatically invalid source text. It is valid in comments and string literals,
  where the grammar allows free-form text.
- The same non-ASCII character is outside the language vocabulary when it appears where the grammar expects an
  ASCII-only token spelling, such as an identifier, keyword, or module name.
- Level-local grammars and contracts should restate this policy only as a consistency copy of this shared rule, not as
  an independent competing definition.
