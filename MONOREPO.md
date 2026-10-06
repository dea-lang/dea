# Dea Monorepo

This repository hosts the Dea language family as a monorepo.

## Root Workflow

The monorepo root owns a minimal maintenance `Makefile`:

```bash
make help   # show root-only monorepo targets
make venv   # create or sync the shared ./.venv (uv if available, pip fallback otherwise)
make test  # run each registered level's normal test entrypoint
make test-extended  # run each registered level's extended validation entrypoint
make clean  # clean each registered level plus root caches/artifacts
make clean-all  # run each level's full cleanup entrypoint plus root caches/artifacts
```

The root `Makefile` is not a dispatcher for focused level-specific targets. Root `make test` and `make test-extended`
delegate to each registered level. Extended coverage varies by level: L0 adds its dedicated Stage 2 trace sweep; L1 runs
its Stage 1 and Stage 2 normal suites. Use `make -C l1 test-ci` for exhaustive L1 coverage. Build, targeted test, docs,
and compiler workflows should be run inside the relevant level directory.

The repository is a single `uv` workspace: the root `pyproject.toml` declares `l0/` and `l1/` as members, owns the
shared dev/docs dependency groups, and produces a single root `uv.lock`. Level Makefiles' `venv` targets delegate to the
root, so `make venv` from any of `./`, `l0/`, or `l1/` converges on the same `./.venv`. `uv` is an optional accelerator:
when absent, `make venv` falls back to `python -m venv` plus `pip install` of the dependency-group specifiers extracted
from the root `pyproject.toml`.

## Language Levels

| Directory  | Description                                                   |
| ---------- | ------------------------------------------------------------- |
| `l0/`      | Dea/L0 language, compiler, runtime, docs, examples, and tests |
| `l1/`      | Dea/L1 compiler stages, runtime, docs, examples, and tests    |
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

The following prerequisites must be met before the first L1 release or snapshot workflow is added:

1. L1 `make install` and `make dist` must be implemented with a stable artifact contract through
   [l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md](l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md)
   or a successor.
2. The exact archive-path output and reusable installed/archive smoke command must be documented and validated from a
   clean, relocated prefix on Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64. The installed `l1c` must work
   without source-worktree dependencies, preparing native support in a separate writable cache. Distribution archives
   must include verified Stage 2 HTML/PDF from
   [l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md](l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md),
   built from the same source/version; Stage 1 autodocs remain separate developer outputs.
3. Tag validation, conversion to `DEA_DIST_VERSION`, release-note baselines, publication behavior, and the smoke-test
   flow must be documented and reproducible in CI. These contracts are specified in
   [work/plans/tools/2026-05-12-l1-gha-release-snapshot-workflows-noref.md](work/plans/tools/2026-05-12-l1-gha-release-snapshot-workflows-noref.md).
4. The existing `l1-v*` and `l1-snapshot-*` tag namespaces must not be used for any other purpose before the first
   deliberately prepared L1 release or snapshot. Check the authoritative remote tag state before activation; historical
   checks and local tag lists are insufficient.

An `l1-release.yml` or `l1-snapshot.yml` workflow that does not meet these conditions is not valid to add. L1 CI
validation (via `l1-ci.yml`) covers both compiler stages and the strict self-hosting fixed point independently of these
release prerequisites.

Workflow review, local syntax/policy validation, and hosted acceptance follow implementation. A successful manual
dispatch is not a prerequisite for writing the workflow. GitHub manual dispatch requires the workflow to exist on the
default branch before the first hosted check. Local validation does not establish successful hosted publication.

Hosted acceptance requires one deliberately prepared snapshot and one versioned release, each building and smoke-testing
all four archives before publication. Follow the separate tag-creation, tag-push, and remote-write authorization gates
in [AGENTS.md](AGENTS.md); implementing the plan does not authorize those actions. Snapshot dispatch with
`publish_release=false` still creates/pushes a tag and uploads a draft release, so it also requires authorization. If
hosted acceptance is deferred, record implementation and pending acceptance separately and leave the workflow plan open.
Do not create a dummy stable tag to close it.

Delivery documentation must distinguish workflow availability, verified publication, and product maturity. Initial L1
archives contain only the self-built Stage 2 compiler, its toolchain assets, and Stage 2 HTML/PDF documentation,
including `VERSION` and the install manifest. Release assets also include the Stage 2 docs bundle, matching PDF, and
checksums. Stage 1 remains a bootstrap/development tool. Both GitHub release types retain Stage 2 development
identification and set `make_latest=false`, preserving L0's latest-release selection. Publishing an L1 GitHub Release
does not by itself declare language or toolchain stability.

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
make test-extended
```

Third-party notices for shared vendored assets live at [`THIRD_PARTY_NOTICES`](THIRD_PARTY_NOTICES).

## Working In `l1/`

Dea/L1 currently provides bootstrap and self-hosted compiler stages inside [`l1/`](l1/). From the monorepo root, `cd l1`
before running L1 bootstrap commands.

- L1 subtree pointer: [`l1/README.md`](l1/README.md)
- L1 AI guidance: [`l1/AGENTS.md`](l1/AGENTS.md)

Typical local bootstrap flow:

```bash
make venv
cd l1
make use-dev-stage2
source build/dea/bin/l1-env.sh
```
