# ADR-0049: Filesystem Replacement and No-Replace Capability

- Decision date: 2026-10-24
- Last edited: 2026-10-24
- Status: Accepted

## Context

Rename overwrite rules vary by host and object type. The private compiler's check-then-rename sequence assumes a single
writer and cannot provide a public atomic no-replace guarantee.

## Decision

`rename` uses host entry rename with overwrite semantics and no copy fallback. Existing directory replacement remains
host-specific: POSIX permits an empty compatible directory; Windows rejects an existing directory. `replace` adds an
explicit non-directory source/destination policy and permits an absent destination. Links are entries, preserving a
replaced link's target. Cross-filesystem rename/replace fails with the native error. Alias behavior remains native;
POSIX same-entry and hard-link aliases are successful no-ops.

`copy_file` follows a regular source and exclusively creates a new destination, rejecting existing entries and aliases.
Copy is incremental, handles partial writes, captures read/write/close failures, and leaves partial destinations for
explicit caller recovery. Neither rename nor copy requests durability.

Defer a separate atomic no-replace rename API. Linux and Darwin exclusivity mechanisms require capability and
filesystem-support handling; a future implementation must return unsupported rather than falling back to a racy check.
The current surface makes no atomic absence guarantee.

## Rationale

Native rename preserves host filesystem atomicity without quietly introducing copy/delete behavior. Explicit
non-directory replacement and exclusive copying give callers usable, documented policies now. Deferral avoids promising
a guarantee that portable check-then-rename cannot deliver.

## Consequences

Callers synchronize writers when they require stable source/destination classifications. Copies are not atomic
publication, snapshots, metadata preservation, or rollback. Native cross-filesystem validation remains unavailable in
the local environment; injected `EXDEV` coverage checks that no fallback or source deletion occurs.

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
