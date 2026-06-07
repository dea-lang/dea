# Feature Plan

## `case` default arm migration to `_`, Phase 1

- Date: 2026-06-07
- Status: Closed
- Title: `case` default arm migration to `_`, Phase 1
- Kind: Feature
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - `l0`
  - `l1`
- Origin: Dangling-`else` ambiguity between an unbraced `if` arm body and the `case` default arm
- Porting rule: L0 Stage 1 (Python) is the behavioral oracle; L0 Stage 2 and L1 Stage 1 reuse identical diagnostic codes
  for equivalent conditions
- Target status:
  - `l0`: Implemented in Stage 1 (Python) and Stage 2 (self-hosted)
  - `l1`: Implemented in Stage 1 (L0-written)
- Subsystem: Lexer/Parser/AST, diagnostics, grammar docs, ADR

## Summary

The `case` statement reused the `else` keyword for its default arm. When a `case` arm body is an unbraced `if`, a
trailing `else` is grammatically ambiguous (dangling-`else` across `if` vs `case`) and a recursive-descent parser
silently attaches it to the nearest `if`, stealing the intended `case` default.

Phase 1 introduces `_ => Stmt` as the canonical default arm (mirroring `match`), deprecates the `else` default with a
warning (`PAR-0242`), and promotes the one genuinely ambiguous configuration to a hard error (`PAR-0243`) so no program
silently changes meaning while `else` lingers. `=> Stmt` arm bodies are unchanged. The `_` arm reuses the existing
wildcard token (`UNDERSCORE`/`TT_UNDERSCORE`) and the match arrow (`ARROW_MATCH`/`TT_ARROW_MATCH`); no lexer or token
additions are required. Deliberate asymmetry: `_` takes `=>`, the deprecated `else` does not.

This is Phase 1 of a two-phase migration. Phase 2 (a separate future plan) removes `else` as a `case` default entirely,
drops `PAR-0243` (no longer reachable once `_` shares no token with `if`), and mechanically rewrites the remaining
in-tree `case ... else` sites to `_ =>`.

## Diagnostics

New shared codes (registered in `docs/specs/compiler/diagnostic-code-catalog.md`):

- `PAR-0242` (warning) - deprecated `else` default arm in `case`; use `_ =>` instead. Span covers the `else` keyword.
- `PAR-0243` (error) - ambiguous `else` after `if` in a `case` value arm; brace the arm body or use a `_ =>` default.
  Emitted when an unbraced `if` *value-arm* body's then-branch is immediately followed by `else` (where the `else` could
  still be the case default). Default-arm bodies are not guarded: once the default slot is taken, a trailing `else` is
  unambiguous, so `_ => if (c) x; else y;` and `else if (c) x; else y;` stay valid.

Reworded existing codes (same numbers, generalized to cover both `_` and `else`): `PAR-0234` (value arm after the
default arm), `PAR-0236` (duplicate default arm), `PAR-0238` (expected value literal, `_`, or `else`). `PAR-0235` is
reused for a `_` default missing its `=>`; `PAR-0237` is unchanged.

## Changes Implemented

1. Grammar: both `l0/docs/reference/grammar.md` and `l1/docs/reference/grammar.md` updated to the transitional Phase 1
   form (`DefaultArm ::= WildcardArm | ElseArm`) with a disambiguation note; both `Version:` lines bumped.
2. L0 Stage 1 (`l0/compiler/stage1_py`): `l0_parser.py` accepts `_ =>` as the default, emits `PAR-0242` for `else`,
   guards the value-arm `if` body with `PAR-0243` (new `guard_dangling_else` path and `_parse_case_value_arm_body`
   helper), and adds a `_warning` emitter. `l0_diagnostics.py` registers `PAR-0242`/`PAR-0243`. No AST shape change: the
   default arm stays spelling-neutral (`CaseStmt.else_arm` / `CaseElse.body`) and the warning is emitted at parse time.
3. L0 Stage 2 (`l0/compiler/stage2_l0/src`): mirrors Stage 1 in `parser/stmt.l0` (with `ps_parse_case_value_arm_body`
   and a guarded `ps_parse_if_stmt`) and adds `ps_emit_warning` in `parser/shared.l0`. No `ast.l0` change.
4. L1 Stage 1 (`l1/compiler/stage1_l0/src`): mirrors Stage 2 in `parser/stmt.l0` and `parser/shared.l0`.
5. Catalog: `docs/specs/compiler/diagnostic-code-catalog.md` adds the two codes and rewords the generalized meanings;
   `Version:` bumped.
6. Tests: L0 Stage 1 `test_case_statement.py` and `test_diagnostic_codes.py`; L0 Stage 2 and L1 Stage 1 `parser_test.l0`
   all gain `_ =>`, `PAR-0242`, `PAR-0234`, `PAR-0235`, and `PAR-0243` coverage.
7. ADR: `docs/decisions/0007-case-default-arm-wildcard.md` records the two-phase decision; `docs/decisions/INDEX.md`
   updated. Its Related Plans link points at this plan's active path; when this plan is closed and `git mv`-ed into
   `work/plans/features/closed/`, update the ADR link to the new `closed/` path.

## Deferred to Phase 2

The in-tree `case ... else` source migration (about 95 default arms, overwhelmingly in the compilers' own `.l0` sources)
is deferred. `else` still parses and CI does not run warnings-as-errors, so the tree builds with `PAR-0242` warnings
only. Because PAR-0243 guards only value-arm `if` bodies (which use `=>`), `rg '=>\s*if\b' l0 l1` is the exact
discriminator and is empty. The stronger proof is empirical: the full L0 Stage 2 self-rebuild, `make triple-test`,
`make test-stage2`, the L1 Stage 1 build, and both `check-examples` all compile the existing ~95 `case ... else` bodies
with no PAR-0243 error, so the in-tree breakage surface is exhaustively confirmed zero.

## Verification

- `_ =>` parses as the `case` default in L0 Stage 1, L0 Stage 2, and L1 Stage 1, with identical diagnostic codes.
- `else` parses but emits `PAR-0242`; the ambiguous arm-body `if` emits `PAR-0243`; both brace/wildcard rewrites
  compile.
- L0 Stage 1 suite green (one unrelated pre-existing docgen-renderer failure); L0 `make triple-test` and
  `make test-stage2` green; L1 `make test-stage1` green (including `diagnostic_code_parity_test.py`); L0 and L1
  `check-examples` pass without warnings.

## Non-Goals

1. Phase 2 removal of `else` as a `case` default and the mass source rewrite.
2. The block-body (`=> Block`) alternative.
3. Any change to `match`, `with`, or `if` outside the `case`-arm `PAR-0243` guard.
4. New token or keyword additions.
