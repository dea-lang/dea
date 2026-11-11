# Bug Fix Plan

## Correct the README's implemented-library status

- Date: 2026-11-11
- Status: Draft
- Title: Stop listing implemented typed formatting and file handles as planned L1 work
- Kind: Bug Fix
- Severity: Low
- Subsystem: Source-tree README / standard-library capability status
- Modules:
  - `l1/README.md`
- Test modules: None; compare the README against current implementation, status, and lifecycle records.
- Related:
  - [l1/docs/project-status.md][status]
  - [l1/docs/roadmap.md][roadmap]
  - [l1/work/initiatives/0011-l1-stabilization.md][stabilization]
  - [l1/work/plans/features/closed/2026-08-30-typed-formatting-noref.md][format-plan]
  - [l1/work/plans/features/closed/2026-08-30-file-handles-and-random-access-noref.md][file-plan]
- Repro: Compare the README's "Motivation" planned-work paragraph with the linked status and stabilization records.

## Summary

The L1 source-tree README still lists typed string formatting and file handles as planned stabilization work even though
both capabilities are implemented and their plans are closed. This understates the available library surface. Severity
is Low because the detailed status and reference documents describe the capabilities correctly. This report records the
defect; the README remains unchanged.

## ADR Impact

- Decision: Report implemented library capabilities separately from remaining stabilization work and release contents.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs a stale status summary without changing the stabilization boundary, API contracts, or
    release compatibility policy.

## Current State

Inspection on 2026-11-11 confirms:

- [l1/README.md][readme] explicitly says it covers the source tree, but its "Motivation" paragraph groups typed string
  formatting and file handles with entropy, temporary objects, processes, and pipes as work that remains planned.
- [l1/docs/project-status.md][status] describes `std.format` and `std.file` as implemented. The stabilization initiative
  marks typed formatting and dynamic byte buffers/files complete, and their implementation plans are closed.
- [l1/compiler/shared/l1/stdlib/std/format.l1][format-source] contains the typed formatting implementation, structured
  errors, and owned-string results. [l1/compiler/shared/l1/stdlib/std/file.l1][file-source] exports and implements
  opaque handles, transfer, positioning, metadata, and synchronization operations.

This is source and document verification, not a new execution of the library suites or independent confirmation of
historical CI acceptance. Existing records establish the intended capability status; pending stabilization gates must
remain explicit.

## Expected Behavior and Scope

Update the source-tree README to place formatting and file handles among implemented capabilities, and retain only
actually pending capabilities in the planned-work paragraph. Preserve the distinction between current source-tree
capabilities, the published development release, and the unfinished stabilization acceptance work. Do not imply that the
presence of these APIs establishes language or ABI stability.

No library implementation, tests, release baseline, diagnostic codes, or stabilization scope need to change.

## Acceptance Criteria

- The README no longer labels typed formatting or file handles as planned.
- Its current/pending distinction agrees with the roadmap, project status, and stabilization initiative.
- Published-release and source-tree claims remain distinct; unfinished acceptance gates are not marked complete.
- Markdown and repository-link validation pass.

[file-plan]: ../features/closed/2026-08-30-file-handles-and-random-access-noref.md
[file-source]: ../../../compiler/shared/l1/stdlib/std/file.l1
[format-plan]: ../features/closed/2026-08-30-typed-formatting-noref.md
[format-source]: ../../../compiler/shared/l1/stdlib/std/format.l1
[readme]: ../../../README.md
[roadmap]: ../../../docs/roadmap.md
[stabilization]: ../../initiatives/0011-l1-stabilization.md
[status]: ../../../docs/project-status.md
