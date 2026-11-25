# Bug Fix Plan

## Preserve explicit entry paths and retry failed module loads

- Date: 2026-11-25
- Status: In Progress (implemented, native Windows verification pending)
- Title: Preserve explicit entry paths and retry failed module loads
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: CLI target normalization, source search, and compilation-unit loading
- Modules:
  - `l0/compiler/stage1_py/l0_cli_context.py`
  - `l0/compiler/stage1_py/l0_paths.py`
  - `l0/compiler/stage1_py/l0_driver.py`
  - `l0/compiler/stage2_l0/src/source_paths.l0`
  - `l0/compiler/stage2_l0/src/l0c_lib.l0`
  - `l0/compiler/stage2_l0/src/build_driver/input.l0`
  - `l0/compiler/stage2_l0/src/driver.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_l0c_assumptions.py`
  - `l0/compiler/stage1_py/tests/driver/test_driver_paths.py`
  - `l0/compiler/stage1_py/tests/driver/test_driver_imports.py`
  - `l0/compiler/stage1_py/tests/driver/test_compilation_unit.py`
  - `l0/compiler/stage2_l0/tests/source_paths_test.l0`
  - `l0/compiler/stage2_l0/tests/driver_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
- Related:
  - [docs/specs/compiler/cli-contract.md](../../../../docs/specs/compiler/cli-contract.md)
  - [l0/docs/specs/compiler/cli-contract.md](../../../../l0/docs/specs/compiler/cli-contract.md)
  - [l0/docs/specs/compiler/stage1-contract.md](../../../../l0/docs/specs/compiler/stage1-contract.md)
- Repro: Give a system root and a project directory different `item.l0` files. Pass the absolute project file to
  `./scripts/l0c --tok -Rs <system> <project>/item.l0` from `l0/` and inspect the token marker.

## Implementation

Both stages previously reduced explicit CLI paths to module names. A competing system file could run even when the
requested entry was missing. The CLI now binds an explicit file to its entry module for token dumps, graph analysis and
native builds. Its parent participates in ordinary import resolution. Dotted targets retain ordered root search.

- Both resolvers skip directory candidates. Stage 1 returns an absolute path for a selected regular file under a
  relative root. Stage 2 can retain a relative path and reports `DRV-0011` for a regular source it cannot read.
- Stage 1 keeps direct single-file parses separate from the cache of completed import closures. It detects a cycle
  through the active load chain and retries failed closures against the filesystem.
- Stage 2 retains parsed units for diagnostic rendering and records successful closures separately. Before another
  top-level load, it releases failed units and their source-cache rows, preserving successful units in order. The
  boolean result reports the current load, while the collector retains earlier diagnostics.

## Verification

- Stage 1 focused tests passed in `test_l0c_assumptions.py`, `test_driver_paths.py`, `test_driver_imports.py`,
  `test_compilation_unit.py`, and `test_driver.py`. From `l0/`, run these modules with
  `../.venv/bin/python -m pytest -q` using the paths listed above and `compiler/stage1_py/tests/driver/test_driver.py`.
- From `l0/`, `make test-stage2 TESTS="source_paths_test driver_test l0c_build_run_test"` passed all three cases.
  Absolute and dot-relative targets selected the requested token marker and returned 23 with a competing source that
  returns 37. Repeated missing imports and cycles failed on the same driver, and repaired graphs loaded successfully.
- `make test-extended` passed on macOS Intel, including 1,688 Stage 1 tests, the Stage 2 suite, triple bootstrap,
  examples, workflow checks, and all 34 Stage 2 ARC/memory trace cases.
- Local lexical simulations exercised drive-rooted, UNC, dot-relative and mixed separators with spaces using `ntpath`
  and `PureWindowsPath` for Stage 1 and native Stage 2 target preparation with synthetic Windows strings.
- The remaining check is native Windows execution of the focused suites. Both CLI regressions exercise a mixed-separator
  target on Windows. Record that result before closure.

## ADR Impact

- Decision: Explicit source paths identify the entry file, while dotted module targets use ordered search roots.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: The shared CLI contract already specifies target identity and precedence.
- Decision: A successful module load establishes a valid transitive import graph.
  - Scope: L0
  - Disposition: Covered by ADR
  - ADR: `l0/docs/decisions/0006-module-system-and-imports.md`
  - Rationale: Retrying a load must uphold the existing module and import-cycle rules.
