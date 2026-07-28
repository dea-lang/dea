# Bug Fix Plan

## Harden verified standalone linking

- Date: 2026-07-28
- Status: Completed
- Title: Harden the Stage 1 verified standalone-link boundary
- Kind: Bug Fix
- Severity: High
- Stage: 1
- Parent Initiative: [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative]
- Roadmap: [`l1/docs/roadmap.md`][roadmap]
- Subsystem: Object inspection / standalone link validation / lifecycle ordering / Windows host transport
- Modules:
  - `l1/compiler/stage1_l0/src/object_reader_types.l0`
  - `l1/compiler/stage1_l0/src/object_reader.l0`
  - `l1/compiler/stage1_l0/src/object_reader_elf.l0`
  - `l1/compiler/stage1_l0/src/object_reader_macho.l0`
  - `l1/compiler/stage1_l0/src/object_reader_pecoff.l0`
  - `l1/compiler/stage1_l0/src/link_driver.l0`
- Test modules:
  - `l1/compiler/stage1_l0/tests/object_reader_test.l0`
  - `l1/compiler/stage1_l0/tests/link_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_link_set_test.py`
  - `l1/compiler/stage1_l0/tests/fixtures/separate_compilation`
- Related:
  - [`l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md`][link-set]
  - [`l1/docs/decisions/0021-portable-object-metadata-and-inspection.md`][inspection-adr]
  - [`l1/docs/decisions/0028-verified-link-set-and-foreign-object-boundary.md`][link-set-adr]
  - [`l1/docs/decisions/0029-output-local-standalone-link-transaction.md`][transaction-adr]
  - [`l1/work/plans/features/2026-04-24-external-library-linking-cli-noref.md`][external-linking]
  - [`docs/specs/compiler/diagnostic-code-catalog.md`][diagnostic-catalog]
- Repro: `make -C l1 test-stage1 TESTS="object_reader_test link_driver_test l1c_stage1_link_set_test.py"`

## Summary

The verified standalone-link implementation accepts object-embedded linker directives that can add hidden libraries or
alter process-link behavior, applies child-argument quoting to values parsed first by `cmd.exe`, traverses dependency
graphs recursively, and lacks end-to-end proof for lifecycle ordering and Windows reparse-point output rejection. This
plan closes those gaps without adding native process spawning or changing the public link-mode syntax.

## Root Cause

The format-neutral object inspection result records symbols and Dea metadata but not linker-control carriers recognized
by host linkers. The Windows transport excludes environment expansion markers but still permits a literal quote that can
terminate the generated shell quoting. Lifecycle planning mirrors recursive depth-first pseudocode directly in the
self-hosted compiler. Wrapper-object validation checks metadata and `main` but not whether user-controlled C options
made the compiler embed a final-link directive. Rejected Windows values are also copied verbatim into diagnostics, so a
blocked line break can still spoof diagnostic output. Finally, the integration fixtures use no observable deferred state
and skip output aliases on Windows.

## Scope of This Fix

1. Mark ELF dependent-library sections, Mach-O `LC_LINKER_OPTION` commands, and PE/COFF `.drectve` sections (including
   bounded decimal and LLVM base-64 string-table name indirections) during object inspection, then reject either Dea or
   foreign operands carrying those controls before scratch allocation. Apply the same inspection to the generated
   wrapper before final host linking.
2. Reject literal quotes in addition to percent, exclamation, carriage-return, and line-feed bytes throughout the
   Windows `system()` command boundary. Validate parsed wrapper-option words plus command redirection paths, and escape
   rejected diagnostic values.
3. Replace recursive dependency traversal with explicit depth-first frames while preserving deterministic lifecycle
   order and canonical cycle diagnostics.
4. Exercise deferred initialization, side-effect-only imports, reverse finalization, and trace cleanup through a linked
   multi-object executable.
5. Exercise final-output reparse-point rejection through a real Windows junction instead of skipping the case.
6. Add the dedicated `L1C-2110` embedded-linker-control diagnostic, subject to implementation-time catalog re-check.

## Non-Goals

- Adding a native subprocess API or changing other compiler modes from `system()` execution.
- Adding external-library, linker-argument, or per-object directive allowlist syntax.
- Adding a dependency-graph depth limit.
- Establishing end-to-end MSVC linking or changing the supported MinGW/GCC-family lane.
- Changing executable publication, rollback, or trusted output-parent semantics.

## ADR Impact

- Decision: Normalize recognized embedded linker-control carriers in the bounded format-neutral object inspection API.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0021-portable-object-metadata-and-inspection.md`
  - Rationale: ADR-0021 owns the portable reader output and must include the additional non-payload control
    classification consumed by standalone linking.
- Decision: Treat absence of format-recognized embedded linker controls as part of every verified standalone-link input.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0028-verified-link-set-and-foreign-object-boundary.md`
  - Rationale: ADR-0028 records the typed input boundary, including that hidden linker-option carriers cannot bypass the
    explicit external-library surface, in the same cohesive change.
- Decision: Reject quote-bearing and expansion-bearing Windows command values until standalone linking has native
  process spawning.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0029-output-local-standalone-link-transaction.md`
  - Rationale: ADR-0029 records the output-local transaction and its pre-allocation Windows command-transport validation
    in the same cohesive change.

## Implementation

1. Extend object containers with one normalized linker-control kind and make each format adapter set it without parsing
   or exposing untrusted directive payloads. Resolve the standard PE/COFF indirect section-name encodings before the
   `.drectve` comparison.
2. Reject any non-empty linker-control kind with `L1C-2110` during input classification, before module registration,
   graph validation, compiler discovery, or transaction allocation, and reject a directive-bearing generated wrapper
   before the final host link.
3. Make the Windows safety predicate reject `"`, validate the exact split compiler-option words, and revalidate command
   words plus stdout/stderr paths at the execution boundary. Render rejected C0 bytes as hexadecimal escapes in
   diagnostics.
4. Use an owned vector of visit frames containing the current input and next ordered-import index. Keep the canonical
   module-name stack synchronized with frame push/pop operations.
5. Add multi-module lifecycle fixtures backed by a foreign observer and trace-located top-level ARC state. Add
   platform-native embedded-control and Windows junction regressions.
6. Create or amend the accepted ADRs and update current CLI, architecture, separate-compilation, and diagnostic
   references.

## Verification Criteria

1. Ordinary ELF, Mach-O, and PE/COFF objects remain directive-free; each recognized carrier, including direct and
   indirect PE/COFF directive names, is reported through the normalized inspection query.
2. Directive-bearing Dea and foreign operands both fail with `L1C-2110` before a transaction exists, and the host linker
   is not invoked.
3. C options that make the wrapper compiler emit a recognized linker control fail with `L1C-2110` before the final host
   link.
4. Windows quote-plus-metacharacter input fails before scratch allocation and cannot create an injection sentinel;
   rejected line breaks cannot inject diagnostic lines, and a real compiler executable reached through a path containing
   spaces still links successfully.
5. A 10,000-module chain validates without native-stack recursion, retains dependency-first ordering, and the existing
   canonical cycle diagnostic remains exact.
6. The linked lifecycle fixture observes leaf, provider, side-effect-only, and entry initialization in order; traced
   finalization releases module state in exact reverse and reports no leaks.
7. A Windows junction at the final output is rejected with `L1C-2105`, remains present, and its target is unchanged.
8. Focused normal and trace suites pass, followed by the full L1 validation tier selected from the final diff.
9. ADR-impact checks, architectural audit, staged whitespace, and pre-commit pass before closure.

## Completion Notes

- Added bounded, payload-free recognition for ELF dependent-library sections, Mach-O linker-option commands, and direct
  or string-table-indirect PE/COFF directive sections.
- Rejected controls in either typed operand role before module registration and in the generated wrapper before final
  host linking.
- Replaced recursive graph traversal with explicit owned DFS frames and proved a 10,000-module chain.
- Hardened Windows exact-word transport, single-line rejection diagnostics, spaced compiler execution, and final-output
  junction handling.
- Added native ELF, Mach-O, and PE/COFF carrier fixtures plus observable lifecycle initialization, reverse ARC
  finalization, and zero-leak trace coverage.
- Validation:
  - `make -C l1 test-stage1 TESTS="object_reader_test"`: passed 1/1.
  - `make -C l1 test-stage1-trace TESTS="object_reader_test"`: passed 1/1.
  - `make -C l1 test-stage1 TESTS="link_driver_test build_driver_test wrapper_emitter_test l1c_stage1_link_set_test.py compiler_filesystem_support_test.py"`:
    passed 5/5.
  - `make -C l1 test-stage1-trace TESTS="link_driver_test"`: passed 1/1.
  - `make -C l1 clean test-all`: passed 64/64 normal Stage 1 tests, environment stackability, 4/4 examples, and 44/44
    dedicated trace tests.
  - `python scripts/check_adr_impact.py --all-active`: passed before closure.
  - `python scripts/validate_architectural_decision_audit.py --json`: passed with all 47 ADR index entries verified and
    no unresolved candidates.
  - `git diff --check` and Python syntax checks: passed.
  - Unified CI passed the complete L1 delegate on Ubuntu, Windows UCRT64, macOS Intel, and macOS ARM, including the
    spaced compiler-path and output-junction regressions on Windows.

[diagnostic-catalog]: ../../../../../docs/specs/compiler/diagnostic-code-catalog.md
[external-linking]: ../../features/2026-04-24-external-library-linking-cli-noref.md
[initiative]: ../../../initiatives/0001-separate-compilation-and-linking.md
[inspection-adr]: ../../../../docs/decisions/0021-portable-object-metadata-and-inspection.md
[link-set]: ../../features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md
[link-set-adr]: ../../../../docs/decisions/0028-verified-link-set-and-foreign-object-boundary.md
[roadmap]: ../../../../docs/roadmap.md
[transaction-adr]: ../../../../docs/decisions/0029-output-local-standalone-link-transaction.md
