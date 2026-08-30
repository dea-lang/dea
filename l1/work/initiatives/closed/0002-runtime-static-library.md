# L1 Initiative 0002 - L1 Runtime Library

- Version: 2026-08-30
- Status: Completed
- Kind: Initiative

## Summary

This initiative moves the L1 runtime from a header-only inclusion model into a real static library with a public header
surface and a separate traced variant. It is a behavior-preserving infrastructure change: no language semantics move, no
FFI surface expands, no source-level export rules change. The contribution is a proper link model for the runtime that
the rest of the L1 toolchain can build on.

This initiative executes under the L1 roadmap ([`l1/docs/roadmap.md`][roadmap]).

## Completion

Initiative 0002 is complete. L1 now ships the copied runtime as public headers plus compiled runtime artifacts under
`compiler/shared/runtime/`, `make runtime` produces `build/dea/include/dea_rt.h`, `build/dea/lib/libdea_rt.a`, and
`build/dea/lib/libdea_rt_traced.a`, and Stage 1 build/run now links the runtime through the selected archive or the
documented repo-local tcc object path.

Validation:

```bash
cd l1
make test-all
```

## Related initiatives

- **Initiative 0001 - Separate Compilation and External Linking**
  ([`l1/work/initiatives/closed/0001-separate-compilation-and-linking.md`][separate-compilation]) was a soft consumer of
  this work. Separate compilation could land independently, but its link model became cleaner once a real runtime
  archive existed to anchor archive linkage and trace-variant selection.
- **Initiative 0003 - C FFI** ([`0003-c-ffi.md`][c-ffi]) is a future downstream consumer for the `dea_siphash.h` aside
  below: once the runtime has been split, surfacing SipHash through the C FFI as its own shared object becomes a natural
  follow-up.

## Non-goals

- **Language changes.** No new syntax, no new semantics, no expansion of the L1 surface.
- **Runtime-toggleable tracing.** Trace and non-trace builds ship as distinct archives; switching tracing on at runtime
  through function pointers is explicitly out of scope.
- **Release-bearing L1 distribution policy** beyond the bootstrap packaging tracked under
  [`l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md`][bootstrap-productization].
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
  archive. The canonical names are `dea_rt.h` (public header), `libdea_rt.a` (runtime archive), and `libdea_rt_traced.a`
  (traced runtime archive). `dea_rt.h` replaces `l1_runtime.h` immediately; no compatibility bridge. See §Resolved
  decisions for the closed answer covering all three facets (rename, `dea_siphash.h` fate, and archive naming).

This is a header-vs.-prototype split with no language semantics change. Trace builds ship as a separate archive
(`libdea_rt_traced.a`) rather than through runtime-toggleable tracing so the current behavior stays intact.

**Aside - `dea_siphash.h`:** this helper is a vendored header-only SipHash implementation. An earlier (retracted)
direction considered hosting it in a shared runtime library between L0 and L1. The closed answer for this initiative
keeps `dea_siphash.h` as a distinct, internal-only header (not folded into `dea_rt.h`, not surfaced through
`build/dea/include/`). A more natural future evolution is exposing SipHash through a dedicated module that produces its
own shared object and participates in the C FFI surface defined in [Initiative 0003][c-ffi]; keeping the header distinct
now preserves that option.

**Aside - `l1_real.h` and `DEA_USE_SYS_REAL`:** the `rt_real_*` floating-point helpers are a deliberate exception to the
"all `_rt_*` and `rt_*` symbols become external" framing above. They live in a separate public optional header,
`l1_real.h`, that `dea_rt.h` includes only when the user CU is compiled with `#define DEA_USE_SYS_REAL 1`. Stage 1 emits
that define exactly when the program imports `sys.real`. The helpers therefore stay `static inline` and are *not* in
`libdea_rt.a` or `libdea_rt_traced.a`. This shape predates the present initiative and was set by the `std.real` feature
plan ([`l1/work/plans/features/closed/2026-04-14-l1-std-real-module-noref.md`][std-real]) decisions 08 and 09, whose
explicit intent is to keep `-lm` off the link line for plain `float` / `double` programs. The exception is expected to
dissolve once [Initiative 0003 - C FFI][c-ffi] lands: `sys.real` is already declared as pure `extern func` bindings, so
once `extern "C"` blocks against host headers are available, `sys.real` can rebind directly to `<math.h>` and retire
`l1_real.h`, `DEA_USE_SYS_REAL`, and the Stage 1 `analysis_uses_sys_real` hook in one motion. Unlike the `dea_siphash`
case above, no new shared object is produced — the migration is a pure rebinding from inline `rt_real_*` helpers to host
`libm`. See Initiative 0003 §"Forward references" for the parallel note.

## Phase 1 - Runtime as a static library

Smallest, most contained change in the broader compilation/linking effort. Doing it first shakes out the FFI and
link-driver pieces in miniature without language semantics moving.

### Scope

- Split the current `compiler/shared/runtime/l1_runtime.h` header into a public header (prototypes, type definitions,
  public macros) plus one or more `.c` files grouped by subsystem: `dea_rt_string.c`, `dea_rt_io.c`, `dea_rt_alloc.c`,
  `dea_rt_hash.c`, `dea_rt_time.c`, `dea_rt_panic.c`, `dea_rt_math.c`. Truly internal helpers stay `static` inside their
  `.c`.
- `dea_siphash.h` stays as a distinct internal-only vendored helper after the split: included only by the runtime's own
  `.c` translation units, not folded into `dea_rt.h`, and not copied to `build/dea/include/`. See §Resolved decisions
  for the rationale.
- Trace builds are a second archive, `libdea_rt_traced.a`, compiled with `DEA_TRACE_ARC` and `DEA_TRACE_MEMORY`. The
  user-CU build no longer needs the trace toggles at compile time; the build driver picks the archive. (Trace flag
  *names* on the CLI stay as today.)
- `make runtime` produces `build/dea/lib/libdea_rt.a`, `build/dea/lib/libdea_rt_traced.a`, and copies headers under
  `build/dea/include/`.
- Once the L1 install workflow exists, `make install` lays out `$(PREFIX)/lib/libdea_rt*.a`,
  `$(PREFIX)/include/dea_rt.h`, plus any other public headers. `dea_siphash.h` is not part of the public install
  surface; it remains internal to the runtime sources.
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

- [x] Phase 1: runtime split into `libdea_rt.a` and `libdea_rt_traced.a`.

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

## Resolved decisions

The runtime-artifact-transition open question is closed. The closed answer has three parts:

1. **Header rename: replace immediately.** `l1/compiler/shared/runtime/l1_runtime.h` is renamed to `dea_rt.h` in one
   coordinated change. There is no `l1_runtime.h` shim; the emitter, tests, docs, and Makefile flip atomically with the
   rename. L1 is bootstrap-only with no external runtime consumers, so a compatibility bridge would protect no one and
   would risk lingering as a permanent fixture.
2. **`dea_siphash.h` stays distinct and internal-only.** It remains a separate vendored helper header, included only by
   the runtime's own `.c` translation units after the split. It is not folded into `dea_rt.h` and is not copied to
   `build/dea/include/`. This matches the §0.5 aside's caution against locking SipHash into a shape that
   [Initiative 0003 - C FFI][c-ffi] would have to reopen, and keeps L1's source layout in line with L0's (which also
   carries `dea_siphash.h` as a distinct file).
3. **Archive names: `libdea_rt.a` and `libdea_rt_traced.a` are introduced fresh.** No `libl0runtime.*` retirement is
   needed because no such artifact lives in the L1 tree today; the open question's "inherited placeholder" framing was
   documentary. Future readers should not look for an artifact that never existed in L1.

CLI-flag migration (`--runtime-include` / `--runtime-lib`, `L1_RUNTIME_INCLUDE` / `L1_RUNTIME_LIB`, the `-I` / `-L`
short aliases) is **out of scope** for this initiative. It is owned by
[Initiative 0001 - Separate Compilation and External Linking][separate-compilation] §Phase 3, which already commits to
retiring the short aliases when `-I` and `-L` are reclaimed for interface and library search.

The implementation of the runtime split itself remains owned by
[`l1/work/plans/refactors/closed/2026-04-24-runtime-static-library-split-noref.md`][runtime-split].

## ADR Impact

- Decision: Deliver the L1 runtime through a declaration-only public header and build-driver-selected normal or traced
  compiled link inputs.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0027-runtime-archive-and-trace-selection-boundary.md`
  - Rationale: ADR-0027 records the header and archive boundary, canonical artifact names, trace selection,
    compiler-family fallback, and L0 isolation implemented by this initiative.

## Spawned plans

- Phase 1: runtime split into `libdea_rt.a` and traced runtime delivery under
  [`l1/work/plans/refactors/closed/2026-04-24-runtime-static-library-split-noref.md`][runtime-split]

## Glossary

- **CU**: compilation unit. In this initiative, the user-side `.c` file generated by the L1 compiler.
- **Trace archive**: `libdea_rt_traced.a`, the variant compiled with `DEA_TRACE_ARC` and `DEA_TRACE_MEMORY` defined.
- **Symbol manifest**: a checked-in list of symbols exported by `libdea_rt.a` used as a validation contract.

[bootstrap-productization]: ../../plans/tools/2026-04-02-l1-bootstrap-productization-noref.md
[c-ffi]: ../0003-c-ffi.md
[roadmap]: ../../../docs/roadmap.md
[runtime-split]: ../../plans/refactors/closed/2026-04-24-runtime-static-library-split-noref.md
[separate-compilation]: 0001-separate-compilation-and-linking.md
[std-real]: ../../plans/features/closed/2026-04-14-l1-std-real-module-noref.md
