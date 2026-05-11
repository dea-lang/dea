# Dea/L1 Binary Interface (LBI)

Version: 2026-05-11

Status: Finalized

This document specifies the binary interface and symbol mangling rules for the Dea/L1 compiler.

The LBI has two layers:

- **Link-name layer.** Stable, shipping ABI. Defines the actual symbol names emitted into object files (`__deaM...S...`,
  `__deaM...I...`).
- **Type-component layer.** A forward-looking grammar reserved for generated type names (e.g. array wrappers), future
  overload keys, and demangler support. Type components are not currently appended to public link names.

The two layers share an alphabet but live in disjoint parsing contexts: a link-name demangler never enters
type-component territory and vice versa. Sigils may overlap between the two layers (notably `M`, `S`, `E`) and this is
deliberate, not a collision: it preserves the visual identity of source-level entities across both layers.

## Link-Name Layer

To ensure stable link-time identity across compilation units and to avoid collisions with C keywords or other symbols,
Dea/L1 uses a **tagged-section, length-prefixed mangling scheme**. The scheme uses only characters drawn from the ISO
C99 identifier alphabet `[A-Za-z0-9_]`, so generated names are valid identifiers under strict ISO/ANSI C99.

### Format

```ebnf
lbi-name          = "__dea" module-section terminal-section
module-section    = "M" (length identifier)+
terminal-section  = source-section | lifecycle-section
source-section    = "S" length identifier
lifecycle-section = "I" length identifier
length            = digit+
identifier        = <length bytes from a Dea identifier>
```

- `__dea` is the fixed prefix on every LBI-mangled name.
- `M` opens the module-path section. Each component is one segment of the dotted source path. `M` is mandatory: every
  LBI-mangled name carries a module-path section, even for top-level entities in single-module programs (the module path
  is the program's root module).
- `S` opens the source-symbol section. It names exactly one L1 source-level symbol.
- `I` opens the compiler-generated module-lifecycle section. It names exactly one lifecycle component.
- `length` is one or more decimal digits giving the byte length of the immediately following identifier.

The `S` section in the link-name layer is intentionally broad: functions, top-level bindings, structs, and enums all use
`S` today. This keeps the current LBI stable and avoids a mass rename to finer-grained category sigils. L1 does not
currently overload source-level symbols by type, so the symbol name alone is the source ABI key.

The type-component layer (defined below) does distinguish structs from enums via separate sigils. This asymmetry is
deliberate: the link-name layer is constrained by shipped object files, the type-component layer is not.

A section ends when the next character is another sigil or end-of-string. No explicit terminator is needed because Dea
identifiers cannot start with a digit, so the boundary between a decimal length and its identifier payload is
unambiguous.

### Category Sigils (Link-Name Layer)

The full uppercase alphabet `A`-`Z` is reserved by the LBI. Defined link-name section sigils:

| Sigil | Meaning                                                               |
| ----- | --------------------------------------------------------------------- |
| `M`   | Module path. Each component is one segment of the dotted source path. |
| `S`   | Source symbol. Exactly one component.                                 |
| `I`   | Module lifecycle symbol. Exactly one compiler-defined component.      |

Other uppercase letters are reserved for future ABI amendments. In particular, do not reuse `N` for functions or `E` for
enums at the link-name layer without a compatibility plan: current object files and generated runtime headers already
use `S` for those names.

### Section Ordering

Sections appear in a fixed order. In this revision the valid orders are:

```text
M S
M I
```

Future categories slot in by spec amendment with a defined position relative to the existing ones. Mangling is
deterministic: there is exactly one valid encoding for any source symbol or compiler-generated module lifecycle entry
point.

### Examples

| Source                                   | Mangled                              |
| ---------------------------------------- | ------------------------------------ |
| `main::main`                             | `__deaM4mainS4main`                  |
| `std.math::abs`                          | `__deaM3std4mathS3abs`               |
| `std.collections.list::push`             | `__deaM3std11collections4listS4push` |
| `demo.main::Point` (struct)              | `__deaM4demo4mainS5Point`            |
| `demo.main::Color` (enum)                | `__deaM4demo4mainS5Color`            |
| `demo.main::static` (let named `static`) | `__deaM4demo4mainS6static`           |
| module lifecycle `demo.main::init`       | `__deaM4demo4mainI4init`             |

The leading `__` places every LBI-mangled name in the implementation-reserved namespace defined by ISO C §7.1.3. The
`__dea` prefix carves out a stable LBI subspace within that namespace.

### Module Lifecycle Components

Module lifecycle symbols are compiler-generated symbols in the `I` section. They are module-scoped entry points used by
the backend/runtime orchestration and cannot collide with source-level `S` symbols.

Defined lifecycle components:

| Component | Meaning                                                       |
| --------- | ------------------------------------------------------------- |
| `init`    | Initializes deferred top-level `let` bindings for the module. |

Future lifecycle components, such as an `at_exit` hook, must be added by ABI amendment before emission.

### Demangling Link Names

Parse left-to-right after the fixed `__dea` prefix:

1. Read the next character. If it is a non-digit, treat it as a category sigil and open a new section.
2. Otherwise read a run of decimal digits as a length, then read exactly that many bytes as the name component, and
   append the component to the current section.
3. Stop at end-of-string. If a section has zero components, the name is malformed.

The closed sigil set means a link-name demangler can be written without consulting external tables: every uppercase
letter is a section opener; every digit run is a length prefix. The demangling rules above apply only to link names;
type components have their own parsing routine (see [Parsing Type Components](#parsing-type-components)).

## Type-Component Layer

Some ABI-owned generated names need a deterministic type key. Current L1 emits the historical C helper spellings
documented in [Generated Helper Names](#generated-helper-names). New type-instantiation encodings, including fixed-size
array wrappers, use the grammar in this section unless the relevant feature plan explicitly reserves a different shape.

Type components are not currently appended to public source symbol names. They are reserved for generated type names,
future overload keys, and demangler support.

### Grammar

```ebnf
type-component = nominal-type | modifier | array | func | builtin
nominal-type   = module-section ("S" | "E") length identifier
modifier       = ("P" | "Q" | "X") type-component
array          = "A" dim "_" type-component
func           = "F" arity type-component* type-component
builtin        = "a" | "h" | "s" | "t" | "i" | "j" | "l" | "m"
               | "f" | "d" | "z" | "c" | "v"
               | "B" length identifier
arity          = digit+
dim            = digit+
```

The grammar is self-delimiting and parseable by recursive descent. The `_` terminates array dimensions because two
unbounded decimal runs cannot otherwise be separated. The `_` is the only non-alphanumeric token in the encoding;
everywhere else the grammar lives entirely in `[A-Za-z0-9]`.

The `dim = digit+` rule currently requires a concrete dimension. An empty `dim` (encoded `A_<elem>`, with the terminator
immediately following the sigil) is **reserved for future use** to represent unbounded or incomplete-extent arrays (e.g.
slice-like FFI signatures, function-parameter arrays of unknown length). The emitter does not produce empty dimensions
today; demanglers do not need to accept them today. When unbounded arrays land, this restriction will be lifted by spec
amendment and the encoding `A_<elem>` will be the canonical form.

### Array Layout

Dea arrays follow C conventions: declaration order is outermost-first, and memory layout is **row-major**. For a Dea
declaration `T[N1][N2]...[Nk]`:

- The leftmost dimension `N1` is the **outermost** (slowest-varying) and strides over the largest blocks in memory.
- The rightmost dimension `Nk` is the **innermost** (fastest-varying) and strides over individual elements of type `T`.
- Index `[i1][i2]...[ik]` resolves to linear offset `((i1 * N2 + i2) * N3 + i3) * ... * Nk + ik` elements from the base,
  scaled by `sizeof(T)`.

The mangled encoding mirrors this layout: dimensions are emitted outermost-first, so `T[N1][N2]...[Nk]` mangles as
`A<N1>_A<N2>_...A<Nk>_<T>`. Source syntax, memory layout, and mangled encoding all agree on outer-to-inner order — this
agreement is a consequence of choosing C conventions on both axes (declarator order and storage layout) and is the
single source of truth for any reader trying to relate the three.

This convention is binding on all backends: code generation, FFI bridges, and any future ABI tooling must treat
multi-dimensional Dea arrays as row-major. A column-major or other layout is not a valid representation of a Dea array
type, regardless of what the underlying target conventions might suggest (e.g. when interoperating with Fortran-style
numerical libraries, the boundary is responsible for transposing, not the ABI).

### Type Sigils

Structural type sigils:

| Sigil | Meaning                            | Shape                   |
| ----- | ---------------------------------- | ----------------------- |
| `M`   | Nominal type module path           | `M<len><id>...`         |
| `S`   | Struct type leaf                   | `S<len><id>`            |
| `E`   | Enum type leaf                     | `E<len><id>`            |
| `A`   | Fixed-size array dimension         | `A<dim>_<elem>`         |
| `B`   | Non-canonical builtin escape hatch | `B<len><id>`            |
| `P`   | Pointer                            | `P<component>`          |
| `Q`   | Nullable/optional                  | `Q<component>`          |
| `F`   | Function type                      | `F<arity><params><ret>` |
| `X`   | Unsafe function/effect modifier    | `X<component>`          |

Note that the type-component layer distinguishes structs (`S`) from enums (`E`) in nominal-type references, even though
the link-name layer currently uses `S` for both. The two `S` sigils live in disjoint parsing contexts and do not
collide: the link-name `S` appears exactly once per name in a position determined by section ordering, and the
type-component `S` only appears nested inside other type components within a generated type name. A hand-reading user
sees `S5Point` and reads "the Dea-level entity `Point`" in either context, which is the intent.

Builtin type sigils (lowercase):

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

The lowercase builtin set is loosely modeled on the Itanium C++ ABI and the JVM class-file descriptors, with deviations
where Dea's type names dictate. In particular, `tiny`/`byte` follow Itanium's signed/unsigned char convention (`a`/`h`),
while `long`/`ulong` use the Itanium mnemonics (`l`/`m`) rather than JVM's `J` (JVM was forced into `J` because `L` is
reserved for reference types; Dea has no such conflict). `string` (sigil `c`) is Dea-specific: it has no Itanium or JVM
counterpart, since it is a built-in ARC-managed reference type rather than a numeric primitive.

Future builtins should pick free lowercase letters mnemonically. The `B<len><name>` escape hatch covers cases where no
good single letter is available, or for target-specific builtins that are not part of the canonical set.

### Encoding Rules

**Length-prefix iff the payload is user-supplied data.** Identifiers (`M`, `S`, `E`, `B`) carry a length because their
content is open-ended user text. Modifiers (`P`, `Q`, `X`), builtins (lowercase), and structural constructors (`A`, `F`)
do not — their payload is either a recursively-self-delimiting component or a closed-set sigil.

**Outermost constructor first, recurse inward.** All type constructors mangle outer-to-inner. For arrays specifically —
including the row-major layout contract — see [Array Layout](#array-layout) above.

**Modifiers attach to the immediately following component.** No length needed; the inner component is self-delimiting.
`Q P i` → `QPi` is unambiguously `optional(pointer(int))`.

**Arrays: one `A` per dimension, `_`-terminated.** No packed rank. Modifiers can appear between dimensions naturally
(`A4_PA3_i` = array of 4 pointers to `int[3]`).

**Surface postfix → mangled prefix.** Dea's `*` and `?` are postfix. The last postfix operator in source becomes the
first type sigil because the encoding walks the type tree from root to leaves.

**Type aliases have no ABI presence.** Aliases resolve to their underlying type before any type-component key is formed.

### Type Examples

```text
int                                  i
int*                                 Pi
int?                                 Qi
int??                                QQi
int*?                                QPi
int*??                               QQPi
int?*                                PQi
int[3]                               A3_i
int[3][4]                            A3_A4_i
int[3][4]*                           PA3_A4_i
int*[4]                              A4_Pi
int[3]*[4]                           A4_PA3_i
int*?[3][4]                          A3_A4_QPi
string                               c
string*                              Pc
string?                              Qc
unsafe func() -> int                 XF0i
func(int*) -> bool                   F1Piz
func(string) -> string               F1cc
func(int, string) -> bool            F2icz
func(int, int) -> bool?              F2iiQz
(func(int, int) -> bool)?            QF2iiz
func() -> func(int) -> int           F0F1ii
demo.main::Point (as type)           M4demo4mainS5Point
demo.main::Color (as type)           M4demo4mainE5Color
func(demo.main::Point) -> int        F1M4demo4mainS5Pointi
demo.main::Point*?[3]                A3_QPM4demo4mainS5Point
```

Arrays are encoded one dimension at a time, outermost first. Modifiers attach to the immediately following component.

### Parsing Type Components

A type-component parser is recursive: each top-level call consumes exactly one component from the input stream and
returns. The component may itself contain nested components (modifiers, array elements, function parameters and
returns), which are consumed by recursive calls.

1. Read the next character.
2. If it is a structural sigil with a user-supplied payload (`M`, `S`, `E`, `B`), read the length and identifier. For
   `M`, continue reading further `M<len><id>` segments until a non-`M` sigil is encountered; then read the trailing
   `S<len><id>` or `E<len><id>` leaf.
3. If it is a modifier sigil (`P`, `Q`, `X`), recurse once for the inner component.
4. If it is `A`, read the dimension digits, consume the `_`, then recurse for the element type.
5. If it is `F`, read the arity, recurse arity times for parameters, then recurse once for the return type.
6. If it is a lowercase builtin letter, the component is complete.

Unlike the link-name parser, a type-component parser does not consume to end-of-string: it consumes exactly one
component and returns, leaving any trailing input for a containing parse to handle.

### `unsafe` Lowering

L1 treats `unsafe func(...) -> T` as a distinct type from `func(...) -> T`. Function pointers of the two types are not
interchangeable in L1 source: assigning one to the other requires explicit coercion at a trust boundary.

The current C lowering does **not** preserve this distinction. Both safe and unsafe function-pointer types lower to the
same C function-pointer typedef. The safety contract is enforced entirely by L1 typing and interface files; once a value
crosses into generated C or into FFI, the `unsafe` marker is no longer observable.

This is acceptable for L1 because Dea source code only enters generated C through L1-typed call sites, and generated C
is not a stable surface intended for hand-written consumers. The consequence at trust boundaries:

- C code calling into Dea cannot statically observe whether a Dea function pointer is `unsafe`.
- Dea code calling into C through `extern` declarations carries the `unsafe` marker on the L1 side regardless of the C
  signature.
- Generated runtime headers do not expose the safe/unsafe distinction.

A future ABI revision may distinguish the two at the C level (e.g. via separate typedefs, a wrapper struct, or a
type-component appended to the link name) if FFI requirements demand it. The type-component layer already encodes the
distinction (`X` modifier) and is the natural place for any such extension.

## Generated Helper Names

The Stage 1 C backend also emits helper names that are ABI-visible in generated C but are not LBI source symbols.

- Builtin C typedefs use the runtime-owned `dea_*` names, such as `dea_int`, `dea_uint`, `dea_bool`, and `dea_string`.
- Runtime-owned nullable wrappers use `dea_opt_*`, such as `dea_opt_int`, `dea_opt_ulong`, and `dea_opt_string`.
- Generated nullable wrappers for non-runtime aggregate types use `dea_opt_s_<lbi-name>` for structs and
  `dea_opt_e_<lbi-name>` for enums.
- Nested nullable helper names preserve ordered constructor shape in the wrapped payload key. The current helper key
  uses `n_` for nullable payloads, `p_` for pointer payloads, and `a<N>_` for array payloads, so `int??` uses
  `dea_opt_n_int` and `int*??` uses `dea_opt_n_p_int`.
- Nullable pointers and nullable function pointers use the `NULL` niche only when the immediate nullable payload is a
  non-nullable pointer-shaped value. For example, `int*?` lowers as `dea_int*`; `int*??` needs the outer
  `dea_opt_n_p_int` wrapper; `int?*?` lowers as `dea_opt_int*`.
- Function pointer typedefs use `dea_func_` plus the current signature key, such as `dea_func_int_int_int`.
- Matching safe and unsafe function pointer types share the same C typedef spelling by design (see
  [`unsafe` Lowering](#unsafe-lowering)).

These helper spellings are part of the current implemented ABI surface. Replacing them with the type-component grammar
above would be an ABI migration, not a compatible clarification.

## Linkage and Visibility

Linkage in the generated C and object output is driven by the module's export manifest.

### Exported Symbols

- Symbols that are explicitly or implicitly exported keep external linkage.
- In generated C, they are emitted without the `static` specifier.
- This applies to functions, `let` bindings, and `const` bindings.

### Non-Exported Symbols

- Top-level symbols that are not exported are emitted with internal linkage (`static`).
- This allows the host C compiler to perform better optimization, such as inlining and dead-stripping.
- `static` does not apply to struct or enum type definitions, which have no C-level storage class; the LBI mangling
  alone gives them stable identity.

### Constants Exception

Exported `const` bindings are emitted with global linkage to satisfy ABI linking requirements:

```c
const T __deaM...S... = value;
```

Non-exported constants remain internal:

```c
static const T __deaM...S... = value;
```

## C FFI and Externs

- Legacy `extern func` declarations bypass LBI mangling entirely and are emitted with their declared C spelling.
- The planned `extern "C"` block surface also bypasses LBI mangling for declarations inside the block.
- Per-symbol C link-name overrides, the mechanism for opting individual Dea declarations out of LBI mangling, and the
  final `cstr` boundary rules are deferred to the forthcoming C FFI ADR. `cstr` is currently treated as a distinct
  boundary type at the L1 surface; its ABI representation is intentionally unspecified in this document and will be
  resolved alongside the rest of the FFI design.

## Portability

The LBI mangling and linkage scheme uses only:

- Characters from the ISO C99 identifier alphabet `[A-Za-z0-9_]`.
- Standard C storage-class specifiers (`static`, `const`).

Generated C is expected to compile under `cc -std=c99 -pedantic-errors`. The LBI does not depend on GCC/Clang/MSVC
`$`-in-identifier extensions, GNU statement expressions, or any other non-ISO feature for symbol naming or linkage
selection.

## Compatibility Notes

The compact type-sigil grammar is compatible as a type-key extension, but not as a literal replacement for existing
public link names.

Compatible without implementation changes:

- Compact one-letter builtin type codes for future type keys.
- Recursive `P`, `Q`, `F`, and `X` type components.
- `_`-terminated fixed-size array dimensions for future array wrapper names.
- Treating `unsafe` as type-level in L1 while keeping the current C representation for function pointers.
- Distinguishing `S` (struct) from `E` (enum) in type-component nominal-type references while keeping `S` for both in
  the link-name layer.

Incompatible with current emitted names unless handled as a deliberate migration:

- Renaming source functions or top-level values from `S` to a finer-grained category sigil (e.g. `N`) in the link-name
  layer.
- Renaming enum types from `S` to `E` in their public C struct names emitted by the link-name layer.
- Appending function type encodings to public function symbols.
- Replacing current `dea_opt_*` and `dea_func_*` helper typedef names with type-component names.
- Committing `cstr` to either a nominal ABI type or a structural alias for `byte*` (sigil `Ph`) before the C FFI ADR
  lands.

Reserved for future use, not yet implemented:

- Empty array dimension (`A_<elem>`) for unbounded or incomplete-extent arrays.
- Substitution back-references for repeated subtrees in type components.
- Calling-convention modifiers folded into the `F` sigil or as a separate top-level type-component sigil.
- Generic / type-parameter sigils.
