# Refactor Plan

## Re-split L1 runtime CUs to match thematic boundaries

- Date: 2026-04-27
- Status: Completed
- Title: Re-split L1 runtime CUs to match thematic boundaries
- Kind: Refactor
- Severity: Low
- Stage: L1
- Subsystem: Runtime
- Modules:
  - `l1/compiler/shared/runtime/src/dea_rt_panic.c`
  - `l1/compiler/shared/runtime/src/dea_rt_math.c`
  - `l1/compiler/shared/runtime/src/dea_rt_sys.c` (new)
  - `l1/compiler/shared/runtime/src/dea_rt_rand.c` (new)
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/Makefile`
- Test modules:
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/io_runtime_test.py`
  - `l1/compiler/stage1_l0/tests/math_runtime_compile_test.l0`
- Related:
  - [2026-04-24-runtime-static-library-split-noref](../refactors/closed/2026-04-24-runtime-static-library-split-noref.md)
  - [0002-runtime-static-library](../../initiatives/closed/0002-runtime-static-library.md)
- Repro: `make -C l1 test-stage1`

## Summary

The closed runtime static-library split landed seven runtime CUs (`string`, `io`, `alloc`, `hash`, `time`, `panic`,
`math`). Two of those CUs ended up carrying functions that don't fit their stated theme:

- `dea_rt_panic.c` carries panic + unwrap, *plus* `rt_system`, `rt_get_pid`/`_rt_pid_to_dea_int`, `rt_get_env_var`, argv
  handling (`_rt_init_args`, `rt_get_argc`, `rt_get_argv`), `rt_abort`, `rt_exit`, and `rt_errno` — six unrelated
  OS/process concerns living under "panic".
- `dea_rt_math.c` carries arithmetic overflow checks + narrowing + casts, *plus* `rt_srand` / `rt_rand` — RNG has
  nothing to do with safe integer arithmetic.

This refactor carves the mismatched groups into two new CUs (`dea_rt_sys.c`, `dea_rt_rand.c`) and trims the originals
back to their intended themes. It is purely a source-organization change: no public API changes, no symbol-set changes,
no behavior changes. The runtime archives (`libdea_rt.a` and `libdea_rt_traced.a`) end up with the same exported symbol
set, sourced from a cleaner CU layout.

Severity is `Low` because the change is behavior-preserving, contained to runtime sources, and does not gate any
downstream initiative work. The other five CUs (`string`, `io`, `alloc`, `hash`, `time`) hold together thematically and
are out of scope.

## Current State

1. `dea_rt_panic.c` defines: `_rt_panic`, `_rt_panic_fmt`, `_unwrap_ptr`, `_unwrap_opt`, `rt_abort`, `_rt_init_args`,
   `rt_get_argc`, `rt_get_argv`, `rt_get_env_var`, `rt_system`, `rt_get_pid`, `_rt_pid_to_dea_int`, `rt_exit`,
   `rt_errno`.
2. `dea_rt_math.c` defines safe arithmetic (`_rt_iadd/sub/mul/div/mod` and their `u*`/`l*`/`ul*` variants), narrowing
   (`_rt_narrow_*`), checked casts (`_rt_cast_*_from_signed/unsigned`), and the RNG entry points `rt_srand` / `rt_rand`.
3. The public header `dea_rt.h` lists declarations sequentially; the source-side CU split is invisible to consumers, so
   this refactor does not alter any consumer include or link.

## Goal

1. Carve OS/process functions out of `dea_rt_panic.c` into a new `dea_rt_sys.c`.
2. Carve `rt_srand` and `rt_rand` out of `dea_rt_math.c` into a new `dea_rt_rand.c`.
3. Leave the trimmed `dea_rt_panic.c` as failure-path only (`_rt_panic`, `_rt_panic_fmt`, `_unwrap_ptr`, `_unwrap_opt`,
   `rt_abort`).
4. Leave the trimmed `dea_rt_math.c` as numeric arithmetic + narrowing + casts only.

## Defaults Chosen

1. New CU name `dea_rt_sys.c` — consistent with the existing `dea_sys_*` Dea-side prefix and broad enough to cover shell
   exec, process id, env vars, args, exit, and errno without overspecific naming.
2. New CU name `dea_rt_rand.c` — RNG only.
3. `_rt_narrow_*` and `_rt_cast_*_from_signed/unsigned` stay in `dea_rt_math.c`. Both groups operate on integers and
   panic on overflow; the seam between checked arithmetic and checked narrowing/casts is weaker than the seam between
   panic/sys or arithmetic/rng. Splitting casts off is rejected as over-fragmentation for this refactor.
4. `rt_abort` stays in `dea_rt_panic.c` because it is the public abort wrapper that calls `_rt_panic` / `_rt_panic_fmt`;
   it is a panic concern, not a process concern.
5. Public header is reorganized cosmetically only (banner comments / decl clustering). No symbol additions, removals, or
   renames.

## Implementation Phases

### Phase 1: Source carve-out

1. Create `l1/compiler/shared/runtime/src/dea_rt_sys.c`, including `../include/dea_rt.h` like its siblings, and move the
   OS/process functions listed under "Current State" item 1 (excluding the panic/unwrap/abort group).
2. Create `l1/compiler/shared/runtime/src/dea_rt_rand.c` and move `rt_srand` and `rt_rand`.
3. Remove the moved blocks from `dea_rt_panic.c` and `dea_rt_math.c`. Leave their banner comments and headers consistent
   with the trimmed scope.

### Phase 2: Build wiring

1. Inspect `l1/Makefile` to determine whether the runtime archive build enumerates `.c` sources via a wildcard or as an
   explicit list. If explicit, add `dea_rt_sys.c` and `dea_rt_rand.c`.
2. Apply the same check to the tcc raw-object lane under `build/dea/runtime/tcc/{normal,traced}/` driven by the same
   build system; update any explicit source list there too.
3. Confirm both the platform-cc and tcc archive paths still build cleanly.

### Phase 3: Header tidy and validation

1. Cluster the sys and rand declarations in `dea_rt.h` under their own banner comments to mirror the new source layout.
   Strictly cosmetic — no signature changes.
2. Run `nm` against `libdea_rt.a` before and after the refactor; sorted symbol lists must be identical (modulo the
   `.o`-file column). Same check for the traced archive.
3. Re-run the runtime archive symbol manifest validation deliverable from the closed library-split plan; it must match
   unchanged.

## Diagnostics

1. No new diagnostics. This refactor does not touch the compiler diagnostic surface, the runtime panic-message surface,
   or any user-facing error path.

## Non-Goals

1. No changes to the public function set, signatures, or `dea_rt.h` type surface.
2. No changes to traced vs. untraced archive selection or build-driver wiring.
3. No splits in `dea_rt_io.c`, `dea_rt_alloc.c`, `dea_rt_string.c`, `dea_rt_hash.c`, or `dea_rt_time.c`, even though
   `dea_rt_io.c` mixes file/stream/print and `dea_rt_alloc.c` mixes alloc/memops/refcount-table.
4. No splitting `_rt_narrow_*` and `_rt_cast_*` off `dea_rt_math.c`.
5. No reorganization of internal-only `internal/dea_siphash.h` or its usage.

## Verification Criteria

1. `make -C l1 test-stage1` passes.
2. `make -C l1 test-stage1-trace` passes — confirms the traced archive variant rebuilt from the new CU layout still
   links and runs.
3. `nm build/dea/lib/libdea_rt.a | sort` yields the same symbol set before and after the refactor (modulo `.o`-file
   column). Same check for `libdea_rt_traced.a`.
4. The runtime archive symbol manifest from the closed library-split plan continues to validate unchanged.
5. Spot-check tcc lane: a Stage 1 test run with the tcc C compiler still passes.
