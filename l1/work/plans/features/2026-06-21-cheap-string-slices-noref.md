# Feature Plan

## Add cheap string slices

- Date: 2026-06-21
- Last reviewed: 2026-09-08
- Status: Draft
- Title: Add ARC-backed cheap string slices
- Kind: Feature
- Severity: High
- Stage: L1
- Subsystem: Intrinsics / backend / ARC runtime / string stdlib
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l0/compiler/shared/runtime/dea_rt.h`
  - `l0/compiler/shared/l0/stdlib/sys/rt.l0`
  - `l0/compiler/shared/l0/stdlib/std/vector.l0`
  - `l0/compiler/shared/l0/stdlib/std/text.l0`
  - `l0/compiler/stage2_l0/src/compiler_byte_batch.l0` (new private wrapper module)
  - `l0/compiler/stage2_l0/src/compiler_filesystem.l0`
  - `l0/compiler/stage2_l0/support/compiler_filesystem.c`
  - `l1/compiler/stage1_l0/src/compiler_byte_batch.l0` (new private wrapper module)
  - `l1/compiler/stage1_l0/src/compiler_filesystem.l0`
  - `l1/compiler/stage1_l0/src/interface_fingerprint.l0`
  - `l1/compiler/stage1_l0/support/compiler_support.c`
  - `l1/compiler/stage1_l0/support/interface_fingerprint.c`
  - `l1/compiler/stage1_l0/src/expr_types/expr.l0`
  - `l1/compiler/stage1_l0/src/backend/lower.l0`
  - `l1/compiler/stage1_l0/src/c_emitter/`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_string.c`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l1/compiler/shared/runtime/src/dea_rt_sys.c`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l1/compiler/shared/l1/stdlib/sys/rt.l1`
  - `l1/compiler/shared/l1/stdlib/std/vector.l1`
  - `l1/compiler/shared/l1/stdlib/std/text.l1`
  - `l1/compiler/shared/l1/stdlib/std/string.l1`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_runtime_alloc_tracker.py`
  - `l0/compiler/stage1_py/tests/backend/test_runtime_pointer_validation.py`
  - `l0/compiler/stage1_py/tests/backend/test_runtime_public_header.py`
  - `l0/compiler/stage2_l0/tests/util_text_test.l0`
  - `l0/compiler/stage2_l0/tests/compiler_byte_batch_test.l0` (new private wrapper coverage)
  - `l0/compiler/stage2_l0/tests/compiler_filesystem_support_test.py`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/fixtures/driver`
  - `l1/compiler/stage1_l0/tests/util_text_test.l0`
  - `l1/compiler/stage1_l0/tests/compiler_byte_batch_test.l0` (new private wrapper coverage)
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_support_test.py`
  - `l1/compiler/stage1_l0/tests/interface_fingerprint_runtime_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_build_run_multi_cu_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_pointer_validation_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_symbol_manifest_test.py`
  - `l1/compiler/stage1_l0/tests/io_runtime_test.py`
  - `l1/compiler/stage1_l0/tests/fixtures/io_runtime/io_numeric_main.l1`
- Related:
  - `l1/work/plans/features/closed/2026-05-19-stage1-slices-len-slice-intrinsics-noref.md`
  - `l1/docs/decisions/0015-slice-types-and-intrinsics.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - [docs/decisions/0010-checked-runtime-pointer-access-validation.md][pointer-validation]
  - [work/plans/features/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md][self-hosting]
- Repro: `make -C l1 test-stage1 && make -C l1 test-stage1-trace`

## Summary

Extend `dea::slice` to accept `string` and return an ordinary ARC-managed `string` that shares the source backing
allocation. A string becomes an immutable logical span over either static storage or a refcounted heap backing. Slicing
adjusts the logical pointer and length, retaining the heap backing when necessary. The result can be returned, stored,
compared, hashed, concatenated, and passed anywhere a normal string is accepted.

Native runtime code distinguishes logically NUL-terminated values from interior views. Operations requiring termination
obtain an owned terminated string, use it, and release it. This is an internal string-runtime mechanism; the feature
does not add a public C-interoperability type or conversion surface.

Published strings expose no mutable byte pointer to Dea code. Length-aware library code copies directly from an
immutable logical span through a bounded runtime helper. `CharBuffer` and `StringBuffer` preserve their existing bulk
copy behavior: one amortized reserve and one `memcpy` per non-empty string append.

## Current State

01. `dea::slice` accepts fixed arrays and `T[]`, returning a non-owning `T[]` descriptor.
02. `std.string::slice_s` and `rt_string_slice` already return `string`, but always allocate and copy the requested byte
    range.
03. The native `dea_string` representation distinguishes static values from heap values. Heap values obtain their
    logical pointer and length exclusively from the backing header, so they cannot describe an interior span.
04. Every current string is terminated at its logical end. Runtime helpers therefore use `_rt_string_bytes` both for
    length-aware byte access and for native calls that require a trailing NUL.
05. The runtime calls `system`, `getenv`, `stat`, `_stat64`, `fopen`, and `remove` with string byte pointers.
06. Current compiler-private bridges also consume the public raw-byte escape: L0 Stage 2 filesystem helpers, L1 Stage 1
    filesystem/process helpers, and L1 interface fingerprinting. The process helper stores an entire argument-pointer
    vector until the native launch/wait call returns. These consumers must migrate before removing the old helper.
07. L1 Stage 1 production code is still compiled against the L0 stdlib/runtime. Its `.l0` implementation tests do not
    prove the new L1 string representation; generated `.l1` fixtures and native runtime probes must cover that ABI.
08. The compiler source is decomposed into subsystem modules. Intrinsic inference lives in `expr_types/expr.l0`,
    lowering in `backend/lower.l0`, and C representation/literal emission in `c_emitter/`.
09. `len(string)` already exists in L1. Preserve that overload and have it report the logical length of a view; the
    shared diagnostic catalog's array/slice-only wording is stale.
10. `ByteArray` currently allocates a wrapper, an `ArrayBase`, and separate byte storage. Native filesystem helpers copy
    paths again for termination; the native process bridge allocates a terminated copy of each argument plus an argument
    table. A packed compiler buffer must replace those allocations rather than wrap the existing containers.

## Defaults Chosen

01. `slice(s)`, `slice(s, start)`, and `slice(s, start, count)` accept `string` and return `string`.
02. The third argument is a count, matching existing array and `T[]` slicing.
03. String offsets and lengths remain byte-based. Unicode scalar and grapheme semantics are out of scope.
04. `std.string::slice_s(s, start, end)` keeps its existing start/end signature and returns the same shared view
    representation.
05. A view is a normal owned string value, not a borrow, `byte[]`, or a new surface type.
06. View construction is O(1), allocation-free, and flattening. Slicing a view adjusts its logical pointer instead of
    building a chain.
07. Empty results use the canonical empty string and retain no backing.
08. A small view may retain a large backing allocation. This feature adds no compaction policy or copy heuristic.
09. Backing storage remains NUL-terminated, but an interior logical view need not be terminated at its logical end.
10. Runtime helpers explicitly request an owned terminated string when calling native APIs that require one.
11. The LBI `string` sigil remains `c`. The generated C layout changes incompatibly, so compiler, runtime, stdlib, and
    generated objects must be rebuilt together.
12. Runtime construction may write newly allocated private backing before publication, but no general mutable string
    accessor exists.
13. The existing raw string-byte pointer operation is removed from both L0 and L1 runtime surfaces. Library code uses a
    bounded copy helper instead.
14. Compiler bridges use a private `CompilerByteBatch`: one tracked allocation for terminated input copies, metadata,
    pointer/length tables, and known-size scratch. Native helpers borrow the completed batch for the synchronous call.
15. Filesystem bridges retain pointer-and-length parameters with a stronger termination precondition; the process bridge
    changes to an opaque batch handle. These private contract changes introduce no public collection, C-string type,
    string-pointer escape, or cast into string layout.

## Compiler Bridge Migration

The following is the production consumer inventory reviewed on 2026-09-08. Repeat a repository search for
`rt_string_bytes_ptr` at implementation time and include any newly added callers, including an L1 Stage 2 copy if the
self-hosting plan has landed. This plan does not depend on Stage 2 existing.

| Consumer                                                                                  | Required migration                                                                                                                                                                                |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `l0/compiler/shared/l0/stdlib/std/text.l0` and `l1/compiler/shared/l1/stdlib/std/text.l1` | Preserve the specialized reserve-once, copy-once vector append described below; append directly into the destination buffer.                                                                      |
| `l0/compiler/stage2_l0/src/compiler_filesystem.l0`                                        | Pack one path or both join operands into one scoped `CompilerByteBatch`, including join-output scratch. Reuse that batch across size-query/fill and bounded retry sequences.                      |
| `l1/compiler/stage1_l0/src/compiler_filesystem.l0`                                        | Pack path/name inputs for classification, identity, mutations, canonicalization, temporary paths, and command search. Include join-output scratch and batch the complete process argument vector. |
| `l1/compiler/stage1_l0/src/interface_fingerprint.l0`                                      | Pack the canonical serialization once and reserve 22 scratch bytes for the tagged digest. Keep the native hash input count, algorithm, canonical bytes, and known-answer digests unchanged.       |

### Packed allocation and construction

Implement `CompilerByteBatch` as a compiler-private opaque handle. Keep layout calculations, initialization, and native
table access in the existing per-level compiler-support C units, with thin Dea wrappers in `compiler_byte_batch.l0`. The
C helpers receive byte counts and raw storage, never Dea string values or their representation. Add no batch type or
batch helper to the public stdlib or runtime symbol manifests.

One `rt_alloc` block holds the entire batch, including its bookkeeping:

```text
[header | aligned char* table + NULL sentinel | logical lengths | bytes + NUL per entry | scratch]
```

The C implementation owns the layout and constructs the native pointer table using C pointer types. Compute padding from
the host ABI rather than assuming pointer widths or alignment in Dea. The Dea wrapper owns the allocation and balances
it with one `rt_free`; do not allocate a separate handle with `new`, a `ByteArray`, or pointer/length vectors. This
keeps the block visible to the existing checked-pointer and memory-trace machinery.

Provide constructors for one string, two strings, and an existing process argument vector. A sizing pass measures the
inputs and known-size scratch before allocation; a filling pass copies each input once into its final position using
`rt_string_copy_bytes` and appends one NUL. Do not create a temporary collection just to feed the one/two-string
constructors. Keep the source values stable across both passes. Check every sum, product, terminator, and alignment
adjustment against both native size limits and `rt_alloc`'s positive `int` size limit before allocating or computing
pointers. Reject an empty process vector before allocation, preserving its current invalid-vector result.

Logical lengths exclude the appended NUL. An empty entry still owns one readable NUL byte inside the block. Preserve
embedded NULs and all other input bytes for the consumer's existing validation; packing must not trim or truncate them.
Publish a batch only after all entries and its final null pointer are initialized. It never grows or reallocates, and
its entry pointers remain borrowed until the owner releases it. Native consumers may write only the designated scratch
region; they must neither mutate nor free the input entries or tables.

### Borrowing native contracts

Filesystem functions retain their pointer-and-length parameter shapes. Their revised private contract requires `len + 1`
readable bytes with `data[len] == '\0'`. Preserve empty-path/name and embedded-NUL rejection, validate the terminator
within that caller-provided extent, and borrow the resulting native string directly. Remove input-copy allocations and
their corresponding frees from every normal and error path. Migrate Dea declarations, C contracts, and direct ABI
fixtures together; the old arbitrary-byte-span contract is no longer sufficient for these calls.

Both `cfs_join_child` wrappers reserve the checked bound `parent_len + child_len + 1` as scratch in their two-input
batch. The extra byte covers the optional separator; the native join output remains an explicit-length span and needs no
terminator. Keep the existing size-query/fill sequence against the same batch, require a positive queried size within
the scratch capacity, and construct the returned string from the filled span before freeing the batch. Remove the
separate output `ByteArray`. Preserve host-specific separator handling and the existing concatenation fallback on
query/fill failure, releasing the batch before returning the fallback.

Change `l1c_process_run` to accept the completed opaque batch handle and its existing status output. It obtains the
count, logical lengths, and null-terminated native argument table from the batch. Preserve invalid-vector checks,
empty-executable rejection, embedded-NUL rejection, exact argument semantics, and launch/wait/status conventions. Remove
the native argument-copy/free loop. The caller keeps the one batch alive until the synchronous launch/wait function
returns, then releases it on every returning path.

On Windows, the process batch also reserves mutable command-line scratch. For a positive argument count, the checked
bound `2 * sum(argument_lengths) + 3 * argument_count` includes per-argument quotes, separators, and the final NUL under
the current quoting algorithm. Include this region in the initial allocation, preserve the existing escaping rules, and
write through a capacity-checked cursor without `realloc`. `CreateProcessA` may modify this scratch; input entries
remain unchanged. POSIX execution uses the native argument table directly and needs no command-line scratch.

For fingerprinting, use one input entry and 22 scratch bytes. Write the six-byte `sip13:` prefix, have
`l1c_interface_fingerprint_sip13_hex_bytes` fill the remaining 16 bytes with the existing digest, and construct the
returned string from the complete 22-byte span before freeing the batch. Preserve the fingerprint bridge's existing
pointer/count/output ABI and support-source ownership. No separate `CharBuffer` or intermediate digest string is needed.

### Failure, lifetime, and cost

Unrepresentable sizes fail before allocation. A constructor returns failure after releasing any partially constructed
block; native consumers never receive a partial batch. Filesystem and process callers retain their existing failure
results, while fingerprinting retains its existing fatal allocation-failure convention. Every successfully allocated
batch is released exactly once on each returning path, after the final consumer. Two-path operations and query/fill
retries share one owner for the whole operation.

The one-allocation guarantee covers the batch, its bookkeeping, and its known-size scratch. Dynamically sized OS results
and returned strings retain their own allocations and lifetimes. Compiler inputs are copied once into the batch, and
native helpers no longer duplicate them merely to obtain termination. This does not change allocation-free string-view
construction or direct `CharBuffer` copying. Measure bridge-heavy workloads against the existing performance gate rather
than assuming a speedup; do not restore the string-pointer escape as a performance workaround.

## Native Representation

Replace the tagged static/heap value with a uniform logical span:

```c
typedef struct {
    dea_int refcount;
    dea_int storage_len;
    char bytes[];
} _dea_h_string;

typedef struct {
    _dea_h_string *owner; /* NULL for static storage. */
    const char *bytes;    /* First byte of the logical value. */
    dea_int len;          /* Logical byte length. */
} dea_string;
```

The representation obeys these invariants:

- `len >= 0`.
- `bytes != NULL` when `len > 0`.
- `owner == NULL` identifies static-lifetime storage.
- For heap-backed values, `bytes[0..len]` lies within `owner->bytes[0..storage_len]`.
- Every backing has one readable NUL byte at its storage end.
- ARC retains and releases `owner`, not the logical byte pointer.
- A logical view does not create another ownership node.

The common 64-bit layout remains three machine words after alignment, matching the current tagged union's effective size
on supported 64-bit targets. The field layout is nevertheless an ABI break.

## Internal String Interfaces

Add distinct access and termination helpers:

```c
const char *_rt_string_data(dea_string value);

void rt_string_copy_bytes(
    dea_string value,
    dea_int start,
    dea_byte *destination,
    dea_int count
);

dea_bool _rt_string_is_terminated(dea_string value);
dea_string _rt_string_ensure_terminated(dea_string value);

dea_string _rt_string_view(
    dea_string value,
    dea_int start,
    dea_int count
);
```

`_rt_string_data` is C-internal, returns borrowed logical bytes, and never allocates. For every logical empty value it
returns a non-null pointer to a static NUL byte, even though the canonical descriptor stores `bytes == NULL`. This keeps
an empty C string distinct from a null native argument. Runtime constructors write directly to the backing of the newly
allocated, unpublished result; construction does not pass through a general mutable string accessor.

`rt_string_copy_bytes` is the only string-byte bridge required by Dea library code. It validates
`0 <= start <= value.len` and `0 <= count <= value.len - start` before pointer arithmetic, avoiding addition overflow. A
zero-length copy permits a null destination and performs no memory access. A positive-length copy requires a non-null
destination; sufficient writable destination capacity remains the unsafe caller precondition. The helper resolves views
directly and performs exactly one libc `memcpy`. It does not allocate, retain, release, scan for NUL, materialize a
terminated value, or delegate to `rt_memcpy`.

The L1 `sys.rt` declaration is unsafe because destination capacity cannot be checked by the helper:

```dea
unsafe extern func rt_string_copy_bytes(s: string, start: int, destination: byte*?, count: int) -> void;
```

The L0 seed exposes the corresponding `extern func` under L0's existing unsafe-runtime conventions. Both seeds use
`byte*?` so a zero-count null destination is expressible from Dea; the C pointer ABI is unchanged.

`_rt_string_ensure_terminated` always returns an owned `dea_string`:

- empty input returns the canonical empty value;
- an already terminated static value is returned unchanged, with release remaining a no-op;
- an already terminated heap value is retained and returned;
- a non-terminated view is copied into a standalone heap string.

The caller always balances the result with `rt_string_release`. This avoids a helper whose return pointer is borrowed
for some inputs and allocated for others.

## Goal

1. Make substring construction O(1) while preserving ordinary `string` usability and ARC safety.
2. Extend the existing `slice` intrinsic without changing array/slice behavior.
3. Separate logical byte access from the internal requirement for trailing-NUL storage.
4. Preserve current native-library behavior for strings passed to NUL-dependent runtime operations.
5. Keep trace diagnostics authoritative for every shared backing and materialized terminated copy.

## Implementation Phases

### Phase 1: Uniform string representation

1. Replace the static/heap tagged union with `{ owner, bytes, len }`.
2. Rename the heap header's `len` to `storage_len`.
3. Update initializers:
   - empty: `{ NULL, NULL, 0 }`;
   - literal: `{ NULL, literal, literal_len }`;
   - heap: `{ header, header->bytes, header->storage_len }`.
4. Refactor string allocation, retain, release, length, indexing, equality, ordering, hashing, concatenation, optional
   wrappers, and raw byte conversion around the uniform fields.
5. Preserve ARC trace identity at the heap-header pointer so all views contribute to the same refcount history.
6. Update literal-emission fixtures and require clean rebuilding of all L1 artifacts.

### Phase 2: Read-only access and bounded copying

01. Replace general `_rt_string_bytes` use with `_rt_string_data` for C-internal borrowed logical bytes.
02. Have concatenation, byte conversion, file reads, and line reads write directly to freshly allocated, unpublished
    backing storage.
03. Add `rt_string_copy_bytes` with the source-range and destination contracts defined above.
04. Add the copy helper to the L0 runtime and public header as well as the L1 runtime, normal/traced symbol manifests,
    and both `sys.rt` modules before migrating consumers.
05. Add a specialized byte-vector operation in both standard-library seeds that reserves once, computes the destination,
    calls `rt_string_copy_bytes`, and updates the vector length only after the copy succeeds.
06. Migrate `cb_append_s` and `cb_append_slice` to the specialized operation. Preserve the existing early return for a
    non-positive slice length; for a positive length, validate the source range before reserving even though the runtime
    helper validates it again.
07. Leave `cb_append`, `cb_to_string`, and the general raw-memory `vec_push_bytes` operation unchanged.
08. Implement the private batch wrappers and C layout helpers, including checked sizing, tracked single-block ownership,
    and the selected scratch regions. Add focused wrapper and native layout/allocation tests before migrating consumers.
09. Migrate every compiler bridge consumer to the borrowing contracts above. Update filesystem termination preconditions
    and the process handle ABI together with their C implementations and direct ABI tests. Remove redundant native input
    copies and frees, and preserve fingerprint support-source ownership.
10. Remove `rt_string_bytes_ptr` from both runtime implementations, public headers, L1 symbol manifests, and `sys.rt`
    modules only after every production consumer has moved. Replace tests that call it with copy-boundary and
    removed-export checks. Remove lazy string-exposure tracker hooks only where they are now unreachable, preserving
    generic allocation, ARC, quarantine, and foreign read-only tracking coverage.
11. Rebuild the upstream L0 Stage 2 compiler before rebuilding L1 Stage 1, so no surviving compiler source requires the
    removed L0 helper. A final production-source search must find no declaration, export, call, or replacement mutable
    string-pointer escape.

### Phase 3: Safe reallocation

Make `_rt_realloc_string` copy-on-write:

- reallocate in place only when the value covers the complete backing and the backing refcount is one;
- otherwise allocate replacement storage, copy `min(old_len, new_len)` bytes, release the consumed source reference, and
  return the replacement;
- resizing to zero releases the source and returns canonical empty;
- reallocation never invalidates another string or view.

### Phase 4: View construction

1. Add `_rt_string_view(value, start, count)`.
2. Check `0 <= start <= value.len` and `0 <= count <= value.len - start` before pointer arithmetic.
3. Return canonical empty for zero count.
4. For heap storage, retain `owner` and return `{ owner, bytes + start, count }`.
5. For static storage, return `{ NULL, bytes + start, count }`.
6. Keep `rt_string_slice(s, start, end)` as the existing stdlib wrapper. Preserve checks for `0 <= start <= value.len`
   and `start <= end <= value.len` before computing `count = end - start` and delegating. Invalid extreme endpoints must
   panic without first overflowing the subtraction.

### Phase 5: Intrinsic typing and lowering

1. Extend `slice` inference:
   - fixed array or `T[]` source returns `T[]`;
   - string source returns `string`.
2. Reuse `TYP-0808` for unsupported source types, `TYP-0809` for invalid arity, and `TYP-0210` for non-`int` range
   arguments.
3. Update `TYP-0808` wording to include strings.
4. Lower string slicing through `_rt_string_view` rather than slice-descriptor construction.
5. Evaluate source, start, and count once in source order. Before evaluating either range operand, capture an owned
   snapshot of the source string: retain copied places and borrowed unwraps, adopt already-owned rvalues, and preserve
   static-storage no-op ownership. Later range operands may replace or release the original source without changing the
   captured value or invalidating its backing.
6. Keep that snapshot alive until `_rt_string_view` has acquired its own reference, then balance the snapshot's
   ownership through the normal temporary cleanup. Merely copying a borrowed descriptor or materializing only ARC
   rvalues is insufficient. Do not transfer these owned-string rules to non-owning array/slice descriptors.
7. Treat the returned view as an ordinary owned string result.

### Phase 6: Internal termination handling

1. Implement `_rt_string_is_terminated`:
   - empty is terminated;
   - otherwise inspect the guaranteed-readable `bytes[len]`.
2. Implement `_rt_string_ensure_terminated` with the uniform owned-result contract.
3. Migrate native calls requiring termination:
   - `system`;
   - `getenv`;
   - `stat` / `_stat64`;
   - `fopen`;
   - `remove`.
4. Each operation obtains an owned terminated value, uses `_rt_string_data` during the native call, and releases it on
   every normal and error path.
5. A path value shared by `stat` and `fopen` is materialized once and kept until both calls have consumed it.
6. Rewrite `rt_abort` to print by pointer and length rather than `%s`.
7. Keep hashing, comparison, printing, file contents, and other length-aware operations on the original logical span
   without copying.
8. Preserve current embedded-NUL behavior in this feature; changing native-call truncation semantics is separate design
   work.
9. Pass a non-null empty C string to `system` for every logical empty command, preserving empty-literal execution
   semantics across all representations. Never turn an empty command into `system(NULL)`, which probes shell
   availability. Keep existing empty-path and empty-environment-name rejection before the native call.

### Phase 7: Documentation and integration

Update [grammar], [design decisions], [ownership], [backend design], [standard library], [project status], [ABI], and
[roadmap]. Document the string overload, shared-backing ownership, possible backing retention, internal terminated-copy
path, immutable byte-copy boundary, and clean-rebuild requirement.

Update the affected L0 stdlib and design-decision references for the shared copy boundary. In the same change that
closes the plan, create the next available L1 ADR for the string-span representation, amend the slice ADR, and amend the
shared pointer-validation ADR as specified below. Re-check the ADR number at closure time.

## Diagnostics

No new diagnostic range is required.

1. Reuse `TYP-0808`, `TYP-0809`, and `TYP-0210`.
2. Update the catalog meaning of `TYP-0808` so both `len` and `slice` accept fixed arrays, slices, or strings. Preserve
   the existing `len(string)` overload and its logical byte-length result.
3. Re-check the live catalog at implementation time before changing diagnostic text or assignments.

Packed-buffer size/allocation failures use the existing compiler filesystem/process failure results or fingerprint
allocation-failure convention described above; they introduce no new compiler diagnostic codes.

## Test Plan

### Representation and ARC

- Static, heap, and empty strings preserve existing behavior.
- Copies retain one backing owner.
- Views keep heap backing alive after the original value leaves scope.
- Releasing original and view values in either order is safe.
- Nested views remain flat.
- Full-range views do not allocate a new backing.
- Trace validation reports zero leaked string backings and no double release.

### Copy-on-write reallocation

- Add direct native probes for unique full backings, shared full backings, interior and nested views, static strings,
  and canonical empty input. Include an interior view whose owner refcount is one; uniqueness alone does not permit
  in-place reallocation of a partial backing.
- Exercise growth, shrinkage, unchanged length, and resize to zero. Preserve `min(old_len, new_len)` logical bytes,
  require a trailing NUL at the new end, and leave sibling strings/views unchanged. Newly grown bytes remain private
  construction storage until initialized.
- Check balanced ownership and allocation tracking through normal and traced native probes, including releasing the
  source reference consumed by copy-on-write and returning canonical empty on zero resize. Existing line-read tests
  exercise only unique full backing and cannot substitute for these cases.

### Slice behavior

- All three intrinsic arities work for static and heap strings.
- Prefix, suffix, interior, full, and empty ranges return correct contents.
- Views can be returned, stored in aggregates and containers, compared, hashed, indexed, concatenated, and printed.
- Slicing an ARC rvalue remains valid after source temporary cleanup.
- Actual `.l1` fixtures replace a borrowed source field from the start operand and from the count operand. The result
  uses the original bytes, each operand runs once in source order, and traces show the captured owner remains alive
  until the view owns it. Cover borrowed unwraps as well as places and owned rvalues.
- Negative and out-of-range operands panic before pointer arithmetic.
- The start/end wrapper rejects extreme integer endpoints, reversed ranges, and out-of-bounds ranges before subtraction;
  valid empty ranges at both ends remain allocation-free.
- `len(string)` returns the logical length of full strings, interior/nested views, and canonical empty results,
  including rvalues whose cleanup must remain balanced.
- Existing array and `T[]` intrinsic behavior remains unchanged.

### Termination handling

- Full literals and full heap strings reuse their storage.
- Suffix views ending at an existing NUL reuse their storage.
- Non-terminated views produce an owned copy.
- Every temporary terminated value is released on success and error paths.
- Interior-view paths work for read, write, metadata, and delete operations.
- Interior-view environment names and command strings reach native calls with the expected logical contents.
- Literal, native-constructed heap, canonical, and zero-length sliced empty commands all pass a non-null `""` to the
  command adapter. Verify empty-command execution separately from a shell-availability probe, and retain empty-path/name
  rejection tests without invoking those native operations.
- Length-aware operations never create terminated copies.

### Immutable byte copying and buffers

- Full static strings, full heap strings, and interior views copy the requested bytes without materialization.
- Full and partial `CharBuffer` appends retain one reserve plus one bulk copy.
- Empty and negative `CharBuffer` slice lengths preserve the existing no-op behavior. For a positive length, invalid
  source ranges panic before pointer arithmetic or destination reservation.
- A null destination is accepted for a zero count and rejected for a positive count, through actual `.l1` calls and
  corresponding L0 seed coverage as well as native probes.
- `StringBuffer` flattening with many parts performs one bulk copy per non-empty part and produces the expected value.
- Generated Dea code and standard-library sources have no operation that obtains a mutable pointer into string storage.
- Runtime construction writes only to fresh unpublished storage.

### Performance validation

1. Compare optimized before/after builds on the same machine, compiler, compiler flags, and test inputs.
2. Measure large `CharBuffer` appends, many small `CharBuffer` appends, and `sb_to_string` with many small parts.
3. Measure the existing L0 Stage 2 triple-bootstrap workload because compiler emission is a real `CharBuffer` hot path.
   Also measure L1 interface fingerprinting and graph-heavy build/run commands, including large argument vectors, to
   expose packed-buffer sizing, copying, and tracking costs. L1 Stage 2 is not a prerequisite; add its fixed-point
   workload only if that stage exists at implementation time.
4. Warm each workload once, collect at least five measured runs, and compare medians.
5. Inspect or instrument the copy path to verify exactly one direct libc `memcpy` per non-empty string append, with no
   terminated-string materialization. Separately verify one owning allocation per compiler batch, one copy of each input
   into the batch, and no duplicate native termination-copy allocation or batch reallocation, including Windows
   command-line construction.
6. Treat any reproducible wall-time regression greater than 5% as blocking. Investigate smaller regressions when they
   are consistent across workloads.

For the `CharBuffer` append path, the expected effect is neutral or slightly positive for separately compiled L1 runtime
code: one checked copy call replaces separate raw-pointer and `rt_memcpy` calls, and sliced appends no longer need
source-side `rt_array_element`. Its expected added work is a constant number of source-range checks, including a
deliberate duplicate check for partial appends. Compiler batches replace native termination copies and per-argument
allocations with one tracked allocation, while adding sizing and bookkeeping work. Their measured behavior remains
subject to the same workload performance gate.

### Validation commands

The implementation is cross-level and trace-sensitive even though cheap string views remain L1-only. Run focused L0
runtime/public-header and both levels' batch-wrapper/compiler-filesystem tests, L1 fingerprint known-answer and
generated-code tests, and the string/bridge probes below. Then run root `make test-all` from a clean artifact baseline,
reusing equivalent just-completed level validation where permitted. Run L1's explicit slow trace cases required by the
changed fixtures; the default aggregate does not include those cases. Verify L0 triple-bootstrap and L1 examples through
these gates.

This Draft-plan refresh requires only Markdown, link, ADR Impact, and staged pre-commit validation.

### Compiler bridge regression coverage

- Test C layout alignment, table bounds, null argument-table sentinel, logical lengths, per-entry terminators, and
  scratch separation on supported hosts. Run strict-C99 native probes plus both Dea wrapper suites; keep size-boundary
  checks independent of huge allocations.
- Cover empty process vectors, empty entries, binary bytes, one/two-string constructors, and large vectors. Inject size
  overflow, allocation failure, and partial-construction failure. Assert one tracked owner allocation, no separate
  wrapper or entry allocations, no reallocation, and exactly one release on every returning path after successful
  allocation.
- Test empty and embedded-NUL path/name inputs against the existing rejection behavior and interior L1 views against
  their logical bytes, including two-path operations and size-query/fill retries. Update direct C fixtures to provide
  the required readable terminator; reject a non-NUL terminator within a valid `len + 1` span without an out-of-bounds
  read.
- Instrument native calls to verify that they borrow batch input addresses, never allocate duplicate input/termination
  copies or free input entries, and keep the same owner across query/fill retries. Constructing joined-path results or
  quoted command-line output may copy bytes into their designated destinations. Check that all entries and sibling
  source strings remain unchanged.
- For both join wrappers, verify one tracked temporary allocation includes both inputs and the checked output bound,
  with no separate output `ByteArray`. Cover existing trailing-separator behavior on POSIX and Windows, query/fill
  failures and fallback cleanup, and joined results that remain valid after the batch is released.
- Verify direct execution preserves empty arguments, spaces, quotes, non-ASCII bytes, argument ordering, and normalized
  exit status. On Windows, exercise quotes, runs of backslashes, trailing backslashes, empty arguments, and command-line
  capacity boundaries; require bounded scratch writes and no growing command-line allocation. Trace native launch/wait
  failures for batch leaks and stale pointers, retaining the owner until the call returns.
- Preserve fingerprint digests for empty, ordinary, and binary canonical serializations, including interior-view input
  when tested through L1. Verify the 22-byte tagged result survives batch cleanup and scratch does not overlap input.
  Keep support-object and runtime-archive symbol ownership checks; private batch helpers stay out of runtime exports.
- Preserve raw-memory/foreign read-only protection tests while replacing tests whose only entrypoint was the removed
  string escape. Verify the old public symbol is absent and copying never changes the source string or a sibling view.
- Compile actual `.l1` fixtures through L1 Stage 1 for the new representation; `.l0` harness coverage alone tests the L0
  seed. Rebuild all affected compiler, runtime, stdlib, and generated native artifacts together.

## Verification Criteria

01. String `slice` returns an ordinary ARC-managed `string` for arities one through three.
02. String views allocate no new backing and preserve source-byte order and bounds checks.
03. Nested views retain only the original heap backing and do not form ownership chains.
04. All string operations accept views without semantic differences other than backing retention.
05. NUL-dependent native runtime calls work with both complete strings and interior views.
06. Generated C evaluates every slicing operand exactly once in source order and retains the captured source across side
    effects in later operands.
07. ARC and memory traces report no leaks, double releases, or invalid accesses.
08. All supported-platform tests pass after a clean build.
09. No published runtime or Dea standard-library API exposes mutable string storage.
10. Every non-empty `CharBuffer` string append performs one reserve decision and one direct bulk copy without NUL work.
11. Performance validation shows no reproducible regression greater than 5%.
12. L0 Stage 2 filesystem helpers and L1 filesystem/process/fingerprint helpers use one scoped, tracked batch per native
    operation, including metadata and known-size scratch, with stable borrowed inputs and no duplicate termination copy.
13. The revised private filesystem/process contracts preserve logical byte semantics, validation, and observable
    results; the fingerprint ABI and tagged digests remain unchanged. Every batch is released once after its final
    consumer.

## ADR Impact

- Decision: Represent immutable strings as ARC-backed spans with flattening, allocation-free O(1) owned views.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The representation changes string ownership, runtime/native boundaries, generated C layout, and the cost
    model of slicing.
- Decision: Extend `dea::slice` to accept `string` and return an owned, byte-indexed `string`.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0015-slice-types-and-intrinsics.md`
  - Rationale: ADR-0015 defines slice typing and indexing semantics and must incorporate the string overload.
- Decision: Replace the L0/L1 public string-byte escape with bounded copying into scoped compiler-owned batches borrowed
  by native bridges.
  - Scope: Shared
  - Disposition: Amend ADR
  - ADR: `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
  - Rationale: ADR-0010 currently specifies lazy read-only registration through `rt_string_bytes_ptr`; removal of that
    entrypoint must update the shared pointer boundary without weakening allocation or foreign-storage checks. Packed
    bridge inputs use the existing tracked raw allocator and a single owner through synchronous native consumption;
    native helpers borrow terminated copies without exposing or modifying string backing.

## Non-Goals

1. Public C-interoperability types or syntax.
2. A new string-like surface type or subtype hierarchy.
3. Returning `byte[]` from string slicing.
4. Unicode-aware indexing or slicing.
5. Mutable string views.
6. Compaction, detachment, or retention heuristics.
7. General borrow checking or lifetime inference.
8. Backporting cheap string views or the string-slice intrinsic overload to L0. Removing the mutable raw-byte escape and
   migrating compiler bridges while preserving `CharBuffer` bulk-copy behavior are shared L0/L1 work required by this
   plan.
9. A public `MultiByteArray` collection, a general-purpose arena API, or a growing/reusable compiler batch. This plan
   selects a private batch sized for one operation.

[abi]: ../../../docs/specs/compiler/abi.md
[backend design]: ../../../docs/reference/c-backend-design.md
[design decisions]: ../../../docs/reference/design-decisions.md
[grammar]: ../../../docs/reference/grammar.md
[ownership]: ../../../docs/reference/ownership.md
[pointer-validation]: ../../../../docs/decisions/0010-checked-runtime-pointer-access-validation.md
[project status]: ../../../docs/project-status.md
[roadmap]: ../../../docs/roadmap.md
[self-hosting]: ../../../../work/plans/features/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md
[standard library]: ../../../docs/reference/standard-library.md
