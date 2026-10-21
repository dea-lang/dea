# ADR-0045: Direct OS Errors and I/O Results

- Decision date: 2026-10-21
- Last edited: 2026-10-21
- Status: Accepted

## Context

Nullable, boolean, and sentinel I/O results cannot distinguish portable failure categories or retain the native error
that caused an operation to fail. Consulting ambient `errno` after cleanup is unreliable and does not identify Win32
errors. The first consumer needs no file-handle ownership or dynamic-buffer API.

## Decision

`std.os` defines `ErrorKind`, `ErrorDomain`, and `OsError { kind, domain, native_code }`. Native codes use signed
`long`; the initial domains are `Runtime`, `Errno`, and `Win32`. Library validation and host failures without a native
code use `Runtime` with code zero. Unknown native codes retain their domain and code and normalize to `Other`.
`error_message` renders the captured error; its text is diagnostic and may depend on the host and locale. Fallback
diagnostics include the normalized category, native domain, and code.

The same module defines concrete `ReadResult`, `WriteResult`, and `FlushResult` enums. Data transfer, clean EOF,
timeout, and failure are distinct variants. Timeout and failure variants carry `OsError`. Counts remain `int`, and a
positive partial transfer succeeds. Zero-length reads return `Read(0)` without probing EOF. Interrupted operations
return immediately without an implicit retry.

`std.io` adds `read_stdin_some_result`, `write_stdout_some_result`, `write_stderr_some_result`, `flush_stdout_result`,
and `flush_stderr_result`. Existing signatures and behavior remain available. The new byte helpers retain the existing
asserted buffer-range contract. Writes count bytes accepted by C stdio; an explicit flush reports delayed output
failures and requests no filesystem durability guarantee. The helpers preserve the host or application's `SIGPIPE`
disposition.

`sys.os` transports flat records with integer category/domain fields and a `long` native code. Runtime operations
capture their native error before any cleanup or message rendering. Windows CRT stdio errors use `Errno`; Windows native
API errors use `Win32`. Normal and traced runtimes export the same new symbol surface.

## Rationale

Portable control flow needs stable categories while diagnostics need the original native domain and value. Concrete
result enums work within L1's existing type system. Standard streams establish a working consumer without coupling the
error foundation to pending file-handle or stream-adapter lifetime decisions.

## Consequences

- Applications can adopt direct results incrementally while existing nullable and sentinel helpers remain compatible.
- Enum constructors have distinct names such as `ReadFailed` and `WriteFailed` because L1 constructors share module
  scope; no nested `Type::Variant` syntax or compiler diagnostic change is introduced.
- Native code/domain values are diagnostic data; normalized categories guide portable branching. Error messages are not
  stable identifiers or machine-readable classifications.
- This change establishes no deadlines, automatic `SIGPIPE` suppression, file handles, process APIs, socket APIs, or
  resolver-domain mappings. Later consumers reuse or extend the shared error contract.
- Positive partial transfer takes precedence over a simultaneous stream error. A later operation reports its own
  captured result; the API does not promise to replay an earlier partial operation's error.

## Related Plans

- [l1/work/plans/features/closed/2026-08-30-os-error-and-io-results-noref.md][os-errors]
- [l1/work/initiatives/0005-filesystem-and-stream-io.md][filesystem-io]

## Current Docs

- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/design-decisions.md][design]
- [l1/docs/project-status.md][status]

[design]: ../reference/design-decisions.md
[filesystem-io]: ../../work/initiatives/0005-filesystem-and-stream-io.md
[os-errors]: ../../work/plans/features/closed/2026-08-30-os-error-and-io-results-noref.md
[status]: ../project-status.md
[stdlib]: ../reference/standard-library.md
