# ADR-0061: Stdlib-First I/O Delivery Boundary

- Decision date: 2026-11-10
- Last edited: 2026-11-10
- Status: Accepted

## Context

Compiler-private native helpers already perform filesystem and I/O operations, but their allocation, errors, encoding,
and ownership conventions serve individual compiler implementations. Making those helpers the public contract would
couple library delivery to compiler migration and expose conventions that ordinary L1 programs cannot safely reuse.

## Decision

Deliver general L1 I/O capability through public `std.*` contracts, `sys.*` transports, and the L1 runtime. Use existing
compiler helpers as reference material and sources of regression cases; adapt their behavior to the public library's
error, width, path, and ownership contracts.

Complete and validate the public APIs independently of compiler adoption. Migrating L2's L1 implementation to those
APIs, extracting shared private code, and removing superseded compiler helpers are separate follow-up work. Canonical L1
remains implemented in L0 with its existing bootstrap boundary. General streams and file watching belong to L2 and do
not gate the completed L1 filesystem initiative.

## Rationale

The language library must serve ordinary programs as well as compilers. Independent delivery makes its contracts
reviewable through actual L1 consumers and native tests without requiring a simultaneous compiler rewrite. Existing
helpers remain useful evidence without becoming an accidental public ABI.

## Consequences

Library completion does not imply that compiler-private I/O has been removed or migrated. Any later consolidation must
preserve the reviewed public contracts and the predecessor/successor ownership boundary. Temporary implementation
duplication is acceptable until a separately scoped migration establishes equivalent behavior.

## Related Plans

- [l1/work/initiatives/closed/0005-filesystem-and-stream-io.md][filesystem-io]
- [l1/work/plans/features/closed/2026-08-30-file-handles-and-random-access-noref.md][file-plan]

## Current Docs

- [l1/docs/reference/design-decisions.md][design]
- [l1/docs/roadmap.md][roadmap]

[design]: ../reference/design-decisions.md
[file-plan]: ../../work/plans/features/closed/2026-08-30-file-handles-and-random-access-noref.md
[filesystem-io]: ../../work/initiatives/closed/0005-filesystem-and-stream-io.md
[roadmap]: ../roadmap.md
