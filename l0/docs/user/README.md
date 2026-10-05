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
- `share/doc/dea/l0/autodocs/stage2/` for the offline Stage 2 HTML and PDF API reference
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

The bundled language reference is under `docs/reference/`. Open `share/doc/dea/l0/autodocs/stage2/html/index.html` for
the generated Stage 2 API reference, or `share/doc/dea/l0/autodocs/stage2/pdf/dea_l0_stage2_api_reference.pdf` for the
complete PDF. Stage 1 compiler autodocs are separate developer artifacts.

Useful starting points:

- [Language grammar](docs/reference/grammar.md)
- [Project status](docs/project-status.md)
- [Standard library](docs/reference/standard-library.md)
- [Architecture](docs/reference/architecture.md)

For Windows-specific usage of the shipped archive, see [README-WINDOWS.md](README-WINDOWS.md).
