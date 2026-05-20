# ADR-0010: Unsafe Marker and Raw-Pointer Indexing

- Decision date: 2026-05-08
- Last edited: 2026-05-20
- Status: Accepted

## Context

L1 needs raw-pointer indexing (`ptr[i]` for `ptr: T*`) for low-level systems code. Unlike fixed-size array indexing
(which is bounds-checked), raw-pointer indexing has no upper-bound to check against and is inherently unsafe: the caller
must prove the index is in range, and the compiler cannot verify this statically.

A gate was needed to prevent raw-pointer indexing from appearing in ordinary safe code.

## Decision

The `unsafe` keyword is a function-level contract marker:

- `unsafe func`: declares that the function body may perform unchecked raw-memory operations.
- Raw-pointer indexing (`ptr[i]` where `ptr: T*`) is accepted **only** inside `unsafe func` bodies; it is rejected in
  safe function bodies.
- Ordinary pointer dereference (`*p`) and pointer field access (`p.field`) remain available in safe code.
- Safe code may call an `unsafe func` value today; the marker is a contract annotation, not a call-site gate. This may
  be tightened in future.
- `unsafe func` types in function pointer signatures (`unsafe func(T) -> U`) are a distinct type from `func(T) -> U`;
  they are not compatible.

## Rationale

- Gating raw-pointer indexing on `unsafe func` makes the hazard visible in the function signature rather than buried in
  the body.
- Allowing ordinary dereference and field access in safe code keeps the common case ergonomic: most pointer use does not
  need the `unsafe` gate.
- Function-level marking (rather than expression-level `unsafe { }` blocks) is simpler to implement and sufficient for
  the current bootstrap stage.

## Consequences

- Any function that uses `ptr[i]` raw indexing must declare itself `unsafe`; this propagates the unsafe contract to
  callers that care.
- The `unsafe` marker is tracked in the function type, so function pointers preserve the safety annotation through
  indirect calls.

## Related Plans

- [l1/work/plans/features/closed/2026-05-08-unsafe-function-marker-noref.md][unsafe-marker]
- [l1/work/plans/features/closed/2026-05-09-raw-pointer-indexing-semantics-noref.md][ptr-indexing]
- [l1/work/initiatives/closed/0004-array-primitives-and-unsafe-marker.md][initiative]

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §7 (pointer and ownership policy, pointer indexing)

[design-decisions]: ../reference/design-decisions.md
[initiative]: ../../initiatives/closed/0004-array-primitives-and-unsafe-marker.md
[ptr-indexing]: ../../work/plans/features/closed/2026-05-09-raw-pointer-indexing-semantics-noref.md
[unsafe-marker]: ../../work/plans/features/closed/2026-05-08-unsafe-function-marker-noref.md
