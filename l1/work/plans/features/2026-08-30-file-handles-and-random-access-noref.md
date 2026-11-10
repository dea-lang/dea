# Feature Plan

## Add file handles and complete file I/O

- Date: 2026-08-30
- Last reviewed: 2026-11-10
- Status: In progress
- Title: Add opaque file handles, incremental transfers, random access, and synchronization
- Kind: Feature
- Priority: High
- Stdlib Tier: 1
- Parent Initiative: `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Subsystem: Stdlib / runtime / filesystem I/O
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/file.l1`
  - `l1/compiler/shared/l1/stdlib/std/bytes.l1`
  - `l1/compiler/shared/l1/stdlib/sys/fs.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l1/compiler/shared/runtime/internal/dea_rt_file.h`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l1/docs/reference/standard-library.md`
  - `l1/docs/reference/design-decisions.md`
- Test modules:
  - `l1/compiler/tests/file_runtime_test.py`
  - `l1/compiler/tests/fixtures/file_runtime/`
  - `l1/compiler/scripts/test_runner_common.py`
  - `l1/compiler/tests/l1c_child_trace_runner_test.py`
- Related:
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/work/plans/features/closed/2026-08-30-os-error-and-io-results-noref.md`
  - `l1/work/plans/features/closed/2026-08-30-dynamic-byte-buffers-noref.md`
- Repro: From `l1/`, run `make test-compiler TESTS="file_runtime_test.py runtime_symbol_manifest_test.py"`.

## Summary

Add the first stateful file API to L1. `std.file` owns opaque file handles and exposes incremental sequential I/O,
64-bit positioning, positional I/O, append, truncate, flush, and durability requests through structured results.

The ownership and I/O choices below are implemented and local validation has passed. The plan remains open for
exhaustive native CI evidence and the corresponding ADR closure records.

## Stdlib-First Direction and Reference Material

The public file contract owns the implementation requirements. Use `pc_meta_file`, bounded read/write loops, and
close-failure handling in [l1/compiler/support/preparation/platform.h][platform-support] as reference material and
sources of regression cases. Replace compiler-specific error and allocation conventions with the selected stdlib results
and ownership model. Compiler migration, shared-private-code extraction, and removal of superseded helpers are outside
this plan; L2 can adopt L1 stdlib through separate follow-up work once the APIs are complete.

## Public Surface

- Types: opaque `File`, `OpenFileResult`, `CloseResult`, `OpenOptions`, `AccessMode`, `CreateMode`, `SeekOrigin`, and
  `FileOffset` as a `long` alias.
- Lifetime: `open` returns `OpenFileResult`; `close(file: File*) -> CloseResult`;
  `free_open_file_result(result: OpenFileResult) -> CloseResult`.
- Transfers: `read_some`, `read_exact`, `write_some`, `write_all`.
- Positioning: `seek`, `position`, `read_at`, `write_at`.
- Extent: `size`, `truncate`.
- Handle metadata: `metadata`, querying the opened object and retaining `long` sizes and timestamp seconds.
- Completion: `flush`, `sync_data`, `sync_all`.

Transfers take an opaque `ByteBuffer*` plus a checked start/count range; they never require a returned slice. Buffer
starts, lengths, and per-call counts are `int`; file sizes, positions, and positional offsets are `long`.

## Ownership and Cleanup

1. `OpenFileResult` owns either one file wrapper or an open failure. Copies share a single cleanup obligation; extracted
   `File*` pointers borrow it. L1 does not enforce unique ownership through its type system.
2. `close` retires the public handle on its first attempt, including on failure, but preserves the wrapper. Store the
   first `CloseResult`, including its captured `OsError`; repeated calls return that result without another native close
   attempt. Unlike the private directory close helper, a repeated failed close does not become success.
3. Ordinary operations on a closed but live wrapper return `InvalidHandle`. After final cleanup, every borrowed alias is
   invalid; there is no recoverable closed-handle guarantee for a destroyed wrapper.
4. `free_open_file_result` closes an open file, destroys its wrapper, and returns the close outcome. For an already
   closed file it destroys the wrapper and returns the saved outcome. A failed-open variant needs no cleanup and returns
   success. Successful ownership is consumed exactly once, including when closing fails; destruction is not idempotent.
5. Register result-level cleanup with `with` before matching success or failure. Explicitly close and inspect the result
   when successful completion depends on closing. Cleanup returns an outcome for the caller to handle; it does not
   automatically propagate an error or replace a primary operation failure.
6. Keep native descriptors/handles and their runtime representation private. Follow each supported host's documented
   close-failure semantics; do not unconditionally retry an interrupted native close, risk closing a reused descriptor,
   or claim that every close failure proves native release. Public logical retirement and native release are distinct.

The result-level owner follows
[l1/docs/decisions/0046-filesystem-paths-and-owned-directory-traversal.md][directory-ownership]. The separate public
close operation and saved close outcome are deliberate file-specific choices. Record these decisions in a new L1 ADR
when implementation closes this plan.

## Required Semantics

1. Use direct native file operations without a library buffer. OS caching still applies. `flush` validates the live
   handle and succeeds without additional work; it does not request durability.
2. `sync_data` requests data synchronization as a minimum guarantee and may perform stronger full synchronization when a
   host lacks a distinct data-only operation. `sync_all` additionally requests associated metadata synchronization.
   Document actual host guarantees and return `Unsupported` when the requested minimum cannot be provided.
3. `read_at` and `write_at` do not mutate the shared cursor. Non-seekable handles return `NotSeekable`.
4. Append uses real host append behavior, not `seek(end)` followed by write. Reject `write_at` on an append handle with
   `InvalidInput` before transferring bytes. Native append guarantees apply per underlying write; a multi-call
   `write_all` does not promise one atomic append.
5. Validate read and write start/count ranges against `bytes::size`, following the existing asserted buffer-range
   convention. Callers resize destinations before reading. Reads preserve logical size on success, EOF, and failure;
   their results report the number of bytes filled. Do not expose backing storage or return views.
6. Reuse the direct error and transfer conventions in
   [l1/docs/decisions/0045-direct-os-errors-and-io-results.md][io-results]: EOF is distinct from failure, zero-length
   reads do not probe EOF, positive partial transfers succeed, and interruptions return without implicit retry.
   `read_exact` and `write_all` loop over successful partial transfers and report accumulated progress when interrupted,
   reaching EOF early, or failing. A positive-length write that makes zero progress must terminate with an error rather
   than loop indefinitely.
7. Child-process inheritance is disabled by default. No public operation exposes the native handle representation.
8. Handle metadata is obtained from the open native handle, not by resolving its original path again. Renaming or
   replacing that path cannot redirect the query to another object. Reuse the path-level metadata record and preserve
   unavailable-field and host-error distinctions.

## Implementation and Local Verification

Implemented `std.file`, its `sys.fs` transports, and synchronous checked buffer bridges without returning storage views.
The native implementation shares existing filesystem path/error helpers in the I/O translation unit. POSIX uses native
descriptors and `pread`/`pwrite`; Windows retains a synchronous primary handle and lazily reopens the same object with
overlapped I/O for cursor-independent positional transfers. Both runtime symbol manifests include the new exports.

Local validation ran on macOS Intel using `/usr/bin/clang`, Apple Clang 17.0.0, with `--no-default-config` support
verified. An explicitly selected upstream L0 Stage 2 compiler built canonical L1 and all 32 bundled interfaces. Test
commands selected that compiler through `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`.

Passed from `l1/`:

- `make test`: the fast local gate, including compiler smoke tests, examples, documentation tests, tooling, and
  fixture-based productization tests.
- `../.venv/bin/python compiler/tests/file_runtime_test.py`: actual public consumers in checked, basic, and unchecked
  modes; logical bounds; source/interface opacity; checked alias expiry; native and public L1 sparse offsets above 4
  GiB; non-seekable FIFO operations; first positional transfers after rename and path replacement; opened-object
  metadata; and resource traces. Hooks cover successful repeated short transfers with nonzero buffer starts, partial
  progress before EOF/interruption/timeout, no-space and zero-progress writes, missing/error metadata, synchronization
  failure and unsupported outcomes, and explicit or cleanup-triggered close failure.
- `make test-compiler TESTS="file_runtime_test.py bytes_test.py os_runtime_test.py io_runtime_test.py runtime_symbol_manifest_test.py l1c_child_trace_runner_test.py"`:
  all six focused regressions passed. The common trace-runner regression also passed.
- `../.venv/bin/python compiler/scripts/run_trace_tests.py --children file_main`: the actual file consumer passed with
  both required memory/ARC event families and zero leaked object or string pointers.
- `make docs`: strict reference generation passed, including the new stdlib and native declarations. The cleanup example
  in the library reference also passed an actual L1 source check.

Root ADR Impact, copyright, whitespace, and explicit C-contract checks passed, including the newly added implementation
header and native fixtures.

Independent review covered every new runtime and public file function, buffer bridges, error conversions, and direct
callers. It found no confirmed implementation defect. Coverage now includes successful multi-call transfers, first
positional access after rename, and public L1 wide offsets. The native probe also passed with MacPorts GCC 15.3.0 at
`/opt/local/bin/gcc-mp-15`, through `file_runtime_test.require_native`.

After the review changes, rebuilt all local runtime variants and reran the file, symbol-manifest, and file child-trace
checks successfully.

Windows fixtures check both handles for disabled inheritance, non-seekable `NUL` operations, captured Win32 domains and
codes, real overlapped partial completions followed by injected terminal errors, and first-error preservation when both
native closes fail. The same injected public-API fixture is selected on Windows and POSIX; Windows no longer skips
failure coverage. These conditional branches await native Windows CI and are not claimed as locally executed.

Remaining CI work: `make test-extended` / `make test-ci`, exhaustive traces and children, and native Linux x86_64, macOS
ARM, and Windows UCRT64 execution. These longer gates were deliberately left to CI. Windows API review and conditional
fixtures do not establish native Windows execution. Close this plan and record its atomic ADR decisions only after the
remaining evidence is available.

## Non-Goals

- memory mapping, locking, or file watching
- asynchronous or evented I/O
- changing container lengths to `long`
- exposing `FILE*`, file descriptors, or Win32 handles
- library buffering, automatic read-buffer growth, or positional writes through append handles
- new language ownership features or automatic error propagation from cleanup
- silently closing an independently owned endpoint through an adapter
- L2 compiler migration, bootstrap changes, or removal of compiler-private support

## ADR Impact

- Decision: Use result-owned file wrappers with separate close/destruction and a repeatable first close outcome.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Result-level cleanup establishes one owner before fallible work, while a live closed wrapper preserves
    error inspection and defined post-close behavior until final destruction.
- Decision: Use direct native file I/O without library buffering and make flush a live-handle check.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Native operations support positional access, append, partial-transfer reporting, and future process
    routing without a second buffering state to coordinate.
- Decision: Preserve native append and cursor-independent positional I/O by rejecting positional writes on append
  handles.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Host append descriptors do not uniformly honor positional-write offsets; rejecting the combination keeps
    both public contracts portable without promising whole-operation append atomicity.
- Decision: Define data and full synchronization as minimum guarantees that permit stronger host operations.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Hosts without separate data-only synchronization can satisfy the request through full synchronization;
    lack of the minimum guarantee remains observable rather than a silent success.
- Decision: Transfer only within pre-sized byte-buffer ranges without changing logical size or exposing storage.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Explicit sizing separates allocation from I/O and makes partial progress and destination contents
    predictable across EOF, interruption, and failure.
- Decision: Bind file metadata queries to the opened object independently of later path replacement.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Consumers need metadata for the object they actually opened; repeating a path lookup can inspect a
    different object and cannot provide that contract.

## Verification Criteria

01. Large sparse files can be traversed and modified through `long` offsets with `int`-sized buffers.
02. EOF, short transfer, interrupted operation, invalid handle, and non-seekable results remain distinct.
03. Positional I/O leaves the shared cursor unchanged. Append-handle `write_at` fails before writing; ordinary append
    follows the selected host contract without extending atomicity to a multi-call `write_all`.
04. Repeated close returns the first success or captured failure with no additional native close attempt. Live aliases
    observe `InvalidHandle` after close. Result cleanup releases the wrapper exactly once after explicit close, close
    failure, normal scope exit, and early exits; failed-open cleanup succeeds without native work. Verify alias expiry
    under supported checked-runtime lifetime validation and do not treat destruction as repeatable.
05. Deterministic failure injection covers close, interruption, and synchronization failures, partial transfers before
    terminal failure or early EOF, and zero-progress writes. Confirm exact/all helpers retain progress and do not spin.
06. Normal and traced runtime symbol manifests remain complete.
07. Where host sharing rules permit, rename the opened path or replace it with another object and verify handle metadata
    still describes the original object while path metadata describes the current name. State host limitations and cover
    closed handles, unavailable fields, and injected metadata failures.
08. Pre-sized read/write ranges reject invalid bounds, preserve logical size, and handle zero-length and exact-boundary
    transfers. Verify the reported prefix after short reads and terminal outcomes without exposing buffer storage.
09. `flush` performs no durability request and rejects a closed handle. Verify stronger `sync_data` fallbacks, full-sync
    requests, and unsupported minimum guarantees independently of host timing.
10. Exercise actual `.l1` consumers and resource traces on Linux x86_64, macOS Intel/ARM, and Windows UCRT64. Record
    unavailable native evidence separately from simulated platform checks; local evidence is recorded above and the
    remaining native CI gate is open.

[directory-ownership]: ../../../docs/decisions/0046-filesystem-paths-and-owned-directory-traversal.md
[io-results]: ../../../docs/decisions/0045-direct-os-errors-and-io-results.md
[platform-support]: ../../../compiler/support/preparation/platform.h
