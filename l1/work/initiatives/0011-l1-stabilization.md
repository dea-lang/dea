# L1 Initiative 0011 - Stabilization for Compilers and Tools

- Version: 2026-10-29
- Status: Active
- Kind: Initiative
- Open plans:
  - `l1/work/plans/features/2026-10-29-stabilization-acceptance-programs-noref.md`
- Closed plans: (none)

## Summary

Stabilize L1 against a finite public capability target for compilers and tools. L1 remains implemented in L0; L2 remains
implemented in L1. There is no deadline driven by starting L2. Additional capabilities require an explicit scope
amendment; defects in the selected contracts remain stabilization work.

The completed [work/plans/features/closed/2026-10-29-l1-stabilization-boundary-noref.md][boundary] records capability
allocation.

Existing initiatives retain ownership of their plans. The dependencies below are completion gates, not additional
membership entries. Compiler migration away from private native helpers is separate follow-up work.

## Completion gates

| Gate                                            | Owning work                                                                                 | Status                                           |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| Borrowed-slice safety                           | [l1/work/plans/bug-fixes/closed/2026-10-29-borrowed-slice-escape-noref.md][slices]          | Complete; native CI passed on all four platforms |
| Dynamic byte buffers and files                  | [l1/work/initiatives/0005-filesystem-and-stream-io.md][files]                               | Planned                                          |
| Entropy, temporary objects, processes and pipes | [l1/work/initiatives/0006-process-and-host-services.md][process]                            | Planned                                          |
| Typed string formatting                         | [l1/work/plans/features/2026-08-30-typed-formatting-noref.md][format]                       | Planned                                          |
| Semantic dependency discovery                   | [l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md][profiles]             | Planned                                          |
| Public-API acceptance programs                  | [l1/work/plans/features/2026-10-29-stabilization-acceptance-programs-noref.md][acceptance]  | Planned                                          |
| Capability audit                                | [l1/work/plans/features/2026-08-30-standard-library-capability-coverage-noref.md][coverage] | After library delivery                           |
| Documentation and fresh artifact acceptance     | Existing compiler, reference and productization gates                                       | Before stability declaration                     |

## Delivery sequence

1. Record the boundary and correct borrowed-slice escapes in L1 (complete).
2. Deliver opaque byte buffers, then file handles and entropy, then temporary objects and process/pipe support.
3. Deliver typed string formatting and semantic dependency discovery independently when their own contracts are settled.
4. Exercise source indexing, explicit child execution with file-routed capture, and bounded-memory binary copying.
5. Reconcile the capability audit and documentation, complete native compiler validation and fresh L1 artifact
   acceptance, then select the stable L1 baseline.

Each library plan settles its remaining API decisions before implementation. Process capture uses explicit file/pipe
routing; concurrent in-memory capture is deferred. Formatting uses explicit `Value...` arguments and returns an owned
string or a structured error. Generic writer integration is separate L2 stream work.

## Deferred successor capabilities

General streams, networking, JSON, file watching, concurrency, owned slices and escaping buffer views, closures,
generics, and broader first-class C interoperability belong to future L2 work. Owned-slice syntax and mutation policy
remain design questions. These capabilities do not gate L1 stability. Later compatible library additions and maintenance
do not reopen this stabilization target automatically.

## ADR Impact

- Decision: Stabilize L1 against a finite public capability target for compiler and tool construction.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0026-l1-stabilization-boundary.md`
  - Rationale: The capability boundary and acceptance evidence define the lasting scope of the stable predecessor.

## References

[acceptance]: ../plans/features/2026-10-29-stabilization-acceptance-programs-noref.md
[boundary]: ../../../work/plans/features/closed/2026-10-29-l1-stabilization-boundary-noref.md
[coverage]: ../plans/features/2026-08-30-standard-library-capability-coverage-noref.md
[files]: 0005-filesystem-and-stream-io.md
[format]: ../plans/features/2026-08-30-typed-formatting-noref.md
[process]: 0006-process-and-host-services.md
[profiles]: 0010-explicit-profiles-and-composable-builds.md
[slices]: ../plans/bug-fixes/closed/2026-10-29-borrowed-slice-escape-noref.md
