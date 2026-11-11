# Refactor Plan

## Decouple byte-buffer range actions from file I/O

- Date: 2026-11-10
- Status: In Progress
- Title: Keep byte-buffer range dispatch independent of I/O without per-transfer allocations
- Kind: Refactor
- Priority: Medium
- Subsystem: L1 standard-library buffer borrowing and file-transfer adapters
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/bytes.l1`
  - `l1/compiler/shared/l1/stdlib/std/file.l1`
  - `l1/compiler/shared/l1/stdlib/std/os.l1` (conversion reuse, only if needed)
- Test modules:
  - `l1/compiler/tests/byte_buffer_range_action_test.py` (new)
  - `l1/compiler/tests/fixtures/bytes/range_action_main.l1` (new)
  - `l1/compiler/tests/bytes_test.py`
  - `l1/compiler/tests/file_runtime_test.py`
  - `l1/compiler/tests/fixtures/file_runtime/`
  - `l1/compiler/tests/l1c_child_trace_runner_test.py`
  - `l1/compiler/scripts/test_runner_common.py` (child-fixture registration)
- Related:
  - [l1/work/plans/features/closed/2026-08-30-file-handles-and-random-access-noref.md][file-plan]
  - [l1/work/plans/features/2026-08-30-secure-os-entropy-noref.md][entropy-plan]
  - [l1/docs/decisions/0052-owned-dynamic-byte-buffers.md][buffer-adr]
  - [l1/docs/decisions/0059-presized-byte-buffer-file-transfers.md][transfer-adr]
  - [l1/docs/reference/standard-library.md][stdlib]
  - [l1/docs/reference/ownership.md][ownership]
  - [l1/docs/reference/filesystem.md][filesystem]
- Repro: From `l1/`, `make test-compiler TESTS="bytes_test.py byte_buffer_range_action_test.py file_runtime_test.py"`;
  use the focused trace and supporting regression selections below.

## Summary

Implemented the synchronous unsafe range callback and migrated all four file transfers. `std.bytes` owns logical-range
validation and temporary access to storage without I/O dependencies. `std.file` owns its native calls and explicit
public-result conversion. Context and results pass by value, using existing native file handles, with no added heap
allocation per transfer. The protocol is also the prerequisite for later entropy work.

This is a standalone L1 refactor of the completed file implementation. Medium priority reflects a useful module-boundary
improvement without a prior correctness blocker. Focused local verification and independent production/generated-C/test
review passed. The plan remains open for native CI and final ADR/index/closure work; broad and long suites were left to
CI. The completed filesystem initiative remains closed.

## ADR Impact

- Decision: Permit synchronous unsafe callback access to opaque byte-buffer storage without an escaping view.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0052-owned-dynamic-byte-buffers.md`
  - Rationale: Qualify the unconditional prohibition on exposing backing storage while retaining opaque layout, explicit
    ownership, logical sizing, and the prohibition on returning or retaining a pointer or slice.
- Decision: Use a finite by-value context and result protocol with action-specific diagnostic meanings for
  I/O-independent byte-buffer range actions.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Record the reusable callback boundary, absence of transport allocations, and caller responsibility for
    pairing an action with its diagnostic schema. File and entropy operations belong to their provider modules, with
    `std.bytes` interpreting no OS payloads. No protocol-domain token or global identifier namespace is needed; field
    types are checked, but schema pairing is not enforced by the compiler.
- Decision: Move native file transfers and result adaptation into `std.file` while preserving public transfer semantics.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0059-presized-byte-buffer-file-transfers.md`
  - Rationale: Replace the file-specific internal bridge with the generic callback boundary, retaining pre-sized logical
    ranges, partial progress, empty-transfer validation, and exact/all behavior. File-local adapters preserve the native
    OS error domain and full native code through explicit diagnostic-field conversion.

## Implementation Scope

The previous file-specific `_bytes_file_read`, `_bytes_file_write`, `_bytes_file_read_at`, and `_bytes_file_write_at`
bridges are removed, together with `std.bytes` imports of `sys.fs` and `sys.os`. The replacement helper validates
logical ranges and result counts; private file callbacks call the native runtime and convert its results. Opaque layout
requires storage access to originate in `std.bytes`, but does not require I/O to execute there.

Source and emitted-interface consumers use the exported unsafe protocol; no friend-module or compiler-private API is
introduced. Existing safe byte-buffer/file APIs and the native runtime ABI are preserved. The normal build regenerated
and verified 32 bundled interfaces. No L0/L2 port, compiler feature, new diagnostic code, or diagnostic reassignment was
introduced; negative type/opacity tests use existing diagnostics.

## Range-Action Protocol

`std.bytes` exports the following transparent types while keeping `ByteBuffer` opaque. Declaration contracts specify the
unsafe borrow and action-defined result interpretation.

```dea
struct ByteBufferRangeActionContext {
    state: void*?;
    argument: long;
}

struct ByteBufferRangeActionDiagnostic {
    tag: int;
    code: int;
    detail: int;
    value: long;
}

enum ByteBufferRangeActionResult {
    RangeActionApplied(processed: int, value: long?);
    RangeActionStopped(processed: int, reason: ByteBufferRangeActionDiagnostic);
    RangeActionFailed(processed: int, error: ByteBufferRangeActionDiagnostic);
}

type ByteBufferRangeAction = unsafe func(
    byte*, int, ByteBufferRangeActionContext
) -> ByteBufferRangeActionResult;

unsafe func with_raw_range(
    buffer: ByteBuffer*, start: int, count: int,
    context: ByteBufferRangeActionContext,
    action: ByteBufferRangeAction
) -> ByteBufferRangeActionResult;
```

`with_raw_range` asserts `0 <= start <= size(buffer)` and `0 <= count <= size(buffer) - start` before invoking the
callback. Use subtraction after checking `start`, avoiding overflowing `start + count`. Capacity beyond logical size is
never accessible. Valid inputs invoke the callback exactly once, synchronously, including `count == 0`. For an empty
range, pass the existing base pointer without offsetting it; no byte is accessible and pointer identity is unspecified.

On callback return, assert `0 <= processed <= count` for every variant and return the result unchanged. Bounds and
result checks must run in checked, basic, and unchecked modes. The helper does not change length or capacity or roll
back callback effects. It does not validate action-specific diagnostic meanings.

`RangeActionApplied` means successful processing of the reported count, including partial or zero progress; it does not
promise the entire range was processed. Its optional `long` supports scalar results such as a position or checksum.
`RangeActionStopped` denotes an action-defined normal terminal condition; `RangeActionFailed` denotes failure. Both can
represent partial progress for general actions. `processed` measures progress, not a universal mutation footprint;
individual action contracts define their effects. This finite protocol does not support arbitrary typed return values.

The selected action's contract defines the meanings of `tag`, `code`, `detail`, and `value`. The caller receives the
immediate result of the callback it supplied and interprets those fields using that action's schema. Different actions
may give identical numeric payloads different meanings. There is no protocol-domain field, marker function, or global
identifier registry. `std.bytes` forwards diagnostics unchanged and cannot detect pairing a callback with the wrong
decoder; this remains the caller's responsibility. Heterogeneous dispatch that needs provenance would require a
separately specified contract.

`state` borrows an existing opaque resource pointer; `argument` carries a scalar such as an offset. `void*?` allows an
action-independent context without a new allocation or a dependency on provider types. A null state supports pure
actions. The compiler checks callback signatures, unsafe markers, fields, and result variants; the callback and caller
remain responsible for the erased pointer's actual meaning and diagnostic schema.

## Unsafe Contract

The helper, callback alias, and provider adapters document these obligations:

- The buffer, callback, and any context resource remain valid throughout the synchronous invocation. Context is
  borrowed; the helper neither owns nor frees it, and copying the context does not extend resource lifetime.
- Access only the supplied `count` bytes. An empty range grants no access. Reinterpreting `byte*` as another pointer
  type requires independent proof of alignment, extent, and valid representation.
- Neither the storage pointer nor any pointer derived from it may escape through a result, context, global, retained
  object, or asynchronous work. All use ends before the callback returns.
- Do not free or reallocate backing storage, destroy the buffer, or resize, reserve, clear, append, or otherwise alter
  its structural state through any alias. Do not reenter buffer operations on the same buffer during the callback.
  Coordinate conflicting concurrent accesses externally.
- Keep context storage and native handles live, and interpret them according to the selected action. Do not close a file
  handle during its transfer or retain a buffer-data pointer in `context.state`.
- Report a valid processed count and action-specific payload. A stop or failure provides no rollback; already performed
  effects remain observable according to the action's contract.
- Pair the selected action with a decoder that follows its diagnostic schema. Callback signature checking and payload
  validation do not prove that pairing; matching numeric values cannot identify which schema produced them.

The helper does not pin memory or enforce no-escape, aliasing, or ownership statically. A typed `byte*` provides element
typing, not a lifetime or bounds proof. Both helper and callback type retain `unsafe`; L1 permits ordinary functions to
call unsafe functions, so this marker is not a call-site permission gate. Do not claim that unsafe-contract violations
must be diagnosed or trap in unchecked mode. The explicit range/result assertions are enforceable independently.

## File Adapters and Allocation Boundary

Four private callbacks in `std.file` call their corresponding native operations. They use an existing file handle as
`state`, zero as the sequential argument, and the complete `long` offset as the positional argument. For example:

```dea
type RangeContext = bytes::ByteBufferRangeActionContext;
type RangeResult = bytes::ByteBufferRangeActionResult;

unsafe func _read_at_action(data: byte*, count: int, context: RangeContext) -> RangeResult {
    return _encode_file_result(rt_file_read_at(
        context.state as void*, data as void*, count, context.argument));
}

unsafe func _write_at_action(data: byte*, count: int, context: RangeContext) -> RangeResult {
    return _encode_file_result(rt_file_write_at(
        context.state as void*, data as void*, count, context.argument));
}
```

`read_at` constructs `RangeContext(file._handle, offset)` by value, calls
`bytes::with_raw_range(buffer, start, count, context, _read_at_action)`, and returns `_decode_file_read(result)`.
`write_at` follows the same path with `_write_at_action` and `_decode_file_write`. Sequential wrappers use their own
callbacks with `argument == 0`. No context `new`, address of a temporary, closure, boxed result, global scratch, or
per-file result scratch is needed.

Encode/decode by explicit variants and fields, never by reinterpreting one struct/enum layout as another:

| Native outcome   | Range result                            | Diagnostic fields |
| ---------------- | --------------------------------------- | ----------------- |
| Success, state 0 | `RangeActionApplied(count, null)`       | None              |
| EOF, state 1     | `RangeActionStopped(count, diagnostic)` | `tag = state`     |
| Failure, state 2 | `RangeActionFailed(count, diagnostic)`  | `tag = state`     |
| Timeout, state 3 | `RangeActionFailed(count, diagnostic)`  | `tag = state`     |

For diagnostics, copy `error.kind` to `code`, `error.domain` to `detail`, and `error.native_code` to `value`, preserving
the full signed `long`. `detail` retains the native OS error domain that distinguishes errno, Windows, and other
existing native error sources; it does not identify the callback protocol. `std.bytes` assigns no I/O meaning to this
field. Keep native state explicitly; do not infer timeout or failure solely from an error code.

Keep file callbacks and their decoders private to `std.file`, with each wrapper selecting the corresponding pair.
Decoders check permitted outcome/tag combinations, null success value, and existing error invariants before adapting to
public results. These checks validate the file schema and do not establish a result's provenance. Native terminal
outcomes currently have zero progress; assert this before converting them into single-attempt public variants that
cannot carry a count. Reject EOF for writes and malformed encodings instead of silently dropping information. Reuse
existing `std.os` conversion logic where possible without making `std.bytes` depend on `std.os` or `sys.os`. Preserve
unknown native codes and normalized `Other` errors; do not whitelist native codes or recapture ambient error state.

Do not short-circuit valid empty transfers in the buffer helper: native handle, offset, append, and seekability
validation must still execute. Preserve short transfers, exact/all accumulation, interruption without retry,
zero-progress write failure, unchanged buffer sizes, cursor preservation, wide offsets, close outcomes, and native error
snapshots. Preserve all existing append, metadata, synchronization, and handle-inheritance contracts.

The allocation guarantee covers range dispatch, context/result transport, and provider adapters. By-value aggregates may
use stack/ABI copies and the callback introduces an indirect call; this is not a zero-overhead claim. Arbitrary
callbacks may allocate under their own contracts. Existing native OS resources, including Windows' lazy positional
handle and operation resources, are outside the Dea heap-transport guarantee and must be reported separately.

## Follow-On Entropy Work

The entropy feature depends on validated range actions and file adapters.
[l1/work/plans/features/2026-08-30-secure-os-entropy-noref.md][entropy-plan] owns its callback adapter, public API,
native source selection, staging, error domains, result ownership, ADRs, and validation. Native entropy operations and
entropy-specific result conversion belong in the provider module, keeping `std.bytes` independent of I/O. Entropy
implementation and integration are outside this refactor and do not block its closure.

## Implementation Status

- [x] Added the transparent protocol, unsafe helper, pure callbacks, and real source/interface-only consumers.
- [x] Migrated all four file transfer paths and removed file-specific buffer exports/imports; native runtime behavior
  and public safe APIs are preserved.
- [x] Added protocol, malformed-adapter, allocation, and POSIX positional-failure coverage; registered the new child
  fixture and checked generated C for aggregate lowering without boxing or allocation.
- [x] Updated declaration contracts, [l1/docs/reference/standard-library.md][stdlib],
  [l1/docs/reference/ownership.md][ownership], [l1/docs/reference/filesystem.md][filesystem],
  [l1/docs/reference/design-decisions.md][design], and the existing buffer/transfer ADRs.
- [ ] Obtain the native CI evidence below; broad and long validation remains assigned to CI.
- [ ] Create the new protocol ADR and [l1/docs/decisions/INDEX.md][adr-index] entry, add closed-plan backlinks to all
  affected ADRs, and close the plan after acceptance. Update the still-active entropy plan's link to the closed
  location; leave that feature open under its existing initiative.

Assign the new ADR number from the live index at implementation closure. Amend the named ADRs and their Related Plans
links, add the new ADR and index entry, and link all records to this plan's closed location in the same closure change.
The other file ADRs remain preservation constraints; their ownership, append, synchronization, metadata, and width
decisions are unchanged.

## Tests and Verification Criteria

### Generic range protocol

- Run new coverage in checked, basic, and unchecked modes. Exercise a non-I/O byte transform and scalar-returning action
  with null state, nonzero starts, empty buffers, `start == size`, and reserved capacity outside logical size.
- Check exactly one callback invocation for every valid input/outcome, including zero-length ranges. Invalid negative,
  out-of-range, and overflow-shaped requests fail before callback entry; use observable nonallocating entry evidence.
- Cover every variant with zero, partial, and complete progress; reject negative and oversized progress in every
  variant. Preserve nullable scalar distinctions, signed wide arguments/results, and all diagnostic fields. Verify
  unchanged length/capacity, untouched surrounding bytes for bounded mutation fixtures, and no implicit rollback on
  stop/failure.
- Exercise source and emitted-`.l1m` consumers with transparent context/result fields, nullable `long`, unsafe function
  aliases, and independently defined non-I/O callbacks with their own diagnostic schemas. Verify unchanged diagnostic
  fields across module boundaries and interpretation by each callback's matching consumer, including identical numeric
  payloads with different action-specific meanings. Verify exact callback typing and continued opaque-buffer access
  rejection. Reject mismatched callback signatures/unsafe markers using existing diagnostics; do not require
  wrong-schema pairing to be detected by either the compiler or the range helper.
- Verify `std.bytes` source and emitted interfaces have no I/O imports, native entropy calls, or file/entropy-specific
  bridge exports. Test actual pure callback use; avoid relying solely on source-text assertions.

### File preservation and conversion

- Test explicit adapter conversion with valid and malformed file-schema payloads: mismatched outcome/tag, EOF on writes,
  non-null success values, and nonzero terminal progress. Preserve error kind, timeout identity, and native codes above
  `int_max`, including unknown codes classified as `Other`. Verify that `error.domain` survives encoding through
  `detail` and decoding without conflating identical numeric codes from different native OS error domains. Exercise each
  file wrapper's callback/decoder pairing; no protocol-domain rejection or function-identity tests are required. Keep
  test access local without adding production public test hooks.
- Retain sequential/positional reads and writes, successful short transfers, EOF/timeouts/failures, exact/all
  accumulated progress, interruption without retry, and zero-progress write failure. Add deterministic POSIX positional
  failure cases using existing `DEA_FILE_PREAD/PWRITE` hooks alongside sequential and Windows fault fixtures.
- Retain empty-transfer validation for closed handles, negative offsets, nonseekable handles, and append restrictions;
  wide sparse offsets above 4 GiB; unchanged cursor/size; first positional operation after rename; and native
  noninheritance. Keep checked lifetime tests separate from unconditional range/protocol assertions.

### Allocation and lifetime evidence

- Build real consumers with `--trace-arc --trace-memory`. Prepare buffer/file owners before a nonallocating, explicitly
  delimited measurement window; exercise both first and repeated generic dispatch and all four file-adapter paths.
  Include non-I/O callbacks returning partial failure to validate the general result contract independently of entropy.
- Reject transport allocation events, including `alloc`, `calloc`, `realloc`, `new_alloc`, `alloc_string`, and
  `realloc_string`. Include a positive-control allocation outside the window so disabled/missing tracing cannot pass.
  Count allocation events, not merely net live allocations or balanced cleanup. Do not hide a first-call context
  allocation behind warmup. Attribute native Windows resource acquisition separately.
- Independently check whole-log ARC/raw ownership balance and cleanup. The existing balanced trace check alone does not
  establish allocation freedom. Inspect generated C to confirm aggregate returns/context values are not boxed; retain
  executable allocation evidence as the acceptance criterion.

### Validation tiers and completion

From `l1/`, explicitly select supported `L0_CC`, `L1_CC`, `L1_RUNTIME_CC`, and `L1_BOOTSTRAP_L0C` as required by
[l1/AGENTS.md][guidance], recording actual executable versions. Reproduce focused validation with:

```sh
make test-compiler TESTS="bytes_test.py byte_buffer_range_action_test.py file_runtime_test.py os_runtime_test.py io_runtime_test.py runtime_symbol_manifest_test.py l1c_child_trace_runner_test.py"
make test-compiler-trace-children TESTS="bytes_main range_action_main file_main"
make docs
```

Keep exhaustive/long validation in CI: `make test-ci` and documentation checks on Linux x86_64, macOS Intel, macOS ARM,
and Windows UCRT64. Record native platform evidence separately; local or simulated Windows checks do not replace it.
Existing file-feature CI success does not validate this refactor. No entropy tests are required for this plan, and no
remote write or workflow dispatch is part of it.

Acceptance requires the I/O-free module boundary, enforceable range/protocol checks, preserved file behavior, positive
allocation-free transport evidence, independent correctness/portability review, completed local and native CI gates,
updated contracts/ADRs/index, and resolvable closed-plan links. Entropy adoption belongs to the later feature plan and
does not block this plan's closure. At planning time, run Markdown formatting/link checks and
`python3 scripts/check_adr_impact.py --all-active`.

## Local Verification Evidence

Local execution used macOS Intel and `/usr/bin/clang`, Apple Clang 17.0.0 (`clang-1700.6.4.2`), selected explicitly for
`L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`. Support for `--no-default-config` was verified. Bootstrap used the explicitly
selected existing L0 Stage 2 compiler, and `make build runtime` refreshed the compiler, interfaces, and runtime inputs.

- The focused `bytes_test.py`, `byte_buffer_range_action_test.py`, `file_runtime_test.py`, `os_runtime_test.py`,
  `io_runtime_test.py`, `runtime_symbol_manifest_test.py`, and `l1c_child_trace_runner_test.py` checks passed. File
  conversion/injection checks and the remaining public/native/wide/interface checks ran separately with unchanged
  production inputs; together they cover the full file harness.
- The range harness passed checked/basic/unchecked guards, every result variant, negative/oversized progress, exact
  callback invocation, and unsafe callback-type rejection. The positive separate-compilation consumer ran with both
  byte-buffer and callback-provider source absent. Interface checks also reject I/O imports.
- Allocation windows observed no allocation events across 128 first/repeated generic dispatches and all four file paths,
  including empty transfers, with a positive control outside the windows. Whole-program ownership traces balanced.
  Independent generated-C review found by-value scalar/pointer aggregates and no boxing, allocation, or ARC retention in
  dispatch, adapters, or conversion helpers.
- Focused child traces for `bytes_main`, `range_action_main`, and `file_main` passed with zero leaked object/string
  pointers. Strict `make docs`, C-contract checks, ADR Impact validation, and whitespace checks passed.

No broad aggregate, exhaustive compiler gate, or native Linux/macOS ARM/Windows run is claimed. Those checks remain for
CI.

## Non-Goals

No generic result polymorphism, closures, new borrow checker, safe dynamic-buffer slices, escaping storage views, async
callbacks, concurrent mutation policy, automatic buffer growth during I/O, generic streams, new native ABI, or broad
performance claim. The protocol can support later non-I/O actions without implementing those future capabilities here.

[adr-index]: ../../../docs/decisions/INDEX.md
[buffer-adr]: ../../../docs/decisions/0052-owned-dynamic-byte-buffers.md
[design]: ../../../docs/reference/design-decisions.md
[entropy-plan]: ../features/2026-08-30-secure-os-entropy-noref.md
[file-plan]: ../features/closed/2026-08-30-file-handles-and-random-access-noref.md
[filesystem]: ../../../docs/reference/filesystem.md
[guidance]: ../../../AGENTS.md
[ownership]: ../../../docs/reference/ownership.md
[stdlib]: ../../../docs/reference/standard-library.md
[transfer-adr]: ../../../docs/decisions/0059-presized-byte-buffer-file-transfers.md
