# Bug Fix Plan

## Correct the README's implemented-library status

- Date: 2026-11-11
- Status: Completed
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
  - [l1/work/plans/features/2026-08-30-secure-os-entropy-noref.md][entropy-plan]
- Repro: The README's former "Motivation" paragraph listed completed formatting and file handles as planned work.

## Summary

The L1 source-tree README now lists typed string formatting, file handles, and secure OS entropy as implemented
capabilities. Its planned work retains temporary objects and shell-free processes and pipes. The library overview
includes these implemented capabilities, and the roadmap records this plan under completed standalone work.

The stale summary was a Low-severity documentation defect: detailed status and reference documents already described the
available APIs correctly. The correction preserves the distinction between current sources, the published development
release, and unfinished stabilization acceptance.

## ADR Impact

- Decision: Report implemented library capabilities separately from remaining stabilization work and release contents.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs a stale status summary without changing the stabilization boundary, API contracts, or
    release compatibility policy.

## Findings and Correction

[l1/README.md][readme] explicitly covers the source tree. Its former planned-work paragraph nevertheless grouped typed
formatting and file handles with pending capabilities. [l1/docs/project-status.md][status], the stabilization
initiative, and the closed implementation plans already identify both as complete.

[l1/compiler/shared/l1/stdlib/std/format.l1][format-source] implements typed formatting, structured errors, and
owned-string results. [l1/compiler/shared/l1/stdlib/std/file.l1][file-source] exports and implements opaque handles,
transfer, positioning, metadata, and synchronization operations. The README now agrees with that implementation and its
existing lifecycle records without implying a new release or completion of remaining acceptance gates.

Secure OS entropy is implemented as well. Its native CI and final ADR closure remain tracked in the
[l1/work/plans/features/2026-08-30-secure-os-entropy-noref.md][entropy-plan]; the README preserves that distinction
between implementation and acceptance.

## Verification

- Compared the corrected capability and planned-work paragraphs against the implementation, project status, roadmap,
  stabilization initiative, and closed library plans.
- Preserved the published development release and compatibility caveats, source-tree scope, and link to the remaining
  stabilization acceptance gates.
- Checked repository links, including the roadmap's updated closed-plan link. Markdown formatting, whitespace, active
  and staged ADR validation, and root pre-commit checks passed.
- This is documentation-only validation. Library tests and historical native CI acceptance were not rerun; no library,
  compiler, runtime, test, diagnostic, release-baseline, or stabilization-scope input changed.

[entropy-plan]: ../../features/2026-08-30-secure-os-entropy-noref.md
[file-plan]: ../../features/closed/2026-08-30-file-handles-and-random-access-noref.md
[file-source]: ../../../../compiler/shared/l1/stdlib/std/file.l1
[format-plan]: ../../features/closed/2026-08-30-typed-formatting-noref.md
[format-source]: ../../../../compiler/shared/l1/stdlib/std/format.l1
[readme]: ../../../../README.md
[roadmap]: ../../../../docs/roadmap.md
[stabilization]: ../../../initiatives/0011-l1-stabilization.md
[status]: ../../../../docs/project-status.md
