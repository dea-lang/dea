# ADR-0046: Filesystem Paths and Owned Directory Traversal

- Decision date: 2026-10-24
- Last edited: 2026-10-24
- Status: Accepted

## Context

Path mutation and streaming enumeration need one public encoding, error, link, and lifetime contract. Compiler-private
helpers use different errors, encodings, and ownership and cannot define a general library API.

## Decision

Deliver path services through `std.fs`, `std.dir`, `sys.fs`, and the L1 runtime. Reject empty paths and embedded NUL.
Use strict UTF-8 conversion and wide Windows APIs, and preserve POSIX filename bytes. Metadata and entry types expose
links explicitly. Recursive removal never traverses final or descendant links and stops at the first failure without
rollback. Existing compiler helpers and the L0 bootstrap boundary remain unchanged; compiler adoption is separate work.

Windows recursive operations recognize drive, UNC, and supported DOS device roots by components, and reject unknown
device namespaces rather than treating them as ordinary descendants. Directory-child joins preserve bare drive-relative
inputs and existing separators. Recursive creation preserves literal components of canonical verbatim paths.

`Dir*` owns one cursor with explicit `close` and `free_dir`. `next` returns entry, end, or captured error, copying each
name and using cheap type hints without per-entry metadata queries. Terminal states repeat; close consumes native state
even on error; next after close reports `InvalidHandle`. Materialization and byte sorting are explicit, owned helpers.
Legacy whole-file APIs share path validation and Windows wide encoding. Persistent metadata retains `long` widths.

## Rationale

Public systems capability must stand independently of compiler-private ABIs. Streaming keeps memory proportional to one
entry, while owned names and explicit close state make escaping entry data and early cleanup reviewable.

## Consequences

Callers synchronize cursor access and process working-directory changes, trust ancestors leading to recursive roots, and
release wrappers/collections explicitly. Sorting and materialization cost is visible. The contract establishes no
security sandbox against concurrent in-place reparse-tag or mount changes, rollback, file handles, L2 migration, or
bootstrap change. Native Windows and other unavailable host execution remains a validation limitation, not simulated
native evidence.

## Related Plans

- [l1/work/plans/features/closed/2026-08-30-filesystem-mutations-and-directory-traversal-noref.md][filesystem-plan]
- [l1/work/initiatives/0005-filesystem-and-stream-io.md][filesystem-io]

## Current Docs

- [l1/docs/reference/filesystem.md][filesystem]
- [l1/docs/reference/standard-library.md][stdlib]

[filesystem]: ../reference/filesystem.md
[filesystem-io]: ../../work/initiatives/0005-filesystem-and-stream-io.md
[filesystem-plan]: ../../work/plans/features/closed/2026-08-30-filesystem-mutations-and-directory-traversal-noref.md
[stdlib]: ../reference/standard-library.md
