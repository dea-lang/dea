# ADR-0003: C ABI Naming Policy

- Decision date: 2026-04-04
- Last edited: 2026-07-11
- Status: Accepted

## Context

The L1 bootstrap compiler inherited `l0_*` / `L0_*` / `_l0_*` / `_L0_*` prefixes from the L0 codebase it was copied
from. These prefixes are misleading in L1 context and would create confusion about which level owns a given symbol.

A clean naming policy was needed before the L1 public ABI surface grew large enough to make migration painful.

## Decision

The canonical C ABI naming convention for L1 generated and runtime code is:

- `dea_*`: public generated/runtime C identifiers.
- `DEA_*`: public generated/runtime preprocessor names.
- `rt_*`: stable public runtime API functions.
- `_rt_*`: private runtime helper functions.

Historical `l0_*`, `L0_*`, `_l0_*`, and `_L0_*` names are not part of the L1 ABI. The emitter reserves both the
historical prefixes and the current `dea_*` prefixes when mangling user/source identifiers, so generated C cannot
collide with backend/runtime-owned namespaces.

The internal SipHash include uses `dea_siphash.h` (level-local, future-neutral name) so L1 carries no legacy-prefixed
include.

## Rationale

- `dea_*` reflects the Dea project identity rather than the L0 implementation origin, making the L1 public ABI
  forward-compatible with future language evolution.
- Reserving both old and new prefixes in the mangler prevents accidental user-identifier collisions with both the old
  and new ABI namespaces.
- Migrating early, before the ABI surface was large, minimized the diff.

## Consequences

- All L1 generated code uses `dea_*` / `DEA_*` prefixes; `l0_*` names in the L1 runtime are migration bugs, not accepted
  artifacts.
- New L1 runtime symbols must follow the `rt_*` / `_rt_*` convention.
- The LBI mangling scheme (see [ADR-0008][adr-lbi]) builds on this namespace policy.

## Related Plans

- [l1/work/plans/features/closed/2026-04-04-l1-dea-c-abi-prefix-migration-noref.md][abi-migration]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §4 (C ABI naming policy)

[abi-migration]: ../../work/plans/features/closed/2026-04-04-l1-dea-c-abi-prefix-migration-noref.md
[adr-lbi]: 0008-lbi-symbol-mangling.md
[design-decisions]: ../reference/design-decisions.md
