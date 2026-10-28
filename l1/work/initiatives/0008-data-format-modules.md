# L1 Initiative 0008 - Data Format Modules

- Version: 2026-10-27
- Status: Active
- Kind: Initiative
- Open plans:
  - `l1/work/plans/features/2026-08-30-json-data-format-noref.md`
- Closed plans: (none)

## Summary

This initiative owns streaming-capable JSON as a Stdlib Tier 3 implementation target after dynamic byte buffers and
streams exist. The speculative IFF item is reassigned to L2 and does not gate this initiative or L1 stability.

## Phases and stdlib tiers

### Phase 1 - JSON (Stdlib Tier 3)

- Add parsing from strings and readers, a streaming tokenizer/parser path, serialization to strings and writers, and
  typed accessors.
- Define duplicate-key, number, Unicode-escape, depth, and error-location behavior explicitly.

Spawned plan: [JSON data format].

## Dependencies

- JSON implementation depends on `std.bytes` and `std.stream` from [Initiative 0005].

## Deferred successor work

The IFF scope investigation now lives in
[l2/work/plans/features/2026-08-30-iff-scope-and-format-selection-noref.md][iff-scope]. It is a standalone L2 draft,
with no parent membership in this L1 initiative.

## Non-goals

- YAML, XML, TOML, CBOR, MessagePack, or schema languages in this initiative
- forcing all input into one whole-file string
- embedding network transport, filesystem, or character-encoding policy in a format parser
- IFF scope selection or implementation, now deferred to L2

## ADR Impact

- Decision: Make JSON streaming-capable over the common reader/writer and byte-buffer contracts.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Incremental parsing and writing avoid making the current `int`-bounded whole-file string helpers a
    format-size constraint.

## References

[iff-scope]: ../../../l2/work/plans/features/2026-08-30-iff-scope-and-format-selection-noref.md
[initiative 0005]: 0005-filesystem-and-stream-io.md
[json data format]: ../plans/features/2026-08-30-json-data-format-noref.md
