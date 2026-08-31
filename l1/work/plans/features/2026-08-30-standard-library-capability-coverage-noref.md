# Feature Plan

## Audit standard-library capability coverage

- Date: 2026-08-30
- Status: Draft
- Title: Document portable systems capability and C99 coverage for the L1 standard library
- Kind: Feature
- Severity: Medium
- Priority: 2
- Stage: L1
- Subsystem: Stdlib / reference documentation / roadmap
- Modules:
  - `l1/docs/reference/standard-library-coverage.md`
  - `l1/docs/reference/standard-library.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `scripts/check_adr_impact.py`
- Related:
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/work/initiatives/0006-process-and-host-services.md`
  - `l1/work/initiatives/0007-blocking-networking.md`
  - `l1/work/initiatives/0008-data-format-modules.md`
- Repro: `rg -n "^## |^### " l1/docs/reference/standard-library.md l1/compiler/shared/l1/stdlib`

## Summary

Create a maintained coverage matrix that replaces vague "C99 parity" with the actual target: portable systems capability
through typed Dea APIs and platform-specific runtime bindings. The audit records what exists, what is partial, what is
planned, what Dea intentionally replaces, what belongs to FFI/packages, and what is intentionally unsupported.

## Coverage Model

Classify each capability as:

- implemented
- partially implemented
- planned
- intentionally replaced by a Dea design
- FFI or package territory
- intentionally unsupported

The matrix covers C99 header families plus non-C99 capabilities required by real systems programs, including
directories, processes, pipes, temporary objects, entropy, networking, and concurrency.

## Required Conclusions

1. C99 assertions, fixed-width scalars, raw memory/string work, numeric parsing, mathematics, environment, and process
   termination are assessed against current L1 behavior.
2. Standard I/O gaps link to Initiative 0005 rather than promise a `stdio.h` clone.
3. Ambient `errno` is classified as replaced by direct structured errors.
4. C variadic formatting is classified as replaced by typed formatting.
5. Locale/wide-character mirrors, safe signal handlers, and `setjmp`/`longjmp` remain unsupported unless a concrete
   future workload justifies them.
6. Complex arithmetic and floating-environment control remain low-priority gaps rather than implied requirements.
7. Every planned row links to an active roadmap item, initiative, or plan.

## Implementation Phases

1. Inventory exported `std.*` and `sys.*` modules and current runtime support.
2. Build the C99-family matrix with evidence links into current reference docs.
3. Add the non-C99 portable systems capability matrix.
4. Reconcile every planned row against active lifecycle documents and remove unsupported parity language.
5. Add a lightweight documentation check that detects broken plan/initiative links.

## Non-Goals

- promising one-to-one C header or function compatibility
- exposing unsafe or global-state-heavy C APIs solely to fill a matrix cell
- documenting draft APIs as implemented
- replacing the canonical implemented API inventory in `standard-library.md`
- expanding this documentation plan into implementation work

## ADR Impact

- Decision: Classify current and planned stdlib capability against an already selected portable-systems target.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The plan records and cross-links existing implementation and roadmap decisions; it does not select a new
    language, ABI, ownership, or runtime architecture.

## Verification Criteria

1. Every matrix row has current-source or lifecycle-document evidence.
2. Draft work is never labeled implemented.
3. C99 omissions and intentional replacements are explicit.
4. Non-C99 systems capabilities are visible so C99 does not become the accidental completeness boundary.
5. All links resolve and the roadmap and coverage matrix agree on ownership and status.
