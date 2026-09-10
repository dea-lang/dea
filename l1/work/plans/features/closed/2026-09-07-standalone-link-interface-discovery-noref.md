# Feature Plan

## Standalone-link discovery: superseded planning record

- Date: 2026-09-10
- Originally planned: 2026-09-07
- Last edited: 2026-09-10
- Status: Closed (superseded / merged into L1 standalone-link discovery and stdlib/runtime preparation and caching).
- Title: Add default managed stdlib discovery and explicit interface search roots to L1 standalone linking
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Compiler CLI / standalone linking / module graph / interface discovery
- Superseded by: [l1/work/plans/features/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][combined-plan]

## Supersession Record

Closed on 2026-09-10 by consolidation into **L1 standalone-link discovery and stdlib/runtime preparation and caching**.
This is an administrative planning closure, not completed implementation. The authoritative plan remains Draft and owns
all implementation, integrated acceptance, documentation, and architectural follow-through.

Transferred scope includes interface-assisted transitive provider discovery; explicit-object and ordered `-I`
precedence; interface authority, opaque native inputs, dependency and operand ordering; managed stdlib/runtime
selection; shared preparation context and performance requirements; cache ownership, integrity, and scoped maintenance;
CLI and diagnostic planning; and all discovery and integrated acceptance criteria. The surviving plan also owns the
planned amendment to the authoritative-module-interface ADR and preserves external-input ownership and ordering.

The implementation sequence is interface discovery with caller-prepared fixtures, preparation/cache foundations and
explicit preparation, cleanup/scrub, managed-provider integration and bootstrap prewarming, then integrated acceptance
and closure. Installed-root fixtures keep the feature independent of installer implementation. No feature is represented
as shipped by this supersession, and publication authorization boundaries are unchanged.

## ADR Impact

- Decision: Consolidate unimplemented standalone-link discovery into one authoritative phased preparation/cache plan.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This closure changes planning ownership only; it implements or accepts no architectural change. All
    durable discovery contracts and future ADR amendment obligations are transferred to the active combined plan, where
    they remain subject to integrated acceptance and implementation closure.

## References

[l1/work/plans/features/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][combined-plan]

[combined-plan]: ../2026-09-07-stdlib-runtime-preparation-and-cache-noref.md
