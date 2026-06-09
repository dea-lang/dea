# Bug Fix Plan

## Shared stop parsing at EOF on block close

- Date: 2026-06-09
- Status: Completed
- Title: Stop emitting duplicate PAR-0091 by making end-of-file terminal during block close
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L0 Stage 1 (`stage1_py`) parser, parity ported to L0 Stage 2 and L1 Stage 1
- Porting rule: Fix all three compiler frontends equivalently with the same terminal-EOF state mechanism
- Target status:
  - L0 Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Parser
- Modules:
  - `l0/compiler/stage1_py/l0_parser.py`
  - `l0/compiler/stage2_l0/src/parser/stmt.l0`
  - `l0/compiler/stage2_l0/src/parser/shared.l0`
  - `l1/compiler/stage1_l0/src/parser/stmt.l0`
  - `l1/compiler/stage1_l0/src/parser/shared.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/parser/`
  - `l0/compiler/stage2_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
- Related:
  - `work/plans/bug-fixes/closed/2026-06-08-shared-parser-recovery-noref.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `printf 'module hello;\nfunc main() {{{\n' > hello.l0 && ./scripts/l0c -P . --check hello`

## Summary

A source file with unterminated nested blocks emits the same `[PAR-0091] expected '}' after block` diagnostic once per
unclosed brace instead of once. The reproducer below produces three identical lines at the same end-of-file location:

```text
module hello;
func main() {{{
```

```text
hello.l0:3:1: error: [PAR-0091] expected '}' after block, got end-of-file instead
hello.l0:3:1: error: [PAR-0091] expected '}' after block, got end-of-file instead
hello.l0:3:1: error: [PAR-0091] expected '}' after block, got end-of-file instead
```

The duplicates carry no extra information: every line points at the same end-of-file token. Once the parser reaches
end-of-file with open blocks, it should report the unterminated block once and stop, not re-report the same condition at
each enclosing nesting level.

This is a shared parser defect: the same block-parse and recovery structure exists in all three frontends. It was
reproduced through Stage 1 (`scripts/l0c`); the Stage 2 and L1 Stage 1 triple-emit is inferred from their identical
`ps_expect(self, ord(TT_RBRACE), "PAR-0091", ...)?` block-close structure and must be confirmed at implementation time.

## Root Cause

Block parsing recovers per nesting level, and end-of-file is not treated as terminal:

1. `_parse_block` (Stage 1) / `ps_parse_block` (self-hosted) loops while the current token is neither `}` nor
   end-of-file, parses statements, then calls `_expect(RBRACE)` / `ps_expect(..., TT_RBRACE, "PAR-0091", ...)`.
2. For `{{{`, each `{` opens a nested block. The innermost block exits its loop at end-of-file, then `_expect(RBRACE)`
   fails at end-of-file and emits `PAR-0091`.
3. The failure unwinds one level (a `_ParseSyncException` caught by the enclosing block's loop in Stage 1, a `null`
   return `?`-propagated in the self-hosted frontends). The enclosing block's recovery (`_sync_stmt` / `ps_sync_stmt`)
   does nothing at end-of-file, the loop condition then sees end-of-file and exits, and the enclosing block calls
   `_expect(RBRACE)` again, re-emitting `PAR-0091`.
4. With three open braces there are three enclosing block-close sites, so the same diagnostic is emitted three times.

The principled fix is to make end-of-file terminal for parsing rather than to special-case de-duplication of `PAR-0091`:
once block close fails at end-of-file, the parser is in an aborted state that every recovery loop honors by stopping.
This also covers other "nested construct unterminated at end-of-file" shapes, not only stacked braces.

## Scope of This Fix

1. Introduce a parser-level terminal/aborted state (a flag on the parser/`ParserState`).
2. Emit `PAR-0091` exactly once, on the first end-of-file-at-block-close.
3. Make all recovery loops honor the flag and stop:
   - `_parse_block` / `ps_parse_block` statement loops
   - `_sync_stmt` / `ps_sync_stmt`
   - the top-level declaration loop (`parse_program` decl loop / self-hosted equivalent)
4. Reuse the existing `PAR-0091` code and its current wording; do not change the message text.

Non-goals are listed below.

## Approach

### Mechanism (shared across all three targets)

The self-hosted frontends have no exceptions, so the only portable mechanism is a flag on `ParserState`. To keep the
three frontends structurally identical (the repo's porting rule), use the same flag mechanism in `stage1_py` rather than
introducing a new exception type that bubbles past the block handlers:

- Add a boolean such as `eof_aborted` (final name chosen at implementation time, matching local naming) to the parser
  state in each frontend.
- When block close fails specifically because the current token is end-of-file, set the flag and emit `PAR-0091` only if
  the flag was not already set.
- Guard every recovery loop condition with the flag so that once it is set, the block statement loops, the sync helpers,
  and the top-level declaration loop all stop advancing and return their partial results.
- Preserve the existing behavior of returning a partial `Module` so the driver still collects and reports the single
  diagnostic.

This keeps Stage 1 and the self-hosted frontends mechanically parallel. If implementation reveals that the Stage 1
exception-based recovery cannot cleanly honor the flag without a dedicated abort path, document the divergence
explicitly in the plan and in code comments, but keep the observable behavior identical (one `PAR-0091`).

### Per-target steps

- L0 Stage 1 (`l0/compiler/stage1_py/l0_parser.py`): add the flag to the parser; gate `_parse_block`'s loop,
  `_sync_stmt`, and the `parse_program` declaration loop; emit `PAR-0091` once at the first end-of-file block-close.
- L0 Stage 2 (`l0/compiler/stage2_l0/src/parser/stmt.l0`, `shared.l0`): add the flag to `ParserState`; gate
  `ps_parse_block`'s loop, `ps_sync_stmt`, and the top-level loop; emit `PAR-0091` once.
- L1 Stage 1 (`l1/compiler/stage1_l0/src/parser/stmt.l0`, `shared.l0`): apply the identical change as L0 Stage 2.

## Diagnostic Codes

No new or reassigned diagnostic codes. The fix reuses the existing `PAR-0091` (`expected '}' after block`) in all three
frontends and only changes how many times it is emitted. No code-block reservation is required. Confirm at
implementation time against `docs/specs/compiler/diagnostic-code-catalog.md` that `PAR-0091` is still the registered
code for this condition.

## Non-Goals

- Changing the `PAR-0091` wording or location.
- Redesigning parser error recovery beyond making end-of-file terminal.
- Adding a distinct "unterminated block at end-of-file" diagnostic code.
- Changing behavior for blocks that are closed normally or for non-end-of-file mismatches.
- Other `}` closers (`struct` and `enum` field lists, `match`/`case` bodies) are unchanged; the fix is scoped to
  statement-block close (`PAR-0091`).

## Verification Criteria

For each of the three frontends, add regression tests and confirm exact output:

1. `func main() {{{` (three unterminated blocks): previously three `PAR-0091`, must become exactly one.
2. `func main() {` (one unterminated block): must stay exactly one `PAR-0091`. This guards against over-suppression and
   against a fix that only triggers at nesting depth two or more.

Both cases must report `PAR-0091` at the end-of-file location with the unchanged message text.

Add the regression tests to:

- `l0/compiler/stage1_py/tests/parser/`
- `l0/compiler/stage2_l0/tests/parser_test.l0`
- `l1/compiler/stage1_l0/tests/parser_test.l0`

Validation commands:

- L0 Stage 1: `../.venv/bin/python -m pytest -n auto compiler/stage1_py/tests/parser`
- L0 Stage 2: `make test-stage2` (includes `triple-test`)
- L1 Stage 1: the L1 parser test entrypoint per `l1/CLAUDE.md`
- Manual: re-run the repro for both the three-brace and one-brace inputs and confirm a single `PAR-0091` line each.

## Completion Notes

The fix has been successfully implemented across all three parsers (L0 Stage 1, L0 Stage 2, L1 Stage 1) by introducing
the `eof_aborted` flag and checking it during recovery. Validation passed via `make clean test-all` from the root.
