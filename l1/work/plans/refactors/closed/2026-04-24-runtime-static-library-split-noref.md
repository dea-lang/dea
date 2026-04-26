# Refactor Plan

## Split the L1 runtime into a real static library

- Date: 2026-04-24
- Status: Completed
- Title: Split the L1 runtime into a real static library
- Kind: Refactor
- Severity: High
- Stage: L1
- Subsystem: Runtime / build driver / packaging / docs
- Modules:
  - `l1/compiler/shared/runtime/`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/codegen_options.l0`
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/Makefile`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/io_runtime_test.py`
  - `l1/compiler/stage1_l0/tests/math_runtime_compile_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/0002-runtime-static-library.md`
  - `l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md`
- Repro: `make -C l1 test-stage1`

## Summary

The current L1 runtime is still header-only: user-generated C includes `l1_runtime.h` and inlines runtime bodies into
the program build. Initiative `0002` requires a real runtime archive so link mechanics, traced-vs-untraced runtime
selection, and future external-library workflows can settle on a proper library model.

This refactor preserves the current language behavior while moving runtime code into `libdea_rt.a` plus a traced runtime
variant.

Severity is `High` despite the behavior-preserving nature of the change because this refactor gates Phase 2's link
mechanics: separate compilation cannot land while the runtime is still header-only-inlined into the user CU, and the
Phase 1 link model (archive linkage, trace variant selection, symbol manifest) is the de-risking surface for the Phase 3
external-library work.

## Current State

1. `compiler/shared/runtime/l1_runtime.h` still contains public declarations and implementation bodies together.
2. Build/run mode passes runtime include and library directories but does not inject a concrete archive name yet.
3. Trace behavior is compiled into the user-generated C build through preprocessor toggles.
4. There is no L1-owned runtime archive symbol manifest or installation contract yet.

## Defaults Chosen

1. The public runtime header becomes a declaration surface, not an implementation body dump.
2. Runtime code moves into one normal archive and one traced archive: `libdea_rt.a` and `libdea_rt_traced.a`.
3. Trace flag names remain user-facing as today, but archive selection moves into the build driver.
4. `dea_rt.h` is the public include name and replaces `l1_runtime.h` immediately; no compatibility bridge.
   `dea_siphash.h` stays as a distinct internal-only vendored helper, included only by runtime `.c` translation units
   and not copied to `build/dea/include/`. Anchored in Initiative 0002 §Resolved decisions.
5. This is a behavior-preserving refactor; it does not expand the L1 language surface.

## Goal

1. Split the runtime into compiled `.c` translation units plus public headers.
2. Teach the L1 build path to link against a concrete runtime archive.
3. Preserve traced and untraced runtime behavior through archive selection.
4. Update docs and packaging assumptions to the new runtime layout.

## Implementation Phases

### Phase 1: Runtime source split

Refactor the copied runtime tree into:

- public declaration headers,
- subsystem `.c` files,
- internal-only helpers that stay `static` inside implementation files.

`dea_siphash.h` stays as a distinct internal-only vendored helper, per the closed answer in Initiative 0002 §Resolved
decisions. It is included only by runtime `.c` translation units and is not part of the public install layout.

Proposed layout sketch (final subsystem decomposition is the scope of this plan's Phase 1 work; shown here so reviewers
can picture the split):

```
compiler/shared/runtime/
    include/
        dea_rt.h          (public prototypes + type definitions + macros)
    internal/
        dea_siphash.h     (internal-only vendored helper, included only by runtime .c)
    src/
        dea_rt_string.c
        dea_rt_io.c
        dea_rt_alloc.c
        dea_rt_hash.c
        dea_rt_time.c
        dea_rt_panic.c
        dea_rt_math.c

build/dea/lib/
    libdea_rt.a
    libdea_rt_traced.a

build/dea/include/
    dea_rt.h
```

Truly internal helpers stay `static` inside their respective `.c` file and are not surfaced through the public header.
The trace archive is compiled from the same sources with `DEA_TRACE_ARC` / `DEA_TRACE_MEMORY` defined.

### Phase 2: Build products and driver wiring

Add build targets that produce `libdea_rt.a` and `libdea_rt_traced.a`, then update Stage 1 build/run flows to link the
chosen archive explicitly rather than relying on header-only inclusion.

### Phase 3: Validation and packaging contract

Add symbol-manifest and smoke-test coverage for the runtime archive surface and update the L1 productization plan/docs
so the install layout reflects the new archive/header split.

## Diagnostics

1. No dedicated new diagnostic-code family is expected from this refactor.
2. Implementation should first reuse existing L1 runtime/build diagnostics such as `L1C-0014` and `L1C-0015` before
   introducing any new runtime-path or archive-discovery codes.

## Non-Goals

1. Separate compilation of user modules.
2. `.l1m` interface files.
3. New FFI syntax or semantics.
4. Release-bearing L1 distribution policy beyond the bootstrap packaging already tracked elsewhere.

## Verification Criteria

1. `make -C l1 test-stage1` still passes after the runtime split.
2. The build driver links a concrete runtime archive rather than inlining runtime implementation bodies into user C.
3. Trace and non-trace builds select the expected runtime archive deterministically.
4. Runtime archive symbols are covered by an explicit manifest or equivalent deterministic validation.

## Resolved decisions

1. Darwin tcc is not archive-compatible with the local platform toolchain in the tested setup: local tcc 0.9.28rc emits
   ELF objects while clang/cc emit Mach-O. A single official archive cannot safely serve both object formats.
2. The official runtime archives (`libdea_rt.a` and `libdea_rt_traced.a`) follow the platform compiler's object format.
   tcc consumes a parallel raw object set under `build/dea/runtime/tcc/{normal,traced}/`, linked directly by the build
   driver when the active C compiler family is tcc.
3. This preserves both goals of Initiative `0002`: the public runtime contract is real archives plus public headers, and
   the tcc carve-out does not roll generated C back to header-only runtime inclusion.
4. The traced archive keeps the stable wrapper ABI (`rt_*` / `_rt_*` wrappers forwarding to
   `_impl(..., "<runtime>", 0)`) for non-emitter consumers. Generated C in trace mode now calls
   `_rt_*_impl(..., __FILE__, __LINE__)` directly at caller sites to preserve source trace fidelity.
5. `--trace-arc` and `--trace-memory` remain allowed with `--gen`; the compiler emits a warning that callers must link
   against `libdea_rt_traced.a` or compile runtime sources with the trace defines. TODO: revisit warning versus error
   policy after a usage cycle.
6. Windows/MSYS2 does not need a host guard for the tcc object path. On that platform tcc and mingw both emit PE/COFF,
   so the direct-object path is redundant but harmless.

## Follow-ups

1. Thread `L1_BUILD_DIR` cleanly through `l1/scripts/build_stage1_l1c.py` wrapper rendering instead of relying on the
   current targeted replacement.
2. Add a Windows CI lane before claiming Windows tcc end-to-end coverage; confirm `nm` underscore normalization there.
3. Consider `DOCKER_RUNTIME_CC` only if Docker runtime-compiler override ergonomics become necessary.
