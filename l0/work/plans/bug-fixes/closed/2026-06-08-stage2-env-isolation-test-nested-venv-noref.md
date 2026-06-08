# Bug Fix Plan

## Remove redundant nested `make venv` from the Stage 2 env-isolation test

- Date: 2026-06-08
- Status: Completed
- Title: Fix flaky Windows CI failure in the L0 Stage 2 env-isolation test caused by a redundant nested `make venv`
- Kind: Bug Fix
- Severity: Medium
- Stage: Stage 2
- Subsystem: Stage 2 integration-test harness / Windows CI
- Modules:
  - `l0/compiler/stage2_l0/tests/l0c_stage2_test_env_isolation_test.py`
- Test modules:
  - `l0/compiler/stage2_l0/tests/l0c_stage2_test_env_isolation_test.py`
- Related:
  - `l0/work/plans/bug-fixes/closed/2026-04-21-fix-windows-ci-stage2-regression.md`
- Repro: Windows-only, intermittent; CI `make -C l0 test-stage2` under MSYS2 UCRT64.

## Summary

`l0c_stage2_test_env_isolation_test.py` intermittently fails on the Windows leg of Unified CI while bootstrapping its
build. It ran a nested `make venv DEA_BUILD_DIR=... install-dev-stage2`; because `.venv` already exists by that point,
the nested `make venv` re-enters the `uv sync` branch and tries to spawn the native `x86_64-pc-windows-gnu` `uv` from
MSYS2 `sh`. That spawn failed with `Windows error: The parameter is incorrect.` (Win32 `ERROR_INVALID_PARAMETER`), and
make reported `Makefile:64: venv` `Error 127`, so the test never reached `install-dev-stage2`.

## Root Cause

The nested `make venv` is redundant and the only ingredient that fails:

- `.venv` is already created and synced once per L0 suite via the `test-stage2: install-dev-stage2 | venv` order-only
  prerequisite. The top-level `make venv` and `install-dev-stage2` both succeeded on the failing job.
- `install-dev-stage2` depends only on `$(PYTHON)` (the venv python), not on the `venv` target, and the `DEA_BUILD_DIR=`
  override is meaningless to `venv`.
- The failure is intermittent MSYS2 fork/exec flakiness, not a regression: on 2026-05-22 this exact test passed on
  Windows in 76.9s with the identical `uv 0.10.12 (x86_64-pc-windows-gnu)`.

The sibling `l0c_stage2_install_prefix_test.py` runs `make ... install` nested through the same `run()` helper (captured
pipes, `stdin=DEVNULL`) without nesting `venv`, and passes. So nested make spawning a native child works under MSYS2;
only the redundant `uv sync` spawn is fragile.

## Scope of This Fix

Drop the redundant `venv` target from the test's make invocation:

```python
# before
run(["make", "venv", f"DEA_BUILD_DIR={dist_dir_rel}", "install-dev-stage2"])
# after
run(["make", f"DEA_BUILD_DIR={dist_dir_rel}", "install-dev-stage2"])
```

This aligns the test with `install_prefix_test`, removes a genuinely flaky redundant step, and is faster.

## Non-Goals

- No change to the root or L0 `venv` targets; the existing `uv sync` / `UV_PROJECT_ENVIRONMENT` / `cygpath -w` logic is
  correct.
- No broad Makefile-level mitigation of MSYS2 nested-spawn fragility. Treat nested `make venv` under captured-pipe
  subprocesses on Windows as a known limitation.

## Verification

- Local (macOS/Linux): `cd l0 && make test-stage2 TESTS="l0c_stage2_test_env_isolation_test"` must still PASS. This
  confirms no off-Windows regression but cannot reproduce the Windows spawn failure (`uv sync` succeeds on macOS/Linux).
- CI: the `windows-ucrt64` Unified CI job's `l0c_stage2_test_env_isolation_test.py` must pass. This is the authoritative
  check.
