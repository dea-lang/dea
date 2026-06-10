# Refactor Plan

## Shared lexer-error recovery tokens and code-point columns

- Date: 2026-06-10
- Status: Completed
- Title: Defer lexer diagnostics into logical recovery wrapper tokens, drop the pre-parse barrier, and count native
  columns in code points
- Kind: Refactor
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
  - Shared docs and diagnostic catalog
- Origin: L0 Stage 1 Python lexer/parser
- Porting rule: Settle the logical recovery contract, parser emit-and-skip behavior, and barrier removal in L0 Stage 1
  first, then port the parser-visible behavior to L0 Stage 2 and seed it to L1 Stage 1 using the physical representation
  that best fits each frontend, preserving L1-only literal diagnostics (`LEX-0062` to `LEX-0068`).
- Target status:
  - L0 Stage 1: Implemented (single-wrapper token with deferred diagnostic list and optional recovery token)
  - L0 Stage 2: Implemented (queued physical lexer-error wrappers with final recovery token)
  - L1 Stage 1: Implemented (queued physical lexer-error wrappers with final recovery token)
  - Shared docs and diagnostic catalog: Implemented (ADR recorded; diagnostic catalog audited with no code changes)
- Subsystem: Lexer / Parser / Diagnostics / LSP recovery
- Modules:
  - `l0/compiler/stage1_py/l0_lexer.py`
  - `l0/compiler/stage1_py/l0_parser.py`
  - `l0/compiler/stage1_py/l0_driver.py`
  - `l0/compiler/stage2_l0/src/lexer.l0`
  - `l0/compiler/stage2_l0/src/tokens.l0`
  - `l0/compiler/stage2_l0/src/parser/shared.l0`
  - `l0/compiler/stage2_l0/src/parser/decl.l0`
  - `l0/compiler/stage2_l0/src/driver.l0`
  - `l0/compiler/stage2_l0/src/util/strings.l0`
  - `l0/compiler/stage2_l0/src/util/intset.l0` (new)
  - `l1/compiler/stage1_l0/src/lexer.l0`
  - `l1/compiler/stage1_l0/src/tokens.l0`
  - `l1/compiler/stage1_l0/src/parser/shared.l0`
  - `l1/compiler/stage1_l0/src/parser/decl.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/util/strings.l0`
  - `l1/compiler/stage1_l0/src/util/intset.l0` (new)
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Test modules:
  - `l0/compiler/stage1_py/tests/lexer/`
  - `l0/compiler/stage1_py/tests/parser/test_parser_recovery.py`
  - `l0/compiler/stage1_py/tests/integration/test_byte_type.py`
  - `l0/compiler/stage2_l0/tests/lexer_test.l0`
  - `l0/compiler/stage2_l0/tests/parser_test.l0`
  - `l0/compiler/stage2_l0/tests/lexer_error_cleanup_test.l0`
  - `l0/compiler/stage2_l0/tests/driver_test.l0`
  - `l0/compiler/stage2_l0/tests/intset_test.l0` (new)
  - `l1/compiler/stage1_l0/tests/lexer_test.l0`
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/lexer_error_cleanup_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/intset_test.l0` (new)
- Related:
  - `work/plans/bug-fixes/closed/2026-06-09-shared-lex-0040-recovery-noref.md`
  - `docs/decisions/0009-logical-lexer-error-recovery-tokens-and-codepoint-columns.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - `docs/specs/language/source-text-and-language-vocabulary.md`
- Repro:
  `./scripts/l0c -P examples --check <module with invalid characters or malformed literals and later valid syntax>`

## Summary

The previous fix (`work/plans/bug-fixes/closed/2026-06-09-shared-lex-0040-recovery-noref.md`) made the lexers recover
after invalid characters but added a phase gate that skips the parser whenever recovered lexing produced any error
diagnostic. That barrier is hostile to LSP-style use: a single stray character, unterminated string, or invalid numeric
suffix means no AST and no later diagnostics. Separately, the native lexers count columns per byte, so any multibyte
UTF-8 character in comments, string literals, or invalid-character runs inflates every later column on the same line,
diverging from the L0 Stage 1 Python oracle which lexes decoded text and counts code points.

This refactor moves lexer-error handling to a logical-token recovery model and aligns native columns with the oracle:

1. Recoverable lexer diagnostics are encapsulated in dedicated lexer-error wrapper tokens carrying the diagnostic
   payload (code, message, full start/end span) instead of being emitted inside the lexer.
2. The shared contract is parser-visible, not representationally uniform: L0 Stage 1 Python keeps one wrapper token and
   may attach a deferred diagnostic list plus an optional recovery token, while native L0 Stage 2 and L1 Stage 1
   preserve the same logical recovery by queueing one or more physical `TT_LEXER_ERROR` tokens, the final one carrying
   the recovered logical token when one exists.
3. Parser code consumes the logical token stream: it emits wrapped diagnostics exactly once (idempotent across
   backtracking), skips wrappers with no recovery token, and exposes the recovered token from the final recoverable
   wrapper.
4. The post-lexing parser barrier is removed in all three frontends. The parser always runs; downstream phases keep
   gating on accumulated error diagnostics, so files with lexer errors still never reach codegen.
5. The native lexers count diagnostic columns per code point everywhere by only bumping the column on non-continuation
   UTF-8 bytes, matching the Python oracle.

This keeps lexer diagnostics attached to exact physical source spans while preserving parse shape for incomplete or
malformed literals, which is the behavior needed by editor and LSP workflows.

## Diagnostic Routing

No new diagnostic codes are introduced; deferred diagnostics keep their numbers, messages, and `Lexer` phase attribution
even though the parser becomes the emission point. The live diagnostic catalog was checked on 2026-06-10 and the
referenced `LEX-*` code meanings were unchanged.

| Code                     | Recovery policy                                                                                                           |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| `LEX-0010`               | Wrap with recovered `STRING` using scanned partial text/value up to newline or EOF.                                       |
| `LEX-0020` / `LEX-0021`  | Wrap with recovered `BYTE`; use scanned byte when valid, otherwise `BYTE("\\0", 0)`.                                      |
| `LEX-0040`               | No-recovery wrapper covering one contiguous invalid-character run; the parser skips it logically.                         |
| `LEX-0060`               | In L0, wrap with recovered `INT(original_text, 0)` in native code and an `INT` recovery token in Python.                  |
| `LEX-0061`               | Wrap with the valid numeric prefix token and leave trailing identifier characters to be lexed normally where implemented. |
| `LEX-0062` to `LEX-0064` | In L1, wrap with recovered integer token for the valid prefix or `INT("0", 0)` when no valid digits exist.                |
| `LEX-0065` to `LEX-0068` | In L1, wrap with recovered `REALNUM` or `INT` for the valid numeric prefix.                                               |
| `LEX-0070`               | Keep direct/no-recovery behavior; block comments are trivia and have no parser-visible recovery token.                    |

Escape-sequence diagnostics (`LEX-0050` to `LEX-0054`, `LEX-0059`) inside otherwise recoverable literals are routed
through wrappers in all targeted frontends. When the same literal later terminates at newline or EOF, L0 Stage 1 Python
groups the diagnostics on one wrapper, while native L0/L1 may emit multiple physical wrappers for the same logical
literal.

## Implementation Approach

### L0 Stage 1 (origin)

1. `l0/compiler/stage1_py/l0_lexer.py`: add `TokenKind.LEXER_ERROR` with a deferred diagnostic list and optional
   recovery token on `Token`. Recoverable branches capture the offending span, build the `Diagnostic`, and return a
   wrapper instead of emitting and continuing.
2. `l0/compiler/stage1_py/l0_parser.py`: logical token access skips wrappers, appends each wrapped diagnostic to
   `self.diagnostics` at most once (per-token-index guard), and exposes the recovery token to parse decisions.
3. `l0/compiler/stage1_py/l0_driver.py`: delete the post-lexing `raise ValueError("lexing failed")` barrier.
4. `--tok` output renders the wrapper and its recovery token; the dump path does not emit deferred diagnostics.

### L0 Stage 2 (mechanical port)

1. `src/util/strings.l0`: add `utf8_seq_len(lead: byte) -> int` next to the existing UTF-8 validators.
2. `src/lexer.l0`: `ls_advance` stays byte-wise but increments `column` only for non-continuation bytes; recoverable
   branches queue `TT_LEXER_ERROR` wrappers, the final one carrying the recovery token.
3. `src/tokens.l0`: add `TT_LEXER_ERROR` with a non-recursive payload (code, message, end span, recovery token); extend
   `token_to_string` and `token_release_payload` (payload strings are ARC-managed).
4. `src/util/intset.l0` (new): `IntSet`, an open-addressing integer hash set modeled on `StringSet` in `std.hashset`,
   with an `iset_*` API; candidate for later promotion to the `std` library.
5. `src/parser/shared.l0`: `ParserState` holds an `IntSet*` of emitted token indices; logical token access (`ps_peek`
   and friends) emits via `diag_error(..., "Lexer", ...)`, skips no-recovery wrappers, and exposes recovery tokens.
6. `src/driver.l0` and `src/parser/decl.l0`: delete the `diag_has_errors` gates added by the previous fix; keep the
   `toks == null` paths for unrecoverable tokenization failures.

### L1 Stage 1 (seeded port)

Mirror the L0 Stage 2 changes in `l1/compiler/stage1_l0/src/`, including the new `util/intset.l0`, preserving L1
divergences (binary/real literal handling, `LEX-0062` to `LEX-0068` routing).

### Shared docs

Update `docs/specs/compiler/diagnostic-code-catalog.md` (wrapper-deferral emission semantics),
`l0/docs/specs/compiler/stage1-contract.md` (token model, phase flow), `l0/docs/reference/architecture.md`, and the L1
equivalents. Add a Dea-wide ADR recording the logical recovery contract, barrier removal, `Lexer` phase attribution, and
code-point columns; update `docs/decisions/INDEX.md`.

## Non-Goals

- Display-width-aware column rendering (East Asian wide characters, grapheme clusters); columns count code points.
- New diagnostic codes or message changes beyond emission-point semantics.

## Verification Criteria

- A file with invalid characters or malformed literals parses: the parser emits each deferred `LEX-*` diagnostic once
  with a code-point-accurate span, continues, and reports later genuine parser errors; downstream phases still refuse
  files with errors.
- Multibyte UTF-8 content in comments and string literals no longer skews later columns on the same line in the native
  frontends; Stage 1 and Stage 2 report identical positions for the same source.
- No duplicate deferred-diagnostic emission across parser backtracking, and no reintroduction of duplicate end-of-file
  parser diagnostics.
- ARC trace tests show no leaks from the new token payload; `make triple-test` passes.
- `../.venv/bin/python -m pytest compiler/stage1_py/tests/lexer/test_lexer.py compiler/stage1_py/tests/lexer/test_lexer_tokens.py compiler/stage1_py/tests/integration/test_byte_type.py compiler/stage1_py/tests/parser/test_parser_recovery.py`
- `make test-stage2 TESTS="lexer_test parser_test lexer_error_cleanup_test driver_test"`
- `make test-stage1 TESTS="lexer_test parser_test lexer_error_cleanup_test driver_test"` from `l1/`
- Full suites pass: `make test-stage1`, `make test-stage2`, `make test-stage2-trace`, `make check-examples`,
  `make -j test-all`, and the L1 test suite.

## Outcome

Implemented across L0 Stage 1, L0 Stage 2, and L1 Stage 1. The lexers defer recoverable diagnostics into lexer-error
wrapper tokens; the parsers emit each deferred diagnostic once at their logical token-access chokepoint (guarded by a
per-token-index `IntSet` in the native frontends), expose recovery tokens to parse decisions, and continue parsing; the
post-lexing parser gates were removed in all three frontends. Native lexers now count diagnostic columns per Unicode
code point, restoring position parity with the L0 Stage 1 Python oracle. The decision is recorded in
[docs/decisions/0009-logical-lexer-error-recovery-tokens-and-codepoint-columns.md](../../../../docs/decisions/0009-logical-lexer-error-recovery-tokens-and-codepoint-columns.md).
