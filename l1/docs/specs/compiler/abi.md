# Dea/L1 Binary Interface (LBI)

Version: 2026-07-27

Status: Finalized

This document specifies the binary interface and symbol mangling rules for the Dea/L1 compiler.

Dea/L1 uses a **unified, tagged-section, recursive mangling scheme**. The scheme collapses link-time identity and
type-level information into a single grammar. Every LBI-mangled name is a valid ISO C99 identifier drawn from the
alphabet `[A-Za-z0-9_]`.

## Format

```ebnf
lbi-name       = "__dea" module-section terminal
module-section = "M" (length identifier)+
terminal       = value | struct-type | enum-type | infrastructure
value          = "N" length identifier [ type-component ]
struct-type    = "S" length identifier
enum-type      = "E" length identifier
infrastructure = "I" length identifier
length         = digit+
identifier     = <length bytes from a Dea identifier>
type-component = <as defined in §Type Components>
```

- `__dea` is the fixed prefix on every LBI-mangled name.
- `M` opens the module-path section. Each component is one segment of the dotted source path.
- `N` marks a value entity (a function or a `let`/`const` binding).
- `S` marks a struct type.
- `E` marks an enum type.
- `I` marks a compiler-generated module-infrastructure symbol.
- `length` is one or more decimal digits giving the byte length of the immediately following identifier.

### Values and Functions

Value terminals (`N`) distinguish between plain bindings and functions via the presence of an optional `type-component`
suffix:

- **Plain bindings** (`let`, `const`) omit the type component.
- **Functions** append a function-type component (sigil `F` or `XF`).

This distinction allows the static linker to resolve calls to the correct overload (when overloading is introduced) and
produces a link error if a value is called as a function or vice-versa across module boundaries.

### Examples

| Source                                     | Mangled                       |
| ------------------------------------------ | ----------------------------- |
| `main::main` (`func() -> void`)            | `__deaM4mainN4mainF0v`        |
| `std.integer::abs` (`func(int) -> int`)    | `__deaM3std7integerN3absF1ii` |
| `std.io::prints` (`func(string) -> void`)  | `__deaM3std2ioN6printsF1cv`   |
| `demo.main::Point` (struct)                | `__deaM4demo4mainS5Point`     |
| `demo.main::Color` (enum)                  | `__deaM4demo4mainE5Color`     |
| `demo.main::static` (`let` named `static`) | `__deaM4demo4mainN6static`    |
| `unsafe func(int*) -> void` exported       | `__deaM<...>N<name>XF1Piv`    |
| `main::sum` (`func(int, int...) -> int`)   | `__deaM4mainN3sumF2iVii`      |
| module lifecycle `demo.main::init`         | `__deaM4demo4mainI4init`      |
| module lifecycle `demo.main::fini`         | `__deaM4demo4mainI4fini`      |
| module entry bridge `demo.main::entry`     | `__deaM4demo4mainI5entry`     |
| module identity record `demo.main`         | `__deaM4demo4mainI8metadata`  |
| module import record `demo.main`           | `__deaM4demo4mainI7imports`   |

### Compiler-Generated Module Symbols

Each independently emitted Dea module reserves these identifiers under the `I` terminal:

| Identifier | C signature                       | Presence                                                                      | Responsibility                                                                                            |
| ---------- | --------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `init`     | `void __deaM<module>I4init(void)` | Every module translation unit                                                 | Initialize deferred top-level `let` values owned by the module, in their established within-module order. |
| `fini`     | `void __deaM<module>I4fini(void)` | Every module translation unit                                                 | Clean ARC-managed top-level `let` values owned by the module.                                             |
| `entry`    | `int __deaM<module>I5entry(void)` | A module with a resolved, zero-parameter, non-extern source `main` definition | Call the owning module's source `main` and normalize its result to a C process status.                    |
| `metadata` | `const uint8_t ...I8metadata[]`   | Every module translation unit                                                 | Record module identity, fingerprint, and entry presence.                                                  |
| `imports`  | `const uint8_t ...I7imports[]`    | Every module translation unit                                                 | Record ordered direct object-backed providers and their expected fingerprints.                            |

In per-module output, these symbols are compiler infrastructure rather than source exports and always have external
linkage, independent of the module export manifest. `I4init` and `I4fini` remain present as callable empty functions
when the module has no owned initialization or cleanup work. They are one-shot operations: a generated executable
wrapper is responsible for calling each initializer exactly once in dependency order and each finalizer exactly once in
reverse order.

`I5entry` is emitted even when the source `main` has internal linkage. It returns an L1 `int` result directly, maps an
L1 `bool` result to `0` for `true` and `1` for `false`, and calls every other resolved result form before returning `0`.
It does not initialize runtime arguments, call module lifecycle functions, or perform dependency orchestration.

A module lifecycle function acts only on storage owned by its translation unit. It never calls an imported module's
lifecycle function or cleans imported storage.

`I8metadata` and `I7imports` are externally linked C99 byte arrays. `I4init` performs one volatile byte read from each
array so a linker dead-strip pass retains the records without custom sections or compiler-specific attributes. These
reads do not change lifecycle ordering or make initialization conditional.

The standalone link driver supplies the process wrapper that composes these symbols. It computes one dependency-first
module order from verified object metadata, calls `_rt_init_args`, calls each `I4init` once in that order, calls only
the selected `I5entry`, and calls each `I4fini` once in the exact reverse order. The wrapper defines the only
process-level C `main`; compiler-emitted module objects do not define it, and an explicit foreign object is rejected if
it does.

## Type Components

Type components are used to encode function signatures into link names and to generate deterministic names for
structural types like array wrappers.

### Grammar

```ebnf
type-component = nominal-type | modifier | array | slice | variadic-param | func | builtin
nominal-type   = module-section ("S" | "E") length identifier
modifier       = ("P" | "Q" | "X") type-component
array          = "A" dim "_" type-component
slice          = "W" type-component
variadic-param = "V" type-component
func           = "F" arity type-component* type-component
builtin        = "a" | "h" | "s" | "t" | "i" | "j" | "l" | "m"
               | "f" | "d" | "z" | "c" | "v"
               | "B" length identifier
arity          = digit+
dim            = digit+
```

The grammar is self-delimiting and parseable by recursive descent.

### Type Sigils

| Sigil | Meaning                            | Shape                   |
| ----- | ---------------------------------- | ----------------------- |
| `M`   | Nominal type module path           | `M<len><id>...`         |
| `S`   | Struct type leaf                   | `S<len><id>`            |
| `E`   | Enum type leaf                     | `E<len><id>`            |
| `A`   | Fixed-size array dimension         | `A<dim>_<elem>`         |
| `W`   | Slice descriptor                   | `W<elem>`               |
| `B`   | Non-canonical builtin escape hatch | `B<len><id>`            |
| `P`   | Pointer                            | `P<component>`          |
| `Q`   | Nullable/optional                  | `Q<component>`          |
| `F`   | Function type                      | `F<arity><params><ret>` |
| `X`   | Unsafe function/effect modifier    | `X<component>`          |
| `V`   | Variadic final function parameter  | `V<element>`            |

### ABI Encoding Decision Rule

Every new LBI grammar marker must be an explicitly selected single ASCII letter. Concatenated recursive components, such
as `XF`, remain separate one-letter markers; multi-letter markers are not permitted.

The exact letter, grammar position, and recursive shape for a new marker must be decided in the active implementation
plan before compiler work begins. The implementation must not invent an encoding. The accepted ADR and this normative
specification must record the same decision when the feature lands.

### Builtin Sigils

| Dea type | Sigil | Notes                                                           |
| -------- | ----- | --------------------------------------------------------------- |
| `tiny`   | `a`   | Signed 8-bit integer. Itanium convention (`a` for signed char). |
| `byte`   | `h`   | Unsigned 8-bit integer. Itanium convention (`h` for uchar).     |
| `short`  | `s`   | Signed 16-bit integer.                                          |
| `ushort` | `t`   | Unsigned 16-bit integer.                                        |
| `int`    | `i`   | Signed 32-bit integer.                                          |
| `uint`   | `j`   | Unsigned 32-bit integer.                                        |
| `long`   | `l`   | Signed 64-bit integer.                                          |
| `ulong`  | `m`   | Unsigned 64-bit integer.                                        |
| `float`  | `f`   | Binary32 floating-point.                                        |
| `double` | `d`   | Binary64 floating-point.                                        |
| `bool`   | `z`   | Boolean. JVM convention (`Z` lowercased).                       |
| `string` | `c`   | ARC-managed L1 string value. "c" for character data.            |
| `void`   | `v`   | No value.                                                       |

## Array Layout

Dea arrays follow C conventions: declaration order is outermost-first, and memory layout is **row-major**. For a Dea
declaration `T[N1][N2]...[Nk]`:

- The leftmost dimension `N1` is the **outermost** (slowest-varying).
- The rightmost dimension `Nk` is the **innermost** (fastest-varying).

The mangled encoding mirrors this layout: dimensions are emitted outermost-first, so `T[N1][N2]...[Nk]` mangles as
`A<N1>_A<N2>_...A<Nk>_<T>`.

## Slice Parameters

A fixed slice parameter `T[]` encodes as `W<T>`. `W` denotes a non-owning window over contiguous storage and keeps the
slice component distinct from the `S` nominal struct leaf. The corresponding generated C descriptor name uses the same
component, for example `int[]` becomes `__deaWi`.

## Variadic Parameters

A variadic final parameter `T...` encodes as `V<T>` inside its function component, so `func(int, int...) -> int` is
`F2iVii`. It lowers to the slice-descriptor parameter ABI documented above, but the distinct LBI component prevents a
variadic function from being linked or typed as a fixed slice function.

## `unsafe` Lowering

L1 treats `unsafe func(...) -> T` as a distinct type from `func(...) -> T`. This distinction is preserved in the LBI via
the `X` modifier sigil. A deliberate safe/unsafe mismatch between modules produces a link error rather than a silent
C-level type-pun.

At the C level, both types continue to share the same function-pointer typedef; the safety contract is enforced by LBI
identity and L1 type-checking.

## Linkage and Visibility

Linkage is driven by the module's export manifest:

- **Exported symbols** have external linkage (no `static` in C).
- **Non-exported symbols** have internal linkage (`static` in C).
- **Constants** follow the same rules, using `const` and optionally `static`.
- **Per-module compiler-generated `I4init`, `I4fini`, `I5entry`, `I8metadata`, and `I7imports` symbols** have external
  linkage independent of the export manifest. Legacy whole-program-only helpers retain their existing internal linkage.

## C FFI and Externs

Declarations marked `extern` or within an `extern "C"` block bypass LBI mangling entirely and use their declared C
spelling. `cstr` boundary rules are deferred to the C FFI ADR.

## Module Interface Fingerprints

The version 1 LBI compatibility fingerprint is a whole-module SipHash-1-3 digest over the canonical effective exported
surface. Textual `.l1m` values use exactly:

```text
sip13:<16 lowercase hexadecimal digits>
```

The public, fixed SipHash key is the 16-byte ASCII string `DeaL1-fp-v1-key!`, with bytes:

```text
44 65 61 4c 31 2d 66 70 2d 76 31 2d 6b 65 79 21
```

The key and `sip13` algorithm identifier are part of the LBI version 1 contract. They are unrelated to the runtime's
randomized process hash key. The unsigned 64-bit SipHash result is formatted with all 16 lowercase hexadecimal digits,
including leading zeroes.

For an interoperability known answer, hashing the five ASCII bytes `input` with this key produces the raw digest
`0c3810c9b2f8823a`.

Canonical input starts with the UTF-8 domain line `l1-interface-fingerprint-v1\n`. Each following exported-declaration
record is framed as its ASCII decimal UTF-8 byte length, a colon, the record bytes, and LF. Record atoms and recursive
type payloads use the same length framing. Counts have no leading zeroes, flags are `0` or `1`, declaration groups and
names are sorted, and layout/signature members retain semantic source order.

The digest covers exported structs, enums, aliases, functions, const values, and top-level let types. It excludes module
identity, filesystem location, the fingerprint itself, dependency manifests, private implementation, tool metadata, and
object metadata. The exact record and type shapes are normative in
[l1/docs/specs/compiler/module-interface-format.md][module-interface-format].

Every `require` and `link` record stores the provider module's tagged whole-module fingerprint, repeated for each used
provider symbol. These dependency values do not participate in the consumer's own digest.

The Stage 1 compiler reaches the 64-bit SipHash implementation through the compiler-private C bridge:

```c
void l1c_interface_fingerprint_sip13_hex(
    const uint8_t *data, int32_t len, uint8_t out_hex[16]);
```

The bridge writes exactly 16 lowercase digest bytes to caller-owned storage, with no NUL terminator or allocation. It is
available in each L1 runtime variant for bootstrap/compiler parity but adds no L1 source-language or standard-library
API.

## Object Metadata Records

Every separately emitted Dea module defines one `I8metadata` identity record and one `I7imports` direct-import record.
Both records begin with this 16-byte header:

| Offset | Field          | Encoding                                                |
| ------ | -------------- | ------------------------------------------------------- |
| 0      | Magic          | Eight ASCII bytes `DEAL1OBJ`                            |
| 8      | Format version | Little-endian `u16`; version 1 is the supported version |
| 10     | Record kind    | Little-endian `u16`; `1` is identity and `2` is imports |
| 12     | Payload length | Little-endian `u32`, excluding the common header        |

### Identity payload

The `I8metadata` payload contains:

1. a little-endian `u32` flags field; bit 0 is `HAS_ENTRY`, and every other bit is zero in version 1;
2. a little-endian `u32` byte length for the canonical dotted module name;
3. the module's whole-interface SipHash-1-3 fingerprint as eight little-endian bytes; and
4. the non-NUL-terminated ASCII module-name bytes.

`HAS_ENTRY` is set exactly when the same object defines the module's external `I5entry`. A valid metadata-bearing object
also defines that module's external `I4init` and `I4fini`.

### Import payload

The `I7imports` payload begins with a little-endian `u32` record count. Each record then contains:

1. a little-endian `u32` canonical dotted module-name length;
2. the expected provider fingerprint as eight little-endian bytes; and
3. the non-NUL-terminated ASCII provider module-name bytes.

The records contain every unique direct object-backed provider exactly once in first source-import order. Equivalently,
virtual compiler-provided modules are omitted because they do not contribute standalone provider objects.
Side-effect-only imports of object-backed providers remain present, and duplicate source edges are coalesced at their
first occurrence before encoding. Version 1 fixes the fingerprint algorithm to SipHash-1-3, so the textual `sip13:` tag
is not embedded; changing the algorithm requires a new metadata format version.

### Validation boundary

Record magic, version, kind, flags, lengths, canonical names, exact payload extent, and import uniqueness are all
validated. Unknown flags, duplicate provider records, trailing bytes, truncation, or inconsistency between the symbol
module and payload module make the metadata malformed.

A supported relocatable object is classified as metadata-free only when it defines neither metadata symbol nor any
external symbol whose normalized name starts with `__dea`. The entire normalized `__dea` prefix is reserved for Dea:
every such definition is Dea evidence even when the rest of the name is not a valid LBI production. A reserved-prefix
definition with absent or invalid records is malformed, not a foreign-compatible object. Container read failures and
unsupported or corrupt object formats remain object-read errors outside this metadata classification.

### Standalone link-set validation

`l1c --link` treats embedded object metadata as the link-time authority and does not reopen source or textual `.l1m`
interfaces. A positional operand must classify as valid Dea metadata. An explicit `--foreign-object` must classify as
metadata-free and must not define normalized process symbol `main`. Malformed Dea evidence and object-read failures are
errors under either spelling.

Metadata classification is independent of embedded linker-control inspection. ELF dependent-library sections, Mach-O
linker-option commands, and PE/COFF directive sections reject either operand role before graph or host-link work; their
payloads never become implicit libraries or raw linker arguments. The generated wrapper object is subject to the same
inspection before the final host link.

The driver requires one supplied object per canonical Dea module identity, complete ordered-import closure, exact
consumer/provider fingerprint agreement, and an acyclic dependency graph. Entry inference requires exactly one object
whose identity record carries `HAS_ENTRY`; explicit selection requires the named supplied object to carry that flag.
Valid metadata already guarantees agreement between `HAS_ENTRY` and the exact module-owned `I5entry` definition. Foreign
objects have no module identity, fingerprint, dependency, lifecycle, or entry semantics.

The full CLI, lifecycle-ordering, output-transaction, and host-link contracts are specified in
[l1/docs/reference/separate-compilation.md][separate-compilation].

## Portability

The LBI uses only ISO C99 identifier characters `[A-Za-z0-9_]`. Generated C is expected to compile under
`cc -std=c99 -pedantic-errors`.

Object readers normalize only these exact C external-name decorations before matching LBI names and process-level
`main`:

- ELF names remain unchanged except for the Darwin TinyCC-compatible aliases `___dea...` to `__dea...` and `_main` to
  `main`.
- Mach-O names lose exactly one leading underscore.
- COFF I386 names lose exactly one leading underscore, and ARM64EC function symbols lose exactly one leading `#`;
  ARM64EC data names and other supported COFF machine names remain unchanged.

No reader performs fuzzy suffix matching or general leading-character stripping. The standard little-endian COFF
relocatable reader accepts I386 (`0x014c`), ARM (`0x01c0`), ARMNT (`0x01c4`), AMD64 (`0x8664`), ARM64EC (`0xa641`), and
ARM64 (`0xaa64`). PE images, COFF bigobj and import-object encodings, and other machines including ARM64X (`0xa64e`) are
unsupported.

[module-interface-format]: module-interface-format.md
[separate-compilation]: ../../reference/separate-compilation.md
