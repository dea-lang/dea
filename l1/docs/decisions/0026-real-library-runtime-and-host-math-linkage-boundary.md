# ADR-0026: L1 Real-Library Runtime and Host-Math Linkage Boundary

- Decision date: 2026-04-14
- Last edited: 2026-07-27
- Status: Accepted

## Context

L1's builtin `float` and `double` types established language and generated-C semantics but did not provide a standard
library for classification, rounding, decomposition, roots, or transcendental operations. Adding that surface raised
independent questions about module naming, pre-overload API shape, the compiler/runtime boundary, multi-result
operations, and when a host math library should enter the link.

Treating every floating-point program as a real-library user would impose an unnecessary header and linker dependency.
Implementing the helpers as compiler intrinsics or backend special cases would also couple an ordinary library surface
to compiler internals.

## Decision

The public floating-point library is `std.real`. Its low-level runtime binding is the separate `sys.real` module rather
than an expansion of `sys.rt`; the current `std.integer` module remains integer-focused.

Public helper names use explicit `_f` and `_d` suffixes for `float` and `double` instead of overloads. `std.real` is a
thin library layer over `sys.real`, not a syntax extension, compiler intrinsic family, or collection of backend special
cases.

Operations that naturally produce multiple results return small named structs from `std.real`. The corresponding
`sys.real` bindings may use C-oriented output parameters internally.

The C99 helper boundary lives in the optional `l1_real.h` runtime header. Generated C includes that boundary only when
the analyzed program uses `sys.real`. The build driver adds the host math-library dependency, such as `-lm`, only when
`sys.real` or its `std.real` wrapper is actually used and the target toolchain requires it. Plain `float` or `double`
use does not trigger either dependency.

## Rationale

The `std.real` / `sys.real` split follows the existing ergonomic-library versus low-level-binding architecture. Explicit
width suffixes keep the API unambiguous before L1 has an overload model. Runtime-backed wrappers preserve a generic
compiler, while conditional inclusion and linkage keep ordinary floating-point programs independent of unused math
support.

The rejected alternatives were naming the public module `std.float`, folding real helpers into the then-current
`std.math` module (now `std.integer`) or `sys.rt`, adding compiler intrinsics, using overloads, and linking the host
math library for every floating-point program.

## Consequences

- `std.real` exposes matched `float` and `double` APIs and named multi-result types.
- `sys.real` remains a thin, C-oriented binding surface.
- Analysis tracks real-helper use separately from builtin floating-point use.
- Generated C conditionally includes `l1_real.h`.
- Only real-helper users receive the target's host math-library link dependency.
- The existing floating-point typing, conversion, NaN, infinity, and signed-zero rules remain unchanged.

## Related Plans

- [l1/work/plans/features/closed/2026-04-14-l1-std-real-module-noref.md][std-real]
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md][publication-plan]

## Current Docs

- [l1/docs/reference/standard-library.md][standard-library]: `std.real`, `sys.real`, result types, and helper inventory
- [l1/docs/reference/design-decisions.md][design-decisions]: library naming, suffixes, and conditional linkage
- [ADR-0005][floating-point]: builtin floating-point semantics and backend contract

[design-decisions]: ../reference/design-decisions.md
[floating-point]: 0005-floating-point-semantics.md
[publication-plan]: ../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md
[standard-library]: ../reference/standard-library.md
[std-real]: ../../work/plans/features/closed/2026-04-14-l1-std-real-module-noref.md
