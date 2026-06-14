# Dea/L1 Module Interface Format

Version: 2026-06-13

Status: Draft artifact contract

This document specifies the textual `.l1m` module interface artifact for the current Dea/L1 bootstrap compiler tranche.
It defines the on-disk file shape, canonical declaration order, type/literal formatting rules, the per-symbol dependency
manifest syntax, and the constrained parse contract shared by interface emission and round-trip tests.

This document does not make `.l1m` files normal user-facing compile inputs yet. Ordinary `--build` and `--run` flows
remain source-based until the separate-compilation driver surface lands under
[l1/work/initiatives/0001-separate-compilation-and-linking.md][initiative-0001].

## Scope

The current `.l1m` format exists to serialize one module's exported public surface in deterministic, human-readable
form:

- the emitter projects analyzed source into canonical text
- the constrained parser reconstructs the interface model from that text
- tests can assert byte-stable output and parser/emitter round-trip behavior
- the internal `--emit-interface` mode can write the artifact for developer/testing use

Hash strings are algorithm-tagged opaque tokens (for example `"sip13:F03142B8C9A7E6F1"`); the empty string `""` means no
compatibility check is performed. The fingerprint algorithm, the canonical hash inputs, and provider/consumer
verification are specified separately in
[l1/work/plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md][interface-fingerprints]. The
schema in this document reserves the hash slots; their values can be `""` until those compatibility checks are wired in.

## File Structure

Each interface file describes exactly one module:

```dea
module interface demo.main;
fingerprint "";

require iface_dep::RemotePoint == "";

link std.io::printl_s == "";

struct Point {
  x: int;
  y: int;
} == "";
```

The file has four regions in fixed order:

1. `module interface <dotted-module-name>;`
2. `fingerprint "<hash>";`
3. zero or more dependency lines, with `require` lines first and then `link` lines
4. zero or more exported declarations in canonical declaration-group order

The `module interface` header uses the module's canonical dotted source path. Filesystem discovery paths do not appear
inside the `.l1m` payload.

The fingerprint slot is always present. Until the fingerprint tranche lands it is emitted as the empty string `""`; the
parser accepts both `""` and any algorithm-tagged value such as `"sip13:F03142B8C9A7E6F1"` without changing the rest of
the file shape.

## Dependency Manifest

The dependency manifest records, per used provider symbol, the compatibility hash that the consumer was compiled
against. It is split into two tiers:

- **`require`**: surface-tier dependencies. The provider symbol is directly named in this module's exported public
  surface (a parameter, return, field, alias target, let/const type, or const value). A consumer that loads only this
  module's `.l1m` for type-checking must eventually resolve every `require` entry transitively.
- **`link`**: implementation-tier dependencies. The provider symbol is used by this module's implementation but does not
  appear in the public surface. Needed for link closure and initialization order, not for downstream typechecking.

A symbol that is both surface-named and implementation-named appears only as `require`.

Each dependency line names the provider symbol with a fully qualified `<provider_module>::<symbol_name>` token and
carries the expected algorithm-tagged compatibility hash:

```dea
require myapp.rectangle::Rectangle == "sip13:62649B8C7D5E4F3A";
link std.io::printl_s == "";
```

The `require` group is emitted first, then the `link` group. Within each group the lines are sorted by
`<provider_module>::<symbol_name>` and deduplicated.

The dependency manifest is **not** part of the whole-module fingerprint input: adding or removing a private import does
not change the module's own ABI hash and must not force consumers to recompile.

Today the emitter records direct uses only: the per-symbol compatibility hash captures transitive layout closure (when
populated), so the consumer's own dependency lines stay tied to symbols its surface actually names. The
implementation-tier `link` group is reserved by the schema; per-symbol tracking of implementation-only uses is not yet
populated by the emitter and is a follow-up owned by the build/run fan-out work. Until then `link` lines round-trip
through the parser but are not produced by `mi_project`.

## Export Surface

Only exported declarations appear in the `.l1m` file. The source `export` manifest is not reproduced verbatim as
`export ...;`; its effect is reflected only through which declarations are present.

The current implemented tranche emits transparent exported nominal types only. Source-level `export opaque T` is
specified in the visibility model but is not implemented yet, so this tranche does not parse or emit opaque interface
declarations.

The current `.l1m` surface includes:

- exported `struct` definitions
- exported `enum` definitions
- exported `type` aliases
- exported `func` signatures without bodies
- exported `const` declarations with canonical literal values
- exported top-level `let` declarations with type only

Local declarations and unexported top-level declarations are absent from the interface file.

## Canonical Declaration Order

Interfaces are emitted deterministically. Source declaration order does not control `.l1m` output order.

Declarations are grouped and sorted as follows:

1. structs, sorted by name
2. enums, sorted by name
3. type aliases, sorted by name
4. functions, sorted by name
5. consts, sorted by name
6. lets, sorted by name

This ordering is part of the `.l1m` contract so byte-identical public surfaces produce byte-identical interface files.

## Declaration Forms

Every declaration form carries a trailing per-symbol hash suffix `== "<hash>";`. The hash is opaque; until the
fingerprint tranche populates it, declarations emit `== ""`.

### Structs

Structs are emitted structurally with a trailing hash suffix:

```dea
struct Point {
  x: int;
  y: int;
} == "";
```

Field order is preserved from the analyzed source because layout is part of the imported type surface.

When source-level opaque exports are implemented, opaque structs will use an explicit name-only interface form:

```dea
opaque struct Handle == "";
```

Bodyless non-opaque declarations such as `struct Handle == "";` are not the intended representation and remain rejected.

### Enums

Enums are emitted structurally, including named variant payload fields:

```dea
enum Color {
  Red;
  Green;
  Rgb(red: int, green: int, blue: int);
} == "";
```

Variant payload fields carry the names from the analyzed source. The names appear in the textual form so consumers can
use named-argument construct syntax; they are not part of the per-symbol hash input.

When source-level opaque exports are implemented, opaque enums will use an explicit name-only interface form:

```dea
opaque enum State == "";
```

Bodyless non-opaque enum declarations such as `enum State == "";` are not the intended representation and remain
rejected.

### Type aliases

Type aliases use ordinary source-like syntax with the trailing hash:

```dea
type Dims = Size == "";
```

### Functions

Functions are signature-only declarations with the trailing hash:

```dea
func area(s: Size) -> int == "";
func ping() -> void == "";
```

Bodies are never emitted into `.l1m`.

### Consts

Consts include their declared type, canonical literal value, and the trailing hash:

```dea
const origin: Point = Point(0, 0) == "";
const zero_color: Color = Red == "";
```

### Lets

Top-level mutable storage is emitted with type only:

```dea
let current_offset: Point? == "";
```

## Type Formatting

The interface emitter uses one canonical textual type format:

- same-module nominal types are emitted unqualified: `Point`
- cross-module nominal types are emitted fully qualified: `std.integer::Value`
- pointer types use suffix `*`
- nullable types use suffix `?`
- function types use `func(T1, T2) -> U` or `unsafe func(T1, T2) -> U`
- `null` is a literal-only keyword and is not a valid interface type

When a nullable wrapper applies to a function type, the function type is parenthesized before `?`:

```dea
(func(int) -> int)?
```

Unsafe function signatures use the same formatting rules at both top level and in nested type positions:

```dea
unsafe func borrow_raw(ptr: void*) -> int;
let callback: unsafe func(byte*) -> int;
```

This formatting rule is shared by every declaration kind in the interface file.

## Const Literal Formatting

The current interface emitter serializes the full Stage 1 compile-time-constant subset:

- integer, bigint, real, byte, string, bool, and `null` literals
- zero-field enum variant references
- struct and enum constructor calls whose arguments are themselves interface literals

Canonical constructor emission uses comma-plus-space separators:

```dea
Point(0, 0)
Rgb(255, 0, 0)
```

Zero-field enum variants are emitted as bare references such as `Red` or qualified references when they name a
cross-module symbol.

## Parser Contract

The constrained `.l1m` parser accepts:

- the `module interface` header
- the `fingerprint` declaration (any string, including algorithm-tagged values such as `"sip13:<hex>"`)
- zero or more `require` lines followed by zero or more `link` lines
- top-level `struct`, `enum`, `type`, `func`, `const`, and `let`, each with a trailing `== "<hash>";` suffix

It rejects ordinary source-only forms such as function bodies. Dotted module names in the header and in dependency lines
are accepted and preserved.

The parser is currently transparent-only for nominal type declarations. Future opaque support will accept explicit
`opaque struct` and `opaque enum` declarations; opacity will not be inferred from a missing body.

Parser failures use the dedicated `PAR-0560` through `PAR-0576` diagnostic range registered in
[docs/specs/compiler/diagnostic-code-catalog.md][diagnostic-catalog].

## Non-goals

This format specification does not define:

- the fingerprint algorithm or object-metadata embedding
- the driver-side enforcement of per-symbol compatibility hashes
- driver search paths or `.l1m` discovery rules
- compile-only object output
- provider-object linking or build/run fan-out
- semantic population of implementation-tier `link` entries
- switching ordinary imports from source analysis to interface loading
- package or library distribution layout

[diagnostic-catalog]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[initiative-0001]: ../../../work/initiatives/0001-separate-compilation-and-linking.md
[interface-fingerprints]: ../../../work/plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md
