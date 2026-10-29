# Feature Plan

## Add streams and buffering

- Date: 2026-08-30
- Last reviewed: 2026-10-29
- Status: Draft
- Title: Add reader, writer, seeker, and buffered stream adapters
- Kind: Feature
- Priority: Medium
- Stdlib Tier: 2
- Subsystem: Stdlib / I/O abstractions
- Modules:
  - `l2/compiler/shared/l2/stdlib/std/stream.l2`
  - `l2/compiler/shared/l2/stdlib/std/file.l2`
  - `l2/compiler/shared/l2/stdlib/std/io.l2`
  - `l2/compiler/shared/l2/stdlib/std/bytes.l2`
  - `l2/docs/reference/standard-library.md`
- Test modules:
  - `l2/compiler/tests/stream_test.l1`
  - `l2/compiler/tests/analysis_trace_test.l1`
  - `l2/compiler/tests/l2c_lib_test.l1`
- Related:
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/work/plans/features/2026-08-30-file-handles-and-random-access-noref.md`
  - `l1/work/plans/features/2026-08-30-dynamic-byte-buffers-noref.md`
- Repro: `make -C l2 test-compiler TESTS="stream_test analysis_trace_test l2c_lib_test"`

## Summary

This work is deferred until stable-L1 catch-up and explicit activation of sustained L2 development. It does not gate L1
stabilization.

Build reusable reader, writer, seeker, and buffering abstractions after the concrete file contract is stable. The v1
surface uses existing function-pointer support for dispatch and makes endpoint ownership explicit.

## Stdlib-First Direction and Reference Material

Use the bounded file-transfer loops and buffer handling in
[l2/compiler/support/preparation/platform.h][platform-support] as implementation references and sources of short-read,
short-write, size-limit, and cleanup cases. Public reader/writer results and endpoint ownership define the stream
implementation; private JSON carriers, allocation-failure exits, and compiler limits are not stream API contracts.
Inventory the applicable reference cases before implementing the adapters.

Migration of L2 compiler code to public stdlib APIs and removal of superseded private helpers are separate follow-up
work. Shared-private-code extraction and compiler migration are not completion requirements for this plan.

## Proposed Surface

- Capabilities: `Reader`, `Writer`, `Seeker`, `BufferedReader`, and `BufferedWriter`.
- Reads: `read_some`, `read_exact`, `read_to_end`, and `read_until`.
- Writes: `write_some`, `write_all`.
- Utilities: `copy`, `flush`, `seek`, and `position`.
- Formatting: later `write_format` integration reuses the adopted L1 typed formatter engine and defines partial-write
  propagation.
- Adapters: files, standard streams, memory buffers, and later transport endpoints.

## Ownership Gate

The implementation must choose explicit ownership transfer, an explicitly shared runtime-owned endpoint, or immortal
standard-stream adapters. A generic adapter may not retain a freely escaping borrowed pointer to an independently
closable endpoint without lifetime enforcement.

## Implementation Phases

1. Finalize capability records/function tables and endpoint ownership.
2. Add unbuffered file, standard-stream, and memory adapters.
3. Add exact/all/copy loops over partial-transfer results.
4. Add buffered readers and writers with explicit flush behavior.
5. Add delimiter reads and bounded read-to-end operations over `ByteBuffer`.
6. Add trace, short-transfer, flush-failure, and nested-adapter tests.

## Non-Goals

- designing streams before file and error semantics settle
- a generic trait or interface language feature
- escaping borrowed endpoint views
- asynchronous streams or event-loop integration
- silent ownership transfer or silent close of independently owned endpoints
- L2 compiler migration, bootstrap changes, or removal of compiler-private support

## ADR Impact

- Decision: Select stream capability dispatch and endpoint ownership semantics for file, standard-stream, memory, and
  later transport adapters.
  - Scope: L2
  - Disposition: Pending
  - ADR: None
  - Rationale: Function pointers can provide dispatch, but L2 currently lacks lifetime enforcement for freely escaping
    borrowed adapters, so ownership must be resolved before implementation.

## Verification Criteria

1. Every adapter has a documented owner and close/flush responsibility.
2. Exact, all, and copy helpers handle repeated partial transfers and terminal failures.
3. Buffering never changes EOF or error classification.
4. Flush failures remain observable.
5. Trace tests cover adapters dropped before and after their endpoints according to the selected ownership rules.

[platform-support]: ../../../../l2/compiler/support/preparation/platform.h
