# Bug Fix Plan

## Shared nonscalar same-type cast pedantic C99 compatibility

- Date: 2026-04-29
- Status: Closed
- Title: Avoid pedantic-invalid C self-casts for same-type nonscalar `as` expressions across L0 and L1 backends
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Python Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: L1 Stage 1 exposed the bug under strict C99 pedantic compilation; L0 Python Stage 1 remains the shared
  backend-rule oracle
- Porting rule: Keep same-type cast lowering as a shared backend rule: implement the no-op fast path in L0 Python Stage
  1, port mechanically to L0 Stage 2, then port the homologous Stage 2 shape into L1 Stage 1
- Target status:
  - L0 Python Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Backend C codegen / cast lowering
- Modules:
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage2_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_codegen_advanced.py`
  - `l0/compiler/stage2_l0/tests/l0c_lib_test.l0`
  - `l0/compiler/stage2_l0/tests/fixtures/driver/same_type_struct_cast_main.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/fixtures/driver/same_type_struct_cast_main.l1`
- Repro:
  ```l1
  module repro;

  import std.io;

  struct Token{
      payload: string;
      offset: int;
  }

  func get(x: int) -> Token? {
      if (x % 2 == 0)
          return null;
      else
          return Token("hello", 0);
  }

  func pl(t: Token) -> string {
      return t.payload;
  }

  func main() -> int {
      let t2 : Token? = get(1);

      if (t2 != null) {
          let t3 : Token = t2 as Token;
          printl_ss("token payload is:", pl(t3 as Token));
      }
      else return 1;

      return 0;
  }
  ```

The user-visible failure was:

```text
error: [L1C-0010] C compilation failed:
temp/repro.l1:27:49: error: ISO C forbids casting nonscalar to the same type [-Wpedantic]
```

## Summary

Valid `T as T` expressions on nonscalar values such as structs lowered to raw C casts like `((struct T)(expr))`, which
`gcc` and `clang` reject under `-std=c99 -pedantic-errors`. Scalar casts were not the issue; the failure was specific to
backend fallback lowering for exact same-type nonscalar casts.

## Current State

The bug first surfaced in L1 Stage 1 with a nullable unwrap plus a same-type struct cast inside a call site. The same
generic cast-fallback shape also existed in L0 Python Stage 1 and L0 Stage 2, so the behavior was shared across all
three aligned backends.

## Root Cause

Each backend handled checked integer casts and nullable wrap/unwrap cases specially, then fell through to an
unconditional raw C cast for the remaining `as` expressions.

That meant an exact same-type nonscalar cast, where source type and destination type were already equal, emitted a
pedantic-invalid C self-cast instead of preserving the already-correct inner expression.

## Scope of This Fix

In scope:

- Add an exact same-type fast path in backend cast lowering before the generic C-cast fallback.
- Return the already-emitted inner C expression for `T as T`.
- Keep checked integer narrowing and nullable wrap/unwrap behavior unchanged.
- Add focused regressions that lock the no-self-cast invariant in generated or kept C.

Not in scope:

- Type-checker changes or new diagnostics.
- Runtime changes.
- C emitter helper changes.
- Broader cast-rule expansion beyond exact same-type no-op lowering.

## Approach

### Phase 1 — L0 Python Stage 1

Add a `src_ty == dst_ty` fast path in `CastExpr` lowering before the fallback `emit_cast(...)`, and return the already
lowered inner expression unchanged.

### Phase 2 — L0 Stage 2

Add the same `type_equals(src_ty, dst_ty)` fast path in `EX_CAST` lowering before the fallback `cem_emit_cast(...)`.

### Phase 3 — L1 Stage 1

Apply the homologous Stage 2 fast path in the L1 backend so the seeded self-hosted path matches the shared backend rule.

### Phase 4 — Regression Coverage

L0 Python Stage 1:

- Add one generated-C regression that asserts the bad struct-cast pattern is absent.
- Compile the generated C under pedantic C99 as part of the regression.

L0 Stage 2 and L1 Stage 1:

- Add one `--run --keep-c` style driver regression with `Token? -> Token` unwrap plus `t3 as Token`.
- Assert both successful execution and absence of the bad kept-C self-cast pattern.

## Verification

```bash
cd l0 && ../.venv/bin/pytest compiler/stage1_py/tests/backend/test_codegen_advanced.py -q -k same_type_struct_cast
cd l0 && make test-stage2 TESTS="l0c_lib_test"
cd l1 && make test-stage1 TESTS="l0c_lib_test backend_test"
```

## Outcome

- Implemented exact same-type nonscalar cast lowering as a no-op in L0 Python Stage 1, L0 Stage 2, and L1 Stage 1.
- Eliminated pedantic-invalid C self-casts for structs and other exact-type nonscalar casts.
- Added focused regressions for generated-C inspection and end-to-end compiler execution.

## Validation Run

Completed on 2026-04-29:

```bash
cd l0 && ../.venv/bin/pytest compiler/stage1_py/tests/backend/test_codegen_advanced.py -q -k same_type_struct_cast
cd l0 && make test-stage2 TESTS="l0c_lib_test"
cd l1 && make test-stage1 TESTS="l0c_lib_test backend_test"
```

## Assumptions

- Root shared placement is correct because the bug and fix span seeded and aligned backends across L0 and L1.
- No diagnostic-code planning is needed because no new diagnostics or diagnostic semantics were introduced.
- No roadmap or stable-doc updates are required for this closed root bug-fix history record.
