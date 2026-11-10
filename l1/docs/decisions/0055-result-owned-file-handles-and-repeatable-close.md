# ADR-0055: Result-Owned File Handles and Repeatable Close

- Decision date: 2026-11-10
- Last edited: 2026-11-10
- Status: Accepted

## Context

A file operation can fail after acquiring a native resource, and close can itself fail. Programs need to establish
cleanup immediately, inspect close failures, and distinguish a logically closed handle from a destroyed wrapper. L1 does
not enforce unique ownership through its type system.

## Decision

`std.file::OpenFileResult` owns one opaque file wrapper on success. Copies share one cleanup obligation; an extracted
`File*` borrows that owner. Register `free_open_file_result` with `with` before matching the result.

`close` retires the public handle on its first attempt, including failure, but preserves the wrapper and the first
`CloseResult` with its captured error. Repeated close returns that result without another native close attempt. Ordinary
operations on the closed live wrapper return `InvalidHandle`.

`free_open_file_result` closes an open file if necessary, destroys its wrapper, and returns the saved or newly captured
close outcome. Successful ownership is consumed exactly once even when close fails; all borrowed aliases then expire.
Failed-open cleanup needs no resource work and returns `Closed`. Destruction is not idempotent.

Logical retirement does not prove native release after a host close failure. Follow host close semantics without blindly
retrying an interrupted close, which could target a reused descriptor. Cleanup does not automatically propagate an error
or replace a primary operation failure.

## Rationale

Result-level ownership establishes cleanup before later fallible work. Separating close from destruction retains a
stable outcome for explicit inspection and defines post-close behavior while the wrapper remains alive. Saving the first
outcome avoids duplicate native closes and prevents a later call from hiding a failure.

## Consequences

Callers coordinate aliases and release each successful result once. When close determines successful completion, call it
explicitly and inspect the outcome before final cleanup. Native handles remain private and non-inheritable; this
contract introduces no transfer of ownership to child processes or independent owners for copied results.

## Related Plans

- [l1/work/plans/features/closed/2026-08-30-file-handles-and-random-access-noref.md][file-plan]
- [l1/work/initiatives/closed/0005-filesystem-and-stream-io.md][filesystem-io]

## Current Docs

- [l1/docs/reference/filesystem.md][filesystem]
- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/design-decisions.md][design]

[design]: ../reference/design-decisions.md
[file-plan]: ../../work/plans/features/closed/2026-08-30-file-handles-and-random-access-noref.md
[filesystem]: ../reference/filesystem.md
[filesystem-io]: ../../work/initiatives/closed/0005-filesystem-and-stream-io.md
[stdlib]: ../reference/standard-library.md
