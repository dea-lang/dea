# ADR-0019: Shared Standard-Library Naming and Compatibility Policy

- Decision date: 2026-05-13
- Last edited: 2026-07-27
- Status: Accepted

## Context

Before Dea's public standard-library compatibility surface hardened, several shared names encoded obsolete intent or
used inconsistent word order. `sys.unsafe` conflicted with reserving `unsafe` for language syntax even though the module
provided memory primitives. The integer-focused `std.math` name obscured its separation from `std.real`. A few
specialized containers used container-first names while the prevailing convention placed specialized type names before
the container.

A compatibility transition could preserve old spellings through forwarding modules, aliases, or parallel helper
families. Doing so before release commitments, however, would make two public names appear equally valid, complicate
module identity and generated symbol naming, and leave a compatibility surface that later work must maintain.

## Decision

Shared public standard-library names are intent-revealing and follow one canonical ordering:

- memory primitives live in `sys.memory`, not `sys.unsafe`;
- integer helpers live in `std.integer`, while floating-point helpers remain in `std.real`; and
- specialized container types use type components before the container name, such as `StringVector`,
  `StringStringLinearMap`, and `IntStringLinearMap`.

Specialized entry types and helper prefixes follow the same ordering as their public container types.

While the affected language and standard-library surfaces are pre-release, these naming migrations are hard source
breaks. Active code keeps no forwarding module, type alias, function alias, or mixed old/new transition period. Module
declarations, imports, qualified names, docs, fixtures, helper prefixes, and module-derived generated identities move
atomically to the canonical spelling.

A naming migration does not by itself change helper semantics, ownership, runtime C ABI, or the underlying generic
container APIs. Historical closed documents may retain old spellings when they describe the state that existed at the
time.

## Rationale

- Intent-revealing modules reserve language vocabulary cleanly and make the module's domain visible at an import site.
- Type-before-container ordering gives specialized collections a predictable family resemblance.
- One canonical spelling prevents obsolete and preferred APIs from becoming long-lived peers.
- A pre-release hard break is cheaper and clearer than carrying shims until an unspecified compatibility deadline.
- Keeping the migration naming-only separates source identity changes from semantic, ownership, and runtime ABI changes.

## Consequences

- Active L0 and L1 sources and documentation use the same canonical shared module and container names.
- Code written against an old spelling must be migrated; it does not compile through a compatibility alias.
- Module-path changes update module-derived L1 mangled names and ABI examples even when runtime helper symbols are
  unchanged.
- Search-based validation is part of a rename: unexplained old spellings in active source indicate an incomplete
  migration.
- Historical plans can mention `sys.unsafe`, `std.math`, or old container names without making them current API aliases.
- Future post-release renames require a fresh compatibility decision; this ADR does not grant a general right to break
  established public APIs without migration policy.

## Related Plans

- [work/plans/refactors/closed/2026-05-08-sys-memory-rename-noref.md](../../work/plans/refactors/closed/2026-05-08-sys-memory-rename-noref.md):
  renamed `sys.unsafe` to `sys.memory` without a shim
- [work/plans/refactors/closed/2026-05-09-shared-stdlib-container-type-renames-noref.md](../../work/plans/refactors/closed/2026-05-09-shared-stdlib-container-type-renames-noref.md):
  normalized specialized containers and helper families to type-before-container order
- [work/plans/refactors/closed/2026-05-13-shared-std-math-to-std-integer-rename-noref.md](../../work/plans/refactors/closed/2026-05-13-shared-std-math-to-std-integer-rename-noref.md):
  renamed the shared integer helper module to `std.integer` without a compatibility module
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the historical decision into the ADR catalog

## Current Docs

- [l0/docs/decisions/0015-stdlib-module-boundaries.md](../../l0/docs/decisions/0015-stdlib-module-boundaries.md): L0
  standard-library module ownership
- [l0/docs/reference/standard-library.md](../../l0/docs/reference/standard-library.md): canonical L0 modules,
  containers, and helper names
- [l1/docs/reference/standard-library.md](../../l1/docs/reference/standard-library.md): canonical L1 modules,
  containers, and helper names
- [docs/reference/style-guide.md](../reference/style-guide.md): shared source naming conventions
