# L1 Ownership and Memory Management Reference

Version: 2026-06-19

This document describes how ownership works in current Dea/L1 bootstrap builds, covering:

- `new` / `drop` heap object lifetime
- ARC-managed `string`
- ownership rules for the copied L1 stdlib containers
- optional-string unwrap behavior

## Scope and Status

- The ground truth is the current bootstrap implementation in `compiler/stage1_l0/` plus the shared L1 stdlib/runtime.
- `compiler/stage2_l1/` is not implemented yet, so this document describes only current bootstrap behavior.
- If runtime or codegen behavior differs from this document, treat that as a bug.

## 1. Ownership Model at a Glance

L1 currently uses three cooperating lifetime systems:

1. `new` / `drop` for heap-allocated objects
2. ARC for `string`
3. container-level ownership rules inside stdlib collections

These systems are separate:

- `_rt_drop` frees memory allocated by `new`
- `rt_string_release` frees a string payload when its refcount reaches zero
- dropping an object does not recursively free unrelated child pointers for you

## 2. Normative Rules Matrix

| Operation                                                                   | Ownership result                      | What you need to do                                                                                            |
| --------------------------------------------------------------------------- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `let p = new T(...)`                                                        | Caller owns the heap object           | Call `drop p` exactly once unless you transfer ownership deliberately.                                         |
| Normal L1 assignment of a `string` (`dst = s`, `*dest = val`, field assign) | Destination takes a managed reference | The compiler emits retain/release automatically. Do not add manual retain/release around ordinary assignments. |
| Removing or clearing string entries from raw storage                        | Container owns stored strings         | Release owned strings before zeroing or removing the storage.                                                  |
| Byte-copy move (`rt_memcpy`) of string-bearing data                         | Ownership moves with the bytes        | Do not release the moved-from slot again.                                                                      |
| `string` returned by value from a container helper                          | Caller receives a managed value       | Follow normal ARC lifetime unless crossing a raw-memory boundary.                                              |
| `return local_var` where `local_var` is owned                               | Ownership moves to caller             | Backend may skip final cleanup for that binding.                                                               |
| `return expr` for a non-local/non-owned value                               | Caller receives a managed reference   | Backend retains the result before scope cleanup.                                                               |

## 3. `new` / `drop` Semantics

Current lowering policy:

- `new` lowers to runtime allocation helpers
- `drop` lowers to runtime deallocation helpers
- `new Struct` and `new Struct()` allocate one zero-initialized object
- `new Struct(args...)` allocates and initializes fields positionally
- `new Variant(args...)` allocates the owning enum object for that active variant
- `new T[N]` and `new T[N]()` allocate one zero-initialized array wrapper
- `new T[N]([ ... ])` and `new T[N](value)` use the same array literal and fill construction rules as stack array
  values; the fill value has element type `T`, which may itself be an array
- `drop` accepts both `T*` and `T*?`
- dropping `null` is a safe no-op

Before calling the final drop helper, compiler-generated cleanup may release owned fields such as `string` members.
Pointer children with independent ownership are still your responsibility.

Fixed-size arrays are value types. Copying an array copies the full wrapper value; if the element type transitively
contains ARC-managed data, generated code retains copied elements and releases overwritten or leaving-scope elements.
Array cleanup runs elements in reverse index order, recursively applying the same rules to nested arrays, structs,
enums, nullable non-pointers, and `string`.

Slices (`T[]`) are non-owning views and carry no ownership. A slice descriptor is `{ dea_int len; T *data; }`, copied by
value with no retain, release, or cleanup for the descriptor itself; the underlying fixed array remains the sole owner
of the storage. Because slices never own their elements, they are restricted to locals, parameters, and call arguments
and may not be returned or stored in long-lived locations (see [design-decisions]). Passing, assigning, or copying a
slice emits only the descriptor copy. If the compiler materializes a fixed-array rvalue to back a slice, that backing
temporary is still an owned array and is cleaned up by the normal array rules when its element type transitively
contains ARC-managed data.

An ordinary variadic call owns a compiler-materialized fixed array containing copies of its trailing arguments. That
array follows the same recursive retain and cleanup rules as any other `T[N]` value and remains alive through the call;
the callee receives only its `T[]` descriptor. Mutating the callee pack therefore does not mutate the original argument
places. A spread call `f(pack...)` forwards existing slice backing storage without copying, so mutations retain normal
slice aliasing behavior.

## 4. ARC `string` Semantics

Every runtime `string` value is reference-counted.

In normal code:

- ordinary assignments are ARC-balanced by the compiler
- local scope cleanup releases initialized owned values
- explicit retain/release calls are reserved for raw-memory boundaries and low-level container internals

## 4.1 ARC assignment replacement semantics

Ordinary assignment to an ARC-managed destination is a slot replacement operation.

That rule applies to:

- local `string` variables
- struct or enum string fields
- dereferenced pointer destinations
- raw-pointer indexed destinations such as `ptr[i]` inside `unsafe func`
- fixed-size array element destinations such as `arr[i]`
- other ordinary assignment destinations whose type is `string`

The intended behavior is:

1. evaluate the right-hand side completely
2. materialize and stabilize any temporary ARC values needed by that expression
3. release the old value currently stored in the destination slot exactly once
4. move the stabilized result into the destination slot without requiring a clone-like copy
5. release temporary ARC values after their last use

This means self-referential ARC assignments are valid ordinary code. For example:

```dea
name = name + "." + suffix;
```

must behave as though the old `name` value remains live while the right-hand side is evaluated, then the destination
slot is replaced exactly once by the newly computed string.

Likewise, replacing one owned string value with another is valid ordinary code:

```dea
let s = "";
s = build_name();
```

and:

```dea
let exe_path = default_exe_path();
if (opts.output != null) {
    exe_path = opts.output as string;
}
```

These forms must work without manual retain/release and without restoring clone-like helper functions. If generated code
or runtime behavior differs from this contract, treat it as a compiler bug.

Raw-pointer writes inherit that same slot-replacement rule even though the access itself is unchecked. In other words,
`ptr[i] = value` inside an `unsafe func` does not add bounds checks or provenance checks, but once the destination slot
is identified it must retain the incoming ARC-managed value before releasing the overwritten contents of that slot.

## 5. Optional Unwrap

When you unwrap `string?` with `opt as string`, the resulting `string` is ownership-stabilized by the backend.

In ordinary L1 code, you should not need to add a compensating manual retain after `opt as string`.

## 6. Container Ownership Contracts

### `std.vector` / `StringVector`

- `sv_push` uses assignment semantics
- `sv_clear` and `sv_free` release stored strings before clearing/freeing storage
- the generic `vec_*` layer is not ARC-aware by itself

### `std.hashmap`

- map keys are ARC strings owned by the map
- insert/update retains new keys and releases replaced keys
- remove/clear/free release all occupied keys
- `spm_keys` and `sim_keys` return caller-owned `StringVector*`

### `std.hashset`

- set keys are ARC strings owned by the set
- add/remove/clear/free follow the same retain/release discipline as map keys
- `ss_to_vector` returns caller-owned `StringVector*`

### `std.linear_map`

- `LinearMapBase` is byte-oriented and does not provide deep ownership on its own
- ARC-aware specializations release owned strings on remove/free paths

## 7. Manual `rt_string_retain` / `rt_string_release`

Manual retain/release is required when you:

1. manipulate string-bearing storage through raw memory operations
2. implement remove/clear/free loops for owned string slots
3. cross an ownership boundary outside ordinary assignment semantics

It is usually wrong when you:

1. perform ordinary assignment on ARC-managed fields or locals
2. use stdlib helpers that already own the ARC transitions for you

## 8. Control Flow and Cleanup

Current compiler behavior:

- scope cleanup runs in reverse declaration order
- `continue` cleans only the current iteration body scope before control returns to the loop update/condition path
- `return`, `break`, and `expr?` early exits run pending `with` cleanup before ordinary owned-value cleanup
- direct return of an owned local may be treated as a move

## 9. Validation and Bug Reporting

For ownership issues, provide:

1. a minimal `.l1` reproducer
2. the generated C excerpt showing retain/release/drop order
3. trace logs when applicable

Useful local checks:

```bash
make use-dev-stage1
source build/dea/bin/l1-env.sh
l1c --gen examples/hello.l1
python compiler/stage1_l0/scripts/run_trace_tests.py
```

## 10. Ground-Truth References

Primary implementation references:

- `compiler/stage1_l0/src/backend.l0`
- `compiler/stage1_l0/src/c_emitter.l0`
- `compiler/stage1_l0/src/expr_types.l0`
- `compiler/stage1_l0/src/lexer.l0`
- `compiler/stage1_l0/src/parser.l0`
- `compiler/shared/l1/stdlib/std/vector.l1`
- `compiler/shared/l1/stdlib/std/hashmap.l1`
- `compiler/shared/l1/stdlib/std/hashset.l1`
- `compiler/shared/l1/stdlib/std/linear_map.l1`
- `compiler/shared/runtime/include/dea_rt.h`

[design-decisions]: design-decisions.md
