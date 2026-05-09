# Refactor Plan

## Relax null-tolerant runtime FFI pointer parameters to optional

- Date: 2026-05-09
- Status: Implemented
- Title: Relax null-tolerant runtime FFI pointer parameters to optional
- Kind: Refactor
- Severity: Low
- Stage: Shared
- Scope: Shared
- Targets:
  - `l0` stdlib / runtime / docs
  - `l1` stdlib / runtime / docs
- Origin: Shared runtime (`l0_runtime.h` and L1 `dea_rt_*` sources)
- Porting rule: Mechanical parity across L0 and L1
- Target status:
  - `l0`: Implemented
  - `l1`: Implemented
- Subsystem: Stdlib FFI / runtime docstrings / user-facing reference
- Modules:
  - `l0/compiler/shared/l0/stdlib/sys/memory.l0`
  - `l1/compiler/shared/l1/stdlib/sys/memory.l1`
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l0/docs/reference/standard-library.md`
  - `l1/docs/reference/standard-library.md`
- Related:
  - `work/plans/refactors/closed/2026-05-08-sys-memory-rename-noref.md`
- Repro: `make -C l0 check-examples && make -C l1 check-examples`

## Context

In Dea, `T*` and `T*?` lower to the same C `T*`, and `T*` widens implicitly to `T*?`. Several runtime FFI functions
already handle `NULL` as a defined, non-panicking, non-UB outcome — they short-circuit and return a sentinel result.
Their Dea-side FFI signatures over-constrained the parameter to `T*`, hiding a useful affordance and forcing callers (or
future callers) to assert non-null even when the runtime would tolerate null.

The motivating example is `rt_stdin_read`: when `buf == NULL` the runtime returns `-1`, the same error sentinel used for
any other I/O failure. Tightening the FFI signature to `byte*?` reflects the actual contract and removes a synthetic
constraint without changing runtime behavior or breaking existing callers.

## Goal

For each runtime extern that already tolerates `NULL` as a defined, sentinel-returning outcome (no UB, no panic), relax
the Dea FFI signature parameter from `T*` to `T*?`. Update the runtime header/source `Dea signature` doc strings, the
parameter `@param`/`@return` lines, and the user-facing FFI inventory tables in both `standard-library.md` files.

Functions that panic on null (`rt_array_element`, `rt_hash_data`, `rt_hash_ptr`, `rt_time_unix`, `rt_time_monotonic`) or
that would invoke C99 UB on null (`rt_string_from_byte_array` calls `memcpy` when `len > 0`) are intentionally not
relaxed.

## Targets

The relaxations land in both L0 and L1.

| Function          | Old signature                            | New signature                             | Null behaviour                  |
| ----------------- | ---------------------------------------- | ----------------------------------------- | ------------------------------- |
| `rt_realloc`      | `(ptr: void*, new_bytes: int) -> void*?` | `(ptr: void*?, new_bytes: int) -> void*?` | `NULL` `ptr` behaves like alloc |
| `rt_stdin_read`   | `(buf: byte*, capacity: int) -> int`     | `(buf: byte*?, capacity: int) -> int`     | `NULL` `buf` reports `-1`       |
| `rt_stdout_write` | `(buf: byte*, len: int) -> int`          | `(buf: byte*?, len: int) -> int`          | `NULL` `buf` reports `-1`       |
| `rt_stderr_write` | `(buf: byte*, len: int) -> int`          | `(buf: byte*?, len: int) -> int`          | `NULL` `buf` reports `-1`       |

L1 preserves the `unsafe extern func` modifier on these declarations.

## Implementation

1. **L0 stdlib** (`l0/compiler/shared/l0/stdlib/sys/memory.l0`): widen the four parameters and add a short doc note
   explaining the null-input outcome.
2. **L1 stdlib** (`l1/compiler/shared/l1/stdlib/sys/memory.l1`): mirror the L0 change, keeping the `unsafe extern func`
   prefix on each.
3. **L0 runtime header** (`l0/compiler/shared/runtime/l0_runtime.h`): update the `L0 signature: …` lines and the
   `@param`/`@return` doc lines for `rt_realloc`, `rt_stdin_read`, `rt_stdout_write`, `rt_stderr_write`. The C function
   bodies are unchanged — they already short-circuit `NULL`.
4. **L1 runtime sources** (`l1/compiler/shared/runtime/src/dea_rt_alloc.c`, `dea_rt_io.c`): update the matching
   `Dea signature: …` lines and `@param`/`@return` blocks. C bodies unchanged.
5. **User-facing docs** (`l0/docs/reference/standard-library.md`, `l1/docs/reference/standard-library.md`): rewrite the
   matching FFI inventory rows to show the new signatures and the null-input outcome.
6. **Version metadata**: both `standard-library.md` files already carry `Version: 2026-05-09`; no bump needed.

## Out of Scope

- `rt_memcpy` / `rt_memset`: relaxing inputs would force widening the return type from `void*` to `void*?`.
- `rt_memcmp`: "0 on null = equal" is misleading enough that exposing null as a valid input is undesirable.
- `rt_string_bytes_ptr` return type: empty static strings can return `NULL`; this is a separate return-side concern and
  not part of this refactor.
- Call-site simplifications in `std/io.l*` and `std/array.l*`: existing callers already pass non-null pointers, so no
  call-site change is required by this widening.

## Verification

- Type-check examples in both subtrees:
  - `make -C l0 check-examples`
  - `make -C l1 check-examples`
- Targeted L0 stage 1 pytest covering memory/stdin/stdout/stderr/realloc paths:
  - `cd l0 && ../.venv/bin/python -m pytest -x -q -k "memory or stdin or stdout or stderr or realloc" compiler/stage1_py/tests`
- Full validation when finalizing:
  - `make -C l0 -j test-all`
  - `make -C l1 test-all`
