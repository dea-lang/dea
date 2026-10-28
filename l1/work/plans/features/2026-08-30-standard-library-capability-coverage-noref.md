# Feature Plan

## Audit standard-library capability coverage

- Date: 2026-08-30
- Last reviewed: 2026-10-28
- Status: Draft
- Title: Document portable systems capability and C99 coverage for the L1 standard library
- Kind: Feature
- Priority: Medium
- Stdlib Tier: 2
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

## Scheduling and Maintenance

Defer the comprehensive audit until the main L1 stdlib additions have landed and their public reference documentation
describes the delivered APIs. Complete the audit and reconcile its findings before declaring L1 stable. Its current
readiness is `not-ready` because preceding stdlib delivery is now an explicit prerequisite.

Use [l1/docs/roadmap.md][roadmap] to identify the main additions at stabilization. Speculative file-watch/concurrency
investigations and deferred L2 work are outside this scheduling gate.

After establishing the coverage baseline, update affected rows, evidence links, and platform limitations in the same
change as subsequent stdlib additions or behavior changes. Refresh the relevant entries incrementally; repeat a broader
audit when the capability scope or stabilization baseline materially changes.

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

## Stdlib-First Direction and Reference Material

Record public stdlib availability separately from compiler-private capability. Inventory
[l1/compiler/support/compiler_support.c][compiler-support] and
[l1/compiler/support/preparation/platform.h][platform-support], with related preparation helpers, as reference material
for implementation and regression cases. A private helper does not make a capability implemented in `std.*` or `sys.*`.
Link candidate public additions to their existing plans: filesystem identity and resolution, opened-file metadata,
executable discovery, bounded-capture assessment, and owned private temporary directories.

The direction is complete L1 stdlib contracts first, then separately scoped L2 adoption and removal of superseded
compiler-private helpers. This audit neither creates that migration plan nor makes migration or shared-private-code
extraction a completion requirement. Private hashing and file-locking code does not imply new public digest or locking
scope in the current stdlib plans.

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
8. Compiler-private reference implementations are distinguished from public API coverage, with public additions owned by
   their stdlib plans and L2 migration/removal left as separate follow-up work.

## Implementation Phases

1. After the scheduling gate is satisfied, inventory exported `std.*` and `sys.*` modules and current runtime support,
   recording private reference code and applicable regression cases separately.
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
- extracting compiler-private C code or implementing L2 migration/removal

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
6. Private-only services remain unimplemented in the public-coverage columns, even when they provide reference code for
   a planned API. L2 migration and removal of superseded helpers are not claimed as stdlib delivery.
7. The comprehensive audit reflects the delivered main stdlib additions, and its findings are reconciled before L1 is
   declared stable. Later stdlib changes update the affected coverage entries and evidence alongside the API change.

[compiler-support]: ../../../compiler/support/compiler_support.c
[platform-support]: ../../../compiler/support/preparation/platform.h
[roadmap]: ../../../docs/roadmap.md
