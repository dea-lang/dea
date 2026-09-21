# Refactor Plan

## Re-evaluate raw environment text in the L1 native preparation identity

- Date: 2026-09-22
- Last reviewed: 2026-09-21
- Status: Completed
- Title: Re-evaluate raw environment text membership in the native preparation identity
- Kind: Refactor
- Severity: Medium
- Stage: 1
- Subsystem: Native preparation identity, environment selection and warm reuse eligibility
- Modules:
  - `l1/compiler/stage1_l0/support/preparation/identity.h`
  - `l1/compiler/stage1_l0/support/preparation/storage.h`
  - `l1/compiler/stage1_l0/src/preparation.l0`
- Test modules:
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_ownership_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_managed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_preparation_test.py`
- Related:
  - [l1/work/plans/features/closed/2026-09-13-warm-preparation-validation-reuse-noref.md][warm-plan]
  - [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][identity-adr]
  - [l1/docs/decisions/0040-warm-preparation-semantic-validation-reuse.md][reuse-adr]
  - [l1/docs/reference/stdlib-preparation.md][preparation]
- Repro: A completed native profile formerly missed under `--no-auto-prepare` when only irrelevant `PATH` spelling
  changed.

## Summary

Raw environment text now selects the observation memo without entering native identity `N`. Equivalent environments
therefore share a completed profile, while fresh observations, live-directory validation, component digests and existing
decline rules still detect meaningful toolchain changes.

## ADR Impact

- Decision: Change the native identity composition so environment text no longer changes `N` when resolved toolchain
  observations and inputs are unchanged.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: ADR-0039 records the settled memo-only environment boundary, independent runtime-target evidence and
    retained conservative refusal rules.

## Outcome

- Removed the raw environment copy from `N` while retaining it in memo selection and directory revalidation.
- Added independent runtime target-macro evidence so application defines cannot hide environment-selected runtime
  targets; older incomplete observation memos are reobserved.
- Preserved `darwin_os_build` as explicit evidence for macOS shared-cache system libraries.
- Kept the existing loader and driver refusal boundary. No new decline-only variable, persistent store, public CLI
  surface, profile migration or diagnostic code was required.
- Added regressions for equivalent environment reuse, tool shadowing, stale memos, header search changes, deployment
  targets and native launcher behavior without relocating installed Windows toolchains.

## Audit Result

| Inputs                                                                          | Final treatment            | Effective evidence                                                       |
| ------------------------------------------------------------------------------- | -------------------------- | ------------------------------------------------------------------------ |
| `PATH`, `PATHEXT`                                                               | Memo-only                  | Resolved invocations, component digests and live search directories      |
| `CPATH`, `C_INCLUDE_PATH`, `CPLUS_INCLUDE_PATH`                                 | Memo-only                  | Selected headers, dependency digests and shadow-directory checks         |
| `LIBRARY_PATH`, `COMPILER_PATH`, `GCC_EXEC_PREFIX`, `TCCDIR`                    | Memo-only                  | Reported tools, support roots, search directories and component digests  |
| `SDKROOT`, `DEVELOPER_DIR`, Clang config directories, `HOME`, `XDG_CONFIG_HOME` | Memo-only                  | Effective SDK/config observations, selected files and live directories   |
| `MACOSX_DEPLOYMENT_TARGET`                                                      | Additional observation     | Independent generated-C and runtime target-macro digests                 |
| `LD_LIBRARY_PATH`                                                               | Memo-only                  | Implementation-library closure, loader directories and component digests |
| `LD_PRELOAD`, `LD_AUDIT`, `CCC_OVERRIDE_OPTIONS`, nonempty `DYLD_*`             | Decline reuse              | Existing refusal before memo lookup                                      |
| `darwin_os_build`                                                               | Explicit identity evidence | macOS build identifier outside the removed environment object            |

## Verification

- `make -C l1 test` passed 82 Stage 1 tests, environment stackability, four examples and six Docker/Wine runner tests.
- `make -C l1 test-stage1-trace` passed all 46 default trace tests with no reported object or string leaks.
- Focused identity and managed-preparation tests passed on macOS with Clang and TinyCC and in Docker with GCC;
  capability reports for all three compilers confirmed zero warm native builds and zero repeated umbrella analyses.
- Hosted Windows UCRT64 `test-ci` passed with GCC and Clang on the final tree, including the preparation capability
  report.
- Steady-state managed overhead measured 0.231 seconds against the 0.36-second budget. Interleaved cold medians were
  23.195 seconds before and 22.997 seconds after, with overlapping ranges and no observed regression.

## Non-Goals

- Cross-host cache portability or authentication.
- Changes to `D`, warm-manifest semantic evidence or ADR-0040.
- Guarantees for concurrent external mutation or unsupported compiler indirection.

[identity-adr]: ../../../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[preparation]: ../../../../docs/reference/stdlib-preparation.md
[reuse-adr]: ../../../../docs/decisions/0040-warm-preparation-semantic-validation-reuse.md
[warm-plan]: ../../features/closed/2026-09-13-warm-preparation-validation-reuse-noref.md
