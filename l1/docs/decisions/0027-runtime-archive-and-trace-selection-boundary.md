# ADR-0027: L1 Runtime Archive and Trace-Selection Boundary

- Decision date: 2026-04-24
- Last edited: 2026-07-27
- Status: Accepted

## Context

L1 initially placed runtime implementation bodies in a header included by every generated C translation unit. That model
made trace behavior a user-C preprocessor choice, duplicated runtime implementation into program builds, and provided no
concrete library boundary for separate compilation or external linking.

A compiled runtime also has to accommodate toolchains whose object formats are incompatible on the same host. Trace
diagnostics additionally need caller source locations without breaking the stable wrapper ABI used by non-emitter
consumers. L1 could adopt this boundary independently because L0 was already constrained to remain header-only for its
1.0 scope.

## Decision

`dea_rt.h` is L1's declaration-only public runtime header. Runtime implementation bodies live in compiled C translation
units, while `dea_siphash.h` remains an internal implementation header and is not installed with the public headers. The
former `l1_runtime.h` name was replaced without a compatibility shim.

L1 provides separate normal and traced runtime archives named `libdea_rt.a` and `libdea_rt_traced.a`. The build driver,
not a runtime toggle or user-C implementation include, selects the archive from the trace flags.

Official archives use the platform compiler's object format. When TinyCC produces an incompatible object format, the
runtime build creates a parallel raw-object set and the driver links those objects directly instead of forcing one
archive format to serve both compiler families.

The traced runtime preserves the stable `rt_*` / `_rt_*` wrapper ABI for callers that do not come through generated C.
Generated traced C calls `_rt_*_impl` entry points with its source file and line directly so diagnostics retain the
actual caller location.

This split is L1-specific. L0 keeps its header-only runtime at the L0 1.0 boundary.

## Rationale

A real archive establishes the link model needed by separate compilation while keeping runtime implementation out of
user translation units. Link-time trace selection is deterministic and avoids runtime indirection. Platform-format
archives preserve normal host-toolchain integration, while a narrow TinyCC raw-object path handles genuine format
incompatibility without weakening the public artifact contract.

The rejected alternatives were keeping L1 header-only, selecting tracing at runtime or through implementation bodies in
each user translation unit, retaining an `l1_runtime.h` compatibility shim, requiring incompatible TinyCC objects to use
the platform archive, and backporting the split to L0.

## Consequences

- Runtime delivery includes a public declaration header, compiled implementation artifacts, and deterministic symbol
  validation.
- Trace and non-trace program builds select different link inputs but expose the same stable public runtime API.
- Generated-C-only callers using trace flags must arrange the matching traced runtime link input.
- Runtime artifacts are built per toolchain and configuration; incompatible object formats are never mixed.
- L1 and L0 intentionally retain different runtime packaging models.

## Related Plans

- [l1/work/plans/refactors/closed/2026-04-24-runtime-static-library-split-noref.md][runtime-split]
- [l1/work/initiatives/closed/0002-runtime-static-library.md][runtime-initiative]
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md][publication-plan]

## Current Docs

- [l1/docs/reference/c-backend-design.md][backend]: runtime headers, archive variants, and TinyCC object selection
- [l1/docs/specs/compiler/abi.md][abi]: stable runtime-facing ABI context
- [l1/docs/reference/design-decisions.md][l1-decisions]: L1 runtime boundary and variant behavior
- [l0/docs/reference/design-decisions.md][l0-decisions]: retained L0 runtime boundary

[abi]: ../specs/compiler/abi.md
[backend]: ../reference/c-backend-design.md
[l0-decisions]: ../../../l0/docs/reference/design-decisions.md
[l1-decisions]: ../reference/design-decisions.md
[publication-plan]: ../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md
[runtime-initiative]: ../../work/initiatives/closed/0002-runtime-static-library.md
[runtime-split]: ../../work/plans/refactors/closed/2026-04-24-runtime-static-library-split-noref.md
