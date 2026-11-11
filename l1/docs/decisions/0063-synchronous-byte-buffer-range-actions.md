# ADR-0063: Synchronous Byte-Buffer Range Actions

- Decision date: 2026-11-11
- Last edited: 2026-11-11
- Status: Accepted

## Context

Opaque `std.bytes::ByteBuffer` storage must support bounded native transfers without exposing its layout or an escaping
view. Storage access originates in the defining module, but native operations and their result interpretation belong to
provider modules. The callback boundary must preserve this separation without allocating a context or result for each
transfer.

## Decision

Expose `std.bytes::with_raw_range` as a synchronous unsafe operation. It checks a start/count range against initialized
logical bytes, invokes one typed action, checks its reported progress, and returns its result unchanged. Range and
progress assertions apply in checked, basic, and unchecked runtime modes. Reserved capacity grants no access. Valid
empty ranges invoke the action exactly once with no accessible bytes and an unspecified pointer identity.

The `ByteBufferRangeAction` type is an
`unsafe func(byte*, int, ByteBufferRangeActionContext) -> ByteBufferRangeActionResult`. Context is a transparent
by-value record containing borrowed `state: void*?` and `argument: long`. Null state supports actions without an
external resource; copying the pointer neither transfers ownership nor extends lifetime.

Return a finite by-value result: `RangeActionApplied(processed: int, value: long?)`,
`RangeActionStopped(processed: int, reason: ByteBufferRangeActionDiagnostic)`, or
`RangeActionFailed(processed: int, error: ByteBufferRangeActionDiagnostic)`. Every count lies between zero and the
supplied count. All variants permit partial progress, and effects are not rolled back. Diagnostics contain `tag`,
`code`, and `detail` as `int`, plus `value: long`; the selected action defines their meanings. The caller pairs the
action with its result interpretation. There is no protocol-domain token, global schema namespace, or runtime provenance
check.

Keep `std.bytes` independent of I/O. Private `std.file` callbacks pass the existing native file handle and a `long`
offset by value, perform native operations, and explicitly convert their results. File decoding preserves the captured
native OS error domain and full native code; these domains identify OS error namespaces, not callback schemas. File
decoders enforce the narrower single-attempt file contract, including zero terminal progress and EOF only for reads.

The caller keeps buffer and context resources live throughout the call. The action accesses only the supplied bytes;
pointer reinterpretation requires alignment, extent, and representation proofs. Storage pointers and derived views must
not escape through results, context, globals, retained objects, or asynchronous work. Do not free, reallocate,
structurally mutate, or reenter operations on the same buffer through aliases during the action. Coordinate conflicting
concurrent access externally. The helper preserves logical size and capacity but does not pin storage or enforce
lifetime and no-escape obligations statically. Source and interface consumers receive the same callback type checking;
the unsafe marker is not a call-site permission gate.

Range dispatch, context/result transport, and file adapters add no Dea heap allocation per transfer. Arbitrary actions
may allocate under their own contracts. Stack/ABI copies, indirect-call cost, and native OS resource acquisition remain
outside that allocation guarantee.

## Rationale

A synchronous typed callback gives providers access for the duration of one operation while preserving opaque storage
ownership. The finite records express the required progress, scalar, and diagnostic data using existing L1 facilities.
By-value context avoids a separately allocated context object and lets positional operations retain full-width offsets.

The immediate caller selects both the action and its decoder, so a protocol identity token adds no necessary dispatch
information. Type checking validates field and callback signatures; schema pairing and erased resource meaning remain
explicit provider contracts. Native OS error domains remain necessary because equal numeric codes can name different
errors in different OS namespaces.

## Consequences

Provider modules own native operations and semantic conversion; `std.bytes` validates generic bounds and progress.
Ordinary buffer and file APIs retain their contracts. Invalid ranges or counts terminate execution, while lifetime,
alias, and schema violations remain unsafe contract violations. The protocol offers no escaping storage view, automatic
buffer growth, asynchronous lifetime extension, rollback, or claim of zero execution overhead.

## Related Plans

- [l1/work/plans/refactors/closed/2026-11-10-byte-buffer-range-actions-noref.md][range-plan]

## Current Docs

- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/ownership.md][ownership]
- [l1/docs/reference/filesystem.md][filesystem]
- [l1/docs/reference/design-decisions.md][design]

[design]: ../reference/design-decisions.md
[filesystem]: ../reference/filesystem.md
[ownership]: ../reference/ownership.md
[range-plan]: ../../work/plans/refactors/closed/2026-11-10-byte-buffer-range-actions-noref.md
[stdlib]: ../reference/standard-library.md
