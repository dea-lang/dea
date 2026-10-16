# Dea/L1

> _C-family syntax, modules and separate compilation, checked arrays and slices, nullable types, and ARC-managed
> strings._

**Dea/L1** is level one of the Dea systems programming language (see [README.md](../README.md)). Its `l1c` compiler
translates `.l1` programs through C into native executables. The canonical compiler is implemented in L0; L1 is also the
implementation language for the next level's compiler, L2.

**Development status:** [L1 0.1.0](https://github.com/dea-lang/dea/releases/tag/l1-v0.1.0) is the current published
development release. Its feature baseline and compatibility limitations are recorded in
[l1/docs/releases/0.1.0.md](docs/releases/0.1.0.md). This development release does not promise stable language,
module-interface, or binary compatibility across future releases. L0 remains the stable toolchain.

This README covers the source tree and development workflow. For packaged compiler usage, see
[l1/docs/user/README.md](docs/user/README.md), which becomes the README in each installed toolchain. Published L1
packages appear under `l1-v*` or `l1-snapshot-*` tags on the
[public release page](https://github.com/dea-lang/dea/releases).

## Motivation

L0 provides a small, bootstrap-friendly foundation for implementing compilers. L1 builds on that foundation with a
broader set of numeric types, arrays and slices, and a module system that supports separately compiled components. These
facilities make it practical to build the next compiler level and larger systems programs without treating every build
as a single compilation unit.

The language keeps explicit types, familiar control flow, nullable values, and deterministic resource management.
Strings use automatic reference counting (ARC); non-owning slices provide views into existing storage. Language
semantics aim to avoid undefined behavior, rejecting invalid operations statically where possible and checking them at
runtime otherwise. C is the portable compilation target, with platform-dependent behavior concentrated in the runtime.

L1's language and runtime are owned by this subtree. L0 supplies the compiler used to build `l1c`; it is not needed to
use an installed L1 toolchain. See [l1/docs/reference/design-decisions.md](docs/reference/design-decisions.md) for the
language and runtime rationale.

## Design highlights

- Modules have explicit exports, alias imports, and selective imports. Verified `.l1m` interfaces describe their public
  declarations and dependencies.
- Separate compilation produces an object and its sibling interface. Build tools can reuse those pairs without
  recompiling provider sources.
- Fixed-size arrays `T[N]` and non-owning slices `T[]` support checked indexing, `len`, and `slice`. Slices are
  escape-restricted views; general owning dynamic buffers and escape-capable slices remain outside the current language.
- `T?` expresses nullability. Structs, enums, and `match` support explicit data modeling and variant handling.
- Signed and unsigned integer types, bitwise operations, `float`, and `double` support numeric and systems code.
- ARC-managed strings, `new` / `drop`, and `with` / `cleanup` provide explicit ownership and cleanup facilities.
- Function pointers and L1-defined variadic functions support indirect calls and typed argument packs.

The standard library covers I/O, strings, paths, filesystems, time, randomness, containers, and numeric helpers. See
[l1/docs/reference/grammar.md](docs/reference/grammar.md),
[l1/docs/reference/ownership.md](docs/reference/ownership.md), and
[l1/docs/reference/standard-library.md](docs/reference/standard-library.md) for the language and library contracts.

## Building the development compiler

Run the build, compiler, and test commands below from the repository's **`l1/` directory**, unless a command explicitly
changes directory.

You need Python 3.14 or newer, Make, a supported C compiler/linker and host tools, and an L0 Stage 2 bootstrap compiler.
`uv` is optional: Make creates or reuses the shared repository environment at `../.venv`.

Use a supported GCC toolchain or capability-verified Clang/Apple Clang. Validated Debian Clang 14/15 support managed
preparation through an isolated empty configuration; modern Clang uses `--no-default-config`. See
[l1/docs/reference/stdlib-preparation.md](docs/reference/stdlib-preparation.md) for reuse requirements and tested scope.
Windows development uses MSYS2 UCRT64. `L0_CC` selects the C compiler used while building L1 through L0; `L1_CC` selects
it for L1 native program builds and defaults `L1_RUNTIME_CC`. See [l1/AGENTS.md](AGENTS.md) for the full
compiler-selection requirements and [l0/README.md](../l0/README.md) for L0 setup.

Select an existing L0 Stage 2 compiler by absolute path, then build and activate L1:

```bash
export L1_BOOTSTRAP_L0C=/absolute/path/to/l0c-stage2
make use-dev
source build/dea/bin/l1-env.sh
l1c --version
l1c --check -Rp examples hello
l1c --run -Rp examples hello
```

The example prints greetings in 25 languages. `make use-dev` includes `make build` and prepares the development
launchers. Native program builds prepare matching standard-library and runtime support on demand in a writable cache;
the first run can take longer.

If `L1_BOOTSTRAP_L0C` is unset, Make uses `../l0/build/dea/bin/l0c-stage2`, preparing it with
`make -C ../l0 use-dev-stage2` if needed. An invalid explicit selection fails; an ambient `l0c` on `PATH` is not
selected automatically.

## Language and build examples

A minimal L1 program:

```l1
module hello;

import std.io;

func main() {
    printl_s("Hello, L1!");
}
```

Save it as `hello.l1` in a scratch directory and use the activated compiler there:

```bash
l1c --check hello.l1
l1c --run hello.l1
l1c --gen hello.l1 -o hello.c
l1c --compile hello.l1 -o hello.o
l1c --link hello.o -o hello
./hello
```

`--gen` exposes the generated C. `--compile` produces `hello.o` and `hello.l1m`; keep that pair together. `--link`
consumes the pair and matching providers to create the executable. On Windows, use `-o hello.exe` for the link step and
run `./hello.exe`.

Back in `l1/`, explore the repository examples:

```bash
l1c --run -Rp examples hello
l1c --run -Rp examples slices
```

[l1/examples/hello.l1](examples/hello.l1) prints multilingual greetings using arrays and randomness;
[l1/examples/slices.l1](examples/slices.l1) demonstrates slice views and shared mutations. For a small incremental build
that reuses a separately compiled module, follow [l1/examples/make/README.md](examples/make/README.md).

## Compiler architecture and source layout

The compiler parses `.l1` sources, resolves a graph of source modules and verified interfaces, performs semantic
analysis, and generates C per module. Build/run modes compile source-backed modules and link them with interface-backed
providers through the common linker path. Compile-only mode requires interfaces for imports; standalone linking uses
`.l1m` metadata for Dea dependency and lifecycle checks and delegates native object compatibility to the host linker.

| Path                         | Purpose                                                           |
| ---------------------------- | ----------------------------------------------------------------- |
| `compiler/src/`              | Canonical compiler implementation in `.l0`                        |
| `compiler/support/`          | Native support for the compiler                                   |
| `compiler/tests/`            | Compiler implementation tests and fixtures                        |
| `compiler/shared/l1/stdlib/` | L1 standard library in `.l1`                                      |
| `compiler/shared/runtime/`   | L1 C runtime and public headers                                   |
| `scripts/` and `tests/`      | Build, installation, documentation, and tooling helpers and tests |
| `examples/`                  | L1 programs and build examples                                    |
| `docs/` and `work/`          | Stable references, decisions, roadmap, and development plans      |

See [l1/docs/reference/architecture.md](docs/reference/architecture.md) for pass structure,
[l1/docs/reference/c-backend-design.md](docs/reference/c-backend-design.md) for C lowering, and
[l1/docs/reference/separate-compilation.md](docs/reference/separate-compilation.md) for artifact and linking contracts.
Native support preparation is described in
[l1/docs/reference/stdlib-preparation.md](docs/reference/stdlib-preparation.md).

## Development validation

Start with a focused test when changing one compiler subsystem:

```bash
make test-compiler TESTS="parser_test"
```

Choose broader validation according to the change:

| Command                    | Coverage                                                                                  |
| -------------------------- | ----------------------------------------------------------------------------------------- |
| `make test`                | Fast local compiler, example, and tooling gate                                            |
| `make test-extended`       | Complete normal compiler suite, examples, and tooling                                     |
| `make test-ci`             | Exhaustive compiler validation, including CI-only, environment, trace, and child fixtures |
| `make check-examples`      | Example-program checks                                                                    |
| `make test-productization` | Installation and archive fixtures                                                         |

Ownership, runtime, and generated-cleanup changes also need relevant trace validation, for example
`make test-compiler-trace TESTS="lexer_test"` for that test's trace run. Actual distribution acceptance is a separate
`make test-productization-acceptance` gate; ordinary compiler tests do not establish it. Follow
[l1/AGENTS.md](AGENTS.md) and [AGENTS.md](../AGENTS.md) for change-specific validation and contribution requirements.

## Documentation and direction

- [l1/docs/user/linking.md](docs/user/linking.md): external libraries and native linking options.
- [docs/specs/compiler/cli-contract.md](../docs/specs/compiler/cli-contract.md): shared compiler CLI contract.
- [l1/docs/specs/compiler/module-interface-format.md](docs/specs/compiler/module-interface-format.md): `.l1m` format.
- [l1/docs/README.md](docs/README.md): documentation layout and offline reference generation.
- [l1/docs/releases/0.1.0.md](docs/releases/0.1.0.md): release feature baseline and limitations.
- [l1/docs/roadmap.md](docs/roadmap.md) and [l1/docs/project-status.md](docs/project-status.md): direction and current
  status.
- [l1/docs/decisions/INDEX.md](docs/decisions/INDEX.md): recorded architectural decisions.
- [editors/README.md](../editors/README.md): shared editor support.

## License

Dea is dual-licensed under [LICENSE-MIT](../LICENSE-MIT) and [LICENSE-APACHE](../LICENSE-APACHE).
