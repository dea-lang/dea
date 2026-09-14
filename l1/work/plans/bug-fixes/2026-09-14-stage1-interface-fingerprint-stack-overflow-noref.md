# Bug Fix Plan

## Make Stage 1 interface fingerprint traversal stack-safe

- Date: 2026-09-14
- Status: Draft
- Title: Make Stage 1 interface fingerprint traversal stack-safe
- Kind: Bug Fix
- Severity: High
- Stage: 1
- Subsystem: Interface fingerprint type planning, emission, and cleanup
- Modules:
  - `l1/compiler/stage1_l0/src/interface_fingerprint.l0`
  - `l1/compiler/stage1_l0/src/types.l0`
  - `l1/docs/reference/architecture.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/interface_fingerprint_test.l0`
- Related:
  - [l1/docs/decisions/0019-whole-module-interface-fingerprints.md][fingerprint-adr]
  - [l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md][fingerprints]
  - [l1/work/plans/bug-fixes/closed/2026-07-26-stage1-cross-platform-ci-regressions-noref.md][cross-platform]
- Repro: Hosted Unified CI on Windows UCRT64 with Clang 22.1.7

## Summary

The Windows UCRT64/Clang Unified CI lane terminates `interface_fingerprint_test` without test output while the same
source revision passes Windows/GCC, Linux/Clang, and the other 81 L1 normal tests. The test constructs a valid
768-wrapper type to exercise the documented absence of an arbitrary interface type-depth limit. Stage 1 measures and
emits that type with native recursion, and the Clang-generated Windows frames exceed the executable's reserved stack.

Repair the implementation with explicit heap-backed traversal state. Preserve canonical bytes, tagged fingerprints,
diagnostics, ownership, and declaration ordering. Do not reduce the regression depth or increase the PE stack reserve to
hide the defect.

## ADR Impact

- Decision: Replace native recursion with explicit traversal state while preserving the existing interface fingerprint
  contract.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: ADR-0019 already fixes the canonical byte stream, two-pass size plan, fingerprint algorithm, and failure
    boundaries. This repair changes the internal traversal and cleanup mechanism so the documented unbounded-depth
    contract is actually portable; it introduces no new architectural or source-language choice.

## Current State

- The hosted Windows UCRT64/Clang job passes L0 and documentation validation, then passes 81 L1 normal tests and fails
  only `interface_fingerprint_test`. Its captured stdout/stderr block is empty, indicating abnormal process termination
  rather than a Dea assertion or fingerprint mismatch.
- The failing test creates 768 alternating pointer, nullable, slice, and array wrappers before canonicalizing, hashing,
  and freeing the resulting interface model.
- Both uploaded Windows executables reserve a 2 MiB stack. Disassembly of equivalent Stage 1 compiler functions from the
  run artifacts shows the following native frame sizes:
  - Windows Clang reserves `0x11b8` bytes (4,536 bytes) for each `ifp_measure_type` call. A 768-level chain therefore
    requires about 3.3 MiB before caller overhead.
  - Windows GCC reserves `0x698` bytes plus saved registers, about 1.3 MiB for the same depth, and passes.
  - Windows Clang reserves `0x558` bytes (1,368 bytes) for each recursive `ifp_emit_planned_type` call. The current
    fixture remains below 2 MiB in that pass, but deeper valid types retain the same failure mode.
  - Recursive `type_free` uses a much smaller frame at the current depth, but it still makes successful cleanup depend
    on native stack capacity.
- Apple Clang passes the focused test locally. This does not falsify the Windows failure because its generated frames
  and available process stack differ.

## Root Cause

`ifp_measure_type` combines validation, preorder-plan construction, child traversal, and postorder size aggregation in
one large recursive function. Generated C materializes enough branch-local state that Windows Clang 22.1.7 allocates a
4,536-byte frame. The valid 768-node wrapper chain crosses the PE stack reserve before the function can return.

`ifp_emit_planned_type` recursively follows the same type tree during the second pass even though the preorder plan
already stores every node and child payload size. `type_free` then recursively releases owned child types. These paths
contradict the stable documentation's claim that fingerprinting introduces no arbitrary type-depth limit.

The native preparation and capability-reporting changes in the tested source revision did not alter fingerprinting. The
new Windows/Clang probe exposed the older compiler-dependent recursion defect.

## Scope of This Fix

1. Make type validation and measured preorder-plan construction iterative for builtin, nominal, wrapped, array, and
   function types.
2. Make planned canonical-byte emission iterative while retaining the exact preorder stream and cached child framing.
3. Make owned `Type` tree cleanup iterative so a successfully planned deep type does not fail while being released.
4. Preserve exact pinned canonical bytes and SipHash digests, existing `SIG-0283` failures, and declaration-ordering
   behavior.
5. Keep focused deep-type coverage and validate the original Windows UCRT64/Clang configuration.

## Approach

### 1. Iterative measurement

Introduce a private measurement-frame representation that records the borrowed `Type*`, preorder plan index, traversal
phase, next function child, and partial payload size. Use a `VectorBase` work stack to perform enter/child/finish steps:

1. validate each node once on entry and append its `IfpTypePlanNode` in the current preorder;
2. visit wrapped/array children, then function parameters and result, in the existing order;
3. incorporate each completed child's checked framed size into its parent; and
4. store the completed payload size at the original plan index before popping the frame.

On validation or checked-size failure, release traversal storage and the partial plan exactly once while retaining the
current diagnostic code and message. Do not introduce a depth limit or recursively restart the traversal.

### 2. Iterative emission

Replace recursive `ifp_emit_planned_type` / `ifp_emit_nested_type_atom` descent with explicit emission frames or an
equivalent cursor-driven loop over the measured preorder plan. Emit each tag, scalar field, nested length prefix,
parameter, and result in the existing byte order. Treat plan-shape inconsistency as an internal invariant failure rather
than silently changing the public fingerprint.

The pinned whole-surface and deep-wrapper digests must remain byte-for-byte unchanged.

### 3. Iterative cleanup

Change `type_free` to release owned type trees through explicit pending-node storage. Enqueue `inner`, function
parameters, and `result` before freeing each node and its parameter container. Preserve ownership of every string and
child and keep `struct_info_free`, `enum_info_free`, signature-table cleanup, and their callers unchanged unless a
focused ownership correction is required.

Exercise success and early-failure cleanup under the existing ARC/memory trace suite. Do not add a second public type
destructor or make callers select between shallow and deep cleanup.

### 4. Regression and documentation coverage

- Retain the 768-level mixed-wrapper regression that reproduces Windows/Clang failure. Do not lower its depth based on
  one compiler's frame layout.
- Cover deeply nested function parameter and result shapes so iterative child scheduling is not limited to unary
  wrappers.
- Cover malformed deep nodes and checked-size failure to verify diagnostic and partial-plan cleanup behavior.
- Keep exact canonical stream and digest assertions for shallow and deep fixtures.
- Update the architecture reference to state that both plan construction and emission use explicit traversal state and
  that deep type cleanup does not consume proportional native stack.

## Diagnostic Codes

No new or reassigned diagnostic code is expected. Continue using `SIG-0283` for invalid interface models and checked
canonical-size overflow. Re-check the live diagnostic catalog only if implementation discovers a genuinely new
user-facing failure rather than an internal traversal invariant.

## Non-Goals

- Increasing linker stack-reserve settings, changing CI runner limits, or special-casing Clang.
- Reducing the deep regression depth or imposing a maximum interface type depth.
- Changing canonical framing, declaration ordering, SipHash inputs or keys, tagged fingerprint spelling, `.l1m` syntax,
  or dependency verification.
- Redesigning general compiler recursion outside owned `Type` cleanup and interface fingerprint traversal.
- Adding Stage 2 source-port work before that implementation exists.
- Changing the normal test runner's presentation of abnormal Windows exit statuses; that may be handled as separate
  tooling work.

## Verification Criteria

1. `make -C l1 test-stage1 TESTS=interface_fingerprint_test L0_CC=clang L1_CC=clang L1_RUNTIME_CC=clang` passes with
   unchanged pinned canonical bytes and digests.
2. The focused normal test also passes with GCC, and the focused default trace test reports zero object and string leaks
   for success, invalid-model, and size-failure paths.
3. Generated C for fingerprint measurement and emission has no self-recursive calls. Deep owned type cleanup likewise
   has no proportional native call-stack growth.
4. The L1 clean `test-all` tier passes because `type_free` is shared compiler infrastructure. Environment stackability
   and all L1 examples remain valid.
5. Staged whitespace, ADR Impact, reference-link, and root pre-commit checks pass.
6. A hosted Windows UCRT64/Clang run using the repaired source revision passes `interface_fingerprint_test`, the
   complete L1 delegate, and its default trace sweep. A local non-Windows Clang result cannot replace this platform
   gate.

## Remote Verification Gate

Hosted confirmation is a separate authorization boundary. Before pushing or dispatching verification, obtain fresh user
confirmation and show:

- the pending commit range;
- the exact push command to the public repository `https://github.com/dea-lang/dea.git` and its tracked `ci-probe`
  branch;
- the exact Unified CI workflow dispatch selecting Windows UCRT64, x86-64, and Clang; and
- the known effects: public branch mutation, CI execution, check results, logs, and short-lived diagnostic artifacts.

Do not create or alter an upstream, bypass the tracked branch with an ad hoc refspec, or treat sandbox approval as
publication authorization. Keep this plan active until hosted Windows/Clang verification passes or the user explicitly
defers that gate.

[cross-platform]: closed/2026-07-26-stage1-cross-platform-ci-regressions-noref.md
[fingerprint-adr]: ../../../docs/decisions/0019-whole-module-interface-fingerprints.md
[fingerprints]: ../features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
