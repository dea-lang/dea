# Bug Fix Plan

## Stray-keyword diagnostics and statement-level recovery parity

- Date: 2026-06-07
- Status: Closed
- Title: Diagnose orphaned `else`/`cleanup` keywords and stop the Stage 2/L1 top-level recovery cascade
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L0 Stage 1 (Python) is the behavioral oracle; the self-hosted stages must reach parity
- Porting rule: Fix the Stage 1 oracle first, then port the settled logic mechanically into L0 Stage 2 and L1 Stage 1
- Target status:
  - L0 Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Parser / diagnostics / error recovery
- Modules:
  - `l0/compiler/stage1_py/l0_parser.py`, `l0_diagnostics.py`
  - `l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`, `tests/integration/` parser tests
  - `l0/compiler/stage2_l0/src/parser/stmt.l0`, `parser/shared.l0`, `tests/parser_test.l0`
  - `l1/compiler/stage1_l0/src/parser/stmt.l0`, `parser/shared.l0`, `tests/parser_test.l0`
  - `docs/specs/compiler/diagnostic-code-catalog.md`

## Problem

A stray `else` (or `cleanup`) at statement position is diagnosed poorly, and on the self-hosted compilers it triggers a
spurious top-level error. Verified by running the three built compilers on:

```
func main() -> int {
    else let hello = "Hello, World";
    printl_s(hello);
    return 0;
}
```

- L0 Stage 1 (Python): `PAR-0225` "unexpected 'else' in expression" only — recovers cleanly within the block.
- L0 Stage 2 and L1 Stage 1: `PAR-0225` **plus** a spurious `PAR-0020` "unexpected token in top level: ident(printl_s)"
  — wrong, the cursor is inside a function body. A stray `cleanup` reproduces this identically.

Two defects:

1. **Poor message.** `else` and `cleanup` are consumed only by their parent statement (`if` eats `else`, `with` eats
   `cleanup`), so an orphaned one is a clear, specific mistake, yet it surfaces as the generic `PAR-0225`.
2. **Recovery cascade (the bug).** Stage 2/L1 `ps_parse_block` parses each statement with
   `let stmt = ps_parse_stmt(self)?;`. The `?` propagates the first failure out of the block and the function, so the
   top-level loop resumes mid-body and emits `PAR-0020`. Stage 1 `_parse_block` instead wraps each statement in
   `try/except _ParseSyncException: self._sync_stmt()` and continues, so it never cascades.

These two are coupled on the self-hosted stages: even after emitting a precise `PAR-0123`/`PAR-0506`, the statement
still fails and (without per-statement recovery) still cascades to `PAR-0020`. The recovery fix is required for the new
diagnostics to land cleanly.

## Diagnostics

- `PAR-0123` — Level All — "`'else'` without a matching `'if'`". Free slot directly after the if-family
  (`PAR-0120`–`0122`).
- `PAR-0506` — Level All — "`'cleanup'` without a matching `'with'`". Free slot directly after the with-family
  (`PAR-0500`–`0505`).

Both fire only for a genuinely orphaned keyword. `if` consumes its `else` and `with` consumes its `cleanup` before
`_parse_stmt`/`ps_parse_stmt` runs, and the deprecated `case`-default `else` is consumed by `_parse_case_stmt`, so valid
`if`/`with`/`case … else` are unaffected. Per ADR-0005, all three stages reuse identical codes.

## Changes

### B1 — L0 Stage 1 (oracle), `l0/compiler/stage1_py`

- `l0_parser.py` `_parse_stmt`: at the top, `else` → `_error_bail("[PAR-0123] 'else' without matching 'if'")`, `cleanup`
  → `_error_bail("[PAR-0506] 'cleanup' without matching 'with'")`. `_parse_block`'s existing sync handling yields a
  single clean diagnostic; no recovery change needed in Stage 1.
- `l0_diagnostics.py`: register `PAR-0123`, `PAR-0506`.
- Tests: add `PAR-0123`/`PAR-0506` triggers to `tests/diagnostics/test_diagnostic_codes.py`; confirm the existing
  `PAR-0225` trigger does not rely on a bare `else`/`cleanup` (adjust if it does). Add parser tests asserting one
  diagnostic for the `else let …; <stmt>` and `cleanup let …; <stmt>` repros.

### B2 — L0 Stage 2, `l0/compiler/stage2_l0/src`

- `parser/stmt.l0` `ps_parse_stmt`: add the same two checks at the top (emit via `ps_emit_error`, return `null`).
- `parser/shared.l0`: add `ps_sync_stmt(self)` mirroring `ps_sync_top_level` (advance until a consumed `;`, or stop at
  `}` / a statement-start keyword / a top-level start / EOF).
- `parser/stmt.l0` `ps_parse_block`: replace `let stmt = ps_parse_stmt(self)?;` with a null-checked form that, on
  `null`, calls `ps_sync_stmt(self)` and continues (unwrapping the non-null `StmtId?` with `as int`); add
  `&& !ps_at_end(self)` to the loop guard and an index-based progress guard. Forward progress is guaranteed because
  statement dispatch consumes its leading keyword before any failure.
- `parser/stmt.l0` `ps_parse_return_stmt`: parse the return value *before* creating the `StmtNode`. Previously the node
  was built first and a failed expression returned via `?` leaked an arena-less node; harmless while a block aborted on
  the first error, but exposed once block-level recovery continues past it (caught by the ARC trace gate).
- Tests: `tests/parser_test.l0` add stray-`else`→`PAR-0123`, stray-`cleanup`→`PAR-0506`, and a no-cascade test.

### B3 — L1 Stage 1, `l1/compiler/stage1_l0/src`

Mirror B2 in `parser/stmt.l0` / `parser/shared.l0`; reuse identical codes; update `tests/parser_test.l0`.

### B4 — Catalog

`docs/specs/compiler/diagnostic-code-catalog.md`: add `PAR-0123` (if-family block) and `PAR-0506` (with-family block);
bump `Version:`.

## Verification

1. The `else let …; <stmt>` and `cleanup let …; <stmt>` repros each emit exactly one diagnostic (`PAR-0123` /
   `PAR-0506`) on L0 Stage 1, L0 Stage 2, and L1 Stage 1 — no `PAR-0020`, no `PAR-0225`.
2. `cd l0 && make triple-test` and `make test-stage2` pass; the block-recovery change does not regress other diagnostics
   (re-run the full Stage 2 / L1 suites; refresh any affected golden/snapshot).
3. `cd l1 && make test-stage1` passes (incl. `diagnostic_code_parity_test`); both `check-examples` clean.
4. L0 Stage 1 suite green; the new codes appear in the diagnostic-code parity matrix.
5. ARC/memory trace gates pass: `make test-stage2-trace` (L0) and `make test-stage1-trace` (L1) report zero leaks,
   confirming the `ps_parse_return_stmt` restructure closed the recovery-exposed node leak.

## Non-Goals

1. No change to `case`/`else`-as-default (that is the Phase 2 feature plan).
2. Recovery scope limited to adding `ps_sync_stmt` parity in `ps_parse_block`; other recovery paths untouched.
3. No ADR; no new tokens or keywords.
