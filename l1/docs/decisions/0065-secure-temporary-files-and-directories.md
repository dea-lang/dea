# ADR-0065: Secure Temporary Files and Directories

- Decision date: 2026-11-22
- Last edited: 2026-11-22
- Status: Accepted

## Context

Compiler and build tools need private scratch files and directory trees. Some tools publish a finished file by renaming
it before scoped cleanup runs. The name returned to the caller can therefore refer to a different object by the time
cleanup starts.

## Decision

`std.temp` accepts an explicit parent or selects the host default. `system_temp_dir()` returns an absolute path for
inspection. Each creation validates the directory hierarchy and pins the selected parent itself. Trusted aliases are
valid, including macOS `/tmp`, when both the alias and its target pass validation.

Create each object exclusively relative to that pinned directory, using a fresh 128-bit name from the OS entropy
provider. Retry only a name collision and report `AlreadyExists` after 32 collisions. POSIX requests mode `0600` for
files and `0700` for directories. Windows applies a protected effective-user DACL at creation and verifies it on the
opened object. A host that cannot enforce the required privacy reports failure.

A successful result owns the pinned parent and the original object identity. Result copies share one cleanup obligation.
The file pointer borrows from that owner and supports ordinary `std.file` operations. Both cleanup functions accept a
failed creation result as a no-op and consume a successful result's owner exactly once, even when cleanup fails.

## Rationale

Pinning the parent ties creation and cleanup to the directory that passed validation. Retaining object identity
independently of the borrowed file handle lets callers close the file normally and publish it with a rename or replace.
An absent original entry needs no removal. When the name identifies a different object, cleanup preserves it and reports
an identity mismatch.

## Consequences

- File cleanup preserves the first close outcome and attempts removal even after a close failure. Creation preserves the
  primary error alongside any rollback failure.
- Tree cleanup traverses retained directory handles and removes symlinks and Windows reparse points as leaves. It stops
  at the first failure and returns the failed operation, affected path, captured OS error, and count removed.
- Callers coordinate concurrent changes by the same principal and keep mounts outside the owned tree. Process
  termination can leave temporary entries behind.

## Related Plans

- [l1/work/plans/features/closed/2026-08-30-secure-temporary-files-and-directories-noref.md][plan]

## Current Docs

- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/ownership.md][ownership]
- [l1/docs/reference/design-decisions.md][design]

[design]: ../reference/design-decisions.md#secure-temporary-files-and-directories
[ownership]: ../reference/ownership.md
[plan]: ../../work/plans/features/closed/2026-08-30-secure-temporary-files-and-directories-noref.md
[stdlib]: ../reference/standard-library.md#stdtemp
