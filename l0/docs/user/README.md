# The Dea Programming Language.

> _C-family syntax, UB-free semantics, ARC strings, sum types and pattern matching._

Welcome to the **Dea** programming language!

## Dea/L<sub>0</sub>

This archive contains the standalone Dea/L0 compiler distribution. Exact build and version metadata are recorded in the
bundled `VERSION` file.

## What is included

- `bin/` for the `l0c` launchers and environment helpers
- `examples/` for runnable example programs
- `docs/reference/` for the shipped language and compiler reference
- `shared/` for the bundled standard library and runtime assets

## Quick start

On POSIX shells:

```bash
source ./bin/l0-env.sh
l0c --version
```

Then try an example:

```bash
l0c -Rp examples --run hello
```

Or use the installed examples as a starting point for your own project:

```bash
l0c --build -Rp examples -o hello examples/hello.l0
```

On Windows, see [README-WINDOWS.md](README-WINDOWS.md) before using `--build` or `--run`; the validated Windows path
depends on the supported MSYS2 `UCRT64` or `MINGW64` MinGW-w64 GCC or Clang toolchain. `UCRT64` is recommended for new
setups.

## Reference docs

The bundled reference set is under `docs/reference/`.

Useful starting points:

- [Language grammar](docs/reference/grammar.md)
- [Project status](docs/project-status.md)
- [Standard library](docs/reference/standard-library.md)
- [Architecture](docs/reference/architecture.md)

For Windows-specific usage of the shipped archive, see [README-WINDOWS.md](README-WINDOWS.md).
