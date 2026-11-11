# ADR-0052: Owned Dynamic Byte Buffers

- Decision date: 2026-11-05
- Last edited: 2026-11-11
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

Expose `size` for the number of initialized logical bytes and `capacity` for reserved byte slots.

Accept borrowed slice subranges only for synchronous copying. Append from another buffer copies its full logical
contents and supports self-append even when growth moves storage. Return no backing pointer or slice. The explicit
unsafe `with_raw_range` exception permits synchronous callback access to a validated logical range without allowing
storage to escape. The callback keeps the buffer live and must not resize, reallocate, free, or reenter operations on it
through any alias. The helper checks returned progress and preserves logical size/capacity; it neither pins storage nor
statically enforces the borrow contract. String conversion is explicit copying in both directions and preserves embedded
NUL and non-UTF-8 bytes without validation.

The callback protocol and its allocation boundary are recorded in
[l1/docs/decisions/0063-synchronous-byte-buffer-range-actions.md][range-actions].

## Rationale

An opaque API preserves length and capacity invariants without exposing `VectorBase` or introducing a new owned-slice
language feature. Explicit cleanup fits existing L1 resource lifetimes. Copying makes mutation and lifetime independent
across buffers and ARC strings, while retained capacity and geometric growth support bounded reusable I/O storage.

The `size` name follows existing container APIs such as `vec_size` and `sb_size`.

## Consequences

Consumers must establish exactly one cleanup owner and coordinate aliases. Borrowed input must remain live during an
append call; no safe public API can derive a slice from buffer storage. The module provides no shared mutable or
cross-thread contract, recoverable allocation result, secure erasure, or zero-copy conversion. `ByteArray` remains
available. Provider modules use the unsafe callback boundary without returning views and keep native operations outside
`std.bytes`.

## Related Plans

- [l1/work/plans/features/closed/2026-08-30-dynamic-byte-buffers-noref.md][buffer-plan]
- [l1/work/plans/refactors/closed/2026-11-10-byte-buffer-range-actions-noref.md][range-plan]

## Current Docs

- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/ownership.md][ownership]

[buffer-plan]: ../../work/plans/features/closed/2026-08-30-dynamic-byte-buffers-noref.md
[ownership]: ../reference/ownership.md
[range-actions]: 0063-synchronous-byte-buffer-range-actions.md
[range-plan]: ../../work/plans/refactors/closed/2026-11-10-byte-buffer-range-actions-noref.md
[stdlib]: ../reference/standard-library.md
