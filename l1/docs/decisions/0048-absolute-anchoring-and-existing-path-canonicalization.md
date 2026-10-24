# ADR-0048: Absolute Anchoring and Existing-Path Canonicalization

- Decision date: 2026-10-24
- Last edited: 2026-10-24
- Status: Accepted

## Context

Tooling needs to anchor future paths as well as resolve existing aliases. One operation cannot serve both contracts
without hiding existence requirements or changing POSIX filename-byte semantics.

## Decision

`absolute` anchors at call-time process current-directory state without requiring existence or resolving filesystem
aliases. POSIX preserves components and literal backslashes; Windows uses native full-path rules for drive-relative,
rooted, drive-rooted, UNC, and mixed-separator spellings. `canonicalize` follows an existing path through POSIX
`realpath` or a Windows normalized final handle path, retaining Windows extended prefixes. Both return owned strings or
captured structured failure and grow native output buffers instead of truncating them.

## Rationale

Anchoring answers which spelling a relative name currently denotes; canonicalization resolves observed aliases. Keeping
those questions separate supports future outputs and existing-object lookup without lexical identity claims.

## Consequences

Neither output proves containment or subsequent object identity. Callers synchronize process/per-drive directory changes
where needed. Missing canonical inputs fail, while missing absolute inputs can succeed. Native host path limits and
unavailable canonical names remain explicit errors.

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
