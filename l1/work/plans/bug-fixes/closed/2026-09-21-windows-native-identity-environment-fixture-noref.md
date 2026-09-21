# Bug Fix Plan

## Stabilize the Windows native identity environment fixture

- Date: 2026-09-22
- Last reviewed: 2026-09-21
- Status: Completed
- Title: Stabilize the Windows native identity environment fixture
- Kind: Bug Fix
- Severity: Medium
- Stage: 1
- Subsystem: Native preparation identity test portability
- Modules:
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_identity_windows_environment_test.py`
- Related:
  - [l1/work/plans/refactors/closed/2026-09-15-native-identity-environment-text-reassessment-noref.md][identity-plan]
  - [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][identity-adr]
- Repro: Windows UCRT64 `test-ci` failed while checking that a changed environment reobserves native identity inputs.

## Summary

The environment fixture changed `os.environ` inside a Python process after loading the native preparation library. On
Windows, Python and the loaded C runtime can observe different environment state, so the probe-count assertion was
nondeterministic. The completed fix runs one targeted Windows memo-selection regression in fresh Python processes with
explicit startup environments, retains the broader in-process audit on POSIX, and compares component paths with platform
path semantics.

## ADR Impact

- Decision: Isolate environment-sensitive native identity tests at process startup.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs test observation and path comparison without changing native identity composition, reuse
    policy, public behavior or the architecture recorded by ADR-0039.

## Implementation

- Run the targeted Windows regression in its own test module and start its identity requests in child Python processes
  with explicit environments.
- Replace Windows environment keys case-insensitively before process creation.
- Check warm and changed-environment probe budgets independently.
- Use `PATHEXT` for Windows memo reobservation; keep broader `PATH`, header, deployment-target and loader-variable
  coverage in the existing POSIX audit.
- Compare native component paths and digest keys with `pathlib.Path` semantics.

## Verification

- `make -C l1 clean test` passed 83 Stage 1 tests, environment stackability, four examples and six Docker/Wine runner
  tests.
- The focused identity test passed on macOS with Clang and TinyCC and in Docker Linux with GCC.
- The isolated Windows startup-environment regression passed under Wine with GCC.
- Hosted Windows UCRT64 `test-ci` passed with GCC and Clang on the completed fix.

[identity-adr]: ../../../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[identity-plan]: ../../refactors/closed/2026-09-15-native-identity-environment-text-reassessment-noref.md
