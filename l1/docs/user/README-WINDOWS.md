# Dea/L<sub>1</sub> on Windows

The L1 Stage 2 development package targets MSYS2 UCRT64. Native compilation and stdlib/runtime preparation require a
compatible UCRT64 C compiler and host tools. Install MSYS2 from <https://www.msys2.org/>, then install GCC from its
UCRT64 shell:

```bash
pacman -S mingw-w64-ucrt-x86_64-gcc
```

The installed Dea compiler does not require Python, Make, upstream L0, or a bootstrap L1 compiler. Its executable still
requires the UCRT64 runtime DLLs, including `libwinpthread-1.dll`, for semantic-only commands such as `--check` and
`--gen`. Keep the UCRT64 `bin` directory on `PATH` even when no C compilation is needed.

## Using the package

From Command Prompt in the package directory:

```cmd
call bin\l1-env.cmd
l1c --version
l1c --check share\dea\l1\smoke\hello.l1
l1c --run share\dea\l1\smoke\hello.l1
```

The activation script discovers MSYS2 and adds the toolchain to `PATH`. Set `MSYS2_TOOLCHAIN_BIN` to select its `bin`
directory, or `MSYS2_ROOT` for a non-default MSYS2 installation. Set `L1_CC` to select a compatible C compiler
explicitly.

From MSYS2 UCRT64 bash in the package directory:

```bash
source ./bin/l1-env.sh
l1c --version
l1c --run share/dea/l1/smoke/hello.l1
```

The smoke program prints `hello from Dea L1`. Quote paths containing spaces. Direct `bin\l1c.cmd` invocation also works
without activation when the required native tools are available on `PATH`.

## Cache and relocation

Keep the complete prefix together when moving it. Native support is prepared in a writable per-user cache; it is not
written into the installed prefix. Select a cache explicitly with `--stdlib-cache` or `L1_STDLIB_CACHE`.

See [share/doc/dea/l1/toolchain.md][toolchain] for preparation, cache reuse, and installation repair, and
[README.md][readme] for the package overview.

[readme]: README.md
[toolchain]: share/doc/dea/l1/toolchain.md
