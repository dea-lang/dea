# Bug Fix Plan

## Shared env script virtualenv path stacking

- Date: 2026-07-02
- Status: Completed
- Title: Fix repo-local env script PATH stacking with stale virtualenv activation metadata
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 repo-local POSIX env script generation
  - L1 repo-local POSIX env script generation
- Origin: Shared launcher renderer in `scripts/dea_tooling/launchers.py`
- Porting rule: Fix the shared renderer once; L0 and L1 generated env scripts must not diverge
- Target status:
  - L0 repo-local POSIX env script generation: Implemented
  - L1 repo-local POSIX env script generation: Implemented
- Subsystem: Repo-local environment activation
- Modules:
  - `scripts/dea_tooling/launchers.py`
  - `l0/scripts/dist_tools_lib.py`
  - `l1/scripts/build_stage1_l1c.py`
- Test modules:
  - `l1/tests/test_env_stackability.py`
  - `l0/tests/test_make_dea_build_workflow.py`
- Repro: `make -C l1 test-env` after renaming a checkout while keeping the existing `.venv`

## Summary

Repo-local `l0-env.sh` and `l1-env.sh` scripts could lose a previously activated level `bin/` directory when the shared
monorepo `.venv/bin/activate` metadata was stale after a checkout rename. In the observed failure, `l0-env.sh` first
made `l0c` visible, then `l1-env.sh` sourced an activation script that still pointed at the old checkout path and
restored an older `PATH`, leaving only `l1c` visible.

The original stackability test covered repeated L0/L1 activation in bash with a healthy venv. It did not cover zsh or
the actual stale activation-file path produced by a renamed checkout.

## Root Cause

Python virtualenv activation scripts embed an absolute `VIRTUAL_ENV` path. When a checkout is renamed but `.venv` is
kept, sourcing `.venv/bin/activate` can export the old path and prepend the old `.venv/bin` to `PATH`. A later generated
env script can then treat the repo venv as inactive, re-source activation, and restore `_OLD_VIRTUAL_PATH` without the
previous level's `bin/`.

The first fix preserved enough `PATH` state for bash, but its helper relied on shell word splitting with `IFS=:`. That
does not split unquoted scalar parameters the same way in zsh, even though the generated env script supports zsh
sourcing.

## Scope of This Fix

1. Normalize repo-local POSIX env scripts after venv activation so the generated level `bin/` and repo `.venv/bin` are
   each present exactly once.
2. Make PATH normalization shell-portable for bash and zsh without relying on word-splitting behavior.
3. Correct stale `VIRTUAL_ENV` values after sourcing an activation script whose embedded path points at an old checkout.
4. Remove the stale old-venv `bin/` entry that such an activation script injects.
5. Keep Windows `.cmd` env-script generation unchanged.

## Approach

- Replace the PATH helper with colon scanning over the `PATH` string, removing all occurrences of an entry before
  prepending the desired entry.
- After sourcing `repo_venv/bin/activate`, if `VIRTUAL_ENV` differs from the repo-local venv path, remove the stale
  `VIRTUAL_ENV/bin` entry and export the repo-local `VIRTUAL_ENV`.
- Apply the same renderer behavior to both L0 and L1 because both levels consume `render_repo_env_script`.
- Extend `l1/tests/test_env_stackability.py` to run the activation matrix under bash and zsh when zsh is available.
- Add a fake renamed-monorepo fixture with a copied stale `.venv/bin/activate` so the regression covers the real failure
  mode without mutating the repository's actual `.venv`.

## Diagnostic Codes

No compiler diagnostics are added or changed. No diagnostic-code reservation is required.

## Non-Goals

- Recreating or repairing `.venv` from the `make venv` target.
- Changing Windows `l0-env.cmd` or `l1-env.cmd` behavior.
- Changing install-prefix env script behavior, which does not source the monorepo `.venv`.

## Verification Criteria

- `make -C l1 test-env` passes and covers bash plus zsh when zsh is installed.
- `make -C l1 test-all` passes.
- `l0/tests/test_make_dea_build_workflow.py` passes to confirm L0 repo-local env generation still works.
- Static checks confirm the Windows `.cmd` renderer is unchanged by the fix.

## Completion Notes

Implemented in the shared launcher renderer. The regression suite now covers repeated L0/L1 activation, stale
`VIRTUAL_ENV` state, zsh PATH splitting behavior, and a copied stale activation script from a renamed checkout. Windows
`.cmd` generation is unaffected because the change is confined to the POSIX repo-env renderer.
