# ADR-0010: Checked Runtime Pointer Access Validation

- Decision date: 2026-07-03
- Last edited: 2026-07-04
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

The runtime tracks allocation records with base address, size, alignment, state, memory kind, allocation site, release
site, generation, and a reserved type-id field. Base pointers use a hash table; interior pointers resolve through an
address-ordered tree. Released records remain in a bounded quarantine so common temporal errors report diagnostics
instead of falling through to allocator reuse.

Every generated checked access site owns a static pointer-site cache. Fast-path hits validate the cached record
generation and access range; slow-path misses perform the full runtime lookup and refill the cache. Generated cache
declarations must not shift source locations reported by runtime diagnostics.

Runtime-managed string storage is registered as read-only tracked storage lazily, at first raw-byte exposure through
`rt_string_bytes_ptr`; strings that never hand out raw bytes stay out of the tracker. Exposed results may be read
through checked pointers, but checked writes, `drop`, `rt_free`, and `rt_realloc` against those records fail at runtime.
Any runtime path that exposes raw or interior pointers into heap string bytes must register the storage the same way
before handing out the pointer.

Unchecked runtime builds remain an explicit opt-out: `L0_RT_UNCHECKED` for the L0 header runtime and `DEA_RT_UNCHECKED`
for the L1 archive runtime. The opt-out is surfaced as the `--unchecked` driver flag (valid in `--build`, `--run`, and
`--gen`; mutually exclusive with the trace flags): the drivers emit the mode define into the generated C prelude, and
the L1 driver additionally links the prebuilt `libdea_rt_unchecked.a` archive variant. Generated code shape is otherwise
identical in both modes, and a raw define passed through C flags remains a supported route for the L0 header runtime.

## Rationale

- Checked-by-default access keeps Dea's "no undefined behavior in the language itself" goal intact when raw aliases
  escape static ownership checks.
- Runtime validation fits the current C backend and bootstrap constraints without adding ownership types, borrow
  checking, pointer tagging, or type-identity enforcement.
- Per-site caches keep repeated checked accesses cheap enough for default builds while preserving precise diagnostics.
- A compile-time unchecked mode preserves a deliberate release-performance escape hatch without changing source syntax
  or generated C shape.
- Treating runtime-owned strings as read-only tracked storage prevents mutable aliases to ARC-managed and static string
  bytes.

## Consequences

- Backends for each Dea level must lower all pointer-shaped accesses and generated drop cleanup through the runtime
  check helpers.
- Runtime helpers that expose raw or interior pointers to checked code must register or validate the underlying storage
  first.
- Diagnostics for invalid pointer access are runtime diagnostics, not compiler diagnostic-code entries.
- Temporal detection is bounded by quarantine retention and allocation-record tracking; unchecked builds make no
  temporal validation guarantee.
- Level runtimes may keep different implementation layouts and symbol surfaces, but the default semantics remain shared.
- Tracker hash-table rebuilds are sized from the live record count, so sustained alloc/free churn purges tombstones at a
  stable capacity and long-running services do not accumulate table growth from lifetime frees.
- Record-pool memory is peak-driven: pool memory is never returned to the C allocator by design, so checked-mode memory
  overhead is bounded by the peak count of live plus quarantined allocations.
- The tracker state is unsynchronized global state; checked mode assumes a single-threaded program.
- Quarantine retention and tracker sizing constants are compile-time overridable in both runtimes, and the prebuilt L1
  archive runtime also honors `DEA_RT_QUARANTINE_MAX_BYTES` and `DEA_RT_QUARANTINE_MAX_COUNT` environment overrides read
  once at first tracker use. Smaller retention trades temporal-detection depth for allocator reuse in allocation-heavy
  code. The retention default stays at 4096 records (detection-first for checked development builds); `256` is the
  documented suggestion for performance-sensitive checked deployments, based on the benchmark matrix recorded in the
  shared runtime allocation tracker benchmark plan, which showed the retention cost curves are compiler-independent and
  intermediate values near 1024 buy no performance over 4096.
- The unchecked opt-out and the retention tunables are exposed through the build surface: the shared `--unchecked`
  driver flag, the L1 `libdea_rt_unchecked.a` archive variant built alongside the default and traced archives, and
  make-level variables that compose the corresponding C defines (`L0_RT_UNCHECKED`, `L0_RT_QUARANTINE_MAX_*` for L0
  builds; `L1_RT_QUARANTINE_MAX_*` baked into the L1 archives). The `make bench-runtime` targets in both levels measure
  the retention settings across C compilers and are the tool for revisiting the retention defaults.

## Related Plans

- [work/plans/features/closed/2026-06-30-shared-runtime-pointer-access-validation-noref.md](../../work/plans/features/closed/2026-06-30-shared-runtime-pointer-access-validation-noref.md)
- [l0/work/plans/features/closed/2026-06-30-runtime-pointer-access-validation-noref.md](../../l0/work/plans/features/closed/2026-06-30-runtime-pointer-access-validation-noref.md)
- [l1/work/plans/features/closed/2026-06-30-runtime-pointer-access-validation-noref.md](../../l1/work/plans/features/closed/2026-06-30-runtime-pointer-access-validation-noref.md)
- [work/plans/bug-fixes/closed/2026-07-03-shared-alloc-tracker-churn-rehash-noref.md](../../work/plans/bug-fixes/closed/2026-07-03-shared-alloc-tracker-churn-rehash-noref.md)
- [work/plans/features/closed/2026-07-03-shared-lazy-arc-string-registration-noref.md](../../work/plans/features/closed/2026-07-03-shared-lazy-arc-string-registration-noref.md)
- [work/plans/features/closed/2026-07-04-shared-runtime-alloc-benchmark-noref.md](../../work/plans/features/closed/2026-07-04-shared-runtime-alloc-benchmark-noref.md)

## Current Docs

- [l0/docs/reference/design-decisions.md](../../l0/docs/reference/design-decisions.md): L0 runtime pointer validation
  policy and release-mode notes
- [l0/docs/reference/standard-library.md](../../l0/docs/reference/standard-library.md): L0 `sys.memory` and `sys.rt`
  runtime surfaces affected by pointer validation
- [l1/docs/reference/standard-library.md](../../l1/docs/reference/standard-library.md): L1 `sys.memory` and `sys.rt`
  runtime surfaces affected by pointer validation
- [l1/docs/roadmap.md](../../l1/docs/roadmap.md): L1 bootstrap baseline status
