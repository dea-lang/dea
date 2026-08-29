# ADR-0025: Runtime Trace Source Provenance

- Decision date: 2026-02-28
- Last edited: 2026-08-29
- Status: Accepted

## Context

ARC and memory traces originate in generated C and the shared runtime, but their purpose is to explain ownership events
in Dea source. Reporting only generated-C locations makes leak and lifetime archaeology depend on a transient
implementation artifact. Passing an explicit location through every L0 runtime declaration would enlarge the public
runtime surface and invite call sites to omit or misstate it.

The C emitter already maps generated code back to Dea source with `#line`, and C provides call-site `__FILE__` and
`__LINE__` macros.

## Decision

Trace source provenance is one generated-C/runtime contract:

1. ARC and memory trace events carry a `loc="file":line` field when source provenance is available.
2. Public trace-sensitive runtime entry points are macro wrappers around implementation functions. The wrappers capture
   `__FILE__` and `__LINE__` at the generated-C call site and pass them to the implementation.
3. Generated C emits `#line` directives that map the C preprocessor's file and line values back to the originating Dea
   source operation.
4. Runtime-internal allocation, release, and drop paths propagate the captured location so the event retains the
   original caller provenance.
5. C forward declarations protect runtime names from accidental function-like macro expansion.
6. Trace parsing and leak triage preserve and display the location field; column provenance is not part of the current
   contract.
7. The public declaration-only C header exposes stable function symbols for trace-sensitive `rt_*` entry points. Calls
   from additional C translation units use `loc="<runtime>":0`; generated L0 calls retain macro-captured Dea provenance
   and the private `_rt_*` implementations remain unexposed.

## Rationale

- A trace is actionable only when an allocation, retain, release, or free can be attributed to the Dea operation that
  caused it.
- Macro capture avoids adding location parameters to the L0-facing runtime declarations.
- Existing `#line` emission lets standard C facilities provide language-source provenance without a second source map.
- One location field shared by runtime output and triage tools keeps trace producers and consumers aligned.

## Consequences

- C emission and runtime trace macros must evolve together; removing or relocating `#line` directives can change trace
  provenance.
- Runtime declarations for macro-wrapped names require a spelling that suppresses preprocessor expansion.
- Trace fixtures and triage tooling treat `loc` as part of the stable text contract when present.
- Runtime-internal events should forward an originating location instead of substituting a runtime-header line.
- Foreign-C calls have no Dea source position and therefore use the stable `<runtime>:0` fallback rather than claiming
  the foreign C file is Dea source.
- Exact source columns would require a separate extension because standard C has no portable `__COLUMN__`.

## Related Plans

- [l0/work/plans/refactors/closed/2026-02-28-trace-source-location.md](../../work/plans/refactors/closed/2026-02-28-trace-source-location.md):
  established macro-captured locations, generated-C mapping, and trace-tool propagation
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the trace provenance contract into this ADR
- [l0/work/plans/features/closed/2026-08-29-public-c-runtime-header-noref.md](../../work/plans/features/closed/2026-08-29-public-c-runtime-header-noref.md):
  added stable foreign-C wrapper symbols without weakening generated Dea provenance

## Current Docs

- [l0/docs/specs/runtime/trace.md](../specs/runtime/trace.md): trace flags, event fields, and `loc` semantics
- [l0/docs/decisions/0011-c-emission-strategy.md](0011-c-emission-strategy.md): generated-C source mapping and emission
  architecture
- [l0/docs/decisions/0027-public-c-runtime-header.md](0027-public-c-runtime-header.md): public declarations and the
  generated-unit runtime ownership boundary
