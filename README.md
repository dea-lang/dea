# The Dea Programming Language.

> _A systems programming language, built one level at a time._

Welcome to the **Dea** programming language!

Dea is a systems programming language organized into levels with an explicit compiler lineage. After L0, each level has
one canonical compiler implemented in the preceding level.

The design is conservative by choice: a small, precisely specified language whose semantics leave no room for undefined
behavior. Operations are either well-defined or rejected - at compile time or with a named runtime error.

_Tertium non datur._

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE-MIT)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE-APACHE)

## Language Levels

This monorepo hosts Dea's language levels. Each level has its own compiler, runtime, standard library, and documentation
in a self-contained subtree:

| Level             | Directory    | Status                                                              |
| ----------------- | ------------ | ------------------------------------------------------------------- |
| Dea/L<sub>0</sub> | [`l0/`](l0/) | **Released** (`l0-v2.1.1`), self-hosted; the current stable Dea     |
| Dea/L<sub>1</sub> | [`l1/`](l1/) | **Development release** (`l1-v0.1.0`); compiler implemented in L0   |
| Dea/L<sub>2</sub> | [`l2/`](l2/) | **Initial independent level**; canonical compiler implemented in L1 |

**Dea/L0** is Dea's foundational level: small, UB-free, and sufficient to host its own compiler. It compiles to C99, is
self-hosted through its Stage 2 compiler, and remains the stable Dea toolchain. Start at [l0/README.md](l0/README.md)
for the L0 overview, quickstart, and language tour.

L0 `2.1.1` fixes ARC cleanup for comparison temporaries and improves AddressSanitizer test validation. See
[l0/docs/releases/2.1.1.md](l0/docs/releases/2.1.1.md) for release notes and compatibility guidance.

**Dea/L1** carries post-L0 language growth: wider fixed-width integer types, `float`/`double` with an explicit
floating-point contract, bitwise operators, top-level `const`, function pointer types, the `unsafe` function marker,
fixed-size arrays, export manifests, and selective/aliased imports, among others. Its L0-implemented canonical compiler
supports per-module generated C, compile-only `.o + .l1m` artifacts, verified standalone linking, and
multi-compilation-unit build/run, including ordered external-library, search-path, rpath, and raw driver arguments. It
uses the L0 Stage 2 compiler at build time; installed L1 use needs no L0 compiler or source checkout.

L1 `0.1.0` is the current development release, with standalone packages for Linux x86_64, macOS Intel and Apple Silicon,
and Windows x86_64 (UCRT64), plus matching offline HTML/PDF documentation. Download
[`l1-v0.1.0`](https://github.com/dea-lang/dea/releases/tag/l1-v0.1.0), then follow
[l1/docs/user/README.md](l1/docs/user/README.md). See [l1/docs/releases/0.1.0.md](l1/docs/releases/0.1.0.md) for release
notes, [l1/README.md](l1/README.md) for source development, and [l1/docs/roadmap.md](l1/docs/roadmap.md) for future
work.

**Dea/L2** starts from the former L1 Stage 2 implementation. Its canonical `l2c` compiles `.l2` programs, emits `.l2m`
interfaces, and owns its stdlib, runtime, and support inputs. Construction requires an explicit L1 toolchain, installed
by default or a development toolchain selected with `L2_BOOTSTRAP_MODE=development`; ordinary L2 use does not invoke it.
See [l2/README.md](l2/README.md).

## Stability and Evolution

Stability is defined per language level:

- **Dea/L0 is stable.** Its current release is `2.1.1`. Language, compiler CLI, and runtime compatibility changes follow
  L0's semantic versioning.
- **Dea/L1 is under active development.** Its current development release is `0.1.0`; it does not promise stable
  language, module-interface, or binary compatibility across future releases.
- **Dea/L2 is an independent development level.** Its canonical compiler is implemented in L1; it does not yet have a
  packaged release. Sustained L2 feature development is deferred until a stable L1 baseline is selected.

Current source development targets a finite L1 foundation for compilers and tools. Borrowed-slice safety, filesystem
operations, and wide time values are implemented. Dynamic byte buffers, file handles, secure entropy and temporary
objects, shell-free processes and pipes, typed string formatting, and semantic dependency discovery remain planned L1
work. General streams, networking, JSON, file watching, concurrency, and broader language features are deferred to L2.
See [l1/docs/roadmap.md](l1/docs/roadmap.md) for the stabilization boundary and acceptance requirements. The published
L1 0.1.0 feature baseline is recorded separately in [l1/docs/releases/0.1.0.md](l1/docs/releases/0.1.0.md).

L1 and L2 development does not change L0's stable status. Future breaking changes are documented and versioned within
the affected level.

## Versioning and Releases

Versions are scoped to one language level, not to the project as a whole:

- `l0-v2.1.1` is a release of **Dea/L0**. There is no "Dea 2.1.1"; a project-wide version number is intentionally not
  defined.
- `l1-v0.1.0` is a development release of **Dea/L1**; its publication does not change L0's stable status.
- Release tags are level-prefixed: L0 uses `l0-vX.Y.Z` and `l0-snapshot-*`; L1 uses `l1-vX.Y.Z` and `l1-snapshot-*`.
- Pre-monorepo bare tags such as `v0.9.0` and `v0.9.1` remain valid historical references to early L0 development.

The full release-tag and release-line gating policy lives in [MONOREPO.md](MONOREPO.md). Release-specific behavior and
migration guidance are recorded in [l0/docs/releases/2.1.1.md](l0/docs/releases/2.1.1.md) and
[l1/docs/releases/0.1.0.md](l1/docs/releases/0.1.0.md).

## The Bootstrap Chain

L0 retains its Python Stage 1 and self-hosted Stage 2. L1 has one compiler implemented in L0; L2 has one compiler
implemented in L1. L1/L2 have no intra-level stage selection, parity gate, or self-hosting requirement. Installed L1
operation is independent of its upstream L0 construction toolchain. L1 `0.1.0` is the first published canonical
L0-implemented L1 development toolchain.

The architectural rationale is recorded in [docs/decisions/](docs/decisions/), starting with
[docs/decisions/0022-single-compiler-level-lineage.md](docs/decisions/0022-single-compiler-level-lineage.md).

## Getting Started

For the L1 development release, download the package for your platform from
[`l1-v0.1.0`](https://github.com/dea-lang/dea/releases/tag/l1-v0.1.0) and follow the prerequisites and first-run
instructions in [l1/docs/user/README.md](l1/docs/user/README.md).

For the stable L0 toolchain, start from a fresh clone:

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
| `l0/`      | Dea/L0 compiler, runtime, docs, and tests            |
| `l1/`      | Dea/L1 compiler, runtime, docs, and tests            |
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
