# ADR-0008: LBI Symbol Mangling

- Decision date: 2026-04-24
- Last edited: 2026-05-20
- Status: Accepted

## Context

L1 supports separate compilation and external library linking. When L1 modules are compiled to object files, their
exported symbols must have stable, predictable C names that encode enough type information to detect ABI mismatches at
link time without requiring a separate metadata file.

## Decision

The Language Boundary Interface (LBI) uses a tagged-section mangling scheme defined in `l1/docs/specs/compiler/abi.md`.
Key properties:

- Each exported L1 symbol is mangled into a unique C identifier encoding the module path, function name, and signature.
- The mangling grammar is recursive and handles nested types, pointers, nullable types, array types, and function
  pointer types.
- The emitter reserves the `dea_*` / `DEA_*` namespace (from [ADR-0002][adr-abi]) and the historical `l0_*` namespace in
  user-identifier mangling to prevent collisions.
- Linkage is export-driven: a symbol is exported only when it appears in the module's export manifest.

The mangling scheme was later unified into a single recursive grammar (initiative
[l1/work/initiatives/closed/0002-runtime-static-library.md][runtime-lib]) that handles all suffix combinations in
source-significant order.

## Rationale

- A stable, self-describing mangling scheme allows object files compiled by different tool invocations to link correctly
  without external metadata.
- Recursive grammar is simpler to specify and implement than a flat ad-hoc encoding that special-cases each type
  combination.
- Export-driven linkage keeps the ABI surface minimal: only explicitly exported symbols are visible at link time.

## Consequences

- All L1 object files follow the LBI mangling scheme; any change to the scheme is an ABI break.
- The normative specification in `l1/docs/specs/compiler/abi.md` is the single source of truth for the mangling
  algorithm.
- Mangling is validated by the test suite; golden fixtures are regenerated when the scheme changes intentionally.

## Related Plans

- [l1/work/plans/features/closed/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md][lbi-mangling]
- [l1/work/plans/refactors/closed/2026-05-11-unified-lbi-mangling-noref.md][lbi-unified]

## Current Docs

- [l1/docs/specs/compiler/abi.md][abi]: normative LBI mangling specification

[abi]: ../specs/compiler/abi.md
[adr-abi]: 0002-c-abi-naming-policy.md
[lbi-mangling]: ../../work/plans/features/closed/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md
[lbi-unified]: ../../work/plans/refactors/closed/2026-05-11-unified-lbi-mangling-noref.md
[runtime-lib]: ../../initiatives/closed/0002-runtime-static-library.md
