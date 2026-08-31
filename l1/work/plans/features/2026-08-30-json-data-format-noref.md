# Feature Plan

## Add a JSON data-format module

- Date: 2026-08-30
- Status: Draft
- Title: Add streaming-capable JSON parsing and serialization
- Kind: Feature
- Severity: Medium
- Priority: 3
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0008-data-format-modules.md`
- Subsystem: Stdlib / data formats / streams
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/json.l1`
  - `l1/compiler/shared/l1/stdlib/std/bytes.l1`
  - `l1/compiler/shared/l1/stdlib/std/stream.l1`
  - `l1/compiler/shared/l1/stdlib/std/string.l1`
  - `l1/compiler/shared/l1/stdlib/std/vector.l1`
  - `l1/compiler/shared/l1/stdlib/std/linear_map.l1`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/json_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_trace_test.l0`
- Related:
  - `l1/work/initiatives/0008-data-format-modules.md`
  - `l1/work/plans/features/2026-08-30-dynamic-byte-buffers-noref.md`
  - `l1/work/plans/features/2026-08-30-streams-and-buffering-noref.md`
- Repro: `make -C l1 test-stage1 TESTS="json_test analysis_trace_test"`

## Summary

Add `std.json` with a streaming tokenizer/parser as the foundation, convenient whole-string parsing, and matching
serialization to strings or writers. The implementation must not require every document to fit in one whole-file string
before parsing begins.

## Proposed Surface

- Parsing: `parse`, `parse_reader`.
- Serialization: `stringify`, `write`.
- Accessors: `get_object`, `get_array`, `get_string`, `get_number`, `get_bool`, and null inspection.
- Diagnostics: structured parse errors with byte offset, line, and column where available.

## Questions to Settle

1. JSON number representation and preservation of integers outside exact `double` range.
2. Duplicate object-key behavior.
3. Maximum nesting, allocation limits, and caller-provided bounds.
4. Invalid UTF-8, surrogate escapes, and Unicode escape normalization.
5. Object ordering guarantees during parsing and serialization.

## Implementation Phases

1. Finalize the value representation and parser limits.
2. Implement a chunk-boundary-safe tokenizer over `Reader` and `ByteBuffer`.
3. Implement streaming parse with structured location errors.
4. Add whole-string convenience parsing over the same engine.
5. Implement deterministic writer/string serialization and escaping.
6. Add conformance, adversarial depth/size, chunk-boundary, and trace tests.

## Non-Goals

- JSON Schema, JSONPath, JSON5, comments, or trailing commas
- silently accepting invalid UTF-8 or unpaired surrogate escapes
- requiring one whole-file read before tokenization
- network transport or filesystem policy inside `std.json`
- a generic serialization framework for arbitrary L1 structs in v1

## ADR Impact

- Decision: Define JSON value representation, number semantics, duplicate-key policy, Unicode behavior, parser limits,
  and deterministic serialization over the common stream contract.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: Streaming is settled direction, but interoperable parsing cannot ship until the durable data-model and
    edge-case policies are explicit.

## Verification Criteria

1. The same parser handles strings and arbitrarily chunked readers.
2. Tokens split at every byte boundary produce the same result as contiguous input.
3. Invalid syntax and Unicode report stable source locations.
4. Limits fail explicitly before stack, arithmetic, or allocation overflow.
5. Parse/serialize round trips follow the selected number and object-order policies.
6. Trace tests cover success and every partially constructed aggregate failure path.
