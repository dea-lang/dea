# Bug Fix Plan

## Shared C compiler invocation ordering

- Date: 2026-07-02
- Status: Completed
- Title: Place C compiler and preprocessor flags before generated C inputs while preserving link-order flags
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: `tcc` rejects compile/preprocessor options that appear after the generated C input
- Porting rule: Keep the shared driver invocation order aligned across L0 Stage 1, L0 Stage 2, and L1 Stage 1; L1 may
  retain its runtime archive and `sys.real` link-flag extensions after the generated C input.
- Target status:
  - L0 Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: CLI build driver / C compiler invocation
- Modules:
  - `l0/compiler/stage1_py/l0c.py`
  - `l0/compiler/stage2_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_l0c_assumptions.py`
  - `l0/compiler/stage2_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
- Related:
  - `l0/work/plans/features/closed/2026-03-08-l0-cflags-c-compiler-options-noref.md`
  - `l0/work/plans/features/closed/2026-03-10-stage2-build-run-driver-milestone.md`
  - `l1/work/initiatives/closed/0002-runtime-static-library.md`
- Repro: `L0_CC=tcc l0/build/dea/bin/l0c-stage2 -v --build -P l0/examples hello`

## Summary

The build drivers previously emitted generated C input paths before user C options, standard C flags, optimization
flags, and runtime include flags. That happened to work with some host compilers, but it breaks `tcc` because `tcc`
classifies several compile/preprocessor options only when they appear before the C input.

The fixed command shape is:

1. C compiler executable.
2. User and environment C option words.
3. Standard C dialect and warning flags.
4. Default optimization flag when one is selected.
5. Runtime include flags.
6. Generated C input path.
7. Output executable flags.
8. Link-time flags, including runtime library paths, runtime archives or objects, and L1 `sys.real` math-library flags.

## Root Cause

The original build-driver code treated compiler invocation words as one flat append-only sequence and inserted the
generated C input immediately after the compiler executable. Later compile/preprocessor flags were appended after that
input path. `tcc` does not reliably apply those trailing words as compile/preprocessor options, so generated programs
that need `-I`, `-D`, standard mode, or optimization flags can fail or compile with the wrong assumptions.

## Scope of This Fix

In scope:

1. Keep compile/preprocessor flags before the generated C input in L0 Stage 1, L0 Stage 2, and L1 Stage 1.
2. Keep output and linker-facing flags after the generated C input so archive/object link order remains stable.
3. Cover the order through production command assembly in the Python Stage 1 captured-command tests and through shared
   command-word helpers in the native build-driver tests.
4. Preserve L1-specific `sys.real` and runtime object/archive behavior after the generated C input.

Not in scope:

1. Adding a general user-facing linker-option surface.
2. Changing `L0_CFLAGS`, `L1_CFLAGS`, or `--c-options` tokenization.
3. Changing compiler auto-detection order.

## Outcome

The L0 Stage 1 Python driver now preserves the corrected command shape and has a captured-subprocess regression test
that asserts `tcc` sees user options, standard flags, optimization, and runtime include flags before the generated C
input. The stale Windows default-output test now checks optimization ordering relative to the generated C input instead
of relying on the obsolete final argument position.

The L0 Stage 2 and L1 Stage 1 build drivers now use shared command-word helper functions for production assembly. Their
build-driver tests exercise those helpers directly, so the tested order matches the production assembly boundary instead
of a copied sequence in the tests. L1 keeps `sys.real`, runtime archive, and tcc runtime object flags after the
generated C input.

## Verification

Completed verification:

1. `cd l0 && ../.venv/bin/python -m pytest compiler/stage1_py/tests/cli/test_l0c_assumptions.py -q`
2. `make -C l0 test-stage2 TESTS=build_driver_test`
3. `make -C l1 test-stage1 TESTS=build_driver_test`
4. `env L0_CC=tcc l0/build/dea/bin/l0c-stage2 -v --build -P l0/examples --output /tmp/dea-l0-hello-tcc hello`
5. `env L1_CC=tcc l1/build/dea/bin/l1c-stage1 -v --build -P l1/compiler/stage1_l0/tests/fixtures/driver --output /tmp/dea-l1-real-basic-tcc real_basic_main`
6. `make clean test-all`
