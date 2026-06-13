# Dea Code Style Guide

Version: 2026-06-13

Conventions for writing Dea source (`.l0` and `.l1`). This guide records the style that is already used near-universally
across the Dea source corpus so that it is explicit rather than implicit.

These are conventions, not language rules. The grammar and neither compiler enforce identifier case, layout, or file
structure; nonconforming code still lexes, parses, and compiles. Follow the guide for consistency, not because the
toolchain requires it. For the rules that the language does enforce on token spelling and source encoding, see the
normative
[docs/specs/language/source-text-and-language-vocabulary.md](../specs/language/source-text-and-language-vocabulary.md).

## Scope

This guide applies to Dea source across language levels unless a level-local document narrows it. It complements, and
does not override, the level grammars ([l0/docs/reference/grammar.md](../../l0/docs/reference/grammar.md),
[l1/docs/reference/grammar.md](../../l1/docs/reference/grammar.md)) and the shared source-text specification.

## Identifier case

| Kind                             | Convention   | Examples                                      |
| -------------------------------- | ------------ | --------------------------------------------- |
| Functions                        | `snake_case` | `make_paths`, `random_coprime_stride`, `main` |
| Local variables (`let`)          | `snake_case` | `out_path`, `entry_ptr`, `i`, `result`        |
| Parameters                       | `snake_case` | `module_name`, `expr_id`, `self`, `value`     |
| Constants (`const`)              | `snake_case` | `origin`, `favorite`                          |
| Module path components           | `snake_case` | `std.integer`, `name_resolver`                |
| Types (`struct`, `enum`, `type`) | `PascalCase` | `Token`, `Result`, `ExprId`                   |

Notes:

- A single lowercase word (`main`, `i`, `result`) is the one-word form of `snake_case` and needs no underscore. It is
  not a separate style.
- Constant-like sentinel values occasionally use `UPPER_SNAKE_CASE` (for example `ISET_EMPTY`, `HM_OCCUPIED`). This is a
  minor, accepted exception for fixed sentinel constants.
- Do not use camelCase for value identifiers. Write `get_value`, not `getValue`; `hello_world_messages`, not
  `helloWorldMessages`. The convention holds throughout the source corpus, which contains no camelCase value
  identifiers.

## File structure

A source file is ordered:

1. **License header.** A block comment carrying an SPDX identifier and a copyright line:

   ```
   /*
    * SPDX-License-Identifier: MIT OR Apache-2.0
    * Copyright (c) 2026 gwz
    */
   ```

2. **Module declaration.** `module <snake_case>;`, where the name matches the file's base name (for example
   `module backend;` in `backend.l0`).

3. **Imports.** Standard-library imports (`std.*`, `sys.*`) first, then a blank line, then local module imports. Sort
   alphabetically within each group:

   ```
   import std.string;
   import std.vector;

   import ast;
   import codegen_options;
   ```

4. **Declarations.** Types, functions, and constants.

## Comments

- Use `/** ... */` Doxygen/Javadoc doc-comment blocks above declarations, with `@param` and `@return` tags where they
  apply.
- Use `//` for inline and single-line comments.

This matches the monorepo-wide rule that C and Dea source files use Doxygen/Javadoc-style block comments.

## Layout

- Indent with 4 spaces. Do not use tabs.
- Use K&R brace placement: the opening `{` stays on the same line as the `func`, `struct`, `enum`, `if`, `while`, or
  `for` it belongs to; the closing `}` sits on its own line.

```
func gcd(a: int, b: int) -> int {
    while (b != 0) {
        let t = b;
        b = a % b;
        a = t;
    }
    return a;
}
```

## Type and ownership notation

- Pointer: `T*`. Optional: `T?`. Optional pointer: `T*?`.
- Member access auto-dereferences: write `ptr.field`, not `(*ptr).field`.

Ownership and memory-management rules (`new`/`drop`, ARC strings, container ownership) are normative in
[l0/docs/reference/ownership.md](../../l0/docs/reference/ownership.md); this guide covers only the surface notation.
