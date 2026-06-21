# Feature Plan

## Add cheap string slices

- Date: 2026-06-21
- Status: Draft
- Title: Add ARC-backed cheap string slices
- Kind: Feature
- Severity: High
- Stage: L1
- Subsystem: Intrinsics / backend / ARC runtime / string stdlib
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l0/compiler/shared/l0/stdlib/sys/rt.l0`
  - `l0/compiler/shared/l0/stdlib/std/vector.l0`
  - `l0/compiler/shared/l0/stdlib/std/text.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_string.c`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l1/compiler/shared/runtime/src/dea_rt_sys.c`
  - `l1/compiler/shared/l1/stdlib/sys/rt.l1`
  - `l1/compiler/shared/l1/stdlib/std/vector.l1`
  - `l1/compiler/shared/l1/stdlib/std/text.l1`
  - `l1/compiler/shared/l1/stdlib/std/string.l1`
- Test modules:
  - `l0/compiler/stage2_l0/tests/util_text_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/fixtures/driver`
  - `l1/compiler/stage1_l0/tests/util_text_test.l0`
- Related:
  - `l1/work/plans/features/closed/2026-05-19-stage1-slices-len-slice-intrinsics-noref.md`
  - `l1/docs/decisions/0015-slice-types-and-intrinsics.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
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

1. `dea::slice` accepts fixed arrays and `T[]`, returning a non-owning `T[]` descriptor.
2. `std.string::slice_s` and `rt_string_slice` already return `string`, but always allocate and copy the requested byte
   range.
3. The native `dea_string` representation distinguishes static values from heap values. Heap values obtain their logical
   pointer and length exclusively from the backing header, so they cannot describe an interior span.
4. Every current string is terminated at its logical end. Runtime helpers therefore use `_rt_string_bytes` both for
   length-aware byte access and for native calls that require a trailing NUL.
5. The runtime calls `system`, `getenv`, `stat`, `_stat64`, `fopen`, and `remove` with string byte pointers.

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

`_rt_string_data` is C-internal, returns borrowed logical bytes, and never allocates. Runtime constructors write
directly to the backing of the newly allocated, unpublished result; construction does not pass through a general mutable
string accessor.

`rt_string_copy_bytes` is the only string-byte bridge required by Dea library code. It validates
`0 <= start <= value.len` and `0 <= count <= value.len - start` before pointer arithmetic, avoiding addition overflow. A
zero-length copy permits a null destination and performs no memory access. A positive-length copy requires a non-null
destination; sufficient writable destination capacity remains the unsafe caller precondition. The helper resolves views
directly and performs exactly one libc `memcpy`. It does not allocate, retain, release, scan for NUL, materialize a
terminated value, or delegate to `rt_memcpy`.

The L1 `sys.rt` declaration is unsafe because destination capacity cannot be checked by the helper:

```dea
unsafe extern func rt_string_copy_bytes(s: string, start: int, destination: byte*, count: int) -> void;
```

The L0 seed exposes the corresponding `extern func` under L0's existing unsafe-runtime conventions.

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

1. Replace general `_rt_string_bytes` use with `_rt_string_data` for C-internal borrowed logical bytes.
2. Have concatenation, byte conversion, file reads, and line reads write directly to freshly allocated, unpublished
   backing storage.
3. Add `rt_string_copy_bytes` with the source-range and destination contracts defined above.
4. Remove `rt_string_bytes_ptr` from the L0 and L1 runtime headers, symbol lists, and `sys.rt` modules.
5. Add a specialized byte-vector operation in both standard-library seeds that reserves once, computes the destination,
   calls `rt_string_copy_bytes`, and updates the vector length only after the copy succeeds.
6. Migrate `cb_append_s` and `cb_append_slice` to the specialized operation. Preserve the existing early return for a
   non-positive slice length; for a positive length, validate the source range before reserving even though the runtime
   helper validates it again.
7. Leave `cb_append`, `cb_to_string`, and the general raw-memory `vec_push_bytes` operation unchanged.

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
6. Keep `rt_string_slice(s, start, end)` as the existing stdlib wrapper and delegate using `count = end - start`.

### Phase 5: Intrinsic typing and lowering

1. Extend `slice` inference:
   - fixed array or `T[]` source returns `T[]`;
   - string source returns `string`.
2. Reuse `TYP-0808` for unsupported source types, `TYP-0809` for invalid arity, and `TYP-0210` for non-`int` range
   arguments.
3. Update `TYP-0808` wording to include strings.
4. Lower string slicing through `_rt_string_view` rather than slice-descriptor construction.
5. Evaluate source, start, and count once in source order.
6. Materialize ARC rvalue sources before calling the helper.
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

### Phase 7: Documentation and integration

Update [grammar], [design decisions], [ownership], [backend design], [standard library], [project status], [ABI], and
[roadmap]. Document the string overload, shared-backing ownership, possible backing retention, internal terminated-copy
path, immutable byte-copy boundary, and clean-rebuild requirement.

After closing the plan, create the next available L1 ADR recording the uniform string-span representation and cheap
slicing. Re-check the ADR number at closure time.

## Diagnostics

No new diagnostic range is required.

1. Reuse `TYP-0808`, `TYP-0809`, and `TYP-0210`.
2. Update the catalog meaning of `TYP-0808` from fixed-array/slice operands to fixed-array/slice/string operands.
3. Re-check the live catalog at implementation time before changing diagnostic text or assignments.

## Test Plan

### Representation and ARC

- Static, heap, and empty strings preserve existing behavior.
- Copies retain one backing owner.
- Views keep heap backing alive after the original value leaves scope.
- Releasing original and view values in either order is safe.
- Nested views remain flat.
- Full-range views do not allocate a new backing.
- Trace validation reports zero leaked string backings and no double release.

### Slice behavior

- All three intrinsic arities work for static and heap strings.
- Prefix, suffix, interior, full, and empty ranges return correct contents.
- Views can be returned, stored in aggregates and containers, compared, hashed, indexed, concatenated, and printed.
- Slicing an ARC rvalue remains valid after source temporary cleanup.
- Negative and out-of-range operands panic before pointer arithmetic.
- Existing array and `T[]` intrinsic behavior remains unchanged.

### Termination handling

- Full literals and full heap strings reuse their storage.
- Suffix views ending at an existing NUL reuse their storage.
- Non-terminated views produce an owned copy.
- Every temporary terminated value is released on success and error paths.
- Interior-view paths work for read, write, metadata, and delete operations.
- Interior-view environment names and command strings reach native calls with the expected logical contents.
- Length-aware operations never create terminated copies.

### Immutable byte copying and buffers

- Full static strings, full heap strings, and interior views copy the requested bytes without materialization.
- Full and partial `CharBuffer` appends retain one reserve plus one bulk copy.
- Empty and negative `CharBuffer` slice lengths preserve the existing no-op behavior. For a positive length, invalid
  source ranges panic before pointer arithmetic or destination reservation.
- A null destination is accepted for a zero count and rejected for a positive count.
- `StringBuffer` flattening with many parts performs one bulk copy per non-empty part and produces the expected value.
- Generated Dea code and standard-library sources have no operation that obtains a mutable pointer into string storage.
- Runtime construction writes only to fresh unpublished storage.

### Performance validation

1. Compare optimized before/after builds on the same machine, compiler, compiler flags, and test inputs.
2. Measure large `CharBuffer` appends, many small `CharBuffer` appends, and `sb_to_string` with many small parts.
3. Measure the existing Stage 2 triple-bootstrap workload because compiler emission is a real `CharBuffer` hot path.
4. Warm each workload once, collect at least five measured runs, and compare medians.
5. Inspect or instrument the copy path to verify exactly one direct libc `memcpy` per non-empty string append, with no
   terminated-string materialization.
6. Treat any reproducible wall-time regression greater than 5% as blocking. Investigate smaller regressions when they
   are consistent across workloads.

The expected effect is neutral or slightly positive for separately compiled L1 runtime code: one checked copy call
replaces separate raw-pointer and `rt_memcpy` calls, and sliced appends no longer need source-side `rt_array_element`.
The only expected added work is a constant number of source-range checks, including a deliberate duplicate check for
partial `CharBuffer` appends.

### Validation commands

1. `make -C l1 test-stage1`
2. `make -C l1 test-stage1-trace`
3. `make -C l1 test-stage1-trace-all`
4. `make -C l1 check-examples`
5. `make -C l1 test-all`

## Verification Criteria

01. String `slice` returns an ordinary ARC-managed `string` for arities one through three.
02. String views allocate no new backing and preserve source-byte order and bounds checks.
03. Nested views retain only the original heap backing and do not form ownership chains.
04. All string operations accept views without semantic differences other than backing retention.
05. NUL-dependent native runtime calls work with both complete strings and interior views.
06. Generated C evaluates every slicing operand exactly once.
07. ARC and memory traces report no leaks, double releases, or invalid accesses.
08. All supported-platform tests pass after a clean build.
09. No published runtime or Dea standard-library API exposes mutable string storage.
10. Every non-empty `CharBuffer` string append performs one reserve decision and one direct bulk copy without NUL work.
11. Performance validation shows no reproducible regression greater than 5%.

## Non-Goals

1. Public C-interoperability types or syntax.
2. A new string-like surface type or subtype hierarchy.
3. Returning `byte[]` from string slicing.
4. Unicode-aware indexing or slicing.
5. Mutable string views.
6. Compaction, detachment, or retention heuristics.
7. General borrow checking or lifetime inference.
8. Backporting cheap string views or the string-slice intrinsic overload to L0. Removing the mutable raw-byte escape and
   preserving `CharBuffer` bulk-copy behavior are shared L0/L1 cleanup required by this plan.

[abi]: ../../../docs/specs/compiler/abi.md
[backend design]: ../../../docs/reference/c-backend-design.md
[design decisions]: ../../../docs/reference/design-decisions.md
[grammar]: ../../../docs/reference/grammar.md
[ownership]: ../../../docs/reference/ownership.md
[project status]: ../../../docs/project-status.md
[roadmap]: ../../../docs/roadmap.md
[standard library]: ../../../docs/reference/standard-library.md
