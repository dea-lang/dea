# Tool Plan

## Convert the monorepo to a uv workspace at the repo root

- Date: 2026-05-06
- Status: Completed
- Title: Convert the monorepo to a uv workspace at the repo root
- Kind: Tooling
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - Monorepo root Python tooling
  - L0 dev environment
  - L1 dev environment
  - GitHub Actions workflows
- Origin: Monorepo root tooling. The shape landed first at the root `pyproject.toml` and root `Makefile`; level
  Makefiles, both Dockerfiles, and the L0 workflow set followed.
- Porting rule: Mechanical. Level Makefiles delegate `venv` upward and no longer own sync logic; CI workflows sync the
  workspace at the repo root rather than per level.
- Target status:
  - Monorepo root Python tooling: Implemented
  - L0 dev environment: Implemented
  - L1 dev environment: Implemented
  - GitHub Actions workflows: Implemented
- Subsystem: Monorepo Python build/dev tooling, GNU Make level entrypoints, GitHub Actions workflow surface
- Modules:
  - `pyproject.toml` (new, repo root)
  - `Makefile` (root)
  - `l0/pyproject.toml`
  - `l0/Makefile`
  - `l1/pyproject.toml`
  - `l1/Makefile`
  - `MONOREPO.md`
  - `CLAUDE.md`
  - `l0/CLAUDE.md`
  - `l1/CLAUDE.md`
  - `.github/workflows/l0-ci.yml`
  - `.github/workflows/l0-snapshot.yml`
  - `.github/workflows/l0-release.yml`
  - `.github/workflows/l0-docs-validate.yml`
  - `.github/workflows/l0-docs-build.yml`
- Test modules:
  - `l0/` `make venv && make test-all` smoke (with uv on PATH)
  - `l0/` `make venv && make test-stage1` smoke (with uv masked, pip-fallback path)
  - `l1/` `make venv && make test-all` smoke (with uv on PATH)
  - L0 docs validate/build workflow runs on a PR that touches `uv.lock`
  - L0 CI matrix run after migration (Linux + macOS + Windows MSYS2)
- Related:
  - `MONOREPO.md`
  - `work/plans/tools/2026-04-02-l1-ci-release-line-noref.md`
- Repro: PyCharm 2026 monorepo mode opens the repo and offers to create `l0/.venv` and `l1/.venv` even when the shared
  `./.venv` is the configured interpreter. Pointing both module SDKs at the root `./.venv` does not work cleanly. The
  underlying fragility is independently observable: `l0/uv.lock` and `l1/uv.lock` already disagree on `pygments`
  (`>=2.20.0` vs `>=2.19.2`), so successive `make venv` runs in `l0/` and `l1/` can churn the shared `../.venv` between
  syncs.

## Summary

The repository currently has one shared `./.venv` at the root and two `pyproject.toml` files in `l0/` and `l1/`. Both
level Makefiles run `UV_PROJECT_ENVIRONMENT=../.venv uv sync --group dev --group docs` against the shared venv, while
each level keeps its own `uv.lock` (`l0/uv.lock`, `l1/uv.lock`). This is two uv projects writing into one venv, governed
by two independent lockfiles — the second sync wins. The dev/docs dep groups are already ~95% identical across the two
levels, so this works in practice but is fragile by construction and does not match any tool's native model, including
PyCharm's new monorepo support.

This plan reshapes the layout into a single uv workspace whose root is the repository root. `l0/` and `l1/` become
workspace members. Dev/docs dep groups move into a new root `pyproject.toml`. The single root `uv.lock` replaces both
level lockfiles. The root `Makefile` takes ownership of `make venv` with the same 3-tier
`uv → pip-existing-venv → python -m venv + pip` fallback that the level Makefiles have today, so uv stays an optional
accelerator and not a hard dependency.

## Current State

- Shared root venv: `./.venv` (created via either level's `make venv`).
- Level pyprojects: both `[tool.uv] package = false`; `[dependency-groups]` `dev` and `docs` carry the actual developer
  toolchain (`pre-commit`, `pytest`, `pytest-xdist`, `mdformat*`, `jinja2`, `PyYAML`, `pygments`).
- Per-level lockfiles: `l0/uv.lock`, `l1/uv.lock` — already drifted on `pygments`.
- Root `Makefile`: `venv` target iterates `l0/` and `l1/` and calls each level's `make venv`. The root does not own the
  venv.
- Level Makefiles (`l0/Makefile`, `l1/Makefile` ~lines 127–140 and ~lines 105–118 respectively): identical 3-tier
  fallback:
  1. `uv` on PATH → `UV_PROJECT_ENVIRONMENT=../.venv uv sync --group dev --group docs`
  2. uv absent, `../.venv` exists → `pip install` the loose dep-group specifiers (extracted via stdlib `tomllib` in
     `PIP_DEPS_CMD`)
  3. uv absent, no venv → `python -m venv` then same pip install
- `scripts/` at the repo root has no `pyproject.toml`; it is stdlib + a sibling `dea_tooling` package and is invoked via
  `$(PYTHON)` from level Makefiles.
- GitHub Actions surface using uv against the level pyprojects:
  - `.github/workflows/l0-ci.yml` (matrix CI; uses `astral-sh/setup-uv`).
  - `.github/workflows/l0-snapshot.yml` (snapshot release; sets up uv).
  - `.github/workflows/l0-release.yml` (release; sets up uv).
  - `.github/workflows/l0-docs-validate.yml` (PR validation; runs
    `UV_PROJECT_ENVIRONMENT=../.venv uv sync --group docs`; path filter watches `l0/uv.lock`).
  - `.github/workflows/l0-docs-build.yml` (docs build; runs `UV_PROJECT_ENVIRONMENT=../.venv uv sync --group docs`).

## Goal

- One uv workspace at the repo root, one root `uv.lock`, one root `./.venv`.
- Dev/docs dep groups live in the root `pyproject.toml`.
- `make venv` works identically with or without `uv` on PATH (preserve the pip fallback).
- PyCharm 2026 monorepo mode auto-detects `./.venv` and stops asking to create per-level venvs.
- CI workflows sync against the root pyproject and root `uv.lock`.

## Non-goals

- No change to runtime, compiler, or stdlib code.
- No change to release tagging or release artifact contents.
- No promotion of `scripts/` to a workspace member (deferred; see Open Questions).
- No upgrade of the dev/docs dep specifiers themselves; existing `>=` floors are carried over verbatim, taking the
  higher floor where l0 and l1 differ today (e.g. `pygments>=2.20.0`).
- No migration of legacy bare `v*` release tags or any other release-namespace work.

## Approach

### Phase 1 — Add root pyproject and reshape level pyprojects

- Create `pyproject.toml` at the repo root with:
  - `[project]` minimal metadata: `name = "dea-monorepo"`, `version = "0.0.0"`, `requires-python = ">=3.14"`, no runtime
    dependencies.
  - `[tool.uv] package = false`.
  - `[tool.uv.workspace] members = ["l0", "l1"]`.
  - `[dependency-groups]` `dev` and `docs` carrying the union of today's level groups (use the higher floor when l0 and
    l1 differ).
- Trim `l0/pyproject.toml` and `l1/pyproject.toml`:
  - Keep `[project]` (current name/version, `requires-python`).
  - Keep `[tool.uv] package = false`.
  - Keep `[tool.pytest.ini_options]` (each level needs its own `testpaths` and `addopts`).
  - Remove `[dependency-groups]`. The pip fallback only reads one pyproject; uv resolves the workspace at the root.
- Delete `l0/uv.lock` and `l1/uv.lock`. Commit a fresh root `uv.lock` produced by `uv sync --all-groups` from the repo
  root.

### Phase 2 — Move venv ownership into the root Makefile

- Move `_check-python` and `PIP_DEPS_CMD` from each level Makefile into the root `Makefile`.
- Implement the root `venv` target with the same 3-tier fallback the level Makefiles have today, but rooted at the repo
  root:
  1. uv present → `uv sync --quiet --all-groups` from the repo root (writes to `./.venv` by default; optionally still
     export `UV_PROJECT_ENVIRONMENT=$(abspath ./.venv)` to be explicit).
  2. uv absent, `./.venv` exists → `./.venv/bin/python -m pip install` the dep-group specifiers extracted from the root
     `pyproject.toml` via `PIP_DEPS_CMD`.
  3. uv absent, no `./.venv` → `python3 -m venv ./.venv` then same pip install.
- Replace each level Makefile's `venv` target with `$(MAKE) -C .. venv`. Keep `VENV_DIR := $(abspath ../.venv)`,
  `VENV_PYTHON`, and `$(PYTHON)` as today; targets like `test-stage1`, `dist`, `refresh-goldens` continue to invoke
  `$(VENV_PYTHON)` / `$(PYTHON)` against `../.venv` as they do now.
- Drop the now-unused `VENV_UV_FLAGS`, `VENV_PIP_FLAGS`, `VENV_QUIET_LABEL`, `_check-python`, and `PIP_DEPS_CMD` from
  the level Makefiles (or leave a thin alias if cleaner).

### Phase 3 — Update GitHub workflows

For each of `l0-ci.yml`, `l0-snapshot.yml`, `l0-release.yml`, `l0-docs-validate.yml`, `l0-docs-build.yml`:

- Continue using `astral-sh/setup-uv@v7`.
- Adjust `cache-suffix` strings only if needed for cache-key invalidation around the lockfile move.
- Replace any `UV_PROJECT_ENVIRONMENT=../.venv uv sync ...` step that runs from `l0/` with a root-level
  `uv sync --all-groups` (or `--group docs` for the docs workflows). Equivalent: invoke `make venv` from the repo root.
- For `l0-docs-validate.yml`, change the path filter from `l0/uv.lock` to `uv.lock` (root). Also add `pyproject.toml` at
  the repo root to the same path filter so dep-group changes still trigger validation.
- Anywhere a workflow `cd`s into `l0/` immediately after sync, the sync step itself can move up to the root; the rest of
  the level-local commands stay unchanged.
- The MSYS2 setup blocks that install `mingw-w64-ucrt-x86_64-uv` and `python-pip` continue to install both — uv stays
  optional, and the pip-fallback path remains available.

### Phase 4 — Documentation updates

- `MONOREPO.md`: describe the workspace model, the new root-owned `make venv`, and the single root `uv.lock`. Update the
  existing "Working In `l0/`" / "Working In `l1/`" snippets that mention `make venv`.
- `CLAUDE.md` (root): update the "Shared Environment" section to reflect that the root `Makefile` owns `make venv`, and
  that levels delegate upward.
- `l0/CLAUDE.md`: rewrite the "Environment & Setup" / "Manual Environment Setup" paragraph. The new manual recipe is
  "create `./.venv` at root, then `./.venv/bin/pip install <deps from root pyproject.toml dependency-groups>`", or
  alternatively `uv sync --all-groups` from the root. Keep the `pre-commit install` invocation but adjust paths if
  needed.
- `l1/CLAUDE.md`: corresponding updates to the `make venv` and shared-`.venv` references.

## Verification Criteria

Run all checks from a clean tree (`rm -rf .venv l0/uv.lock l1/uv.lock`).

1. **With uv:** `make venv` from the repo root succeeds, creates exactly one `./.venv`, and writes a single root
   `uv.lock`. `cd l0 && make venv` and `cd l1 && make venv` are now no-ops that delegate upward and converge on the same
   `./.venv`.
2. **Without uv:** mask uv on PATH (`PATH=$(echo $PATH | tr ':' '\n' | grep -v '/uv$' | paste -sd: -)` or rename the
   binary), `rm -rf .venv`, then `make venv` from the repo root creates `./.venv` via `python3 -m venv` and pip-installs
   all dep-group specifiers. From `./.venv/bin/python`, all of `pytest`, `pre_commit`, `mdformat`, `jinja2`, `yaml`, and
   `pygments` import.
3. **L0 smoke:** `cd l0 && make test-all` passes after the migration, both with and without uv.
4. **L1 smoke:** `cd l1 && make test-all` passes after the migration with uv on PATH.
5. **L0 docs:** `cd l0 && python scripts/gen_docs.py --strict` runs to completion using the root `./.venv`.
6. **PyCharm:** open the repo root in PyCharm 2026; the IDE auto-selects `./.venv` as the project interpreter; `l0/` and
   `l1/` resolve their imports without prompting to create level-local venvs.
7. **Pre-commit:** the invocation documented in `l0/CLAUDE.md`
   (`uv run --directory l0 --group dev pre-commit install -c .pre-commit-config.yaml`) still installs and runs the
   hooks; alternatively the root-rooted equivalent works.
8. **CI matrix:** the L0 CI workflow run on the migration branch succeeds across Linux, macOS, and Windows MSYS2; the L0
   docs validate and build workflows run, including a PR commit that touches the root `uv.lock` to confirm the new path
   filter triggers them.

## Open Questions

- Should `scripts/` be promoted to a third workspace member with its own `pyproject.toml`? Currently stdlib-only, so the
  answer is no for this plan; revisit when `dea_tooling` grows real deps.
- Should we add a CI job that explicitly exercises the uv-less fallback so it does not silently rot? Recommended but out
  of scope for this plan; if approved, open a follow-up `tools/` plan for it.

## Completion Notes

- Root `pyproject.toml` declares `[tool.uv.workspace] members = ["l0", "l1"]`, `[tool.uv] package = false`, and the
  union of dev/docs dependency groups (taking the higher floor where l0 and l1 differed; e.g. `pygments>=2.20.0`).
- Single root `uv.lock` replaces the deleted `l0/uv.lock` and `l1/uv.lock`.
- Level `pyproject.toml` files now keep only `[project]`, `[tool.uv] package = false`, and `[tool.pytest.ini_options]`.
- Root `Makefile` owns `make venv` with the same 3-tier `uv → pip-existing → python -m venv + pip` fallback that the
  level Makefiles previously implemented; `_check-python` and `PIP_DEPS_CMD` moved to the root.
- Level `Makefile` `venv` targets reduced to `$(MAKE) -C .. venv`.
- Both Dockerfiles updated to copy the root `pyproject.toml`, root `uv.lock`, every workspace member `pyproject.toml`,
  and the root `Makefile`; sync uses `uv sync --frozen --all-groups` from the workspace root. `l0/Makefile` gained a
  `test-docker` target mirroring `l1/Makefile`.
- All five GitHub workflows updated: `cache-suffix` bumped with a `-ws` suffix; `l0-docs-validate.yml` and
  `l0-docs-build.yml` now run `uv sync --group docs` from `${{ github.workspace }}`; `l0-docs-validate.yml` path filter
  switched from `l0/uv.lock` to `uv.lock` plus `pyproject.toml` at the repo root.
- Documentation refreshed across `MONOREPO.md`, root `CLAUDE.md`, `l0/CLAUDE.md`, `README.md`, `CONTRIBUTING.md`, and
  `.github/copilot-instructions.md`. `l1/CLAUDE.md` already defers to root and needed no changes. The pre-commit
  invocation moved from `uv run --directory l0 --group dev ...` to root-rooted `uv run --group dev ...` because
  `--group dev` is now declared only at the workspace root.
- Verification performed: `make venv` from root with uv produces a single `./.venv` and root `uv.lock` and all dev/docs
  imports succeed; the same target with uv masked falls through to `python -m venv` + `pip install` and the same imports
  succeed; `cd l0 && make venv` and `cd l1 && make venv` delegate upward and converge on the shared venv;
  `cd l1 && make test-docker` and the L0 test suite both pass.
- `scripts/` remains an informal stdlib-only module set; promoting it to a workspace member is deferred.
