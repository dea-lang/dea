# Bug Fix Plan

## Reject borrowed slices whose backing expires before their destination

- Date: 2026-10-29
- Status: Completed
- Title: Reject accidental borrowed-slice escapes in L1
- Kind: Bug Fix
- Severity: High
- Subsystem: Compiler / semantic analysis / borrowed slices
- Modules:
  - `l1/compiler/src/analysis.l0`
  - `l1/compiler/src/slice_lifetimes.l0`
  - `l1/compiler/src/signatures/`
  - `l1/compiler/src/type_resolve/`
- Test modules:
  - `l1/compiler/tests/slice_lifetimes_test.l0`
  - `l1/compiler/tests/interface_replay_test.l0`
  - `l1/compiler/tests/slice_trace_test.l0`
- Repro: `make -C l1 test-compiler TESTS="slice_lifetimes_test interface_replay_test slice_trace_test"`

## Current State and Root Cause

Before correction, L1 accepted a slice of an inner-block array assigned to an outer variable; generated L1 C retained a
pointer after the array's lifetime ends. Reproductions also cover copied aliases, temporary arrays, aggregate fields,
writes into caller-owned descriptor arrays, and nullable/pointer wrappers around arrays of slices. Existing signature
checks rejected direct escapes but provided no local backing-lifetime analysis and did not consistently inspect
wrappers. The correction and required native compiler validation are complete.

## Selected Contract

Backing storage must outlive the destination binding or storage. Reject shorter-lived stores even when later code would
restore the destination before scope exit. Preserve aliases whose actual backing has an enclosing lifetime. Apply the
same restrictions through composite types and interfaces. Keep descriptor layout, bounds checks, and explicit
raw-pointer lifetime contracts; do not introduce implicit copies, promotion, or escaping owned slices.

## Implementation

L1 runs lifetime validation after successful typing. Resolved binding identities and lexical scope ancestry preserve
direct aliases and subobjects. Reachable control-flow joins, loop fixed points, iteration temporaries, early nullable
propagation, and every registered `with` cleanup contribute to the transfer proof. Invalid or unprovable stores fail
before C emission. Caller-owned destinations require a compatible caller origin rather than the weaker guarantee
sufficient for local storage.

Every descriptor-array store must preserve containment, including stores through aliases. Reads conservatively use the
containing storage's lifetime, rather than assuming an element's previous origin survives alias mutation. Source and
interface type validation follows arrays, nullable/pointer wrappers and resolved aliases, while preserving legal
callable slice parameters.

Nullable unwrap/try carriers copy payloads without owning them. Borrowing ARC array elements from such a carrier is
unprovable if replacing the original carrier can release its elements. An explicit owning array binding followed by a
borrow remains legal; the checker does not insert that copy.

## Diagnostic-Code Planning

The live catalog was rechecked before assigning unused `TYP-0818` to invalid or unprovable L1 slice lifetime transfers.
Existing `TYP-0810` and `TYP-0814` cover result escapes and wrapper containment.

## Verification

The 37 negative source fixtures cover all reproductions, aliases, shadowing, branches, loops, cleanup, nested
descriptors and wrappers; interface replay adds imported wrapper cases. Analysis positives preserve same-scope
borrowing, outer-backed inner aliases, parameters, subslicing, variadic packs, fixed-array value copies and unreachable
branches.

Hosted `Unified CI` verification on 2026-10-29 passed `make -C l1 test-ci` on all four native platforms. Each platform
passed 100 normal compiler cases including CI-only cases, 51 canonical trace cases, and five child trace fixtures, plus
the environment/bootstrap, examples, tooling, and productization fixture gates. The slice lifetime and target trace
regressions passed with zero leaked objects or strings. Each environment selected the following compiler for `L0_CC`,
`L1_CC`, and `L1_RUNTIME_CC`:

| Platform       | Compiler executable | Version                                 |
| -------------- | ------------------- | --------------------------------------- |
| Linux x86_64   | `/usr/bin/gcc`      | GCC 15.2.0 (Ubuntu 15.2.0-16ubuntu1)    |
| macOS Intel    | `/usr/bin/clang`    | Apple Clang 17.0.0 (clang-1700.0.13.5)  |
| macOS ARM      | `/usr/bin/clang`    | Apple Clang 21.0.0 (clang-2100.1.1.101) |
| Windows UCRT64 | `/ucrt64/bin/gcc`   | GCC 16.2.0 (MSYS2 Rev4)                 |

The `l1-docs-validation / validate-docs` check passed strict reference generation with full PDF and verified bundle;
`ADR impact policy` also passed. These results cover the delivered code, tests, build configuration, and dependencies.
Fresh artifact acceptance remains a separate stabilization gate.

Focused local evidence:

- Native macOS Intel, `/usr/bin/clang`, Apple Clang 17.0.0: `make test-extended` passed 92 normal compiler cases, four
  examples, six Docker/Wine runner tests, 183 tooling tests (one skipped), and 289 productization fixture tests (14
  skipped).
- The same host passed
  `make test-compiler-trace TESTS="slice_lifetimes_test expr_types_test interface_replay_test locals_test backend_test slice_trace_test"`:
  six cases, zero leaked objects or strings.
- Linux x86_64 in the existing repository-owned `l1-test` container, `/usr/bin/gcc`, Debian GCC 12.2.0:
  `make test-compiler` and `make test-compiler-trace` with the same six selectors passed. The container used copied
  current sources, a read-only checkout mount, and no network.
- All 37 negative fixtures independently failed `l1c --gen` with the expected `TYP-0818`, `TYP-0814`, or `TYP-0810` and
  no generated C output.
- The actual L1 `slice_trace_main` program built with `--trace-arc --trace-memory`, exited successfully, and
  independently passed `compiler/scripts/check_trace_log.py`: 42 events, zero errors or warnings. It exercises
  ARC-bearing aliases, array copies, temporary arrays, cleanup and explicit owning nullable extraction.

The broader `slice_lifetime_ok` fixture is an analysis regression, not runtime acceptance: its nested descriptor arrays
and aggregate callable/array fields expose existing generated-C declaration-order failures. The unchanged ordering
implementation and the earlier finding in
[work/plans/bug-fixes/closed/2026-09-11-shared-arc-comparison-temporary-cleanup-noref.md][arc-cleanup] distinguish this
limitation from the lifetime correction. The dedicated ARC target supplies successful runtime evidence without claiming
those separate backend defects are fixed.

## ADR Impact

- Decision: Require L1 slice backing to outlive destination storage with conservative proof of transfers.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0015-slice-types-and-intrinsics.md`
  - Rationale: This corrects enforcement of the existing non-owning slice boundary without adding owned slices or
    changing the ABI.

## References

[arc-cleanup]: ../../../../../work/plans/bug-fixes/closed/2026-09-11-shared-arc-comparison-temporary-cleanup-noref.md
