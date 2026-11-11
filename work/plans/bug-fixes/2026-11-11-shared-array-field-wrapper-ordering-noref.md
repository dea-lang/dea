# Bug Fix Plan

## Emit fixed-array wrappers before aggregate value fields

- Date: 2026-11-11
- Status: Draft
- Title: Emit fixed-array wrappers before aggregate value fields
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Targets:
  - L1 canonical compiler
  - L2 canonical compiler
- Origin: L1 generated-C failure for a struct containing a builtin fixed-size array
- Porting rule: Repair dependency ordering in L1 and transfer the repair to the seeded L2 backend, preserving each
  level's owned implementation and tests.
- Target status:
  - L1 canonical compiler: Pending
  - L2 canonical compiler: Pending
- Subsystem: C backend type-definition ordering
- Modules:
  - `l1/compiler/src/backend/output.l0`
  - `l1/compiler/src/backend/types.l0`
  - `l1/compiler/src/c_emitter/declarations.l0`
  - `l1/compiler/src/c_emitter/wrappers.l0`
  - `l2/compiler/src/backend/output.l1`
  - `l2/compiler/src/backend/types.l1`
  - `l2/compiler/src/c_emitter/declarations.l1`
  - `l2/compiler/src/c_emitter/wrappers.l1`
- Test modules:
  - `l1/compiler/tests/backend_test.l0`
  - `l1/compiler/tests/l1c_compile_only_test.py`
  - `l2/compiler/tests/backend_test.l1`
  - `l2/compiler/tests/l2c_compile_only_test.py`
- Related:
  - [l1/docs/reference/design-decisions.md][array-contract]
  - [l1/work/plans/bug-fixes/closed/2026-10-29-borrowed-slice-escape-noref.md][slice-plan]
  - [work/plans/bug-fixes/closed/2026-09-11-shared-arc-comparison-temporary-cleanup-noref.md][arc-plan]
- Repro: Generate and compile the exported `Box { ram: byte[2]; }` module below.

## Summary

A valid struct with a builtin fixed-size array field is accepted but emits C that uses the array-wrapper typedef before
its definition. Native compilation fails with an unknown-type diagnostic. Severity is High because an ordinary,
documented value layout cannot be compiled; replacing the field with a pointer changes storage and ownership semantics.

The L1 defect is reproduced independently on current sources. L2 contains the same emission sequence and is included as
a seeded implementation target; its executable reproduction remains pending. L0 does not support these source-level
fixed-array types and is outside this report. This document records a confirmed defect and proposed correction only.

## ADR Impact

- Decision: Preserve supported fixed-array value layouts through dependency-correct C emission.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs ordering in the existing C representation without changing language semantics, ABI layout,
    ownership rules, or the compiler architecture.

## Reproduction

Use a canonical L1 compiler built from the sources under examination. From `l1/`, set `L1C` to that executable and run
this macOS reproduction; all generated files stay in a temporary directory:

```sh
ARRAY_REPRO="$(mktemp -d "${TMPDIR:-/tmp}/dea-array-field.XXXXXX")"
ARRAY_CC="$(xcrun --find clang)"
ARRAY_SDK="$(xcrun --sdk macosx --show-sdk-path)"
export L1_HOME="$PWD/compiler"
export L1_BUILD_DIR="$ARRAY_REPRO/build"
mkdir -p "$L1_BUILD_DIR"
cat > "$ARRAY_REPRO/array_field.l1" <<'SOURCE'
module array_field;
export Box;
struct Box {
    ram: byte[2];
}
SOURCE
"$L1C" --gen --no-managed-stdlib --project-root "$ARRAY_REPRO" \
  -o "$ARRAY_REPRO/array_field.c" array_field
"$ARRAY_CC" -std=c99 -isysroot "$ARRAY_SDK" \
  -I"$PWD/compiler/shared/runtime/include" \
  -c "$ARRAY_REPRO/array_field.c" -o "$ARRAY_REPRO/array_field.o"
```

Expected: both commands succeed and the wrapper is completely defined before the struct field uses it by value. Actual:
generation succeeds, then Clang rejects `__deaA2_h` as an unknown type. The generated order is:

```c
struct __deaM11array_fieldS3Box {
    __deaA2_h ram;
};
/* Later in the same translation unit. */
typedef struct __deaA2_h { dea_byte data[2]; } __deaA2_h;
```

## Verification evidence and limits

- Verified on 2026-11-11 on macOS x86_64 with a fresh L1 build from current sources and the explicit L0 Stage 2
  bootstrap. The host C compiler was
  `/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang`, Apple Clang 17.0.0
  (`clang-1700.6.4.2`), with the macOS 26.2 SDK.

- `--gen` exited 0. The independent C99 compile exited 1 with `unknown type name '__deaA2_h'` at generated line 18; the
  wrapper definition occurred at line 25.

- The equivalent `--compile` command exited 1 with `L1C-0010` and the same native compiler diagnostic:

  ```sh
  "$L1C" --compile --no-managed-stdlib --project-root "$ARRAY_REPRO" \
    --c-compiler "$ARRAY_CC" --c-options="-isysroot \"$ARRAY_SDK\"" \
    --runtime-include "$PWD/compiler/shared/runtime/include" \
    -o "$ARRAY_REPRO/array_driver.o" array_field
  ```

- L2 source inspection confirms identical `be_generate_output` ordering and matching array-wrapper and nominal-type
  dependency paths. No fresh L2 executable probe was run; confirm with an L2-owned `.l2` fixture during correction.

- No compiler implementation changed and no aggregate suite was run. Linux, Windows, and macOS ARM execution are
  unverified by this report.

## Cause and proposed scope

`be_generate_output` emits nominal definitions before its general array-wrapper pass. `cem_emit_struct_info` writes each
field's C type directly without first arranging its wrapper dependencies. The nominal-type ordering pass emits array
wrappers immediately after their nominal element type is defined, but builtin array elements never take that path. The
same paths are present in L2.

The existing tests exercise arrays of nominal elements, local builtin arrays, and generated-text fragments. Those cases
do not establish that a builtin array stored inside a nominal value compiles. Earlier closed plans already record this
declaration-order limitation separately from their completed ownership repairs.

1. Arrange wrapper and nominal definitions according to complete-type and typedef dependencies before each use.
2. Preserve the existing array-of-nominal ordering: globally moving all arrays before nominal definitions is
   insufficient.
3. Add independently owned compile-through regressions in L1 and L2, along with focused backend ordering coverage.

No new compiler diagnostic code is expected: valid programs should compile, and the native compiler failure is a symptom
rather than a new source-language error. Broader callable/slice declaration-order defects mentioned by the related plans
are not claimed as independently reproduced by this report.

## Acceptance criteria

- The minimal module succeeds through both `--gen` followed by C99 compilation and `--compile` in each target level.
- A constructed struct with a builtin array field supports element writes and reads with the expected result.
- Cover primitive and nominal element types, nested nominal dependencies, multidimensional arrays, and supported enum
  payload combinations; distinguish any newly discovered failures from this confirmed minimal case.
- Preserve existing optional/pointer wrapper ordering, nominal-array layouts, ARC ownership behavior, and deterministic
  per-module C output.
- Run the focused backend and compile-only suites for each target and appropriate native regression coverage. Record
  native-platform coverage separately from unexecuted platforms.

[arc-plan]: closed/2026-09-11-shared-arc-comparison-temporary-cleanup-noref.md
[array-contract]: ../../../l1/docs/reference/design-decisions.md#71-fixed-size-array-policy
[slice-plan]: ../../../l1/work/plans/bug-fixes/closed/2026-10-29-borrowed-slice-escape-noref.md
