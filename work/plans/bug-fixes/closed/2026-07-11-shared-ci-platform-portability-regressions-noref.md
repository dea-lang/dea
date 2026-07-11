# Bug Fix Plan

## Shared CI platform portability regressions

- Date: 2026-07-11
- Status: Completed
- Title: Restore strict C initializer and Apple Silicon bootstrap portability in CI
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Stage 2 triple-bootstrap validation
  - L1 Stage 1 C backend
- Origin: Unified CI failures on GCC 16 and macOS Apple Silicon
- Porting rule: Keep each platform correction local to its owning target; no mechanical cross-level port is required.
- Target status:
  - L0 Stage 2 triple-bootstrap validation: Implemented
  - L1 Stage 1 C backend: Implemented
- Subsystem: C backend static initialization and native bootstrap reproducibility
- Modules:
  - `l0/compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py`
  - `l1/compiler/stage1_l0/src/backend.l0`
- Test modules:
  - `l0/compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_toplet_test.py`
- Repro: Unified CI on Ubuntu or Windows with GCC 16 and on macOS Apple Silicon with Clang

## Summary

Two portability defects prevent the unified suite from passing on newer CI hosts. L1 emits a compound-literal expression
for a file-scope fixed-array initializer, which strict GCC rejects as non-constant. The L0 triple-bootstrap test also
suppresses the Mach-O UUID and ad hoc signature on every Darwin host, producing an executable that the Apple Silicon
loader refuses to launch.

## Root Cause

The L1 backend shares one fixed-array lowering form between block-scope expressions and file-scope declarations even
though file-scope C requires initializer syntax rather than a compound-literal expression. The bootstrap test applies
Intel-compatible linker normalization flags without accounting for Apple Silicon loader requirements.

## Scope of This Fix

1. Emit direct brace initialization for file-scope L1 fixed arrays while retaining compound literals in expression
   contexts.
2. Cover the const string-array regression in the end-to-end top-level binding test.
3. Preserve Darwin UUID and signing load commands on Apple Silicon while retaining the existing Intel normalization.

## Non-Goals

- Changes to L1 fixed-array language semantics.
- Changes to normal L0 compiler build flags outside strict triple-bootstrap validation.
- New diagnostics.

## Verification Criteria

- The L1 top-level binding regression executes and its generated declaration uses a direct brace initializer.
- Focused L1 Stage 1 backend and top-level binding tests pass.
- The L0 triple-bootstrap test passes on the local Intel macOS host.
- Unified CI can execute the first self-hosted compiler on Apple Silicon and compile the L1 fixture with strict GCC.

## Outcome

- Added a dedicated file-scope fixed-array initializer path that lowers both the wrapper and managed leaf values as C
  constant initializers.
- Retained the existing compound-literal path for block-scope and other expression contexts.
- Kept Mach-O UUID and ad hoc signature generation enabled on Apple Silicon while preserving the Intel Darwin
  reproducibility flags.
- Strengthened the L1 top-level regression with an assertion covering the exact generated declaration form.

## Verification

```bash
cd l1 && L1_CC=gcc-16 make test-stage1 TESTS="backend_test l1c_stage1_toplet_test.py"
cd l0 && make triple-test
git diff --check
```
