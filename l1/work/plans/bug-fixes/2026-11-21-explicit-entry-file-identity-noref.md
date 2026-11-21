# Bug Fix Plan

## Honor explicit entry files throughout L1 compilation

- Date: 2026-11-21
- Status: Draft
- Title: Honor explicit entry files throughout L1 compilation
- Kind: Bug Fix
- Severity: High
- Subsystem: CLI target preparation, source resolution, and native build orchestration
- Modules:
  - `l1/compiler/src/source_paths.l0`
  - `l1/compiler/src/l1c_lib.l0`
  - `l1/compiler/src/driver/resolve.l0`
  - `l1/compiler/src/build_driver.l0`
  - `l1/compiler/src/link_driver/workspace.l0`
- Test modules:
  - `l1/compiler/tests/source_paths_test.l0`
  - `l1/compiler/tests/l1c_lib_test.l0`
  - `l1/compiler/tests/l1c_build_run_multi_cu_test.py`
- Related:
  - [docs/specs/compiler/cli-contract.md][cli]
  - [l0/work/plans/bug-fixes/2026-11-21-stage1-entry-paths-and-import-cache-noref.md][l0-paths]
- Repro: From a project directory, run `l1c --tok -Rs SYSTEM ./item.l1` and `l1c --run -Rs SYSTEM ./item.l1` with
  different `item.l1` files in the project and system directories.

## Summary

The requested entry returned 0 when run alone. With a competing system module, absolute and dot-relative targets both
dumped the competing declaration and returned 37. Even a nonexistent explicit path ran the competing program. This can
silently validate or execute the wrong source. Target normalization retains the module name and adds a project search
root, allowing subsequent lookups of the entry to select another file.

## ADR Impact

- Decision: An explicit file operand selects the source entry, while imports use the configured resolution policy.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: The shared CLI contract already distinguishes file operands from dotted module operands. L1 needs to
    preserve the selected entry across its own compilation phases.

## Fix and regression criteria

1. Preserve the explicit entry path alongside the canonical module name from target preparation through direct token
   reads, graph resolution and per-module build/run work. Use the original working directory for a relative target
   across workspace transitions. Validate the module declaration against the expected name.
2. Resolve the entry from that path and retain its parent for imports. Keep ordinary dotted-module search, ordered
   source roots and authoritative imported interfaces on their existing paths. This fix is independent of which
   non-regular candidates a dotted source lookup should skip.
3. Give the two files distinct token markers and return values. For both absolute and `./` spellings, assert the
   requested marker under `--tok` and `--tok --all-modules`, the requested value under `--run`, and consistent source
   selection through analysis and generated C. An explicitly missing entry must fail even when its basename exists
   elsewhere. Exercise a declared-name mismatch and a sibling import. Use a dotted target as the precedence control.
   Compare native paths portably and exercise directories containing spaces.

From `l1/`, run `make test-compiler TESTS="source_paths_test l1c_lib_test l1c_build_run_multi_cu_test"`. Use the
registered missing-source, read-error and module-name-mismatch diagnostics on their respective paths.

[cli]: ../../../../docs/specs/compiler/cli-contract.md#5-target-and-source-path-rules
[l0-paths]: ../../../../l0/work/plans/bug-fixes/2026-11-21-stage1-entry-paths-and-import-cache-noref.md
