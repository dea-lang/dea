# Dea Monorepo

This repository hosts the Dea language family as a monorepo.

## Root Workflow

The monorepo root owns a minimal maintenance `Makefile`:

```bash
make help   # show root-only monorepo targets
make venv   # create or sync the shared ./.venv (uv if available, pip fallback otherwise)
make test  # run each registered level's normal test entrypoint without dedicated broad trace sweeps
make test-all  # run each registered level's full test entrypoint
make clean  # clean each registered level plus root caches/artifacts
make clean-all  # run each level's full cleanup entrypoint plus root caches/artifacts
```

The root `Makefile` is not a dispatcher for focused level-specific targets. Use root `make test` for normal
registered-level validation without the dedicated broad trace sweeps and root `make test-all` for the full
trace-inclusive validation. Build, targeted test, docs, and compiler workflows should be run inside the relevant level
directory.

The repository is a single `uv` workspace: the root `pyproject.toml` declares `l0/` and `l1/` as members, owns the
shared dev/docs dependency groups, and produces a single root `uv.lock`. Level Makefiles' `venv` targets delegate to the
root, so `make venv` from any of `./`, `l0/`, or `l1/` converges on the same `./.venv`. `uv` is an optional accelerator:
when absent, `make venv` falls back to `python -m venv` plus `pip install` of the dependency-group specifiers extracted
from the root `pyproject.toml`.

## Language Levels

| Directory  | Description                                                   |
| ---------- | ------------------------------------------------------------- |
| `l0/`      | Dea/L0 language, compiler, runtime, docs, examples, and tests |
| `l1/`      | Dea/L1 bootstrap compiler, runtime, docs, examples, and tests |
| `editors/` | Shared editor grammars, fallback modes, tags, and tests       |
| `scripts/` | Monorepo-owned automation and shared helper modules           |
| `docs/`    | Dea-wide and monorepo-wide stable documentation               |
| `work/`    | Dea-wide and monorepo-wide plans and proposals                |
| `tools/`   | Vendored third-party dependencies                             |

Root-level stable documentation under [`docs/`](docs/) is reserved for Dea-wide and monorepo-wide reference/spec
material. Root-level lifecycle artifacts such as shared plans live under [`work/`](work/). Shared editor integrations,
the self-contained Tree-sitter grammar package, and their focused validation live under [`editors/`](editors/). Existing
user-facing L0 documentation remains under [`l0/`](l0/). Root-owned automation helpers live under
[`scripts/`](scripts/), while vendored third-party assets remain under [`tools/`](tools/).

## Release Tags

Pre-monorepo history keeps its original bare tags. Existing legacy tags such as `v0.9.0`, `v0.9.1`, and older
`snapshot*` releases remain valid historical references and are not renamed.

Monorepo releases use level-prefixed tags only:

- L0 stable releases: `l0-vX.Y.Z`
- L0 snapshots: `l0-snapshot-...`
- Future L1 stable releases: `l1-vX.Y.Z`
- Future L1 snapshots: `l1-snapshot-...`

Bare `v*` tags are therefore a closed pre-monorepo namespace. New monorepo releases should not dual-tag with bare `v*`.

## Release-line Gating Policy

L0 stable releases (`l0-v*`) and L0 snapshots (`l0-snapshot-*`) are the only currently active release workflows. L1
release namespaces (`l1-v*` and `l1-snapshot-*`) remain reserved but are not yet active.

The following conditions must be met before the first L1 release or snapshot workflow is added:

1. The L1 install/dist artifact contract must be defined and stable through the L1 bootstrap productization plan
   (`l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md`) or a successor.
2. The artifact must be smoke-testable from a clean install prefix, producing a working `l1c` launcher.
3. Release notes, tag gating, and smoke-test flow must be documented and reproducible in CI.
4. The existing `l1-v*` and `l1-snapshot-*` tag namespaces must not be used for any other purpose before the first
   deliberately prepared L1 release or snapshot.

An `l1-release.yml` or `l1-snapshot.yml` workflow that does not meet these conditions is not valid to add. L1 CI
validation (via `l1-ci.yml`) remains bootstrap-only until the above prerequisites exist.

## Working In `l0/`

Dea/L0 works as a self-contained project inside [`l0/`](l0/). From the monorepo root, `cd l0` before running build,
test, or docs commands.

- Dea-family monorepo overview: [`README.md`](README.md)
- Canonical L0 overview and quickstart: [`l0/README.md`](l0/README.md)
- L0 contributor guidance: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Repository security policy: [`SECURITY.md`](SECURITY.md)
- L0 AI guidance: [`l0/AGENTS.md`](l0/AGENTS.md)

For example:

```bash
make venv   # shared by all level subtrees
cd l0
make help
make test
make test-all
```

Third-party notices for shared vendored assets live at [`THIRD_PARTY_NOTICES`](THIRD_PARTY_NOTICES).

## Working In `l1/`

Dea/L1 currently exists as a bootstrap compiler subtree inside [`l1/`](l1/). From the monorepo root, `cd l1` before
running L1 bootstrap commands.

- L1 subtree pointer: [`l1/README.md`](l1/README.md)
- L1 AI guidance: [`l1/AGENTS.md`](l1/AGENTS.md)

Typical local bootstrap flow:

```bash
make venv
cd l1
make use-dev-stage1
source build/dea/bin/l1-env.sh
```
