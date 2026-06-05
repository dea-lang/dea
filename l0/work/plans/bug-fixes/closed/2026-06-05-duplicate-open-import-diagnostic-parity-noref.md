# Bug Fix Plan

## Duplicate open import diagnostic parity (RES-0036)

- Date: 2026-06-05
- Status: Closed (fixed)
- Title: Make L0 warn once (RES-0036) on a duplicate open import instead of flooding RES-0022 and erroring TYP-0155
- Kind: Bug Fix
- Severity: Medium
- Stage: Shared
- Subsystem: Parser / Name Resolver / Stage 1 and Stage 2 diagnostic parity
- Modules:
  - `compiler/stage1_py/l0_parser.py`
  - `compiler/stage1_py/l0_name_resolver.py`
  - `compiler/stage1_py/l0_diagnostics.py`
  - `compiler/stage2_l0/src/ast.l0`
  - `compiler/stage2_l0/src/parser/decl.l0`
  - `compiler/stage2_l0/src/name_resolver.l0`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - `scripts/diagnostic_parity.py`
- Test modules:
  - `compiler/stage1_py/tests/name_resolver/test_name_resolver_module_envs.py`
  - `compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`
  - `compiler/stage2_l0/tests/name_resolver_test.l0`
  - `compiler/stage2_l0/tests/fixtures/semantics/dupimp_main.l0`
  - `compiler/stage2_l0/tests/fixtures/semantics/dupimp_dep.l0`
  - `compiler/stage2_l0/tests/diagnostic_code_parity_test.py`
- Related:
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - `l1/compiler/stage1_l0/src/name_resolver.l0`
- Repro:
  ```l0
  module hello;
  import std.io;
  import std.io;
  func main() { printl_s("Hello, World"); }
  ```
  `./build/dea/bin/l0c-stage2 --check -P <dir> hello`

## Summary

A duplicate open import (`import std.io;` twice) was handled three different ways:

- `l1c` (correct): one `[RES-0036] duplicated 'import std.io'` warning at the import line.
- `l0c` Stage 2 (self-hosted, reported): a flood of `[RES-0022]` warnings (one per symbol of the duplicated module, all
  anchored at `module ...;`) plus a bogus `[TYP-0155] ambiguous identifier` error.
- `l0c` Stage 1 (Python): silent; no warning, compiles clean.

Both L0 stages were wrong in different directions. The fix makes L0 match `l1c`: emit a single `RES-0036` warning at the
import line in both stages, with no flood and no error.

## Root Cause

When the same module is opened twice, its symbols are merged twice. Stage 2's `nr_open_imports_one` flagged every
already-present name as cross-module ambiguity (`RES-0022`) and removed it from the visible set, so the later call
became ambiguous (`TYP-0155`). Stage 1's same-symbol identity guard (`env.imported[name] is not sym`) avoided the flood
but emitted nothing. Neither stage detected the redundant import as such, and neither knew `RES-0036` (which was
registered as `L1+` only).

## Scope of This Fix

- Promote `RES-0036` from `L1+` to `All` in the shared catalog. Only `RES-0036` is promoted; `RES-0030`-`0035` remain
  `L1+` (export manifests, selective imports, and aliases do not exist in L0).
- Detect a duplicate open import at the import-loop level in both stages: track opened module names, emit a single
  `RES-0036` warning at the redundant import's span, and skip re-opening the module.
- Reuse the exact `l1` code and message text: `duplicated 'import <module>'`.

## Approach

### Stage 1 (Python)

- `_open_imports` tracks opened module names in a local set; a repeat appends a warning
  `[RES-0036] duplicated 'import <name>'` (via `diag_from_node(node=imp)`) and skips re-opening.
- The parser now gives each `Import` node a span (`_span_start` / `_extend_span`) so the warning anchors on the import
  line, matching `l1c`.
- `RES-0036` added to the `RES` family registry in `l0_diagnostics.py`.

### Stage 2 (self-hosted L0)

- `struct Import` gains a `span: Span` field, populated in `ps_parse_module`'s import loop the same way `Module`
  captures its span.
- `nr_open_imports` checks `ss_has(env.imported_modules, imp.name)` before recording the module; a duplicate emits
  `RES-0036` at `imp.span` and skips `nr_open_imports_one`.

## Non-Goals

- No change to genuine cross-module ambiguity (`RES-0022`) for the same name from two different modules.
- No change to L1, which already emitted `RES-0036` correctly.

## Verification Criteria

- `l0c` Stage 1 and Stage 2 both emit exactly one `RES-0036` at the import line for a doubled import, with no `RES-0022`
  and no `TYP-0155`, and the duplicated module's symbols remain usable.
- Stage 1 / Stage 2 diagnostic code and message parity hold (the new code and wording).

## Outcome

Implemented as described. Validation run:

- Stage 1: full `pytest compiler/stage1_py/tests` (1207 passed), including the new focused resolver test and the
  `RES-0036` trigger in `test_diagnostic_codes.py`.
- Stage 2: full `make test-stage2` (53 passed, including triple-bootstrap), the new `name_resolver_test` case, and L0 +
  L1 diagnostic code/message parity.
- `make check-examples` (Stage 2): all 8 examples pass without warnings.
- Both stages now produce a single `warning: [RES-0036] duplicated 'import std.io'` anchored at the import line,
  matching `l1c`.
