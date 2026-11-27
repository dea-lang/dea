# ADR-0028: Module-Scope Reservation of Intrinsic Names

- Decision date: 2026-11-26
- Last edited: 2026-11-27
- Status: Accepted

## Context

L0 implements `sizeof` and `ord` directly. A module could previously declare a function with either name, and the
compiler could silently lower a qualified call to the intrinsic. L1 supports shadowing intrinsics at module scope and
exposes them through `dea`. The same source could therefore call different operations at the two levels.

## Decision

Reserve `sizeof` and `ord` in L0's module symbol table. Reject a function, extern function, struct, enum, enum variant,
type alias or top-level `let` that introduces either name. Bare calls invoke the intrinsics. Qualified calls look up a
declaration owned by the named module. L0 provides no intrinsic module.

## Rationale

Checking declarations catches the conflict even in an unused import. This keeps ordinary qualified lookup uniform and
prevents an accepted L0 module-level declaration from changing the meaning of an intrinsic call under L1.

## Consequences

Previously accepted module declarations with these names must be renamed to compile as L0. Parameters, locals, pattern
bindings, fields and module path components can still use both identifiers. L1 retains its own shadowing rules.

## Related Plans

- [l0/work/plans/bug-fixes/closed/2026-11-21-module-qualified-lookup-noref.md](../../work/plans/bug-fixes/closed/2026-11-21-module-qualified-lookup-noref.md)

## Current Docs

- [l0/docs/reference/grammar.md](../reference/grammar.md)
- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md)
- [docs/specs/compiler/diagnostic-code-catalog.md](../../../docs/specs/compiler/diagnostic-code-catalog.md)
