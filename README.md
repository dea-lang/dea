# The Dea Programming Language.

> _C-family syntax, UB-free semantics, ARC strings, sum types and pattern matching._

Welcome to the **Dea** programming language!

Dea is a systems programming language built through a staged bootstrap chain: each language level is compiled by the
previous one, self-hosts, and then becomes the compiler base for the next level.

The design is conservative by choice: a small, precisely specified language whose semantics leave no room for undefined
behavior. Operations are either well-defined or rejected - at compile time or with a named runtime error.

_Tertium non datur._

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE-MIT)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE-APACHE)

## Language Levels

This repository is a monorepo hosting the Dea language family. Each level is a self-contained subtree:

| Level             | Directory    | Status                                                          |
| ----------------- | ------------ | --------------------------------------------------------------- |
| Dea/L<sub>0</sub> | [`l0/`](l0/) | **Released** (`l0-v1.1.0`), self-hosted; the current stable Dea |
| Dea/L<sub>1</sub> | [`l1/`](l1/) | **In bootstrap development**; the current Dea bleeding edge     |

**Dea/L0** is a small, UB-free systems language, compiling to C99, sufficient to host its own compiler. It is
self-hosted through its Stage 2 compiler and is the canonical user-facing toolchain today. Start at
[l0/README.md](l0/README.md) for the L0 overview, quickstart, and language tour.

**Dea/L1** carries post-L0 language growth: wider fixed-width integer types, `float`/`double` with an explicit
floating-point contract, bitwise operators, top-level `const`, function pointer types, the `unsafe` function marker,
fixed-size arrays, export manifests, and selective/aliased imports, among others. Its L0-implemented bootstrap compiler
(`stage1_l0`) now supports per-module generated C, compile-only `.o + .l1m` artifacts, verified standalone linking, and
multi-compilation-unit build/run. It consumes the L0 Stage 2 compiler as its upstream toolchain and is not yet a
release-bearing product. Start at [l1/README.md](l1/README.md) and [l1/docs/roadmap.md](l1/docs/roadmap.md).

## Stability and Evolution

Dea is highly experimental, and the language itself is evolving daily. Dea/L0 is quite stable as of its `1.1.0` release,
but no level is immune from breaking changes; when breaking changes land, they are properly incorporated into that
level's semantic versioning. The current L0 development line targets `2.0.0` because it includes a coordinated breaking
CLI alias migration; `1.1.0` remains the latest released version.

At any given moment:

- the **bleeding edge** of Dea is the highest language level at its latest commit (today: Dea/L1 on the development
  branch);
- the **stable** version of Dea is the highest released level/version (today: Dea/L0 `1.1.0`).

When Dea one day becomes production-ready, or at least reasonably stable, it will be announced. Until then, consider Dea
in constant evolution, even though its shape is progressively emerging.

## Versioning and Releases

Versions are scoped to one language level, not to the project as a whole:

- `l0-v1.1.0` is a release of **Dea/L0**. There is no "Dea 1.1"; a project-wide version number is intentionally not
  defined.
- Release tags are level-prefixed: `l0-vX.Y.Z` and `l0-snapshot-*` are active today; `l1-v*` and `l1-snapshot-*` are
  reserved but not yet active.
- Pre-monorepo bare tags such as `v0.9.0` and `v0.9.1` remain valid historical references to early L0 development.

The full release-tag and release-line gating policy lives in [MONOREPO.md](MONOREPO.md).

## The Bootstrap Chain

Each Dea level implements its compiler in two stages: Stage 1 is written in an external host language (Python for L0, L0
itself for L1) and is the behavioral oracle; Stage 2 is written in the level's own language and, once mature, becomes
the primary delivery vehicle. **Level 0 is self-hosted today** and is the compiler base used to build L1; L1 will
subsequently self-host, and the process repeats for successive levels.

The architectural rationale is recorded in [docs/decisions/](docs/decisions/), starting with
[docs/decisions/0001-two-stage-architecture.md](docs/decisions/0001-two-stage-architecture.md).

## Getting Started

The practical entry point today is Dea/L0. From a fresh clone:

```shell
make venv   # create the shared repo-local virtual environment
cd l0       # all L0 build/test/install workflows run from here
```

Then follow the install and quickstart instructions in [l0/README.md](l0/README.md). For Windows-specific setup, see
[l0/README-WINDOWS.md](l0/README-WINDOWS.md).

For L1 bootstrap development:

```shell
make venv
cd l1
make use-dev-stage1            # auto-prepares the repo-local upstream L0 Stage 2 compiler
source build/dea/bin/l1-env.sh
```

See [l1/README.md](l1/README.md) for the current L1 workflow.

## Repository Layout

| Directory  | Description                                          |
| ---------- | ---------------------------------------------------- |
| `l0/`      | Dea/L0 language, compiler, runtime, docs, and tests  |
| `l1/`      | Dea/L1 bootstrap compiler, runtime, docs, and tests  |
| `editors/` | Shared editor grammars, modes, indexes, and fixtures |
| `scripts/` | Shared monorepo automation and helper modules        |
| `docs/`    | Dea-wide and monorepo-wide stable documentation      |
| `work/`    | Dea-wide and monorepo-wide plans and proposals       |
| `tools/`   | Vendored third-party dependencies                    |

Monorepo structure, the root maintenance `Makefile`, the shared `uv` workspace, and the release-tag policy are
documented in [MONOREPO.md](MONOREPO.md). Shared syntax highlighting, the in-repository Tree-sitter grammar, and
navigation-index setup live in [editors/README.md](editors/README.md). The Dea-wide status snapshot lives at
[docs/project-status.md](docs/project-status.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for developer workflow, setup, and validation commands, and
[SECURITY.md](SECURITY.md) for the security policy.

## License

[MIT](LICENSE-MIT) or [Apache 2.0](LICENSE-APACHE), at your option.

Third-party notices: [`THIRD_PARTY_NOTICES`](THIRD_PARTY_NOTICES).

## Author

[@googlielmo](https://github.com/googlielmo) a.k.a. `gwz`
