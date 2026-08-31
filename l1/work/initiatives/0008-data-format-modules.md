# L1 Initiative 0008 - Data Format Modules

- Version: 2026-08-30
- Status: Active
- Kind: Initiative
- Open plans:
  - `l1/work/plans/features/2026-08-30-json-data-format-noref.md`
  - `l1/work/plans/features/2026-08-30-iff-scope-and-format-selection-noref.md`
- Closed plans: (none)

## Summary

This initiative owns the data-format modules already named by the L1 roadmap. JSON is a Priority 3 implementation target
after dynamic byte buffers and streams exist. The roadmap's `IFF` entry remains Priority 4 because neither the intended
interchange format nor a motivating consumer is documented; its first plan resolves that ambiguity instead of inventing
an API around an unexplained acronym.

## Phases and priorities

### Phase 1 - JSON (Priority 3)

- Add parsing from strings and readers, a streaming tokenizer/parser path, serialization to strings and writers, and
  typed accessors.
- Define duplicate-key, number, Unicode-escape, depth, and error-location behavior explicitly.

Spawned plan: [JSON data format].

### Phase 2 - IFF scope decision (Priority 4)

- Identify the intended format and consumer, decide whether it belongs in the core stdlib, and specify its module and
  stream contract before opening implementation work.

Spawned plan: [IFF scope and format selection].

## Dependencies

- JSON implementation depends on `std.bytes` and `std.stream` from [Initiative 0005].
- A selected IFF design must reuse the same binary-buffer and stream foundations rather than create a parallel I/O
  stack.

## Non-goals

- YAML, XML, TOML, CBOR, MessagePack, or schema languages in this initiative
- forcing all input into one whole-file string
- embedding network transport, filesystem, or character-encoding policy in a format parser
- implementing an IFF module before the acronym, format variant, and consumer are selected

## ADR Impact

- Decision: Make JSON streaming-capable over the common reader/writer and byte-buffer contracts.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Incremental parsing and writing avoid making the current `int`-bounded whole-file string helpers a
    format-size constraint.
- Decision: Select the exact meaning, consumer, and stdlib ownership of the roadmap's `IFF` item.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: The roadmap names `IFF` without an exact format scope or demonstrated user, so an implementation contract
    cannot yet be justified.

## References

[iff scope and format selection]: ../plans/features/2026-08-30-iff-scope-and-format-selection-noref.md
[initiative 0005]: 0005-filesystem-and-stream-io.md
[json data format]: ../plans/features/2026-08-30-json-data-format-noref.md
