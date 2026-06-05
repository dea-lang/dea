# Bug Fix Plan

## Stage 2 surfaces compiler warnings only under --check

- Date: 2026-06-05
- Status: Closed (fixed)
- Title: Surface analysis warnings in L0 Stage 2 `--build`, `--run`, `--gen`, `--sym`, and `--type` modes to match the
  Stage 1 oracle
- Kind: Bug Fix
- Severity: Medium
- Stage: Stage 2
- Subsystem: Driver / CLI diagnostic reporting
- Modules:
  - `compiler/stage2_l0/src/build_driver.l0`
  - `compiler/stage2_l0/src/l0c_lib.l0`
- Test modules:
  - `compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `compiler/stage2_l0/tests/fixtures/driver/dup_import_main.l0`
  - `compiler/stage1_py/tests/cli/test_l0c_assumptions.py`
- Related:
  - `l0/work/plans/bug-fixes/closed/2026-06-05-duplicate-open-import-diagnostic-parity-noref.md`
- Repro:
  ```l0
  module hello;
  import std.io;
  import std.io;
  func main() { printl_s("Hello, World"); }
  ```
  `l0c --run hello` (warning swallowed); `l0c --check hello` (warning shown).

## Summary

Stage 2 printed analysis diagnostics only when there were errors, so warnings (`RES-0036`, `RES-0020/21/22`,
type-checker warnings) were silently discarded on a clean compile in every non-`check` analysis mode. Only `--check`
showed them. The user observed a duplicate `import std.io;` warning under `--check` but not under `--run` / `--build`.

Stage 1 prints diagnostics unconditionally in check/gen/sym/type/build/run (via `_run_analysis` and `cmd_build`), so
this was also a Stage 1 / Stage 2 parity defect with Stage 1 as the oracle.

## Root Cause

Four Stage 2 sites gated the diagnostic print behind the error check:

- `bd_build_to_exe` (`compiler/stage2_l0/src/build_driver.l0`) - serves `--build` and `--run`.
- `l0c_cmd_gen`, `l0c_cmd_sym`, `l0c_cmd_type` (`compiler/stage2_l0/src/l0c_lib.l0`).

Each had the shape `if (analysis_has_errors(result)) { dp_print_collector_with_sources(...); return 1; }`, printing only
on error. `l0c_cmd_check` already printed unconditionally. Diagnostics are written to stderr (`dp_print_*` uses
`err_printl_s`), so they never corrupted `--run` program stdout or `--gen` C output; they were simply dropped.

Out of scope: `--ast` and `--tok` use the parse-level `driver_*` pipeline and print only on error in both stages, so
they already matched the oracle.

## Approach

At each of the four sites, hoist the diagnostic print out of the `analysis_has_errors` guard so it runs unconditionally
(matching `l0c_cmd_check` and the Stage 1 oracle), keeping the error check only for the return code:

```
dp_print_collector_with_sources(result.diags, analysis_source_names(result), analysis_source_texts(result));
if (analysis_has_errors(result)) {
    analysis_result_free(result);
    return 1;
}
```

In `bd_build_to_exe` the print runs right after analysis, before `bd_validate_entry_main` and codegen; `validate_diags`
printing is unchanged.

## Non-Goals

- No change to which diagnostics are produced, only to when they are printed.
- No change to `--ast` / `--tok` (already parity-correct).
- No change to Stage 1 (already the correct oracle).

## Verification Criteria

- `l0c-stage2 --run` / `--build` / `--gen` on a program with a duplicate import show the `RES-0036` warning on stderr,
  keep `--run` stdout and `--gen` C output intact, and exit 0 (warning non-fatal).
- Stage 1 / Stage 2 behavior matches across check/build/run/gen/sym/type.

## Outcome

Implemented as described. Validation:

- Stage 2 `l0c_build_run_test` extended with a `dup_import_main` fixture asserting the `RES-0036` warning on stderr for
  `--run` and `--build`, correct program stdout, exit code 0, plus a `--gen` assertion (warning on stderr, C on stdout).
- Stage 1 oracle pinned with `test_build_surfaces_analysis_warning_for_duplicate_import` in `test_l0c_assumptions.py`
  (build surfaces the warning, exit 0).
- Full `make -C l0 clean test-all` (Stage 1 + Stage 2 incl. triple-bootstrap, trace suites, examples) green.
- Manual repro confirms `--run` prints `Hello, World` on stdout with the warning on stderr and exit 0.
