# ADR-0008: Source Text Encoding and ASCII Language Vocabulary

- Decision date: 2026-06-09
- Last edited: 2026-06-09
- Status: Accepted

## Context

The repository already documented parts of the source-text policy, but only in level-local fragments:

- L0 and L1 reference grammars already defined identifiers with explicit ASCII letter and digit ranges.
- L0 and L1 architecture and contract docs already described source decoding as UTF-8, with optional BOM stripping in
  the implementations that support it.
- String literal grammar already allowed multi-byte UTF-8 text.

What was missing was a single Dea-wide decision that states how these pieces fit together. That gap matters because the
current implementations are not fully aligned: L0 Stage 2 and L1 Stage 1 classify identifier bytes with explicit ASCII
helpers, while L0 Stage 1 Python still uses Unicode-aware `isalpha()` and `isalnum()` checks and therefore accepts
non-ASCII identifier characters that the documented grammar does not.

## Decision

Dea source text uses a split policy:

1. **Canonical source encoding is UTF-8.** Source files are decoded as UTF-8 before lexing. Invalid UTF-8 input is not
   valid Dea source text. A UTF-8 BOM may be accepted and stripped when a level-local compiler contract says so.
2. **Comments and string literals may carry Unicode text.** Unicode characters representable in UTF-8 are allowed in
   comment text and string literal payloads, subject to the existing lexical delimiter and escape rules of the relevant
   level grammar.
3. **The language vocabulary is ASCII-only.** Grammar-defined spellings such as identifiers, keywords, reserved words,
   builtin type names, module path components, and file-name components derived from module paths must use ASCII only.
4. **This is a Dea-wide rule.** The shared normative specification for the rule lives in
   [docs/specs/language/source-text-and-language-vocabulary.md](../specs/language/source-text-and-language-vocabulary.md).
   Level-local grammar and contract docs may restate it for clarity but do not own an independent variant of the policy.

## Rationale

- UTF-8 is the conventional source encoding for modern toolchains and already matches the current driver contracts.
- Allowing Unicode in comments and string payloads keeps source files suitable for natural-language text and data
  without forcing the language grammar itself to become Unicode-sensitive.
- Keeping the language vocabulary ASCII-only makes identifier classification, keyword matching, module resolution, and
  seeded compiler ports deterministic across implementations and host languages.
- A shared Dea-wide rule removes ambiguity about whether a permissive implementation detail, such as Python Unicode
  character classes, is intentional language surface or just an implementation bug.

## Consequences

- The shared policy is now recorded normatively in `docs/specs/language/source-text-and-language-vocabulary.md`.
- L0 and L1 current-state docs should remain consistent with that shared rule.
- L0 Stage 1 must be tightened to reject non-ASCII identifier characters so the implementation matches the documented
  grammar and the other active frontends.
- Future Dea implementations should treat Unicode in comments and string literals as valid source text without extending
  identifiers or other grammar-defined token spellings beyond ASCII unless a later Dea-wide decision explicitly changes
  this ADR.

## Related Plans

- [l0/work/plans/bug-fixes/closed/2026-06-09-stage1-non-ascii-identifier-rejection-noref.md](../../l0/work/plans/bug-fixes/closed/2026-06-09-stage1-non-ascii-identifier-rejection-noref.md):
  closed L0 Stage 1 conformance fix for non-ASCII identifiers

## Current Docs

- [docs/specs/language/source-text-and-language-vocabulary.md](../specs/language/source-text-and-language-vocabulary.md):
  shared normative rule
- [l0/docs/specs/compiler/stage1-contract.md](../../l0/docs/specs/compiler/stage1-contract.md): L0 Stage 1 source/module
  contract note
- [l0/docs/reference/grammar.md](../../l0/docs/reference/grammar.md): L0 ASCII identifier grammar and Unicode string
  note
- [l0/docs/reference/architecture.md](../../l0/docs/reference/architecture.md): L0 source decoding and vocabulary note
- [l1/docs/reference/grammar.md](../../l1/docs/reference/grammar.md): L1 ASCII identifier grammar and Unicode string
  note
- [l1/docs/reference/architecture.md](../../l1/docs/reference/architecture.md): L1 source decoding and vocabulary note
