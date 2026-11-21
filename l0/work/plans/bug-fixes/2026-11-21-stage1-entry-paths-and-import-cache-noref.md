# Bug Fix Plan

## Preserve explicit entry paths and retry failed module loads

- Date: 2026-11-21
- Status: Draft
- Title: Preserve explicit entry paths and retry failed module loads
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: CLI target normalization, source search, and compilation-unit loading
- Modules:
  - `l0/compiler/stage1_py/l0_cli_context.py`
  - `l0/compiler/stage1_py/l0_cli_commands.py`
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

## Summary

Both stages can execute a different file from the explicit CLI operand. In the native Stage 2 probe, the requested file
returned 0 alone. With a competing system root, absolute, dot-relative and explicitly missing paths all ran the system
file and returned 37. A directory named `thing.l0` also hid the next root's source and produced `DRV-0011`. The
absolute-result guarantee belongs to the Stage 1 Python resolver. Stage 2 documents the first matching source path and
successfully loads relative results.

Both loaders also cache failures. On a single Stage 2 `DriverState`, `dr_load_module` returned false, then true, for
both a missing import and a cycle. The original error remained in the collector. A fresh CLI process cannot expose this
false cache hit.

## Fixes and regression tests

1. **Explicit entry identity.** Classify the original target spelling before constructing a host `Path`, which can
   discard a leading `./`. Carry the selected file into token dumping (including `--all-modules`) and the
   compilation-unit loader used by analysis and generation. Keep its parent available for import resolution. Give two
   same-named files different declarations and results. With the competing system root first, verify that absolute and
   `./` targets dump the requested marker and execute the requested result. An explicitly missing file must fail even
   when another root has its basename. On Stage 2 carry the explicit path through both CLI and build-driver input
   preparation and into the graph loader. Run the marker and exit-value fixtures through the native launcher. Exercise a
   dotted target and a sibling import separately to verify root precedence and entry-parent handling.
2. **Directory shadowing.** Accept a candidate when it is a file. Put a directory named `thing.l0` in the first root and
   a module file of that name in the next. Assert filesystem identity with the latter. With only the directory
   available, assert the Stage 1 missing-module exception and the Stage 2 driver's `DRV-0010`. Apply the file-kind check
   in both Stage 2 root groups. Preserve `DRV-0011` when a selected regular source cannot be read. Strengthen the
   existing system-before-project test with distinct file contents or file identity.
3. **Absolute results (Stage 1).** Honor the documented `SourceSearchPaths.resolve` return contract even for relative
   roots. Assert both `is_absolute()` and identity with the selected file for relative system and project roots
   containing spaces. For Stage 2 assert that `sp_resolve` selects the intended file under a relative root containing
   spaces.
4. **Cache after failure.** Separate in-progress cycle detection, parsed files, and successfully loaded import closures.
   Inspect both cache writes in `load_module` and `_parse_source`; preserve the direct single-file parser's cache
   contract. On one driver, call `load_module` twice with a missing dependency and build the same cyclic compilation
   unit twice. Each attempt must raise the original exception. Repair the fixture, retry on that driver, and assert the
   complete module set. Include a successful diamond import as the reuse control. In Stage 2, `dr_mark_loaded` runs even
   when a child fails. Register successful closures only, and handle pending parsed units so a retry cannot duplicate or
   reuse a failed unit. In `driver_test`, reuse one state per fixture: require two false returns and the appropriate
   `DRV-0010` or `DRV-0030`. Check the boolean independently of the retained diagnostics. Repair the dependency and
   require a successful reload with one unit per module.

## Verification

Run the four listed pytest modules from `l0/` with `../.venv/bin/python -m pytest -q` and their level-relative paths.
Run `make test-stage2 TESTS="source_paths_test driver_test l0c_build_run_test"` there. Assert exit status and marker
contents independently of path rendering. Exercise native POSIX and Windows path spellings on their respective hosts,
including mixed separators on Windows. Identify any `PureWindowsPath` cases as simulation. Keep existing missing-file
and cycle diagnostic meanings (`DRV-0010`, `DRV-0030`) and token-mode resolution diagnostics. These fixes need no new
diagnostic code.

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
