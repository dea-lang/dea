# L1 Initiative 0002 - L1 Runtime Library

- Version: 2026-04-25
- Status: Active
- Kind: Initiative

## Summary

This initiative moves the L1 runtime from a header-only inclusion model into a real static library with a public header
surface and a separate traced variant. It is a behavior-preserving infrastructure change: no language semantics move, no
FFI surface expands, no source-level export rules change. The contribution is a proper link model for the runtime that
the rest of the L1 toolchain can build on.

This initiative executes under the L1 roadmap ([`l1/docs/roadmap.md`](../../docs/roadmap.md)).

## Related initiatives

- **Initiative 0001 - Separate Compilation and External Linking**
  ([`0001-separate-compilation-and-linking.md`](0001-separate-compilation-and-linking.md)) is a soft consumer of this
  work. Separate compilation can land independently, but its link model is cleaner once a real runtime archive exists to
  anchor archive linkage and trace-variant selection.
- **Initiative 0003 - C FFI** ([`0003-c-ffi.md`](0003-c-ffi.md)) is a future downstream consumer for the `dea_siphash.h`
  aside below: once the runtime has been split, surfacing SipHash through the C FFI as its own shared object becomes a
  natural follow-up.

## Non-goals

- **Language changes.** No new syntax, no new semantics, no expansion of the L1 surface.
- **Runtime-toggleable tracing.** Trace and non-trace builds ship as distinct archives; switching tracing on at runtime
  through function pointers is explicitly out of scope.
- **Release-bearing L1 distribution policy** beyond the bootstrap packaging tracked under
  [`l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md`](../plans/tools/2026-04-02-l1-bootstrap-productization-noref.md).
- **Backporting to L0.** L0 keeps its header-only runtime per the `1.0.0` scope boundary. Everything in this initiative
  lands in `l1/`'s copy of the runtime tree.

## Current baseline

Relevant runtime-only facts that constrain the plan:

- The runtime (`compiler/shared/runtime/l1_runtime.h` plus the internal `dea_siphash.h` include) is **header-only**:
  every callable is `static` or `static inline` and is inlined into the single generated C CU at build time.
- Optional tracing (`DEA_TRACE_ARC`, `DEA_TRACE_MEMORY`) is wired through preprocessor toggles resolved at user-CU
  compile time by `--trace-arc` and `--trace-memory`.
- Build/run mode currently discovers runtime headers with `--runtime-include` / `L1_RUNTIME_INCLUDE` and runtime
  libraries with `--runtime-lib` / `L1_RUNTIME_LIB`. L1 does not ship a separate runtime archive yet; the current Stage
  1 build driver only checks that the configured runtime-library path is a directory and forwards it as a search path.
  It does not validate specific archive filenames or inject a concrete runtime archive name yet.
- `compiler/stage1_l0/` is the only implemented L1 compiler today. `compiler/stage2_l1/` is a placeholder for the future
  self-hosted L1 compiler, so every change in this initiative lands first in Stage 1.

## Phase 0 - Anchor decisions before coding

### 0.5 Where runtime symbols live

Once the runtime is a real static library, the `_rt_*` and `rt_*` symbols currently defined in `l1_runtime.h` become
external. That changes how `extern func rt_foo(...)` resolves:

- **Today:** the L1 declaration matches an inline `static` definition pulled in via `#include`.
- **After Phase 1:** the L1 declaration matches an `extern` declaration in a slim public header, backed by a runtime
  archive. The proposed target names are `dea_rt.h`, `dea_siphash.h`, `libdea_rt.a`, and `libdea_rt_traced.a`, but the
  Phase 1 plan must verify whether those names should replace or coexist temporarily with the current `l1_runtime.h`
  header name and any temporary artifact-name compatibility bridge.

This is a header-vs.-prototype split with no language semantics change. Trace builds ship as a separate archive
(`libdea_rt_traced.a`) rather than through runtime-toggleable tracing so the current behavior stays intact.

**Aside - `dea_siphash.h`:** this helper is a vendored header-only SipHash implementation. An earlier (retracted)
direction considered hosting it in a shared runtime library between L0 and L1. With the Phase 1 runtime split, a more
natural future evolution is exposing SipHash through a dedicated module that produces its own shared object and
participates in the C FFI surface defined in [Initiative 0003](0003-c-ffi.md). Not urgent, but worth flagging so this
initiative does not lock SipHash into a shape that later FFI work would have to reopen.

## Phase 1 - Runtime as a static library

Smallest, most contained change in the broader compilation/linking effort. Doing it first shakes out the FFI and
link-driver pieces in miniature without language semantics moving.

### Scope

- Split the current `compiler/shared/runtime/l1_runtime.h` header into a public header (prototypes, type definitions,
  public macros) plus one or more `.c` files grouped by subsystem: `dea_rt_string.c`, `dea_rt_io.c`, `dea_rt_alloc.c`,
  `dea_rt_hash.c`, `dea_rt_time.c`, `dea_rt_panic.c`, `dea_rt_math.c`. Truly internal helpers stay `static` inside their
  `.c`.
- Decide whether `dea_siphash.h` stays as a distinct internal helper include or folds into the same runtime-archive
  split, so L1 does not freeze a new public runtime layout around an unnecessary helper-header boundary.
- Trace builds are a second archive, `libdea_rt_traced.a`, compiled with `DEA_TRACE_ARC` and `DEA_TRACE_MEMORY`. The
  user-CU build no longer needs the trace toggles at compile time; the build driver picks the archive. (Trace flag
  *names* on the CLI stay as today.)
- `make runtime` produces `build/dea/lib/libdea_rt.a`, `build/dea/lib/libdea_rt_traced.a`, and copies headers under
  `build/dea/include/`.
- Once the L1 install workflow exists, `make install` lays out `$(PREFIX)/lib/libdea_rt*.a`,
  `$(PREFIX)/include/dea_rt.h`, `$(PREFIX)/include/dea_siphash.h`, plus any other public headers.
- The build driver appends `-I$(L1_HOME)/include -L$(L1_HOME)/lib -ldea_rt` (or `-ldea_rt_traced` when tracing) instead
  of relying on `#include` to inline the runtime. This is a migration of the current `--runtime-include` /
  `L1_RUNTIME_INCLUDE` and `--runtime-lib` / `L1_RUNTIME_LIB` directory plumbing into explicit `libdea_rt*` linkage once
  the real runtime archive exists.

### Validation

- Current Stage 1 validation (`make test-stage1` and `make test-all`) must still pass. Once `stage2_l1` and L1
  triple-bootstrap exist, the retained-C identity check needs to ignore the now-trivial prologue differences (no inline
  runtime body in the user CU).
- A new test compares `nm libdea_rt.a` output against a checked-in symbol manifest, locking the exported runtime
  surface. Adds/removes to that surface require an explicit manifest update in the same change.
- `tcc` validation: confirm link-order behavior. Keep the runtime archive listed *after* the user object on the link
  line. If `tcc` needs `--whole-archive`-equivalent treatment for any always-linked symbols (e.g., `_rt_panic`
  referenced from inlines that no longer exist), document it in the build driver.

### Risks

- `tcc` link semantics on Windows/MinGW are the most likely sharp edge.
- Trace-build duplication doubles the test matrix for runtime builds. Acceptable, but worth measuring.

## Sequencing and dependencies

This is a single-phase initiative. It is independently shippable and does not depend on other initiatives. Initiative
0001 (separate compilation and linking) consumes whatever runtime-link model this initiative settles on.

Recorded near-term tranche checkpoint:

- [ ] Phase 1: runtime split into `libdea_rt.a` and `libdea_rt_traced.a`.

## Cross-cutting concerns

### Stage 1 oracle and future Stage 2 parity

Every change lands in `compiler/stage1_l0/` while L1 is Stage 1-only. `stage1_l0` remains the behavioral oracle. When
`compiler/stage2_l1/` is implemented, this initiative must preserve a Stage 1/Stage 2 parity contract for the equivalent
surface.

### Determinism

The runtime archive's symbol manifest must be deterministic so the validation check (`nm libdea_rt.a` versus the
checked-in manifest) is stable across builds and platforms.

### L0 isolation

L0 is unaffected. The runtime split lands in `l1/`'s copy of the runtime tree; L0's header-only runtime stays as-is per
the `1.0.0` scope boundary.

## Open questions

These remain open after the decisions above and should be resolved in the phase plan:

1. **Runtime artifact transition.** Replace `l1_runtime.h` immediately, decide whether `dea_siphash.h` remains a
   separate helper header or folds into the same transition, and retire the inherited `libl0runtime.*` placeholder
   naming at the same time, or carry a short compatibility bridge while the build driver and docs move to `dea_rt.h`,
   `dea_siphash.h`, and `libdea_rt.*`?

Each open question gets a short design note under `l1/docs/specs/compiler/` once decided.

## Spawned plans

- Phase 1: runtime split into `libdea_rt.a` and traced runtime delivery under
  [`l1/work/plans/refactors/2026-04-24-runtime-static-library-split-noref.md`](../plans/refactors/2026-04-24-runtime-static-library-split-noref.md)

## Glossary

- **CU**: compilation unit. In this initiative, the user-side `.c` file generated by the L1 compiler.
- **Trace archive**: `libdea_rt_traced.a`, the variant compiled with `DEA_TRACE_ARC` and `DEA_TRACE_MEMORY` defined.
- **Symbol manifest**: a checked-in list of symbols exported by `libdea_rt.a` used as a validation contract.
