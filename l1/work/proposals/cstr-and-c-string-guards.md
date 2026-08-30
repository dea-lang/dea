# `cstr` and Scoped C-String Guards Proposal

Version: 2026-08-30

Status: Proposed

## Summary

Define a typed C-string boundary for L1 after native strings can represent non-terminated logical views. The proposed
surface introduces builtin `cstr`, explicit pointer conversions, a call-scoped `string as cstr` conversion, and an
internal guard that owns a terminated string for the duration of a C call.

This document is a design proposal, not an implementation plan. Accepted decisions should graduate into the L1 C-FFI
initiative, a new or substantively revised feature plan, and stable language/runtime documentation before
implementation.

## Context

The [cheap string slices plan] allows a `string` to describe an interior span whose logical end is not necessarily
followed by NUL. Consequently, arbitrary `string -> cstr` conversion cannot remain an unrestricted zero-cost pointer
reinterpretation.

The planned string runtime provides two relevant primitives:

```c
dea_string _rt_string_ensure_terminated(dea_string value);
const char *_rt_string_data(dea_string value);
```

`_rt_string_ensure_terminated` returns an owned value, retaining an already terminated heap string or copying an
interior view. These primitives can support a scoped C boundary without constraining every native string to be
terminated at its logical end.

## Goals

1. Give C declarations a type-level null-terminated pointer contract.
2. Keep ordinary Dea `string` values out of the raw C ABI.
3. Make potentially allocating string conversion explicit and lifetime-bounded.
4. Preserve zero-copy conversion for already terminated literals, full heap strings, and terminated suffix views.
5. Prevent a materialized temporary pointer from escaping its owning guard.
6. Define embedded-NUL behavior rather than inheriting silent C truncation.

## Proposed `cstr` Type

- `cstr` is a builtin C-boundary type.
- Its generated C representation is `const char *`.
- It is pointer-shaped and representation-compatible with a C byte pointer, but its Dea type is read-only.
- `cstr` and `byte*` remain distinct Dea types.
- An explicit `byte* -> cstr` cast is permitted only in an unsafe context where the programmer guarantees NUL
  termination and sufficient lifetime.
- A `cstr -> byte*` cast is rejected because it would discard the read-only contract. Bind mutable C `char *` parameters
  as `byte*`, not `cstr`.
- Ordinary `string` is not ABI-compatible with `cstr` and never crosses a C boundary unwrapped.
- A `cstr` obtained from C follows the lifetime and ownership contract of the bound C API.

The trailing-NUL guarantee is a type-level property of `cstr`, but it does not imply ownership of the pointed-to bytes.
Neither `cstr` nor an internal guard grants mutable access to Dea string storage.

## Internal Guard

The compiler and runtime use a guard built from an owned terminated `dea_string`:

```c
typedef struct {
    const char *ptr;
    dea_string held;
} _dea_cstr_guard;
```

Conceptual acquisition:

```c
_dea_cstr_guard _rt_cstr_acquire(dea_string value) {
    dea_string held = _rt_string_ensure_terminated(value);
    return (_dea_cstr_guard){
        .ptr = _rt_string_data(held),
        .held = held,
    };
}
```

Conceptual release:

```c
void _rt_cstr_release(_dea_cstr_guard *guard) {
    rt_string_release(guard->held);
    *guard = (_dea_cstr_guard){0};
}
```

The guard always owns `held`:

- a terminated static input needs no retain and release remains a no-op;
- a terminated heap input contributes one retained reference;
- a non-terminated view produces a standalone terminated heap string;
- empty input points at stable empty C-string storage.

The raw pointer remains valid until guard release.

Guard acquisition obtains its pointer only through `_rt_string_data`. It never uses a mutable string accessor. Any
terminated copy is confined to this C boundary; ordinary length-aware operations such as `CharBuffer` appends use the
bounded string-copy helper and never acquire a guard or materialize NUL-terminated storage.

## Proposed Source Conversion

```dea
foreign_call(value as cstr);
```

`string as cstr` is accepted only when the cast is the direct argument corresponding to a `cstr` parameter of an
`extern "C"` call.

The transient cast is rejected in:

- local initialization;
- assignment;
- return expressions;
- struct, enum, or array construction;
- container insertion;
- ordinary Dea calls;
- nested forwarding expressions.

This restriction gives the compiler an exact normal-path lifetime boundary for the guard and prevents a pointer to a
temporary terminated copy from being stored as an ordinary value.

## Lowering

For each transient cast, generated C must:

1. evaluate the source string once in source order;
2. materialize any ARC rvalue required to keep the source valid;
3. acquire one `_dea_cstr_guard`;
4. pass `guard.ptr` to the C function;
5. capture a non-void return value before cleanup;
6. release guards in reverse acquisition order immediately after the call;
7. yield the captured return value.

Arguments already typed as `cstr` pass directly and create no guard. The lowering must preserve the language's chosen
argument-evaluation order even when only some arguments require guards.

## Lifetime Contract

A transient pointer created from `string` is valid only until the `extern "C"` call returns. A binding for a C function
that retains a pointer must not use the transient conversion. Such an API requires explicitly managed C storage whose
lifetime satisfies the external contract.

A `cstr` returned by C is not automatically owned. Its validity remains defined by the bound library. The language
should not infer `free`, ARC, or static lifetime from the type alone.

Read-only `cstr` does not model APIs that write through `char *`. Such bindings use `byte*` and carry their allocation,
capacity, termination, and ownership rules explicitly.

## Embedded NUL Policy

A conversion intended to represent the complete Dea string must reject embedded NUL bytes; otherwise C observes only a
prefix. The proposed behavior is:

1. scan `bytes[0..len)` during guard acquisition;
2. panic with a dedicated runtime message when an embedded NUL is found;
3. never silently truncate a transient conversion;
4. consider cached NUL metadata only if profiling later justifies the added representation complexity.

This policy applies to the public conversion described here. Whether existing high-level runtime wrappers preserve their
historical truncation behavior or adopt exact rejection is a separate compatibility decision.

## C Calls That Retain Pointers

The scoped conversion is suitable for APIs that consume their string argument during the call, including common path,
environment-name, and command APIs. It is not suitable for registration, callback, asynchronous I/O, or configuration
APIs that retain the pointer.

Bindings for retaining APIs should use one of these explicit strategies:

- caller-owned C allocation with a documented release function;
- library-owned allocation returned by a constructor;
- static `cstr` storage;
- a future owning C-string buffer type distinct from raw `cstr`.

## Alternatives

### Unrestricted pointer cast

Rejected because a non-terminated view may require allocation, and a raw pointer cannot represent cleanup or the
lifetime of that allocation.

### Implicit argument conversion

Rejected for the initial surface because it hides possible allocation and a runtime embedded-NUL check. The explicit
cast makes the boundary visible in source.

### Always copy

Rejected because it imposes allocation on literals and already terminated heap strings even though the guard can safely
retain and borrow them.

### Owning `cstr` value

Deferred because ownership cannot be represented by a raw read-only pointer and would require special ABI extraction at
every C call. A separate owning buffer type can be proposed later if retaining C APIs demonstrate the need.

### Require every `string` to be terminated

Rejected because it forces substring copying and prevents cheap ordinary-string views.

## Typing and Diagnostics

The eventual implementation needs diagnostics for:

- transient conversion outside direct C-call argument position;
- ordinary `string` crossing a C boundary;
- incompatible `cstr` / `byte*` use without an allowed explicit conversion;
- attempts to cast read-only `cstr` to mutable `byte*`;
- invalid C-boundary declaration types.

The active C-FFI documents currently reserve `TYP-0760` to `TYP-0779`, but that range now contains named-argument
diagnostics. If this proposal is accepted, provisionally move the reservation to `TYP-0840` to `TYP-0859` and re-check
the live catalog before implementation.

## Validation Scenarios for a Future Plan

- Static and full heap strings convert without copying.
- Interior views materialize and clean up exactly once.
- Multiple transient arguments preserve source evaluation and reverse cleanup order.
- Non-void return values remain valid after guard cleanup.
- Escaping transient conversions are rejected.
- Existing raw `cstr` arguments incur no allocation.
- Explicit unsafe `byte* -> cstr` conversion is accepted.
- `cstr -> byte*` conversion is rejected, and mutable C buffers remain expressible as `byte*`.
- Embedded NUL is rejected.
- ARC and memory traces remain leak-free.
- Native calls that retain pointers are documented as incompatible with transient conversion.
- CharBuffer and other length-aware library operations never acquire a C-string guard or pay termination costs.

## Open Questions

1. Should the initial surface accept only `string as cstr`, or also a named boundary intrinsic with identical
   call-scoped restrictions?
2. Should C functions that retain a pointer receive an annotation visible to the analyzer, or remain entirely a binding
   contract?
3. Should exact embedded-NUL rejection later be shared with existing high-level runtime wrappers?
4. Does a future owning C-string buffer warrant a separate builtin type, or can it remain a library abstraction?

## Proposal Lifecycle

1. Link this proposal from the [C FFI initiative]; retain the closed [C FFI plan] only as a historical design record.
2. Do not document this surface as accepted language behavior while the proposal remains open.
3. On acceptance, move normative rules into L1 grammar, ownership, C-backend, and ABI documentation.
4. Carry forward only justified parts of the closed C-FFI plan, revisiting its zero-cost `string -> cstr` assumption and
   diagnostic reservations.
5. Create or update the implementation plan only after the proposal's conversion syntax, lifetime, and embedded-NUL
   decisions are accepted.

[c ffi initiative]: ../initiatives/0003-c-ffi.md
[c ffi plan]: ../plans/features/closed/2026-04-24-c-ffi-extern-c-and-cstr-noref.md
[cheap string slices plan]: ../plans/features/2026-06-21-cheap-string-slices-noref.md
