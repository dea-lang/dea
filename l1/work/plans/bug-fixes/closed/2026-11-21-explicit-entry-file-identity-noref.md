# Bug Fix Plan

## Honor explicit entry files throughout L1 compilation

- Date: 2026-11-25
- Status: Completed
- Title: Honor explicit entry files throughout L1 compilation
- Kind: Bug Fix
- Severity: High
- Subsystem: CLI target preparation, source resolution, and native build orchestration
- Modules:
  - `l1/compiler/src/source_paths.l0`
  - `l1/compiler/src/l1c_lib.l0`
  - `l1/compiler/src/driver/resolve.l0`
  - `l1/compiler/src/build_driver.l0`
  - `l1/compiler/src/link_driver/build.l0`
- Test modules:
  - `l1/compiler/tests/source_paths_test.l0`
  - `l1/compiler/tests/l1c_lib_test.l0`
  - `l1/compiler/tests/l1c_build_run_multi_cu_test.py`
- Related:
  - [docs/specs/compiler/cli-contract.md][cli]
  - [l0/work/plans/bug-fixes/closed/2026-11-21-stage1-entry-paths-and-import-cache-noref.md][l0-paths]
- Repro: From a project directory, run `l1c --tok -Rs SYSTEM ./item.l1` and `l1c --run -Rs SYSTEM ./item.l1` with
  different `item.l1` files in the project and system directories.

## Findings and implementation

A system root containing its own `item.l1` could change which program an explicit path ran. The original reproducer
returned 0 when run alone and 37 with the competing module present. Even a missing file could select the system copy.
Both the frontend and native driver discarded the selected path when deriving the entry module name.

All source-taking commands now share input preparation. A path operand binds the entry name to an absolute path from the
invocation directory and adds its parent to the project roots for imports. Direct token reads, dependency discovery, and
per-module native reanalysis use this binding. Missing or unreadable entries report the selected file. Dotted module
names and bare filenames retain normal source lookup, and imported interfaces retain their configured priority.

## ADR Impact

- Decision: An explicit file operand selects the source entry, while imports use the configured resolution policy.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: The shared CLI contract already distinguishes file operands from dotted module operands. L1 needs to
    preserve the selected entry across its own compilation phases.

## Regression coverage

The multi-CU fixture places different `item.l1` programs under system and project roots containing spaces. Absolute and
dot-relative entry paths produce the project token markers in both token modes, generate the project function, and
return 23 from the native program. Dependency discovery identifies the entry and its sibling import by filesystem
identity. A separate native run selects the sibling's compiled interface even when its source and a competing entry
interface are invalid. Dotted names and bare filenames still select the system copy.

Missing files, unreadable files and mismatched declarations exercise their existing diagnostics. A missing explicit
`dea.l1` also fails, while an existing one conflicts with the compiler-owned virtual module. The fixture covers a POSIX
directory alias ending in a literal backslash and includes a mixed-separator operand on Windows.

## Verification

On macOS with Apple Clang 17, all seven focused cases passed from `l1/`:

```sh
make test-compiler TESTS="source_paths_test l1c_lib_test l1c_build_run_multi_cu_test driver_test module_graph_test l1c_dependency_discovery_test l1c_compile_only_test"
```

Run `make test-compiler-trace TESTS="source_paths_test l1c_lib_test"` to check object and string ownership during source
lookup and CLI input cleanup.

A separate Windows lexical check covered drive and UNC roots, mixed separators, spaces, and a distinct shadow path.
Native Windows execution remains unverified locally.

[cli]: ../../../../../docs/specs/compiler/cli-contract.md#5-target-and-source-path-rules
[l0-paths]: ../../../../../l0/work/plans/bug-fixes/closed/2026-11-21-stage1-entry-paths-and-import-cache-noref.md
