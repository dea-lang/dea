# The Dea Programming Language

> _C-family syntax, UB-free semantics, ARC strings, sum types and pattern matching._

## Dea/L<sub>1</sub>

This package contains the standalone, self-hosted Dea/L1 Stage 2 development compiler. The package version does not
imply stable language or toolchain maturity. Exact build and version metadata are recorded in [VERSION].

## What is included

- `bin/` for the `l1c` launchers and environment helpers
- `interfaces/` for bundled semantic interfaces
- `shared/` for standard library and runtime rebuild sources
- `include/` for public runtime headers
- `share/dea/l1/smoke/hello.l1` for a runnable smoke program
- `share/doc/dea/l1/toolchain.md` for usage, native preparation, cache controls, and relocation instructions

The compiler needs no Python, Make, upstream L0, or bootstrap L1 compiler. Native compilation and stdlib preparation
require a compatible host C compiler/linker and host tools. GCC and upstream Clang 16+ are supported; Apple Clang must
support the compiler's configuration controls.

## Quick start

From the package directory in bash or zsh:

```bash
source ./bin/l1-env.sh
l1c --version
l1c --check share/dea/l1/smoke/hello.l1
l1c --run share/dea/l1/smoke/hello.l1
```

The smoke program prints `hello from Dea L1`. To build an executable:

```bash
l1c --build share/dea/l1/smoke/hello.l1 -o hello
./hello
```

On Windows, see [README-WINDOWS.md][windows] before using native build/run commands. The L1 Windows package targets
MSYS2 UCRT64.

## Reference docs

See the bundled [share/doc/dea/l1/toolchain.md][toolchain] for native preparation, writable cache selection, and
relocation. Keep the entire prefix together when moving it. Activation is optional; direct launcher invocation works
from any directory.

Distribution archives include autodocs; direct installations may omit them. Open
`share/doc/dea/l1/autodocs/stage2/html/index.html` for the offline HTML reference or
`share/doc/dea/l1/autodocs/stage2/pdf/dea_l1_stage2_api_reference.pdf` for the full PDF. Compiler-only installations
omit these optional files.

Project source and reference documentation are available at <https://github.com/dea-lang/dea>.

## Licensing

See [LICENSE-MIT][mit], [LICENSE-APACHE][apache], and [THIRD_PARTY_NOTICES][notices].

[apache]: LICENSE-APACHE
[mit]: LICENSE-MIT
[notices]: THIRD_PARTY_NOTICES
[toolchain]: share/doc/dea/l1/toolchain.md
[version]: VERSION
[windows]: README-WINDOWS.md
