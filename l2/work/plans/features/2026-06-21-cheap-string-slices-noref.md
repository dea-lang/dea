# Feature Plan

## Add cheap string slices

- Date: 2026-06-21
- Last reviewed: 2026-10-27
- Status: Draft
- Title: Add ARC-backed cheap string slices
- Kind: Feature
- Priority: Low
- Subsystem: Intrinsics / backend / ARC runtime / string stdlib
- Modules:
  - `l2/compiler/src/expr_types/expr.l1`
  - `l2/compiler/src/backend/lower.l1`
  - `l2/compiler/src/c_emitter/`
  - `l2/compiler/shared/runtime/include/dea_rt.h`
  - `l2/compiler/shared/runtime/src/dea_rt_string.c`
  - `l2/compiler/shared/runtime/src/dea_rt_io.c`
  - `l2/compiler/shared/runtime/src/dea_rt_sys.c`
  - `l2/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l2/compiler/shared/runtime/dea_rt.symbols`
  - `l2/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l2/compiler/shared/l2/stdlib/sys/rt.l2`
  - `l2/compiler/shared/l2/stdlib/std/vector.l2`
  - `l2/compiler/shared/l2/stdlib/std/text.l2`
  - `l2/compiler/shared/l2/stdlib/std/string.l2`
- Test modules:
  - `l2/compiler/tests/expr_types_test.l1`
  - `l2/compiler/tests/backend_test.l1`
  - `l2/compiler/tests/c_emitter_test.l1`
  - `l2/compiler/tests/l2c_lib_test.l1`
  - `l2/compiler/tests/l2c_arc_trace_regression_test.py`
  - `l2/compiler/tests/fixtures/driver/`
  - `l2/compiler/tests/runtime_pointer_validation_test.py`
  - `l2/compiler/tests/io_runtime_test.py`
- Related:
  - [l2/work/plans/features/2026-10-27-stable-l1-catch-up-noref.md][catch-up]
  - [l2/docs/roadmap.md][roadmap]
  - [docs/decisions/0010-checked-runtime-pointer-access-validation.md][pointer-validation]
- Repro: `make -C l2 test-compiler TESTS="expr_types_test backend_test c_emitter_test"`

## Summary

This optional optimization is deferred to L2 and does not gate L1 stability. Activate it only after the
[l2/work/plans/features/2026-10-27-stable-l1-catch-up-noref.md][catch-up] and the start of sustained L2 work. Low
priority reflects that deferral. Recheck this retained design against the adopted baseline before implementation; its
current readiness is `not-ready`.

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

1. L2 currently inherits the copying string runtime and array/slice intrinsics. Re-inventory the adopted stable-L1
   baseline after catch-up; the detailed contracts below describe the intended target behavior.
2. L2 compiler production code is implemented in `.l1` and runs against the selected L1 bootstrap runtime. Its
   implementation tests do not establish the string ABI of generated `.l2` programs.
3. The target runtime and `.l2` stdlib are L2-owned. Target-runtime native calls must accept interior views, and every
   target-library raw-byte consumer must migrate before removing its raw string-pointer export.
4. Preserve `len(string)` and the existing array/slice overloads. Add actual `.l2` fixtures and native probes for the
   target representation, ownership, source snapshots, and pointer boundary.

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
13. Remove the target raw string-byte pointer operation from the L2 runtime surface after migrating all target-library
    consumers to bounded copying. Keep the stable L1 bootstrap ABI and its existing compiler-private bridges unchanged.

## Level Ownership and Bootstrap

This plan changes L2-generated programs, L2 target libraries, and the L2-owned runtime. The `.l1` compiler's filesystem,
process, and fingerprint bridges continue to consume stable L1 strings and remain outside this migration. Removing
`rt_string_bytes_ptr` from L2 target exports does not require removing the predecessor's export or rebuilding L0/L1.

Repeat the target-runtime consumer inventory after catch-up, including any newly adopted file, process, or networking
helpers. A later self-hosting or bootstrap-bridge optimization requires separate scope; compiler byte batches are not a
prerequisite for this feature.

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

The L2 `sys.rt` declaration is unsafe because destination capacity cannot be checked by the helper:

```dea
unsafe extern func rt_string_copy_bytes(s: string, start: int, destination: byte*?, count: int) -> void;
```

Use `byte*?` so a zero-count null destination is expressible from Dea; the C pointer ABI is unchanged.

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
6. Update literal-emission fixtures and require clean rebuilding of all L2 target artifacts.

### Phase 2: Read-only access and bounded copying

1. Replace general `_rt_string_bytes` use with `_rt_string_data` for C-internal borrowed logical bytes.
2. Have concatenation, byte conversion, file reads, and line reads write directly to freshly allocated, unpublished
   backing storage.
3. Add `rt_string_copy_bytes` with the source-range and destination contracts defined above, including the target public
   header, normal/traced symbol manifests, and `sys.rt` declaration.
4. Add a specialized byte-vector operation that reserves once, computes the destination, calls `rt_string_copy_bytes`,
   and updates the vector length only after copying succeeds.
5. Migrate `cb_append_s` and `cb_append_slice` to the specialized operation. Preserve the existing early return for a
   non-positive slice length; for a positive length, validate the source range before reserving even though the runtime
   helper validates it again.
6. Leave `cb_append`, `cb_to_string`, and the general raw-memory `vec_push_bytes` operation unchanged.
7. Remove `rt_string_bytes_ptr` from L2 target runtime/public headers, symbol manifests, and `sys.rt` only after every
   target-library consumer has moved. Replace direct-export tests with copy-boundary and removed-export checks.
8. Remove lazy string-exposure tracker hooks only where they are now unreachable, preserving generic allocation, ARC,
   quarantine, and foreign read-only tracking coverage. Rebuild the affected target runtime/interfaces and generated
   objects together; preserve the upstream compiler's ABI and exports.

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

Update [l2/docs/reference/grammar.md][grammar], [l2/docs/reference/design-decisions.md][design decisions],
[l2/docs/reference/ownership.md][ownership], [l2/docs/reference/c-backend-design.md][backend design],
[l2/docs/reference/standard-library.md][standard library], [l2/docs/project-status.md][project status],
[l2/docs/specs/compiler/abi.md][abi], and [l2/docs/roadmap.md][roadmap]. Document the string overload, shared-backing
ownership, possible backing retention, internal terminated-copy path, immutable byte-copy boundary, and clean-rebuild
requirement for L2 target artifacts.

Create and index the L2 ADRs when closing this plan. Existing L1 slice and shared pointer-validation decisions remain
the baseline references; L2-only representation and export changes do not rewrite stable L1 behavior.

## Diagnostics

No new diagnostic range is required.

1. Reuse `TYP-0808`, `TYP-0809`, and `TYP-0210`.
2. Document the L2 string overload under the existing `TYP-0808` meaning while retaining L1's current slice operand
   restrictions. Preserve `len(string)` and its logical byte-length result in both levels; no code is reassigned.
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
- Actual `.l2` fixtures replace a borrowed source field from the start operand and from the count operand. The result
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
- A null destination is accepted for a zero count and rejected for a positive count, through actual `.l2` calls and
  native probes.
- `StringBuffer` flattening with many parts performs one bulk copy per non-empty part and produces the expected value.
- Generated Dea code and standard-library sources have no operation that obtains a mutable pointer into string storage.
- Runtime construction writes only to fresh unpublished storage.

### Performance validation

1. Compare optimized before/after builds on the same machine, compiler, compiler flags, and test inputs.
2. Measure large `CharBuffer` appends, many small `CharBuffer` appends, and `sb_to_string` with many small parts.
3. Exercise those workloads as generated L2 programs, including full strings and interior views. The compiler executable
   itself continues using stable L1 strings and is not evidence for the changed target ABI.
4. Warm each workload once, collect at least five measured runs, and compare medians.
5. Inspect or instrument the copy path to verify exactly one direct libc `memcpy` per non-empty string append, with no
   terminated-string materialization.
6. Treat any reproducible wall-time regression greater than 5% as blocking. Investigate smaller regressions when they
   are consistent across workloads.

For the `CharBuffer` append path, one checked copy call replaces separate raw-pointer and `rt_memcpy` calls, and sliced
appends no longer need source-side `rt_array_element`. Its added work is a constant number of source-range checks,
including a deliberate duplicate check for partial appends. Measure the effect against the same performance gate.

### Validation commands

After catch-up, run focused expression/lowering/emitter tests and actual `.l2` string/termination/byte-copy fixtures,
with native runtime/public-header/symbol probes and ARC/memory tracing. Then run L2 `make test-ci` with explicit
`L2_BOOTSTRAP_L1C`, using the selected stable L1 installation. Obtain Linux, macOS Intel/ARM, and Windows UCRT64
evidence. Run opt-in L2 `make test-isolation` with a compatible installed Linux L1 prefix to preserve target ownership.

Implementation `.l1` tests exercise the bootstrap runtime; they cannot substitute for `.l2` target fixtures. No L0/L1
rebuild, root aggregate, or intra-L2 self-bootstrap is required by this target-only feature. This draft reassignment
requires Markdown, link, and ADR Impact checks only.

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
12. The L2 compiler remains buildable with the unchanged stable L1 bootstrap, and generated target programs use only
    L2-owned headers, runtime, and standard-library inputs.

## ADR Impact

- Decision: Represent immutable L2 strings as ARC-backed spans with flattening, allocation-free O(1) owned views.
  - Scope: L2
  - Disposition: New ADR
  - ADR: `l2/docs/decisions/`
  - Rationale: The representation changes target string ownership, native boundaries, generated C layout, and slicing
    costs independently of the stable predecessor runtime.
- Decision: Extend the L2 `dea::slice` intrinsic to return an owned, byte-indexed string.
  - Scope: L2
  - Disposition: New ADR
  - ADR: `l2/docs/decisions/`
  - Rationale: The L2 overload must preserve the inherited array/slice contract while adding owned string results.
- Decision: Replace the L2 target string-byte pointer export with bounded copying and internal termination handling.
  - Scope: L2
  - Disposition: New ADR
  - ADR: `l2/docs/decisions/`
  - Rationale: Published L2 string storage remains immutable without changing stable L1 bootstrap or shared foreign-
    storage validation behavior.

## Non-Goals

1. Public C-interoperability types or syntax.
2. A new string-like surface type or subtype hierarchy.
3. Returning `byte[]` from string slicing.
4. Unicode-aware indexing or slicing.
5. Mutable string views.
6. Compaction, detachment, or retention heuristics.
7. General borrow checking or lifetime inference.
8. Changing L0/L1 string representations, exports, standard libraries, or compiler-private bridges.
9. Packed compiler-byte batches, self-hosting, a public multi-byte-array collection, or a general-purpose arena API.

## Deferred Compiler Bridge Reference

The following packed-batch design is retained for possible future L2 compiler-support optimization. It is outside this
feature's implementation, verification, and closure requirements. Open separate scope before adopting it; the stable L1
bootstrap keeps its existing representation and public exports. The `.l1` wrappers use the predecessor's existing
read-only raw-byte access and bulk copy, independently of the new L2 target copy helper. Recheck actual support names,
consumer inventory, and Windows launch behavior after stable-L1 catch-up.

### Packed allocation and construction

Implement `CompilerByteBatch` as a compiler-private opaque handle. Keep layout calculations, initialization, and native
table access in the existing per-level compiler-support C units, with thin Dea wrappers in `compiler_byte_batch.l1`. The
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
inputs and known-size scratch before allocation; a filling pass copies each input once into its final position using the
stable L1 read-only byte pointer plus its bulk-copy primitive and appends one NUL. Do not create a temporary collection
just to feed the one/two-string constructors. Keep the source values stable across both passes. Check every sum,
product, terminator, and alignment adjustment against both native size limits and `rt_alloc`'s positive `int` size limit
before allocating or computing pointers. Reject an empty process vector before allocation, preserving its current
invalid-vector result.

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

Change `l2c_process_run` to accept the completed opaque batch handle and its existing status output. It obtains the
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
native helpers no longer duplicate them merely to obtain termination. Measure bridge-heavy workloads before adopting
this optional design; the L2 target string-pointer removal and stable L1 bootstrap exports are separate boundaries.

[abi]: ../../../docs/specs/compiler/abi.md
[backend design]: ../../../docs/reference/c-backend-design.md
[catch-up]: 2026-10-27-stable-l1-catch-up-noref.md
[design decisions]: ../../../docs/reference/design-decisions.md
[grammar]: ../../../docs/reference/grammar.md
[ownership]: ../../../docs/reference/ownership.md
[pointer-validation]: ../../../../docs/decisions/0010-checked-runtime-pointer-access-validation.md
[project status]: ../../../docs/project-status.md
[roadmap]: ../../../docs/roadmap.md
[standard library]: ../../../docs/reference/standard-library.md
