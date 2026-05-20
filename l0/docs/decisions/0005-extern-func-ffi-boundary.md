# ADR-0005: `extern func` and the FFI Boundary

- Decision date: 2025-12-06
- Last edited: 2026-05-20
- Status: Accepted

## Context

L0 programs need to call C runtime functions (memory allocators, I/O helpers, ARC retain/release, etc.) without
introducing a C header parsing step into the compiler. The question was how to declare C-callable functions and what
guarantees the L0 type system makes across that boundary.

## Decision

`extern func` declarations introduce a C symbol by name without mangling:

```
ExternFuncDecl ::= "extern" "func" Ident "(" ParamList? ")" "->" Type ";"
```

Semantics:

- The function name is emitted as-is into the C translation unit; no `dea_*` mangling is applied.
- The caller is fully responsible for ABI-correctness: matching the C parameter types, return type, and calling
  convention. The L0 type system only checks that call sites match the declared L0 type signature.
- L0's no-undefined-behavior guarantee applies only to L0-authored code. There is no UB guarantee for code reached
  through an `extern func` boundary.
- `extern func` does not expose C header parsing; every extern declaration must be written by hand.
- Variadic C functions and function pointers to C functions are not modeled as `extern func`; they require a different
  binding strategy.

The C backend emits `extern func` declarations as forward declarations (no definition body).

## Rationale

- Keeping `extern func` name-based and un-mangled makes the C symbol directly visible for linking without a separate
  export table.
- Deferring ABI responsibility to the caller is the minimal safe contract: it avoids false safety guarantees for a
  boundary the compiler cannot fully type-check.
- Omitting C header parsing keeps the Stage 1 Python compiler self-contained and avoids a dependency on a C preprocessor
  or header database at compile time.

## Consequences

- Runtime functions called from L0 (such as `rt_string_retain`, `rt_alloc`, and I/O helpers) require an `extern func`
  declaration at the top of each file that uses them, or in an imported module that re-exports them.
- ABI mismatches between an `extern func` declaration and the actual C symbol are not diagnosed by the L0 compiler; they
  are the programmer's responsibility.
- `extern func` symbols are intentionally not mangled, which distinguishes them from all L0-authored top-level
  functions.

## Related Plans

None (pre-plan era).

## Current Docs

- [l0/docs/reference/grammar.md](../reference/grammar.md): §3.2 (extern func declaration grammar)
- [l0/docs/reference/c-backend-design.md](../reference/c-backend-design.md): extern func emission, non-mangled symbols
- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §3 (pointer model and extern pointer
  origins)
