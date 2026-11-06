# ADR-0052: Owned Dynamic Byte Buffers

- Decision date: 2026-11-05
- Last edited: 2026-11-06
- Status: Accepted

## Context

Incremental binary I/O needs reusable growable storage distinct from immutable strings. Fixed `ByteArray` remains
useful, while the raw `VectorBase` representation exposes untyped storage and cannot define the public buffer boundary.
L1 slices borrow fixed-array storage and cannot safely serve as escaping views into a resizable allocation.

## Decision

Expose `std.bytes::ByteBuffer` as an opaque struct used only through pointers. Constructors return one explicit cleanup
obligation, consumed exactly once by `free`, including through `with`. Aliases borrow that obligation; the type system
does not enforce unique ownership. The module privately owns a raw allocation using existing checked runtime primitives.

Use `int` for lengths, capacities, indexes, and counts. Reserve grows capacity geometrically with checked arithmetic and
saturation at `int_max`; shrinking and clearing retain capacity. Resize zeroes every newly visible byte. Clear does not
securely erase storage. Invalid sizes/ranges, append overflow, and allocation failure terminate execution, consistently
with the existing container allocation policy and independently of checked versus unchecked runtime selection.

Expose `size` for the number of initialized logical bytes and `capacity` for reserved byte slots. Do not provide a `len`
compatibility alias; `dea::len` remains the intrinsic for strings, arrays, and slices.

Accept borrowed slice subranges only for synchronous copying. Append from another buffer copies its full logical
contents and supports self-append even when growth moves storage. Export no backing pointer or slice. String conversion
is explicit copying in both directions and preserves embedded NUL and non-UTF-8 bytes without validation.

## Rationale

An opaque API preserves length and capacity invariants without exposing `VectorBase` or introducing a new owned-slice
language feature. Explicit cleanup fits existing L1 resource lifetimes. Copying makes mutation and lifetime independent
across buffers and ARC strings, while retained capacity and geometric growth support bounded reusable I/O storage.

The `size` name follows existing container APIs such as `vec_size` and `sb_size` and avoids shadowing the implicitly
imported `dea::len`. A local `len` alias would retain that shadow warning even when callers qualify their imports.

## Consequences

Consumers must establish exactly one cleanup owner and coordinate aliases. Borrowed input must remain live during an
append call; no safe public API can derive a slice from buffer storage. The module provides no shared mutable or
cross-thread contract, recoverable allocation result, secure erasure, or zero-copy conversion. `ByteArray` remains
available. Future concrete file and entropy APIs can accept a buffer with checked ranges without returning views.

Callers of the former `std.bytes::len` API must migrate to `size` and rebuild dependent compiled artifacts because the
exported symbol and module interface change. The rename does not change buffer layout or ownership behavior.

## Related Plans

- [l1/work/plans/features/closed/2026-08-30-dynamic-byte-buffers-noref.md][buffer-plan]

## Current Docs

- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/ownership.md][ownership]

[buffer-plan]: ../../work/plans/features/closed/2026-08-30-dynamic-byte-buffers-noref.md
[ownership]: ../reference/ownership.md
[stdlib]: ../reference/standard-library.md
