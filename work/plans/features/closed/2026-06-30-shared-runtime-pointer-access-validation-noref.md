# Feature Plan

## Shared Runtime Pointer Access Validation

- Date: 2026-06-30
- Status: Completed
- Title: Checked-by-default runtime pointer access validation
- Kind: Feature
- Severity: High
- Stage: Shared
- Subsystem: Runtime safety, C backend
- Scope: Shared
- Targets:
  - L0 Stage 1 Python backend and shared header runtime
  - L0 Stage 2 backend and shared header runtime
  - L1 Stage 1 backend and shared runtime archive
- Origin: L0 shared runtime and Stage 1 backend
- Porting rule: Port the shared semantics mechanically, but keep level-specific runtime shape and naming where the level
  runtime already diverges.
- Target status:
  - L0 Stage 1 Python backend and shared header runtime: Done
  - L0 Stage 2 backend and shared header runtime: Done
  - L1 Stage 1 backend and shared runtime archive: Done
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l0/compiler/stage1_py/l0_backend.py`
  - `l0/compiler/stage2_l0/src/backend.l0`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend`
  - `l0/compiler/stage2_l0/tests`
  - `l1/compiler/stage1_l0/tests`
- Related:
  - `l0/work/plans/features/closed/2026-06-30-runtime-pointer-access-validation-noref.md`
  - `l1/work/plans/features/closed/2026-06-30-runtime-pointer-access-validation-noref.md`
- Repro: `zap(p); p.s` after callee-side `drop p`

## Summary

Dea currently prevents many local use-after-drop cases statically, but raw pointer aliases can still survive a
callee-side `drop` and later dereference freed memory. This plan adds runtime validation for generated pointer
dereferences, member access, and pointer indexing so invalid pointer access terminates with a runtime diagnostic instead
of C undefined behavior. Checked builds are the default; a release build split compiles validation out on explicit
opt-out.

## Shared Design

- Extend allocation tracking from address-only sets into records with base, size, alignment, generation, state, memory
  kind, allocation site, drop site, and a reserved type-id field.
- Keep `type_id` stored but unenforced in this work. Runtime type compatibility belongs to a future type-identity
  initiative.
- Track allocations from `new`, `rt_alloc`, `rt_calloc`, and `rt_realloc`; `rt_free` and `drop` validate against the
  tracker before releasing memory.
- Split drop into begin/finish operations so generated cleanup runs only after exact-base validation and before the
  allocation becomes quarantined.
- Add a bounded quarantine for dropped/freed blocks. Detection is guaranteed while the old block remains quarantined;
  pointer tagging or generation-carrying pointer values are out of scope.
- Preserve the existing memory-trace lifecycle surface instead of adding per-access trace spam. `rt_alloc`, `rt_calloc`,
  `rt_realloc`, `rt_free`, and `new` keep their current trace events; generated `drop` emits the existing drop event at
  finish, after cleanup has run. Successful pointer access checks, derived-pointer validation, and quarantine eviction
  do not emit trace lines.
- Lvalue emission propagates write mode through compound store targets: when a field store's object is not itself a
  pointer (explicit dereference objects such as `(*q).b` and nested embedded-struct chains such as `q.inner.b`), the
  object is emitted as an lvalue so the inner pointer access is checked with write mode instead of falling back to the
  read-mode rvalue path. This also keeps side-effecting non-pointer objects from being materialized into a struct
  temporary that would silently absorb the store.

### Tracker Performance Design

- Allocation records are pool-allocated and never returned to the C allocator; recycled records reset their generation
  so stale references are rejected by a generation compare. Record removal is O(1) with no cache scrubbing.
- Base-pointer lookup uses an open-addressing hash table (O(1) amortized). Interior pointers resolve through an
  address-ordered treap keyed by allocation base (O(log n) insert, remove, and lookup with no bulk element moves).
- Every generated checked access site declares one static call-site cache holding the last owning record and its
  generation. A hit validates with one generation compare and one range check, without hashing. The slow path refills
  the site cache after a full tracker lookup.
- Runtime helpers that derive interior pointers (for example `rt_array_element`) validate the derived pointer against
  the owning allocation range instead of registering one derived record per call. Temporal errors on derived pointers
  are still detected through the owning record state while the parent is tracked or quarantined.

### String Storage Registration

- Heap string blocks are registered with the tracker at allocation and unregistered on final ARC release, so
  `rt_string_bytes_ptr` results validate as interior pointers of the owning block.
- Static string spans are registered lazily by `rt_string_bytes_ptr` as static-kind records.
- Heap and static string records are read-only for checked access: reads through `rt_string_bytes_ptr` validate, while
  writes report a runtime error before mutating runtime-managed or static storage.
- ARC-managed and static records are not droppable: `drop`, `rt_free`, and `rt_realloc` on them report a runtime error
  instead of releasing runtime-managed storage.

### Checked And Release Builds

- Checked validation is the default build mode for generated code and runtimes.
- Defining `L0_RT_UNCHECKED` (L0 header runtime) or `DEA_RT_UNCHECKED` (L1 archive runtime and public header) compiles
  pointer access validation, allocation tracking, and quarantine out entirely. Release allocation and drop paths call
  the C allocator directly.
- Generated C is identical in both modes; the mode is chosen when compiling generated C (and, for L1, when building the
  runtime archive). A release build trades temporal/spatial diagnostics for raw pointer performance and is an explicit
  opt-out of checked semantics.
- Follow-up: surface the release mode as a first-class driver flag (`l0c`/`l1c`) and an L1 unchecked archive build
  variant, instead of a raw C define passed through build flags.

## Non-Goals

- No ownership types, borrow checking, static alias analysis, per-site static check elision, pointer tagging, or
  enforced type IDs.
- No compiler diagnostic-code reservation is required; failures are runtime diagnostics.
- No claim of complete temporal memory safety after quarantine eviction and address reuse.
- No temporal validation guarantees in release (unchecked) builds; that mode is an explicit opt-out.

## Completion Notes

Completed on 2026-07-03.

- Implemented checked-by-default pointer access validation across L0 Stage 1, L0 Stage 2, and L1 Stage 1.
- Added per-site pointer-check caches, read-only string storage registration, split drop validation, and unchecked
  runtime compile-out modes.
- Preserved generated `#line` source fidelity for checked pointer accesses after per-site cache declarations.
- Recorded the shared architecture in `docs/decisions/0010-checked-runtime-pointer-access-validation.md`.
- Final validation: `make clean test-all`.

## Verification Criteria

- The callee-drop repro reports a runtime pointer error instead of segfaulting.
- Null, unregistered, quarantined, stale-derived, double-drop, and non-base drop cases report runtime errors.
- Raw allocation APIs remain usable by stdlib containers because their allocations are tracked.
- Field stores through explicit dereferences and nested embedded-struct chains on read-only records report
  `read-only pointer write` instead of mutating read-only storage.
- Existing memory trace and ARC trace tests continue to pass.
