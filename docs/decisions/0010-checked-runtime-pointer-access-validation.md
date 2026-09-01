# ADR-0010: Checked Runtime Pointer Access Validation

- Decision date: 2026-07-03
- Last edited: 2026-09-01
- Status: Accepted

## Context

Dea's static ownership checks reject many local use-after-drop patterns, but raw pointer aliases can still outlive a
callee-side `drop` or raw-memory release. Before this decision, generated pointer dereferences lowered directly to C
accesses, so invalid aliases could become C undefined behavior instead of a Dea runtime failure.

L0 and L1 share the same safety goal but have different runtime shapes: L0 embeds a header runtime, while L1 links an
archive runtime with public symbol manifests. The pointer-access contract therefore needs one shared semantic decision
with level-specific implementation details.

## Decision

Generated Dea code validates pointer dereferences, pointer field accesses, pointer indexing, and generated drop cleanup
by default before touching the pointed-to storage.

The runtime tracks allocation records with base address, size, alignment, state, allocation provenance, allocation site,
release site, generation, and a reserved type-id field. Provenance distinguishes raw (`rt_alloc`/`rt_calloc`/
`rt_realloc`), `new`, ARC, static, and registered foreign storage. `drop` accepts only a live exact-base `new`
allocation, while `rt_free` and `rt_realloc` accept only raw allocations. Generated drop begin calls also provide the
pointee size and alignment, so an invalid cast to a larger owned type fails before field cleanup can dereference it.
Base pointers use a hash table; interior pointers resolve through an address-ordered tree. Released owned records remain
in a bounded quarantine so common temporal errors report diagnostics instead of falling through to allocator reuse.

Every generated checked access site owns a static pointer-site cache. Fast-path hits validate the cached record
generation and access range; slow-path misses perform the full runtime lookup and refill the cache. Generated cache
declarations must not shift source locations reported by runtime diagnostics.

Runtime-managed string byte storage is registered as read-only tracked storage lazily at the exact pointer exposed by
`rt_string_bytes_ptr`; strings that never hand out raw bytes stay out of the tracker. Exposed results may be read
through checked pointers, but checked writes, `drop`, `rt_free`, and `rt_realloc` against those records fail at runtime.
Any runtime path that exposes raw or interior pointers into heap string bytes must register the storage the same way
before handing out the pointer.

Externally owned memory crosses the checked boundary through `rt_register_foreign(ptr, bytes, read_only)` and
`rt_unregister_foreign(ptr)`. Registration records an explicit lifetime and accessible extent without transferring
ownership; unregistration removes that tracking without freeing the payload. A later access fails as unregistered in the
fully checked runtime; basic mode retains its general hash-miss-as-untracked contract. In checked modes, repeating an
identical live registration is idempotent, while conflicting registrations and invalid unregistrations panic. Unchecked
builds still validate the registration arguments but intentionally keep no tracker state.

Unchecked runtime builds remain an explicit opt-out: `L0_RT_UNCHECKED` for the L0 header runtime and `DEA_RT_UNCHECKED`
for the L1 archive runtime. The opt-out is surfaced as the `--unchecked` driver flag (valid in `--build`, `--run`, and
`--gen`; mutually exclusive with the trace flags): the drivers emit the mode define into the generated C prelude, and
the L1 driver additionally links the prebuilt `libdea_rt_unchecked.a` archive variant. Generated code shape is otherwise
identical in both modes, and a raw define passed through C flags remains a supported route for the L0 header runtime.

Basic checked runtime builds remain checked builds: `L0_RT_CHECK_BASIC` for the L0 header runtime and
`DEA_RT_CHECK_BASIC` for the L1 archive runtime. The `--check-basic` driver flag (valid in `--build`, `--run`, and
`--gen`; mutually exclusive with unchecked and trace flags) keeps exact-base hash validation, quarantine, generation
caches, null checks, double-drop and untracked-drop diagnostics, exact-base ARC/static string read-only protection, and
alignment checks for hash-miss accesses while compiling out the interior-pointer treap and static-overlap checks. L1
links `libdea_rt_check_basic.a` for build/run and warns on `--gen` so callers link the matching archive or compile the
runtime sources with `DEA_RT_CHECK_BASIC`.

Native compiler executables use a compiler-specific checked-runtime profile. L0 Stage 2 and the L0-hosted L1 Stage 1
compiler default to basic checks with a 256-record quarantine cap. Their Make interfaces retain explicit full and
unchecked selections plus compiler-specific quarantine overrides. This profile affects only the runtime embedded in the
compiler executable: generated user programs remain full checked by default, and L1 continues to build and select its
distinct full, basic, unchecked, and traced runtime archives independently.

## Rationale

- Checked-by-default access keeps Dea's "no undefined behavior in the language itself" goal intact when raw aliases
  escape static ownership checks.
- Runtime validation fits the current C backend and bootstrap constraints without adding ownership types, borrow
  checking, pointer tagging, or type-identity enforcement.
- Per-site caches keep repeated checked accesses cheap enough for default builds while preserving precise diagnostics.
- A compile-time unchecked mode preserves a deliberate release-performance escape hatch without changing source syntax
  or generated C shape.
- A compile-time basic checked mode preserves the checked-runtime backstop for exact allocation bases while reducing the
  allocation-tracker and interior-lookup cost that remains before static check elision exists.
- Using the basic checked mode for native compiler executables recovers a meaningful portion of compiler-only time while
  preserving exact-base validation and leaving generated-program safety defaults unchanged.
- Treating runtime-owned strings as read-only tracked storage prevents mutable aliases to ARC-managed and static string
  bytes.

## Consequences

- Backends for each Dea level must lower all pointer-shaped accesses and generated drop cleanup through the runtime
  check helpers.
- Runtime helpers that expose raw or interior pointers to checked code must register or validate the underlying storage
  first.
- Allocation families are not interchangeable: raw memory uses `rt_free`/`rt_realloc`, `new` memory uses `drop`, ARC
  storage uses its ARC lifetime, and foreign registration never authorizes runtime release.
- Diagnostics for invalid pointer access are runtime diagnostics, not compiler diagnostic-code entries.
- Temporal detection is bounded by quarantine retention and allocation-record tracking; unchecked builds make no
  temporal validation guarantee.
- AddressSanitizer builds poison quarantined user payloads until eviction, preserving sanitizer visibility for direct
  stale C accesses without making tracker metadata inaccessible. Eviction unpoisons each range before allocator release.
- Basic checked builds preserve temporal diagnostics for exact base pointers while treating hash-miss interior pointers
  as untracked alignment-checked storage.
- Level runtimes may keep different implementation layouts and symbol surfaces, but the default semantics remain shared.
- Tracker hash-table rebuilds are sized from the live record count, so sustained alloc/free churn purges tombstones at a
  stable capacity and long-running services do not accumulate table growth from lifetime frees. Removal also rebuilds
  when the live count falls below one quarter of the current capacity, so the table contracts after a large live set
  subsides instead of retaining its peak slot array.
- Record-pool memory is peak-driven: pool memory is never returned to the C allocator by design, so checked-mode memory
  overhead is bounded by the peak count of live plus quarantined allocations.
- The tracker state is unsynchronized global state; checked mode assumes a single-threaded program.
- Quarantine retention and tracker sizing constants are compile-time overridable in both runtimes, and the prebuilt L1
  archive runtime also honors `DEA_RT_QUARANTINE_MAX_BYTES` and `DEA_RT_QUARANTINE_MAX_COUNT` environment overrides read
  once at first tracker use. Smaller retention trades temporal-detection depth for allocator reuse in allocation-heavy
  code. The retention default stays at 4096 records (detection-first for checked development builds); `256` is the
  documented suggestion for performance-sensitive checked deployments. The corrected monotonic, anti-elision benchmark
  matrix shows that smaller caps generally reduce allocation-heavy costs, but the magnitude and the value of
  intermediate settings vary by compiler and workload; deployments that need more temporal depth should measure their
  own 1024-or-higher tradeoff rather than treating one intermediate setting as universally equivalent to 4096.
- Per-site check granularity is the intended unit for future static check elision: a site a static analysis proves safe
  is simply not lowered through the check helper, while unproven sites keep their runtime check, and elision never
  rejects a program the analysis cannot verify. The long-term direction, including the staged analysis and the
  differential-oracle role of the checked runtime, is recorded in
  [work/proposals/static-pointer-check-elision.md](../../work/proposals/static-pointer-check-elision.md).
- The checked-basic mode, unchecked opt-out, and retention tunables are exposed through the build surface: the shared
  `--check-basic` and `--unchecked` driver flags, the L1 `libdea_rt_check_basic.a` and `libdea_rt_unchecked.a` archive
  variants built alongside the default and traced archives, and make-level variables that compose the corresponding C
  defines (`L0_RT_CHECK_BASIC`, `L0_RT_UNCHECKED`, `L0_RT_QUARANTINE_MAX_*` for L0 builds; `DEA_RT_CHECK_BASIC` and L1
  retention settings baked into the L1 archives). The `make bench-runtime` targets in both levels measure the retention
  settings plus the basic checked mode across C compilers and are the tool for revisiting the retention defaults. The
  harness uses monotonic wall time and observable pointer escapes so optimized unchecked loops cannot disappear.
- L1 runtime object variants carry content-sensitive build-configuration stamps. Changing the selected compiler, runtime
  flags, checked-mode defines, or baked tuning values rebuilds the affected archives and tcc objects; repeating an
  identical configuration remains an incremental no-op.
- Compiler-build runtime controls are separate from generated-program controls. In particular, the L1 compiler's
  level-named compiler variables configure the L0 runtime embedded in `l1c-stage1.native`; they do not alter L1 runtime
  archives or the runtime mode selected for programs compiled by that executable.

## Related Plans

- [work/plans/features/closed/2026-06-30-shared-runtime-pointer-access-validation-noref.md](../../work/plans/features/closed/2026-06-30-shared-runtime-pointer-access-validation-noref.md)
- [l0/work/plans/features/closed/2026-06-30-runtime-pointer-access-validation-noref.md](../../l0/work/plans/features/closed/2026-06-30-runtime-pointer-access-validation-noref.md)
- [l1/work/plans/features/closed/2026-06-30-runtime-pointer-access-validation-noref.md](../../l1/work/plans/features/closed/2026-06-30-runtime-pointer-access-validation-noref.md)
- [work/plans/bug-fixes/closed/2026-07-03-shared-alloc-tracker-churn-rehash-noref.md](../../work/plans/bug-fixes/closed/2026-07-03-shared-alloc-tracker-churn-rehash-noref.md)
- [work/plans/features/closed/2026-07-03-shared-lazy-arc-string-registration-noref.md](../../work/plans/features/closed/2026-07-03-shared-lazy-arc-string-registration-noref.md)
- [work/plans/features/closed/2026-07-04-shared-runtime-alloc-benchmark-noref.md](../../work/plans/features/closed/2026-07-04-shared-runtime-alloc-benchmark-noref.md)
- [work/plans/features/closed/2026-07-08-shared-runtime-check-basic-mode-noref.md](../../work/plans/features/closed/2026-07-08-shared-runtime-check-basic-mode-noref.md)
- [work/plans/bug-fixes/closed/2026-07-11-shared-checked-runtime-review-gaps-noref.md](../../work/plans/bug-fixes/closed/2026-07-11-shared-checked-runtime-review-gaps-noref.md)
- [work/plans/bug-fixes/closed/2026-07-13-shared-checked-runtime-contraction-alignof-noref.md](../../work/plans/bug-fixes/closed/2026-07-13-shared-checked-runtime-contraction-alignof-noref.md)
- [work/plans/features/closed/2026-07-16-shared-compiler-runtime-check-basic-default-noref.md](../../work/plans/features/closed/2026-07-16-shared-compiler-runtime-check-basic-default-noref.md)
- [work/plans/bug-fixes/closed/2026-09-01-shared-builtin-and-runtime-contract-observability-noref.md](../../work/plans/bug-fixes/closed/2026-09-01-shared-builtin-and-runtime-contract-observability-noref.md)

## Current Docs

- [l0/docs/reference/design-decisions.md](../../l0/docs/reference/design-decisions.md): L0 runtime pointer validation
  policy and release-mode notes
- [l0/docs/reference/standard-library.md](../../l0/docs/reference/standard-library.md): L0 `sys.memory` and `sys.rt`
  runtime surfaces affected by pointer validation
- [l1/docs/reference/standard-library.md](../../l1/docs/reference/standard-library.md): L1 `sys.memory` and `sys.rt`
  runtime surfaces affected by pointer validation
- [l1/docs/reference/design-decisions.md](../../l1/docs/reference/design-decisions.md): L1 compiler and runtime build
  defaults
- [l1/docs/roadmap.md](../../l1/docs/roadmap.md): L1 bootstrap baseline status
