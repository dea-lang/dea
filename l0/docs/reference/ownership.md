# L0 Ownership and Memory Management Reference

Version: 2026-06-24

This document describes how ownership works in L0 today, covering:

- **`new` / `drop`**: heap object allocation and deallocation.
- **ARC-managed `string`**: reference-counted string values.
- **Container ownership**: how stdlib containers manage the elements they store.
- **`string?` unwrap**: what happens when you write `opt as string` to extract a value from an optional.

## Scope and Status

- The ground truth is the **current implementation**: Stage 1 backend lowering, Stage 2 backend lowering and driver
  paths for `--gen`, `--build`, and `--run`, and the current stdlib/runtime.
- When Stage 1 and Stage 2 wording diverge, treat Stage 1 as the oracle and Stage 2 parity failures as bugs.
- If runtime or codegen behavior differs from this document, treat it as a bug and report it.

## 1. Ownership Model at a Glance

L0 uses three cooperating lifetime systems:

1. **`new` / `drop`** for heap-allocated objects.
2. **ARC** (automatic reference counting) for `string` values, via `rt_string_retain` / `rt_string_release`.
3. **Container-level ownership** rules that govern elements stored inside stdlib collections.

These systems are deliberately separate:

- `_rt_drop` frees the memory that `new` allocated. It does **not** walk ARC references.
- `rt_string_release` frees a string's payload when its refcount reaches zero. It does **not** free `new`-allocated
  object memory.

## 2. Normative Rules Matrix

| Operation                                                                   | Ownership result                      | What you need to do                                                                                                |
| --------------------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `let p = new T(...)`                                                        | Caller owns the heap object           | Call `drop p` exactly once, unless you explicitly transfer ownership elsewhere.                                    |
| Normal L0 assignment of a `string` (`dst = s`, `*dest = val`, field assign) | Destination takes a managed reference | The compiler emits retain/release automatically. Do **not** add manual retain/release around ordinary assignments. |
| Removing or clearing string entries from raw storage                        | Container owns stored strings         | Call `rt_string_release` on each owned string **before** zeroing or removing the storage.                          |
| Byte-copy move (`rt_memcpy`) of string-bearing data                         | Ownership moves with the bytes        | Do **not** release the moved-from slot again; the destination is now the sole owner.                               |
| Bulk zero (`rt_memset`, `arr_zap`) on string-bearing storage                | Zeroing bypasses ARC                  | Release owned strings **first**, then zero.                                                                        |
| `string` returned by value from a container helper                          | Caller receives a managed value       | Follow normal ARC lifetime. Avoid compensating manual releases unless you are crossing a raw-memory boundary.      |
| `return local_var` (where `local_var` is owned)                             | Ownership moves to caller             | The compiler skips local cleanup for the returned variable (move optimization).                                    |
| `return expr` (non-local or non-owned)                                      | Caller receives a managed reference   | The compiler retains the result before scope cleanup runs.                                                         |

## 3. `new` / `drop` Semantics

How it lowers at runtime:

- `new` lowers to `_rt_alloc_obj(bytes)`.
- `drop` lowers to `_rt_drop(ptr)`.
- `new Struct` and `new Struct()` allocate one heap object and zero-initialize it.
- `new Struct(args...)` allocates one heap object and initializes fields positionally; when arguments are present, the
  constructor requires full struct-field arity.
- `new Variant(args...)` allocates the owning enum object initialized to that specific variant.
- The `drop` statement accepts both standard pointers (`T*`) and nullable pointers (`T*?`).
- `_rt_drop(NULL)` is a safe no-op (e.g. `drop p` where `p` is `null` does nothing).
- Dropping a pointer that was not allocated by `new` triggers a runtime panic.

Before calling `_rt_drop`, the compiler may emit field cleanup automatically:

- If the struct/enum has ARC fields (e.g. `string` members), the current backends insert `rt_string_release` calls for
  those fields before freeing the object.
- Pointer fields that own **separate** heap objects are **not** cleaned up automatically. You must free or drop children
  explicitly before dropping the parent.

**Rule of thumb:** if your struct owns child pointers, clean them up yourself before `drop`.

## 4. ARC `string` Semantics

Every `string` value is reference-counted:

- `rt_string_retain` increments the refcount (no-op for static/literal strings).
- `rt_string_release` decrements the refcount and frees the payload when it reaches zero (no-op for statics).

In practice:

- Most ordinary L0 code never needs manual retain/release: the compiler balances ARC automatically on assignments and
  copies.
- Manual retain/release is reserved for **low-level container internals** and **raw-memory boundaries** (see section 7).

### ARC assignment replacement semantics

Ordinary assignment to an ARC-managed destination is a slot replacement operation.

That rule applies to:

- local `string` variables
- struct or enum string fields
- dereferenced pointer destinations
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

### Borrowed ARC parameters and reassignment

ARC-typed parameters (`string`, ARC-managed containers) are borrowed at function entry: the caller owns the value and
the callee must not release it. Reassigning such a parameter inside the body is permitted. When the compiler detects any
syntactic assignment to an ARC parameter in the function body, it inserts one defensive retain at the function prologue
and marks the parameter as owned for scope-exit cleanup. Subsequent reassignments then follow normal owned-lvalue
semantics (release the current value, take ownership of the new one), and scope exit performs a single release that
balances the entry retain. For functions that never reassign their ARC parameters, no extra retain/release is emitted
and the parameter stays plain borrowed.

**Cost:** one retain + one release per call, but only for functions whose body syntactically reassigns an ARC parameter.
The common borrowed pattern pays nothing extra.

## 5. Optional Unwrap: `string?` to `string` via `opt as string`

When you have a `string?` (an optional string) and unwrap it with `opt as string`, the result is a plain `string` value.
The key ownership question is: **does the unwrapped value need an extra retain?**

**Short answer:** usually no.

The current backend lowering already handles this correctly. When you write:

```
let s: string = opt as string
```

the unwrapped string is ownership-stabilized: it is **not** tied to the optional's cleanup path, so it will not be
prematurely released when the optional goes out of scope.

The same applies to:

- Returning an unwrapped `string?` from a function.
- Passing an unwrapped `string?` into a container (e.g. `sv_push`).

**When would you need a manual retain?** Only if you are moving the unwrapped value across a **raw, non-assignment
boundary**, for example storing it via `rt_memcpy` into a manually managed buffer. In normal L0 code, you should not
need to add `rt_string_retain` after `opt as string`.

## 6. Container Ownership Contracts

### 6.1 `std.vector` / `StringVector`

- `sv_push` uses assignment semantics: the compiler retains the incoming value and releases any overwritten slot.
- `sv_clear` and `sv_free` release all stored strings before clearing or freeing the underlying storage.
- The generic `vec_*` API is **not** ARC-aware; always use the `sv_*` helpers for string vectors.

**Caller rule:** do not manually release a string after `sv_push`; the container now owns it.

### 6.2 `std.hashmap` (`spm` / `sim`)

- Map **keys** are ARC strings owned by the map.
- Insert/update retains the new key and releases any replaced key.
- Remove/clear/free release all occupied keys.
- Rehash moves keys by byte-copy (`rt_memcpy`); old storage is freed without additional per-key release.
- `spm_keys` / `sim_keys` return a **caller-owned** `StringVector*`; you must call `sv_free` on it.

Value ownership:

- `spm` values are `void*` and caller-managed; the map does **not** drop or free pointees.
- `sim` values are plain `int`.

### 6.3 `std.hashset` (`ss`)

- Set keys are ARC strings owned by the set.
- Add/remove/clear/free follow the same retain/release discipline as hashmap keys.
- Rehash uses byte-copy ownership transfer.
- `ss_to_vector` returns a **caller-owned** `StringVector*`; call `sv_free` when done.

### 6.4 `std.linear_map`

- `LinearMapBase` is byte-oriented and does **not** provide deep-ownership semantics on its own.
- ARC-aware specializations (`sslm`, `islm`) use assignment semantics for string fields and explicit release on
  remove/free paths.
- Swap-removal copies bytes to avoid extra assignment churn, but ownership rules still require explicit release when a
  slot is destroyed.

## 7. Manual `rt_string_{retain,release}`: When It's Required vs. Wrong

**Required** when:

1. You manage string-bearing storage through raw memory ops (`rt_memcpy`, `rt_memset`, slot zaps).
2. You implement container remove/clear/free loops over owned string slots.
3. You cross an explicit ownership boundary outside normal assignment semantics.

**Usually wrong** when:

1. You perform ordinary L0 assignment on ARC-managed fields or slots.
2. You use ARC-aware stdlib helpers that already handle ownership (`sv_*`, `sslm_*`, `islm_*`, map/set key APIs).

## 8. Control Flow and ARC Cleanup

The compiler ensures that ARC-managed locals are only cleaned up if they were actually initialized on the current path.

- **`continue` in loops:** Cleanup only runs for variables declared within the current iteration body. The update step
  and loop condition are evaluated after iteration-scope cleanup.
- **`for` headers:** Initialization and update execute in the surrounding loop context. Header `break` / `continue`
  targets an enclosing loop, while body loop control targets the `for` itself. Condition-false and body-break exits
  release initialization-scope ARC values exactly once.
- **Drop liveness:** A pointer binding is usable only when it is alive on every path reaching the use. Loop analysis
  converges liveness across backedges, and assignment to a bare local revives the binding only after the right-hand side
  checks successfully.
- **Early `return`:** All scopes up to the function top-level are cleaned in reverse order.
- **`with` exit precedence:** Cleanup fallthrough resumes the pending exit. An abrupt cleanup replaces that exit, and
  inline cleanup runs in LIFO order until one statement transfers control.
- **Move optimization:** Returning a local variable (`return x;`) skips its final `release` because ownership is
  transferred to the caller.

## 9. Stage 2 Lexer/Parser Ownership Patterns

Recommended pattern for temporary allocations:

```
with (let x = create() => free(x))
```

On successful ownership transfer into a result node, null out the local owner to prevent double cleanup.

Common examples:

- Temporary vectors in parser helpers.
- Token/vector cleanup helpers that release payload strings.
- AST free helpers that release nested containers before dropping nodes.

## 10. Bug Reporting and Trace Validation

If you observe behavior that contradicts this reference:

1. **Stop and report** immediately.
2. Provide a minimal `.l0` reproducer.
3. Include the generated C excerpt showing the retain/release/drop sequence.
4. Include trace logs and triage output.

Recommended commands:

```bash
./scripts/l0c ... --gen ...
./compiler/stage2_l0/scripts/run_test_trace.py <test-or-reproducer>
./compiler/stage2_l0/scripts/check_trace_log.py <stderr.log> --triage
```

For ownership-related Stage 2 changes, run the full finalization checks:

```bash
./compiler/stage2_l0/scripts/run_trace_tests.py
./compiler/stage2_l0/scripts/run_test_trace.py <test_name>
./compiler/stage2_l0/scripts/check_trace_log.py <stderr.log> --triage
```

Pass criteria:

- Analyzer exit code `0`.
- `leaked_object_ptrs=0`.
- `leaked_string_ptrs=0`.
- No definite trace or runtime errors.

## 11. Ground-Truth References

Primary source files:

- `compiler/stage1_py/l0_backend.py`
- `compiler/stage2_l0/src/backend.l0`
- `compiler/stage2_l0/src/c_emitter.l0`
- `compiler/shared/l0/stdlib/std/vector.l0`
- `compiler/shared/l0/stdlib/std/hashmap.l0`
- `compiler/shared/l0/stdlib/std/hashset.l0`
- `compiler/shared/l0/stdlib/std/linear_map.l0`
- `compiler/shared/l0/stdlib/std/io.l0`
- `compiler/stage2_l0/src/{tokens,lexer,parser,ast,expr_types,scope_context}.l0`
- `compiler/shared/runtime/l0_runtime.h`

Repro-style checks:

```bash
./scripts/l0c -P compiler/stage2_l0/tests -S compiler/shared/l0/stdlib --gen -o /tmp/map_test.c map_test
./scripts/l0c -P compiler/stage2_l0/tests -S compiler/shared/l0/stdlib --gen -o /tmp/hashmap_test.c hashmap_test
```
