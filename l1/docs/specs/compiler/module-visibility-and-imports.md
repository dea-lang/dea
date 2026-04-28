# Dea/L1 Module Visibility and Imports

Version: 2026-04-28

Status: Finalized

This document specifies the Dea/L1 module visibility model and the import forms used by separate compilation. It is the
source of truth for export manifests, alias imports, selective imports, and the public surface projected into textual
`.l1m` module interfaces.

The link-symbol spelling and C storage-class consequences are specified separately in
[`l1/docs/specs/compiler/abi.md`][abi]. The broader rollout is tracked by
[`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative-0001].

## Module Surface

Each `.l1` source file declares exactly one module:

```dea
module std.math;
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
             | "export" IdentList ";"

IdentList  ::= Ident ("," Ident)*
```

There is no per-declaration `pub` or `priv` modifier in L1. Visibility is fixed at the module level by this single
manifest.

## Export Set Computation

The compiler computes one effective export set for each module:

1. `export *;` exports every top-level symbol, including names that begin with `_`.
2. `export a, b;` exports exactly the listed top-level symbols.
3. If no export manifest is present, every top-level symbol except `_`-prefixed names is exported.

An explicit export list is an allowlist, not a renaming mechanism. The listed names must resolve to top-level
declarations in the same module, and duplicate names in the list are rejected.

Names beginning with `_` are private by default only under the implicit export rule. A module can intentionally publish
such a name with either `export *;` or an explicit list:

```dea
module internals.visible;

export _token;

const _token: int = 7;
```

## Interface Projection

The effective export set defines the public `.l1m` interface surface. The export manifest itself is not emitted into the
interface file as an `export ...;` statement. Instead, the `.l1m` contains only exported declarations in canonical form.

Two modules with the same effective public declarations produce the same interface text regardless of whether the source
used `export *;`, an explicit allowlist, or the implicit default.

An interface file begins with:

```dea
module interface std.math;
fingerprint "0000000000000000";
```

The remaining declarations are the exported surface needed by importers:

- exported `struct` and `enum` definitions, including their structural layout;
- exported function signatures without bodies;
- exported `const` declarations with literal values;
- exported top-level `let` declarations with type information;
- exported type aliases, when present in the source surface.

Interface emission is deterministic. Declaration order in source does not affect the canonical `.l1m` order or the
fingerprint computed over that public surface.

## Import Forms

L1 supports three import forms:

```dea
import std.math;
import std.math as math;
import abs, pi from std.math;
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
import std.math;

func main() -> int {
    return abs(-4) + std.math::abs(-5);
}
```

The qualified path is the canonical imported module path, not a filesystem path. Open imports are convenient for small
modules and preserve the existing qualified-name disambiguation surface.

## Alias Imports

An alias import binds the provider module under a local namespace only:

```dea
import std.math as math;

func main() -> int {
    return math::abs(-4);
}
```

An alias import does not introduce the provider's exported names as unqualified bindings. In the example above,
`abs(-4)` is unresolved unless another import or local declaration supplies `abs`.

Aliases are local to the importing module. They do not change the provider module's canonical identity, `.l1m` path,
fingerprint, or LBI-mangled link names. `math::abs` still binds to the provider-owned symbol for `std.math::abs`.

## Selective Imports

A selective import binds only the named exports as unqualified imported symbols:

```dea
import abs, pi from std.math;

func circumference(radius: int) -> int {
    return 2 * pi * abs(radius);
}
```

Every selected name must be exported by the provider. Selective imports do not bind a qualified namespace, so
`std.math::abs` is not made available by the statement above. Use a separate open or alias import when qualified access
is also desired.

Selective imports are ordinary imported bindings in the consumer's scope. Collisions with local declarations, aliases,
or other imported names are diagnosed by name resolution using the same deterministic ambiguity rules as other imports.

## Mixed Forms

Import forms do not combine in one statement. These are intentionally separate:

```dea
import std.math as math;
import abs from std.math;
```

There is no syntax for `import abs from std.math as math;`, wildcard selective imports, import-time renaming, or grouped
imports from multiple modules.

## Resolution Rules

Name resolution follows these rules:

1. A provider module is first resolved by its canonical dotted module path.
2. The provider's exported surface is loaded from source analysis today and from `.l1m` interfaces in separate
   compilation.
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
- imported declarations reference provider-owned LBI names.

For example, `import std.math as m;` followed by `m::abs(-1)` still calls the LBI symbol for `std.math::abs`, such as
`__deaM3std4mathS3abs`. The local alias `m` is not encoded into generated C symbol names.

Struct and enum type definitions have no C storage class. Their exported-vs-private status determines whether they are
present in the public interface, while LBI naming gives generated C type spellings deterministic module identity.

## Non-Goals

This visibility and import model does not introduce:

- packages, registries, lock files, or dependency manifests;
- import-time renaming of individual symbols;
- wildcard selective imports such as `import * from std.math;`;
- per-declaration visibility modifiers;
- access to non-exported declarations through friend, internal, or package scopes;
- C FFI visibility controls.

[abi]: abi.md
[initiative-0001]: ../../../work/initiatives/0001-separate-compilation-and-linking.md
