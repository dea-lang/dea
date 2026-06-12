# ADR-0002: Pointer Model and No Address-of

- Decision date: 2025-12-06
- Last edited: 2026-05-20
- Status: Accepted

## Context

L0 includes pointer types (`T*`, `T*?`) and dereference (`*expr`), but a key question arose at the start: should L0
expose an address-of operator (`&`) that takes the address of a local variable or struct field?

This decision builds on the three-layer runtime boundary established in
[ADR-0001](0001-foundational-language-contract.md).

## Decision

`&` is excluded from L0. There is no way to take the address of a local variable, stack-allocated field, or array
element.

Pointer values in L0 originate exclusively from:

- Runtime/kernel functions (`rt_alloc`, `rt_string_*`, etc.).
- Other functions that already hold heap pointers.
- Fields inside heap-allocated structs accessed through an existing pointer.

Pointer arithmetic is not part of the L0 surface. Dereference (`*expr`) and field access through pointer auto-deref
(`ptr.field`) are the only pointer operations in Stage 1.

## Rationale

- Without `&`, there is no way to create a pointer to a stack variable whose lifetime ends before the pointer does. The
  entire class of dangling-stack- pointer bugs is structurally impossible.
- All pointer values ultimately refer to heap storage managed through the C kernel, keeping lifetime reasoning simple
  and auditable.
- The restriction is sufficient for writing the bootstrap compiler: all data structures the compiler needs can be
  heap-allocated.

## Consequences

- `&` remains a reserved token, kept for potential future use under a non-UB semantics with explicit lifetime
  constraints.
- Pointer indexing syntax (`p[i]`) was removed from Stage 1 on 2026-01-14 pending proper array-type support. It is
  re-enabled in L1 under the `unsafe func` gate (see
  `l1/docs/decisions/0010-unsafe-marker-and-raw-pointer-indexing.md`).
- Stage 2 type checker enforces that `&` produces a diagnostic rather than generating code.

## Related Plans

- [l0/work/plans/bug-fixes/closed/2026-05-08-stage2-pointer-indexing-parity-noref.md](../../work/plans/bug-fixes/closed/2026-05-08-stage2-pointer-indexing-parity-noref.md):
  restored Stage 2 parity for pointer-indexing diagnostics

## Current Docs

- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §3 (pointer model and address-of decision)
- [l0/docs/reference/ownership.md](../reference/ownership.md): ownership rules for pointers
