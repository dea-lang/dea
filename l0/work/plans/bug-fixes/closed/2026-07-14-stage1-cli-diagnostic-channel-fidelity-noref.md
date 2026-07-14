# Bug Fix Plan

## Restore Stage 1 CLI diagnostic channel fidelity

- Date: 2026-07-14
- Status: Closed (fixed)
- Title: Decouple L0 Stage 1 diagnostics from configurable logging
- Kind: Bug Fix
- Severity: Medium
- Stage: 1
- Subsystem: CLI / Diagnostics / Logging
- Modules:
  - [l0/compiler/stage1_py/l0c.py](../../../../compiler/stage1_py/l0c.py)
  - [l0/compiler/stage1_py/l0_diagnostics.py](../../../../compiler/stage1_py/l0_diagnostics.py)
- Test modules:
  - [l0/compiler/stage1_py/tests/cli/test_l0c_assumptions.py](../../../../compiler/stage1_py/tests/cli/test_l0c_assumptions.py)
  - [l0/compiler/stage1_py/tests/diagnostics/test_diagnostics_reporting.py](../../../../compiler/stage1_py/tests/diagnostics/test_diagnostics_reporting.py)
  - [l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py](../../../../compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py)
- Related:
  - [l0/docs/specs/compiler/diagnostic-format.md](../../../../docs/specs/compiler/diagnostic-format.md)
  - [l0/docs/specs/compiler/cli-contract.md](../../../../docs/specs/compiler/cli-contract.md)
  - [docs/specs/compiler/diagnostic-code-catalog.md](../../../../../docs/specs/compiler/diagnostic-code-catalog.md)
  - [l0/work/plans/refactors/closed/2026-03-01-stage1-diagnostics.md](../../refactors/closed/2026-03-01-stage1-diagnostics.md)
  - [l0/work/plans/bug-fixes/closed/2026-06-05-stage2-surface-warnings-in-build-run-gen-noref.md](2026-06-05-stage2-surface-warnings-in-build-run-gen-noref.md)
- Repro: `./scripts/l0c --log --check -P compiler/stage2_l0/tests/fixtures/driver invalid_chars`

## Summary

L0 Stage 1 sends normative compiler diagnostics through the configurable logger. With `--log`, the logger decorates each
diagnostic header, source gutter, and caret line with a timestamp and `[ERROR]`, so the result no longer matches the
normative diagnostic format. Two advisory CLI diagnostics, `L0C-0013` and `L0C-0017`, are also emitted at the logger's
error level even though their text says `warning:` and the command continues successfully.

The single-module `--tok` path has a related context-routing defect: it calls the token dumper without the compilation
context. A read or decoding failure therefore prints the logger fallback line `No context provided for logging.` before
the actual coded error.

This plan separates user-facing diagnostics from operational logs, preserves their exact severity and layout under all
logging modes, and makes token-dump error routing consistent between the single-module and all-modules paths.

## Current State

- `print_diagnostic_with_snippet()` sends the diagnostic header, source line, and caret through `log_error()`. Rich log
  formatting consequently prefixes every normative line with timestamped logger metadata.
- Coded CLI errors in [l0/compiler/stage1_py/l0c.py](../../../../compiler/stage1_py/l0c.py) use the same logger path, so
  enabling `--log` changes their externally visible diagnostic syntax as well.
- `_check_entry_main_for_build()` emits `warning: [L0C-0013]` through `log_error()`. `cmd_run()` does the same for
  `warning: [L0C-0017]`, producing contradictory `[ERROR] warning:` output in rich mode.
- Replacing those calls with `log_warning()` is not sufficient: the normal Stage 1 context filters warning-level log
  records, while these compiler warnings are required to appear even without verbose logging.
- `cmd_tok()` passes the optional logging context only in the all-modules branch. The single-module branch omits it,
  exposing the logger's missing-context fallback on `L0C-0040`, `L0C-0041`, or `L0C-0042` failures.
- The diagnostic-format specification is normative, and Stage 1 remains the behavioral oracle for equivalent Stage 2
  paths. Stage 2's direct stderr printer is a parity reference for the intended channel separation.

## Root Cause

Stage 1 conflates two output channels with different contracts:

1. compiler diagnostics are mandatory, structured stderr output governed by the diagnostic-format specification; and
2. operational logs are thresholded, optionally timestamped records governed by verbosity and `--log`.

Using `log_error()` as a general stderr writer makes diagnostic rendering depend on logging policy. The token-dump
context omission then exposes an additional logger fallback that was never intended to be user-facing compiler output.

## Scope of This Fix

1. Introduce or centralize a direct Stage 1 diagnostic-emission path that writes mandatory diagnostic text to stderr
   without log thresholds, timestamps, or logger severity prefixes.
2. Route structured diagnostic headers and snippets through that path.
3. Audit coded `error:` and `warning:` emissions in the Stage 1 CLI and move normative compiler diagnostics off the
   operational logger while leaving genuine verbose/debug logging unchanged.
4. Emit `L0C-0013` and `L0C-0017` as real warning diagnostics that remain visible in default and rich-log modes.
5. Make diagnostic rendering and token-error reporting context-free so no token path can invoke the logger's
   missing-context fallback.
6. Add exact-output regressions that exercise default and `--log` behavior rather than checking diagnostic-code
   substrings only.

## Diagnostic-Code Plan

No new diagnostic assignments or catalog-document changes are expected.

- Preserve the existing `L0C-0013` and `L0C-0017` warning assignments.
- Preserve existing Stage 1 CLI error codes, including `L0C-0040`, `L0C-0041`, and `L0C-0042` in token mode.
- Add the already-cataloged `L0C-0042` to the Stage 1 in-code diagnostic registry.
- The work changes routing, formatting fidelity, and logger severity only; it does not introduce a new failure category.

## Approach

1. Add a small direct stderr diagnostic writer in the Stage 1 CLI layer. Keep it independent of
   `CompilationContext.log_level` and `CompilationContext.log_rich_format`.
2. Update `print_diagnostic_with_snippet()` so its header, source gutter, and caret are emitted exactly once and retain
   the layout specified by
   [l0/docs/specs/compiler/diagnostic-format.md](../../../../docs/specs/compiler/diagnostic-format.md).
3. Route every handwritten `L0C` diagnostic and formatted internal compiler error directly, including `L0C-0009` through
   `L0C-0014`, `L0C-0016`, `L0C-0017`, `L0C-0020`, `L0C-0030`, `L0C-0040` through `L0C-0042`, `L0C-0050`, `L0C-0060`,
   and `L0C-0070`. Keep progress logging, unsupported-compiler warnings, and raw captured C-compiler output on the
   existing logger path.
4. Represent `L0C-0013` and `L0C-0017` through the diagnostic path with lowercase `warning:` headers. Confirm both
   warnings remain non-fatal and visible at the default log level.
5. Remove diagnostic-only context plumbing from the renderer and token dumper rather than propagating a logger context
   through an output path that no longer uses logging.
6. Tighten Stage 1 tests to assert complete stderr lines, source/caret layout, absence of timestamp/logger prefixes, and
   absence of `No context provided for logging.`. Cover both default mode and `--log`, including structured analysis
   warnings and an unstructured `L0C-0042` lexer failure.

## Reproduction Matrix

Run these commands from [l0](../../../..):

1. `./scripts/l0c --log --check -P compiler/stage2_l0/tests/fixtures/driver invalid_chars` demonstrates timestamped
   `[ERROR]` prefixes on a structured diagnostic and its snippet.
2. `./scripts/l0c --log --build -P compiler/stage2_l0/tests/fixtures/driver -o /tmp/l0-stage1-cli-byte-main byte_main`
   demonstrates `[ERROR] warning: [L0C-0013]` while the build remains successful.
3. `./scripts/l0c --log --run -P compiler/stage2_l0/tests/fixtures/driver -o /tmp/l0-stage1-cli-ignored-output ok_main`
   demonstrates `[ERROR] warning: [L0C-0017]` while execution proceeds.
4. `./scripts/l0c --tok -P compiler/stage2_l0/tests/fixtures/driver read_fail` demonstrates the unintended
   `No context provided for logging.` preamble on the single-module token path.

The build repro writes its executable under `/tmp`; `--run` ignores the supplied output without `--keep-c` and uses a
temporary executable.

## Non-Goals

1. Changing diagnostic messages, codes, or documented severity assignments.
2. Redesigning the general Stage 1 verbosity or rich operational-log format.
3. Changing L0 Stage 2, whose diagnostic/output separation already supplies the intended behavior.
4. Stabilizing the developer-facing token-dump data format beyond removing the unintended logger preamble.
5. Converting every compiler diagnostic producer to a new diagnostic object model.

## Conditional L1 Follow-Up

After the L0 fix is validated, confirm L1's equivalent rich-log check, warning, and token-error paths. Current source
inspection shows L1 already prints diagnostics through `diag_print` directly to stderr and uses a diagnostic collector
in both token paths, so no L1 plan is expected. Only create the requested standalone L1 bug-fix plan if an end-to-end
repro contradicts that assessment; do not implement an L1 fix in this work item.

## Verification Criteria

- Structured diagnostics have the same normative header, source gutter, and caret text with and without `--log`.
- No diagnostic line gains a timestamp, `[ERROR]`, `[WARNING]`, or other operational-log decoration.
- `L0C-0013` and `L0C-0017` are visible as lowercase `warning:` diagnostics in default and `--log` modes, remain
  non-fatal, and never render as `[ERROR] warning:`.
- Single-module token read, UTF-8 decoding, and lexer failures contain the intended coded diagnostic and never contain
  `No context provided for logging.`.
- Genuine info/debug logging still obeys verbosity and rich-format settings.
- `L0C-0042` remains registered in the shared catalog and appears in the Stage 1 diagnostic registry.
- L1 confirmation finds no logger decoration, warning suppression, or missing-context fallback; otherwise a standalone
  L1 draft plan is created with the required roadmap entry and no L1 code changes.
- Focused Stage 1 CLI and diagnostic tests pass, followed by the normal L0 Stage 1 validation required by the
  finalization workflow.

## Outcome

Implemented the direct diagnostic channel as planned.

- Added a context-free stderr emitter for structured diagnostics, handwritten L0C diagnostics, and formatted internal
  compiler errors.
- Kept operational progress/debug output and raw captured C-compiler replay on the logger path.
- Removed diagnostic-only context plumbing from renderer and token-dump paths.
- Registered the already-cataloged L0C-0042 in the Stage 1 diagnostic registry.
- Added exact-output regression coverage for structured diagnostics, L0C-0013, L0C-0017, token failures L0C-0040 through
  L0C-0042, and retained rich info logging.

Validation completed:

- make venv
- ../.venv/bin/python -m pytest -q compiler/stage1_py/tests/cli/test_l0c_assumptions.py
  compiler/stage1_py/tests/diagnostics/test_diagnostics_reporting.py
  compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py — 302 passed.
- make test-stage1 — 1332 passed.
- Manual L0 rich-log repros confirmed clean structured errors, L0C-0013, L0C-0017, and L0C-0040 output.
- Manual L1 rich-log check, warning, and token-error repros confirmed direct stderr diagnostics without logger
  decoration or a missing-context fallback. The same defect does not apply to L1, so no L1 plan was created.
