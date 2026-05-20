# ADR-0009: Module Visibility, Exports, and Imports

- Decision date: 2026-04-24
- Last edited: 2026-05-20
- Status: Accepted

## Context

L1 separate compilation requires a defined public surface for each module. L0's open-import model (all top-level names
visible to any importer) is too permissive for a language with a stable ABI. The question was how modules declare their
public surface and how importers refer to it.

## Decision

L1 uses an explicit export manifest at the module level, plus aliased and selective import forms:

**Export manifest:**

```ebnf
ExportDecl ::= "export" "*" ";"
             | "export" IdentList ";"
IdentList  ::= Ident ("," Ident)*
```

- `export *;` exports every top-level symbol (including `_`-prefixed names).
- `export a, b;` exports exactly the listed names.
- No manifest: every top-level name except `_`-prefixed names is exported (backward-compatible open default).
- There is no per-declaration `pub`/`priv` modifier; visibility is a module-level manifest.
- At most one export manifest per module, placed immediately after the `module` declaration.

**Import forms:**

```ebnf
ImportDecl ::= "import" ModulePath ";"                          (* open import *)
             | "import" ModulePath "as" Ident ";"              (* alias import *)
             | "import" "{" IdentList "}" "from" ModulePath ";"  (* selective import *)
```

**Module identity:**

- A module's canonical identity is its dotted source path (e.g., `std.integer`), not the filesystem path.
- Filesystem paths, search roots, and platform separators are discovery details.

**Public-surface contract:**

- Only exported names from a module are accessible to importers.
- `_`-prefixed names are treated as private by convention (excluded from the open-manifest default).
- The export set drives LBI symbol mangling for separate compilation.

## Rationale

- A module-level manifest is simpler to enforce and audit than per-declaration visibility modifiers; there is only one
  place to look to understand a module's public surface.
- Aliased imports (`import M as N`) allow callers to avoid name collisions without renaming symbols in the defining
  module.
- Selective imports (`import { a, b } from M`) reduce namespace pollution in modules that need only a few names from a
  large dependency.
- Module identity as a dotted path (not a filesystem path) keeps LBI mangling and the import graph stable across
  refactors that move files within the source tree.

## Consequences

- The compiler must enforce that only exported names are accessible across module boundaries.
- The export set is the input to LBI symbol mangling (see [l1/docs/decisions/0008-lbi-symbol-mangling.md][lbi]).
- The broader separate-compilation initiative is still open; this ADR covers the visibility/import decisions already
  implemented.

## Related Plans

- [l1/work/plans/features/closed/2026-04-24-export-manifests-and-aliased-imports-noref.md][export-plan]

## Related Initiatives

- [l1/work/initiatives/0001-separate-compilation-and-linking.md][initiative]: broader rollout (open)

## Current Docs

- [l1/docs/specs/compiler/module-visibility-and-imports.md][visibility-spec]: normative spec (Version 2026-05-19)
- [l1/docs/specs/compiler/abi.md][abi-spec]: LBI symbol mangling for exported names

[abi-spec]: ../specs/compiler/abi.md
[export-plan]: ../../work/plans/features/closed/2026-04-24-export-manifests-and-aliased-imports-noref.md
[initiative]: ../../work/initiatives/0001-separate-compilation-and-linking.md
[lbi]: 0008-lbi-symbol-mangling.md
[visibility-spec]: ../specs/compiler/module-visibility-and-imports.md
