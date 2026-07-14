# Bug Fix Plan

## Restore Stage 1 CLI diagnostic channel fidelity

- Date: 2026-07-14
- Status: Draft
- Title: Decouple L0 Stage 1 diagnostics from configurable logging and preserve CLI context
- Kind: Bug Fix
- Severity: Medium
- Stage: 1
- Subsystem: CLI / Diagnostics / Logging
- Modules:
  - [l0/compiler/stage1_py/l0c.py](../../../compiler/stage1_py/l0c.py)
- Test modules:
  - [l0/compiler/stage1_py/tests/cli/test_l0c_assumptions.py](../../../compiler/stage1_py/tests/cli/test_l0c_assumptions.py)
  - [l0/compiler/stage1_py/tests/diagnostics/test_diagnostics_reporting.py](../../../compiler/stage1_py/tests/diagnostics/test_diagnostics_reporting.py)
- Related:
  - [l0/docs/specs/compiler/diagnostic-format.md](../../../docs/specs/compiler/diagnostic-format.md)
  - [l0/docs/specs/compiler/cli-contract.md](../../../docs/specs/compiler/cli-contract.md)
  - [l0/work/plans/bug-fixes/closed/2026-06-05-stage2-surface-warnings-in-build-run-gen-noref.md](closed/2026-06-05-stage2-surface-warnings-in-build-run-gen-noref.md)
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
- Coded CLI errors in [l0/compiler/stage1_py/l0c.py](../../../compiler/stage1_py/l0c.py) use the same logger path, so
  enabling `--log` changes their externally visible diagnostic syntax as well.
- `_check_entry_main_for_build()` emits `warning: [L0C-0013]` through `log_error()`. `cmd_run()` does the same for
  `warning: [L0C-0017]`, producing contradictory `[ERROR] warning:` output in rich mode.
- Replacing those calls with `log_warning()` is not sufficient: the normal Stage 1 context filters warning-level log
  records, while these compiler warnings are required to appear even without verbose logging.
- `cmd_tok()` passes `context` to `_dump_tokens_for_file()` only in the all-modules branch. The single-module branch
  omits it, exposing the logger's missing-context fallback on `L0C-0040`, `L0C-0041`, or `L0C-0042` failures.
- L0 Stage 2 is the behavioral oracle: its diagnostic printer writes structured diagnostics directly to stderr and its
  `L0C-0013` / `L0C-0017` paths retain warning severity independently of log configuration.

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
5. Pass the active compilation context through the single-module `--tok` path and ensure no missing-context fallback is
   printed for token read, decode, or lexer failures.
6. Add exact-output regressions that exercise default and `--log` behavior rather than checking diagnostic-code
   substrings only.

## Diagnostic-Code Plan

No new diagnostic codes or catalog changes are expected.

- Preserve the existing `L0C-0013` and `L0C-0017` warning assignments.
- Preserve existing Stage 1 CLI error codes, including `L0C-0040`, `L0C-0041`, and `L0C-0042` in token mode.
- The work changes routing, formatting fidelity, and logger severity only; it does not introduce a new failure category.

## Approach

1. Add a small direct stderr diagnostic writer in the Stage 1 CLI layer, or make the existing diagnostic renderer own
   this responsibility explicitly. Keep it independent of `CompilationContext.log_level` and
   `CompilationContext.log_rich_format`.
2. Update `print_diagnostic_with_snippet()` so its header, source gutter, and caret are emitted exactly once and retain
   the layout specified by
   [l0/docs/specs/compiler/diagnostic-format.md](../../../docs/specs/compiler/diagnostic-format.md).
3. Classify every coded CLI emission in [l0/compiler/stage1_py/l0c.py](../../../compiler/stage1_py/l0c.py) as either a
   mandatory compiler diagnostic or an operational log record. Route the former directly; do not broadly change the
   behavior of `l0_logger.py` for legitimate log callers.
4. Represent `L0C-0013` and `L0C-0017` through the diagnostic path with lowercase `warning:` headers. Confirm both
   warnings remain non-fatal and visible at the default log level.
5. Pass `context=context` in the single-module `cmd_tok()` call and keep the all-modules path behavior aligned.
6. Tighten Stage 1 tests to assert complete stderr lines, source/caret layout, absence of timestamp/logger prefixes, and
   absence of `No context provided for logging.`. Cover both default mode and `--log`.

## Reproduction Matrix

Run these commands from [l0](../../..):

1. `./scripts/l0c --log --check -P compiler/stage2_l0/tests/fixtures/driver invalid_chars` demonstrates timestamped
   `[ERROR]` prefixes on a structured diagnostic and its snippet.
2. `./scripts/l0c --log --build -P compiler/stage2_l0/tests/fixtures/driver byte_main` demonstrates
   `[ERROR] warning: [L0C-0013]` while the build remains successful.
3. `./scripts/l0c --log --run -P compiler/stage2_l0/tests/fixtures/driver -o ignored-output ok_main` demonstrates
   `[ERROR] warning: [L0C-0017]` while execution proceeds.
4. `./scripts/l0c --tok -P compiler/stage2_l0/tests/fixtures/driver read_fail` demonstrates the unintended
   `No context provided for logging.` preamble on the single-module token path.

Temporary executable and C outputs from the build/run repros should be directed into a disposable directory when the
plan is implemented and verified.

## Non-Goals

1. Changing diagnostic messages, codes, or documented severity assignments.
2. Redesigning the general Stage 1 verbosity or rich operational-log format.
3. Changing L0 Stage 2, whose diagnostic/output separation already supplies the intended behavior.
4. Stabilizing the developer-facing token-dump data format beyond removing the unintended logger preamble.
5. Converting every compiler diagnostic producer to a new diagnostic object model.

## Verification Criteria

- Structured diagnostics have the same normative header, source gutter, and caret text with and without `--log`.
- No diagnostic line gains a timestamp, `[ERROR]`, `[WARNING]`, or other operational-log decoration.
- `L0C-0013` and `L0C-0017` are visible as lowercase `warning:` diagnostics in default and `--log` modes, remain
  non-fatal, and never render as `[ERROR] warning:`.
- Single-module token read, UTF-8 decoding, and lexer failures contain the intended coded diagnostic and never contain
  `No context provided for logging.`.
- Genuine info/debug logging still obeys verbosity and rich-format settings.
- Focused Stage 1 CLI and diagnostic tests pass, followed by the normal L0 Stage 1 validation required by the
  finalization workflow.
