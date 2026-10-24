# ADR-0047: Followed Native Filesystem Identity

- Decision date: 2026-10-24
- Last edited: 2026-10-24
- Status: Accepted

## Context

Lexical equality and canonical spellings cannot distinguish hard links, followed aliases, and distinct objects reliably.
Treating failed queries as unequal would conceal missing or inaccessible inputs.

## Decision

`std.fs::same_file` compares existing followed object identities: device/inode on POSIX, and 64-bit volume serial plus
128-bit file ID on Windows. Both successful queries produce `SameFile(bool)`; either failure produces
`SameFileFailed(OsError)`. A Windows filesystem unable to provide the requested identity information returns failure.
Native identities are not exposed as persistent public tokens. No path normalization or case folding substitutes for
identity.

## Rationale

Native identity answers whether two observed names refer to the same object. Preserving query failures keeps the answer
distinct from an inability to observe an object.

## Consequences

Hard links and symbolic links may compare equal despite different spelling; missing inputs never yield successful false.
The two observations are not a snapshot, and identity can change after return. Canonicalization remains a separate
operation.

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
