# Feature Plan

## Shared compiler runtime quarantine default

- Date: 2026-07-05
- Status: Completed
- Title: Build distributed and developer compiler binaries with the performance-sensitive checked-runtime quarantine
  count
- Kind: Feature
- Severity: Medium
- Stage: Shared
- Subsystem: Runtime pointer validation, compiler build workflows, L1 unsafe pointer docs
- Scope: Shared
- Targets:
  - L0 Stage 2 developer, install-prefix, distribution, and triple-bootstrap compiler builds
  - L1 Stage 1 developer compiler build
  - L1 unsafe raw-pointer reference documentation
- Origin: Shared runtime pointer validation default discussion
- Porting rule: Keep user-program runtime defaults unchanged while applying the compiler-binary build setting through
  each level's existing compiler build path.
- Target status:
  - L0 Stage 2 developer, install-prefix, distribution, and triple-bootstrap compiler builds: Done
  - L1 Stage 1 developer compiler build: Done
  - L1 unsafe raw-pointer reference documentation: Done
- Modules:
  - `l0/Makefile`
  - `l0/scripts/build_stage2_l0c.py`
  - `l0/scripts/gen_dist_tools.py`
  - `l1/Makefile`
  - `l1/scripts/build_stage1_l1c.py`
  - `l1/docs/reference/design-decisions.md`
- Test modules:
  - `l0/tests/test_make_dist_workflow.py`
  - `l0/compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py`
- Related:
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
  - `work/plans/features/closed/2026-07-04-shared-runtime-alloc-benchmark-noref.md`
  - `work/plans/features/closed/2026-07-04-shared-unchecked-build-surface-noref.md`

## Summary

Checked runtime pointer validation remains the default Dea semantics, but the compiler binaries themselves are
allocation-heavy enough to use the documented performance-sensitive quarantine count. This work applies
`_RT_QUARANTINE_MAX_COUNT=256` only when building L0/L1 compiler executables. Programs built by those compilers and L1
runtime archives keep the checked-runtime default of `4096` unless users explicitly retune them.

## Implementation

- Add compiler-build-only quarantine count variables for L0 and L1, defaulting to `256` and allowing an empty value to
  disable the compiler-build default.
- Apply the setting inside the Python compiler build scripts so direct script invocation and Makefile workflows behave
  consistently.
- Preserve explicit user control: an existing `-D_RT_QUARANTINE_MAX_COUNT=...` in `L0_CFLAGS` or an explicit runtime
  quarantine variable takes precedence over the compiler-build default.
- Clarify L1 raw-pointer docs so `unsafe func` is a source-level proof boundary, while checked builds may still provide
  dynamic pointer validation and `--unchecked` builds lower directly.

## Non-Goals

- No rename of `--unchecked`.
- No change to the default quarantine count for user programs or L1 runtime archives.
- No new compiler diagnostic codes.

## Completion Notes

Completed on 2026-07-05.

- L0 developer, install-prefix, distribution, and triple-bootstrap compiler builds now receive the compiler-only
  quarantine count unless explicitly overridden.
- L1 Stage 1 compiler builds receive the compiler-only quarantine count through the upstream L0 build environment,
  without changing L1 runtime archive defaults.
- L1 reference and decision docs now distinguish source-level unsafe contracts from checked-runtime diagnostics.

## Verification Criteria

- `make -C l0 test-dist` shows distributed compiler builds using `_RT_QUARANTINE_MAX_COUNT=256` and compiled user
  programs still run through normal defaults.
- `make -C l0 triple-test` builds all self-hosted compiler stages with matching compiler-build C flags.
- `make -C l1 build-stage1` builds the L1 compiler with the compiler-only quarantine count while runtime archive
  defaults remain controlled by `L1_RT_QUARANTINE_MAX_COUNT`.
