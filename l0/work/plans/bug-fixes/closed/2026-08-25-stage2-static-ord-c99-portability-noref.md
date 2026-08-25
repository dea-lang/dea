# Bug Fix Plan

## Emit portable Stage 2 static ord initializers

- Date: 2026-08-25
- Status: Completed
- Title: Emit C99-portable L0 Stage 2 static `ord` initializers
- Kind: Bug Fix
- Severity: High
- Stage: 2
- Subsystem: Backend / Static initialization / C99 portability
- Modules:
  - `l0/compiler/stage2_l0/src/backend.l0`
- Test modules:
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_toplet_test.py`
- Related:
  - `l0/work/plans/bug-fixes/closed/2026-03-13-linux-c99-compatibility-noref.md`
  - `l0/work/plans/bug-fixes/closed/2026-08-23-stage2-toplet-initializer-typing-regression-noref.md`
- Repro: `L0_CC=gcc-16 DEA_BUILD_DIR=build/dea python3 l0/compiler/stage2_l0/tests/l0c_stage2_toplet_test.py`

## Summary

L0 Stage 2 lowers a static `ord(EnumVariant)` initializer through the ordinary expression path. That path constructs a
tagged-union compound literal and reads its `.tag` field. Apple Clang accepts the resulting file-scope scalar
initializer, but GCC rejects it under C99 because it is not an arithmetic constant expression.

The backend already emits direct C enum-tag constants for `case` labels and static enum constructors. Static `ord`
lowering should reuse that representation instead of materializing a compound literal.

## ADR Impact

- Decision: Lower statically known `ord` calls directly to the resolved C enum-tag constant.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The change restores the existing C99 portability contract for one incorrect backend lowering without
    changing L0 semantics, the runtime, the ABI, or compiler architecture.

## Root Cause

1. The static-initializer classifier accepts `ord` when its operand is itself a supported static initializer.
2. The static initializer emitter delegates accepted `ord` calls to ordinary call lowering.
3. Ordinary `ord` lowering emits a `.tag` read from the fully lowered enum expression.
4. A variant expression lowers to a compound literal, whose member access is not a portable C99 constant expression at
   file scope.
5. The focused backend test asserts the nonportable generated spelling, so only native compilation with GCC exposes the
   defect.

## Scope of This Fix

1. Resolve statically known bare and constructed enum variants to their direct C enum-tag constant.
2. Use the direct constant only in top-level static `ord` initialization.
3. Preserve ordinary runtime `ord` lowering for variables and other evaluated enum expressions.
4. Preserve rejection of non-static top-level `ord` operands with `ICE-1181`.
5. Replace the nonportable backend expectation and add payload-variant coverage.

## Non-Goals

1. Expanding the accepted top-level initializer language.
2. Changing Stage 1 or L1 constant evaluation.
3. Changing enum layout, tag numbering, or runtime `ord` behavior.

## Implementation Sequence

1. Add a backend helper that recognizes a statically known enum variant and emits its direct tag constant.
2. Route static `ord` calls through that helper rather than ordinary expression lowering.
3. Update focused retained-C and native CLI regressions for bare and payload variants.
4. Run focused GCC validation and the trace-independent L0 aggregate suite.

## Verification Criteria

1. `ord(None)` at file scope emits the direct `l0_<module>_<enum>_None` tag constant.
2. `ord(Some(1))` uses the direct `Some` tag constant without materializing its payload constructor.
3. `ord(choice)` for a top-level variable remains rejected before host C compilation.
4. The focused test passes with GCC under the Stage 2 C99 and pedantic flags.
5. Normal L0 validation passes without requiring the dedicated trace sweep because the change affects only pure scalar
   constant emission.

## Implementation Outcome

1. Stage 2 now resolves bare and called enum-variant operands in static `ord` initializers and emits the direct mangled
   C enum-tag constant.
2. Ordinary expression-context `ord` lowering remains unchanged, and non-static top-level operands still fail with
   `ICE-1181` before host compilation.
3. Backend retained-C coverage now requires portable direct-tag spelling for both zero-field and payload-bearing
   variants.
4. The native top-level regression checks both spellings and compiles and executes them with GCC.

## Verification Outcome

1. `L0_CC=/usr/local/bin/gcc-16 DEA_BUILD_DIR=build/dea ../.venv/bin/python compiler/stage2_l0/scripts/run_tests.py backend_test l0c_stage2_toplet_test.py`
   passed both focused tests.
2. A clean L0 build followed by `UV_CACHE_DIR=/tmp/dea-uv-cache L0_CC=/usr/local/bin/gcc-16 make test` passed 1,472
   Python Stage 1 tests, all 56 Stage 2 tests, triple bootstrap, eight examples, and all workflow and distribution
   tests.
3. The dedicated trace sweep was not required because the change only substitutes one pure scalar constant spelling and
   does not affect allocation, ownership, cleanup, runtime behavior, or trace instrumentation.
