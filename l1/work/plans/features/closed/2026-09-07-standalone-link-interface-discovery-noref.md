# Feature Plan

## Standalone-link discovery: superseded planning record

- Date: 2026-09-10
- Originally planned: 2026-09-07
- Last edited: 2026-09-11
- Status: Closed (superseded / merged into L1 standalone-link discovery and stdlib/runtime preparation and caching).
- Title: Add default managed stdlib discovery and explicit interface search roots to L1 standalone linking
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Compiler CLI / standalone linking / module graph / interface discovery
- Superseded by: [l1/work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][combined-plan]

## Supersession Record

Closed on 2026-09-10 by consolidation into **L1 standalone-link discovery and stdlib/runtime preparation and caching**.
This was an administrative planning closure. The authoritative combined plan owns implementation, integrated acceptance,
documentation, and architectural follow-through; its current status records that work.

Transferred scope includes interface-assisted transitive provider discovery; explicit-object and ordered `-I`
precedence; interface authority, opaque native inputs, dependency and operand ordering; managed stdlib/runtime
selection; shared preparation context and performance requirements; local cache ownership and integrity; CLI and
diagnostic planning; and all discovery and integrated acceptance criteria. The surviving plan also owns the planned
amendment to the authoritative-module-interface ADR and preserves external-input ownership and ordering.

The revised combined plan supplies bootstrap-owned semantic interfaces, one local derived native cache, conservative
reuse, a reduced preparation CLI and integrated contract alignment. It excludes cleanup/scrub, system caches and
installed native profiles. Read-only installed fixtures keep native preparation independent of installer implementation.
This supersession record alone does not represent implementation, and publication authorization boundaries are
unchanged.

## ADR Impact

- Decision: Consolidate unimplemented standalone-link discovery into one authoritative phased preparation/cache plan.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This closure changes planning ownership only; it implements or accepts no architectural change. All
    durable discovery contracts and future ADR amendment obligations are transferred to the combined plan, whose
    implementation closure records the resulting architectural decisions.

## References

[l1/work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][combined-plan]

[combined-plan]: 2026-09-07-stdlib-runtime-preparation-and-cache-noref.md
