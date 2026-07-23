# ADR-0013: Opaque Type Exports and Layout-Hiding Visibility

- Decision date: 2026-06-13
- Last edited: 2026-07-23
- Status: Accepted

## Context

L1 visibility is currently type-granular and all-or-nothing: a struct/enum is either exported (name and full layout,
every field accessible to importers) or not exported at all. There is no field-level visibility and no notion of an
abstract/opaque type. This decision refines [l1/docs/decisions/0009-module-visibility-exports-imports.md][adr-0009] by
adding an opaque rung and an exported-surface typing rule; it does not supersede it. The scope is the L1 module system,
separate compilation (`.l1m`), and signature/export resolution.

This baseline has a latent defect. Nothing checks that an exported signature only mentions exported types. An exported
`func f(p: T*)` whose `T` is not exported resolves cleanly today, because `sig_resolve_func` resolves parameter types
purely within the defining module's scope, against no export set. Under whole-source compilation this happens to work: a
consumer can call `f(g())` where `g` also yields a `T*`, with the pointer flowing through by inference and `T` never
being named. Under `.l1m`-based separate compilation (initiative 0001) the same program is unsound: the interface would
reference a type that is defined nowhere in it.

Separately, L1 has no way to intend the opaque-handle idiom. The behavior above only arises by accident, is
inference-only (the consumer cannot name `T`, so it cannot declare or store a `T*`), and silently makes a type cross a
module boundary that the author never exported.

L1 is unreleased; there are no external compatibility constraints. This is the moment to design the model correctly
rather than bolt a check onto the existing one.

## Decision

Adopt layout-hiding field visibility as the underlying model, and make opacity a derived property of it rather than a
distinct type-system primitive. `export opaque { T }` is introduced as sugar for "export the name, hide all fields."

### Visibility states

A nominal type has three effective states with respect to a consumer module:

| State                     | Spelling              | Name visible | Layout visible |
| ------------------------- | --------------------- | ------------ | -------------- |
| Unexported (module-local) | _(no export)_         | no           | no             |
| Opaque                    | `export opaque { T }` | yes          | no             |
| Transparent               | `export T`            | yes          | yes            |

`export T` retains its current meaning exactly (transparent), so existing code is unchanged.

### Governing principle

An importer's available operations on a type are a pure function of what the interface lets it see.

- Naming the type or forming a pointer to it: requires the name to be exported.
- Reading or writing a field: requires that field to be exported.
- Any layout-requiring operation (by-value parameter or return, copy, assignment, `sizeof`, construction): requires
  every field to be exported.

Consequently, on an opaque type an importer may name it and form, hold, receive, and pass pointers to it, but may not
construct, copy/assign by value, `sizeof`, dereference, or access fields. These are not special-cased prohibitions; the
operations are simply unavailable without a layout.

### Layout-hiding, not name-hiding

A hidden field hides the field's contribution to layout, not merely its name (the OCaml / Modula-3 / C-incomplete-type
reading, not the C++ "private is access control, layout still known" reading). This is the property that makes opacity
derivable and makes the `.l1m` self-consistent.

### Exported-surface typing rule

For any type `U` referenced by an exported item (a function signature parameter/return, or a visible field of an
exported aggregate):

- By pointer (`U*`): `U`'s name must be exported, opaque or transparent suffices.
- By value (direct parameter, return, field, array element, by-value enum payload): `U` must be transparent.
- An unexported `U` in either position is an error.

Violations are reported at the exporting item's definition, in the defining module: the module that created the leak,
not the consumer.

### Transitivity (aggregates)

To export a struct `S` transparently, its by-value layout closure must be transparent: follow every by-value field edge
(embedded structs, array elements, by-value enum payloads) and require each reached type to be transparent. The walk
stops at pointers whose pointee has a forward-declarable ABI spelling: such a pointer field places its pointee at the
frontier (must be >= opaque) but is not descended into. A synthesized by-value wrapper is not such a frontier. For
example, `U*?` is a nullable pointer and may name opaque `U`, whereas the pointee of `U?*` embeds `U` by value and
therefore requires `U` to be transparent.

The check is enforced one level deep at each export; full transitivity follows by induction, since a transparent export
is itself only legal when its by-value closure is transparent and its pointee frontier is >= opaque. An unexported
by-value intermediary therefore trips the rule at the first level, before any deeper type is reached.

### `.l1m` projection

Per exported type, the interface emits only its exported fields:

- opaque: a name-only (forward) declaration;
- transparent: the full definition.

The forward-decl-vs-full-def distinction is thus derived, not a separate emitter mode ("project the exported fields").
The interface is self-contained if and only if the typing rule holds: separate-compilation soundness by construction.

### `unsafe` is orthogonal

Opacity is a visibility property and is not gated by `unsafe`. `unsafe` answers "must the compiler trust an invariant it
cannot check?"; opacity answers "can the importer see this representation?" Holding and passing an opaque handle is
safe. The unsafe operation in this area is forging a handle (casting a raw pointer to an opaque pointer type), and
`unsafe` attaches to that cast, not to the opacity.

### Enums

Variants are the layout-determining members; the same rules apply with variants standing in for fields. Initially
all-or-none: all variants hidden yields an opaque enum that can be held but neither matched nor constructed.

### Implementation scope: endpoints only

A type is implemented as either transparent (no fields hidden) or fully opaque (all fields hidden, i.e.
`export opaque { T }`). Mixed/partial field visibility is specified but rejected with a not-yet-implemented diagnostic,
pending the offset-vs-accessor decision (see Open questions). The endpoints are cheap (all-public emits the layout
already produced today; zero-public emits only the name), while the partial case requires either emitting field offsets
(leaks partial layout, pins ABI) or accessor thunks.

## Rationale

- Separate compilation is sound by construction: a type can only enter the `.l1m` surface through a deliberate
  `export T` or `export opaque { T }`, so the interface never references a type it does not also define or
  forward-declare.
- Opacity is derived from visibility rather than introduced as a new type-system primitive, which keeps the type system
  unchanged and makes `export opaque` mere sugar for one point in the visibility space.
- Layout-hiding (not name-hiding) semantics is the load-bearing property: it is what lets an opaque type project as a
  forward declaration and what makes the by-value/by-pointer typing rule decidable one level deep.

## Considered alternatives

1. Gate opacity behind `unsafe`. Rejected: category error. There is no coherent attachment point: requiring `unsafe` at
   a safe handle call site is false and viral; placing it on the export gives it no semantic teeth. It also fails to
   address the by-value soundness problem (an `unsafe` marker does not give the importer a layout).
2. `opaque` as a distinct type-system primitive / third semantic state. Rejected in favor of deriving opacity from
   visibility. `opaque` is retained only as sugar for the all-fields-hidden point of the visibility space, which is not
   a separate state.
3. Private-by-default fields (Rust-style). Rejected: inverts the current contract, forces `pub` on every field of every
   plain-data / C-interop struct, and spends explicitness on the common case (exposing data) rather than the rare one
   (hiding a field to form a handle). Fields are visible-by-default within an exported type; hiding is opt-in.
4. Permit implicit unexported-by-pointer flow (the inference-only `f(g())` that works today). Rejected: it forces the
   compiler to emit an implicit forward declaration of a type the author never exported, breaking the property that the
   export surface is exactly and only what is written; and it is ergonomically crippled (the consumer cannot name the
   type). `export opaque { T }` is the explicit replacement.
5. "Sized-opaque" (export size/alignment, hide fields). Rejected/deferred: it would enable by-value embedding of a
   hidden type but pins the size as an early ABI commitment and complicates evolution. For a hidden type the only
   choices are transparent or by-pointer; there is no middle rung.
6. Declaration-site visibility modifiers vs. export-statement field lists. Leaning toward keeping visibility in the
   export statement (a single auditable locus, which matters because the `.l1m` surface is derived from it). Deferred to
   the partial-visibility work; not needed for endpoints-only.

## Consequences

Positive:

- Separate compilation is sound by construction; the original accidental-leak case is designed out: a type crosses a
  boundary only via `export T` or `export opaque { T }`, both written deliberately.
- The opaque-handle idiom is explicit, nameable, and storable on the consumer side.
- The export surface remains fully auditable from the declarations / `.l1m`.
- Zero migration: `export T` is unchanged.
- `unsafe` keeps a single precise meaning.
- The emitter rule collapses to "project the exported fields."

Negative / costs:

- New visibility semantics and corresponding checker work (the typing rule and the aggregate closure check).
- Partial field visibility is deferred; only the two endpoints are available initially (known limitation, not a defect).
- By-value embedding/use of a hidden type is foreclosed (no sized-opaque rung).
- No automated drift-guard yet against a handle type silently gaining a public field (see Open questions).

Neutral:

- Enums are constrained to all-or-none variant visibility initially.

## Implementation notes (spec and compiler deltas)

- `module-visibility-and-imports.md`: add the three-state model, the operation-availability principle, layout-hiding
  semantics, the exported-surface typing rule (by-value to transparent, by-pointer to >= opaque), the aggregate
  transitivity rule, the `export opaque` sugar, the enum treatment, the endpoints restriction, and the `unsafe`
  orthogonality note.
- `.l1m` projection (initiative 0001): emit exported fields only; opaque projects a forward declaration, transparent the
  full definition.
- Resolution (`sig_resolve_func`, `signatures.l0`): check each referenced type against the module export set with the
  by-value/by-pointer split; add the analogous aggregate-export (layout-closure, one-level) check.
- Diagnostics cover unexported types in exported signatures/aggregates and opaque types used by value. Mixed field
  visibility remains outside the current grammar because partial field visibility is deferred.
- Tests cover private types in public signatures, opaque-pointer round trips across modules, by-value rejection,
  nested-struct closure cases (by-value chain, pointer frontier, unexported intermediary), and `.l1m`
  forward-declaration emission for opaque types.

## Open questions / follow-ups

- Field-visibility syntax, once partial visibility lands: `export T hiding { ... }` vs. a positive list
  `export T { ... }`.
- Checked opacity assertion (drift-guard): an annotation meaning "I intend this type to project with no readable
  representation; error if any field is exported." A lint over the derived rule, not a new state. Add only if accidental
  public-field creep appears in practice.
- Read-only-but-visible fields (mutability vs. visibility as a separate axis): out of scope; separate ADR.
- Granularity between module-private and exported (submodule/friend visibility): tentatively no; the visibility doc
  should state this explicitly rather than by omission.

## Related Plans

- [l1/work/plans/features/closed/2026-06-13-opaque-type-exports-and-layout-hiding-noref.md][opaque-plan]: endpoints-only
  implementation (Completed).

## Related Initiatives

- [l1/work/initiatives/0001-separate-compilation-and-linking.md][initiative]: separate compilation and `.l1m` emission
  (Active).

## Related Decisions

- [l1/docs/decisions/0009-module-visibility-exports-imports.md][adr-0009]: the visibility/export/import model this ADR
  refines.

## Current Docs

- [l1/docs/specs/compiler/module-visibility-and-imports.md][visibility-spec]: normative spec, updated with the
  three-state visibility model.

[adr-0009]: 0009-module-visibility-exports-imports.md
[initiative]: ../../work/initiatives/0001-separate-compilation-and-linking.md
[opaque-plan]: ../../work/plans/features/closed/2026-06-13-opaque-type-exports-and-layout-hiding-noref.md
[visibility-spec]: ../specs/compiler/module-visibility-and-imports.md
