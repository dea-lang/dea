# Feature Plan

## Runtime Pointer Access Validation

- Date: 2026-06-30
- Status: Completed
- Title: Checked-by-default L0 runtime pointer access validation
- Kind: Feature
- Severity: High
- Stage: Shared
- Subsystem: Runtime safety, Stage 1 backend, Stage 2 backend
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage1_py/l0_c_emitter.py`
  - `l0/compiler/stage2_l0/src/backend.l0`
  - `l0/compiler/stage2_l0/src/c_emitter.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend`
  - `l0/compiler/stage2_l0/tests`
- Related:
  - `work/plans/features/closed/2026-06-30-shared-runtime-pointer-access-validation-noref.md`
- Repro: `zap(p); p.s` after callee-side `drop p`

## Summary

L0 gets the shared pointer-validation semantics in its header-only runtime and both implemented compiler backends.
Generated C validates pointer accesses at dereference time and validates drops before generated cleanup reads owned
fields.

## Implementation

- Replace the current address-only `new`/`drop` tracker with pool-allocated allocation records, a base-keyed hash table,
  an address-ordered treap for interior pointers, and a bounded quarantine.
- Track `rt_alloc`, `rt_calloc`, `rt_realloc`, `rt_free`, `_rt_alloc_obj`, and `_rt_drop`. Register heap string blocks
  as ARC-managed records and static string spans lazily through `rt_string_bytes_ptr`; runtime-managed records are not
  droppable, and string records reject checked writes.
- Add the `_rt_check_ptr_site` fast path with per-call-site caches and the `_rt_check_ptr_site_slow` refill path in
  `l0_runtime.h`, preserving trace-memory locations. Derived pointers from runtime helpers are validated against the
  owning allocation range instead of per-call derived records.
- Support the release build split: defining `L0_RT_UNCHECKED` compiles validation and tracking out while generated C
  stays identical.
- Keep trace-memory output lifecycle-oriented: raw allocation/free and `new` events stay as-is, generated `drop` logs at
  `rt_drop_finish`, and successful access checks/derived registration/quarantine eviction remain untraced.
- Lower pointer field access, dereference, pointer indexing, and drop cleanup through checked pointers. Evaluate pointer
  expressions exactly once. Each checked access site declares one static `_rt_ptr_site` cache slot in both Stage 1 and
  Stage 2 emitters with identical output.
- Propagate write mode through compound store targets: when a field store's object is not itself a pointer (explicit
  dereference objects such as `(*q).b` and nested embedded-struct chains such as `q.inner.b`), emit the object as an
  lvalue so the inner pointer access is write-checked instead of falling back to the read-mode rvalue path, and so
  side-effecting non-pointer objects are not materialized into a struct temporary that would absorb the store.
- Treat unchecked host/foreign pointer manipulation as a runtime-helper responsibility. Pointers returned to checked L0
  code must be registered first.

## Completion Notes

Completed on 2026-07-03.

- Implemented checked pointer access lowering and runtime allocation tracking for both L0 backends.
- Added read-only string storage checks, raw allocation tracking, split drop validation, and unchecked runtime
  compile-out support in `l0_runtime.h`.
- Fixed generated source-line fidelity for runtime pointer diagnostics after per-site cache declarations.
- Final validation: `make clean test-all`.

## Verification Criteria

- Focused Stage 1 tests cover null access, use after drop, double drop, derived pointer invalidation, raw allocation
  tracking, and side-effecting access expressions.
- Field stores through explicit dereferences and nested embedded-struct chains on read-only records report
  `read-only pointer write` instead of mutating read-only storage.
- Stage 2 codegen and runtime tests preserve Stage 1 behavior.
- Existing Stage 1, Stage 2, ARC trace, memory trace, and example checks continue to pass.
