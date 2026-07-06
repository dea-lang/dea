# Feature Plan

## Shared lazy ARC string registration

- Date: 2026-07-03
- Status: Completed
- Title: Register heap string blocks with the pointer tracker lazily at first raw-byte exposure
- Kind: Feature
- Severity: Medium
- Stage: Shared
- Subsystem: Runtime allocation tracker, string runtime
- Scope: Shared
- Targets:
  - L0 shared header runtime
  - L1 shared archive runtime
- Origin: Checked-mode performance follow-up from the shared allocation tracker churn rehash bug fix
- Porting rule: Keep the lazy registration contract identical across the L0 header runtime and the L1 archive runtime;
  level runtimes keep their own helper naming and symbol manifests.
- Target status:
  - L0 shared header runtime: Done
  - L1 shared archive runtime: Done
- Modules:
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l1/compiler/shared/runtime/src/dea_rt_string.c`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_runtime_alloc_tracker.py`
  - `l0/compiler/stage1_py/tests/backend/test_runtime_pointer_validation.py`
  - `l1/compiler/stage1_l0/tests/runtime_alloc_tracker_test.py`
  - `l1/compiler/stage1_l0/tests/io_runtime_test.py`
- Related:
  - `work/plans/bug-fixes/closed/2026-07-03-shared-alloc-tracker-churn-rehash-noref.md`
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
  - `l1/work/plans/features/2026-06-21-cheap-string-slices-noref.md`

## Summary

Checked builds currently register every heap string block with the pointer access tracker at allocation and unregister
it on final ARC release, so string-churn-heavy programs (for example the compiler bootstrap) pay one hash insert, one
treap insert, one hash remove, and one treap remove per string even though checked pointers into string bytes only arise
through `rt_string_bytes_ptr`. This plan registers heap string blocks lazily at first `rt_string_bytes_ptr` exposure,
mirroring the existing lazy registration of static string spans, and keeps release-side unregistration tolerant of
never-registered blocks.

## Shared Design

- Add one idempotent lazy registration helper to the tracker: look up the block base first and register a read-only
  ARC-kind record only when absent.
- `rt_string_bytes_ptr` registers heap string storage (header plus bytes plus terminator, based at the block) before
  returning the byte pointer, so checked reads validate as interior pointers exactly as before.
- String allocation and string reallocation stop registering eagerly. Final ARC release keeps calling the untrack
  helper, which is already a no-op when no record exists; for never-exposed strings that is one failed hash lookup
  instead of two inserts and two removes.
- Checked-write, `drop`, `rt_free`, and `rt_realloc` rejection semantics for exposed string storage are unchanged
  because the record still exists (read-only, ARC kind, not droppable) whenever a raw pointer has been handed out.
- Temporal diagnostics for string byte pointers are unchanged in kind: dangling `rt_string_bytes_ptr` pointers report as
  unregistered access after release, exactly as today, because final release already removes the record without
  quarantining ARC storage. Under memory tracing the record's recorded allocation site becomes the exposure site
  (`<runtime>`) instead of the string allocation site.
- Constraint for follow-up work: any future runtime path that exposes raw or interior pointers into heap string bytes
  (for example ARC-backed `dea::slice` string views from the cheap-string-slices draft) must call the same lazy
  registration helper before handing out the pointer.

## Non-Goals

- No change to static string span registration (already lazy).
- No change to unchecked builds.
- No quarantine for ARC-managed storage.
- No reduction of tracker cost for `new`/`rt_alloc` user allocations (treap participation and record layout stay
  follow-up work).

## Completion Notes

Completed on 2026-07-03.

- Replaced the eager `_rt_track_arc_alloc` helper with the idempotent lazy `_rt_track_arc_bytes` helper in both runtimes
  and updated the L1 symbol manifests.
- String allocation and reallocation no longer touch the tracker; `rt_string_bytes_ptr` registers heap storage at first
  exposure and final ARC release keeps the tolerant untrack call.
- White-box laziness coverage added to the L0 tracker churn tests; L1 keeps behavioral coverage through the `io_runtime`
  read-only write fixtures.
- Benchmarks (tcc bootstrap host): a five-million-pair string churn loop dropped from about 0.41 s of tracking overhead
  to none; `make -C l0 triple-test` improved from about 35 s to about 34 s, and to about 31 s when combined with
  `_RT_QUARANTINE_MAX_COUNT=0`, against a pre-validation baseline of about 11 s. The remaining checked-mode bootstrap
  overhead is dominated by per-access checks and `new`/`drop` tracking, which stay follow-up work.

## Verification Criteria

- White-box churn tests assert that pure string churn leaves the tracker empty and that `rt_string_bytes_ptr`
  registration is idempotent.
- Existing pointer-validation suites keep passing: read-only write rejection for heap and static string bytes, drop and
  free rejection on string storage, and stale byte-pointer reporting.
- ARC and memory trace suites keep passing unchanged (registration emits no trace events).
- Bootstrap benchmark: `make -C l0 triple-test` wall time improves measurably against the checked baseline.
