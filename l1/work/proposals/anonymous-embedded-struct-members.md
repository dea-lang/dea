# Anonymous Embedded Struct Members Proposal

Version: 2026-07-25

Status: Proposed

## Summary

This proposal reopens whether L1 should support anonymous struct composition with promoted field access. The spelling
`_ : StructType` remains the motivating candidate, but neither that syntax nor its construction, lookup, ownership,
layout, ABI, or conversion semantics are accepted.

This is a design proposal, not an implementation plan. L1 already has enough language surface to reach its first
self-hosted Stage 2 fixed point, so this proposal must not delay the mechanical Stage 2 port. If the design is later
accepted, its normative rules must first graduate into L1 documentation and then into a new Stage 1-first feature plan
with future Stage 2 parity requirements.

## Current Problem

The [withdrawn feature plan] treated a single first-position `_ : StructType` member, flattened construction, promoted
field access, nested C layout, and collision rejection as implementation defaults. Those choices were made before the
current L1 surface included named constructor arguments, textual `.l1m` interfaces, canonical interface fingerprints,
opaque exports, and the current ownership and separate-compilation rules.

The current compiler also uses one resolved field list for several different purposes: physical C layout, recursive
ownership operations, constructor parameters, field lookup, interface emission, and fingerprinting. Anonymous embedding
would split that one view into at least:

- physical fields, including a nested base subobject;
- promoted logical selectors;
- constructor-visible parameters;
- interface and fingerprint records that preserve ABI-relevant structure.

The withdrawn plan did not decide how those views relate. It also did not establish enough practical value to justify
the added language and compiler complexity.

## Practical Value

The current compiler contains a few plausible but limited applications:

- `StructInfo` and `EnumInfo` in [l1/compiler/stage1_l0/src/types.l0][types] share the meaningful prefix `key`,
  `module_name`, `name`, `filename`, and `span`.
- `ParseResult` and `ImplParseResult` in [l1/compiler/stage1_l0/src/parser.l0][parser] and
  [l1/compiler/stage1_l0/src/parser/shared.l0][parser-shared] have the same five-field shape.
- `PreparedInput` and `BuildPreparedInput` duplicate a small entry-module and search-path bundle.
- Some stdlib records, maps, and sets share storage prefixes, although several existing wrappers contain pointers to
  their storage and therefore would not benefit from by-value-only embedding.

These examples show that anonymous composition could be used, but they do not establish that it would improve compiler
readability. Shared types, module-facade improvements, ordinary named composition, or future generics may be better
fits. The feature provides no Stage 2 expressiveness that the compiler currently lacks: the [Stage 2 self-hosting plan]
records a successful suffix-only feasibility port and a byte-identical retained-C fixed point.

## Candidate Direction

The motivating surface remains:

```l1
struct Shape { cx: double; cy: double };
struct Square { _: Shape; size: double };
```

One possible interpretation would let `square.cx` select `cx` through the embedded `Shape`. This example is
non-normative. It does not decide whether `square._` is legal, whether `Square` can be converted to `Shape`, how a
`Square` is constructed, or how either type is represented in an interface or ABI.

The proposal concerns anonymous composition and selector promotion. It does not by itself introduce classes, nominal
subtyping, methods, virtual dispatch, traits, or mixins. Documentation should avoid describing the feature as
inheritance unless a later proposal deliberately adds an `is-a` relationship.

## Open Questions

Every group below is a decision gate. An implementation plan must not open until all groups have accepted answers.

### 1. Declaration syntax and base access

1. Is `_ : T` the right declaration syntax, given that `_` currently denotes a wildcard elsewhere in L1?
2. Is the embedded subobject directly expressible as `value._`, or is it intentionally inaccessible as a value?
3. If `value._` is unavailable, what operation copies, passes, or otherwise observes the base subobject?
4. Would an explicit form such as `embed T` communicate the feature better and leave `_` with one language-wide role?

### 2. Eligible types and type relationships

1. Is embedding limited to a concrete struct value, or may aliases, imported structs, pointers, nullable values, enums,
   or opaque types appear?
2. Does the outer value support explicit base extraction by value or by pointer?
3. Is any implicit `Outer -> Base` or `Outer* -> Base*` conversion permitted?
4. If no conversion exists, is promoted field spelling alone valuable enough to justify the feature?

### 3. Cardinality, placement, and recursive embedding

1. May a struct contain one embedded member or several?
2. Must embedded members come first, or may they appear among ordinary fields?
3. Are fields promoted transitively through an embedding chain?
4. How are repeated base types, value-layout cycles, and excessively deep promotion chains handled?

### 4. Lookup, shadowing, and collisions

1. Does a direct outer field shadow a promoted field, or is every collision rejected?
2. How are collisions between two promoted paths resolved if multiple embedding is allowed?
3. Are field and future method names in one selector namespace?
4. Must the compiler retain the selected physical field path on the typed expression, or may the backend repeat lookup?

### 5. Construction and source compatibility

1. Does an outer constructor accept a complete base value, flattened base fields, or both?
2. How do named arguments identify the embedded value or its promoted fields?
3. Can an existing base value initialize the outer type without copying each field?
4. Does adding a field to the base change every outer constructor's arity or named-argument surface?
5. How should this interact with future struct literals, field defaults, and partial construction?

### 6. Ownership and value semantics

1. How do copy, move, retain, release, and `drop` traverse the embedded value?
2. Are promoted fields ordinary places for assignment and ownership analysis?
3. How do nullable or pointer-bearing bases affect cleanup and pointer-access validation?
4. Does existing by-value cycle detection operate on the physical member, the promoted view, or both?

### 7. Physical layout and ABI

1. Is storage nested, flattened, or selectable, and is the embedded subobject guaranteed to begin at offset zero?
2. How do nested tail padding, alignment, and `sizeof(Outer)` behave?
3. What stable synthetic C field name represents an anonymous member without exposing `_` as a C ABI identifier?
4. Which layout facts enter ABI compatibility and interface fingerprints?
5. Is changing the embedded base or its fields always an ABI-breaking change for the outer type?

### 8. Modules, interfaces, and visibility

1. How does an emitted `.l1m` distinguish a physical embedded member from an ordinary named member?
2. Must interface replay reconstruct promoted lookup paths exactly?
3. May a public struct embed a private, opaque, or selectively imported type?
4. Does a type alias preserve embedding identity, or only the resolved physical layout?
5. Which embedded and promoted names participate in public-surface fingerprinting?

### 9. Compiler representation and diagnostics

1. Does `StructInfo` retain separate physical, promoted, and constructor field views, or derive some views on demand?
2. How is the selected nested field path represented between type checking and backend lowering?
3. Which invalid forms are parser errors versus signature or typing errors?
4. Can diagnostics name an otherwise anonymous base and explain promotion paths without exposing backend names?

### 10. Adoption and future language evolution

1. Which compiler or stdlib types become materially clearer when rewritten with the accepted feature?
2. Should initial implementation require at least two reviewed production uses, or ship without internal adoption?
3. How would future methods, interfaces, traits, or nominal inheritance coexist with promoted fields?
4. Is anonymous composition still worthwhile after generics and improved module type sharing reduce current duplication?
5. When Stage 2 exists, how will Stage 1-first semantics and diagnostic parity be maintained without making the feature
   a prerequisite for the initial self-hosting fixed point?

## Alternatives

### Ordinary named composition

Keep `base: Shape` as an ordinary field and require `square.base.cx`. This is explicit, already supported, and exposes
the base value for copying and function calls without introducing promoted lookup.

### Explicit embedding syntax

Reserve a dedicated declaration form such as `embed Shape` rather than overloading `_`. This makes the language feature
searchable and leaves room to define base access independently from wildcard syntax.

### Shared helper types without promotion

Extract common record prefixes into explicitly named fields while preserving ordinary composition. This reduces
duplication without changing selector resolution.

### Defer to broader abstraction work

Wait for generics, improved module type sharing, traits, or another broader abstraction mechanism. Those features may
address the compiler's actual duplication more directly than field promotion.

## Diagnostic Policy

This proposal reserves no diagnostic codes.

The withdrawn plan's provisional `SIG-0240` to `SIG-0259` reservation is released. Its former `TYP-0780` to `TYP-0799`
suggestion is unavailable because that range now contains unsafe/plain function-type diagnostics. Any future
implementation plan must inspect the live diagnostic catalog and reserve fresh, non-overlapping ranges after the
language semantics have been accepted.

## Decision Criteria

The proposal is ready for acceptance only when:

1. every open-question group has a recorded answer;
2. construction, ownership, interface, fingerprint, and ABI behavior form one coherent model;
3. the design demonstrates clearer production code in concrete compiler or stdlib examples;
4. adding or changing a base field has a documented source- and binary-compatibility consequence;
5. the accepted surface does not require or delay the first L1 Stage 2 fixed point.

## Proposal Lifecycle

1. Link this proposal from [l1/docs/roadmap.md][roadmap] as unresolved language-core design work.
2. Keep stable grammar, ABI, ownership, and compiler documentation unchanged while the proposal remains open.
3. On acceptance, graduate the normative decisions into the appropriate L1 specs, references, and implementation
   documentation.
4. Create a new Stage 1-first feature plan only after those decisions are accepted; that plan must include future Stage
   2 parity and freshly checked diagnostic reservations.
5. On rejection, mark this proposal rejected and update the roadmap without reviving the withdrawn plan.

[parser]: ../../compiler/stage1_l0/src/parser.l0
[parser-shared]: ../../compiler/stage1_l0/src/parser/shared.l0
[roadmap]: ../../docs/roadmap.md
[stage 2 self-hosting plan]: ../../../work/plans/features/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md
[types]: ../../compiler/stage1_l0/src/types.l0
[withdrawn feature plan]: ../plans/features/closed/2026-04-22-anonymous-embedded-struct-members-noref.md
