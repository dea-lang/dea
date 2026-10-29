# Feature Plan

## Demonstrate the bounded L1 compiler and tool foundation

- Date: 2026-10-29
- Status: Draft
- Title: Validate L1 stabilization with public-API compiler and tool workloads
- Kind: Feature
- Parent Initiative: `l1/work/initiatives/0011-l1-stabilization.md`
- Priority: High
- Subsystem: Stdlib integration and stabilization acceptance

## Summary

After the required library contracts are delivered, exercise three bounded programs through public L1 APIs. These
workloads establish practical capability without migrating compiler-private support or expanding the language target.

## Acceptance Programs

1. Source indexer: traverse a source tree, read modules, emit deterministic index output and typed diagnostics, and
   publish output through a temporary file. Cover input and publication failures.
2. Build driver: execute a fixture child with exact arguments, explicit environment and working directory; redirect
   stdout/stderr to temporary files, wait and inspect exit status and binary output. No shell or concurrent in-memory
   capture helper is required.
3. Binary copier: copy arbitrary bytes in bounded reusable chunks, handling partial transfers and failures. Validate
   exact contents and byte count independently, with inputs larger than the working buffer.

## Verification

Run actual `.l1` programs against the delivered target stdlib. Cover spaces, quotes, empty arguments, Unicode, binary
bytes, EOF, partial transfers and resource cleanup. Keep native Windows evidence distinct from simulated path tests.
Require Linux, macOS Intel/ARM and Windows UCRT64 results plus fresh L1 artifact acceptance before stability
declaration.

## ADR Impact

- Decision: Verify the selected stabilization capabilities through bounded public-API workloads.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: These programs validate the stabilization initiative's contracts without introducing an independent
    architecture.
