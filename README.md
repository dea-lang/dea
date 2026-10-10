# The Dea Programming Language.

> _C-family syntax, UB-free semantics, ARC strings, sum types and pattern matching._

Welcome to the **Dea** programming language!

Dea is a systems programming language built through an explicit compiler lineage. After L0, each language level has one
canonical compiler implemented in the preceding level.

The design is conservative by choice: a small, precisely specified language whose semantics leave no room for undefined
behavior. Operations are either well-defined or rejected - at compile time or with a named runtime error.

_Tertium non datur._

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE-MIT)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE-APACHE)

## Language Levels

This repository is a monorepo hosting the Dea language family. Each level is a self-contained subtree:

| Level             | Directory    | Status                                                              |
| ----------------- | ------------ | ------------------------------------------------------------------- |
| Dea/L<sub>0</sub> | [`l0/`](l0/) | **Released** (`l0-v2.1.1`), self-hosted; the current stable Dea     |
| Dea/L<sub>1</sub> | [`l1/`](l1/) | **In development**; canonical compiler implemented in L0            |
| Dea/L<sub>2</sub> | [`l2/`](l2/) | **Initial independent level**; canonical compiler implemented in L1 |

**Dea/L0** is a small, UB-free systems language, compiling to C99, sufficient to host its own compiler. It is
self-hosted through its Stage 2 compiler and is the canonical user-facing toolchain today. Start at
[l0/README.md](l0/README.md) for the L0 overview, quickstart, and language tour.

L0 `2.1.1` fixes ARC cleanup for comparison temporaries and improves AddressSanitizer test validation. See
[l0/docs/releases/2.1.1.md](l0/docs/releases/2.1.1.md) for release notes and compatibility guidance.

**Dea/L1** carries post-L0 language growth: wider fixed-width integer types, `float`/`double` with an explicit
floating-point contract, bitwise operators, top-level `const`, function pointer types, the `unsafe` function marker,
fixed-size arrays, export manifests, and selective/aliased imports, among others. Its L0-implemented canonical compiler
supports per-module generated C, compile-only `.o + .l1m` artifacts, verified standalone linking, and
multi-compilation-unit build/run, including ordered external-library, search-path, rpath, and raw driver arguments. It
consumes the L0 Stage 2 compiler as its upstream toolchain and is not yet a release-bearing product. Start at
[l1/README.md](l1/README.md) and [l1/docs/roadmap.md](l1/docs/roadmap.md).

**Dea/L2** starts from the former L1 Stage 2 implementation. Its canonical `l2c` compiles `.l2` programs, emits `.l2m`
interfaces, and owns its stdlib, runtime, and support inputs. Construction requires an explicitly installed L1
toolchain; ordinary L2 use does not invoke it. See [l2/README.md](l2/README.md).

## Stability and Evolution

Dea is highly experimental, and the language itself is evolving daily. Dea/L0 `2.1.1` is the current stable release. The
2.0.0 major release completed the coordinated short-option migration and the move to wildcard-only `case` defaults,
while adding checked pointer validation modes and shared editor support. No level is immune from future breaking
changes; when they land, they are incorporated into that level's semantic versioning.

At any given moment:

- L1 and L2 are **development** levels; L1 feature plans remain owned by L1 pending individual placement review;
- the **stable** version of Dea is the highest released level/version (today: Dea/L0 `2.1.1`).

When Dea one day becomes production-ready, or at least reasonably stable, it will be announced. Until then, consider Dea
in constant evolution, even though its shape is progressively emerging.

## Versioning and Releases

Versions are scoped to one language level, not to the project as a whole:

- `l0-v2.1.1` is a release of **Dea/L0**. There is no "Dea 2.1.1"; a project-wide version number is intentionally not
  defined.
- Release tags are level-prefixed: `l0-vX.Y.Z` and `l0-snapshot-*` are active today; `l1-v*` and `l1-snapshot-*` are
  reserved but not yet active.
- Pre-monorepo bare tags such as `v0.9.0` and `v0.9.1` remain valid historical references to early L0 development.

The full release-tag and release-line gating policy lives in [MONOREPO.md](MONOREPO.md). Release-specific behavior and
migration guidance are recorded in [l0/docs/releases/2.1.1.md](l0/docs/releases/2.1.1.md).

## The Bootstrap Chain

L0 retains its Python Stage 1 and self-hosted Stage 2. L1 has one compiler implemented in L0; L2 has one compiler
implemented in L1. L1/L2 have no intra-level stage selection, parity gate, or self-hosting requirement. Installed L1
operation is independent of its upstream L0 construction toolchain. L1 0.1.0 remains the intended first canonical L1
development-toolchain release, pending fresh artifact acceptance and separately authorized hosted release work.

The architectural rationale is recorded in [docs/decisions/](docs/decisions/), starting with
[docs/decisions/0022-single-compiler-level-lineage.md](docs/decisions/0022-single-compiler-level-lineage.md).

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
make use-dev                  # auto-prepares the repo-local upstream L0 Stage 2 compiler
source build/dea/bin/l1-env.sh
```

See [l1/README.md](l1/README.md) for the current L1 workflow.

## Repository Layout

| Directory  | Description                                          |
| ---------- | ---------------------------------------------------- |
| `l0/`      | Dea/L0 language, compiler, runtime, docs, and tests  |
| `l1/`      | Dea/L1 bootstrap compiler, runtime, docs, and tests  |
| `l2/`      | Dea/L2 compiler, runtime, docs, and tests            |
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
