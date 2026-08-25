# Dea/L1 Module Visibility and Imports

Version: 2026-08-25

Status: Finalized

This document specifies the Dea/L1 module visibility model and the import forms used by separate compilation. It is the
source of truth for export manifests, alias imports, selective imports, the fingerprinted public surface projected into
textual `.l1m` module interfaces, and the separate ordered lifecycle-import projection.

The link-symbol spelling and C storage-class consequences are specified separately in
[`l1/docs/specs/compiler/abi.md`][abi]. The broader rollout is tracked by
[`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative-0001].

## Module Surface

Each `.l1` source file declares exactly one module:

```dea
module std.integer;
```

The module's dotted source path is its canonical identity for import resolution and LBI mangling. Filesystem paths,
search roots, and platform path separators are discovery details; they do not participate in symbol identity.

Top-level declarations are the only declarations that can be exported. This includes functions, structs, enums, type
aliases, top-level `let` bindings, and top-level `const` bindings. Local declarations inside functions are never part of
a module's exported surface.

## Export Manifest Syntax

A module may contain at most one export manifest, immediately after the `module` declaration and before any imports or
top-level declarations.

```dea
module example.api;

export abs, pi;
```

Supported forms:

```ebnf
ExportDecl ::= "export" "*" ";"
             | "export" ExportList ";"

ExportList ::= ExportItem ("," ExportItem)*
ExportItem ::= "opaque" "{" IdentList "}"
             | Ident

IdentList  ::= Ident ("," Ident)*
```

There is no per-declaration `pub` or `priv` modifier in L1. Visibility is fixed at the module level by this single
manifest.

The `opaque` modifier may prefix a brace-delimited list of exported type names (structs or enums) to export those names
while hiding their layouts; see [Type Visibility States](#type-visibility-states). For example:

```dea
export opaque { T };
export opaque { T, U }, make_t;
```

The brace group is the modifier's argument, not a general transparent grouping construct: `export { T, U };` is not
valid. Applying `opaque` to a non-type symbol, or under `export *;`, is rejected: `export *;` exports every name
transparently, and opacity must be requested per type name.

## Export Set Computation

The compiler computes one effective export set for each module:

1. `export *;` exports every top-level declaration, including names that begin with `_`.
2. `export a, b;` exports exactly the listed top-level declarations.
3. If no export manifest is present, every top-level declaration except `_`-prefixed names is exported.

An explicit export list is an allowlist, not a renaming mechanism. The listed names must resolve to top-level
declarations in the same module, and duplicate names in the list are rejected.

Enum variants are members of their owning declaration, not independently exportable top-level declarations. Exporting an
enum transparently exports every variant; exporting it opaquely or not exporting it exposes no variants. Under the
implicit rule, the owning enum's name determines visibility, so a public-looking variant cannot leak from an
underscore-prefixed private enum. Listing a variant directly in an explicit export manifest is rejected as a
non-top-level name.

Names beginning with `_` are private by default only under the implicit export rule. A module can intentionally publish
such a name with either `export *;` or an explicit list:

```dea
module internals.visible;

export _token;

const _token: int = 7;
```

## Type Visibility States

A nominal type (struct or enum) has three effective states with respect to a consumer module:

| State                     | Spelling              | Name visible | Layout visible |
| ------------------------- | --------------------- | ------------ | -------------- |
| Unexported (module-local) | _(no export)_         | no           | no             |
| Opaque                    | `export opaque { T }` | yes          | no             |
| Transparent               | `export T`            | yes          | yes            |

`export T` is transparent and matches the prior behavior exactly. An importer's available operations on a type are a
pure function of what the interface lets it see:

- Naming the type or forming a pointer to it requires the name to be exported (opaque or transparent).
- Reading or writing a field requires that field to be exported.
- Any layout-requiring operation (by-value parameter or return, copy, assignment, `sizeof`, construction, or `drop` of
  an owned pointee) requires every field to be exported, that is, a transparent type.

A hidden field hides the field's contribution to layout, not merely its name. On an opaque type an importer may name it
and form, hold, receive, and pass pointers to it, but may not construct it, copy or assign it by value, take its
`sizeof`, dereference it, access its fields, or apply `drop` directly to an owned pointer. Dropping the allocation must
run cleanup for any hidden owned fields, so opaque resources require a provider-exported destruction operation. These
are not special-cased prohibitions; the operations are simply unavailable without a visible layout.

### Exported-surface typing rule

For any type `U` referenced by an exported item (a function signature parameter or return type, or a visible field of an
exported aggregate):

- By pointer (`U*`): `U`'s name must be exported; opaque or transparent suffices.
- By value (direct parameter, return, field, array element, by-value enum payload): `U` must be transparent.
- An unexported `U` in either position is an error, reported at the exporting item's definition in the defining module
  (the module that created the leak, not the consumer).

Ordered suffix constructors preserve that layout distinction. `U*?` is a nullable pointer represented with the null
niche, so an opaque `U` is sufficient. `U?*` is instead a pointer to a non-pointer nullable wrapper; that wrapper embeds
`U` by value, so `U` must be transparent even though the wrapper itself is behind a pointer.

### Aggregate transitivity

To export a struct `S` transparently, its by-value layout closure must be transparent: follow every by-value field edge
(embedded structs, array elements, by-value enum payloads) and require each reached type to be transparent. The walk
stops at pointers whose pointee has a forward-declarable ABI spelling: such a pointer field places its pointee at the
frontier (the pointee's name must be exported, opaque or transparent) but is not descended into. A synthesized by-value
wrapper such as the pointee of `U?*` is not such a frontier because defining the wrapper requires `U`'s layout.

The check is enforced one level deep at each export; full transitivity follows by induction, since a transparent export
is itself legal only when its by-value closure is transparent and its pointee frontier names are exported.

### Enums

Enum variants are the layout-determining members; the same rules apply with variants standing in for fields. Variant
visibility is all-or-none initially: hiding all variants yields an opaque enum that can be held and pointed to but
neither matched nor constructed. The effective variant export set is therefore derived from the owning enum's
transparent or opaque state.

### Implementation scope

A type is either transparent (no fields hidden) or fully opaque (all fields hidden, spelled `export opaque { T }`).
Mixed or partial field visibility is specified by this model but rejected with a not-yet-implemented diagnostic, pending
a future field-visibility syntax. There is no "sized-opaque" rung that exports size and alignment while hiding fields;
for a hidden type the only choices are transparent or by-pointer.

### Relationship to `unsafe`

Opacity is a visibility property and is not gated by `unsafe`. Holding and passing an opaque handle is safe. The unsafe
operation in this area is forging a handle by casting a raw pointer to an opaque pointer type; `unsafe` attaches to that
cast, not to the opacity. See [`l1/docs/decisions/0010-unsafe-marker-and-raw-pointer-indexing.md`][unsafe-adr].

## Interface Projection

The effective export set defines the public-declaration portion of the textual `.l1m`. The export manifest itself is not
emitted into the interface file as an `export ...;` statement; only the resulting exported declarations are projected
into that portion in canonical form.

Equivalent export-manifest spellings that yield the same effective public declarations yield the same canonical
declaration projection and public fingerprint. Equal public declarations alone do not guarantee byte-identical `.l1m`
text because module identity and the operational `entry`, ordered `import module`, `require`, and `link` regions are
also serialized.

An interface file begins with:

```dea
module interface std.integer;
fingerprint "sip13:0123456789abcdef";
```

The public declaration surface follows non-fingerprinted operational regions for optional `entry;`, ordered
`import module` records, and `require` / `link` provider expectations. Entry and provider manifests can change interface
bytes and executable lifecycle behavior without changing the public fingerprint.

The remaining declarations are the exported surface needed by importers:

- exported transparent `struct` and `enum` definitions, including their structural layout;
- exported opaque `struct` and `enum` types as name-only forward declarations, with no fields or variants;
- exported function signatures without bodies;
- exported `const` declarations with literal values;
- exported top-level `let` declarations with type information;
- exported type aliases, when present in the source surface.

Interface emission is deterministic. Declaration order in source does not affect the canonical `.l1m` order or the
fingerprint computed over that public surface.

Every resolved non-virtual source import is lifecycle-bearing, including an import used only for side effects. The
module graph retains direct imports in exact source declaration order, including duplicates. Interface projection walks
that vector without mutating it, omits compiler-synthesized virtual providers, retains only the first occurrence of each
remaining provider, and emits that stable canonical order as `import module` records. `require` and `link` remain
separate symbol-dependency views and never create lifecycle edges.

The interface fingerprint covers only canonical exported declarations. It excludes module identity, `entry`, ordered
module imports, `require`, `link`, all source-level import spelling and order, and native-object contents.

## Import Forms

L1 supports three import forms:

```dea
import std.integer;
import std.integer as math;
import abs, pi from std.integer;
```

Grammar:

```ebnf
ImportDecl ::= "import" ModulePath ";"
             | "import" ModulePath "as" Ident ";"
             | "import" IdentList "from" ModulePath ";"
```

Each import binds only symbols from the provider module's exported surface. A consumer cannot access a provider's
non-exported top-level declarations through any import form.

## Open Imports

A plain import opens the provider's exported names into the consumer's unqualified scope and also permits qualified
lookup through the provider module path:

```dea
import std.integer;

func main() -> int {
    return abs(-4) + std.integer::abs(-5);
}
```

The qualified path is the canonical imported module path, not a filesystem path. Open imports are convenient for small
modules and preserve the existing qualified-name disambiguation surface.

## Alias Imports

An alias import binds the provider module under a local namespace only:

```dea
import std.integer as math;

func main() -> int {
    return math::abs(-4);
}
```

An alias import does not introduce the provider's exported names as unqualified bindings. In the example above,
`abs(-4)` is unresolved unless another import or local declaration supplies `abs`.

Aliases are local to the importing module. They do not change the provider module's canonical identity, `.l1m` path,
fingerprint, or LBI-mangled link names. `math::abs` still binds to the provider-owned symbol for `std.integer::abs`.

## Selective Imports

A selective import binds only the named exports as unqualified imported symbols:

```dea
import abs, pi from std.integer;

func circumference(radius: int) -> int {
    return 2 * pi * abs(radius);
}
```

Every selected name must be exported by the provider. Selective imports do not bind a qualified namespace, so
`std.integer::abs` is not made available by the statement above. Use a separate open or alias import when qualified
access is also desired.

Selective imports are ordinary imported bindings in the consumer's scope. Collisions with local declarations, aliases,
or other imported names are diagnosed by name resolution using the same deterministic ambiguity rules as other imports.

## Mixed Forms

Import forms do not combine in one statement. These are intentionally separate:

```dea
import std.integer as math;
import abs from std.integer;
```

There is no syntax for `import abs from std.integer as math;`, wildcard selective imports, import-time renaming, or
grouped imports from multiple modules.

## Resolution Rules

Name resolution follows these rules:

1. A provider module is first resolved by its canonical dotted module path.
2. The provider's exported surface is loaded from source analysis or from a verified `.l1m` interface according to the
   active resolution policy.
3. Open imports contribute all exported names to the consumer's unqualified imported scope and permit
   `<module.path>::name` qualified lookup.
4. Alias imports contribute exactly one local module namespace, addressable as `<alias>::name`.
5. Selective imports contribute exactly the requested exported names to the consumer's unqualified imported scope.
6. A binding introduced by an import always points back to the provider declaration and provider-owned link identity.

Import aliases and selected names are source-level conveniences for the consumer. They never rewrite the provider's
module path or exported symbol name.

## Linkage Interaction

The export set also controls generated C linkage:

- exported functions and top-level storage keep external linkage;
- non-exported top-level functions and storage use internal linkage where the backend can represent that with `static`;
- imported non-extern L1 declarations reference provider-owned LBI names; C `extern` declarations retain their declared
  C spelling.

For example, `import std.integer as m;` followed by `m::abs(-1)` still calls the LBI symbol for `std.integer::abs`, such
as `__deaM3std7integerN3absF1ii`. The local alias `m` is not encoded into generated C symbol names.

Struct and enum type definitions have no C storage class. A type's visibility state determines its presence and form in
the public interface: unexported types are absent, opaque types appear as name-only forward declarations, and
transparent types appear with full layout. LBI naming gives generated C type spellings deterministic module identity.

Standalone link consumes only verified sibling interfaces for Dea identity and lifecycle semantics. The paired native
object remains opaque; it is not inspected to reconstruct visibility, imports, fingerprints, or entry presence.

## Non-Goals

This visibility and import model does not introduce:

- packages, registries, lock files, or dependency manifests;
- mixed or partial per-field visibility, and any "sized-opaque" type that exports size and alignment while hiding
  fields;
- import-time renaming of individual symbols;
- wildcard selective imports such as `import * from std.integer;`;
- per-declaration visibility modifiers;
- access to non-exported declarations through friend, internal, or package scopes;
- C FFI visibility controls.

[abi]: abi.md
[initiative-0001]: ../../../work/initiatives/0001-separate-compilation-and-linking.md
[unsafe-adr]: ../../decisions/0010-unsafe-marker-and-raw-pointer-indexing.md
