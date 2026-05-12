# Dea/L1 Binary Interface (LBI)

Version: 2026-05-12

Status: Finalized

This document specifies the binary interface and symbol mangling rules for the Dea/L1 compiler.

Dea/L1 uses a **unified, tagged-section, recursive mangling scheme**. The scheme collapses link-time identity and
type-level information into a single grammar. Every LBI-mangled name is a valid ISO C99 identifier drawn from the
alphabet `[A-Za-z0-9_]`.

## Format

```ebnf
lbi-name        = "__dea" module-section terminal
module-section  = "M" (length identifier)+
terminal        = value | struct-type | enum-type | lifecycle
value           = "N" length identifier [ type-component ]
struct-type     = "S" length identifier
enum-type       = "E" length identifier
lifecycle       = "I" length identifier
length          = digit+
identifier      = <length bytes from a Dea identifier>
type-component  = <as defined in §Type Components>
```

- `__dea` is the fixed prefix on every LBI-mangled name.
- `M` opens the module-path section. Each component is one segment of the dotted source path.
- `N` marks a value entity (a function or a `let`/`const` binding).
- `S` marks a struct type.
- `E` marks an enum type.
- `I` marks a compiler-generated module-lifecycle component.
- `length` is one or more decimal digits giving the byte length of the immediately following identifier.

### Values and Functions

Value terminals (`N`) distinguish between plain bindings and functions via the presence of an optional `type-component`
suffix:

- **Plain bindings** (`let`, `const`) omit the type component.
- **Functions** append a function-type component (sigil `F` or `XF`).

This distinction allows the static linker to resolve calls to the correct overload (when overloading is introduced) and
produces a link error if a value is called as a function or vice-versa across module boundaries.

### Examples

| Source                                     | Mangled                     |
| ------------------------------------------ | --------------------------- |
| `main::main` (`func() -> void`)            | `__deaM4mainN4mainF0v`      |
| `std.math::abs` (`func(int) -> int`)       | `__deaM3std4mathN3absF1ii`  |
| `std.io::prints` (`func(string) -> void`)  | `__deaM3std2ioN6printsF1cv` |
| `demo.main::Point` (struct)                | `__deaM4demo4mainS5Point`   |
| `demo.main::Color` (enum)                  | `__deaM4demo4mainE5Color`   |
| `demo.main::static` (`let` named `static`) | `__deaM4demo4mainN6static`  |
| `unsafe func(int*) -> void` exported       | `__deaM<...>N<name>XF1Piv`  |
| module lifecycle `demo.main::init`         | `__deaM4demo4mainI4init`    |

## Type Components

Type components are used to encode function signatures into link names and to generate deterministic names for
structural types like array wrappers.

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

The grammar is self-delimiting and parseable by recursive descent.

### Type Sigils

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

## C FFI and Externs

Declarations marked `extern` or within an `extern "C"` block bypass LBI mangling entirely and use their declared C
spelling. `cstr` boundary rules are deferred to the C FFI ADR.

## Portability

The LBI uses only ISO C99 identifier characters `[A-Za-z0-9_]`. Generated C is expected to compile under
`cc -std=c99 -pedantic-errors`.
