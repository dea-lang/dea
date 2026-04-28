# Dea/L1 Binary Interface (LBI)

Version: 2026-04-28

Status: Finalized

This document specifies the binary interface and symbol mangling rules for the Dea/L1 compiler.

## Symbol Mangling

To ensure stable link-time identity across compilation units and to avoid collisions with C keywords or other symbols,
Dea/L1 uses a **tagged-section, length-prefixed mangling scheme**. The scheme uses only characters drawn from the ISO
C99 identifier alphabet `[A-Za-z0-9_]`, so generated names are valid identifiers under strict ISO/ANSI C99 — no compiler
extension is required.

### Format

```
__dea <category-section>+
```

A *category section* is a single uppercase ASCII letter — the **sigil** — followed by one or more length-prefixed *name
components*:

```
<sigil> ( <decimal-len> <name-component> )+
```

- **`__dea`** — fixed prefix on every mangled name.
- **`<sigil>`** — one uppercase ASCII letter from the LBI category-sigil registry.
- **`<decimal-len>`** — one or more decimal digits giving the byte length of the immediately following
  `<name-component>`.
- **`<name-component>`** — a Dea source identifier. Dea identifiers cannot start with a digit, so the boundary between
  `<decimal-len>` and `<name-component>` is unambiguous.

A section ends when the next character is either another sigil (a non-digit letter) or end-of-string. No explicit
terminator is needed.

### Category sigils

The full uppercase alphabet `A`–`Z` is **reserved by the LBI** for category sigils. Defined sigils:

| Sigil | Meaning                                                                    |
| ----- | -------------------------------------------------------------------------- |
| `M`   | Module path. Each component is one segment of the dotted source path.      |
| `S`   | Symbol name. Exactly one component.                                        |
| `I`   | Module lifecycle symbol. Exactly one compiler-defined lifecycle component. |

Other uppercase letters are reserved for future categories (provisionally — type instantiation, generic parameters,
variant tags, function-signature overload keys, impl-block identifiers — none are committed to here). User-defined Dea
identifiers MUST NOT influence sigil choice; sigils are a closed set fixed by this spec. The `I` section is reserved for
compiler-generated module lifecycle entry points and is not a source-level symbol namespace.

### Section ordering

Sections appear in a fixed order. In this revision the order is:

```
M S
M I
```

Future categories slot in by spec amendment with a defined position relative to the existing ones. Mangling is
deterministic — there is exactly one valid encoding for any source symbol or compiler-generated module lifecycle entry
point, and the demangler can therefore decode any LBI name without external context.

### Examples

| Source                                   | Mangled                              |
| ---------------------------------------- | ------------------------------------ |
| `main::main`                             | `__deaM4mainS4main`                  |
| `std.math::abs`                          | `__deaM3std4mathS3abs`               |
| `std.collections.list::push`             | `__deaM3std11collections4listS4push` |
| `demo.main::Point` (struct)              | `__deaM4demo4mainS5Point`            |
| `demo.main::static` (let named `static`) | `__deaM4demo4mainS6static`           |
| module lifecycle `demo.main::init`       | `__deaM4demo4mainI4init`             |

The leading `__` (two underscores) places every LBI-mangled name in the implementation-reserved namespace defined by ISO
C §7.1.3, so collisions with user-defined C identifiers and with C keywords are excluded by language rule. The `__dea`
prefix carves out a stable LBI subspace within that namespace.

### Module lifecycle components

Module lifecycle symbols are compiler-generated symbols in the `I` section. They are module-scoped entry points used by
the backend/runtime orchestration and cannot collide with source-level `S` symbols.

Defined lifecycle components:

| Component | Meaning                                                       |
| --------- | ------------------------------------------------------------- |
| `init`    | Initializes deferred top-level `let` bindings for the module. |

Future lifecycle components, such as an `at_exit` hook, must be added by ABI amendment before emission.

### Demangling

Parse left-to-right after the fixed `__dea` prefix:

1. Read the next character. If it is a non-digit, treat it as a category sigil and open a new section.
2. Otherwise read a run of decimal digits as a length, then read exactly that many bytes as the name component, and
   append the component to the current section.
3. Stop at end-of-string. If a section has zero components, the name is malformed.

The closed sigil set means a demangler can be written without consulting external tables: every uppercase letter is a
section opener; every digit run is a length prefix.

## Linkage and Visibility

Linkage in the generated C and object output is driven by the module's export manifest.

### Exported Symbols

- Symbols that are explicitly or implicitly exported keep **external linkage** (global).
- In generated C, they are emitted without the `static` specifier.
- This applies to functions, `let` bindings, and `const` bindings.

### Non-Exported Symbols

- Top-level symbols that are not exported are emitted with **internal linkage** (`static`).
- This allows the host C compiler to perform better optimization, such as inlining and dead-stripping.
- `static` does not apply to struct or enum *type* definitions, which have no C-level storage class; the LBI mangling
  alone gives them stable identity.

### Constants Exception

Exported `const` bindings are an exception to the earlier `static const` default. To satisfy ABI linking requirements,
they are emitted with global linkage: `const T __deaM... S... = value;`

Non-exported constants remain internal: `static const T __deaM... S... = value;`

## C FFI and Externs

- Declarations inside an `extern "C"` block bypass LBI mangling entirely.
- They are emitted with their declared C spelling (or a provided link-name override).
- Legacy `extern func` declarations also bypass mangling. This is the only currently supported FFI escape hatch; the
  full `extern "C"` surface is deferred to the FFI plan.

## Portability

The LBI mangling and linkage scheme uses only:

- Characters from the ISO C99 identifier alphabet `[A-Za-z0-9_]`.
- Standard C storage-class specifiers (`static`, `const`).

Generated C is expected to compile under `cc -std=c99 -pedantic-errors`. The LBI does **not** depend on the
GCC/Clang/MSVC `$`-in-identifier extension, the GNU statement-expression extension, or any other non-ISO feature for
symbol naming or linkage selection.
