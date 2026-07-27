# ADR-0019: Stage 2 AST and Parser Ownership

- Decision date: 2026-02-14
- Last edited: 2026-07-27
- Status: Accepted

## Context

The self-hosted Stage 2 parser needed an AST representation that fits L0 ownership rules, remains practical for a
recursive-descent parser, and supports later semantic and backend passes. An entirely pointer-linked tree would create a
large ownership graph for dense syntax nodes. Individually transferring arena ownership to downstream passes would make
lifetime and cleanup responsibilities ambiguous.

Declaration-level structures also need stable direct identity and contain shared metadata for which pointer ownership is
more convenient than integer arena handles.

## Decision

Stage 2 uses a hybrid AST storage and ownership model:

1. Declarations and shared metadata are pointer-owned structures.
2. High-volume expression, statement, and pattern nodes are individually allocated, owned by per-family arenas, and
   registered in pointer tables addressed by integer IDs. Edges among those arena-backed node families use IDs rather
   than pointers.
3. APIs distinguish pointer-owned metadata from ID-addressed arena nodes; an ID is meaningful only with its owning
   arena.
4. `parse_module_source` and `parse_module_tokens` return a `ParseResult` that owns the parsed module and all AST arenas
   as one aggregate.
5. The caller retains that aggregate for as long as any AST pointer or node ID is in use and releases it through
   `parse_result_free`.
6. Cleanup releases nested strings, vectors, declaration metadata, and arena contents deterministically. Values that
   contain managed strings are not copied with raw-memory ownership shortcuts.

## Rationale

- Dense syntax graphs benefit from compact, stable handles and centralized arena ownership without requiring
  pointer-linked edges.
- Pointer-owned declarations preserve direct identity for long-lived objects and shared metadata.
- One `ParseResult` lifetime prevents arenas from being detached from the IDs that depend on them.
- Explicit aggregate cleanup makes ownership tractable in the self-hosted implementation.
- The representation can follow Stage 1's recursive-descent grammar without requiring premature generic graph
  abstractions.

## Consequences

- Downstream semantic and backend phases borrow AST data from a live `ParseResult`; they cannot retain an ID after its
  arenas are freed.
- AST helper signatures reveal whether a node family is pointer-owned or arena-addressed.
- Parser and analyzer migrations must be coordinated when a node moves between the two representation families.
- Arena-table reordering, compaction, or deduplication must preserve ID stability for the lifetime of the parse result.
- Parser error paths must release both partially built metadata and every arena through the same ownership boundary.

## Related Plans

- [l0/work/plans/features/closed/2026-02-14-stage2-parser-specification-noref.md](../../work/plans/features/closed/2026-02-14-stage2-parser-specification-noref.md):
  selected and implemented the hybrid arena representation and `ParseResult` lifecycle
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the Stage 2 parser ownership model into this ADR

## Current Docs

- [l0/docs/reference/architecture.md](../reference/architecture.md): Stage 2 parser pipeline and arena-backed AST
- [l0/docs/specs/compiler/stage2-contract.md](../specs/compiler/stage2-contract.md): current self-hosted compiler
  contract
