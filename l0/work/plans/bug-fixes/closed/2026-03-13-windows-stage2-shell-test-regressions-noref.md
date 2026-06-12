# Bug Fix Plan

## Windows Stage 2 shell test regressions after path-handling fixes

- Date: 2026-03-13
- Status: Implemented
- Title: Fix remaining Windows CI Stage 2 test failures caused by missing `.cmd` wrapper `L0_HOME`, `/tmp` path mapping,
  and missing `win32` platform handling
- Kind: Bug Fix
- Severity: High (6 of 41 Stage 2 tests fail on Windows CI; blocks `test-all-windows`)
- Stage: 2
- Subsystem: Driver / build tooling / test infrastructure
- Modules:
  - `scripts/dist_tools_lib.py`
  - `compiler/stage2_l0/tests/l0c_codegen_test.sh`
  - `compiler/stage2_l0/tests/l0c_build_run_test.sh`
  - `compiler/stage2_l0/tests/l0c_stage2_bootstrap_test.sh`
  - `compiler/stage2_l0/tests/l0c_stage2_verbose_output_test.sh`
  - `compiler/stage2_l0/tests/l0c_stage2_install_prefix_test.sh`
  - `compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py`
- Test modules:
  - (the failing tests are themselves the affected modules)
- Repro: `make test-stage2` on Windows CI (`msys2/MINGW64`, MinGW-w64 GCC, `.venv/Scripts/python.exe`)

## Summary

After the initial Windows path-handling fixes for Stage 2 shell tests, the Windows CI (`test-all-windows`) still fails 6
of 41 Stage 2 tests. Four distinct root causes remain.

## Root Cause 1: Windows `.cmd` wrapper does not set `L0_HOME`

`render_stage2_cmd_wrapper()` in `scripts/dist_tools_lib.py` (line 553) generates a minimal batch wrapper:

```batch
@echo off
"%~dp0l0c-stage2.native" %*
```

The POSIX shell wrapper (`render_stage2_wrapper()`, line 536) derives `repo_root` from its own location and sets
`L0_HOME="${repo_root}/compiler"`. The `.cmd` wrapper does nothing equivalent.

Tests that use `clean_env_run` (which strips the environment with `env -i`, preserving only `PATH`, `SYSTEMROOT`,
`COMSPEC`, `WINDIR`) lose `L0_HOME`. The `.cmd` wrapper does not re-derive it, so `l0c-stage2.native` cannot resolve
stdlib modules.

**Failing tests:**

- `l0c_stage2_bootstrap_test.sh` — `[DRV-0010] Module 'std.io' not found` at line 118
- `l0c_stage2_verbose_output_test.sh` — `FAIL: -v --build should succeed` at line 100
- `l0c_stage2_install_prefix_test.sh` — version mismatch at line 166

## Root Cause 2: Triple bootstrap test has no `win32` platform branch

`deterministic_linker_flags()` in `l0c_triple_bootstrap_test.py` (line 160) only handles `sys.platform == "darwin"` and
`sys.platform.startswith("linux")`. On the Windows CI, Python is a native Windows Python from
`.venv/Scripts/python.exe`, so `sys.platform == "win32"`. The function raises `TripleBootstrapFailure` immediately.

**Failing test:** `l0c_triple_bootstrap_test.py`

## Root Cause 3: MSYS2 `/tmp` vs Windows native path mapping divergence

Multiple tests create temp directories under MSYS2 `/tmp/` using `mktemp -d /tmp/...`, then use `native_path`
(`cygpath -w`) to convert paths for Windows Python, then use the original MSYS2 paths with MSYS2 tools (`diff`, `grep`,
`cmp`). If MSYS2's `/tmp` mount and `cygpath -w /tmp` resolve to different Windows directories, Python writes files at
one location while MSYS2 tools look at another.

The codegen test demonstrates this clearly: the `normalize_text_file` function passes `native_path`-converted paths to
Windows Python (which creates files at the Windows path), but `diff` on line 170 uses the original MSYS2 paths and
reports `No such file or directory` for all `.normalized.c` files.

The earlier Windows path-handling fix already applied this change for internal L0 tests (moving from `/tmp/` to
repo-local `build/` paths). The verbose output test (`l0c_stage2_verbose_output_test.sh` line 12) also already uses
`$REPO_ROOT/build/...`. The remaining shell tests still use `/tmp/`.

**Failing tests:** `l0c_codegen_test.sh`, `l0c_build_run_test.sh` (primary); others as secondary contributor

## Root Cause 4: Symlink assertion on Windows

`l0c_stage2_install_prefix_test.sh` line 147 asserts POSIX symlinks (`assert_symlink_target`). Windows does not support
POSIX symlinks by default; `write_relative_symlink()` in `dist_tools_lib.py` calls `path.symlink_to()` which may fail or
produce a different link type. This is a secondary contributor after RC1.

## Planned Fix

### Fix 1: `.cmd` wrapper `L0_HOME` derivation (RC1)

Update `render_stage2_cmd_wrapper()` in `dist_tools_lib.py` to derive and set `L0_HOME` from `%~dp0`, mirroring the
POSIX wrapper logic. Two `.cmd` templates are needed:

- **Repo-local:** derive `REPO_ROOT` from `%~dp0` using the same relative path as the POSIX wrapper, then set
  `L0_HOME=%REPO_ROOT%\compiler`.
- **Prefix:** derive `PREFIX_ROOT` from `%~dp0\..`, then set `L0_HOME=%PREFIX_ROOT%`.

This matches the existing split between `render_stage2_wrapper` / `render_prefix_stage2_wrapper` for POSIX.

### Fix 2: Move shell test temp files to repo-local paths (RC3)

Replace `mktemp -d /tmp/...` and `/tmp/...` temp file paths with repo-local paths under `$REPO_ROOT/build/tests/...` in:

- `l0c_codegen_test.sh` (line 13: `ARTIFACT_DIR`)
- `l0c_build_run_test.sh` (line 12: `WORK_DIR`)
- `l0c_stage2_bootstrap_test.sh` (lines 15-22: multiple temp files)
- `l0c_stage2_install_prefix_test.sh` (lines 11-22: `PREFIX_DIR`, `PROJECT_DIR`, temp files)

This follows the pattern already established by `l0c_stage2_verbose_output_test.sh` and the earlier internal L0 test
path-handling fix.

### Fix 3: Add `win32` platform support to triple bootstrap (RC2)

Add a `sys.platform == "win32"` branch to `deterministic_linker_flags()`. MinGW-w64 uses GNU ld which supports
`--build-id=none`. If PE timestamps or other non-determinism prevents byte-identical native binaries, skip the native
comparison on Windows (as is done for tcc) and only verify retained-C identity.

Also verify that `normalized_native_artifact()` (line 309) handles the non-Linux case, since it currently only strips on
Linux.

### Fix 4: Adapt symlink assertion for Windows (RC4)

Either skip `assert_symlink_target` on Windows or replace the POSIX symlink with a `.cmd` forwarder. This depends on
whether `write_relative_symlink()` already handles Windows gracefully; if it falls back to a copy or junction, the
assertion needs to match.

## Verification

```bash
make test-stage2                             # local sanity (macOS/Linux)
make DEA_BUILD_DIR=build/dev-dea test-stage2 # full Stage 2 suite
make DEA_BUILD_DIR=build/dev-dea triple-test # triple bootstrap
make docker CMD=test-all                     # Linux regression
# Push and verify Windows CI passes
```

## Assumptions

- MSYS2 `/tmp` path mapping divergence is the cause of the codegen test `No such file or directory` failures. Using
  repo-local paths avoids the mapping entirely.
- MinGW-w64 GNU ld supports `--build-id=none`. If Windows PE binaries are inherently non-deterministic, the native
  comparison should be skipped rather than the entire triple bootstrap test.
- The `.cmd` wrapper `L0_HOME` derivation uses `for %%I in ("%~dp0\..\..\..") do set "REPO_ROOT=%%~fI"` or equivalent
  batch relative-path resolution, which is standard cmd.exe behavior.
