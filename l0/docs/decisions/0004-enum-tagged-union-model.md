# ADR-0004: Enum and Tagged-Union Model

- Decision date: 2025-12-06
- Last edited: 2026-05-20
- Status: Accepted

## Context

L0 programs need to represent values that are one of a fixed set of variants, each potentially carrying different
payload data. The question was what model to use for sum types and how to expose variant construction and inspection.

## Decision

L0 enums are tagged unions: a discriminant tag plus a union payload. The grammar is:

```
EnumDecl        ::= "enum" Ident "{" EnumVariantDecl* "}"
EnumVariantDecl ::= Ident VariantFields? ";"
VariantFields   ::= "(" VariantField ("," VariantField)* ")"
VariantField    ::= Ident ":" Type
```

Semantics:

- A variant with no payload fields is a unit variant; its name is used as a value expression directly.
- A variant with payload fields is constructed by calling the variant name as a function:
  `VariantName(field: value, ...)`.
- Pattern matching in `match` destructures enum values. Patterns bind variant payload fields to local names.
- No exhaustiveness checking beyond match-case completeness; the language is conservative here.
- The generated C representation uses a C `int` tag and a `union` of payload structs.

## Rationale

- Tagged unions model the intent directly: one tag, one payload, no ambiguity about which payload is active.
- Using a named-field payload (not positional) makes construction and pattern matching self-documenting.
- Generating a C `int` tag and a `union` keeps the lowering straightforward and portable across C99 targets.
- Avoiding built-in exhaustiveness checking keeps the early bootstrap implementation tractable; it can be added later.

## Consequences

- Pattern matching in `match` is the primary way to branch on enum variants; there is no implicit coercion or implicit
  tag access outside of `match`.
- Payload field names must be unique within a variant but can be reused across variants of the same enum.
- The C backend emits one `struct` per variant payload and one `union` wrapping all variant structs.

## Related Plans

None (pre-plan era).

## Current Docs

- [l0/docs/reference/grammar.md](../reference/grammar.md): §3.4 (enum grammar), §5.5 (match statement)
- [l0/docs/reference/architecture.md](../reference/architecture.md): backend lowering for enum types
