# Dea/L1 Module Interface Format

Version: 2026-08-20

Status: Finalized

This document specifies the textual `.l1m` module interface artifact for the current Dea/L1 bootstrap compiler tranche.
It defines the on-disk file shape, canonical declaration and fingerprint inputs, type/literal formatting rules,
operational manifests, verification, discovery, standalone-link authority, and transitive closure.

`.l1m` files are normal verified dependency inputs for L1 `-c` / `--compile`, which produces one source module's sibling
`.o` and `.l1m` artifacts and optionally retains `.c` with `--keep-c`. Ordinary `--build` and `--run` flows remain
source-based under [l1/work/initiatives/0001-separate-compilation-and-linking.md][initiative].

Standalone `--link` also requires one verified sibling `.l1m` for every positional Dea `.o`. The interface is the sole
Dea semantic, entry, dependency, and lifecycle authority; the paired native object is an opaque host-link payload.

## Scope

The current `.l1m` format serializes one module's exported public surface in deterministic, human-readable form:

- the emitter projects analyzed source into canonical text and assigns a whole-module fingerprint
- the constrained parser reconstructs the interface model from that text
- every operational consumer validates and recomputes the fingerprint before graph registration or semantic replay
- the interface carries non-fingerprinted entry, ordered lifecycle-import, `require`, and `link` records
- internal analysis entry points discover interfaces from ordered roots and recursively load dependency closure
- programmatic supplied-interface registries use the same verification and graph contract
- standalone link derives each sibling path from the caller's positional `.o` and verifies the complete interface set
  before registering any module identity
- the internal `--emit-interface` mode writes artifacts for developer and testing use

The version 1 fingerprint is mandatory and has the exact spelling `sip13:<16 lowercase hexadecimal digits>`. There is no
untagged or empty compatibility fallback.

## File Structure

Each interface file describes exactly one module:

```dea
module interface demo.main;
fingerprint "sip13:0123456789abcdef";

entry;

import module iface_dep == "sip13:62649b8c7d5e4f3a";

require iface_dep::RemotePoint == "sip13:62649b8c7d5e4f3a";
link std.io::printl_s == "sip13:40d3cb93d387f3c1";

struct Point {
  x: int;
  y: int;
}
```

The digest values above illustrate the required spelling; a consumable file must contain the values computed from its
actual declarations and providers.

The file has eight regions in fixed order:

1. `module interface <dotted-module-name>;`
2. `fingerprint "<tagged-whole-module-fingerprint>";`
3. zero or one `entry;` marker
4. zero or more `import module <provider> == "<fingerprint>";` records in lifecycle order
5. zero or more `require` records
6. zero or more `link` records
7. zero or more exported declarations in canonical declaration-group order
8. end of file

The header uses the module's canonical dotted source path. Module identity and filesystem discovery paths do not
participate in the module's fingerprint.

The operational regions are strict. Duplicate `entry;`, duplicate import providers, records that return to an earlier
region, and trailing unknown records are rejected. When a record is both duplicate and misplaced, the duplicate
diagnostic wins. Whitespace and emitter-inserted blank lines are not semantically significant.

## Whole-Module Fingerprint

### Tagged value and algorithm

The tagged envelope contains exactly one colon, a nonempty algorithm identifier matching `[a-z][a-z0-9]*`, and a
nonempty payload. Envelope validation happens before algorithm selection. A well-formed unknown algorithm is
unsupported, while a malformed `sip13` payload is a malformed fingerprint.

Version 1 supports only SipHash-1-3:

- fixed 16-byte ASCII key: `DeaL1-fp-v1-key!`
- key bytes: `44 65 61 4c 31 2d 66 70 2d 76 31 2d 6b 65 79 21`
- hash input: the canonical UTF-8 byte stream below, with LF line endings and no terminating NUL
- result: the unsigned 64-bit SipHash value rendered as exactly 16 lowercase hexadecimal digits, including leading
  zeroes
- textual value: lowercase `sip13:` followed by that digest

The fixed key is public and versioned as part of the LBI. It is distinct from the runtime's randomized hash-flooding
key. The contract detects accidental staleness and corruption; it does not provide cryptographic authenticity.

### Framing

Let `F(x)` be the ASCII decimal UTF-8 byte length of `x`, with no leading zero except the number `0`, followed by `:`,
followed by the raw bytes of `x`.

The canonical stream is:

```text
l1-interface-fingerprint-v1\n
F(record-1)\n
F(record-2)\n
...
```

There is one line for each exported declaration and no terminating NUL. An interface with no exported declarations
hashes only the domain line. Each record payload concatenates framed atoms. A type is first encoded as its recursive
type payload and then included as one framed record field; recursive child types use the same rule.

Flags are `0` or `1`. Counts and fixed-array lengths are unsigned ASCII decimal without leading zeroes.

### Declaration records

Records use the same group and name ordering as text emission:

1. structs sorted by name; a transparent record is `struct`, name, field count, then each field name/type, while an
   opaque record is `opaque-struct`, name
2. enums sorted by name; a transparent record is `enum`, name, variant count, then each variant name, payload count, and
   payload label/type, while an opaque record is `opaque-enum`, name
3. aliases sorted by name: `alias`, name, target type
4. functions sorted by name: `func`, name, `extern`/`unsafe`/variadic flags, parameter count, each parameter name/type,
   and result type
5. consts sorted by name: `const`, name, type, canonical folded literal
6. lets sorted by name: `let`, name, type

Field, variant, payload, and parameter order remains source order because it is part of the public surface.

### Type records

Type payloads start with one of these tags:

- `builtin`, followed by the canonical builtin name
- `nominal`, followed by module and name; the module atom is empty for a same-module reference
- `pointer`, followed by the pointee type
- `nullable`, followed by the inner type
- `array`, followed by the unsigned dimension and element type
- `slice`, followed by the element type
- `function`, followed by unsafe and variadic flags, parameter count, parameter types in order, and result type

Nominal type records deliberately do not distinguish struct from enum. The declaration record preserves that distinction
for local declarations, while a cross-module reference records only the provider module and public name. This lets a
consumer verify parsed bytes before graph-backed semantic nominal-kind materialization.

`TY_NULL`, invalid dimensions, inconsistent field/variant/parameter vectors, and impossible type or flag combinations
cannot be canonicalized and produce a compatibility diagnostic instead of a digest.

### Included and excluded data

The fingerprint includes only the effective exported declarations listed above. It excludes:

- source export-manifest spelling
- the module header, filesystem location, and fingerprint declaration
- `entry`, `import module`, `require`, and `link` operational manifests
- private declarations, bodies, implementation-only imports, and other implementation details
- native-object contents, compiler version strings, timestamps, and host-platform data

Changing any exported name, transparent layout, enum variant or payload label, opacity state, alias target, signature
including parameter names and flags, const type/value, or let type changes the fingerprint. Source declaration order,
private implementation changes, entry/import/dependency-manifest changes, and equivalent export-manifest spelling do
not.

## Operational Manifests

The non-fingerprinted operational regions have distinct roles:

- **`entry;`**: the module emits `I5entry`. The producer derives this from the same resolved source-entry predicate used
  by backend generation.
- **`import module P`**: source directly imports the object-backed provider `P`, including for side effects. These
  records are the only standalone lifecycle edges and retain first source occurrence order.
- **`require P::S`**: `P::S` is exposed through the consumer's public surface. This creates no lifecycle edge by itself.
- **`link P::S`**: `P::S` is used by implementation and is not already in `require`. This creates no lifecycle edge by
  itself.

Compiler-synthesized virtual providers are omitted from all three provider manifests because they have no sibling native
artifact or independent lifecycle.

The manifest records, per used provider symbol, the provider module fingerprint against which the consumer was
projected:

- **`require`**: the provider symbol is named in this module's exported surface and must be available through semantic
  interface closure.
- **`link`**: the provider symbol is used only by implementation and creates a future link obligation without exposing
  names for downstream type checking.

A symbol present in both tiers appears only as `require`. Each line names `<provider_module>::<symbol_name>` and repeats
the provider's canonical tagged whole-module fingerprint:

```dea
require myapp.rectangle::Rectangle == "sip13:62649b8c7d5e4f3a";
link std.io::printl_s == "sip13:40d3cb93d387f3c1";
```

The `require` group is emitted before `link`. Lines within each group are sorted by qualified symbol and deduplicated.
Every entry for one provider module must carry the same valid fingerprint. Dependency values are excluded from the
consumer's own fingerprint.

`import module` records are projected independently from resolved direct source imports. Projection walks the graph's
exact source-order vector, omits virtual providers, retains the first occurrence of each remaining provider, and keeps
side-effect-only imports. It does not mutate or deduplicate `ModuleGraphNode.direct_imports`. A provider may occur in a
symbol manifest without being a direct interface import when a public type names a transitive provider.

Projection uses an already verified provider fingerprint for interface-backed providers. For source-backed providers, it
independently projects and hashes the provider's public surface, without recursively adding its dependencies to that
hash, and copies the result to each corresponding entry.

Operational verification validates fingerprint spelling, import-provider uniqueness, virtual-provider exclusion, and
same-provider fingerprint agreement across `import module`, `require`, and `link`. Standalone link then compares every
expectation with the supplied provider's verified interface fingerprint.

After lifecycle ordering succeeds, every non-virtual provider named by `require` or `link` must be transitively
reachable from the consumer through a nonempty path of existing `import module` edges. This proves source-import
provenance without converting semantic records into lifecycle edges or discovering implicit objects.

## Interface Discovery and Verification

The internal module-graph resolver applies these rules:

1. The requested compilation target is source-backed even if a matching interface exists.
2. For each imported canonical module, ordered interface roots are searched for the dotted relative path with an `.l1m`
   suffix. The first existing candidate wins.
3. A selected interface is authoritative. A non-regular or unreadable file, invalid UTF-8, parse failure, declared
   module mismatch, invalid fingerprint, or digest mismatch fails without source fallback.
4. When no interface exists, `MRP_REQUIRE_INTERFACE` reports a missing-interface diagnostic. `MRP_ALLOW_SOURCE_FALLBACK`
   uses system-roots-before-project-roots source precedence.
5. Compiler-synthesized virtual modules retain their special handling and do not require interface files.

Operational consumers use this order:

1. constrained parse
2. declared module-identity check
3. tagged public and operational provider fingerprint validation
4. operational uniqueness, virtual-provider exclusion, and same-provider consistency validation
5. canonical public-surface recomputation and exact declared/recomputed comparison
6. graph registration and caching
7. graph normalization, activation, and semantic replay

Programmatically supplied interfaces are verified when selected for graph registration; an unused supplied entry remains
inert. Success is cached only after verification. Identity checking precedes fingerprint checking so a header-mismatched
file retains its dedicated driver diagnostic.

The loader recursively resolves both dependency tiers. `require` activates provider interfaces for semantic replay;
`link` creates a graph obligation without opening provider names. Each interface surface is type-checked against its own
semantic require closure, which follows transitive `require` edges through interface-backed providers and direct source
imports from source-backed providers, but never follows `link`.

Semantic interface copies may materialize nominal kinds and expand transparent aliases. Graph and projection interfaces
retain the parsed spelling for deterministic clone and re-emission behavior.

Standalone link uses a path-only association. Each positional operand must have a nonempty basename stem followed by the
exact case-sensitive terminal suffix `.o`; replacing only that suffix with `.l1m` in the same directory selects the
sibling. Both paths must resolve to regular files. The verified sibling header is authoritative regardless of basename,
and all Dea objects remain explicit CLI operands. An interface record validates the supplied set but never searches for
or adds an object.

## Export Surface and Declaration Forms

Only exported declarations appear. The source `export` manifest is not reproduced.

Declarations are grouped as structs, enums, aliases, functions, consts, and lets, with names sorted in each group. There
are no per-declaration compatibility suffixes.

Transparent structs and enums preserve their field, variant, and payload order:

```dea
struct Point {
  x: int;
  y: int;
}

enum Color {
  Red;
  Green;
  Rgb(red: int, green: int, blue: int);
}
```

Opaque nominal declarations expose only their name:

```dea
opaque struct Handle;
opaque enum State;
```

Aliases, functions, consts, and lets end in semicolons:

```dea
type Dims = Size;
func area(s: Size) -> int;
func collect(prefix: int, values: string...) -> int;
extern func puts(value: string) -> int;
unsafe extern func raw_sink(value: int*) -> void;
const origin: Point = Point(0, 0);
const samples: int[3] = [1, 2, 3];
let current_offset: Point?;
```

Bodies are never emitted. `extern`, `unsafe`, and variadic markers remain part of function declarations and fingerprint
records.

## Type and Const Formatting

Textual types use these canonical forms:

- same-module nominal types are unqualified; cross-module nominal types are fully qualified
- pointer, nullable, fixed-array, and slice suffixes are `*`, `?`, `[N]`, and `[]`
- function types use `func(T1, T2) -> U` or `unsafe func(T1, T2) -> U`
- a final variadic parameter uses `T...`
- `null` is a literal-only keyword and not an interface type

A nullable function type is parenthesized before `?`, for example `(func(int) -> int)?`.

Const declarations contain canonical folded values. Supported forms include scalar literals, zero-field enum variants,
struct and enum constructors with interface literals, and empty, flat, or nested array literals. Scalar expressions are
folded rather than preserved as source expressions. Constructors and arrays use comma-plus-space separators and no
trailing comma. Signed numeric tokens are emitted without whitespace between sign and magnitude.

Canonical integer and byte values use unsigned or signed decimal without redundant leading zeroes. Integer literal
values must lie in at least one implemented integer domain: negative values are bounded by `long` and non-negative
values by `ulong`. String values are encoded from their decoded bytes: printable ASCII other than `\\` and `\"` is
direct, the standard named control escapes are used where available, and every other byte uses a three-digit octal
escape. Raw UTF-8 source and equivalent scalar escapes converge before projection, while octal escapes remain
byte-valued. The fingerprint canonicalizer validates this producer spelling recursively inside arrays and constructors;
alternate numeric bases, out-of-domain integer values, character-style byte literals, equivalent string escapes, and
same-module qualification are not accepted as canonical model data.

## Parser and Diagnostic Contract

The constrained parser recognizes the grammar above and preserves the raw fingerprint string in its wire model.
Operational producer and consumer entry points are responsible for assignment or verification, so a low-level
parser-only test may preserve a noncanonical token without making it valid compatibility data.

Declaration names must be unique across all groups. Enum variants share the module-level namespace with declarations.
Function bodies and implicit opaque declarations are rejected.

Parser shape failures use `PAR-0560` through `PAR-0579`, plus shared `PAR-0520` for invalid variadic placement and
`PAR-0602` for malformed unsafe declarations. `PAR-0572` covers malformed operational shapes not assigned a more
specific code, `PAR-0574` through `PAR-0576` describe the common provider-expectation tail, `PAR-0578` covers duplicate
operational records, and `PAR-0579` covers nonduplicate canonical-region regressions. Public and provider fingerprint
validation uses `SIG-0280` through `SIG-0285`; `SIG-0284` is within-interface provider disagreement and `SIG-0285`
rejects invalid operational models such as programmatic duplicate imports or persisted virtual providers. Discovery and
graph failures use the applicable `DRV-*` diagnostics.

All concrete codes are registered in [docs/specs/compiler/diagnostic-code-catalog.md][diagnostic-catalog].

## Non-goals

This contract does not define:

- authentication or cryptographic binding between sibling `.o` and `.l1m` bytes
- implicit object discovery from interface records or search roots
- build/run source fan-out
- package or library distribution layout

[diagnostic-catalog]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[initiative]: ../../../work/initiatives/0001-separate-compilation-and-linking.md
