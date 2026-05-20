# ADR-0006: Module System and Import Semantics

- Decision date: 2025-12-06
- Last edited: 2026-05-20
- Status: Accepted

## Context

L0 source code is split across multiple files. A module system was needed to define the unit of compilation, how names
are organized across files, and how one module accesses names defined in another. The decision needed to complement the
name disambiguation model (see ADR-0012) without introducing a package manager or hierarchical build system.

## Decision

One source file corresponds to one module. The module system grammar is:

```
CompilationUnit ::= ModuleDecl ImportDecl* TopLevelDecl*
ModuleDecl      ::= "module" ModulePath ";"
ImportDecl      ::= "import" ModulePath ";"
ModulePath      ::= Ident ("." Ident)*
```

Semantics:

- Module paths are dot-separated identifiers (`std.io`, `sys.memory`). There are no hierarchical packages beyond this
  convention; each component must be a valid identifier.
- `import M` opens module `M` into the current namespace, making all of `M`'s top-level names available unqualified.
  This is an open (wildcard) import.
- When two imported modules define a name with the same spelling, it is not an automatic error; the conflict is only
  diagnosed when the ambiguous name is actually used. At the use site, a qualified reference (`M::Name`) resolves the
  ambiguity (see ADR-0012).
- The module path is also the directory path used by the compiler to locate the source file. No import aliases or
  selective imports exist in L0 (that extension is introduced in L1).
- There is no circular import detection requirement in the bootstrap; the compiler processes modules in dependency
  order.

## Rationale

- Open imports keep call sites concise; for a bootstrap language where most stdlib surface is well-known, unqualified
  access is the ergonomic default.
- Deferring conflict detection to the use site avoids false positives when two modules happen to define the same name
  but only one is actually used.
- Flat dot-separated paths avoid the complexity of a hierarchical package registry while still allowing namespaced names
  (`std.io`, `std.integer`) that are readable and sortable.

## Consequences

- Name conflicts from open imports are diagnosed lazily (at the ambiguous use site), not eagerly at the `import` line.
  Code with many imports may encounter surprising resolution errors at use sites rather than at import sites.
- The compiler uses module paths as source file lookup keys, which ties module identity to directory layout.
- L1 extends this model with selective and aliased imports and explicit export manifests; the L0 open-import model is
  the simpler foundation.

## Related Plans

None (pre-plan era).

## Current Docs

- [l0/docs/reference/grammar.md](../reference/grammar.md): §2 (module and import syntax)
- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §6 (name disambiguation, adjacent section)
