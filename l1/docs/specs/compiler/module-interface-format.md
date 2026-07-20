# Dea/L1 Module Interface Format

Version: 2026-07-20

Status: Draft artifact contract

This document specifies the textual `.l1m` module interface artifact for the current Dea/L1 bootstrap compiler tranche.
It defines the on-disk file shape, canonical declaration order, type/literal formatting rules, the per-symbol dependency
manifest syntax, and the constrained parse, discovery, and transitive-closure contracts.

This document does not make `.l1m` files normal user-facing compile inputs yet. `-c` remains gated without producing
artifacts, while ordinary `--build` and `--run` flows remain source-based under
[l1/work/initiatives/0001-separate-compilation-and-linking.md][initiative-0001].

## Scope

The current `.l1m` format exists to serialize one module's exported public surface in deterministic, human-readable
form:

- the emitter projects analyzed source into canonical text
- the constrained parser reconstructs the interface model from that text
- internal analysis entry points can discover interfaces from ordered roots and recursively load dependency closure
- programmatic supplied-interface registries use the same graph contract for focused semantic tests
- tests can assert byte-stable output and parser/emitter round-trip behavior
- the internal `--emit-interface` mode can write the artifact for developer/testing use

The current parser treats every hash string as an opaque token and preserves it byte-for-byte. Examples use the planned
canonical spelling `sip13:<16 lowercase hexadecimal digits>`, such as `"sip13:f03142b8c9a7e6f1"`; the emitter uses the
empty string `""` as its placeholder. No compatibility check is performed in the current tranche, and the parser does
not validate the tag, digest, or casing. The fingerprint algorithm, canonical hash inputs, and future provider/consumer
verification are specified separately in
[l1/work/plans/features/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref][interface-fingerprints].
The schema in this document reserves the hash slots; their values can be `""` until those compatibility checks are wired
in.

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
parser accepts `""`, canonical-looking values such as `"sip13:f03142b8c9a7e6f1"`, and non-canonical strings without
changing the rest of the file shape. Operational verification will require the tag and canonical lowercase spelling; an
untagged digest will not select an implicit algorithm.

## Dependency Manifest

The dependency manifest records, per used provider symbol, the compatibility hash that the consumer was compiled
against. It is split into two tiers:

- **`require`**: surface-tier dependencies. The provider symbol is directly named in this module's exported public
  surface (a parameter, return, field, alias target, let/const type, or const value). A consumer that loads only this
  module's `.l1m` for type-checking must eventually resolve every `require` entry transitively.
- **`link`**: implementation-tier dependencies. The provider symbol is used by this module's implementation but does not
  appear in the public surface. Needed for link closure, not for downstream typechecking. Initialization order instead
  follows the graph's exact ordered direct-import sequence.

A symbol that is both surface-named and implementation-named appears only as `require`.

Each dependency line names the provider symbol with a fully qualified `<provider_module>::<symbol_name>` token and an
opaque compatibility-hash slot. The planned fingerprint tranche defines a populated slot as the provider module's
canonical tagged whole-module fingerprint:

```dea
require myapp.rectangle::Rectangle == "sip13:62649b8c7d5e4f3a";
link std.io::printl_s == "";
```

The `require` group is emitted first, then the `link` group. Within each group the lines are sorted by
`<provider_module>::<symbol_name>` and deduplicated.

The dependency manifest is **not** part of the whole-module fingerprint input: adding or removing a private import does
not change the module's own ABI hash and must not force consumers to recompile.

The emitter classifies resolved cross-module symbol references into these tiers. References that appear in the exported
surface become `require`; other implementation references become `link`; and `require` wins when the same provider
symbol appears in both. It copies the provider's whole-module fingerprint string into each entry when one is available,
but computes neither a per-symbol nor a whole-module fingerprint. Empty provider placeholders therefore remain valid
until the fingerprint tranche lands.

Public-surface collection walks parsed type references so an imported alias remains the dependency identity instead of
being replaced by its nominal target. It covers exported layouts and signatures, exported binding types, and exported
const initializers even when their scalar value was folded. Enum variant references normalize to their owning enum.
Parsed interface expectation strings are preserved verbatim during replay.

## Interface Discovery and Closure

The internal module-graph resolver applies these rules:

1. The requested compilation target is source-backed even if a matching interface exists.
2. For each imported canonical module, ordered interface roots are searched for the dotted relative path with an `.l1m`
   suffix. The first existing candidate wins.
3. A selected interface is authoritative. A non-regular or unreadable file, invalid UTF-8, parser failure, or
   header/module-name mismatch fails without source fallback.
4. When no interface exists, `MRP_REQUIRE_INTERFACE` reports a missing-interface diagnostic. `MRP_ALLOW_SOURCE_FALLBACK`
   uses the existing system-roots-before-project-roots source precedence and preserves declaration order within each
   root tier.
5. Compiler-synthesized virtual modules retain their special handling and do not require interface files.

The loader recursively resolves provider modules named by both dependency tiers. A `require` dependency activates the
provider interface for semantic replay; a `link` dependency creates a graph obligation without exposing provider names
inside the importing module. Programmatic registry providers follow the same closure logic, while duplicate registry
entries retain `DRV-0071`. Filesystem discovery is first-root-wins and does not report lower-priority matches as an
ambiguity.

Each interface surface is type-checked against its own **semantic require closure**. The closure starts with that
interface, follows only transitive `require` edges through interface-backed providers, and follows direct source imports
when source fallback supplies a provider. It never follows `link` edges. Every provider named by a materialized public
surface type, including a provider reached while expanding a transparent alias, must be in the applicable semantic
closure. A surface that can be satisfied only from the broader link graph is invalid and reports `RES-0040`,
`interface surface references a provider outside its semantic require closure`.

This validation does not rewrite the parsed dependency manifest or canonical declaration spelling. Semantic interface
copies may finalize nominal kinds and expand transparent aliases for analysis and code generation, while graph and
projection interfaces retain the parsed form for byte-stable round trips.

Graph node enumeration is sorted by canonical module name. Source nodes separately retain every direct import in exact
declaration order, including duplicates and imports that contribute no referenced symbol. That ordered sequence is not
reconstructed from or deduplicated with the sorted per-symbol dependency manifest.

## Export Surface

Only exported declarations appear in the `.l1m` file. The source `export` manifest is not reproduced verbatim as
`export ...;`; its effect is reflected only through which declarations are present.

The current `.l1m` surface includes:

- exported `struct` definitions
- exported `enum` definitions
- exported opaque `struct` and `enum` name declarations
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

Every declaration form currently carries a trailing per-symbol hash suffix `== "<hash>";`. The hash is opaque and
declarations emit `== ""`. The fingerprint tranche removes these declaration suffixes instead of populating them; module
and dependency fingerprints remain.

### Structs

Structs are emitted structurally with a trailing hash suffix:

```dea
struct Point {
  x: int;
  y: int;
} == "";
```

Field order is preserved from the analyzed source because layout is part of the imported type surface.

Opaque structs use an explicit name-only interface form:

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
use named-argument construct syntax. No fingerprint input is computed today; the planned whole-module canonicalizer
includes these public payload labels.

Opaque enums use an explicit name-only interface form:

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
func collect(prefix: int, values: string...) -> int == "";
extern func puts(value: string) -> int == "";
unsafe extern func raw_sink(value: int*) -> void == "";
```

Bodies are never emitted into `.l1m`. `extern func` declarations preserve their unmangled C ABI spelling, and
`unsafe extern func` preserves both the external linkage marker and the unsafe contract marker. Variadic function
declarations and function types preserve the final `T...` marker so consumers distinguish them from fixed `T[]`
signatures.

### Consts

Consts include their declared type, canonical literal value, and the trailing hash:

```dea
const origin: Point = Point(0, 0) == "";
const zero_color: Color = Red == "";
const min_offset: int = -5 == "";
const samples: int[3] = [1, 2, 3] == "";
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

The current interface emitter serializes accepted Stage 1 compile-time constants as folded values:

- integer, bigint, real, byte, string, bool, and `null` literals; integer, bigint, and real literals may carry a leading
  minus sign
- zero-field enum variant references
- struct and enum constructor calls whose arguments are themselves interface literals
- empty, flat, and nested array literals whose elements are themselves interface literals

Scalar const expressions are not preserved as expression syntax in `.l1m`; supported arithmetic, bitwise, boolean,
comparison, and cast expressions appear as their folded literal values.

Canonical constructor emission uses comma-plus-space separators:

```dea
Point(0, 0)
Rgb(255, 0, 0)
[1, 2, 3]
[[1, 2], [3, 4]]
[-1, 0, 1]
```

Array literals use square brackets and the same comma-plus-space separator. Empty arrays are written `[]`; trailing
commas are not accepted.

Canonical signed numerics are sign-inclusive lexer tokens, and direct replay evaluates them through the ordinary scalar
constant rules, including signed bigint values. The parser also accepts a split-token spelling such as `- 5` and
canonicalizes it to `-5`; the defensive raw replay fallback for `TT_MINUS` followed by `TT_BIGINT` returns no scalar
value, but emitted and parser-normalized interfaces do not use that split form.

Zero-field enum variants are emitted as bare references such as `Red` or qualified references when they name a
cross-module symbol.

## Parser Contract

The constrained `.l1m` parser accepts:

- the `module interface` header
- the `fingerprint` declaration (any string, including canonical-looking values such as `"sip13:0123456789abcdef"` and
  non-canonical opaque values)
- zero or more `require` lines followed by zero or more `link` lines
- top-level `struct`, `enum`, `type`, `func`, `unsafe func`, `extern func`, `unsafe extern func`, `const`, and `let`,
  each with a trailing `== "<hash>";` suffix
- recursive interface const literals, including empty and nested arrays

Declaration names must be unique across all declaration groups in one interface. Enum variants occupy the same
module-level namespace as structs, enums, aliases, functions, consts, and lets, so a variant cannot duplicate any of
those names or another variant name.

It rejects ordinary source-only forms such as function bodies. Dotted module names in the header and in dependency lines
are accepted and preserved.

Internal replay accepts dependency-bearing interfaces and resolves their transitive closure through the module graph.

The parser accepts explicit `opaque struct` and `opaque enum` declarations. Opacity is never inferred from a missing
body.

Parser failures use the dedicated `PAR-0560` through `PAR-0577` diagnostic range, plus shared `PAR-0520` for invalid
variadic placement and `PAR-0602` for malformed unsafe declarations, registered in
[docs/specs/compiler/diagnostic-code-catalog.md][diagnostic-catalog].

Discovery and graph failures use `DRV-0072` through `DRV-0077` where the existing source lookup, header-validation,
parser, or cycle diagnostics do not already describe the failure exactly.

## Non-goals

This format specification does not define:

- the fingerprint algorithm or object-metadata embedding
- whole-module fingerprint and provider-dependency verification
- compile-only object output
- provider-object linking or build/run fan-out
- making `-c`, standalone linking, or multi-CU build/run operational
- package or library distribution layout

[diagnostic-catalog]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[initiative-0001]: ../../../work/initiatives/0001-separate-compilation-and-linking.md
[interface-fingerprints]: ../../../work/plans/features/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
