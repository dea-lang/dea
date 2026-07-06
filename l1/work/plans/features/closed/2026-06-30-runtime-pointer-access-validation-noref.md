# Feature Plan

## Runtime Pointer Access Validation

- Date: 2026-06-30
- Status: Completed
- Title: Checked-by-default L1 runtime pointer access validation
- Kind: Feature
- Severity: High
- Stage: 1
- Subsystem: Runtime safety, Stage 1 backend
- Modules:
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
- Test modules:
  - `l1/compiler/stage1_l0/tests`
- Related:
  - `work/plans/features/closed/2026-06-30-shared-runtime-pointer-access-validation-noref.md`
- Repro: `zap(p); p.s` after callee-side `drop p`

## Summary

L1 ports the shared pointer-validation semantics into its archive-based runtime and Stage 1 compiler backend. The L1
implementation must preserve the public runtime-header shape, trace archive behavior, and symbol manifests.

## Implementation

- Extend `dea_rt_alloc.c` allocation tracking to pool-allocated records, a base-keyed hash table, an address-ordered
  treap for interior pointers, split drop begin/finish, access checks, derived-pointer range validation, and bounded
  quarantine. Register heap string blocks as ARC-managed records in `dea_rt_string.c` and static string spans lazily
  through `rt_string_bytes_ptr`; runtime-managed records are not droppable, and string records reject checked writes.
- Keep the `_rt_check_ptr_site` fast path as a `static inline` in `dea_rt.h` with per-call-site caches so checked access
  avoids an archive call on hits; export `_rt_check_ptr_site_slow` and the string tracking helpers, and update
  normal/traced symbol manifests.
- Support the release build split: defining `DEA_RT_UNCHECKED` when building the archive and generated C compiles
  validation and tracking out while generated C stays identical.
- Preserve L1 trace archive behavior by tracing allocation/free and drop lifecycle events only. Do not add trace events
  for successful access checks, derived-pointer registration, or quarantine eviction.
- Lower pointer field access, dereference, and pointer indexing through checked pointers while preserving existing
  fixed-array and slice bounds checks.
- Propagate write mode through compound store targets: when a field store's object is not itself a pointer (explicit
  dereference objects such as `(*q).b` and nested embedded-struct chains such as `q.inner.b`), emit the object as an
  lvalue so the inner pointer access is write-checked instead of falling back to the read-mode rvalue path, and so
  side-effecting non-pointer objects are not materialized into a struct temporary that would absorb the store.
- Keep `type_id` reserved but unenforced; runtime type identity is future work.

## Completion Notes

Completed on 2026-07-03.

- Ported checked pointer access validation to the L1 archive runtime and Stage 1 backend.
- Updated normal and traced runtime symbol manifests for the exported pointer-check and string-tracking helpers.
- Preserved generated source-line fidelity for runtime pointer diagnostics after per-site cache declarations.
- Final validation: `make clean test-all`.

## Verification Criteria

- Focused Stage 1 runtime tests cover the shared invalid-access and drop cases.
- Field stores through explicit dereferences and nested embedded-struct chains on read-only records report
  `read-only pointer write` instead of mutating read-only storage.
- Runtime symbol manifest tests pass for normal and traced archives.
- Existing L1 Stage 1 runtime, trace, and bootstrap tests continue to pass.
