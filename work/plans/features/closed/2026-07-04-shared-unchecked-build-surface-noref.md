# Feature Plan

## Shared unchecked build surface

- Date: 2026-07-04
- Status: Completed
- Title: Surface the unchecked runtime mode and tracker tunables through driver flags and make variables
- Kind: Feature
- Severity: Medium
- Stage: Shared
- Subsystem: CLI drivers, C backend prelude, runtime archive build, make workflow
- Scope: Shared
- Targets:
  - L0 Stage 1 Python driver and backend
  - L0 Stage 2 driver and backend
  - L1 Stage 1 driver, backend, and runtime archive build
- Origin: Follow-up recorded in the shared runtime pointer access validation plan
- Porting rule: Keep the `--unchecked` flag semantics, mode scoping, conflict policy, and diagnostic wording identical
  across the three drivers; only L1 selects a runtime archive variant.
- Target status:
  - L0 Stage 1 Python driver and backend: Done
  - L0 Stage 2 driver and backend: Done
  - L1 Stage 1 driver, backend, and runtime archive build: Done
- Modules:
  - `l0/compiler/stage1_py/l0c.py`
  - `l0/compiler/stage1_py/l0_c_emitter.py`
  - `l0/compiler/stage2_l0/src/cli_args.l0`
  - `l0/compiler/stage2_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l0/Makefile`
  - `l1/Makefile`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_cli_mode_flags.py`
  - `l0/compiler/stage1_py/tests/backend/test_codegen_semantics.py`
  - `l0/compiler/stage1_py/tests/backend/test_runtime_pointer_validation.py`
  - `l0/compiler/stage2_l0/tests/cli_args_test.l0`
  - `l0/compiler/stage2_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/io_runtime_test.py`
- Related:
  - `work/plans/features/closed/2026-06-30-shared-runtime-pointer-access-validation-noref.md`
  - `work/plans/bug-fixes/closed/2026-07-03-shared-alloc-tracker-churn-rehash-noref.md`
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`

## Summary

The unchecked runtime mode and the quarantine tunables existed only as raw C defines passed through build flags, and L1
programs could not opt out of checked mode at all because the prebuilt archive is checked-only. This plan surfaces the
release-mode opt-out recorded as follow-up in the pointer-access-validation plan: a first-class `--unchecked` driver
flag across all three compilers, an L1 unchecked runtime archive variant, and make-level variables for the tunables.

## Shared Design

- `--unchecked` is valid in `--build`, `--run`, and `--gen`, mirroring the trace flags, and is mutually exclusive with
  `--trace-arc`/`--trace-memory` (traced builds assert checked-runtime invariants and no traced-unchecked archive
  variant exists).
- L0 drivers emit `#define L0_RT_UNCHECKED 1` into the generated C prelude before the runtime include, mirroring the
  trace define emission. L1 emits `#define DEA_RT_UNCHECKED 1` so the inline per-site check fast path compiles out of
  the generated translation unit.
- The L1 driver selects `libdea_rt_unchecked.a` (or the tcc `unchecked` object variant) at the existing trace-flag
  archive selection points. `--gen --unchecked` emits a link-guidance warning, mirroring the traced `--gen` warning.
- Diagnostic codes: `L0C-2025`/`L1C-2025` (mode scope), `L0C-2026`/`L1C-2026` (trace conflict), and `L1C-0020` (`--gen`
  link guidance) are registered in the shared catalog.
- `l1/Makefile` builds the unchecked archive and tcc objects alongside the default and traced variants, and accepts
  `L1_RT_QUARANTINE_MAX_BYTES`/`L1_RT_QUARANTINE_MAX_COUNT` bake variables for the checked variants.
- `l0/Makefile` composes `L0_RT_UNCHECKED`, `L0_RT_QUARANTINE_MAX_BYTES`, and `L0_RT_QUARANTINE_MAX_COUNT` into
  `L0_CFLAGS` for `install`, `dist`, and `install-dev-stage2`; explicit user `L0_CFLAGS` still wins and the variables
  only append defines.
- Mixed configurations remain link-safe: the unchecked runtime keeps the full public symbol surface as passthrough
  stubs, so checked generated code links against unchecked archives and vice versa.

## Non-Goals

- No general release profile (optimization levels stay owned by `L0_CFLAGS`/`L1_CFLAGS`).
- No quarantine tunables as driver flags; they remain make variables, C defines, and L1 environment overrides.
- No traced-unchecked archive variant.

## Completion Notes

Completed on 2026-07-04.

- Implemented the flag in all three drivers with identical wording, mode scoping, and conflict diagnostics, plus the L1
  archive variant and make-level knobs.
- Tests cover flag parsing, mode scoping, conflict rejection, prelude define emission, L1 archive and tcc variant
  selection, the `--gen` link-guidance warning, and a behavioral `--unchecked` run through the L1 driver.
- Documented the surface in the L0 CLI contract, the shared diagnostic-code catalog, level reference docs, and ADR-0010.

## Verification Criteria

- `l0c`/`l1c` `--run --unchecked` build and run valid programs; generated C carries the mode define; L1 links the
  unchecked archive (visible with `-vvv`).
- `--unchecked` outside `--build`/`--run`/`--gen` and combined with trace flags fails with the registered diagnostics in
  all three drivers.
- `make -C l1 runtime` produces `libdea_rt.a`, `libdea_rt_traced.a`, and `libdea_rt_unchecked.a`.
- `make -C l0 install`/`dist`/`install-dev-stage2` compose the tuning defines into `L0_CFLAGS`.
- Full `make -C l0 test-all` and `make -C l1 test-all` suites pass.
