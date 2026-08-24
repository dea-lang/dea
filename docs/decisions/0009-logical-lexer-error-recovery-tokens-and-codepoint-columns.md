# ADR-0009: Logical Lexer-Error Recovery Tokens and Code-Point Columns

- Decision date: 2026-06-10
- Last edited: 2026-08-24
- Status: Accepted

## Context

The invalid-character recovery introduced by the closed bug-fix plan
[work/plans/bug-fixes/closed/2026-06-09-shared-lex-0040-recovery-noref.md](../../work/plans/bug-fixes/closed/2026-06-09-shared-lex-0040-recovery-noref.md)
made all three frontends continue lexing after `LEX-0040`, but it paired that recovery with a phase gate: any lexer
error diagnostic skipped the parser entirely. That barrier is hostile to editor and LSP-style use, where a single stray
character, an unterminated string, a malformed byte literal, or an invalid numeric suffix should not suppress the AST
and every later diagnostic.

Separately, the native frontends (L0 Stage 2 and L1 Stage 1) lex raw UTF-8 bytes and advanced the diagnostic column once
per byte. Multibyte UTF-8 characters in comments, string literals, or invalid-character runs therefore inflated every
later column on the same line, and the implementations had no defined way to step over one Unicode character. The L0
Stage 1 Python frontend lexes decoded text and already counted code points, so the frontends disagreed on positions for
the same source.

The compiler phases already gate semantic analysis and code generation on accumulated error diagnostics. Placeholder
literal values are therefore useful for parse recovery but are not semantically authoritative. The shared recovery
contract also does not require one identical physical token representation in every frontend.

## Decision

1. **Recoverable lexer diagnostics are deferred into lexer-error wrapper tokens.** The lexer encapsulates the diagnostic
   (code, message, and the full start/end span) in a dedicated token kind (`TokenKind.LEXER_ERROR` in L0 Stage 1,
   `TT_LEXER_ERROR` in the native frontends) instead of emitting it. The span of a lexer diagnostic stays attached to
   the physical source that caused it.
2. **The recovery contract is Dea-wide logical, not a mandatory physical token layout.** L0 Stage 1 Python may attach
   one or more lexer diagnostics to a single wrapper token plus an optional recovery token. Native L0/L1 may emit a run
   of physical `TT_LEXER_ERROR` tokens for one malformed literal: earlier diagnostics are emitted as unrecoverable
   wrappers, and the final wrapper carries the parser-visible recovery token when one exists.
3. **The parser is the emission point and token access is logical.** `peek`, `advance`, `check`, `match`, and `last`
   expose the recovered token when a wrapper run provides one, skip wrappers with no recovery token, and emit each
   wrapped lexer diagnostic exactly once even when backtracking revisits the same physical token. Deferred diagnostics
   keep their `LEX-*` codes and phase `Lexer`.
4. **The pre-parse lexer barrier is removed.** The parser always runs after lexing. Downstream phases keep gating on
   accumulated error diagnostics, so sources with lexical errors still never reach code generation.
5. **Recoverable literal and numeric diagnostics use wrappers; `LEX-0040` and `LEX-0070` stay no-recovery paths.**
   Wrappers replace direct lexer emission wherever the lexer can preserve a reasonable token shape. Invalid-character
   wrappers (`LEX-0040`) cover one contiguous run of invalid characters and are skipped logically; `LEX-0070`
   (unterminated block comment) remains unrecoverable trivia.
6. **Native columns count Unicode code points.** The byte-based lexers advance the stored column only on non-newline
   bytes that are not UTF-8 continuation bytes, aligning native positions with the L0 Stage 1 Python oracle. Byte
   offsets remain byte-based. Unicode display-width handling stays out of scope.
7. **Token-dump modes render the physical wrapper and its recovery token.** Dumps do not emit diagnostics because the
   parser is not running.

## Rationale

- Deferring diagnostics into the token stream lets the parser keep its position context, report the lexical error
  inline, and continue, which is the behavior editors and language servers need.
- The parser should operate on the token shape most useful for recovery, not on implementation wrappers; one central
  logical-token path avoids scattering lexer-wrapper handling through parse functions and synchronization loops.
- Emitting at a single chokepoint with a per-token-index guard is robust against parser backtracking.
- Existing downstream gates already prevent placeholder values from affecting semantic analysis or code generation.
- Counting columns per code point restores Stage 1/Stage 2 diagnostic parity, which the diagnostic-code policy treats as
  the oracle relationship, and gives "advance one character" a precise meaning in the byte-based lexers.

## Consequences

- A file with lexical errors now parses; `LEX-*` diagnostics appear alongside any genuine parser diagnostics, and
  downstream phases still refuse files with errors.
- `Lexer.tokenize()` in L0 Stage 1 returns wrapper tokens for recoverable diagnostics instead of appending those
  diagnostics directly, and those wrappers may retain multiple lexer diagnostics on one token.
- The native `Token` enum carries a non-recursive payload variant beside `TT_LEXER_ERROR` whose strings are ARC-managed
  and released by the shared token cleanup path; one malformed literal may realize the logical recovery contract as
  multiple queued physical wrappers.
- Parser lookahead helpers must use logical token access when making parse decisions. Direct physical token-vector reads
  are reserved for centralized lookahead code that intentionally understands wrapper runs. The native parsers track
  emitted lexer-error token indices in a new `IntSet` utility (`util/intset.l0`), an open-addressing integer hash set
  modeled on `StringSet` in `std.hashset` and a candidate for later promotion to the `std` library.
- Native diagnostic columns after multibyte content changed (intentionally) from byte counts to code-point counts.
- Existing diagnostic codes and meanings stay unchanged.

## Related Plans

- [work/plans/bug-fixes/closed/2026-08-23-shared-lexer-recovery-expression-context-noref.md](../../work/plans/bug-fixes/closed/2026-08-23-shared-lexer-recovery-expression-context-noref.md):
  closed bug-fix plan that aligned signed-literal context with parser-visible recovery tokens
- [work/plans/refactors/closed/2026-06-10-shared-lexer-error-recovery-tokens-and-codepoint-columns-noref.md](../../work/plans/refactors/closed/2026-06-10-shared-lexer-error-recovery-tokens-and-codepoint-columns-noref.md):
  closed shared refactor plan that introduced this design
- [work/plans/bug-fixes/closed/2026-06-09-shared-lex-0040-recovery-noref.md](../../work/plans/bug-fixes/closed/2026-06-09-shared-lex-0040-recovery-noref.md):
  closed bug-fix plan whose post-recovery parser gate this decision replaces

## Current Docs

- [docs/specs/compiler/diagnostic-code-catalog.md](../specs/compiler/diagnostic-code-catalog.md): shared `LEX-*` code
  meanings and wrapper-deferral note
- [l0/docs/specs/compiler/stage1-contract.md](../../l0/docs/specs/compiler/stage1-contract.md): L0 Stage 1 token model
  with `LEXER_ERROR`
- [l0/docs/reference/architecture.md](../../l0/docs/reference/architecture.md): L0 lexer/parser handoff and code-point
  columns
- [l1/docs/reference/architecture.md](../../l1/docs/reference/architecture.md): L1 lexer/parser handoff and
  logical-column contract
